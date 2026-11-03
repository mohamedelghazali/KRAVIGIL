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
        db.close()


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
        _close_worker_session(db)


import json
import os
import httpx
from pathlib import Path

from backend.database.models.asset import Asset
from backend.database.models.user import Organization
from backend.database.models.threat_intel import ThreatIndicator
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
        scan = db.query(Scan).filter(Scan.id == scan_uuid, Scan.tenant_id == tenant_uuid).first()
        if scan is not None:
            scan.status = "FAILED"
            scan.error_message = str(exc)[:2048]
            scan.finished_at = datetime.utcnow()
            db.commit()
        logger.exception("Network scan %s failed", scan_id)
        raise
    finally:
        _close_worker_session(db)


@celery_app.task(bind=True, name="tasks.run_web_scan", acks_late=True)
def run_web_scan(self, tenant_id: str, scan_id: str, asset_id: str, target_url: str):
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
        scan = db.query(Scan).filter(Scan.id == scan_uuid, Scan.tenant_id == tenant_uuid).first()
        if scan is not None:
            scan.status = "FAILED"
            scan.error_message = str(exc)[:2048]
            scan.finished_at = datetime.utcnow()
            db.commit()
        logger.exception("Web scan %s failed", scan_id)
        raise
    finally:
        _close_worker_session(db)


@celery_app.task(bind=True, name="tasks.run_sast_scan", acks_late=True)
def run_sast_scan(self, tenant_id: str, scan_id: str, asset_id: str, code_path: str):
    db = SessionLocal()
    try:
        tenant_uuid = uuid.UUID(str(tenant_id))
        scan_uuid = uuid.UUID(str(scan_id))
        asset_uuid = uuid.UUID(str(asset_id))
        set_worker_tenant(db, tenant_uuid)
        scan = db.query(Scan).filter(Scan.id == scan_uuid, Scan.tenant_id == tenant_uuid).first()
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
        scan = db.query(Scan).filter(Scan.id == scan_uuid, Scan.tenant_id == tenant_uuid).first()
        if scan is not None:
            scan.status = "FAILED"
            scan.error_message = str(exc)[:2048]
            scan.finished_at = datetime.utcnow()
            db.commit()
        logger.exception("SAST scan %s failed", scan_id)
        raise
    finally:
        _close_worker_session(db)


@celery_app.task(name="tasks.correlate_findings", acks_late=True)
def correlate_findings(tenant_id: str, scan_id: str, asset_id: str):
    db = SessionLocal()
    try:
        set_worker_tenant(db, tenant_id)
        observations = db.query(Observation).filter(
            Observation.tenant_id == tenant_uuid,
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
        _close_worker_session(db)


@celery_app.task(name="tasks.generate_report", acks_late=True)
def generate_report(tenant_id: str, report_id: str):
    db = SessionLocal()
    try:
        set_worker_tenant(db, tenant_id)
        ReportOrchestrator(db).generate_report(uuid.UUID(report_id), uuid.UUID(tenant_id))
        return {"status": "completed", "report_id": report_id}
    finally:
        _close_worker_session(db)


@celery_app.task(name="tasks.analyze_finding_with_ai", acks_late=True)
def analyze_finding_with_ai(tenant_id: str, finding_id: str):
    db = SessionLocal()
    try:
        set_worker_tenant(db, tenant_id)
        finding = db.query(Finding).filter(
            Finding.id == uuid.UUID(str(finding_id)),
            Finding.tenant_id == tenant_uuid,
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
        _close_worker_session(db)

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
        ).with_for_update(skip_locked=True).all()

        for schedule in due_schedules:
            tenant_uuid = uuid.UUID(str(schedule.tenant_id))
            set_worker_tenant(db, tenant_uuid)
            target = db.query(Target).filter(
                Target.id == schedule.target_id,
                Target.tenant_id == tenant_uuid,
                Target.is_authorized.is_(True),
            ).first()
            if target is None:
                schedule.next_run = CronParser.get_next_run(schedule.cron_expression, now)
                db.commit()
                continue

            asset = db.query(Asset).filter(
                Asset.target_id == target.id,
                Asset.tenant_id == tenant_uuid,
            ).first()
            if asset is None:
                asset = Asset(
                    tenant_id=tenant_uuid,
                    target_id=target.id,
                    ip_address=target.ip_address or target.domain,
                )
                db.add(asset)
                db.flush()

            scan_type = schedule.scan_type.upper()
            params = dict(schedule.parameters or {})
            scan = Scan(
                tenant_id=tenant_uuid,
                target_id=target.id,
                asset_id=asset.id,
                status="PENDING",
                scan_type=scan_type,
            )
            db.add(scan)
            db.flush()
            scan_uuid = scan.id
            asset_uuid = asset.id
            target_address = asset.ip_address
            target_domain = target.domain
            schedule.last_run = now
            schedule.next_run = CronParser.get_next_run(schedule.cron_expression, now)

            # Commit the scan row before publishing to Celery to avoid a worker
            # racing ahead and querying a scan that is not committed yet.
            db.commit()

            try:
                if scan_type == "NETWORK":
                    task = run_network_scan.delay(
                        str(tenant_uuid), str(scan_uuid), str(asset_uuid),
                        target_address, params.get("ports", [22, 80, 443, 8080]),
                    )
                elif scan_type == "WEB":
                    target_url = params.get("target_url") or target_domain or target_address
                    if not str(target_url).startswith(("http://", "https://")):
                        target_url = f"https://{target_url}"
                    task = run_web_scan.delay(
                        str(tenant_uuid), str(scan_uuid), str(asset_uuid), str(target_url),
                    )
                elif scan_type == "SAST":
                    task = run_sast_scan.delay(
                        str(tenant_uuid), str(scan_uuid), str(asset_uuid), str(params.get("code_path", "")),
                    )
                elif scan_type == "CLOUD":
                    task = run_cloud_scan.delay(
                        str(tenant_uuid), str(scan_uuid), str(asset_uuid), str(params.get("provider", "aws")),
                    )
                else:
                    set_worker_tenant(db, tenant_uuid)
                    failed_scan = db.query(Scan).filter(
                        Scan.id == scan_uuid, Scan.tenant_id == tenant_uuid
                    ).first()
                    if failed_scan:
                        failed_scan.status = "FAILED"
                        failed_scan.error_message = f"Unsupported scheduled scan type: {scan_type}"
                        failed_scan.finished_at = datetime.utcnow()
                        db.commit()
                    continue

                set_worker_tenant(db, tenant_uuid)
                persisted_scan = db.query(Scan).filter(
                    Scan.id == scan_uuid, Scan.tenant_id == tenant_uuid
                ).first()
                if persisted_scan:
                    persisted_scan.task_id = task.id
                    db.commit()
                dispatched += 1
            except Exception as dispatch_error:
                set_worker_tenant(db, tenant_uuid)
                failed_scan = db.query(Scan).filter(
                    Scan.id == scan_uuid, Scan.tenant_id == tenant_uuid
                ).first()
                if failed_scan:
                    failed_scan.status = "FAILED"
                    failed_scan.error_message = str(dispatch_error)[:2048]
                    failed_scan.finished_at = datetime.utcnow()
                    db.commit()
                logger.exception("Could not dispatch scheduled scan %s", scan_uuid)

        return {"dispatched": dispatched}
    except Exception:
        db.rollback()
        logger.exception("Scheduled scan dispatch failed")
        raise
    finally:
        _close_worker_session(db)


@celery_app.task(name="tasks.sync_threat_intel", acks_late=True)
def sync_threat_intel():
    api_key = os.getenv("OTX_API_KEY")
    if not api_key:
        raise RuntimeError("OTX_API_KEY is required to synchronize AlienVault OTX indicators")

    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            "https://otx.alienvault.com/api/v1/pulses/subscribed",
            params={"limit": 100},
            headers={"X-OTX-API-KEY": api_key, "Accept": "application/json"},
        )
        response.raise_for_status()
        pulses = response.json().get("results", [])

    db = SessionLocal()
    inserted = 0
    try:
        organizations = db.query(Organization).all()
        for organization in organizations:
            set_worker_tenant(db, organization.id)
            for pulse in pulses:
                pulse_name = str(pulse.get("name") or pulse.get("id") or "unknown")[:255]
                for indicator in pulse.get("indicators", []):
                    value = str(indicator.get("indicator") or "").strip()
                    indicator_type = str(indicator.get("type") or "unknown").lower()[:50]
                    if not value:
                        continue
                    existing = db.query(ThreatIndicator.id).filter(
                        ThreatIndicator.tenant_id == organization.id,
                        ThreatIndicator.indicator_type == indicator_type,
                        ThreatIndicator.indicator_value == value[:512],
                        ThreatIndicator.source == "alienvault_otx",
                    ).first()
                    if existing:
                        continue
                    db.add(ThreatIndicator(
                        tenant_id=organization.id,
                        indicator_type=indicator_type,
                        indicator_value=value[:512],
                        threat_type=pulse_name,
                        source="alienvault_otx",
                        raw_data={"pulse_id": pulse.get("id"), "indicator": indicator},
                    ))
                    inserted += 1
            db.commit()
        return {"pulses": len(pulses), "indicators_inserted": inserted}
    except Exception:
        db.rollback()
        logger.exception("Threat intelligence synchronization failed")
        raise
    finally:
        _close_worker_session(db)
