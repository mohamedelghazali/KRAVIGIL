import uuid

import pytest

from backend.database.models.asset import Asset
from backend.database.models.finding import Finding
from backend.database.models.scan import Scan
from backend.database.models.target import Target
from backend.database.models.user import Organization, User
from backend.database.repositories import (
    AssetRepository,
    BaseRepository,
    FindingRepository,
    ScanRepository,
    UserRepository,
)


def _scope(db_session):
    tenant_id = uuid.uuid4()
    target_id = uuid.uuid4()
    organization = Organization(id=tenant_id, name=f"repo-{tenant_id}")
    target = Target(
        id=target_id,
        tenant_id=tenant_id,
        name="authorized test target",
        ip_address="192.0.2.44",
        is_authorized=True,
    )
    db_session.add_all([organization, target])
    db_session.flush()
    return tenant_id, target_id


def test_base_repository_requires_tenant_scoped_model(db_session):
    with pytest.raises(TypeError):
        BaseRepository(db_session, Organization)


def test_user_repository_never_returns_another_tenants_user(db_session):
    tenant_id, _ = _scope(db_session)
    other_tenant_id = uuid.uuid4()
    db_session.add(Organization(id=other_tenant_id, name=f"repo-{other_tenant_id}"))
    db_session.flush()

    user = UserRepository(db_session).create(
        tenant_id,
        {
            "email": f"analyst-{tenant_id}@example.test",
            "hashed_password": "not-a-real-password-hash",
            "role": "analyst",
        },
    )
    repository = UserRepository(db_session)
    assert repository.get(tenant_id, user.id) is user
    assert repository.get(other_tenant_id, user.id) is None
    assert repository.get_by_email(tenant_id, user.email) is user
    assert repository.get_by_email(other_tenant_id, user.email) is None


def test_base_repository_rejects_tenant_override_and_immutable_updates(db_session):
    tenant_id, target_id = _scope(db_session)
    repository = AssetRepository(db_session)
    asset = repository.create(tenant_id, {"target_id": target_id, "ip_address": "192.0.2.45"})

    with pytest.raises(ValueError):
        repository.create(
            tenant_id,
            {"tenant_id": uuid.uuid4(), "target_id": target_id, "ip_address": "192.0.2.46"},
        )
    with pytest.raises(ValueError):
        repository.update(tenant_id, asset.id, {"tenant_id": uuid.uuid4()})
    with pytest.raises(ValueError):
        repository.update(tenant_id, asset.id, {"id": uuid.uuid4()})
    assert repository.update(tenant_id, asset.id, {"hostname": "host.example.test"}).hostname == "host.example.test"


def test_asset_repository_is_tenant_scoped_and_paginates(db_session):
    tenant_id, target_id = _scope(db_session)
    other_tenant_id = uuid.uuid4()
    db_session.add(Organization(id=other_tenant_id, name=f"repo-{other_tenant_id}"))
    db_session.flush()
    db_session.add(
        Asset(tenant_id=other_tenant_id, target_id=target_id, ip_address="192.0.2.99")
    )
    repository = AssetRepository(db_session)
    repository.create(tenant_id, {"target_id": target_id, "ip_address": "192.0.2.46"})
    repository.create(tenant_id, {"target_id": target_id, "ip_address": "192.0.2.47"})

    assert len(repository.list_by_target(tenant_id, target_id, limit=1)) == 1
    assert len(repository.list_by_target(other_tenant_id, target_id)) == 1
    with pytest.raises(ValueError):
        repository.list(tenant_id, limit=501)
    with pytest.raises(ValueError):
        repository.list(tenant_id, offset=-1)


def test_finding_and_scan_repositories_apply_filters(db_session):
    tenant_id, target_id = _scope(db_session)
    asset = Asset(tenant_id=tenant_id, target_id=target_id, ip_address="192.0.2.48")
    db_session.add(asset)
    db_session.flush()
    finding = Finding(
        tenant_id=tenant_id,
        asset_id=asset.id,
        engine_id="nuclei",
        engine_version="3.4",
        title="Test finding",
        vulnerability_key=f"test:{uuid.uuid4()}",
        severity="high",
        confidence="confirmed",
        validation_status="confirmed",
        workflow_status="open",
    )
    scan = Scan(
        tenant_id=tenant_id,
        target_id=target_id,
        asset_id=asset.id,
        status="PENDING",
        scan_type="NETWORK",
    )
    db_session.add_all([finding, scan])
    db_session.flush()

    findings = FindingRepository(db_session).list_by_asset(
        tenant_id, asset.id, severity="HIGH", workflow_status="OPEN"
    )
    scans = ScanRepository(db_session).list_by_target(
        tenant_id, target_id, status="pending"
    )
    assert [item.id for item in findings] == [finding.id]
    assert [item.id for item in scans] == [scan.id]
