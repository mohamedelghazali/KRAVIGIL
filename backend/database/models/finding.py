import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Column,
    String,
    DateTime,
    ForeignKey,
    Text,
    Table,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from backend.database.models.base import Base


finding_observations = Table(
    "finding_observations",
    Base.metadata,
    Column(
        "finding_id",
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "observation_id",
        UUID(as_uuid=True),
        ForeignKey("observations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Finding(Base):
    __tablename__ = "findings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id = Column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_id = Column(String(100))
    engine_id = Column(String(100), nullable=False)
    engine_version = Column(String(50), nullable=False)

    title = Column(String(255), nullable=False)
    description = Column(Text)
    vulnerability_key = Column(String(255), nullable=False, index=True)
    cwe_id = Column(String(50), index=True)
    cve_id = Column(String(50), index=True)

    severity = Column(String(50), index=True)
    confidence = Column(String(50), default="potential", nullable=False)
    exploitability = Column(String(50))
    exposure = Column(String(50))
    business_impact = Column(String(50))

    validation_status = Column(String(50), default="potential", nullable=False)
    workflow_status = Column(String(50), default="open", nullable=False)
    disposition = Column(String(50))

    evidence_refs = Column(JSON().with_variant(JSONB, "postgresql"), default=list, nullable=False)
    remediation = Column(Text)

    first_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    observations = relationship(
        "Observation",
        secondary=finding_observations,
        backref="findings",
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "asset_id",
            "vulnerability_key",
            name="uq_finding_deduplication",
        ),
        Index("ix_findings_tenant_severity", "tenant_id", "severity"),
    )
