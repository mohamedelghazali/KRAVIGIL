from types import SimpleNamespace
import uuid

from backend.database.models.scan import Scan
from backend.database.models.target import Target
from backend.database.models.user import User
import backend.api.v1.endpoints.scans as scans_endpoint


def test_network_scan_pipeline_persists_and_dispatches_tenant_scoped_task(
    client, auth_headers, db_session, monkeypatch
):
    user = db_session.query(User).filter(User.email == "admin@testorg.com").first()
    assert user is not None
    target = Target(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        name="Integration authorized target",
        ip_address="192.0.2.90",
        is_authorized=True,
    )
    db_session.add(target)
    db_session.commit()

    dispatched = {}

    def fake_delay(**kwargs):
        dispatched.update(kwargs)
        return SimpleNamespace(id="integration-task-001")

    monkeypatch.setattr(
        scans_endpoint,
        "_resolve_scan_ip",
        lambda target, guard: target.ip_address,
    )
    monkeypatch.setattr(
        scans_endpoint,
        "run_network_scan",
        SimpleNamespace(delay=fake_delay),
    )

    response = client.post(
        "/api/v1/scans/network",
        json={"target_id": str(target.id), "ports": [80, 443]},
        headers=auth_headers,
    )

    assert response.status_code == 202, response.text
    payload = response.json()
    scan_id = uuid.UUID(payload["id"])
    assert payload["scan_type"] == "NETWORK"
    assert payload["status"] == "PENDING"
    assert dispatched == {
        "tenant_id": str(user.tenant_id),
        "scan_id": str(scan_id),
        "asset_id": dispatched["asset_id"],
        "target_ip": "192.0.2.90",
        "ports": [80, 443],
    }

    scan = (
        db_session.query(Scan)
        .filter(Scan.id == scan_id, Scan.tenant_id == user.tenant_id)
        .first()
    )
    assert scan is not None
    assert scan.status == "PENDING"
    assert scan.task_id == "integration-task-001"
    assert scan.asset_id is not None


def test_network_scan_rejects_cross_tenant_target_without_dispatch(
    client, auth_headers, db_session, monkeypatch
):
    user = db_session.query(User).filter(User.email == "admin@testorg.com").first()
    assert user is not None
    from backend.database.models.user import Organization

    other_tenant_id = uuid.uuid4()
    db_session.add(
        Organization(id=other_tenant_id, name=f"other-scan-tenant-{other_tenant_id}")
    )
    db_session.flush()
    target = Target(
        id=uuid.uuid4(),
        tenant_id=other_tenant_id,
        name="Other tenant target",
        ip_address="192.0.2.91",
        is_authorized=True,
    )
    db_session.add(target)
    db_session.commit()

    called = False

    def fake_delay(**kwargs):
        nonlocal called
        called = True
        return SimpleNamespace(id="should-not-run")

    monkeypatch.setattr(
        scans_endpoint,
        "_resolve_scan_ip",
        lambda target, guard: target.ip_address,
    )
    monkeypatch.setattr(
        scans_endpoint,
        "run_network_scan",
        SimpleNamespace(delay=fake_delay),
    )

    response = client.post(
        "/api/v1/scans/network",
        json={"target_id": str(target.id), "ports": [80]},
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert called is False
