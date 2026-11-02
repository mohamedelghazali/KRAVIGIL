import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.database.models.base import Base

class Asset(Base):
    __tablename__ = "assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    target_id = Column(UUID(as_uuid=True), ForeignKey("targets.id"), nullable=False, index=True)
    ip_address = Column(String, index=True, nullable=False)
    hostname = Column(String)
    os_family = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    target = relationship("Target")
