"""Deterministic normalization and merge rules for duplicate findings."""

from collections.abc import Iterable, Mapping
from typing import Any

_SEVERITY_RANK = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def canonical_vulnerability_key(value: str) -> str:
    """Normalize scanner keys so case/spacing differences do not create duplicates."""
    if not isinstance(value, str):
        raise TypeError("vulnerability key must be a string")
    normalized = " ".join(value.strip().casefold().split())
    if not normalized:
        raise ValueError("vulnerability key must not be blank")
    return normalized


def highest_severity(*values: str) -> str:
    """Return the most severe supported value; reject unknown values rather than downgrade."""
    if not values:
        raise ValueError("at least one severity is required")
    normalized = [value.strip().casefold() for value in values]
    unknown = [value for value in normalized if value not in _SEVERITY_RANK]
    if unknown:
        raise ValueError(f"unsupported severity value: {unknown[0]}")
    return max(normalized, key=_SEVERITY_RANK.__getitem__)


def merge_duplicate_findings(
    findings: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Merge payloads by canonical vulnerability key, preserving first-seen order."""
    merged: dict[str, dict[str, Any]] = {}
    for source in findings:
        item = dict(source)
        key = canonical_vulnerability_key(str(item.get("vulnerability_key", "")))
        existing = merged.get(key)
        if existing is None:
            item["vulnerability_key"] = key
            item["evidence_refs"] = list(dict.fromkeys(item.get("evidence_refs", [])))
            merged[key] = item
            continue
        existing["severity"] = highest_severity(
            str(existing.get("severity", "info")),
            str(item.get("severity", "info")),
        )
        refs = list(existing.get("evidence_refs", []))
        refs.extend(item.get("evidence_refs", []))
        existing["evidence_refs"] = list(dict.fromkeys(refs))
        if item.get("last_seen") and (
            not existing.get("last_seen") or item["last_seen"] > existing["last_seen"]
        ):
            existing["last_seen"] = item["last_seen"]
    return list(merged.values())
