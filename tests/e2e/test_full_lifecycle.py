import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from backend.main import app
from backend.database.models.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.session import get_db, get_tenant_db
from backend.core.security import security_service
import uuid

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_e2e.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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

def test_full_lifecycle():
    # 1. Create Organization & Admin (Mocked via DB directly)
    from backend.database.models.user import Organization, User
    db = TestingSessionLocal()
    org = Organization(id=uuid.uuid4(), name="E2E Org")
    db.add(org)
    db.commit()

    admin = User(
        id=uuid.uuid4(),
        tenant_id=org.id,
        email="e2e_admin@kravigil.local",
        hashed_password=security_service.get_password_hash("E2EPassword123!"),
        role="admin",
        is_active=True
    )
    db.add(admin)
    db.commit()
    db.close()

    # 2. Login
    login_res = client.post("/api/v1/auth/login", data={
        "username": "e2e_admin@kravigil.local",
        "password": "E2EPassword123!"
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Create Target
    target_res = client.post("/api/v1/targets/", json={
        "name": "E2E Target",
        "ip_address": "93.184.216.34", # example.com
        "is_authorized": True
    }, headers=headers)
    assert target_res.status_code == 201
    target_id = target_res.json()["id"]

    # 4. Start Scan
    with patch("workers.tasks.run_network_scan.delay") as mock_scan:
        scan_res = client.post("/api/v1/scans/network", json={
            "target_id": target_id,
            "ports": [80, 443]
        }, headers=headers)
        assert scan_res.status_code == 202
        assert mock_scan.called
        scan_id = scan_res.json()["id"]

    # 5. Simulate Worker Completion
    from backend.database.models.scan import Scan
    from backend.database.models.observation import Observation
    from backend.database.models.finding import Finding

    db = TestingSessionLocal()
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    scan.status = "COMPLETED"
    db.commit()

    obs = Observation(
        id=uuid.uuid4(),
        tenant_id=org.id,
        scan_id=scan_id,
        asset_id=scan.asset_id,
        engine_id="network_cpp",
        event_type="PORT_OPEN",
        raw_data={"port": 80, "status": "OPEN"}
    )
    db.add(obs)
    db.commit()

    # 6. Simulate Correlation
    from backend.services.correlation.correlation_engine import CorrelationEngine
    engine = CorrelationEngine(db)
    finding_id = engine.process_observation(obs, "open_port_80", "HTTP")
    db.close()

    # 7. Verify Finding API
    findings_res = client.get("/api/v1/findings/", headers=headers)
    assert findings_res.status_code == 200
    assert len(findings_res.json()) == 1
    assert findings_res.json()[0]["vulnerability_key"] == "open_port_80"

    # 8. Request Report
    with patch("workers.tasks.generate_report.delay") as mock_report:
        report_res = client.post("/api/v1/reports/", json={"scan_id": scan_id}, headers=headers)
        assert report_res.status_code == 202
        assert mock_report.called

    # 9. Check Audit Logs
    from backend.database.models.audit import AuditLog
    db = TestingSessionLocal()
    audits = db.query(AuditLog).filter(AuditLog.tenant_id == org.id).all()
    assert len(audits) >= 2 # Should have LOGIN_SUCCESS and TARGET_CREATED
    db.close()
