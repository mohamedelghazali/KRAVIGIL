from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from backend.database.models.finding import Finding
from backend.database.models.user import User
from backend.database.session import get_tenant_db
from backend.core.security import get_current_user
from pydantic import BaseModel
import uuid
from datetime import datetime

router = APIRouter()

class FindingResponse(BaseModel):
    id: uuid.UUID
    title: str
    vulnerability_key: str | None
    severity: str
    confidence: str
    validation_status: str
    first_seen: datetime
    last_seen: datetime

    class Config:
        from_attributes = True

@router.get("/", response_model=List[FindingResponse])
def list_findings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db)
):
    return db.query(Finding).all()
