"""Tenant-scoped scan queries."""

from uuid import UUID

from backend.database.models.scan import Scan
from backend.database.repositories.base_repo import BaseRepository


class ScanRepository(BaseRepository[Scan]):
    def __init__(self, db):
        super().__init__(db, Scan)

    def list_by_target(
        self,
        tenant_id: UUID,
        target_id: UUID,
        *,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Scan]:
        if not 1 <= limit <= self.MAX_PAGE_SIZE:
            raise ValueError(f"limit must be between 1 and {self.MAX_PAGE_SIZE}")
        if offset < 0:
            raise ValueError("offset must be non-negative")
        query = self.db.query(Scan).filter(
            Scan.tenant_id == tenant_id,
            Scan.target_id == target_id,
        )
        if status is not None:
            query = query.filter(Scan.status == status.strip().upper())
        return query.order_by(Scan.created_at.desc(), Scan.id).offset(offset).limit(limit).all()
