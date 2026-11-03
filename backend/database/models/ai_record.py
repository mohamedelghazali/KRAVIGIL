import uuid
from datetime import datetime
from sqlalchemy import JSON, Column, String, DateTime, ForeignKey, Integer, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database.models.base import Base

class AIAnalysisRecord(Base):
    __tablename__ = 'ai_analysis_records'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True)
    finding_id = Column(UUID(as_uuid=True), ForeignKey('findings.id', ondelete='CASCADE'), nullable=False, index=True)
    provider = Column(String(50), nullable=False)
    model_name = Column(String(100), nullable=False)
    prompt_tokens = Column(Integer, default=0, nullable=False)
    completion_tokens = Column(Integer, default=0, nullable=False)
    status = Column(String(50), nullable=False)
    response_raw = Column(JSON().with_variant(JSONB, "postgresql"))
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (Index('ix_ai_records_tenant_finding', 'tenant_id', 'finding_id'),)
