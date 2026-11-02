import logging
import uuid
import asyncio
from datetime import datetime
from celery import shared_task
from sqlalchemy import text
from workers.celery_app import celery_app
from engines.network_cpp.grpc_client import NetworkEngineClient
from backend.database.session import SessionLocal
from backend.services.normalization.normalizer import Normalizer
from backend.services.normalization.adapters.nuclei import NucleiAdapter
from backend.services.normalization.adapters.semgrep import SemgrepAdapter
from backend.services.correlation.correlation_engine import CorrelationEngine
from backend.database.models.scan import Scan
from backend.database.models.observation import Observation
from backend.database.models.finding import Finding
from ai.gateway.ai_gateway import AIGateway
from backend.services.reporting.report_orchestrator import ReportOrchestrator
from backend.services.risk.risk_engine import RiskEngine
from backend.services.differential.incremental_processor import IncrementalProcessor
from backend.api.websockets.manager import manager

logger = logging.getLogger(__name__)

def broadcast_ws(tenant_id: str, message: dict):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(manager.broadcast(tenant_id, message))
        loop.close()
    except Exception as e:
        logger.error(f"WebSocket broadcast failed: {e}")

@celery_app.task(bind=True, name="tasks.run_network_scan", max_retries=3, acks_late=True)
def run_network_scan(self, tenant_id: str, scan_id: str, asset_id: str, target_ip: str, ports: list[int]):
    db = SessionLocal()
    client = None
    try:
        db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)})
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan: raise ValueError(f"Scan {scan_id} not found")
            
        scan.status = "RUNNING"
        scan.started_at = datetime.utcnow()
        db.commit()
        
        broadcast_ws(tenant_id, {"type": "scan_update", "scan_id": scan_id, "status": "RUNNING"})

        client = NetworkEngineClient()
        observations = []
        processed_count = 0

        for event in client.start_scan(scan_id, target_ip, ports):
            if self.is_aborted(): raise RuntimeError("Task aborted")

            obs = Normalizer.from_network_event(uuid.UUID(tenant_id), uuid.UUID(scan_id), uuid.UUID(asset_id), event)
            if obs:
                observations.append(obs)
                processed_count += 1

            if len(observations) >= 500:
                db.bulk_save_objects(observations)
                db.commit()
                observations.clear()
                self.update_state(state='PROGRESS', meta={'processed_events': processed_count})

        if observations:
            db.bulk_save_objects(observations)
            db.commit()

        scan.status = "COMPLETED"
        scan.finished_at = datetime.utcnow()
        db.commit()
        
        broadcast_ws(tenant_id, {"type": "scan_update", "scan_id": scan_id, "status": "COMPLETED"})

        correlate_findings.delay(tenant_id, scan_id, asset_id)
        return {"status": "completed", "scan_id": scan_id, "events_processed": processed_count}
    except Exception as e:
        db.rollback()
        logger.error(f"Network scan {scan_id} failed: {str(e)}", exc_info=True)
        try:
            db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)})
            scan = db.query(Scan).filter(Scan.id == scan_id).first()
            if scan:
                scan.status = "FAILED"
                scan.error_message = str(e)
                scan.finished_at = datetime.utcnow()
                db.commit()
                broadcast_ws(tenant_id, {"type": "scan_update", "scan_id": scan_id, "status": "FAILED"})
        except Exception as inner_e:
            logger.error(f"Failed to update scan status: {str(inner_e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)
    finally:
        if client: client.close()
        db.close()

@celery_app.task(bind=True, name="tasks.correlate_findings", max_retries=3, acks_late=True)
def correlate_findings(self, tenant_id: str, scan_id: str, asset_id: str):
    db = SessionLocal()
    try:
        db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)})
        engine = CorrelationEngine(db)
        risk_engine = RiskEngine(db)
        
        observations = db.query(Observation).filter(
            Observation.scan_id == scan_id,
            Observation.asset_id == asset_id
        ).all()
        
        processed = 0
        for obs in observations:
            vuln_key = ""
            severity = "low"
            confidence = "high"
            cve_id = None
            cwe_id = None
            service_id = ""

            if obs.event_type == "PORT_OPEN":
                port = obs.raw_data.get("port")
                vuln_key = f"open_port_{port}"
                service_id = obs.raw_data.get("status")
            elif obs.event_type == "VULNERABILITY_FOUND":
                vuln_key = obs.raw_data.get("template_id") or obs.raw_data.get("title")
                severity = obs.raw_data.get("severity", "medium").lower()
                cve_id = obs.raw_data.get("cve_id")
                cwe_id = obs.raw_data.get("cwe_id")
                service_id = "web"
            elif obs.event_type == "CODE_VULNERABILITY":
                vuln_key = obs.raw_data.get("title")
                severity = obs.raw_data.get("severity", "medium").lower()
                cwe_id = obs.raw_data.get("cwe_id")
                service_id = "codebase"

            if vuln_key:
                finding_id = engine.process_observation(
                    obs=obs, 
                    vulnerability_key=vuln_key, 
                    service_id=service_id,
                    severity=severity,
                    confidence=confidence,
                    cve_id=cve_id,
                    cwe_id=cwe_id
                )
                risk_engine.calculate_risk(uuid.UUID(tenant_id), finding_id)
                processed += 1
                
        broadcast_ws(tenant_id, {"type": "correlation_complete", "scan_id": scan_id, "processed": processed})
        return {"status": "correlated", "observations_processed": processed}
    except Exception as e:
        db.rollback()
        logger.error(f"Correlation failed for scan {scan_id}: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=30, max_retries=3)
    finally:
        db.close()

@celery_app.task(bind=True, name="tasks.generate_report", max_retries=3, acks_late=True)
def generate_report(self, tenant_id: str, report_id: str):
    db = SessionLocal()
    try:
        db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)})
        orchestrator = ReportOrchestrator(db)
        orchestrator.generate_report(uuid.UUID(report_id))
        broadcast_ws(tenant_id, {"type": "report_ready", "report_id": report_id})
        return {"status": "success", "report_id": report_id}
    except Exception as e:
        logger.error(f"Report generation failed for {report_id}: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=60, max_retries=3)
    finally:
        db.close()
