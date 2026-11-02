import uuid
import hashlib
import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from backend.database.models.scan import Scan
from backend.database.models.finding import Finding

logger = logging.getLogger(__name__)

class SnapshotManager:
    def __init__(self, db: Session):
        self.db = db

    def _generate_finding_fingerprint(self, finding: Finding) -> str:
        canonical = f"{finding.tenant_id}|{finding.asset_id}|{finding.service_id or ''}|{finding.vulnerability_key}"
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    def create_snapshot(self, tenant_id: uuid.UUID, scan_id: uuid.UUID) -> dict:
        findings = self.db.query(Finding).filter(
            Finding.tenant_id == tenant_id,
            Finding.scan_id == scan_id
        ).all()

        snapshot = {}
        for finding in findings:
            fp = self._generate_finding_fingerprint(finding)
            snapshot[fp] = {
                "finding_id": str(finding.id),
                "severity": finding.severity,
                "confidence": finding.confidence,
                "validation_status": finding.validation_status
            }

        return snapshot

    def compare_snapshots(self, old_snapshot: dict, new_snapshot: dict) -> dict:
        old_keys = set(old_snapshot.keys())
        new_keys = set(new_snapshot.keys())

        new_findings = new_keys - old_keys
        resolved_findings = old_keys - new_keys
        unchanged_findings = old_keys & new_keys
        
        changed_findings = []
        for key in unchanged_findings:
            old_data = old_snapshot[key]
            new_data = new_snapshot[key]
            if old_data["severity"] != new_data["severity"] or old_data["validation_status"] != new_data["validation_status"]:
                changed_findings.append({
                    "fingerprint": key,
                    "old": old_data,
                    "new": new_data
                })

        return {
            "new": list(new_findings),
            "resolved": list(resolved_findings),
            "changed": changed_findings,
            "unchanged_count": len(unchanged_findings) - len(changed_findings)
        }
