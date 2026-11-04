import hashlib
import uuid
from datetime import datetime, timedelta

from backend.core.security import security_service
from backend.database.models.session import UserSession
from backend.core import audit_service
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



def test_refresh_token_cannot_use_another_tenants_session(client, db_session):
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    user_a = User(
        id=uuid.uuid4(),
        tenant_id=tenant_a,
        email=f"refresh-a-{tenant_a}@example.test",
        hashed_password="test-only-hash",
        role="admin",
        is_active=True,
    )
    user_b = User(
        id=uuid.uuid4(),
        tenant_id=tenant_b,
        email=f"refresh-b-{tenant_b}@example.test",
        hashed_password="test-only-hash",
        role="admin",
        is_active=True,
    )
    db_session.add_all(
        [
            Organization(id=tenant_a, name=f"RefreshOrgA-{tenant_a}"),
            Organization(id=tenant_b, name=f"RefreshOrgB-{tenant_b}"),
            user_a,
            user_b,
        ]
    )
    db_session.commit()

    refresh_token = security_service.create_refresh_token(
        {"sub": str(user_a.id), "tenant": str(tenant_a)}
    )
    mismatched_session = UserSession(
        id=uuid.uuid4(),
        tenant_id=tenant_b,
        user_id=user_b.id,
        refresh_token_hash=hashlib.sha256(refresh_token.encode()).hexdigest(),
        expires_at=datetime.utcnow() + timedelta(days=1),
        is_revoked=False,
    )
    db_session.add(mismatched_session)
    db_session.commit()
    original_last_used_at = mismatched_session.last_used_at

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 401
    db_session.refresh(mismatched_session)
    assert mismatched_session.last_used_at == original_last_used_at



def test_asset_and_finding_routes_are_tenant_scoped(client, db_session):
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    user_a = User(
        id=uuid.uuid4(),
        tenant_id=tenant_a,
        email=f"resource-a-{tenant_a}@example.test",
        hashed_password="test-only-hash",
        role="admin",
        is_active=True,
    )
    user_b = User(
        id=uuid.uuid4(),
        tenant_id=tenant_b,
        email=f"resource-b-{tenant_b}@example.test",
        hashed_password="test-only-hash",
        role="admin",
        is_active=True,
    )
    target_a = Target(
        id=uuid.uuid4(), tenant_id=tenant_a, name="Tenant A target",
        ip_address="1.1.1.1", is_authorized=True,
    )
    target_b = Target(
        id=uuid.uuid4(), tenant_id=tenant_b, name="Tenant B target",
        ip_address="8.8.8.8", is_authorized=True,
    )
    asset_a = Asset(
        id=uuid.uuid4(), tenant_id=tenant_a, target_id=target_a.id,
        ip_address="1.1.1.1",
    )
    asset_b = Asset(
        id=uuid.uuid4(), tenant_id=tenant_b, target_id=target_b.id,
        ip_address="8.8.8.8",
    )
    finding_a = Finding(
        id=uuid.uuid4(), tenant_id=tenant_a, asset_id=asset_a.id,
        engine_id="test", engine_version="1", title="Tenant A finding",
        vulnerability_key=f"tenant-a-{uuid.uuid4()}",
    )
    finding_b = Finding(
        id=uuid.uuid4(), tenant_id=tenant_b, asset_id=asset_b.id,
        engine_id="test", engine_version="1", title="Tenant B finding",
        vulnerability_key=f"tenant-b-{uuid.uuid4()}",
    )
    db_session.add_all([
        Organization(id=tenant_a, name=f"ResourceOrgA-{tenant_a}"),
        Organization(id=tenant_b, name=f"ResourceOrgB-{tenant_b}"),
        user_a, user_b, target_a, target_b, asset_a, asset_b, finding_a, finding_b,
    ])
    db_session.commit()

    token_a = security_service.create_access_token(
        {"sub": str(user_a.id), "tenant": str(tenant_a), "role": "admin"}
    )
    headers_a = {"Authorization": f"Bearer {token_a}"}

    assets = client.get("/api/v1/assets/", headers=headers_a)
    assert assets.status_code == 200
    assert {item["id"] for item in assets.json()} == {str(asset_a.id)}
    assert client.get(
        f"/api/v1/assets/{asset_b.id}", headers=headers_a
    ).status_code == 404

    findings = client.get("/api/v1/findings/", headers=headers_a)
    assert findings.status_code == 200
    assert {item["id"] for item in findings.json()} == {str(finding_a.id)}
    assert client.get(
        f"/api/v1/findings/{finding_b.id}", headers=headers_a
    ).status_code == 404


def test_agent_cannot_submit_another_agents_task(client, db_session):
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    target = Target(
        id=uuid.uuid4(), tenant_id=tenant_a, name="Agent task target",
        ip_address="1.1.1.1", is_authorized=True,
    )
    asset = Asset(
        id=uuid.uuid4(), tenant_id=tenant_a, target_id=target.id,
        ip_address="1.1.1.1",
    )
    scan = Scan(
        id=uuid.uuid4(), tenant_id=tenant_a, target_id=target.id,
        asset_id=asset.id, status="RUNNING", scan_type="NETWORK",
    )
    owner_agent = Agent(
        id=uuid.uuid4(), tenant_id=tenant_a, name="Owner agent",
        certificate_fingerprint="a" * 64, public_key="owner-key",
        status="ENROLLED",
    )
    other_agent = Agent(
        id=uuid.uuid4(), tenant_id=tenant_b, name="Other agent",
        certificate_fingerprint="b" * 64, public_key="other-key",
        status="ENROLLED",
    )
    task = AgentTask(
        id=uuid.uuid4(), tenant_id=tenant_a, agent_id=owner_agent.id,
        scan_id=scan.id, command_type="NETWORK_SCAN",
        parameters={"asset_id": str(asset.id)}, status="DISPATCHED",
    )
    db_session.add_all([
        Organization(id=tenant_a, name=f"AgentOrgA-{tenant_a}"),
        Organization(id=tenant_b, name=f"AgentOrgB-{tenant_b}"),
        target, asset, scan, owner_agent, other_agent, task,
    ])
    db_session.commit()

    response = client.post(
        f"/api/v1/agent-tasks/{task.id}/submit",
        headers={"X-Agent-Fingerprint": other_agent.certificate_fingerprint},
        json={"status": "COMPLETED", "observations": []},
    )

    assert response.status_code == 404
    db_session.refresh(task)
    assert task.status == "DISPATCHED"
