import pytest

from shared.enums.severity import Severity
from shared.enums.status import (
    FindingWorkflowStatus,
    ScanStatus,
    ValidationStatus,
)


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("critical", Severity.CRITICAL),
        ("HIGH", Severity.HIGH),
        (" medium ", Severity.MEDIUM),
        ("LOW", Severity.LOW),
        ("info", Severity.INFO),
    ],
)
def test_severity_normalizes_scanner_values(raw_value: str, expected: Severity) -> None:
    assert Severity(raw_value) is expected


def test_severity_engine_value_is_uppercase() -> None:
    assert Severity.CRITICAL.engine_value == "CRITICAL"


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("PENDING", ScanStatus.PENDING),
        ("queued", ScanStatus.QUEUED),
        ("RUNNING", ScanStatus.RUNNING),
        ("completed", ScanStatus.COMPLETED),
        ("FAILED", ScanStatus.FAILED),
        ("cancelled", ScanStatus.CANCELLED),
    ],
)
def test_scan_status_accepts_storage_and_api_values(
    raw_value: str, expected: ScanStatus
) -> None:
    assert ScanStatus(raw_value) is expected


def test_validation_status_matches_frontend_contract() -> None:
    assert {item.value for item in ValidationStatus} == {
        "potential",
        "confirmed",
        "inconclusive",
        "rejected",
        "needs_review",
    }


def test_finding_workflow_status_matches_persisted_default() -> None:
    assert FindingWorkflowStatus.OPEN.value == "open"


@pytest.mark.parametrize("raw_value", ["", "unknown", "done", None])
def test_invalid_values_are_rejected(raw_value: object) -> None:
    with pytest.raises(ValueError):
        Severity(raw_value)  # type: ignore[arg-type]
