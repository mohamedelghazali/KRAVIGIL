import hashlib
from datetime import datetime
from backend.database.models.finding import Finding
from backend.database.models.observation import Observation
from sqlalchemy.orm import Session

class CorrelationEngine:
    def __init__(self, db: Session):
        self.db = db

    def _generate_fingerprint(self, tenant_id: str, asset_id: str, service_id: str, vulnerability_key: str) -> str:
        raw = f"{tenant_id}|{asset_id}|{service_id}|{vulnerability_key}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def process_observation(self, obs: Observation, vulnerability_key: str, service_id: str = "") -> Finding:
        fingerprint = self._generate_fingerprint(str(obs.tenant_id), str(obs.asset_id), service_id, vulnerability_key)
        
        existing = self.db.query(Finding).filter(
            Finding.tenant_id == obs.tenant_id,
            Finding.asset_id == obs.asset_id,
            Finding.vulnerability_key == vulnerability_key
        ).first()

        if existing:
            existing.last_seen = datetime.utcnow()
            existing.observations.append(obs)
            self.db.commit()
            return existing

        finding = Finding(
            tenant_id=obs.tenant_id,
            asset_id=obs.asset_id,
            service_id=service_id,
            engine_id=obs.engine_id,
            engine_version="1.0.0",
            title=f"{vulnerability_key} detected on {service_id or 'unknown service'}",
            vulnerability_key=vulnerability_key,
            severity="medium",
            confidence="potential",
            validation_status="potential",
            workflow_status="open",
            observations=[obs]
        )
        self.db.add(finding)
        self.db.commit()
        self.db.refresh(finding)
        return finding
