from workers.celery_app import celery_app
from engines.network_cpp.grpc_client import NetworkEngineClient
from backend.database.session import SessionLocal
from backend.database.models.observation import Observation
from backend.services.normalization.normalizer import Normalizer
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

            self.update_state(state='PROGRESS', meta={'current_port': event.port})

        if observations:
            db.bulk_save_objects(observations)
            db.commit()

        client.close()
        return {"status": "completed", "scan_id": scan_id}
        
    except Exception as e:
        db.rollback()
        raise self.retry(exc=e, countdown=10, max_retries=3)
    finally:
        db.close()
