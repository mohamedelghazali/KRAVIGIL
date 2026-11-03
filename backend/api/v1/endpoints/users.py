import uuid
from datetime import datetime
import logging
import pyotp
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.database.models.user import User
from backend.database.models.session import UserSession
from backend.database.tenant import get_tenant_db
from backend.core.security import get_current_user, require_role, security_service
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
    is_mfa_enabled: bool

    class Config:
        from_attributes = True

class UserUpdateRole(BaseModel):
    role: str

class MFASetupResponse(BaseModel):
    secret: str
    provisioning_uri: str

class MFAEnableRequest(BaseModel):
    mfa_token: str

class SessionResponse(BaseModel):
    id: uuid.UUID
    ip_address: str | None
    user_agent: str | None
    created_at: datetime
    last_used_at: datetime

    class Config:
        from_attributes = True

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


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

@router.post("/me/mfa/setup", response_model=MFASetupResponse)
def setup_mfa(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db)
):
    if current_user.is_mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA is already enabled")

    secret = security_service.generate_mfa_secret()
    current_user.mfa_secret = secret
    db.commit()

    provisioning_uri = pyotp.TOTP(secret).provisioning_uri(
        name=current_user.email,
        issuer_name="KRAVIGIL"
    )
    return {"secret": secret, "provisioning_uri": provisioning_uri}

@router.post("/me/mfa/enable")
def enable_mfa(
    req: MFAEnableRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db)
):
    if not current_user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA setup not initiated")
        
    if not security_service.verify_mfa_token(current_user.mfa_secret, req.mfa_token):
        raise HTTPException(status_code=400, detail="Invalid MFA token")

    current_user.is_mfa_enabled = True
    db.commit()
    return {"status": "success"}

@router.get("/me/sessions", response_model=List[SessionResponse])
def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db)
):
    return db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.is_revoked == False,
        UserSession.expires_at > datetime.utcnow()
    ).all()

@router.delete("/me/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db)
):
    session = db.query(UserSession).filter(
        UserSession.id == session_id,
        UserSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session.is_revoked = True
    db.commit()
