"""Tenant-scoped finding queries."""

from uuid import UUID

from backend.database.models.finding import Finding
from backend.database.repositories.base_repo import BaseRepository


class FindingRepository(BaseRepository[Finding]):
    def __init__(self, db):
        super().__init__(db, Finding)

    def list_by_asset(
        self,
        tenant_id: UUID,
        asset_id: UUID,
        *,
        severity: str | None = None,
        workflow_status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Finding]:
        if not 1 <= limit <= self.MAX_PAGE_SIZE:
            raise ValueError(f"limit must be between 1 and {self.MAX_PAGE_SIZE}")
        if offset < 0:
            raise ValueError("offset must be non-negative")
        query = self.db.query(Finding).filter(
            Finding.tenant_id == tenant_id,
            Finding.asset_id == asset_id,
        )
        if severity is not None:
            query = query.filter(Finding.severity == severity.strip().casefold())
        if workflow_status is not None:
            query = query.filter(
                Finding.workflow_status == workflow_status.strip().casefold()
            )
        return query.order_by(Finding.id).offset(offset).limit(limit).all()
