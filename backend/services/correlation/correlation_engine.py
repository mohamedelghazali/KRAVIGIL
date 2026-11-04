import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.database.models.finding import Finding
from backend.database.models.observation import Observation
from backend.services.correlation.deduplication import (
    canonical_vulnerability_key,
    highest_severity,
)

logger = logging.getLogger(__name__)


class CorrelationEngine:
    def __init__(self, db: Session):
        self.db = db

    def process_observation(
        self,
        obs: Observation,
        vulnerability_key: str,
        service_id: str = "",
        severity: str = "medium",
        confidence: str = "potential",
        cve_id: Optional[str] = None,
        cwe_id: Optional[str] = None,
    ) -> uuid.UUID:
        canonical_key = canonical_vulnerability_key(vulnerability_key)
        normalized_severity = highest_severity(severity)
        now = datetime.utcnow()
        raw_data = obs.raw_data or {}

        statement = insert(Finding).values(
            id=uuid.uuid4(),
            tenant_id=obs.tenant_id,
            asset_id=obs.asset_id,
            service_id=service_id,
            engine_id=obs.engine_id,
            engine_version=raw_data.get("engine_version", "1.0.0"),
            title=f"{canonical_key} detected on {service_id or 'unknown'}",
            vulnerability_key=canonical_key,
            cve_id=cve_id,
            cwe_id=cwe_id,
            severity=normalized_severity,
            confidence=confidence,
            validation_status="potential",
            workflow_status="open",
            first_seen=now,
            last_seen=now,
        )

        statement = statement.on_conflict_do_update(
            constraint="uq_finding_deduplication",
            set_={
                "last_seen": now,
                "severity": normalized_severity,
                "confidence": confidence,
                "updated_at": now,
            },
        ).returning(Finding.id)

        finding_id = self.db.execute(statement).scalar_one()
        finding = self.db.query(Finding).filter(
            Finding.id == finding_id,
            Finding.tenant_id == obs.tenant_id,
        ).first()
        if finding is not None:
            linked_observation_ids = {item.id for item in finding.observations}
            if obs.id not in linked_observation_ids:
                finding.observations.append(obs)

        self.db.commit()
        return finding_id
