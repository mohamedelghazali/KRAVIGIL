import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text, Table
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from backend.database.models.base import Base

finding_observations = Table(
    "finding_observations",
    Base.metadata,
    Column("finding_id", UUID(as_uuid=True), ForeignKey("findings.id"), primary_key=True),
    Column("observation_id", UUID(as_uuid=True), ForeignKey("observations.id"), primary_key=True)
)

class Finding(Base):
    __tablename__ = "findings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("assets.id"), nullable=False, index=True)
    service_id = Column(String)
    engine_id = Column(String, nullable=False)
    engine_version = Column(String, nullable=False)
    
    title = Column(String, nullable=False)
    description = Column(Text)
    vulnerability_key = Column(String, index=True)
    cwe_id = Column(String, index=True)
    cve_id = Column(String, index=True)
    
    severity = Column(String, index=True)
    confidence = Column(String, default="potential")
    exploitability = Column(String)
    exposure = Column(String)
    business_impact = Column(String)
    
    validation_status = Column(String, default="potential")
    workflow_status = Column(String, default="open")
    disposition = Column(String)
    
    evidence_refs = Column(JSONB, default=list)
    remediation = Column(Text)
    
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    observations = relationship("Observation", secondary=finding_observations, backref="findings")
