"""Validated API contracts for tenant-owned assets."""

import ipaddress
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AssetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_id: UUID
    ip_address: str
    hostname: str | None = Field(default=None, max_length=255)
    os_family: str | None = Field(default=None, max_length=100)

    @field_validator("ip_address")
    @classmethod
    def validate_ip_address(cls, value: str) -> str:
        try:
            return str(ipaddress.ip_address(value.strip()))
        except ValueError as exc:
            raise ValueError("ip_address must be a valid IPv4 or IPv6 address") from exc


class AssetUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hostname: str | None = Field(default=None, max_length=255)
    os_family: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    target_id: UUID
    ip_address: str
    hostname: str | None = None
    os_family: str | None = None
    is_active: bool
    created_at: datetime
