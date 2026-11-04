import hashlib
import uuid

import backend.services.evidence.evidence_manager as evidence_module
from backend.database.models.asset import Asset
from backend.database.models.evidence import Evidence
from backend.database.models.scan import Scan
from backend.database.models.target import Target


class FakeStorage:
    def __init__(self):
        self.objects = {}
        self.fail_delete = False

    def delete_object(self, object_key):
        if self.fail_delete:
            raise RuntimeError("object storage unavailable")
        self.objects.pop(object_key, None)


def _create_chain(db_session, tenant_id):
    target = Target(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="Cascade cleanup target",
        ip_address="192.0.2.180",
        is_authorized=True,
    )
    db_session.add(target)
    db_session.flush()
    asset = Asset(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        target_id=target.id,
        ip_address="192.0.2.180",
    )
    db_session.add(asset)
    db_session.flush()
    scan = Scan(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        target_id=target.id,
        asset_id=asset.id,
        status="COMPLETED",
        scan_type="NETWORK",
    )
    db_session.add(scan)
    db_session.flush()

    payload = b"evidence object that must not become orphaned"
    object_key = f"{tenant_id}/{scan.id}/{uuid.uuid4()}.bin"
    evidence = Evidence(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        scan_id=scan.id,
        object_key=object_key,
        storage_backend="minio",
        content_type="application/octet-stream",
        size_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        metadata_json={},
    )
    db_session.add(evidence)
    db_session.commit()
    return target, asset, scan, evidence, object_key, payload


def _patch_storage(monkeypatch, object_key, payload):
    storage = FakeStorage()
    storage.objects[object_key] = payload
    monkeypatch.setattr(evidence_module, "MinIOClient", lambda: storage)
    return storage


def test_scan_delete_removes_evidence_object_before_row_cascade(
    client, db_session, integration_admin, monkeypatch
):
    user, headers = integration_admin
    target, asset, scan, evidence, object_key, payload = _create_chain(
        db_session, user.tenant_id
    )
    scan_id, evidence_id = scan.id, evidence.id
    storage = _patch_storage(monkeypatch, object_key, payload)

    response = client.delete(f"/api/v1/scans/{scan_id}", headers=headers)

    assert response.status_code == 204, response.text
    assert db_session.query(Scan).filter(Scan.id == scan_id).count() == 0
    assert db_session.query(Evidence).filter(Evidence.id == evidence_id).count() == 0
    assert object_key not in storage.objects


def test_asset_delete_cleans_all_scan_evidence_before_cascade(
    client, db_session, integration_admin, monkeypatch
):
    user, headers = integration_admin
    target, asset, scan, evidence, object_key, payload = _create_chain(
        db_session, user.tenant_id
    )
    asset_id, scan_id, evidence_id = asset.id, scan.id, evidence.id
    storage = _patch_storage(monkeypatch, object_key, payload)

    response = client.delete(f"/api/v1/assets/{asset_id}", headers=headers)

    assert response.status_code == 204, response.text
    assert db_session.query(Asset).filter(Asset.id == asset_id).count() == 0
    assert db_session.query(Scan).filter(Scan.id == scan_id).count() == 0
    assert db_session.query(Evidence).filter(Evidence.id == evidence_id).count() == 0
    assert object_key not in storage.objects


def test_target_delete_cleans_all_descendant_evidence_before_cascade(
    client, db_session, integration_admin, monkeypatch
):
    user, headers = integration_admin
    target, asset, scan, evidence, object_key, payload = _create_chain(
        db_session, user.tenant_id
    )
    target_id, asset_id, scan_id, evidence_id = target.id, asset.id, scan.id, evidence.id
    storage = _patch_storage(monkeypatch, object_key, payload)

    response = client.delete(f"/api/v1/targets/{target_id}", headers=headers)

    assert response.status_code == 204, response.text
    assert db_session.query(Target).filter(Target.id == target_id).count() == 0
    assert db_session.query(Asset).filter(Asset.id == asset_id).count() == 0
    assert db_session.query(Scan).filter(Scan.id == scan_id).count() == 0
    assert db_session.query(Evidence).filter(Evidence.id == evidence_id).count() == 0
    assert object_key not in storage.objects


def test_parent_delete_stays_pending_when_evidence_storage_delete_fails(
    client, db_session, integration_admin, monkeypatch
):
    user, headers = integration_admin
    target, asset, scan, evidence, object_key, payload = _create_chain(
        db_session, user.tenant_id
    )
    scan_id, evidence_id = scan.id, evidence.id
    storage = _patch_storage(monkeypatch, object_key, payload)
    storage.fail_delete = True

    response = client.delete(f"/api/v1/scans/{scan_id}", headers=headers)

    assert response.status_code == 503
    assert db_session.query(Scan).filter(Scan.id == scan_id).count() == 1
    pending = db_session.query(Evidence).filter(Evidence.id == evidence_id).one()
    assert pending.deletion_status == "PENDING_DELETE"
    assert object_key in storage.objects

    storage.fail_delete = False
    retry = client.delete(f"/api/v1/scans/{scan_id}", headers=headers)
    assert retry.status_code == 204, retry.text
    assert db_session.query(Scan).filter(Scan.id == scan_id).count() == 0
    assert db_session.query(Evidence).filter(Evidence.id == evidence_id).count() == 0
    assert object_key not in storage.objects


def test_scan_delete_rejects_active_scan_without_touching_evidence(
    client, db_session, integration_admin, monkeypatch
):
    user, headers = integration_admin
    _, _, scan, evidence, object_key, payload = _create_chain(db_session, user.tenant_id)
    scan_id, evidence_id = scan.id, evidence.id
    scan.status = "RUNNING"
    db_session.commit()
    storage = _patch_storage(monkeypatch, object_key, payload)

    response = client.delete(f"/api/v1/scans/{scan_id}", headers=headers)

    assert response.status_code == 409
    assert db_session.query(Scan).filter(Scan.id == scan_id).count() == 1
    assert db_session.query(Evidence).filter(Evidence.id == evidence_id).count() == 1
    assert object_key in storage.objects


def test_asset_delete_rejects_active_descendant_scan(
    client, db_session, integration_admin, monkeypatch
):
    user, headers = integration_admin
    _, asset, scan, evidence, object_key, payload = _create_chain(db_session, user.tenant_id)
    asset_id, scan_id, evidence_id = asset.id, scan.id, evidence.id
    scan.status = "PENDING"
    db_session.commit()
    storage = _patch_storage(monkeypatch, object_key, payload)

    response = client.delete(f"/api/v1/assets/{asset_id}", headers=headers)

    assert response.status_code == 409
    assert db_session.query(Asset).filter(Asset.id == asset_id).count() == 1
    assert db_session.query(Scan).filter(Scan.id == scan_id).count() == 1
    assert db_session.query(Evidence).filter(Evidence.id == evidence_id).count() == 1
    assert object_key in storage.objects


def test_target_delete_rejects_active_descendant_scan(
    client, db_session, integration_admin, monkeypatch
):
    user, headers = integration_admin
    target, _, scan, evidence, object_key, payload = _create_chain(db_session, user.tenant_id)
    target_id, scan_id, evidence_id = target.id, scan.id, evidence.id
    scan.status = "RUNNING"
    db_session.commit()
    storage = _patch_storage(monkeypatch, object_key, payload)

    response = client.delete(f"/api/v1/targets/{target_id}", headers=headers)

    assert response.status_code == 409
    assert db_session.query(Target).filter(Target.id == target_id).count() == 1
    assert db_session.query(Scan).filter(Scan.id == scan_id).count() == 1
    assert db_session.query(Evidence).filter(Evidence.id == evidence_id).count() == 1
    assert object_key in storage.objects
