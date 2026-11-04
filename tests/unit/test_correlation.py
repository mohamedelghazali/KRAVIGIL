import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.models.base import Base
from backend.database.models.asset import Asset
from backend.database.models.finding import Finding
from backend.database.models.observation import Observation
from backend.database.models.scan import Scan
from backend.database.models.target import Target
from backend.database.models.user import Organization
from backend.services.differential.incremental_processor import IncrementalProcessor

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



def _make_differential_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)(), engine


def test_snapshot_query_uses_observations_and_enforces_tenant_scope() -> None:
    db, engine = _make_differential_session()
    try:
        tenant_id = uuid.uuid4()
        target_id, asset_id, scan_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        observation_id, finding_id = uuid.uuid4(), uuid.uuid4()
        now = datetime.now(timezone.utc)
        organization = Organization(id=tenant_id, name="snapshot-tenant")
        target = Target(
            id=target_id, tenant_id=tenant_id, name="authorized target",
            ip_address="192.0.2.20", is_authorized=True,
        )
        asset = Asset(
            id=asset_id, tenant_id=tenant_id, target_id=target_id,
            ip_address="192.0.2.20",
        )
        scan = Scan(
            id=scan_id, tenant_id=tenant_id, target_id=target_id,
            asset_id=asset_id, status="COMPLETED", scan_type="NETWORK",
        )
        observation = Observation(
            id=observation_id, tenant_id=tenant_id, scan_id=scan_id,
            asset_id=asset_id, engine_id="nuclei", event_type="VULNERABILITY_FOUND",
            raw_data={"template_id": "tls/weak"},
        )
        finding = Finding(
            id=finding_id, tenant_id=tenant_id, asset_id=asset_id,
            engine_id="nuclei", engine_version="1.0",
            title="Weak TLS", vulnerability_key="tls/weak", severity="medium",
            confidence="potential", validation_status="potential",
            workflow_status="open", first_seen=now, last_seen=now,
            observations=[observation],
        )
        db.add_all([organization, target, asset, scan, finding])
        db.commit()

        snapshot = SnapshotManager(db).create_snapshot(tenant_id, scan_id)
        assert len(snapshot) == 1
        assert SnapshotManager(db).create_snapshot(uuid.uuid4(), scan_id) == {}
    finally:
        db.close()
        engine.dispose()


def test_incremental_processor_marks_only_tenant_finding_resolved() -> None:
    db, engine = _make_differential_session()
    try:
        tenant_id = uuid.uuid4()
        target_id, asset_id = uuid.uuid4(), uuid.uuid4()
        previous_scan_id, current_scan_id = uuid.uuid4(), uuid.uuid4()
        now = datetime.now(timezone.utc)
        organization = Organization(id=tenant_id, name="differential-tenant")
        target = Target(
            id=target_id, tenant_id=tenant_id, name="authorized target",
            ip_address="192.0.2.30", is_authorized=True,
        )
        asset = Asset(
            id=asset_id, tenant_id=tenant_id, target_id=target_id,
            ip_address="192.0.2.30",
        )
        previous_scan = Scan(
            id=previous_scan_id, tenant_id=tenant_id, target_id=target_id,
            asset_id=asset_id, status="COMPLETED", scan_type="NETWORK",
        )
        current_scan = Scan(
            id=current_scan_id, tenant_id=tenant_id, target_id=target_id,
            asset_id=asset_id, status="COMPLETED", scan_type="NETWORK",
        )
        observation = Observation(
            id=uuid.uuid4(), tenant_id=tenant_id, scan_id=previous_scan_id,
            asset_id=asset_id, engine_id="nuclei", event_type="VULNERABILITY_FOUND",
            raw_data={"template_id": "tls/weak"},
        )
        finding = Finding(
            id=uuid.uuid4(), tenant_id=tenant_id, asset_id=asset_id,
            engine_id="nuclei", engine_version="1.0",
            title="Weak TLS", vulnerability_key="tls/weak", severity="medium",
            confidence="potential", validation_status="potential",
            workflow_status="open", first_seen=now, last_seen=now,
            observations=[observation],
        )
        db.add_all([organization, target, asset, previous_scan, current_scan, finding])
        db.commit()

        result = IncrementalProcessor(db).process_differential(
            tenant_id, current_scan_id, previous_scan_id
        )
        db.refresh(finding)
        assert result["resolved_findings_count"] == 1
        assert finding.workflow_status == "resolved"
    finally:
        db.close()
        engine.dispose()
