from types import SimpleNamespace

import pytest

from backend.api.v1.endpoints.scans import _resolve_scan_ip
from backend.core.exceptions import ScopeViolationException


class RecordingGuard:
    def __init__(self):
        self.targets = []

    def validate_target(self, target):
        self.targets.append(target)
        return ["203.0.113.10"]


def test_validates_both_ip_and_domain_when_both_are_configured():
    target = SimpleNamespace(ip_address="198.51.100.20", domain="scan.example.test")
    guard = RecordingGuard()

    resolved = _resolve_scan_ip(target, guard)

    assert resolved == "198.51.100.20"
    assert guard.targets == ["198.51.100.20", "scan.example.test"]


def test_validates_domain_when_no_ip_is_configured():
    target = SimpleNamespace(ip_address=None, domain="scan.example.test")
    guard = RecordingGuard()

    resolved = _resolve_scan_ip(target, guard)

    assert resolved == "203.0.113.10"
    assert guard.targets == ["scan.example.test"]


def test_rejects_target_without_destination():
    target = SimpleNamespace(ip_address=None, domain=None)
    with pytest.raises(ScopeViolationException):
        _resolve_scan_ip(target, RecordingGuard())


def test_rejects_invalid_configured_ip():
    target = SimpleNamespace(ip_address="not-an-ip", domain=None)
    with pytest.raises(ScopeViolationException):
        _resolve_scan_ip(target, RecordingGuard())
