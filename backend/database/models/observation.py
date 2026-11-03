import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, String
from sqlalchemy import Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

from backend.database.models.base import Base


class Observation(Base):
    __tablename__ = "observations"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scan_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    engine_id = Column(String(100), nullable=False)
    event_type = Column(String(100), nullable=False)
    raw_data = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    scan = relationship("Scan", back_populates="observations")
    created_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    __table_args__ = (
        Index("ix_obs_tenant_scan", "tenant_id", "scan_id"),
        Index("ix_obs_tenant_asset", "tenant_id", "asset_id"),
    )
