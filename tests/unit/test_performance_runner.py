import pytest

from scripts.performance.run_api_load import percentile, validate_target


def test_percentile_uses_nearest_rank():
    assert percentile([10.0, 20.0, 30.0, 40.0], 50) == 20.0
    assert percentile([10.0, 20.0, 30.0, 40.0], 95) == 40.0


def test_percentile_returns_none_for_empty_samples():
    assert percentile([], 95) is None


def test_read_only_target_endpoint_requires_bearer_token():
    with pytest.raises(ValueError, match="KRAVIGIL_BEARER_TOKEN"):
        validate_target("https://staging.example", "/api/v1/targets/", None)


def test_non_allowlisted_or_mutating_path_is_rejected():
    with pytest.raises(ValueError, match="read-only allowlist"):
        validate_target("https://staging.example", "/api/v1/scans/network", "token")


def test_remote_http_target_is_rejected():
    with pytest.raises(ValueError, match="HTTPS"):
        validate_target("http://staging.example", "/api/v1/system/version", None)


def test_local_http_target_is_allowed():
    assert validate_target("http://127.0.0.1:8000", "/health", None) == "http://127.0.0.1:8000/health"


def test_base_url_with_path_is_rejected():
    with pytest.raises(ValueError, match="must not contain a path"):
        validate_target("https://staging.example/api", "/health", None)
