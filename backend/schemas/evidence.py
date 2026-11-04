"""Evidence metadata contracts; object storage keys remain server-controlled."""

import re
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvidenceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scan_id: UUID
    finding_id: UUID | None = None
    content_type: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0, le=2_147_483_647)
    sha256: str
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    retention_policy: str = Field(default="standard", min_length=1, max_length=50)

    @field_validator("sha256")
    @classmethod
    def validate_sha256(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", normalized):
            raise ValueError("sha256 must be a 64-character hexadecimal digest")
        return normalized


class EvidenceRead(BaseModel):
    """Safe metadata projection; omits object_key, backend credentials and version IDs."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scan_id: UUID
    finding_id: UUID | None = None
    content_type: str
    size_bytes: int
    sha256: str
    encryption: str
    retention_policy: str
    created_at: datetime
