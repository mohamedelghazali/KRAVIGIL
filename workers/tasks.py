import asyncio
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
from backend.database.models.scan import Scan
from backend.database.models.observation import Observation
from backend.database.models.finding import Finding
from ai.gateway.ai_gateway import AIGateway
from backend.services.reporting.report_orchestrator import ReportOrchestrator

logger = logging.getLogger(__name__)

def _set_tenant(db, tenant_id: str):
    db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
               {"tenant_id": str(tenant_id)})

@celery_app.task(bind=True, name="tasks.run_network_scan", max_retries=3, acks_late=True)
def run_network_scan(self, tenant_id: str, scan_id: str, asset_id: str, target_ip: str, ports: list[int]):
    db = SessionLocal()
    client = None
    try:
        _set_tenant(db, tenant_id)
        scan = db.query(Scan).filter(Scan.id == scan_id, Scan.tenant_id == tenant_id).first()
        if not scan:
            raise ValueError(f"Scan {scan_id} not found")
        scan.status = "RUNNING"
        scan.started_at = datetime.utcnow()
        db.commit()
        client = NetworkEngineClient()
        observations, processed_count = [], 0
        for event in client.start_scan(scan_id, target_ip, ports):
            if self.is_aborted():
                raise RuntimeError("Task aborted")
            obs = Normalizer.from_network_event(uuid.UUID(tenant_id), uuid.UUID(scan_id),
                                                uuid.UUID(asset_id), event)
            if obs:
                observations.append(obs)
                processed_count += 1
            if len(observations) >= 500:
                db.bulk_save_objects(observations)
                db.commit()
                observations.clear()
                self.update_state(state="PROGRESS", meta={"processed_events": processed_count})
        if observations:
            db.bulk_save_objects(observations)
            db.commit()
        scan.status = "COMPLETED"
        scan.finished_at = datetime.utcnow()
        db.commit()
        correlate_findings.delay(tenant_id, scan_id, asset_id)
        return {"status": "completed", "scan_id": scan_id, "events_processed": processed_count}
    except Exception as exc:
        db.rollback()
        logger.exception("Scan %s failed", scan_id)
        try:
            _set_tenant(db, tenant_id)
            scan = db.query(Scan).filter(Scan.id == scan_id, Scan.tenant_id == tenant_id).first()
            if scan:
                scan.status = "FAILED"
                scan.error_message = str(exc)
                scan.finished_at = datetime.utcnow()
                db.commit()
        except Exception:
            logger.exception("Failed to update scan status")
        raise self.retry(exc=exc, countdown=60, max_retries=3)
    finally:
        if client:
            client.close()
        db.close()

@celery_app.task(bind=True, name="tasks.correlate_findings", max_retries=3, acks_late=True)
def correlate_findings(self, tenant_id: str, scan_id: str, asset_id: str):
    db = SessionLocal()
    try:
        _set_tenant(db, tenant_id)
        observations = db.query(Observation).filter(
            Observation.scan_id == scan_id, Observation.asset_id == asset_id
        ).all()
        engine, processed = CorrelationEngine(db), 0
        for obs in observations:
            if obs.event_type == "PORT_OPEN":
                port = obs.raw_data.get("port")
                service = obs.raw_data.get("status")
                engine.process_observation(obs=obs, vulnerability_key=f"open_port_{port}",
                    service_id=service, severity="low", confidence="high")
                processed += 1
        return {"status": "correlated", "observations_processed": processed}
    except Exception as exc:
        db.rollback()
        logger.exception("Correlation failed for scan %s", scan_id)
        raise self.retry(exc=exc, countdown=30, max_retries=3)
    finally:
        db.close()

@celery_app.task(bind=True, name="tasks.analyze_finding_with_ai", max_retries=3, acks_late=True)
def analyze_finding_with_ai(self, tenant_id: str, finding_id: str):
    db = SessionLocal()
    loop = None
    try:
        _set_tenant(db, tenant_id)
        finding = db.query(Finding).filter(Finding.id == finding_id,
                                           Finding.tenant_id == tenant_id).first()
        if not finding:
            raise ValueError(f"Finding {finding_id} not found")
        evidence_text = " ".join(str(obs.raw_data) for obs in finding.observations)
        finding_data = {"title": finding.title, "severity": finding.severity,
                        "engine": finding.engine_id, "cve": finding.cve_id, "cwe": finding.cwe_id}
        gateway = AIGateway()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            gateway.process_finding_analysis(tenant_id, finding_id, finding_data, evidence_text))
        return {"status": "success", "result": result}
    except Exception as exc:
        logger.exception("AI analysis failed for finding %s", finding_id)
        raise self.retry(exc=exc, countdown=60, max_retries=3)
    finally:
        if loop is not None:
            loop.close()
        asyncio.set_event_loop(None)
        db.close()

@celery_app.task(bind=True, name="tasks.generate_report", max_retries=3, acks_late=True)
def generate_report(self, tenant_id: str, report_id: str):
    db = SessionLocal()
    try:
        _set_tenant(db, tenant_id)
        ReportOrchestrator(db).generate_report(uuid.UUID(report_id), uuid.UUID(tenant_id))
        return {"status": "success", "report_id": report_id}
    except Exception as exc:
        logger.exception("Report generation failed for %s", report_id)
        raise self.retry(exc=exc, countdown=60, max_retries=3)
    finally:
        db.close()
