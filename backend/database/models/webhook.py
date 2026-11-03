import uuid
from datetime import datetime
from sqlalchemy import JSON, Column, String, DateTime, ForeignKey, Boolean, Index
from sqlalchemy import Uuid
from sqlalchemy.dialects.postgresql import JSONB
from backend.database.models.base import Base

class Webhook(Base):
    __tablename__ = "webhooks"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    url = Column(String(2048), nullable=False)
    secret = Column(String(255), nullable=False)
    events = Column(JSON().with_variant(JSONB, "postgresql"), default=list)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_webhooks_tenant_active", "tenant_id", "is_active"),
    )
