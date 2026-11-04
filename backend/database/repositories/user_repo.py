"""Tenant-scoped user lookup and administration queries."""

from uuid import UUID

from backend.database.models.user import User
from backend.database.repositories.base_repo import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db):
        super().__init__(db, User)

    def get_by_email(self, tenant_id: UUID, email: str) -> User | None:
        normalized = email.strip().casefold()
        if not normalized:
            return None
        return (
            self.db.query(User)
            .filter(User.tenant_id == tenant_id, User.email == normalized)
            .first()
        )

    def list_active(self, tenant_id: UUID, *, limit: int = 100) -> list[User]:
        if not 1 <= limit <= self.MAX_PAGE_SIZE:
            raise ValueError(f"limit must be between 1 and {self.MAX_PAGE_SIZE}")
        return (
            self.db.query(User)
            .filter(User.tenant_id == tenant_id, User.is_active.is_(True))
            .order_by(User.email)
            .limit(limit)
            .all()
        )
