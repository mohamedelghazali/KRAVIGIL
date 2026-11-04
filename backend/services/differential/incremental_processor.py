"""Apply scan-to-scan changes to finding workflow state."""

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.database.models.finding import Finding
from backend.services.differential.snapshot_manager import SnapshotManager

logger = logging.getLogger(__name__)


class IncrementalProcessor:
    def __init__(self, db: Session):
        self.db = db
        self.snapshot_manager = SnapshotManager(db)

    def process_differential(
        self,
        tenant_id: uuid.UUID,
        current_scan_id: uuid.UUID,
        previous_scan_id: uuid.UUID,
    ) -> dict[str, Any]:
        old_snapshot = self.snapshot_manager.create_snapshot(tenant_id, previous_scan_id)
        new_snapshot = self.snapshot_manager.create_snapshot(tenant_id, current_scan_id)
        diff = self.snapshot_manager.compare_snapshots(old_snapshot, new_snapshot)

        try:
            for fingerprint in diff["resolved"]:
                finding_id = uuid.UUID(old_snapshot[fingerprint]["finding_id"])
                finding = (
                    self.db.query(Finding)
                    .filter(
                        Finding.id == finding_id,
                        Finding.tenant_id == tenant_id,
                    )
                    .first()
                )
                if finding is not None:
                    finding.workflow_status = "resolved"
                    finding.updated_at = datetime.utcnow()
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("Failed to apply differential state for tenant %s", tenant_id)
            raise

        logger.info(
            "Differential processed for scan %s: %s new, %s resolved, %s changed",
            current_scan_id,
            len(diff["new"]),
            len(diff["resolved"]),
            len(diff["changed"]),
        )
        return {
            "new_findings_count": len(diff["new"]),
            "resolved_findings_count": len(diff["resolved"]),
            "changed_findings_count": len(diff["changed"]),
            "unchanged_findings_count": diff["unchanged_count"],
        }
