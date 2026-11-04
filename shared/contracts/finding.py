"""Transport-neutral finding contract shared by API, workers and integrations."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from shared.enums.severity import Severity
from shared.enums.status import FindingWorkflowStatus, ValidationStatus


class FindingContract(BaseModel):
    """Canonical normalized finding payload; never includes tenant secrets or storage keys."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    tenant_id: UUID
    asset_id: UUID
    vulnerability_key: str = Field(min_length=1, max_length=255)
    engine_id: str = Field(min_length=1, max_length=100)
    engine_version: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    severity: Severity
    confidence: str = Field(min_length=1, max_length=50)
    validation_status: ValidationStatus = ValidationStatus.POTENTIAL
    workflow_status: FindingWorkflowStatus = FindingWorkflowStatus.OPEN
    cwe_id: str | None = Field(default=None, max_length=50)
    cve_id: str | None = Field(default=None, max_length=50)
    evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    remediation: str | None = None
    first_seen: datetime
    last_seen: datetime

    @field_validator("vulnerability_key", "engine_id", "engine_version", "title", "confidence")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("evidence_refs")
    @classmethod
    def normalize_evidence_refs(cls, refs: list[str]) -> list[str]:
        normalized = [ref.strip() for ref in refs]
        if any(not ref for ref in normalized):
            raise ValueError("evidence references must not be blank")
        return list(dict.fromkeys(normalized))
