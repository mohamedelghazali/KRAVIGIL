import uuid
import logging
from typing import Generator

from sqlalchemy.orm import Session

from backend.database.models.finding import Finding
from backend.database.models.observation import Observation

logger = logging.getLogger(__name__)


class DataExtractor:
    def __init__(self, db: Session):
        self.db = db

    def iterate_findings(
        self,
        tenant_id: uuid.UUID,
        scan_id: uuid.UUID,
        batch_size: int = 200,
    ) -> Generator[Finding, None, None]:
        """Yield unique findings evidenced by this tenant's scan in bounded batches."""
        if not 1 <= batch_size <= 1000:
            raise ValueError("batch_size must be between 1 and 1000")
        tenant_uuid = uuid.UUID(str(tenant_id))
        scan_uuid = uuid.UUID(str(scan_id))
        last_id = None

        while True:
            query = (
                self.db.query(Finding)
                .join(Finding.observations)
                .filter(
                    Finding.tenant_id == tenant_uuid,
                    Observation.tenant_id == tenant_uuid,
                    Observation.scan_id == scan_uuid,
                )
                .distinct()
            )
            if last_id is not None:
                query = query.filter(Finding.id > last_id)
            batch = (
                query.order_by(Finding.id)
                .limit(batch_size)
                .all()
            )
            if not batch:
                break
            for finding in batch:
                yield finding
            last_id = batch[-1].id
