"""Validated API contracts for normalized vulnerability findings."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from shared.enums.severity import Severity
from shared.enums.status import FindingWorkflowStatus, ValidationStatus


class FindingCreate(BaseModel):
    """Normalized scanner finding input; tenant ownership is resolved server-side."""

    model_config = ConfigDict(extra="forbid")

    asset_id: UUID
    engine_id: str = Field(min_length=1, max_length=100)
    engine_version: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=255)
    vulnerability_key: str = Field(min_length=1, max_length=255)
    description: str | None = None
    severity: Severity
    confidence: str = Field(default="potential", min_length=1, max_length=50)
    cwe_id: str | None = Field(default=None, max_length=50)
    cve_id: str | None = Field(default=None, max_length=50)
    evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    remediation: str | None = None

    @field_validator("title", "vulnerability_key", "engine_id", "engine_version")
    @classmethod
    def reject_whitespace_only(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("evidence_refs")
    @classmethod
    def validate_evidence_refs(cls, refs: list[str]) -> list[str]:
        normalized = [ref.strip() for ref in refs]
        if any(not ref for ref in normalized):
            raise ValueError("evidence references must not be blank")
        return list(dict.fromkeys(normalized))


class FindingUpdate(BaseModel):
    """User-editable finding workflow fields; identity and tenant fields are immutable."""

    model_config = ConfigDict(extra="forbid")

    validation_status: ValidationStatus | None = None
    workflow_status: FindingWorkflowStatus | None = None
    disposition: str | None = Field(default=None, max_length=100)
    remediation: str | None = None


class FindingRead(BaseModel):
    """Public finding representation without tenant or storage internals."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    asset_id: UUID
    title: str
    vulnerability_key: str
    severity: Severity | None = None
    confidence: str
    validation_status: ValidationStatus
    workflow_status: FindingWorkflowStatus
    first_seen: datetime
    last_seen: datetime
    description: str | None = None
    remediation: str | None = None
