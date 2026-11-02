import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from backend.database.models.audit import AuditLog
from backend.database.models.user import User
from backend.database.session import get_tenant_db
from backend.core.security import require_role
from pydantic import BaseModel

router = APIRouter()

class AuditLogResponse(BaseModel):
    id: uuid.UUID
    action: str
    resource_type: str
    resource_id: str | None
    actor_id: uuid.UUID | None
    timestamp: datetime
    details: dict

    class Config:
        from_attributes = True

@router.get("/", response_model=List[AuditLogResponse])
def list_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    action: Optional[str] = Query(None),
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_tenant_db)
):
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    
    return query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()
