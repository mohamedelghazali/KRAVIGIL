"""Validated API contracts for scan creation and representation."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from shared.enums.status import ScanStatus

ScanType = Literal["NETWORK", "WEB", "SAST", "CLOUD"]


class ScanCreate(BaseModel):
    """Request contract for creating a scan against an existing authorized target.

    Authorization and tenant ownership are enforced by the endpoint/service layer;
    accepting a UUID here never grants access to that target.
    """

    model_config = ConfigDict(extra="forbid")

    target_id: UUID
    scan_type: ScanType
    ports: list[int] = Field(default_factory=lambda: [22, 80, 443, 8080], max_length=1000)

    @field_validator("ports")
    @classmethod
    def validate_ports(cls, ports: list[int]) -> list[int]:
        if any(port < 1 or port > 65535 for port in ports):
            raise ValueError("ports must contain integers between 1 and 65535")
        # Preserve input order while removing duplicates.
        return list(dict.fromkeys(ports))


class ScanRead(BaseModel):
    """Public scan representation; excludes internal worker and error details."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    target_id: UUID
    status: ScanStatus
    scan_type: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ScanStatusUpdate(BaseModel):
    """Internal lifecycle update contract; terminal-state rules belong to service logic."""

    model_config = ConfigDict(extra="forbid")

    status: ScanStatus
    error_message: str | None = Field(default=None, max_length=2048)
