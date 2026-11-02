import uuid
import logging
from typing import Generator
from sqlalchemy.orm import Session
from backend.database.models.finding import Finding

logger = logging.getLogger(__name__)

class DataExtractor:
    def __init__(self, db: Session):
        self.db = db

    def iterate_findings(self, tenant_id: uuid.UUID, scan_id: uuid.UUID,
                         batch_size: int = 200) -> Generator[Finding, None, None]:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        tenant_uuid, scan_uuid = uuid.UUID(str(tenant_id)), uuid.UUID(str(scan_id))
        last_id = None
        while True:
            query = self.db.query(Finding).filter(
                Finding.tenant_id == tenant_uuid,
                Finding.scan_id == scan_uuid
            )
            if last_id is not None:
                query = query.filter(Finding.id > last_id)
            batch = query.order_by(Finding.id).limit(batch_size).all()
            if not batch:
                break
            for finding in batch:
                yield finding
            last_id = batch[-1].id
