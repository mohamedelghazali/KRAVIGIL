import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.core.audit_service import AuditService
from backend.core.security import get_current_user, require_role
from backend.database.models.asset import Asset
from backend.database.models.target import Target
from backend.database.models.user import User
from backend.database.tenant import get_tenant_db
from backend.schemas.asset import AssetCreate, AssetRead as AssetResponse, AssetUpdate

router = APIRouter()

@router.post("/", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
def create_asset(
    asset_in: AssetCreate,
    request: Request,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_tenant_db)
):
    target = db.query(Target).filter(Target.id == asset_in.target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    asset = Asset(
        tenant_id=current_user.tenant_id,
        target_id=target.id,
        ip_address=asset_in.ip_address,
        hostname=asset_in.hostname,
        os_family=asset_in.os_family
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    AuditService.log_event(
        action="ASSET_CREATED",
        resource_type="asset",
        resource_id=str(asset.id),
        tenant_id=current_user.tenant_id,
        actor_id=current_user.id,
        source_ip=request.client.host if request.client else "unknown"
    )
    return asset

@router.get("/", response_model=List[AssetResponse])
def list_assets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db)
):
    return db.query(Asset).all()

@router.get("/{asset_id}", response_model=AssetResponse)
def get_asset(
    asset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db)
):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset

@router.put("/{asset_id}", response_model=AssetResponse)
def update_asset(
    asset_id: uuid.UUID,
    asset_in: AssetUpdate,
    request: Request,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_tenant_db)
):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    if asset_in.hostname is not None: asset.hostname = asset_in.hostname
    if asset_in.os_family is not None: asset.os_family = asset_in.os_family
    if asset_in.is_active is not None: asset.is_active = asset_in.is_active

    db.commit()
    db.refresh(asset)

    AuditService.log_event(
        action="ASSET_UPDATED",
        resource_type="asset",
        resource_id=str(asset.id),
        tenant_id=current_user.tenant_id,
        actor_id=current_user.id,
        source_ip=request.client.host if request.client else "unknown"
    )
    return asset

@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(
    asset_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_tenant_db)
):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    db.delete(asset)
    db.commit()

    AuditService.log_event(
        action="ASSET_DELETED",
        resource_type="asset",
        resource_id=str(asset_id),
        tenant_id=current_user.tenant_id,
        actor_id=current_user.id,
        source_ip=request.client.host if request.client else "unknown"
    )
