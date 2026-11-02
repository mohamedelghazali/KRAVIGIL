from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from backend.database.models.asset import Asset
from backend.database.models.user import User
from backend.database.session import get_tenant_db
from backend.core.security import get_current_user
from backend.core.exceptions import KravigilException
from pydantic import BaseModel
import uuid

router = APIRouter()

class AssetResponse(BaseModel):
    id: uuid.UUID
    ip_address: str
    hostname: str | None
    os_family: str | None
    is_active: bool

    class Config:
        from_attributes = True

@router.get("/", response_model=List[AssetResponse])
def list_assets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db)
):
    try:
        return db.query(Asset).all()
    except Exception as e:
        raise KravigilException(message="Failed to fetch assets", status_code=500, error_code="DB_ERROR")
