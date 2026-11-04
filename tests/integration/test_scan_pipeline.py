import uuid

from backend.database.models.target import Target
import backend.api.v1.endpoints.scans as scans_endpoint


def test_cloud_scan_rejects_unknown_provider_before_creating_scan(
    client, db_session, integration_admin, monkeypatch
):
    user, headers = integration_admin
    target = Target(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        name="Cloud provider validation target",
        ip_address="192.0.2.93",
        is_authorized=True,
    )
    db_session.add(target)
    db_session.commit()

    dispatched = []
    monkeypatch.setattr(
        scans_endpoint,
        "run_cloud_scan",
        type("FakeTask", (), {"delay": staticmethod(lambda *args: dispatched.append(args))}),
    )

    response = client.post(
        "/api/v1/scans/cloud",
        json={"target_id": str(target.id), "provider": "unsupported-cloud"},
        headers=headers,
    )
    assert response.status_code == 422
    assert dispatched == []
