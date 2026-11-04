"""Canonical severity values shared by ingestion, API, and reporting."""

from enum import StrEnum


class Severity(StrEnum):
    """Normalized finding severity; values match the public frontend contract."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

    @classmethod
    def _missing_(cls, value: object) -> "Severity | None":
        """Accept scanner/database uppercase spellings without widening the enum."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            for member in cls:
                if member.value == normalized:
                    return member
        return None

    @property
    def engine_value(self) -> str:
        """Return the uppercase spelling used by scanner engines and CLI filters."""
        return self.value.upper()
