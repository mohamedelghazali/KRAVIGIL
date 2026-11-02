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
from backend.services.normalization.adapters.gitleaks import GitleaksAdapter
from backend.services.normalization.adapters.trivy import TrivyAdapter
from backend.services.normalization.adapters.cloud_scanner import CloudScannerAdapter
from backend.services.correlation.correlation_engine import CorrelationEngine
from backend.database.models.scan import Scan
from backend.database.models.observation import Observation
from backend.database.models.finding import Finding
from backend.database.models.webhook import Webhook
from backend.database.models.setting import TenantSetting
from ai.gateway.ai_gateway import AIGateway
from backend.services.reporting.report_orchestrator import ReportOrchestrator
from backend.services.risk.risk_engine import RiskEngine
from backend.services.notifications.webhook_dispatcher import WebhookDispatcher
from backend.services.notifications.email_dispatcher import EmailDispatcher
from backend.services.notifications.slack_dispatcher import SlackDispatcher
from backend.services.notifications.siem_dispatcher import SIEMDispatcher
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

def trigger_notifications(db, tenant_id: str, event_type: str, data: dict):
    try:
        webhooks = db.query(Webhook).filter(Webhook.tenant_id == tenant_id).all()
        if webhooks:
            WebhookDispatcher.dispatch(webhooks, event_type, data)
            
        email_setting = db.query(TenantSetting).filter(
            TenantSetting.tenant_id == tenant_id,
            TenantSetting.key == "email_alerts"
        ).first()
        
        if email_setting and email_setting.value.get("enabled"):
            EmailDispatcher.send_alert(
                smtp_config=email_setting.value.get("smtp", {}),
                to_addresses=email_setting.value.get("recipients", []),
                event_type=event_type,
                data=data
            )
            
        slack_setting = db.query(TenantSetting).filter(
            TenantSetting.tenant_id == tenant_id,
            TenantSetting.key == "slack_alerts"
        ).first()
        
        if slack_setting and slack_setting.value.get("enabled"):
            SlackDispatcher.send_alert(
                webhook_url=slack_setting.value.get("webhook_url", ""),
                event_type=event_type,
                data=data
            )

        siem_setting = db.query(TenantSetting).filter(
            TenantSetting.tenant_id == tenant_id,
            TenantSetting.key == "siem_alerts"
        ).first()
        
        if siem_setting and siem_setting.value.get("enabled"):
            SIEMDispatcher.send_syslog(
                siem_config=siem_setting.value,
                event_type=event_type,
                data=data
            )
    except Exception as e:
        logger.error(f"Notification trigger failed: {e}")

@celery_app.task(bind=True, name="tasks.run_cloud_scan", max_retries=3, acks_late=True)
def run_cloud_scan(self, tenant_id: str, scan_id: str, asset_id: str, provider: str):
    db = SessionLocal()
    try:
        db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)})
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan: raise ValueError(f"Scan {scan_id} not found")

        scan.status = "RUNNING"
        scan.started_at = datetime.utcnow()
        db.commit()

        adapter = CloudScannerAdapter()
        results = adapter.scan(provider)

        observations = []
        for res in results:
            obs = Normalizer.from_cloud_result(uuid.UUID(tenant_id), uuid.UUID(scan_id), uuid.UUID(asset_id), res)
            observations.append(obs)

        if observations:
            db.bulk_save_objects(observations)
            db.commit()

        scan.status = "COMPLETED"
        scan.finished_at = datetime.utcnow()
        db.commit()
        
        trigger_notifications(db, tenant_id, "scan.completed", {"scan_id": scan_id, "type": "cloud"})
        correlate_findings.delay(tenant_id, scan_id, asset_id)
        return {"status": "completed", "scan_id": scan_id, "findings": len(results)}
    except Exception as e:
        db.rollback()
        logger.error(f"Cloud scan {scan_id} failed: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=60, max_retries=3)
    finally:
        db.close()
