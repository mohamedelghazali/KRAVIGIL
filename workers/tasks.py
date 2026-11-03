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

def set_worker_tenant(db, tenant_id) -> None:
    db.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, false)"),
        {"tenant_id": str(tenant_id)},
    )
    db.commit()


def _close_worker_session(db) -> None:
    try:
        if db.get_bind().dialect.name == "postgresql":
            db.rollback()
            db.execute(
                text("SELECT set_config('app.tenant_id', '', false), set_config('app.auth_lookup', 'false', false)")
            )
            db.commit()
    except Exception:
        db.rollback()
    finally:
        _close_worker_session(db)


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
        tenant_uuid = uuid.UUID(str(tenant_id))
        webhooks = db.query(Webhook).filter(Webhook.tenant_id == tenant_uuid).all()
        if webhooks:
            WebhookDispatcher.dispatch(webhooks, event_type, data)
            
        email_setting = db.query(TenantSetting).filter(
            TenantSetting.tenant_id == tenant_uuid,
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
        tenant_uuid = uuid.UUID(str(tenant_id))
        scan_uuid = uuid.UUID(str(scan_id))
        asset_uuid = uuid.UUID(str(asset_id))
        set_worker_tenant(db, tenant_uuid)
        scan = db.query(Scan).filter(Scan.id == scan_uuid, Scan.tenant_id == tenant_uuid).first()
        if not scan: raise ValueError(f"Scan {scan_id} not found")

        scan.status = "RUNNING"
        scan.started_at = datetime.utcnow()
        db.commit()

        adapter = CloudScannerAdapter()
        results = adapter.scan(provider)

        observations = []
        for res in results:
            obs = Normalizer.from_cloud_result(tenant_uuid, scan_uuid, asset_uuid, res)
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


import json
import os
from pathlib import Path

from backend.database.models.asset import Asset
from backend.database.models.target import Target
from backend.database.models.schedule import ScheduledScan
from backend.services.scheduler.cron_parser import CronParser


@celery_app.task(bind=True, name="tasks.run_network_scan", acks_late=True)
def run_network_scan(self, tenant_id: str, scan_id: str, asset_id: str, target_ip: str, ports: list[int]):
    db = SessionLocal()
    try:
        tenant_uuid = uuid.UUID(str(tenant_id))
        scan_uuid = uuid.UUID(str(scan_id))
        asset_uuid = uuid.UUID(str(asset_id))
        set_worker_tenant(db, tenant_uuid)
        scan = db.query(Scan).filter(Scan.id == scan_uuid, Scan.tenant_id == tenant_uuid).first()
        if scan is None:
            raise ValueError("Scan not found for tenant")
        scan.status = "RUNNING"
        scan.started_at = datetime.utcnow()
        db.commit()

        client_host = os.getenv("KRAVIGIL_ENGINE_HOST", "network_engine")
        with NetworkEngineClient(host=client_host) as client:
            for event in client.start_scan(
                scan_id=scan_id,
                target_ip=target_ip,
                ports=ports,
                timeout_ms=int(os.getenv("NETWORK_SCAN_TIMEOUT_MS", "1500")),
            ):
                observation = Normalizer.from_network_event(
                    tenant_uuid, scan_uuid, asset_uuid, event
                )
                if observation is not None:
                    db.add(observation)
            db.commit()

        scan = db.query(Scan).filter(Scan.id == scan_uuid, Scan.tenant_id == tenant_uuid).first()
        scan.status = "COMPLETED"
        scan.finished_at = datetime.utcnow()
        db.commit()
        trigger_notifications(db, tenant_id, "scan.completed", {"scan_id": scan_id, "type": "network"})
        correlate_findings.delay(tenant_id, scan_id, asset_id)
        return {"status": "completed", "scan_id": scan_id}
    except Exception as exc:
        db.rollback()
        scan = db.query(Scan).filter(Scan.id == scan_id, Scan.tenant_id == tenant_id).first()
        if scan is not None:
            scan.status = "FAILED"
            scan.error_message = str(exc)[:2048]
            scan.finished_at = datetime.utcnow()
            db.commit()
        logger.exception("Network scan %s failed", scan_id)
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="tasks.run_web_scan", acks_late=True)
def run_web_scan(self, tenant_id: str, scan_id: str, asset_id: str, target_url: str):
    db = SessionLocal()
    try:
        tenant_uuid = uuid.UUID(str(tenant_id))
        scan_uuid = uuid.UUID(str(scan_id))
        asset_uuid = uuid.UUID(str(asset_id))
        db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_uuid)})
        scan = db.query(Scan).filter(Scan.id == scan_uuid, Scan.tenant_id == tenant_uuid).first()
        if scan is None:
            raise ValueError("Scan not found for tenant")
        scan.status = "RUNNING"
        scan.started_at = datetime.utcnow()
        db.commit()

        results = NucleiAdapter().scan(target_url)
        observations = [
            Normalizer.from_nuclei_result(tenant_uuid, scan_uuid, asset_uuid, item)
            for item in results
        ]
        if observations:
            db.add_all(observations)
        scan.status = "COMPLETED"
        scan.finished_at = datetime.utcnow()
        db.commit()
        trigger_notifications(db, tenant_id, "scan.completed", {"scan_id": scan_id, "type": "web"})
        correlate_findings.delay(tenant_id, scan_id, asset_id)
        return {"status": "completed", "scan_id": scan_id, "findings": len(results)}
    except Exception as exc:
        db.rollback()
        scan = db.query(Scan).filter(Scan.id == scan_id, Scan.tenant_id == tenant_id).first()
        if scan is not None:
            scan.status = "FAILED"
            scan.error_message = str(exc)[:2048]
            scan.finished_at = datetime.utcnow()
            db.commit()
        logger.exception("Web scan %s failed", scan_id)
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="tasks.run_sast_scan", acks_late=True)
def run_sast_scan(self, tenant_id: str, scan_id: str, asset_id: str, code_path: str):
    db = SessionLocal()
    try:
        db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)})
        scan = db.query(Scan).filter(Scan.id == scan_id, Scan.tenant_id == tenant_id).first()
        if scan is None:
            raise ValueError("Scan not found for tenant")
        source_path = Path(code_path).resolve(strict=True)
        if not source_path.is_dir():
            raise ValueError("SAST code_path must be an existing directory")
        scan.status = "RUNNING"
        scan.started_at = datetime.utcnow()
        db.commit()

        results = SemgrepAdapter().scan(str(source_path))
        observations = []
        for item in results:
            observations.append(Observation(
                id=uuid.uuid4(),
                tenant_id=tenant_uuid,
                scan_id=scan_uuid,
                asset_id=asset_uuid,
                engine_id="semgrep",
                event_type="SAST_FINDING",
                raw_data=item,
            ))
        if observations:
            db.add_all(observations)
        scan.status = "COMPLETED"
        scan.finished_at = datetime.utcnow()
        db.commit()
        trigger_notifications(db, tenant_id, "scan.completed", {"scan_id": scan_id, "type": "sast"})
        correlate_findings.delay(tenant_id, scan_id, asset_id)
        return {"status": "completed", "scan_id": scan_id, "findings": len(results)}
    except Exception as exc:
        db.rollback()
        scan = db.query(Scan).filter(Scan.id == scan_id, Scan.tenant_id == tenant_id).first()
        if scan is not None:
            scan.status = "FAILED"
            scan.error_message = str(exc)[:2048]
            scan.finished_at = datetime.utcnow()
            db.commit()
        logger.exception("SAST scan %s failed", scan_id)
        raise
    finally:
        db.close()


@celery_app.task(name="tasks.correlate_findings", acks_late=True)
def correlate_findings(tenant_id: str, scan_id: str, asset_id: str):
    db = SessionLocal()
    try:
        db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)})
        observations = db.query(Observation).filter(
            Observation.tenant_id == uuid.UUID(str(tenant_id)),
            Observation.scan_id == uuid.UUID(str(scan_id)),
        ).all()
        engine = CorrelationEngine(db)
        severity_order = {"CRITICAL": "critical", "HIGH": "high", "MEDIUM": "medium", "LOW": "low", "INFO": "info"}
        created = 0
        for obs in observations:
            data = obs.raw_data or {}
            if obs.engine_id == "network_cpp":
                port = data.get("port")
                if not port:
                    continue
                key = f"open-port:{port}"
                severity = "low"
                service = f"tcp/{port}"
                cve_id = None
                cwe_id = None
            elif obs.engine_id == "nuclei":
                key = data.get("cve_id") or data.get("template_id") or data.get("title") or str(obs.id)
                severity = severity_order.get(str(data.get("severity", "medium")).upper(), "medium")
                service = str(data.get("matched_at") or "")
                cve_id = data.get("cve_id")
                cwe_id = data.get("cwe_id")
            elif obs.engine_id == "semgrep":
                key = data.get("check_id") or f"semgrep:{obs.id}"
                severity = severity_order.get(str(data.get("severity", "medium")).upper(), "medium")
                service = f"{data.get('path', '')}:{data.get('line', '')}"
                cve_id = None
                cwe_id = data.get("cwe_id")
            elif obs.engine_id == "cloud_scanner":
                key = data.get("resource_arn") or data.get("title") or str(obs.id)
                severity = severity_order.get(str(data.get("severity", "medium")).upper(), "medium")
                service = str(data.get("resource_arn") or "")
                cve_id = None
                cwe_id = None
            else:
                continue
            engine.process_observation(
                obs,
                vulnerability_key=str(key)[:255],
                service_id=service[:100],
                severity=severity,
                confidence="confirmed" if obs.engine_id == "network_cpp" else "potential",
                cve_id=cve_id,
                cwe_id=cwe_id,
            )
            created += 1
        return {"scan_id": scan_id, "observations_correlated": created}
    finally:
        db.close()


@celery_app.task(name="tasks.generate_report", acks_late=True)
def generate_report(tenant_id: str, report_id: str):
    db = SessionLocal()
    try:
        db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)})
        ReportOrchestrator(db).generate_report(uuid.UUID(report_id), uuid.UUID(tenant_id))
        return {"status": "completed", "report_id": report_id}
    finally:
        db.close()


@celery_app.task(name="tasks.analyze_finding_with_ai", acks_late=True)
def analyze_finding_with_ai(tenant_id: str, finding_id: str):
    db = SessionLocal()
    try:
        db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(tenant_id)})
        finding = db.query(Finding).filter(
            Finding.id == uuid.UUID(str(finding_id)),
            Finding.tenant_id == uuid.UUID(str(tenant_id)),
        ).first()
        if finding is None:
            raise ValueError("Finding not found for tenant")
        finding_data = {
            "title": finding.title,
            "description": finding.description,
            "severity": finding.severity,
            "confidence": finding.confidence,
            "cve_id": finding.cve_id,
            "cwe_id": finding.cwe_id,
            "vulnerability_key": finding.vulnerability_key,
        }
        evidence = [
            item.raw_data for item in finding.observations
        ]
        evidence_text = json.dumps(evidence, ensure_ascii=False, default=str)
    finally:
        db.close()

    gateway = AIGateway()
    return asyncio.run(gateway.process_finding_analysis(
        tenant_id=tenant_id,
        finding_id=finding_id,
        finding_data=finding_data,
        raw_evidence=evidence_text,
    ))


@celery_app.task(name="tasks.check_scheduled_scans")
def check_scheduled_scans():
    db = SessionLocal()
    now = datetime.utcnow()
    dispatched = 0
    try:
        due_schedules = db.query(ScheduledScan).filter(
            ScheduledScan.is_active.is_(True),
            ScheduledScan.next_run <= now,
        ).all()
        for schedule in due_schedules:
            set_worker_tenant(db, schedule.tenant_id)
            target = db.query(Target).filter(
                Target.id == schedule.target_id,
                Target.tenant_id == schedule.tenant_id,
                Target.is_authorized.is_(True),
            ).first()
            if target is None:
                schedule.next_run = CronParser.get_next_run(schedule.cron_expression, now)
                continue
            asset = db.query(Asset).filter(
                Asset.target_id == target.id,
                Asset.tenant_id == schedule.tenant_id,
            ).first()
            if asset is None:
                asset = Asset(
                    tenant_id=schedule.tenant_id,
                    target_id=target.id,
                    ip_address=target.ip_address or target.domain,
                )
                db.add(asset)
                db.flush()
            scan = Scan(
                tenant_id=schedule.tenant_id,
                target_id=target.id,
                asset_id=asset.id,
                status="PENDING",
                scan_type=schedule.scan_type.upper(),
            )
            db.add(scan)
            db.flush()
            params = schedule.parameters or {}
            scan_type = schedule.scan_type.upper()
            if scan_type == "NETWORK":
                task = run_network_scan.delay(
                    str(schedule.tenant_id), str(scan.id), str(asset.id),
                    asset.ip_address, params.get("ports", [22, 80, 443, 8080]),
                )
            elif scan_type == "WEB":
                target_url = params.get("target_url") or target.domain or target.ip_address
                if not str(target_url).startswith(("http://", "https://")):
                    target_url = f"https://{target_url}"
                task = run_web_scan.delay(
                    str(schedule.tenant_id), str(scan.id), str(asset.id), str(target_url),
                )
            elif scan_type == "SAST":
                task = run_sast_scan.delay(
                    str(schedule.tenant_id), str(scan.id), str(asset.id), str(params.get("code_path", "")),
                )
            elif scan_type == "CLOUD":
                task = run_cloud_scan.delay(
                    str(schedule.tenant_id), str(scan.id), str(asset.id), str(params.get("provider", "aws")),
                )
            else:
                scan.status = "FAILED"
                scan.error_message = f"Unsupported scheduled scan type: {scan_type}"
                scan.finished_at = datetime.utcnow()
                task = None
            if task is not None:
                scan.task_id = task.id
                dispatched += 1
            schedule.last_run = now
            schedule.next_run = CronParser.get_next_run(schedule.cron_expression, now)
        db.commit()
        return {"dispatched": dispatched}
    except Exception:
        db.rollback()
        logger.exception("Scheduled scan dispatch failed")
        raise
    finally:
        db.close()
