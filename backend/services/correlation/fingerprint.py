"""Stable finding fingerprint helpers shared by correlation and differential scans."""

import hashlib
import json
from uuid import UUID


def _normalize(value: object | None) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().casefold().split())


def finding_fingerprint(
    tenant_id: UUID | str,
    asset_id: UUID | str,
    service_id: str | None,
    vulnerability_key: str,
) -> str:
    """Return a deterministic, tenant-scoped SHA-256 fingerprint.

    JSON encoding avoids delimiter-collision ambiguity in concatenated values.
    """
    key = _normalize(vulnerability_key)
    if not key:
        raise ValueError("vulnerability_key must not be blank")
    canonical = [
        str(tenant_id),
        str(asset_id),
        _normalize(service_id),
        key,
    ]
    payload = json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
