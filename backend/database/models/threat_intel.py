import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy import Uuid
from sqlalchemy.dialects.postgresql import JSONB

from backend.database.models.base import Base


class ThreatIndicator(Base):
    __tablename__ = "threat_indicators"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    indicator_type = Column(String(50), nullable=False)
    indicator_value = Column(String(512), nullable=False)
    threat_type = Column(String(255), nullable=False, default="unknown")
    source = Column(String(100), nullable=False, default="alienvault_otx")
    raw_data = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "indicator_type",
            "indicator_value",
            "source",
            name="uq_threat_indicator_tenant_value_source",
        ),
        Index("ix_threat_indicators_tenant_created", "tenant_id", "created_at"),
    )
