"""Central role-based access control policy for KRAVIGIL.

The API currently persists one of three organization roles on each user. Keep
that vocabulary strict and make permission decisions deny-by-default.
"""
from enum import Enum
from types import MappingProxyType
from typing import AbstractSet, FrozenSet, Iterable


class Role(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class Permission(str, Enum):
    TARGET_READ = "targets:read"
    TARGET_WRITE = "targets:write"
    ASSET_READ = "assets:read"
    ASSET_WRITE = "assets:write"
    SCAN_READ = "scans:read"
    SCAN_CREATE = "scans:create"
    SCAN_CANCEL = "scans:cancel"
    SCAN_DELETE = "scans:delete"
    FINDING_READ = "findings:read"
    FINDING_UPDATE = "findings:update"
    FINDING_DELETE = "findings:delete"
    REPORT_READ = "reports:read"
    REPORT_CREATE = "reports:create"
    EVIDENCE_READ = "evidence:read"
    EVIDENCE_UPLOAD = "evidence:upload"
    EVIDENCE_DELETE = "evidence:delete"
    USER_READ = "users:read"
    USER_MANAGE = "users:manage"
    SETTINGS_MANAGE = "settings:manage"
    AUDIT_READ = "audit:read"
    THREAT_INTEL_READ = "threat-intel:read"


_READ_PERMISSIONS: FrozenSet[Permission] = frozenset(
    {
        Permission.TARGET_READ,
        Permission.ASSET_READ,
        Permission.SCAN_READ,
        Permission.FINDING_READ,
        Permission.REPORT_READ,
        Permission.EVIDENCE_READ,
        Permission.USER_READ,
        Permission.THREAT_INTEL_READ,
    }
)

_ANALYST_PERMISSIONS: FrozenSet[Permission] = frozenset(
    {
        Permission.TARGET_WRITE,
        Permission.ASSET_WRITE,
        Permission.SCAN_CREATE,
        Permission.SCAN_CANCEL,
        Permission.FINDING_UPDATE,
        Permission.REPORT_CREATE,
        Permission.EVIDENCE_UPLOAD,
    }
)

ROLE_PERMISSIONS = MappingProxyType(
    {
        Role.ADMIN: frozenset(Permission),
        Role.ANALYST: _READ_PERMISSIONS | _ANALYST_PERMISSIONS,
        Role.VIEWER: _READ_PERMISSIONS,
    }
)


def normalize_role(role: Role | str | None) -> Role | None:
    """Return a known role, or None for malformed/unknown values."""
    if isinstance(role, Role):
        return role
    if not isinstance(role, str):
        return None
    try:
        return Role(role.strip().lower())
    except ValueError:
        return None


def normalize_permission(permission: Permission | str | None) -> Permission | None:
    """Return a known permission, or None for malformed/unknown values."""
    if isinstance(permission, Permission):
        return permission
    if not isinstance(permission, str):
        return None
    try:
        return Permission(permission.strip().lower())
    except ValueError:
        return None


def has_permission(role: Role | str | None, permission: Permission | str) -> bool:
    """Check one permission; unknown roles and permissions are always denied."""
    normalized_role = normalize_role(role)
    normalized_permission = normalize_permission(permission)
    if normalized_role is None or normalized_permission is None:
        return False
    return normalized_permission in ROLE_PERMISSIONS[normalized_role]


def has_any_role(role: Role | str | None, allowed_roles: Iterable[Role | str]) -> bool:
    """Check an explicit role allow-list without granting unknown role values."""
    normalized_role = normalize_role(role)
    if normalized_role is None:
        return False
    allowed: AbstractSet[Role] = frozenset(
        candidate
        for item in allowed_roles
        if (candidate := normalize_role(item)) is not None
    )
    return normalized_role in allowed


def permissions_for(role: Role | str | None) -> FrozenSet[Permission]:
    """Return an immutable permission set; unknown roles receive no permissions."""
    normalized_role = normalize_role(role)
    if normalized_role is None:
        return frozenset()
    return ROLE_PERMISSIONS[normalized_role]
