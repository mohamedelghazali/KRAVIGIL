"""Tenant-scoped asset queries."""

from uuid import UUID

from backend.database.models.asset import Asset
from backend.database.repositories.base_repo import BaseRepository


class AssetRepository(BaseRepository[Asset]):
    def __init__(self, db):
        super().__init__(db, Asset)

    def list_by_target(
        self,
        tenant_id: UUID,
        target_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Asset]:
        if not 1 <= limit <= self.MAX_PAGE_SIZE:
            raise ValueError(f"limit must be between 1 and {self.MAX_PAGE_SIZE}")
        if offset < 0:
            raise ValueError("offset must be non-negative")
        return (
            self.db.query(Asset)
            .filter(Asset.tenant_id == tenant_id, Asset.target_id == target_id)
            .order_by(Asset.id)
            .offset(offset)
            .limit(limit)
            .all()
        )
