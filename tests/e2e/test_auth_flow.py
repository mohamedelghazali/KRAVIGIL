import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database.models.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.session import get_db
from backend.core.security import security_service
import uuid

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_auth.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_login_and_refresh():
    from backend.database.models.user import Organization, User
    db = TestingSessionLocal()
    org = Organization(id=uuid.uuid4(), name="Auth Org")
    db.add(org)
    user = User(
        id=uuid.uuid4(), tenant_id=org.id, email="auth@test.com",
        hashed_password=security_service.get_password_hash("AuthPassword123!"),
        role="admin", is_active=True
    )
    db.add(user)
    db.commit()
    db.close()

    res = client.post("/api/v1/auth/login", data={"username": "auth@test.com", "password": "AuthPassword123!"})
    assert res.status_code == 200
    tokens = res.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    refresh_res = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh_res.status_code == 200
    assert "access_token" in refresh_res.json()

def test_forgot_password_flow():
    from backend.database.models.user import Organization, User
    from backend.database.models.session import PasswordResetToken
    db = TestingSessionLocal()
    org = Organization(id=uuid.uuid4(), name="Reset Org")
    db.add(org)
    user = User(
        id=uuid.uuid4(), tenant_id=org.id, email="reset@test.com",
        hashed_password=security_service.get_password_hash("ResetPassword123!"),
        role="admin", is_active=True
    )
    db.add(user)
    db.commit()

    res = client.post("/api/v1/auth/forgot-password", json={"email": "reset@test.com"})
    assert res.status_code == 202

    token_entry = db.query(PasswordResetToken).first()
    assert token_entry is not None
    db.close()
