import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.database.models.base import Base

class Scan(Base):
    __tablename__ = "scans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    target_id = Column(UUID(as_uuid=True), ForeignKey("targets.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    
    task_id = Column(String(255), nullable=True)
    status = Column(String(50), default="PENDING", nullable=False, index=True)
    scan_type = Column(String(50), default="NETWORK", nullable=False)
    error_message = Column(Text)
    
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    target = relationship("Target")
    asset = relationship("Asset")
    observations = relationship("Observation", back_populates="scan", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_scans_tenant_status", "tenant_id", "status"),
    )
