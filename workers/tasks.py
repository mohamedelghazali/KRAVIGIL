from workers.celery_app import celery_app
from engines.network_cpp.grpc_client import NetworkEngineClient
from backend.database.session import SessionLocal
from backend.database.models.observation import Observation
from backend.database.models.finding import Finding
from backend.services.normalization.normalizer import Normalizer
from backend.services.correlation.correlation_engine import CorrelationEngine
from sqlalchemy import text
import uuid

@celery_app.task(bind=True, name="tasks.run_network_scan")
def run_network_scan(self, tenant_id: str, scan_id: str, asset_id: str, target_ip: str, ports: list):
    db = SessionLocal()
    try:
        db.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
            {"tenant_id": tenant_id}
        )

        client = NetworkEngineClient()
        observations = []

        for event in client.start_scan(scan_id, target_ip, ports):
            obs = Normalizer.from_network_event(tenant_id, scan_id, asset_id, event)
            observations.append(obs)

            if len(observations) >= 100:
                db.bulk_save_objects(observations)
                db.commit()
                observations.clear()

        if observations:
            db.bulk_save_objects(observations)
            db.commit()

        client.close()
        
        correlate_findings.delay(tenant_id, scan_id, asset_id)
        
        return {"status": "completed", "scan_id": scan_id}
        
    except Exception as e:
        db.rollback()
        raise self.retry(exc=e, countdown=10, max_retries=3)
    finally:
        db.close()

@celery_app.task(name="tasks.correlate_findings")
def correlate_findings(tenant_id: str, scan_id: str, asset_id: str):
    db = SessionLocal()
    try:
        db.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
            {"tenant_id": tenant_id}
        )
        
        engine = CorrelationEngine(db)
        observations = db.query(Observation).filter(
            Observation.scan_id == scan_id,
            Observation.asset_id == asset_id
        ).all()
        
        for obs in observations:
            if obs.event_type == "PORT_OPEN":
                port = obs.raw_data.get("port")
                service = obs.raw_data.get("status")
                vuln_key = f"open_port_{port}"
                engine.process_observation(obs, vuln_key, service_id=service)
                
        return {"status": "correlated", "count": len(observations)}
    finally:
        db.close()
