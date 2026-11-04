from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.schemas.asset import AssetCreate, AssetRead, AssetUpdate
from backend.schemas.evidence import EvidenceCreate, EvidenceRead
from backend.schemas.report import ReportCreate, ReportRead
from backend.schemas.user import UserCreate, UserRead, UserRoleUpdate


def test_asset_create_normalizes_ip_and_rejects_hostname() -> None:
    asset = AssetCreate(target_id=uuid4(), ip_address=" 2001:0db8::1 ")
    assert asset.ip_address == "2001:db8::1"
    with pytest.raises(ValidationError):
        AssetCreate(target_id=uuid4(), ip_address="scanner.example")


def test_asset_update_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AssetUpdate.model_validate({"tenant_id": str(uuid4())})


def test_asset_read_from_orm_shape() -> None:
    row = SimpleNamespace(
        id=uuid4(),
        target_id=uuid4(),
        ip_address="192.0.2.10",
        hostname=None,
        os_family="Linux",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    assert AssetRead.model_validate(row).is_active is True


def test_user_create_requires_valid_email_and_strong_password_length() -> None:
    user = UserCreate(email="analyst@example.com", password="long-enough-password", role="analyst")
    assert user.role == "analyst"
    with pytest.raises(ValidationError):
        UserCreate(email="not-an-email", password="short", role="root")


def test_user_role_update_is_allowlisted() -> None:
    assert UserRoleUpdate(role="viewer").role == "viewer"
    with pytest.raises(ValidationError):
        UserRoleUpdate(role="owner")


def test_user_read_never_accepts_secret_fields() -> None:
    row = SimpleNamespace(
        id=uuid4(),
        email="analyst@example.com",
        role="analyst",
        is_active=True,
        is_mfa_enabled=False,
        created_at=datetime.now(timezone.utc),
        hashed_password="never-return-this",
        mfa_secret="never-return-this-either",
    )
    response = UserRead.model_validate(row)
    assert "hashed_password" not in response.model_dump()
    assert "mfa_secret" not in response.model_dump()


def test_evidence_create_validates_digest_and_positive_size() -> None:
    digest = "a" * 64
    evidence = EvidenceCreate(
        scan_id=uuid4(),
        content_type="application/json",
        size_bytes=1024,
        sha256=digest.upper(),
    )
    assert evidence.sha256 == digest
    with pytest.raises(ValidationError):
        EvidenceCreate(
            scan_id=uuid4(),
            content_type="application/json",
            size_bytes=0,
            sha256="invalid",
        )


def test_evidence_read_omits_storage_locator_fields() -> None:
    row = SimpleNamespace(
        id=uuid4(),
        scan_id=uuid4(),
        finding_id=None,
        content_type="application/json",
        size_bytes=128,
        sha256="b" * 64,
        encryption="SSE-S3",
        retention_policy="standard",
        created_at=datetime.now(timezone.utc),
        object_key="private/tenant/path",
        object_version_id="private-version",
    )
    response = EvidenceRead.model_validate(row)
    assert "object_key" not in response.model_dump()
    assert "object_version_id" not in response.model_dump()


def test_report_create_and_read_contracts() -> None:
    scan_id = uuid4()
    request = ReportCreate(scan_id=scan_id)
    assert request.report_type == "PDF"
    with pytest.raises(ValidationError):
        ReportCreate(scan_id=scan_id, report_type="CSV")
    row = SimpleNamespace(
        id=uuid4(),
        scan_id=scan_id,
        report_type="PDF",
        status="READY",
        created_at=datetime.now(timezone.utc),
        completed_at=None,
        file_size_bytes=512,
        expires_at=None,
        object_key="private/report.pdf",
        error_message="internal detail",
    )
    response = ReportRead.model_validate(row)
    assert response.status == "READY"
    assert "object_key" not in response.model_dump()
    assert "error_message" not in response.model_dump()
