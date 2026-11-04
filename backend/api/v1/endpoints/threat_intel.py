from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from backend.database.models.threat_intel import ThreatIndicator
from backend.database.models.user import User
from backend.database.tenant import get_tenant_db
from backend.core.security import require_role
from pydantic import BaseModel
from datetime import datetime
import uuid
from workers.tasks import sync_threat_intel

router = APIRouter()

class IndicatorResponse(BaseModel):
    id: uuid.UUID
    indicator_type: str
    indicator_value: str
    threat_type: str
    source: str
    created_at: datetime

    class Config:
        from_attributes = True

@router.get("/", response_model=List[IndicatorResponse])
def list_indicators(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    ioc_type: str = Query(None),
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_tenant_db)
):
    query = db.query(ThreatIndicator).filter(ThreatIndicator.tenant_id == current_user.tenant_id)
    if ioc_type:
        query = query.filter(ThreatIndicator.indicator_type == ioc_type)
    return query.order_by(ThreatIndicator.created_at.desc()).offset(skip).limit(limit).all()

@router.post("/sync", status_code=202)
def trigger_sync(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role(["admin"])),
):
    background_tasks.add_task(sync_threat_intel.delay)
    return {"status": "sync_queued"}
