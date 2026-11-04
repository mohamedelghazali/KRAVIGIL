import hashlib
import uuid
from io import BytesIO

import pytest

import backend.services.evidence.evidence_manager as evidence_module
from backend.database.models.asset import Asset
from backend.database.models.evidence import Evidence
from backend.database.models.scan import Scan
from backend.database.models.target import Target
from backend.database.models.user import Organization


class FakeStorage:
    def __init__(self):
        self.objects = {}

    def upload_stream(self, object_key, stream, content_type):
        payload = stream.read()
        self.objects[object_key] = payload
        return object_key, hashlib.sha256(payload).hexdigest(), len(payload)

    def delete_object(self, object_key):
        self.objects.pop(object_key, None)


def _create_scan(db_session):
    tenant_id = uuid.uuid4()
    target_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    scan_id = uuid.uuid4()
    db_session.add(Organization(id=tenant_id, name=f"evidence-{tenant_id}"))
    db_session.flush()
    db_session.add(
        Target(
            id=target_id,
            tenant_id=tenant_id,
            name="Evidence test target",
            ip_address="192.0.2.120",
            is_authorized=True,
        )
    )
    db_session.flush()
    db_session.add(
        Asset(
            id=asset_id,
            tenant_id=tenant_id,
            target_id=target_id,
            ip_address="192.0.2.120",
        )
    )
    db_session.add(
        Scan(
            id=scan_id,
            tenant_id=tenant_id,
            target_id=target_id,
            asset_id=asset_id,
            status="COMPLETED",
            scan_type="NETWORK",
        )
    )
    db_session.commit()
    return tenant_id, scan_id


def test_refresh_failure_after_commit_preserves_evidence_object(
    db_session, monkeypatch
):
    tenant_id, scan_id = _create_scan(db_session)
    storage = FakeStorage()
    monkeypatch.setattr(evidence_module, "MinIOClient", lambda: storage)
    manager = evidence_module.EvidenceManager(db_session)

    original_refresh = db_session.refresh

    def fail_refresh(instance, *args, **kwargs):
        if isinstance(instance, Evidence):
            raise RuntimeError("refresh connection interrupted")
        return original_refresh(instance, *args, **kwargs)

    monkeypatch.setattr(db_session, "refresh", fail_refresh)

    with pytest.raises(RuntimeError, match="refresh connection interrupted"):
        manager.store_evidence(
            tenant_id=tenant_id,
            scan_id=scan_id,
            finding_id=None,
            stream=BytesIO(b"committed evidence"),
            content_type="application/octet-stream",
        )

    persisted = (
        db_session.query(Evidence)
        .filter(Evidence.tenant_id == tenant_id, Evidence.scan_id == scan_id)
        .one()
    )
    assert persisted.object_key in storage.objects
    assert storage.objects[persisted.object_key] == b"committed evidence"
    assert persisted.sha256 == hashlib.sha256(b"committed evidence").hexdigest()


def test_database_commit_failure_cleans_up_uploaded_evidence(
    db_session, monkeypatch
):
    tenant_id, scan_id = _create_scan(db_session)
    storage = FakeStorage()
    monkeypatch.setattr(evidence_module, "MinIOClient", lambda: storage)
    manager = evidence_module.EvidenceManager(db_session)

    original_commit = db_session.commit

    def fail_commit():
        raise RuntimeError("database commit failed")

    monkeypatch.setattr(db_session, "commit", fail_commit)

    with pytest.raises(RuntimeError, match="database commit failed"):
        manager.store_evidence(
            tenant_id=tenant_id,
            scan_id=scan_id,
            finding_id=None,
            stream=BytesIO(b"uncommitted evidence"),
            content_type="application/octet-stream",
        )

    monkeypatch.setattr(db_session, "commit", original_commit)
    db_session.rollback()
    assert storage.objects == {}
    assert (
        db_session.query(Evidence)
        .filter(Evidence.tenant_id == tenant_id, Evidence.scan_id == scan_id)
        .count()
        == 0
    )
