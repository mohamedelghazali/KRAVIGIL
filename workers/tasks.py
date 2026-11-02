import logging
import uuid

from sqlalchemy import text

from workers.celery_app import celery_app
from engines.network_cpp.grpc_client import NetworkEngineClient
from backend.database.session import SessionLocal
from backend.services.normalization.normalizer import Normalizer
from backend.services.correlation.correlation_engine import CorrelationEngine
from backend.database.models.scan import Scan
from backend.database.models.observation import Observation

logger = logging.getLogger(__name__)


def _set_tenant_context(db, tenant_id: str) -> None:
    db.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


@celery_app.task(bind=True, name="tasks.run_network_scan", max_retries=3)
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
        _set_tenant_context(db, tenant_id)

        scan = (
            db.query(Scan)
            .filter(
                Scan.id == uuid.UUID(scan_id),
                Scan.tenant_id == uuid.UUID(tenant_id),
                Scan.asset_id == uuid.UUID(asset_id),
            )
            .first()
        )
        if scan is None:
            raise ValueError(f"Scan {scan_id} was not found for this tenant and asset")

        scan.status = "RUNNING"
        scan.started_at = db.execute(text("SELECT NOW()")).scalar()
        scan.finished_at = None
        db.commit()

        client = NetworkEngineClient()
        observations = []
        processed_count = 0

        for event in client.start_scan(scan_id, target_ip, ports):
            if event.event_type == "COMPLETED":
                continue

            observation = Normalizer.from_network_event(
                uuid.UUID(tenant_id),
                uuid.UUID(scan_id),
                uuid.UUID(asset_id),
                event,
            )
            if observation is None:
                continue

            observations.append(observation)
            processed_count += 1

            if len(observations) >= 500:
                _set_tenant_context(db, tenant_id)
                db.bulk_save_objects(observations)
                db.commit()
                observations.clear()
                self.update_state(
                    state="PROGRESS",
                    meta={"processed_ports": processed_count},
                )

        if observations:
            _set_tenant_context(db, tenant_id)
            db.bulk_save_objects(observations)
            db.commit()

        _set_tenant_context(db, tenant_id)
        scan = (
            db.query(Scan)
            .filter(
                Scan.id == uuid.UUID(scan_id),
                Scan.tenant_id == uuid.UUID(tenant_id),
            )
            .first()
        )
        if scan is None:
            raise ValueError(f"Scan {scan_id} disappeared before completion")

        scan.status = "COMPLETED"
        scan.finished_at = db.execute(text("SELECT NOW()")).scalar()
        db.commit()

        correlate_findings.delay(tenant_id, scan_id, asset_id)

        return {
            "status": "completed",
            "scan_id": scan_id,
            "observations_processed": processed_count,
        }

    except Exception as exc:
        db.rollback()
        logger.exception("Network scan %s failed: %s", scan_id, exc)

        try:
            _set_tenant_context(db, tenant_id)
            scan = (
                db.query(Scan)
                .filter(
                    Scan.id == uuid.UUID(scan_id),
                    Scan.tenant_id == uuid.UUID(tenant_id),
                )
                .first()
            )
            if scan is not None:
                if self.request.retries < self.max_retries:
                    scan.status = "RETRYING"
                else:
                    scan.status = "FAILED"
                    scan.finished_at = db.execute(text("SELECT NOW()")).scalar()
                db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to update status for scan %s", scan_id)

        if isinstance(exc, ValueError):
            raise
        raise self.retry(exc=exc, countdown=60)

    finally:
        if client is not None:
            client.close()
        db.close()


@celery_app.task(bind=True, name="tasks.correlate_findings", max_retries=3)
def correlate_findings(self, tenant_id: str, scan_id: str, asset_id: str):
    db = SessionLocal()

    try:
        _set_tenant_context(db, tenant_id)

        observations = (
            db.query(Observation)
            .filter(
                Observation.tenant_id == uuid.UUID(tenant_id),
                Observation.scan_id == uuid.UUID(scan_id),
                Observation.asset_id == uuid.UUID(asset_id),
            )
            .all()
        )

        engine = CorrelationEngine(db)
        processed = 0

        for observation in observations:
            if observation.event_type != "PORT_OPEN":
                continue

            port = observation.raw_data.get("port")
            service = observation.raw_data.get("status")
            if port is None:
                continue

            vulnerability_key = f"open_port_{int(port)}"
            engine.process_observation(
                observation,
                vulnerability_key,
                service_id=service,
            )
            processed += 1

        db.commit()
        return {
            "status": "correlated",
            "observations_processed": processed,
        }

    except Exception as exc:
        db.rollback()
        logger.exception("Correlation failed for scan %s: %s", scan_id, exc)
        raise self.retry(exc=exc, countdown=30)

    finally:
        db.close()
