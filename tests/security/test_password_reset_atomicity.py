import hashlib
import uuid
from datetime import datetime, timedelta

from backend.core.security import security_service
from backend.database.models.session import PasswordResetToken, UserSession
from backend.database.models.user import Organization, User


def test_password_reset_commits_password_token_and_session_revocation_atomically(
    client, db_session, monkeypatch
):
    organization = Organization(id=uuid.uuid4(), name="Reset Atomicity Org")
    user = User(
        id=uuid.uuid4(),
        tenant_id=organization.id,
        email="atomic-reset@example.test",
        hashed_password=security_service.get_password_hash("OldPassword123!"),
        role="admin",
        is_active=True,
    )
    raw_token = "single-use-reset-token"
    reset_entry = PasswordResetToken(
        id=uuid.uuid4(),
        tenant_id=organization.id,
        user_id=user.id,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=datetime.utcnow() + timedelta(hours=1),
        is_used=False,
    )
    session = UserSession(
        id=uuid.uuid4(),
        tenant_id=organization.id,
        user_id=user.id,
        refresh_token_hash=hashlib.sha256(b"active-refresh-token").hexdigest(),
        expires_at=datetime.utcnow() + timedelta(days=7),
        is_revoked=False,
    )
    db_session.add_all([organization, user, reset_entry, session])
    db_session.commit()

    commit_count = 0
    original_commit = db_session.commit

    def counted_commit():
        nonlocal commit_count
        commit_count += 1
        original_commit()

    monkeypatch.setattr(db_session, "commit", counted_commit)

    response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "NewPassword123!"},
    )

    assert response.status_code == 200
    assert commit_count == 1

    db_session.refresh(user)
    db_session.refresh(reset_entry)
    db_session.refresh(session)
    assert security_service.verify_password("NewPassword123!", user.hashed_password)
    assert reset_entry.is_used is True
    assert session.is_revoked is True
