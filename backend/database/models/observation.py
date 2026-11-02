import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database.models.base import Base

class Observation(Base):
    __tablename__ = "observations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    scan_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    asset_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    engine_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    raw_data = Column(JSONB, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
