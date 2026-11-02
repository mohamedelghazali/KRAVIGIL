import asyncio
import logging
import uuid
from datetime import datetime

from sqlalchemy import text

from workers.celery_app import celery_app
from engines.network_cpp.grpc_client import NetworkEngineClient
from backend.database.session import SessionLocal
from backend.services.normalization.normalizer import Normalizer
from backend.services.correlation.correlation_engine import CorrelationEngine
from backend.database.models.scan import Scan
from backend.database.models.observation import Observation
from backend.database.models.finding import Finding
from ai.gateway.ai_gateway import AIGateway

logger = logging.getLogger(__name__)


def set_tenant_context(db, tenant_id):
    tenant_uuid = uuid.UUID(str(tenant_id))
    db.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_uuid)},
    )
    return tenant_uuid


@celery_app.task(bind=True, name="tasks.run_network_scan", max_retries=3, acks_late=True)
def run_network_scan(self, tenant_id, scan_id, asset_id, target_ip, ports):
    db = SessionLocal()
    client = None
    try:
        tenant_uuid = set_tenant_context(db, tenant_id)
        scan_uuid = uuid.UUID(str(scan_id))
        asset_uuid = uuid.UUID(str(asset_id))
        scan = db.query(Scan).filter(
            Scan.id == scan_uuid, Scan.tenant_id == tenant_uuid
        ).first()
        if scan is None:
            raise ValueError("Scan not found for tenant")

        scan.status = "RUNNING"
        scan.started_at = datetime.utcnow()
        db.commit()
        client = NetworkEngineClient()
        pending = []
        processed = 0
        for event in client.start_scan(scan_id, target_ip, ports):
            if self.is_aborted():
                raise RuntimeError("Task aborted")
            item = Normalizer.from_network_event(
                tenant_uuid, scan_uuid, asset_uuid, event
            )
            if item is not None:
                pending.append(item)
                processed += 1
            if len(pending) >= 500:
                db.bulk_save_objects(pending)
                db.commit()
                pending.clear()
                self.update_state(state="PROGRESS", meta={"processed_events": processed})
        if pending:
            db.bulk_save_objects(pending)
            db.commit()

        scan.status = "COMPLETED"
        scan.finished_at = datetime.utcnow()
        db.commit()
        correlate_findings.delay(str(tenant_uuid), str(scan_uuid), str(asset_uuid))
        return {"status": "completed", "scan_id": scan_id, "events_processed": processed}
    except Exception as exc:
        db.rollback()
        logger.exception("Scan %s failed", scan_id)
        try:
            tenant_uuid = set_tenant_context(db, tenant_id)
            scan = db.query(Scan).filter(
                Scan.id == uuid.UUID(str(scan_id)),
                Scan.tenant_id == tenant_uuid,
            ).first()
            if scan is not None:
                scan.status = "FAILED"
                scan.error_message = str(exc)[:4000]
                scan.finished_at = datetime.utcnow()
                db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to update scan status")
        raise self.retry(exc=exc, countdown=60, max_retries=3)
    finally:
        if client is not None:
            client.close()
        db.close()


@celery_app.task(bind=True, name="tasks.correlate_findings", max_retries=3, acks_late=True)
def correlate_findings(self, tenant_id, scan_id, asset_id):
    db = SessionLocal()
    try:
        tenant_uuid = set_tenant_context(db, tenant_id)
        observations = db.query(Observation).filter(
            Observation.scan_id == uuid.UUID(str(scan_id)),
            Observation.asset_id == uuid.UUID(str(asset_id)),
            Observation.tenant_id == tenant_uuid,
        ).all()
        engine = CorrelationEngine(db)
        processed = 0
        for obs in observations:
            if obs.event_type != "PORT_OPEN":
                continue
            raw_data = obs.raw_data or {}
            port = raw_data.get("port")
            if port is None:
                continue
            service = raw_data.get("service") or raw_data.get("status") or ""
            engine.process_observation(
                obs=obs,
                vulnerability_key=f"open_port_{port}",
                service_id=str(service),
                severity="low",
                confidence="high",
            )
            processed += 1
        return {"status": "correlated", "observations_processed": processed}
    except Exception as exc:
        db.rollback()
        logger.exception("Correlation failed for scan %s", scan_id)
        raise self.retry(exc=exc, countdown=30, max_retries=3)
    finally:
        db.close()


@celery_app.task(bind=True, name="tasks.analyze_finding_with_ai", max_retries=3, acks_late=True)
def analyze_finding_with_ai(self, tenant_id, finding_id):
    db = SessionLocal()
    try:
        tenant_uuid = set_tenant_context(db, tenant_id)
        finding = db.query(Finding).filter(
            Finding.id == uuid.UUID(str(finding_id)),
            Finding.tenant_id == tenant_uuid,
        ).first()
        if finding is None:
            raise ValueError("Finding not found for tenant")

        evidence = " ".join(
            str(obs.raw_data or {}) for obs in finding.observations
        )
        data = {
            "title": finding.title,
            "description": finding.description,
            "severity": finding.severity,
            "engine": finding.engine_id,
            "engine_version": finding.engine_version,
            "service": finding.service_id,
            "cve": finding.cve_id,
            "cwe": finding.cwe_id,
            "vulnerability_key": finding.vulnerability_key,
        }
        db.close()
        db = None
        result = asyncio.run(
            AIGateway().process_finding_analysis(
                str(tenant_uuid), str(finding_id), data, evidence
            )
        )
        return {"status": "success", "result": result}
    except Exception as exc:
        logger.exception("AI analysis failed for finding %s", finding_id)
        raise self.retry(exc=exc, countdown=60, max_retries=3)
    finally:
        if db is not None:
            db.close()
