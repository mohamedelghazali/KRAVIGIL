import pytest
from backend.core.exceptions import ScopeViolationException
from backend.security.scope_guard import ScopeGuard

def test_blocks_metadata_endpoint():
    with pytest.raises(ScopeViolationException):
        ScopeGuard().validate_target("http://169.254.169.254/latest/meta-data/")

def test_blocks_private_ip():
    with pytest.raises(ScopeViolationException):
        ScopeGuard().validate_target("http://192.168.1.1")

def test_blocks_loopback():
    with pytest.raises(ScopeViolationException):
        ScopeGuard().validate_target("http://127.0.0.1")

def test_allows_public_ip(monkeypatch):
    guard = ScopeGuard()
    monkeypatch.setattr(guard, "_resolve", lambda host: ["1.1.1.1"])
    assert guard.validate_target("https://one.one.one.one") == ["1.1.1.1"]

def test_blocks_private_ipv6_link_local():
    with pytest.raises(ScopeViolationException):
        ScopeGuard().validate_target("http://[fe80::1]")

def test_explicit_allowed_cidr():
    guard = ScopeGuard(allowed_cidrs=["192.168.1.0/24"])
    assert guard.validate_ip_direct("192.168.1.50")

def test_rejects_non_http_scheme():
    with pytest.raises(ScopeViolationException):
        ScopeGuard().validate_target("file:///etc/passwd")
