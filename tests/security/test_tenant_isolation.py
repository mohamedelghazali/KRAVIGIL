import uuid

from backend.core.security import security_service
from backend.core import audit_service
from backend.database.models.target import Target
from backend.database.models.user import Organization, User
from tests.conftest import TestingSessionLocal


def test_tenant_isolation(client, db_session, monkeypatch):
    monkeypatch.setattr(audit_service, "SessionLocal", TestingSessionLocal)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    user_a = User(
        id=uuid.uuid4(),
        tenant_id=tenant_a,
        email=f"tenant-a-{tenant_a}@example.test",
        hashed_password="test-only-hash",
        role="admin",
        is_active=True,
    )
    user_b = User(
        id=uuid.uuid4(),
        tenant_id=tenant_b,
        email=f"tenant-b-{tenant_b}@example.test",
        hashed_password="test-only-hash",
        role="admin",
        is_active=True,
    )
    db_session.add_all(
        [
            Organization(id=tenant_a, name=f"OrgA-{tenant_a}"),
            Organization(id=tenant_b, name=f"OrgB-{tenant_b}"),
            user_a,
            user_b,
        ]
    )
    db_session.commit()

    token_a = security_service.create_access_token(
        {"sub": str(user_a.id), "tenant": str(tenant_a), "role": "admin"}
    )
    token_b = security_service.create_access_token(
        {"sub": str(user_b.id), "tenant": str(tenant_b), "role": "admin"}
    )
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    response_a = client.post(
        "/api/v1/targets/",
        json={"name": "Target A", "ip_address": "1.1.1.1"},
        headers=headers_a,
    )
    assert response_a.status_code == 201, response_a.text

    response_b = client.post(
        "/api/v1/targets/",
        json={"name": "Target B", "ip_address": "2.2.2.2"},
        headers=headers_b,
    )
    assert response_b.status_code == 201, response_b.text

    list_a = client.get("/api/v1/targets/", headers=headers_a)
    assert list_a.status_code == 200
    assert [item["name"] for item in list_a.json()] == ["Target A"]

    list_b = client.get("/api/v1/targets/", headers=headers_b)
    assert list_b.status_code == 200
    assert [item["name"] for item in list_b.json()] == ["Target B"]

    target_b_id = response_b.json()["id"]
    cross_tenant_get = client.get(
        f"/api/v1/targets/{target_b_id}", headers=headers_a
    )
    assert cross_tenant_get.status_code == 404

    cross_tenant_update = client.put(
        f"/api/v1/targets/{target_b_id}",
        json={"name": "Hijacked Target"},
        headers=headers_a,
    )
    assert cross_tenant_update.status_code == 404

    cross_tenant_delete = client.delete(
        f"/api/v1/targets/{target_b_id}", headers=headers_a
    )
    assert cross_tenant_delete.status_code == 404
