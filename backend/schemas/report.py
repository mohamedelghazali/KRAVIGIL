"""Report request and safe status response contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

ReportType = Literal["PDF"]
ReportStatus = Literal["QUEUED", "RUNNING", "READY", "FAILED"]


class ReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_id: UUID
    report_type: ReportType = "PDF"


class ReportRead(BaseModel):
    """Public report status; excludes object storage key and internal errors."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scan_id: UUID
    report_type: ReportType
    status: ReportStatus
    created_at: datetime
    completed_at: datetime | None = None
    file_size_bytes: int | None = None
    expires_at: datetime | None = None
