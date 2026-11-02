import logging
import uuid
from datetime import datetime

from celery import shared_task
from sqlalchemy import text

from workers.celery_app import celery_app
from engines.network_cpp.grpc_client import NetworkEngineClient
from backend.database.session import SessionLocal
from backend.services.normalization.normalizer import Normalizer
from backend.services.correlation.correlation_engine import CorrelationEngine
from backend.services.vulnerability_intelligence.nvd_client import VulnerabilityIntelligence
from backend.database.models.scan import Scan
from backend.database.models.observation import Observation


logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="tasks.run_network_scan", max_retries=3, acks_late=True)
def run_network_scan(
    self,
    tenant_id: str,
    scan_id: str,
    asset_id: str,
    target_ip: str,
    ports: list[int],
):
    db = SessionLocal()
    client = None

    try:
        db.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )

        scan = (
            db.query(Scan)
            .filter(
                Scan.id == uuid.UUID(str(scan_id)),
                Scan.tenant_id == uuid.UUID(str(tenant_id)),
            )
            .first()
        )
        if scan is None:
            raise ValueError(f"Scan {scan_id} not found for tenant {tenant_id}")

        scan.status = "RUNNING"
        scan.started_at = datetime.utcnow()
        scan.error_message = None
        db.commit()

        client = NetworkEngineClient()
        pending_observations = []
        processed_count = 0

        for event in client.start_scan(scan_id, target_ip, ports):
            if self.is_aborted():
                raise RuntimeError("Task aborted by worker shutdown or cancellation")

            observation = Normalizer.from_network_event(
                uuid.UUID(str(tenant_id)),
                uuid.UUID(str(scan_id)),
                uuid.UUID(str(asset_id)),
                event,
            )
            if observation is not None:
                pending_observations.append(observation)
                processed_count += 1

            if len(pending_observations) >= 500:
                db.bulk_save_objects(pending_observations)
                db.commit()
                pending_observations.clear()
                self.update_state(
                    state="PROGRESS",
                    meta={"processed_events": processed_count},
                )

        if pending_observations:
            db.bulk_save_objects(pending_observations)
            db.commit()

        scan = (
            db.query(Scan)
            .filter(
                Scan.id == uuid.UUID(str(scan_id)),
                Scan.tenant_id == uuid.UUID(str(tenant_id)),
            )
            .first()
        )
        if scan is not None:
            scan.status = "COMPLETED"
            scan.finished_at = datetime.utcnow()
            db.commit()

        correlate_findings.delay(tenant_id, scan_id, asset_id)

        return {
            "status": "completed",
            "scan_id": scan_id,
            "events_processed": processed_count,
        }

    except Exception as exc:
        db.rollback()
        logger.error("Scan %s failed: %s", scan_id, exc, exc_info=True)

        try:
            db.execute(
                text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)},
            )
            scan = (
                db.query(Scan)
                .filter(
                    Scan.id == uuid.UUID(str(scan_id)),
                    Scan.tenant_id == uuid.UUID(str(tenant_id)),
                )
                .first()
            )
            if scan is not None:
                scan.status = "FAILED"
                scan.error_message = str(exc)
                scan.finished_at = datetime.utcnow()
                db.commit()
        except Exception as status_exc:
            db.rollback()
            logger.error(
                "Failed to update scan status to FAILED: %s",
                status_exc,
                exc_info=True,
            )

        raise self.retry(exc=exc, countdown=60, max_retries=3)

    finally:
        if client is not None:
            client.close()
        db.close()


@celery_app.task(bind=True, name="tasks.correlate_findings", max_retries=3, acks_late=True)
def correlate_findings(self, tenant_id: str, scan_id: str, asset_id: str):
    db = SessionLocal()
    intel = VulnerabilityIntelligence()

    try:
        db.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )

        observations = (
            db.query(Observation)
            .filter(
                Observation.scan_id == uuid.UUID(str(scan_id)),
                Observation.asset_id == uuid.UUID(str(asset_id)),
                Observation.tenant_id == uuid.UUID(str(tenant_id)),
            )
            .all()
        )

        engine = CorrelationEngine(db)
        processed = 0

        for observation in observations:
            if observation.event_type != "PORT_OPEN":
                continue

            raw_data = observation.raw_data or {}
            port = raw_data.get("port")
            service = raw_data.get("service") or raw_data.get("status") or ""

            if port is None:
                continue

            engine.process_observation(
                obs=observation,
                vulnerability_key=f"open_port_{port}",
                service_id=str(service),
                severity="low",
                confidence="high",
            )
            processed += 1

        return {
            "status": "correlated",
            "observations_processed": processed,
        }

    except Exception as exc:
        db.rollback()
        logger.error(
            "Correlation failed for scan %s: %s",
            scan_id,
            exc,
            exc_info=True,
        )
        raise self.retry(exc=exc, countdown=30, max_retries=3)

    finally:
        intel.close()
        db.close()
