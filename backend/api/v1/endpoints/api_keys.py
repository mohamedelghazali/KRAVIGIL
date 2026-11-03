import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.database.models.api_key import APIKey
from backend.database.models.user import User
from backend.database.tenant import get_tenant_db
from backend.core.security import require_role
from backend.core.exceptions import KravigilException
from backend.core.audit_service import AuditService
from pydantic import BaseModel

router = APIRouter()

class APIKeyCreate(BaseModel):
    name: str
    expires_in_days: int = 365

class APIKeyCreateResponse(BaseModel):
    id: uuid.UUID
    name: str
    raw_key: str
    prefix: str

class APIKeyResponse(BaseModel):
    id: uuid.UUID
    name: str
    prefix: str
    is_active: bool
    created_at: datetime
    expires_at: datetime | None

    class Config:
        from_attributes = True

@router.post("/", response_model=APIKeyCreateResponse, status_code=status.HTTP_201_CREATED)
def create_api_key(
    key_in: APIKeyCreate,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_tenant_db)
):
    try:
        raw_key, prefix, key_hash = APIKey.generate_key()
        expires_at = datetime.utcnow() + timedelta(days=key_in.expires_in_days) if key_in.expires_in_days > 0 else None

        api_key = APIKey(
            tenant_id=current_user.tenant_id,
            created_by_user_id=current_user.id,
            name=key_in.name,
            prefix=prefix,
            key_hash=key_hash,
            expires_at=expires_at
        )
        db.add(api_key)
        db.commit()
        db.refresh(api_key)

        AuditService.log_event(
            action="API_KEY_CREATED",
            resource_type="api_key",
            resource_id=str(api_key.id),
            tenant_id=current_user.tenant_id,
            actor_id=current_user.id
        )

        return {
            "id": api_key.id,
            "name": api_key.name,
            "raw_key": raw_key,
            "prefix": prefix
        }
    except Exception as e:
        db.rollback()
        raise KravigilException(message=str(e), status_code=500, error_code="API_KEY_CREATE_ERROR")

@router.get("/", response_model=List[APIKeyResponse])
def list_api_keys(
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_tenant_db)
):
    return db.query(APIKey).filter(APIKey.tenant_id == current_user.tenant_id).all()

@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    key_id: uuid.UUID,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_tenant_db)
):
    api_key = db.query(APIKey).filter(
        APIKey.id == key_id,
        APIKey.tenant_id == current_user.tenant_id
    ).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="API Key not found")

    api_key.is_active = False
    db.commit()

    AuditService.log_event(
        action="API_KEY_REVOKED",
        resource_type="api_key",
        resource_id=str(key_id),
        tenant_id=current_user.tenant_id,
        actor_id=current_user.id
    )

@router.post("/{key_id}/rotate", response_model=APIKeyCreateResponse)
def rotate_api_key(
    key_id: uuid.UUID,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_tenant_db)
):
    old_key = db.query(APIKey).filter(
        APIKey.id == key_id,
        APIKey.tenant_id == current_user.tenant_id
    ).first()
    if not old_key:
        raise HTTPException(status_code=404, detail="API Key not found")
    if not old_key.is_active:
        raise HTTPException(status_code=400, detail="API Key is already inactive")

    raw_key, prefix, key_hash = APIKey.generate_key()
    new_key = APIKey(
        tenant_id=current_user.tenant_id,
        created_by_user_id=current_user.id,
        name=old_key.name,
        prefix=prefix,
        key_hash=key_hash,
        expires_at=old_key.expires_at
    )
    old_key.is_active = False
    db.add(new_key)
    try:
        db.commit()
        db.refresh(new_key)
    except Exception:
        db.rollback()
        raise

    AuditService.log_event(
        action="API_KEY_ROTATED",
        resource_type="api_key",
        resource_id=str(new_key.id),
        tenant_id=current_user.tenant_id,
        actor_id=current_user.id,
        details={"old_key_id": str(key_id)}
    )
    return {"id": new_key.id, "name": new_key.name, "raw_key": raw_key, "prefix": prefix}
