"""Transport-neutral scan lifecycle event contract shared by API and workers."""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from shared.enums.status import ScanStatus


class ScanEvent(BaseModel):
    """Tenant-scoped scan event envelope for asynchronous worker boundaries."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    scan_id: UUID
    target_id: UUID
    asset_id: UUID
    scan_type: Literal["NETWORK", "WEB", "SAST", "CLOUD"]
    status: ScanStatus
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    task_id: str | None = Field(default=None, max_length=255)
    error_message: str | None = Field(default=None, max_length=2048)
