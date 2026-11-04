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
        self.fail_delete = False
        self.fail_upload_after_write = False

    def upload_stream(self, object_key, stream, content_type):
        payload = stream.read()
        self.objects[object_key] = payload
        if self.fail_upload_after_write:
            raise RuntimeError("upload response lost after object write")
        return object_key, hashlib.sha256(payload).hexdigest(), len(payload)

    def delete_object(self, object_key):
        if self.fail_delete:
            raise RuntimeError("object storage unavailable")
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


def _create_evidence(db_session, tenant_id, scan_id, payload=b"evidence to delete"):
    object_key = f"{tenant_id}/{scan_id}/{uuid.uuid4()}.bin"
    record = Evidence(
        tenant_id=tenant_id,
        scan_id=scan_id,
        object_key=object_key,
        storage_backend="minio",
        content_type="application/octet-stream",
        size_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        metadata_json={},
    )
    db_session.add(record)
    db_session.commit()
    return record, object_key, payload


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



def test_ambiguous_upload_failure_cleans_up_remote_object(
    db_session, monkeypatch
):
    tenant_id, scan_id = _create_scan(db_session)
    storage = FakeStorage()
    storage.fail_upload_after_write = True
    monkeypatch.setattr(evidence_module, "MinIOClient", lambda: storage)
    manager = evidence_module.EvidenceManager(db_session)

    with pytest.raises(RuntimeError, match="upload response lost after object write"):
        manager.store_evidence(
            tenant_id=tenant_id,
            scan_id=scan_id,
            finding_id=None,
            stream=BytesIO(b"remotely written but unacknowledged"),
            content_type="application/octet-stream",
        )

    assert storage.objects == {}
    assert (
        db_session.query(Evidence)
        .filter(Evidence.tenant_id == tenant_id, Evidence.scan_id == scan_id)
        .count()
        == 0
    )


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


def test_storage_delete_failure_keeps_retryable_hidden_tombstone(
    db_session, monkeypatch
):
    tenant_id, scan_id = _create_scan(db_session)
    record, object_key, payload = _create_evidence(db_session, tenant_id, scan_id)
    storage = FakeStorage()
    storage.objects[object_key] = payload
    storage.fail_delete = True
    monkeypatch.setattr(evidence_module, "MinIOClient", lambda: storage)
    manager = evidence_module.EvidenceManager(db_session)

    with pytest.raises(RuntimeError, match="object storage unavailable"):
        manager.delete_evidence(record.id, tenant_id)

    persisted = db_session.query(Evidence).filter(Evidence.id == record.id).one()
    assert persisted.deletion_status == "PENDING_DELETE"
    assert persisted.deletion_requested_at is not None
    assert object_key in storage.objects
    with pytest.raises(ValueError, match="Evidence not found"):
        manager.get_download_url(record.id, tenant_id)

    storage.fail_delete = False
    manager.delete_evidence(record.id, tenant_id)
    assert db_session.query(Evidence).filter(Evidence.id == record.id).count() == 0
    assert object_key not in storage.objects


def test_final_database_commit_failure_can_be_retried_after_object_removal(
    db_session, monkeypatch
):
    tenant_id, scan_id = _create_scan(db_session)
    record, object_key, payload = _create_evidence(db_session, tenant_id, scan_id)
    storage = FakeStorage()
    storage.objects[object_key] = payload
    monkeypatch.setattr(evidence_module, "MinIOClient", lambda: storage)
    manager = evidence_module.EvidenceManager(db_session)
    original_commit = db_session.commit
    commits = 0

    def fail_second_commit():
        nonlocal commits
        commits += 1
        if commits == 2:
            raise RuntimeError("final database commit failed")
        return original_commit()

    monkeypatch.setattr(db_session, "commit", fail_second_commit)
    with pytest.raises(RuntimeError, match="final database commit failed"):
        manager.delete_evidence(record.id, tenant_id)

    monkeypatch.setattr(db_session, "commit", original_commit)
    db_session.rollback()
    persisted = db_session.query(Evidence).filter(Evidence.id == record.id).one()
    assert persisted.deletion_status == "PENDING_DELETE"
    assert object_key not in storage.objects

    manager.delete_evidence(record.id, tenant_id)
    assert db_session.query(Evidence).filter(Evidence.id == record.id).count() == 0


def test_initial_tombstone_commit_failure_does_not_remove_object(
    db_session, monkeypatch
):
    tenant_id, scan_id = _create_scan(db_session)
    record, object_key, payload = _create_evidence(db_session, tenant_id, scan_id)
    storage = FakeStorage()
    storage.objects[object_key] = payload
    monkeypatch.setattr(evidence_module, "MinIOClient", lambda: storage)
    manager = evidence_module.EvidenceManager(db_session)
    original_commit = db_session.commit

    def fail_commit():
        raise RuntimeError("tombstone commit failed")

    monkeypatch.setattr(db_session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="tombstone commit failed"):
        manager.delete_evidence(record.id, tenant_id)

    monkeypatch.setattr(db_session, "commit", original_commit)
    db_session.rollback()
    persisted = db_session.query(Evidence).filter(Evidence.id == record.id).one()
    assert persisted.deletion_status == "ACTIVE"
    assert object_key in storage.objects
