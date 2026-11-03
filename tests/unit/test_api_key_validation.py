import pytest
from pydantic import ValidationError

from backend.api.v1.endpoints.api_keys import APIKeyCreate


def test_api_key_name_is_trimmed():
    assert APIKeyCreate(name="  automation  ").name == "automation"


@pytest.mark.parametrize("name", ["", "   "])
def test_api_key_rejects_blank_name(name):
    with pytest.raises(ValidationError):
        APIKeyCreate(name=name)


@pytest.mark.parametrize("days", [-1, 3651])
def test_api_key_rejects_invalid_expiry(days):
    with pytest.raises(ValidationError):
        APIKeyCreate(name="automation", expires_in_days=days)


def test_zero_expiry_is_explicit_non_expiring_value():
    assert APIKeyCreate(name="automation", expires_in_days=0).expires_in_days == 0
