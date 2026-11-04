"""Tenant-scoped scan snapshots and deterministic differential comparisons."""

import uuid

from sqlalchemy.orm import Session

from backend.database.models.finding import Finding
from backend.database.models.observation import Observation
from backend.services.correlation.fingerprint import finding_fingerprint


class SnapshotManager:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _generate_finding_fingerprint(finding: Finding) -> str:
        return finding_fingerprint(
            finding.tenant_id,
            finding.asset_id,
            finding.service_id,
            finding.vulnerability_key,
        )

    def create_snapshot(self, tenant_id: uuid.UUID, scan_id: uuid.UUID) -> dict:
        """Select only findings evidenced by observations from this tenant's scan."""
        findings = (
            self.db.query(Finding)
            .join(Finding.observations)
            .filter(
                Finding.tenant_id == tenant_id,
                Observation.tenant_id == tenant_id,
                Observation.scan_id == scan_id,
            )
            .distinct()
            .all()
        )
        snapshot = {}
        for finding in findings:
            fingerprint = self._generate_finding_fingerprint(finding)
            snapshot[fingerprint] = {
                "finding_id": str(finding.id),
                "severity": finding.severity,
                "confidence": finding.confidence,
                "validation_status": finding.validation_status,
            }
        return snapshot

    @staticmethod
    def compare_snapshots(old_snapshot: dict, new_snapshot: dict) -> dict:
        old_keys = set(old_snapshot)
        new_keys = set(new_snapshot)
        new_findings = new_keys - old_keys
        resolved_findings = old_keys - new_keys
        common = old_keys & new_keys

        changed_findings = []
        for fingerprint in sorted(common):
            old_data = old_snapshot[fingerprint]
            new_data = new_snapshot[fingerprint]
            if (
                old_data.get("severity") != new_data.get("severity")
                or old_data.get("validation_status") != new_data.get("validation_status")
            ):
                changed_findings.append(
                    {
                        "fingerprint": fingerprint,
                        "old": old_data,
                        "new": new_data,
                    }
                )

        return {
            "new": sorted(new_findings),
            "resolved": sorted(resolved_findings),
            "changed": changed_findings,
            "unchanged_count": len(common) - len(changed_findings),
        }
