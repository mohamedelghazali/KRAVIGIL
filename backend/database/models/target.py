import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy import Uuid
from sqlalchemy.orm import relationship
from backend.database.models.base import Base

class Target(Base):
    __tablename__ = "targets"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    ip_address = Column(String(45), index=True)
    domain = Column(String(255), index=True)
    is_authorized = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    organization = relationship("Organization", back_populates="targets")
    assets = relationship("Asset", back_populates="target", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_targets_tenant_ip", "tenant_id", "ip_address"),
        Index("ix_targets_tenant_domain", "tenant_id", "domain"),
    )
