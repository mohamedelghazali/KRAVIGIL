import uuid

import pytest
from fastapi import HTTPException

from backend.core.security import _get_api_key_owner
from backend.database.models.api_key import APIKey
from backend.database.models.user import Organization, User


def _create_owner(db_session, *, role="analyst", active=True):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    db_session.add(Organization(id=tenant_id, name=f"tenant-{tenant_id}"))
    db_session.flush()
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email=f"{user_id}@example.test",
        hashed_password="not-used-in-this-test",
        role=role,
        is_active=active,
    )
    db_session.add(user)
    db_session.flush()
    return tenant_id, user


def _create_key(db_session, tenant_id, owner_id):
    key = APIKey(
        tenant_id=tenant_id,
        created_by_user_id=owner_id,
        name="test-key",
        prefix="kv_test",
        key_hash=uuid.uuid4().hex + uuid.uuid4().hex,
        is_active=True,
    )
    db_session.add(key)
    db_session.flush()
    return key


def test_api_key_resolves_to_its_creator_and_current_role(db_session):
    tenant_id, owner = _create_owner(db_session, role="analyst")
    key = _create_key(db_session, tenant_id, owner.id)

    resolved = _get_api_key_owner(db_session, key)

    assert resolved.id == owner.id
    assert resolved.role == "analyst"


def test_unowned_legacy_api_key_is_rejected(db_session):
    tenant_id, _ = _create_owner(db_session, role="admin")
    key = _create_key(db_session, tenant_id, None)

    with pytest.raises(HTTPException) as exc:
        _get_api_key_owner(db_session, key)

    assert exc.value.status_code == 401


def test_api_key_cannot_resolve_owner_from_another_tenant(db_session):
    tenant_id, _ = _create_owner(db_session, role="analyst")
    other_tenant_id, other_owner = _create_owner(db_session, role="admin")
    key = _create_key(db_session, tenant_id, other_owner.id)

    with pytest.raises(HTTPException) as exc:
        _get_api_key_owner(db_session, key)

    assert exc.value.status_code == 401
    assert other_tenant_id != tenant_id


def test_api_key_of_inactive_owner_is_rejected(db_session):
    tenant_id, owner = _create_owner(db_session, role="admin", active=False)
    key = _create_key(db_session, tenant_id, owner.id)

    with pytest.raises(HTTPException) as exc:
        _get_api_key_owner(db_session, key)

    assert exc.value.status_code == 401
