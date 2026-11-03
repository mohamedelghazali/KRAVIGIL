import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from backend.database.models.setting import TenantSetting
from backend.database.models.user import User
from backend.database.tenant import get_tenant_db
from backend.core.security import require_role
from backend.core.exceptions import KravigilException
from backend.core.audit_service import AuditService
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

class SettingUpdate(BaseModel):
    key: str
    value: Dict[str, Any]

class SettingResponse(BaseModel):
    key: str
    value: Dict[str, Any]

    class Config:
        from_attributes = True

@router.get("/", response_model=List[SettingResponse])
def get_settings(
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_tenant_db)
):
    return db.query(TenantSetting).all()

@router.put("/", response_model=SettingResponse)
def update_setting(
    setting_in: SettingUpdate,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_tenant_db)
):
    try:
        setting = db.query(TenantSetting).filter(
            TenantSetting.tenant_id == current_user.tenant_id,
            TenantSetting.key == setting_in.key
        ).first()

        if setting:
            setting.value = setting_in.value
        else:
            setting = TenantSetting(
                tenant_id=current_user.tenant_id,
                key=setting_in.key,
                value=setting_in.value
            )
            db.add(setting)

        db.commit()
        db.refresh(setting)

        AuditService.log_event(
            action="SETTING_UPDATED",
            resource_type="setting",
            resource_id=setting.id,
            tenant_id=current_user.tenant_id,
            actor_id=current_user.id,
            details={"key": setting_in.key}
        )
        return setting
    except Exception as e:
        db.rollback()
        raise KravigilException(message=str(e), status_code=500, error_code="SETTING_UPDATE_ERROR")

@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_setting(
    key: str,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_tenant_db)
):
    setting = db.query(TenantSetting).filter(
        TenantSetting.tenant_id == current_user.tenant_id,
        TenantSetting.key == key
    ).first()

    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")

    db.delete(setting)
    db.commit()

    AuditService.log_event(
        action="SETTING_DELETED",
        resource_type="setting",
        resource_id=setting.id,
        tenant_id=current_user.tenant_id,
        actor_id=current_user.id,
        details={"key": key}
    )
