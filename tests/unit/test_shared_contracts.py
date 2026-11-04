from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from shared.contracts.finding import FindingContract
from shared.contracts.scan import ScanEvent
from shared.enums.severity import Severity
from shared.enums.status import FindingWorkflowStatus, ScanStatus


def test_scan_event_validates_tenant_scoped_worker_envelope() -> None:
    event = ScanEvent(
        tenant_id=uuid4(),
        scan_id=uuid4(),
        target_id=uuid4(),
        asset_id=uuid4(),
        scan_type="NETWORK",
        status="PENDING",
    )
    assert event.status is ScanStatus.PENDING
    assert event.occurred_at.tzinfo is not None


def test_scan_event_rejects_unknown_fields_and_scan_types() -> None:
    payload = {
        "tenant_id": uuid4(),
        "scan_id": uuid4(),
        "target_id": uuid4(),
        "asset_id": uuid4(),
        "scan_type": "UNKNOWN",
        "status": "RUNNING",
    }
    with pytest.raises(ValidationError):
        ScanEvent.model_validate(payload)
    payload["scan_type"] = "WEB"
    payload["admin"] = True
    with pytest.raises(ValidationError):
        ScanEvent.model_validate(payload)


def test_scan_event_bounds_error_message() -> None:
    with pytest.raises(ValidationError):
        ScanEvent(
            tenant_id=uuid4(),
            scan_id=uuid4(),
            target_id=uuid4(),
            asset_id=uuid4(),
            scan_type="SAST",
            status="FAILED",
            error_message="x" * 2049,
        )


def test_finding_contract_normalizes_canonical_payload() -> None:
    now = datetime.now(timezone.utc)
    finding = FindingContract(
        id=uuid4(),
        tenant_id=uuid4(),
        asset_id=uuid4(),
        vulnerability_key=" cve:CVE-2025-1234 ",
        engine_id=" nuclei ",
        engine_version=" 3.4 ",
        title=" Exposed endpoint ",
        severity="HIGH",
        confidence=" confirmed ",
        first_seen=now,
        last_seen=now,
        evidence_refs=[" evidence://a ", "evidence://a"],
        workflow_status="RESOLVED",
    )
    assert finding.severity is Severity.HIGH
    assert finding.workflow_status is FindingWorkflowStatus.RESOLVED
    assert finding.vulnerability_key == "cve:CVE-2025-1234"
    assert finding.evidence_refs == ["evidence://a"]


def test_finding_contract_rejects_invalid_severity_and_tenant_override() -> None:
    now = datetime.now(timezone.utc)
    payload = {
        "id": uuid4(),
        "tenant_id": uuid4(),
        "asset_id": uuid4(),
        "vulnerability_key": "scanner:issue",
        "engine_id": "scanner",
        "engine_version": "1.0",
        "title": "Issue",
        "severity": "unknown",
        "confidence": "potential",
        "first_seen": now,
        "last_seen": now,
    }
    with pytest.raises(ValidationError):
        FindingContract.model_validate(payload)
    payload["severity"] = "low"
    payload["object_key"] = "private/path"
    with pytest.raises(ValidationError):
        FindingContract.model_validate(payload)
