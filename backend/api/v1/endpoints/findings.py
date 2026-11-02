import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from backend.core.security import get_current_user
from backend.database.models.finding import Finding
from backend.database.models.user import User
from backend.database.session import get_tenant_db


router = APIRouter()


class FindingResponse(BaseModel):
    id: uuid.UUID
    title: str
    vulnerability_key: str
    severity: Optional[str] = None
    confidence: Optional[str] = None
    validation_status: Optional[str] = None
    first_seen: datetime
    last_seen: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("/", response_model=List[FindingResponse])
def list_findings(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    severity: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db),
):
    query = db.query(Finding).filter(
        Finding.tenant_id == current_user.organization_id
    )
    if severity:
        query = query.filter(Finding.severity == severity)

    return (
        query.order_by(Finding.last_seen.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
