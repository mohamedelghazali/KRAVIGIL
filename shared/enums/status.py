"""Canonical lifecycle values used by scans and findings."""

from enum import StrEnum


class ScanStatus(StrEnum):
    """Scan lifecycle states, accepting legacy uppercase database values."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @classmethod
    def _missing_(cls, value: object) -> "ScanStatus | None":
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
        return None


class ValidationStatus(StrEnum):
    """Finding validation states exposed by the frontend contract."""

    POTENTIAL = "potential"
    CONFIRMED = "confirmed"
    INCONCLUSIVE = "inconclusive"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"

    @classmethod
    def _missing_(cls, value: object) -> "ValidationStatus | None":
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
        return None


class FindingWorkflowStatus(StrEnum):
    """Finding workflow states currently persisted by the application."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"

    @classmethod
    def _missing_(cls, value: object) -> "FindingWorkflowStatus | None":
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
        return None
