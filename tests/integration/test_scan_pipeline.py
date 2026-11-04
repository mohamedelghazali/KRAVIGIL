from types import SimpleNamespace
import uuid

from backend.database.models.scan import Scan
from backend.database.models.target import Target
from backend.database.models.user import User
import backend.api.v1.endpoints.scans as scans_endpoint


def test_network_scan_validates_ports_before_enqueue(
    client, auth_headers, db_session, monkeypatch
):
    user = db_session.query(User).filter(User.email == "admin@testorg.com").first()
    assert user is not None
    target = Target(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        name="Port validation target",
        ip_address="192.0.2.92",
        is_authorized=True,
    )
    db_session.add(target)
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

    response = client.post(
        "/api/v1/scans/network",
        json={"target_id": str(target.id), "ports": [0, 443]},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert enqueued == []
    assert db_session.query(Scan).filter(Scan.tenant_id == user.tenant_id).count() == 0
