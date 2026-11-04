import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.main import app
from backend.database.session import get_db
from backend.database.tenant import get_tenant_db
from backend.database.models.base import Base
from backend.database.models.user import User, Organization
from backend.core.security import security_service
from backend.core import audit_service
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
def setup_db(monkeypatch):
    monkeypatch.setattr(audit_service, "SessionLocal", TestingSessionLocal)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = TestingSessionLocal()
    org_a = Organization(id=uuid.uuid4(), name="OrgA")
    org_b = Organization(id=uuid.uuid4(), name="OrgB")
    db.add(org_a)
    db.add(org_b)
    db.commit()

    user_a = User(
        id=uuid.uuid4(), 
        tenant_id=org_a.id, 
        email="a@test.com", 
        hashed_password=security_service.get_password_hash("Password123!"),
        role="admin"
    )
    user_b = User(
        id=uuid.uuid4(), 
        tenant_id=org_b.id, 
        email="b@test.com", 
        hashed_password=security_service.get_password_hash("Password123!"),
        role="admin"
    )
    db.add(user_a)
    db.add(user_b)
    db.commit()
    db.close()

def get_token(email):
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        return security_service.create_access_token(
            data={"sub": str(user.id), "tenant": str(user.tenant_id), "role": user.role}
        )
    finally:
        db.close()

def test_tenant_isolation():
    token_a = get_token("a@test.com")
    token_b = get_token("b@test.com")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    res_a = client.post("/api/v1/targets/", json={"name": "Target A", "ip_address": "1.1.1.1"}, headers=headers_a)
    assert res_a.status_code == 201
    
    res_b = client.post("/api/v1/targets/", json={"name": "Target B", "ip_address": "2.2.2.2"}, headers=headers_b)
    assert res_b.status_code == 201

    res_list_a = client.get("/api/v1/targets/", headers=headers_a)
    assert res_list_a.status_code == 200
    assert len(res_list_a.json()) == 1
    assert res_list_a.json()[0]["name"] == "Target A"
    
    res_list_b = client.get("/api/v1/targets/", headers=headers_b)
    assert res_list_b.status_code == 200
    assert len(res_list_b.json()) == 1
    assert res_list_b.json()[0]["name"] == "Target B"

    target_b_id = res_b.json()["id"]
    cross_tenant_get = client.get(f"/api/v1/targets/{target_b_id}", headers=headers_a)
    assert cross_tenant_get.status_code == 404

    cross_tenant_update = client.put(
        f"/api/v1/targets/{target_b_id}",
        json={"name": "Hijacked Target"},
        headers=headers_a,
    )
    assert cross_tenant_update.status_code == 404

    cross_tenant_delete = client.delete(
        f"/api/v1/targets/{target_b_id}", headers=headers_a
    )
    assert cross_tenant_delete.status_code == 404
