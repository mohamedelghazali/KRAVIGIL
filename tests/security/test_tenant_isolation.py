import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from backend.main import app
from backend.database.session import get_db
from backend.database.models.base import Base
from backend.database.models.user import User, Organization
from backend.core.security import get_password_hash, create_access_token
import uuid

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

def override_get_tenant_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_tenant_db] = override_get_tenant_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    org_a = Organization(id=uuid.uuid4(), name="OrgA")
    org_b = Organization(id=uuid.uuid4(), name="OrgB")
    db.add(org_a)
    db.add(org_b)
    db.commit()

    user_a = User(id=uuid.uuid4(), tenant_id=org_a.id, email="a@test.com", hashed_password=get_password_hash("pass"))
    user_b = User(id=uuid.uuid4(), tenant_id=org_b.id, email="b@test.com", hashed_password=get_password_hash("pass"))
    db.add(user_a)
    db.add(user_b)
    db.commit()
    db.close()

def get_token(email):
    res = client.post("/api/v1/auth/login", data={"username": email, "password": "pass"})
    return res.json()["access_token"]

def test_tenant_isolation():
    token_a = get_token("a@test.com")
    token_b = get_token("b@test.com")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    client.post("/api/v1/targets/", json={"name": "Target A", "ip_address": "1.1.1.1"}, headers=headers_a)
    client.post("/api/v1/targets/", json={"name": "Target B", "ip_address": "2.2.2.2"}, headers=headers_b)

    res_a = client.get("/api/v1/targets/", headers=headers_a)
    res_b = client.get("/api/v1/targets/", headers=headers_b)

    assert len(res_a.json()) == 1
    assert res_a.json()[0]["name"] == "Target A"

    assert len(res_b.json()) == 1
    assert res_b.json()[0]["name"] == "Target B"
