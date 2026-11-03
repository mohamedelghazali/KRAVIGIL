import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database.session import get_db
from backend.database.tenant import get_tenant_db
from backend.database.models.base import Base
from backend.core.security import security_service

engine = create_engine(
    "sqlite:///./test_kravigil.db",
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def provide_test_ai_credentials(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-api-key")


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_tenant_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    from backend.database.models.user import Organization, User

    session = TestingSessionLocal()
    organization = Organization(id=uuid.uuid4(), name="TestOrg")
    session.add(organization)
    session.commit()

    user = User(
        id=uuid.uuid4(),
        tenant_id=organization.id,
        email="admin@testorg.com",
        hashed_password=security_service.get_password_hash("TestPassword123!"),
        role="admin",
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.close()

    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "admin@testorg.com",
            "password": "TestPassword123!",
        },
    )
    access_token = response.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}
