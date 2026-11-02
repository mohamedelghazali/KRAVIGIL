import uuid
from typing import List
from fastapi import APIRouter, Depends, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, validator, IPvAnyAddress
from backend.database.models.target import Target
from backend.database.models.user import User
from backend.database.session import get_tenant_db
from backend.core.security import get_current_user, require_role
from backend.core.exceptions import KravigilException
from backend.core.audit_service import AuditService

router = APIRouter()

class TargetCreate(BaseModel):
    name: str
    ip_address: str | None = None
    domain: str | None = None
    is_authorized: bool = False

    @validator("name")
    def name_not_empty(cls, value):
        if not value.strip():
            raise ValueError("Name cannot be empty")
        return value.strip()

    @validator("ip_address")
    def validate_ip(cls, value):
        if value is not None:
            try:
                IPvAnyAddress(value)
            except ValueError:
                raise ValueError("Invalid IP address format")
        return value

class TargetResponse(BaseModel):
    id: uuid.UUID
    name: str
    ip_address: str | None
    domain: str | None
    is_authorized: bool

    class Config:
        from_attributes = True

@router.post("/", response_model=TargetResponse, status_code=status.HTTP_201_CREATED)
def create_target(request: Request, target_in: TargetCreate,
                  current_user: User = Depends(require_role(["admin", "analyst"])),
                  db: Session = Depends(get_tenant_db)):
    try:
        target = Target(
            tenant_id=current_user.tenant_id, name=target_in.name,
            ip_address=target_in.ip_address, domain=target_in.domain,
            is_authorized=target_in.is_authorized,
        )
        db.add(target)
        db.commit()
        db.refresh(target)
        AuditService.log_event(
            action="TARGET_CREATED", resource_type="target",
            resource_id=str(target.id), tenant_id=current_user.tenant_id,
            actor_id=current_user.id,
            source_ip=request.client.host if request.client else "unknown",
            details={"name": target_in.name, "ip": target_in.ip_address},
        )
        return target
    except Exception:
        db.rollback()
        raise KravigilException(message="Failed to create target",
                                 status_code=500, error_code="DB_ERROR")

@router.get("/", response_model=List[TargetResponse])
def list_targets(current_user: User = Depends(get_current_user),
                 db: Session = Depends(get_tenant_db)):
    try:
        return db.query(Target).all()
    except Exception:
        raise KravigilException(message="Failed to fetch targets",
                                 status_code=500, error_code="DB_ERROR")
