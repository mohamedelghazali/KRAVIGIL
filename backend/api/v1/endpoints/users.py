import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.database.models.user import User
from backend.database.session import get_tenant_db
from backend.core.security import require_role, security_service
from backend.core.exceptions import KravigilException
from backend.core.audit_service import AuditService
from pydantic import BaseModel, EmailStr, validator

logger = logging.getLogger(__name__)
router = APIRouter()

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str = "analyst"

    @validator("role")
    def validate_role(cls, v):
        if v not in ["admin", "analyst", "viewer"]:
            raise ValueError("Role must be admin, analyst, or viewer")
        return v

class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True

class UserUpdateRole(BaseModel):
    role: str

    @validator("role")
    def validate_role(cls, v):
        if v not in ["admin", "analyst", "viewer"]:
            raise ValueError("Role must be admin, analyst, or viewer")
        return v

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreate,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_tenant_db)
):
    try:
        existing = db.query(User).filter(User.email == user_in.email).first()
        if existing:
            raise HTTPException(status_code=409, detail="User with this email already exists")

        hashed_pw = security_service.get_password_hash(user_in.password)
        
        new_user = User(
            id=uuid.uuid4(),
            tenant_id=current_user.tenant_id,
            email=user_in.email,
            hashed_password=hashed_pw,
            role=user_in.role,
            is_active=True
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        AuditService.log_event(
            action="USER_CREATED",
            resource_type="user",
            resource_id=str(new_user.id),
            tenant_id=current_user.tenant_id,
            actor_id=current_user.id,
            details={"email": user_in.email, "role": user_in.role}
        )
        return new_user
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise KravigilException(message=str(e), status_code=500, error_code="USER_CREATE_ERROR")

@router.get("/", response_model=List[UserResponse])
def list_users(
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_tenant_db)
):
    return db.query(User).all()

@router.put("/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: uuid.UUID,
    role_in: UserUpdateRole,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_tenant_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = role_in.role
    db.commit()
    db.refresh(user)

    AuditService.log_event(
        action="USER_ROLE_UPDATED",
        resource_type="user",
        resource_id=str(user.id),
        tenant_id=current_user.tenant_id,
        actor_id=current_user.id,
        details={"new_role": role_in.role}
    )
    return user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_tenant_db)
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    db.commit()

    AuditService.log_event(
        action="USER_DEACTIVATED",
        resource_type="user",
        resource_id=str(user.id),
        tenant_id=current_user.tenant_id,
        actor_id=current_user.id
    )
