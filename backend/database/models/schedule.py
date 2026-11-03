import uuid
from datetime import datetime
from sqlalchemy import JSON, Column, String, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database.models.base import Base

class ScheduledScan(Base):
    __tablename__ = "scheduled_scans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    target_id = Column(UUID(as_uuid=True), ForeignKey("targets.id", ondelete="CASCADE"), nullable=False, index=True)
    
    name = Column(String(255), nullable=False)
    scan_type = Column(String(50), nullable=False)
    cron_expression = Column(String(100), nullable=False)
    parameters = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    last_run = Column(DateTime)
    next_run = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_schedules_tenant_active", "tenant_id", "is_active"),
    )
