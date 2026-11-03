import pytest

from backend.security.rbac import (
    Permission,
    Role,
    has_any_role,
    has_permission,
    permissions_for,
)


@pytest.mark.parametrize(
    ("role", "permission", "expected"),
    [
        ("admin", Permission.USER_MANAGE, True),
        ("analyst", Permission.SCAN_CREATE, True),
        ("analyst", Permission.SCAN_DELETE, False),
        ("viewer", Permission.FINDING_READ, True),
        ("viewer", Permission.FINDING_UPDATE, False),
        ("unknown", Permission.USER_MANAGE, False),
        (None, Permission.SCAN_CREATE, False),
        ("admin", "not-a-permission", False),
    ],
)
def test_permission_matrix_is_deny_by_default(role, permission, expected):
    assert has_permission(role, permission) is expected


def test_role_allow_list_rejects_unknown_role_and_ignores_unknown_candidates():
    assert has_any_role("admin", ["viewer", "admin"])
    assert not has_any_role("root", ["admin"])
    assert not has_any_role("viewer", ["root"])


def test_permission_sets_are_immutable_and_unknown_role_is_empty():
    assert Permission.USER_MANAGE in permissions_for(Role.ADMIN)
    assert permissions_for("not-a-role") == frozenset()
    with pytest.raises(AttributeError):
        permissions_for(Role.ADMIN).add(Permission.SCAN_CREATE)
