import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database.models.base import Base

class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)

    scan_id = Column(UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True)
    command_type = Column(String(50), nullable=False)
    parameters = Column(JSONB, nullable=False)

    status = Column(String(50), default="PENDING", nullable=False, index=True)
    error_message = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    dispatched_at = Column(DateTime)
    completed_at = Column(DateTime)

    __table_args__ = (
        Index("ix_agent_tasks_agent_status", "agent_id", "status"),
    )
