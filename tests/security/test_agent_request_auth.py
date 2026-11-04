import base64
import hashlib
import json
import time
import uuid
from datetime import datetime, timedelta

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from backend.database.models.agent import Agent
from backend.database.models.agent_task import AgentTask
from backend.database.models.scan import Scan
from backend.database.models.user import Organization


def _new_agent_identity():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    fingerprint = hashlib.sha256(public_key.encode("utf-8")).hexdigest()
    return private_key, public_key, fingerprint


def _signed_headers(private_key, fingerprint, method, path, body=b"", timestamp=None):
    issued_at = str(int(time.time()) if timestamp is None else timestamp)
    body_hash = hashlib.sha256(body).hexdigest()
    message = "\\n".join(
        (method.upper(), path, issued_at, body_hash)
    ).encode("utf-8")
    signature = private_key.sign(message, padding.PKCS1v15(), hashes.SHA256())
    return {
        "X-Agent-Fingerprint": fingerprint,
        "X-Agent-Timestamp": issued_at,
        "X-Agent-Signature": base64.urlsafe_b64encode(signature).decode("ascii").rstrip("="),
    }


def test_agent_endpoints_reject_fingerprint_without_private_key_proof(client, db_session):
    tenant_id = uuid.uuid4()
    _, public_key, fingerprint = _new_agent_identity()
    db_session.add(Organization(id=tenant_id, name=f"AgentAuth-{tenant_id}"))
    db_session.add(
        Agent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            name="Signed agent",
            certificate_fingerprint=fingerprint,
            public_key=public_key,
            status="ENROLLED",
        )
    )
    db_session.commit()

    response = client.get(
        "/api/v1/agent-tasks/poll",
        headers={"X-Agent-Fingerprint": fingerprint},
    )

    assert response.status_code == 401


def test_signed_agent_heartbeat_updates_only_authenticated_agent(client, db_session):
    tenant_id = uuid.uuid4()
    private_key, public_key, fingerprint = _new_agent_identity()
    agent = Agent(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="Signed heartbeat agent",
        certificate_fingerprint=fingerprint,
        public_key=public_key,
        status="ENROLLED",
        ip_address="192.0.2.10",
    )
    db_session.add_all(
        [Organization(id=tenant_id, name=f"HeartbeatOrg-{tenant_id}"), agent]
    )
    db_session.commit()

    payload = {"status": "ONLINE", "ip_address": "192.0.2.20"}
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = _signed_headers(
        private_key, fingerprint, "POST", "/api/v1/agents/heartbeat", body
    )
    headers["Content-Type"] = "application/json"
    response = client.post(
        "/api/v1/agents/heartbeat", content=body, headers=headers
    )

    assert response.status_code == 200, response.text
    db_session.refresh(agent)
    assert agent.status == "ONLINE"
    assert agent.ip_address == "192.0.2.20"
    assert agent.last_heartbeat is not None


def test_agent_signature_cannot_be_replayed_after_timestamp_window(client, db_session):
    tenant_id = uuid.uuid4()
    private_key, public_key, fingerprint = _new_agent_identity()
    db_session.add(Organization(id=tenant_id, name=f"ExpiredAgent-{tenant_id}"))
    db_session.add(
        Agent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            name="Expired signature agent",
            certificate_fingerprint=fingerprint,
            public_key=public_key,
            status="ENROLLED",
        )
    )
    db_session.commit()

    payload = {"status": "ONLINE", "ip_address": "192.0.2.30"}
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = _signed_headers(
        private_key,
        fingerprint,
        "POST",
        "/api/v1/agents/heartbeat",
        body,
        timestamp=int(time.time()) - 600,
    )
    headers["Content-Type"] = "application/json"
    response = client.post(
        "/api/v1/agents/heartbeat", content=body, headers=headers
    )

    assert response.status_code == 401


def test_authenticated_agent_cannot_submit_another_agents_task(client, db_session):
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    private_key, public_key, fingerprint = _new_agent_identity()
    _, owner_public_key, owner_fingerprint = _new_agent_identity()
    owner_agent = Agent(
        id=uuid.uuid4(),
        tenant_id=tenant_a,
        name="Task owner",
        certificate_fingerprint=owner_fingerprint,
        public_key=owner_public_key,
        status="ENROLLED",
    )
    other_agent = Agent(
        id=uuid.uuid4(),
        tenant_id=tenant_b,
        name="Different agent",
        certificate_fingerprint=fingerprint,
        public_key=public_key,
        status="ENROLLED",
    )
    scan = Scan(
        id=uuid.uuid4(),
        tenant_id=tenant_a,
        target_id=uuid.uuid4(),
        asset_id=uuid.uuid4(),
        status="RUNNING",
        scan_type="NETWORK",
    )
    task = AgentTask(
        id=uuid.uuid4(),
        tenant_id=tenant_a,
        agent_id=owner_agent.id,
        scan_id=scan.id,
        command_type="NETWORK_SCAN",
        parameters={},
        status="DISPATCHED",
    )
    db_session.add_all(
        [
            Organization(id=tenant_a, name=f"TaskOwnerOrg-{tenant_a}"),
            Organization(id=tenant_b, name=f"OtherAgentOrg-{tenant_b}"),
            owner_agent,
            other_agent,
            scan,
            task,
        ]
    )
    db_session.commit()

    path = f"/api/v1/agent-tasks/{task.id}/submit"
    payload = {"status": "COMPLETED", "observations": []}
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = _signed_headers(private_key, fingerprint, "POST", path, body)
    headers["Content-Type"] = "application/json"
    response = client.post(path, content=body, headers=headers)

    assert response.status_code == 404
    db_session.refresh(task)
    assert task.status == "DISPATCHED"
