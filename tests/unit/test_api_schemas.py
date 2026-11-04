from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.schemas.finding import FindingCreate, FindingRead, FindingUpdate
from backend.schemas.scan import ScanCreate, ScanRead, ScanStatusUpdate
from shared.enums.severity import Severity
from shared.enums.status import FindingWorkflowStatus, ScanStatus, ValidationStatus


def test_scan_create_deduplicates_ports_and_rejects_extra_fields() -> None:
    request = ScanCreate(
        target_id=uuid4(),
        scan_type="NETWORK",
        ports=[443, 80, 443],
    )
    assert request.ports == [443, 80]
    with pytest.raises(ValidationError):
        ScanCreate(target_id=uuid4(), scan_type="NETWORK", unsafe=True)


@pytest.mark.parametrize("ports", [[0], [65536], [-1]])
def test_scan_create_rejects_invalid_ports(ports: list[int]) -> None:
    with pytest.raises(ValidationError):
        ScanCreate(target_id=uuid4(), scan_type="NETWORK", ports=ports)


def test_scan_read_normalizes_legacy_uppercase_status() -> None:
    now = datetime.now(timezone.utc)
    row = SimpleNamespace(
        id=uuid4(),
        target_id=uuid4(),
        status="PENDING",
        scan_type="NETWORK",
        created_at=now,
        started_at=None,
        finished_at=None,
    )
    response = ScanRead.model_validate(row)
    assert response.status is ScanStatus.PENDING


def test_scan_status_update_bounds_error_message() -> None:
    with pytest.raises(ValidationError):
        ScanStatusUpdate(status="failed", error_message="x" * 2049)


def test_finding_create_normalizes_values_and_evidence_refs() -> None:
    request = FindingCreate(
        asset_id=uuid4(),
        engine_id=" nmap ",
        engine_version=" 7.95 ",
        title=" Exposed service ",
        vulnerability_key=" service:22 ",
        severity="HIGH",
        evidence_refs=[" evidence://one ", "evidence://one"],
    )
    assert request.title == "Exposed service"
    assert request.severity is Severity.HIGH
    assert request.evidence_refs == ["evidence://one"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"title": "   "},
        {"vulnerability_key": ""},
        {"engine_id": " "},
        {"engine_version": ""},
        {"severity": "unknown"},
        {"evidence_refs": [""]},
    ],
)
def test_finding_create_rejects_invalid_input(overrides: dict[str, object]) -> None:
    payload: dict[str, object] = {
        "asset_id": uuid4(),
        "engine_id": "scanner",
        "engine_version": "1.0",
        "title": "Finding",
        "vulnerability_key": "scanner:finding",
        "severity": "medium",
    }
    payload.update(overrides)
    with pytest.raises(ValidationError):
        FindingCreate.model_validate(payload)


def test_finding_update_rejects_identity_and_tenant_mutation() -> None:
    with pytest.raises(ValidationError):
        FindingUpdate.model_validate({"tenant_id": str(uuid4())})


def test_finding_read_accepts_orm_shape() -> None:
    now = datetime.now(timezone.utc)
    row = SimpleNamespace(
        id=uuid4(),
        asset_id=uuid4(),
        title="TLS configuration issue",
        vulnerability_key="tls:weak-protocol",
        severity="critical",
        confidence="high",
        validation_status="confirmed",
        workflow_status="open",
        first_seen=now,
        last_seen=now,
        description=None,
        remediation=None,
    )
    response = FindingRead.model_validate(row)
    assert response.severity is Severity.CRITICAL
    assert response.validation_status is ValidationStatus.CONFIRMED
    assert response.workflow_status is FindingWorkflowStatus.OPEN
