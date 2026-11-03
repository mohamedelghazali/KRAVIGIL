import uuid
from datetime import datetime
from sqlalchemy import JSON, Column, String, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database.models.base import Base

class Agent(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    certificate_fingerprint = Column(String(64), unique=True, nullable=False, index=True)
    public_key = Column(String(4096), nullable=False)
    
    status = Column(String(50), default="ENROLLED", nullable=False)
    last_heartbeat = Column(DateTime)
    version = Column(String(50))
    ip_address = Column(String(45))
    metadata_json = Column(JSON().with_variant(JSONB, "postgresql"), default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_agents_tenant_status", "tenant_id", "status"),
    )
