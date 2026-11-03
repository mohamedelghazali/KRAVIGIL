import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.security import security_service
from backend.database.models.base import Base
from backend.database.session import get_db
from backend.database.tenant import get_tenant_db
from backend.main import app

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_final.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_tenant_db] = override_get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_e2e_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_full_platform_lifecycle():
    # 1. Setup Tenant & Admin
    from backend.database.models.user import Organization, User

    db = TestingSessionLocal()
    org = Organization(id=uuid.uuid4(), name="E2E Final Org")
    db.add(org)
    db.commit()

    admin = User(
        id=uuid.uuid4(),
        tenant_id=org.id,
        email="final_admin@kravigil.local",
        hashed_password=security_service.get_password_hash("FinalPassword123!"),
        role="admin",
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.close()

    # 2. Login
    login_res = client.post(
        "/api/v1/auth/login",
        data={
            "username": "final_admin@kravigil.local",
            "password": "FinalPassword123!",
        },
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Create Target
    target_res = client.post(
        "/api/v1/targets/",
        json={
            "name": "Final Target",
            "ip_address": "93.184.216.34",  # example.com
            "is_authorized": True,
        },
        headers=headers,
    )
    assert target_res.status_code == 201
    target_id = target_res.json()["id"]

    # 4. Schedule a Scan (Celery Beat Mock)
    with patch("workers.tasks.check_scheduled_scans"):
        from backend.database.models.schedule import ScheduledScan

        db = TestingSessionLocal()
        schedule = ScheduledScan(
            tenant_id=org.id,
            target_id=target_id,
            name="Daily Scan",
            scan_type="NETWORK",
            cron_expression="0 2 * * *",
            parameters={"ports": [22, 80]},
            next_run=datetime.utcnow() - timedelta(minutes=1),
        )
        db.add(schedule)
        db.commit()

        # Trigger the beat task manually
        from workers.tasks import check_scheduled_scans

        with patch("workers.tasks.run_network_scan.delay") as mock_scan:
            check_scheduled_scans()
            assert mock_scan.called
        db.close()

    # 5. Start Cloud Scan
    with patch("workers.tasks.run_cloud_scan.delay") as mock_cloud:
        cloud_res = client.post(
            "/api/v1/scans/cloud",
            json={
                "target_id": target_id,
                "provider": "aws",
            },
            headers=headers,
        )
        assert cloud_res.status_code == 202
        assert mock_cloud.called

    # 6. Verify Audit Logs exist
    logs_res = client.get("/api/v1/audit-logs/", headers=headers)
    assert logs_res.status_code == 200
    logs = logs_res.json()
    actions = [log["action"] for log in logs]
    assert "LOGIN_SUCCESS" in actions
    assert "TARGET_CREATED" in actions
    assert "SCHEDULE_CREATED" in actions
