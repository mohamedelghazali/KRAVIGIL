from types import SimpleNamespace
import uuid

import pytest

from backend.database.models.asset import Asset
from backend.database.models.scan import Scan
from backend.database.models.target import Target
import backend.api.v1.endpoints.scans as scans_endpoint


def test_network_scan_pipeline_persists_and_dispatches_tenant_scoped_task(
    client, db_session, integration_admin, monkeypatch
):
    user, headers = integration_admin
    target = Target(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        name="Integration authorized target",
        ip_address="192.0.2.90",
        is_authorized=True,
    )
    db_session.add(target)
    db_session.commit()

    dispatched = []

    def fake_delay(**kwargs):
        dispatched.append(kwargs)
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
        headers=headers,
    )

    assert response.status_code == 202, response.text
    payload = response.json()
    scan_id = uuid.UUID(payload["id"])
    assert payload["scan_type"] == "NETWORK"
    assert payload["status"] == "PENDING"
    assert len(dispatched) == 1
    assert dispatched[0]["tenant_id"] == str(user.tenant_id)
    assert dispatched[0]["scan_id"] == str(scan_id)
    assert dispatched[0]["target_ip"] == "192.0.2.90"
    assert dispatched[0]["ports"] == [80, 443]
    assert dispatched[0]["asset_id"]

    scan = (
        db_session.query(Scan)
        .filter(Scan.id == scan_id, Scan.tenant_id == user.tenant_id)
        .first()
    )
    assert scan is not None
    assert scan.status == "PENDING"
    assert scan.task_id == "integration-task-001"
    assert scan.asset_id is not None


def test_network_scan_rejects_cross_tenant_target_and_invalid_ports(
    client, db_session, integration_admin, monkeypatch
):
    user, headers = integration_admin
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
    own_target = Target(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        name="Own tenant target",
        ip_address="192.0.2.92",
        is_authorized=True,
    )
    db_session.add_all([target, own_target])
    db_session.commit()

    enqueued = []
    monkeypatch.setattr(
        scans_endpoint,
        "_resolve_scan_ip",
        lambda target, guard: target.ip_address,
    )
    monkeypatch.setattr(
        scans_endpoint,
        "run_network_scan",
        SimpleNamespace(delay=lambda **kwargs: enqueued.append(kwargs)),
    )

    cross_tenant = client.post(
        "/api/v1/scans/network",
        json={"target_id": str(target.id), "ports": [80]},
        headers=headers,
    )
    assert cross_tenant.status_code == 404
    assert enqueued == []

    invalid_ports = client.post(
        "/api/v1/scans/network",
        json={"target_id": str(own_target.id), "ports": [0, 443]},
        headers=headers,
    )
    assert invalid_ports.status_code == 422
    assert enqueued == []

def test_network_scan_enqueue_failure_marks_persisted_scan_failed(
    client, db_session, integration_admin, monkeypatch
):
    user, headers = integration_admin
    target = Target(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        name="Network enqueue failure target",
        ip_address="192.0.2.93",
        is_authorized=True,
    )
    db_session.add(target)
    db_session.commit()

    def fail_delay(**kwargs):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(
        scans_endpoint,
        "_resolve_scan_ip",
        lambda target, guard: target.ip_address,
    )
    monkeypatch.setattr(
        scans_endpoint,
        "run_network_scan",
        SimpleNamespace(delay=fail_delay),
    )

    response = client.post(
        "/api/v1/scans/network",
        json={"target_id": str(target.id), "ports": [80, 443]},
        headers=headers,
    )

    assert response.status_code == 500, response.text
    failed_scans = (
        db_session.query(Scan)
        .filter(
            Scan.tenant_id == user.tenant_id,
            Scan.target_id == target.id,
            Scan.scan_type == "NETWORK",
        )
        .all()
    )
    assert len(failed_scans) == 1
    failed_scan = failed_scans[0]
    assert failed_scan.status == "FAILED"
    assert failed_scan.error_message == "broker unavailable"
    assert failed_scan.finished_at is not None
    assert failed_scan.task_id is None

@pytest.mark.parametrize(
    ("endpoint", "payload_factory", "task_name", "scan_type"),
    [
        (
            "/api/v1/scans/web",
            lambda target, asset: {"target_id": str(target.id)},
            "run_web_scan",
            "WEB",
        ),
        (
            "/api/v1/scans/cloud",
            lambda target, asset: {"target_id": str(target.id), "provider": "aws"},
            "run_cloud_scan",
            "CLOUD",
        ),
        (
            "/api/v1/scans/sast",
            lambda target, asset: {
                "asset_id": str(asset.id),
                "code_path": "/workspace/project",
            },
            "run_sast_scan",
            "SAST",
        ),
    ],
)
def test_non_network_scan_enqueue_failure_persists_failed_state(
    endpoint,
    payload_factory,
    task_name,
    scan_type,
    client,
    db_session,
    integration_admin,
    monkeypatch,
):
    user, headers = integration_admin
    target = Target(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        name=f"{scan_type} enqueue failure target",
        ip_address="192.0.2.94",
        domain="scan.example.test",
        is_authorized=True,
    )
    db_session.add(target)
    db_session.flush()

    asset = Asset(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        target_id=target.id,
        ip_address=target.ip_address,
    )
    db_session.add(asset)
    db_session.commit()

    monkeypatch.setattr(
        scans_endpoint,
        "_resolve_scan_ip",
        lambda target, guard: target.ip_address,
    )

    def fail_delay(*args, **kwargs):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(
        scans_endpoint,
        task_name,
        SimpleNamespace(delay=fail_delay),
    )

    response = client.post(
        endpoint,
        json=payload_factory(target, asset),
        headers=headers,
    )

    assert response.status_code == 500, response.text
    failed_scans = (
        db_session.query(Scan)
        .filter(
            Scan.tenant_id == user.tenant_id,
            Scan.target_id == target.id,
            Scan.scan_type == scan_type,
        )
        .all()
    )
    assert len(failed_scans) == 1
    failed_scan = failed_scans[0]
    assert failed_scan.status == "FAILED"
    assert failed_scan.error_message == "broker unavailable"
    assert failed_scan.finished_at is not None
    assert failed_scan.task_id is None

