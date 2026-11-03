import uuid
from datetime import datetime
from sqlalchemy import JSON, Column, String, Float, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from backend.database.models.base import Base

class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    finding_id = Column(UUID(as_uuid=True), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True)
    
    cvss_score = Column(Float)
    epss_score = Column(Float)
    kev_status = Column(Boolean, default=False)
    asset_criticality = Column(String(20), default="medium")
    exposure = Column(String(50), default="unknown")
    
    calculated_risk_score = Column(Float, nullable=False)
    risk_level = Column(String(20), nullable=False, index=True)
    
    scoring_model_version = Column(String(20), default="1.0")
    policy_version = Column(String(20), default="1.0")
    explanation = Column(JSON().with_variant(JSONB, "postgresql"), default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_risk_tenant_level", "tenant_id", "risk_level"),
        Index("ix_risk_tenant_finding", "tenant_id", "finding_id"),
    )
