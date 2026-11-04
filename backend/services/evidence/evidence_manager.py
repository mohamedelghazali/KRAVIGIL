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
            uploaded_key, sha, size = self.storage.upload_stream(object_key, stream, content_type)
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
            # Once commit succeeds, the row and object form a consistent pair.
            # A later refresh failure must not delete the object referenced by
            # the committed row; leave it intact for a subsequent read/retry.
            if uploaded_key and not database_committed:
                try:
                    self.storage.delete_object(uploaded_key)
                except Exception:
                    logger.exception("Failed to clean up uploaded evidence %s", uploaded_key)
            raise

    def _get_record(self, evidence_id: uuid.UUID, tenant_id: uuid.UUID) -> Evidence:
        record = self.db.query(Evidence).filter(
            Evidence.id == uuid.UUID(str(evidence_id)),
            Evidence.tenant_id == uuid.UUID(str(tenant_id))).first()
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

    def delete_evidence(self, evidence_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        record = self._get_record(evidence_id, tenant_id)
        self.storage.delete_object(record.object_key)
        self.db.delete(record)
        self.db.commit()
        logger.info("Deleted evidence %s", evidence_id)
