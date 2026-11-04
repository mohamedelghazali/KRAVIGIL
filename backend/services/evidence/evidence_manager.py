import logging
import uuid
from datetime import datetime
from typing import BinaryIO, Optional
from sqlalchemy.orm import Session
from backend.database.models.evidence import Evidence
from backend.database.models.finding import Finding
from backend.database.models.scan import Scan
from backend.services.evidence.minio_client import MinIOClient

logger = logging.getLogger(__name__)


class EvidenceManager:
    def __init__(self, db: Session):
        self.db = db
        self.storage = MinIOClient()

    def store_evidence(self, tenant_id: uuid.UUID, scan_id: uuid.UUID,
                       finding_id: Optional[uuid.UUID], stream: BinaryIO,
                       content_type: str, extension: str = "bin",
                       metadata: Optional[dict] = None) -> Evidence:
        tenant_uuid, scan_uuid = uuid.UUID(str(tenant_id)), uuid.UUID(str(scan_id))
        scan = self.db.query(Scan).filter(Scan.id == scan_uuid, Scan.tenant_id == tenant_uuid).first()
        if scan is None:
            raise ValueError("Scan not found for tenant")
        finding_uuid = uuid.UUID(str(finding_id)) if finding_id else None
        if finding_uuid:
            finding = self.db.query(Finding).filter(
                Finding.id == finding_uuid, Finding.tenant_id == tenant_uuid,
                Finding.asset_id == scan.asset_id).first()
            if finding is None:
                raise ValueError("Finding not found for tenant or scan asset")

        ext = "".join(c for c in (extension or "bin").lower() if c.isalnum())[:16] or "bin"
        evidence_id = uuid.uuid4()
        object_key = f"{tenant_uuid}/{scan_uuid}/{evidence_id}.{ext}"
        uploaded_key = None
        database_committed = False
        try:
            # The object key is known before upload. Keep it available for
            # compensating cleanup even when the storage request succeeds
            # remotely but its response is lost (for example, a timeout).
            uploaded_key = object_key
            _, sha, size = self.storage.upload_stream(object_key, stream, content_type)
            record = Evidence(id=evidence_id, tenant_id=tenant_uuid, scan_id=scan_uuid,
                finding_id=finding_uuid, object_key=uploaded_key, storage_backend="minio",
                content_type=content_type, size_bytes=size, sha256=sha,
                metadata_json=metadata or {}, created_at=datetime.utcnow())
            self.db.add(record)
            self.db.commit()
            database_committed = True
            self.db.refresh(record)
            logger.info("Stored evidence %s for tenant %s", evidence_id, tenant_uuid)
            return record
        except Exception:
            self.db.rollback()
            # Once commit succeeds, a later refresh failure must not delete the
            # object referenced by the committed row.
            if uploaded_key and not database_committed:
                try:
                    self.storage.delete_object(uploaded_key)
                except Exception:
                    logger.exception("Failed to clean up uploaded evidence %s", uploaded_key)
            raise

    def _get_record(self, evidence_id: uuid.UUID, tenant_id: uuid.UUID,
                    include_pending: bool = False) -> Evidence:
        query = self.db.query(Evidence).filter(
            Evidence.id == uuid.UUID(str(evidence_id)),
            Evidence.tenant_id == uuid.UUID(str(tenant_id)))
        if not include_pending:
            query = query.filter(Evidence.deletion_status == "ACTIVE")
        record = query.first()
        if record is None:
            raise ValueError("Evidence not found")
        return record

    def retrieve_evidence(self, evidence_id: uuid.UUID, tenant_id: uuid.UUID):
        record = self._get_record(evidence_id, tenant_id)
        return record, self.storage.download_stream(record.object_key, record.sha256)

    def get_download_url(self, evidence_id: uuid.UUID, tenant_id: uuid.UUID,
                         expires_seconds: int = 300) -> str:
        record = self._get_record(evidence_id, tenant_id)
        return self.storage.generate_presigned_url(record.object_key, expires_seconds)

    @classmethod
    def delete_for_scans(cls, db: Session, scan_ids: list[uuid.UUID],
                         tenant_id: uuid.UUID) -> int:
        """Remove all evidence objects and rows before parent scans are cascaded."""
        tenant_uuid = uuid.UUID(str(tenant_id))
        scan_uuids = [uuid.UUID(str(scan_id)) for scan_id in scan_ids]
        if not scan_uuids:
            return 0

        evidence_ids = [
            row[0]
            for row in db.query(Evidence.id).filter(
                Evidence.tenant_id == tenant_uuid,
                Evidence.scan_id.in_(scan_uuids),
            ).order_by(Evidence.id).all()
        ]
        if not evidence_ids:
            return 0

        manager = cls(db)
        deleted = 0
        for evidence_id in evidence_ids:
            try:
                manager.delete_evidence(evidence_id, tenant_uuid)
                deleted += 1
            except ValueError:
                # Another idempotent deletion may have completed after the
                # identifier list was read. Ignore only a genuinely missing row.
                still_exists = db.query(Evidence.id).filter(
                    Evidence.id == evidence_id,
                    Evidence.tenant_id == tenant_uuid,
                ).first()
                if still_exists is not None:
                    raise
        return deleted

    def delete_evidence(self, evidence_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        # Persist a tombstone before touching object storage. A failed storage
        # delete or a crash leaves a retryable PENDING_DELETE row, never an
        # apparently active row whose object may already have disappeared.
        record = self._get_record(evidence_id, tenant_id, include_pending=True)
        if record.deletion_status != "PENDING_DELETE":
            record.deletion_status = "PENDING_DELETE"
            record.deletion_requested_at = datetime.utcnow()
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

        # MinIO/S3 object removal is idempotent: retries also cover a crash
        # after object removal but before the final database commit.
        self.storage.delete_object(record.object_key)
        try:
            self.db.delete(record)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        logger.info("Deleted evidence %s for tenant %s", evidence_id, tenant_id)
