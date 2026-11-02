import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.database.models.base import Base

class Asset(Base):
    __tablename__ = "assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    target_id = Column(UUID(as_uuid=True), ForeignKey("targets.id", ondelete="CASCADE"), nullable=False, index=True)
    ip_address = Column(String(45), nullable=False, index=True)
    hostname = Column(String(255))
    os_family = Column(String(100))
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    target = relationship("Target", back_populates="assets")

    __table_args__ = (
        Index("ix_assets_tenant_ip", "tenant_id", "ip_address"),
    )
