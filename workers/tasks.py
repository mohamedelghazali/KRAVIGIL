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
from backend.services.correlation.correlation_engine import CorrelationEngine
from backend.database.models.scan import Scan
from backend.database.models.observation import Observation
from backend.database.models.finding import Finding
from backend.database.models.webhook import Webhook
from backend.database.models.setting import TenantSetting
from backend.database.models.schedule import ScheduledScan
from backend.database.models.target import Target
from backend.database.models.asset import Asset
from backend.services.scheduler.cron_parser import CronParser
from ai.gateway.ai_gateway import AIGateway
from backend.services.reporting.report_orchestrator import ReportOrchestrator
from backend.services.risk.risk_engine import RiskEngine
from backend.services.notifications.webhook_dispatcher import WebhookDispatcher
from backend.services.notifications.email_dispatcher import EmailDispatcher
from backend.services.notifications.slack_dispatcher import SlackDispatcher
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
    except Exception as e:
        logger.error(f"Notification trigger failed: {e}")

@celery_app.task(name="tasks.check_scheduled_scans")
def check_scheduled_scans():
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        schedules = db.query(ScheduledScan).filter(
            ScheduledScan.is_active == True,
            ScheduledScan.next_run <= now
        ).all()
        
        for schedule in schedules:
            db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(schedule.tenant_id)})
            
            target = db.query(Target).filter(Target.id == schedule.target_id).first()
            asset = db.query(Asset).filter(Asset.target_id == target.id).first()
            
            if not asset:
                asset = Asset(
                    tenant_id=schedule.tenant_id,
                    target_id=target.id,
                    ip_address=target.ip_address or target.domain
                )
                db.add(asset)
                db.commit()
                db.refresh(asset)
                
            scan = Scan(
                tenant_id=schedule.tenant_id,
                target_id=target.id,
                asset_id=asset.id,
                status="PENDING",
                scan_type=schedule.scan_type
            )
            db.add(scan)
            db.commit()
            db.refresh(scan)
            
            if schedule.scan_type == "NETWORK":
                run_network_scan.delay(
                    tenant_id=str(schedule.tenant_id),
                    scan_id=str(scan.id),
                    asset_id=str(asset.id),
                    target_ip=asset.ip_address,
                    ports=schedule.parameters.get("ports", [22, 80, 443])
                )
            elif schedule.scan_type == "WEB":
                run_web_scan.delay(
                    tenant_id=str(schedule.tenant_id),
                    scan_id=str(scan.id),
                    asset_id=str(asset.id),
                    target_url=target.domain or f"http://{target.ip_address}"
                )
                
            schedule.last_run = now
            schedule.next_run = CronParser.get_next_run(schedule.cron_expression, now)
            db.commit()
            
    except Exception as e:
        logger.error(f"Scheduled scans check failed: {e}")
    finally:
        db.close()
