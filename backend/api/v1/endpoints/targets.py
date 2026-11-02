from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.database.models.target import Target
from backend.database.models.user import User
from backend.database.session import get_tenant_db
from backend.core.security import get_current_user, require_role
from backend.core.exceptions import KravigilException
from pydantic import BaseModel, validator, IPvAnyAddress
import uuid

router = APIRouter()

class TargetCreate(BaseModel):
    name: str
    ip_address: str | None = None
    domain: str | None = None
    is_authorized: bool = False

    @validator("name")
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()

    @validator("ip_address")
    def validate_ip(cls, v):
        if v is not None:
            try:
                IPvAnyAddress(v)
            except ValueError:
                raise ValueError("Invalid IP address format")
        return v

class TargetResponse(BaseModel):
    id: uuid.UUID
    name: str
    ip_address: str | None
    domain: str | None
    is_authorized: bool

    class Config:
        from_attributes = True

@router.post("/", response_model=TargetResponse, status_code=status.HTTP_201_CREATED)
def create_target(
    target_in: TargetCreate,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_tenant_db)
):
    try:
        new_target = Target(
            tenant_id=current_user.tenant_id,
            name=target_in.name,
            ip_address=target_in.ip_address,
            domain=target_in.domain,
            is_authorized=target_in.is_authorized
        )
        db.add(new_target)
        db.commit()
        db.refresh(new_target)
        return new_target
    except Exception as e:
        db.rollback()
        raise KravigilException(message="Failed to create target", status_code=500, error_code="DB_ERROR")

@router.get("/", response_model=List[TargetResponse])
def list_targets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db)
):
    try:
        return db.query(Target).all()
    except Exception as e:
        raise KravigilException(message="Failed to fetch targets", status_code=500, error_code="DB_ERROR")
