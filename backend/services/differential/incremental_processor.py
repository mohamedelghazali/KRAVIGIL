import logging
import uuid
from typing import Dict, Any
from sqlalchemy.orm import Session
from backend.services.differential.snapshot_manager import SnapshotManager
from backend.database.models.finding import Finding
from backend.database.models.asset import Asset

logger = logging.getLogger(__name__)

class IncrementalProcessor:
    def __init__(self, db: Session):
        self.db = db
        self.snapshot_manager = SnapshotManager(db)

    def process_differential(self, tenant_id: uuid.UUID, current_scan_id: uuid.UUID, previous_scan_id: uuid.UUID) -> Dict[str, Any]:
        old_snapshot = self.snapshot_manager.create_snapshot(tenant_id, previous_scan_id)
        new_snapshot = self.snapshot_manager.create_snapshot(tenant_id, current_scan_id)

        diff = self.snapshot_manager.compare_snapshots(old_snapshot, new_snapshot)

        for fingerprint in diff["resolved"]:
            finding_id = old_snapshot[fingerprint]["finding_id"]
            finding = self.db.query(Finding).filter(Finding.id == finding_id).first()
            if finding:
                finding.workflow_status = "resolved"
                finding.updated_at = self.db.execute(self.db.bind.dialect.statement_compiler)

        self.db.commit()
        
        logger.info(f"Differential processed for scan {current_scan_id}: {len(diff['new'])} new, {len(diff['resolved'])} resolved, {len(diff['changed'])} changed")
        
        return {
            "new_findings_count": len(diff["new"]),
            "resolved_findings_count": len(diff["resolved"]),
            "changed_findings_count": len(diff["changed"]),
            "unchanged_findings_count": diff["unchanged_count"]
        }
