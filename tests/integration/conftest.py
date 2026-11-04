import uuid

import pytest

from backend.core.security import security_service
from backend.database.models.user import Organization, User


@pytest.fixture
def integration_admin(db_session):
    tenant_id = uuid.uuid4()
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email=f"integration-admin-{tenant_id}@example.test",
        hashed_password="test-only-hash",
        role="admin",
        is_active=True,
    )
    db_session.add_all(
        [Organization(id=tenant_id, name=f"integration-{tenant_id}"), user]
    )
    db_session.commit()
    token = security_service.create_access_token(
        {"sub": str(user.id), "tenant": str(tenant_id)}
    )
    return user, {"Authorization": f"Bearer {token}"}
