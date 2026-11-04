import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Index, JSON, String
from sqlalchemy import Uuid
from sqlalchemy.dialects.postgresql import JSONB
from backend.database.models.base import Base


class Evidence(Base):
    __tablename__ = "evidence"
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    scan_id = Column(Uuid(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True)
    finding_id = Column(Uuid(as_uuid=True), ForeignKey("findings.id", ondelete="SET NULL"), nullable=True, index=True)
    object_key = Column(String(512), nullable=False, unique=True)
    object_version_id = Column(String(255))
    storage_backend = Column(String(50), default="minio", nullable=False)
    content_type = Column(String(255), nullable=False)
    size_bytes = Column(__import__("sqlalchemy").BigInteger, nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    encryption = Column(String(50), default="SSE-S3", nullable=False)
    metadata_json = Column(JSON().with_variant(JSONB, "postgresql"), default=dict, nullable=False)
    retention_policy = Column(String(50), default="standard", nullable=False)
    deletion_status = Column(String(20), default="ACTIVE", server_default="ACTIVE", nullable=False)
    deletion_requested_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (
        Index("ix_evidence_tenant_scan", "tenant_id", "scan_id"),
        Index("ix_evidence_tenant_sha", "tenant_id", "sha256"),
        Index("ix_evidence_deletion_status", "deletion_status"),
    )
