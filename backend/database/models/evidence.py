import uuid
from datetime import datetime
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from backend.database.models.base import Base

class Evidence(Base):
    __tablename__ = "evidence"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    scan_id = Column(UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True)
    finding_id = Column(UUID(as_uuid=True), ForeignKey("findings.id", ondelete="SET NULL"), nullable=True, index=True)
    object_key = Column(String(512), nullable=False, unique=True)
    object_version_id = Column(String(255))
    storage_backend = Column(String(50), default="minio", nullable=False)
    content_type = Column(String(255), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    encryption = Column(String(50), default="SSE-S3", nullable=False)
    metadata_json = Column(JSON().with_variant(JSONB, "postgresql"), default=dict, nullable=False)
    retention_policy = Column(String(50), default="standard", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (
        Index("ix_evidence_tenant_scan", "tenant_id", "scan_id"),
        Index("ix_evidence_tenant_sha", "tenant_id", "sha256"),
    )
