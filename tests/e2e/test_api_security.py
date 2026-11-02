import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_api_rate_limiting():
    for _ in range(100):
        client.get("/health")

    response = client.get("/api/v1/auth/login")
    assert response.status_code == 429

def test_scope_guard_blocks_metadata():
    from backend.security.scope_guard import ScopeGuard
    from backend.core.exceptions import ScopeViolationException

    guard = ScopeGuard()
    with pytest.raises(ScopeViolationException):
        guard.validate_target("http://169.254.169.254/latest/meta-data/")

def test_rls_tenant_isolation(client, auth_headers):
    res = client.post("/api/v1/targets/", json={
        "name": "Isolated Target",
        "ip_address": "8.8.8.8"
    }, headers=auth_headers)
    assert res.status_code == 201

    res_unauth = client.get("/api/v1/targets/")
    assert res_unauth.status_code == 401
