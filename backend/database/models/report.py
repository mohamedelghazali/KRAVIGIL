import uuid
from datetime import datetime
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, String
from sqlalchemy import Uuid
from sqlalchemy.orm import relationship
from backend.database.models.base import Base

class Report(Base):
    __tablename__ = "reports"
    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    scan_id = Column(Uuid(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True)
    report_type = Column(String(50), default="PDF", nullable=False)
    status = Column(String(50), default="QUEUED", nullable=False, index=True)
    object_key = Column(String(512))
    file_size_bytes = Column(BigInteger)
    sha256 = Column(String(64))
    error_message = Column(String(2048))
    requested_by = Column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime)
    expires_at = Column(DateTime)
    scan = relationship("Scan")
    __table_args__ = (Index("ix_reports_tenant_status", "tenant_id", "status"),)
