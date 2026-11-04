import uuid

import pytest

from backend.services.correlation.deduplication import (
    canonical_vulnerability_key,
    highest_severity,
    merge_duplicate_findings,
)
from backend.services.correlation.fingerprint import finding_fingerprint
from backend.services.differential.snapshot_manager import SnapshotManager


def test_fingerprint_is_stable_and_tenant_scoped() -> None:
    tenant_id, asset_id = uuid.uuid4(), uuid.uuid4()
    first = finding_fingerprint(tenant_id, asset_id, "HTTPS:443", " CVE-2025-1234 ")
    second = finding_fingerprint(tenant_id, asset_id, "https:443", "cve-2025-1234")
    other_tenant = finding_fingerprint(uuid.uuid4(), asset_id, "https:443", "cve-2025-1234")
    assert first == second
    assert first != other_tenant
    assert len(first) == 64


def test_fingerprint_rejects_blank_vulnerability_key() -> None:
    with pytest.raises(ValueError):
        finding_fingerprint(uuid.uuid4(), uuid.uuid4(), None, "  ")


def test_canonical_key_and_severity_are_normalized() -> None:
    assert canonical_vulnerability_key("  CVE  2025-1234 ") == "cve 2025-1234"
    assert highest_severity("LOW", "critical", "Medium") == "critical"
    with pytest.raises(ValueError):
        highest_severity("low", "unclassified")


def test_duplicate_findings_merge_evidence_and_keep_highest_severity() -> None:
    result = merge_duplicate_findings(
        [
            {
                "vulnerability_key": "CVE-2025-1234",
                "severity": "medium",
                "evidence_refs": ["evidence://one"],
            },
            {
                "vulnerability_key": " cve-2025-1234 ",
                "severity": "HIGH",
                "evidence_refs": ["evidence://one", "evidence://two"],
            },
        ]
    )
    assert len(result) == 1
    assert result[0]["severity"] == "high"
    assert result[0]["evidence_refs"] == ["evidence://one", "evidence://two"]


def test_snapshot_comparison_is_deterministic_and_counts_changes() -> None:
    old = {
        "a": {"severity": "low", "validation_status": "potential"},
        "b": {"severity": "medium", "validation_status": "potential"},
    }
    new = {
        "b": {"severity": "high", "validation_status": "confirmed"},
        "c": {"severity": "critical", "validation_status": "potential"},
    }
    result = SnapshotManager.compare_snapshots(old, new)
    assert result["new"] == ["c"]
    assert result["resolved"] == ["a"]
    assert result["changed"] == [
        {
            "fingerprint": "b",
            "old": old["b"],
            "new": new["b"],
        }
    ]
    assert result["unchanged_count"] == 0
