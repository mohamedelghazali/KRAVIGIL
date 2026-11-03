import uuid
from datetime import datetime
from sqlalchemy import JSON, Column, String, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database.models.base import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_type = Column(String(50), default="user", nullable=False)

    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(255))

    source_ip = Column(String(45))
    user_agent = Column(String(512))
    status_code = Column(String(10))
    details = Column(JSON().with_variant(JSONB, "postgresql"), default=dict)

    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("ix_audit_tenant_action", "tenant_id", "action"),
    )
