
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.database.models.target import Target
from backend.database.models.asset import Asset
from backend.database.models.scan import Scan
from backend.database.models.user import User
from backend.database.session import get_tenant_db
from backend.core.security import get_current_user, require_role
from backend.core.exceptions import KravigilException, ScopeViolationException
from backend.security.scope_guard import ScopeGuard
from workers.tasks import run_network_scan, run_web_scan, run_sast_scan, run_cloud_scan
from pydantic import BaseModel, Field, validator
import uuid

router = APIRouter()

class NetworkScanCreate(BaseModel):
    target_id: uuid.UUID
    ports: List[int] = Field(default=[22, 80, 443, 8080], max_items=1000)

    @validator("ports")
    def validate_ports(cls, v):
        for port in v:
            if port < 1 or port > 65535:
                raise ValueError(f"Invalid port number: {port}")
        return list(set(v))

class WebScanCreate(BaseModel):
    target_id: uuid.UUID

class SASTScanCreate(BaseModel):
    asset_id: uuid.UUID
    code_path: str

class CloudScanCreate(BaseModel):
    asset_id: uuid.UUID
    provider: str = "aws"

class ScanResponse(BaseModel):
    id: uuid.UUID
    scan_type: str
    status: str

    class Config:
        from_attributes = True

def _init_scan(db: Session, tenant_id: uuid.UUID, target_id: uuid.UUID, scan_type: str) -> tuple[Scan, Asset]:
    target = db.query(Target).filter(Target.id == target_id).first()
    if not target: raise HTTPException(status_code=404, detail="Target not found")
    if not target.is_authorized: raise ScopeViolationException("Target is not authorized")

    guard = ScopeGuard()
    guard.validate_target(target.ip_address or target.domain)

    asset = db.query(Asset).filter(Asset.target_id == target.id).first()
    if not asset:
        asset = Asset(
            tenant_id=tenant_id,
            target_id=target.id,
            ip_address=target.ip_address or target.domain
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)

    scan = Scan(
        tenant_id=tenant_id,
        target_id=target.id,
        asset_id=asset.id,
        status="PENDING",
        scan_type=scan_type
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)
    return scan, asset

@router.post("/network", response_model=ScanResponse, status_code=status.HTTP_202_ACCEPTED)
def start_network_scan(
    scan_in: NetworkScanCreate,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_tenant_db)
):
    try:
        scan, asset = _init_scan(db, current_user.tenant_id, scan_in.target_id, "NETWORK")
        run_network_scan.delay(
            tenant_id=str(current_user.tenant_id),
            scan_id=str(scan.id),
            asset_id=str(asset.id),
            target_ip=asset.ip_address,
            ports=scan_in.ports
        )
        return scan
    except (HTTPException, ScopeViolationException):
        raise
    except Exception as e:
        db.rollback()
        raise KravigilException(message=f"Failed to initiate scan: {str(e)}", status_code=500, error_code="SCAN_INIT_ERROR")

@router.post("/web", response_model=ScanResponse, status_code=status.HTTP_202_ACCEPTED)
def start_web_scan(
    scan_in: WebScanCreate,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_tenant_db)
):
    try:
        scan, asset = _init_scan(db, current_user.tenant_id, scan_in.target_id, "WEB")
        target = db.query(Target).filter(Target.id == scan_in.target_id).first()
        target_url = target.domain or f"http://{target.ip_address}"
        
        run_web_scan.delay(
            tenant_id=str(current_user.tenant_id),
            scan_id=str(scan.id),
            asset_id=str(asset.id),
            target_url=target_url
        )
        return scan
    except (HTTPException, ScopeViolationException):
        raise
    except Exception as e:
        db.rollback()
        raise KravigilException(message=f"Failed to initiate web scan: {str(e)}", status_code=500, error_code="SCAN_INIT_ERROR")

@router.post("/sast", response_model=ScanResponse, status_code=status.HTTP_202_ACCEPTED)
def start_sast_scan(
    scan_in: SASTScanCreate,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_tenant_db)
):
    try:
        asset = db.query(Asset).filter(Asset.id == scan_in.asset_id).first()
        if not asset: raise HTTPException(status_code=404, detail="Asset not found")

        scan = Scan(
            tenant_id=current_user.tenant_id,
            target_id=asset.target_id,
            asset_id=asset.id,
            status="PENDING",
            scan_type="SAST"
        )
        db.add(scan)
        db.commit()
        db.refresh(scan)

        run_sast_scan.delay(
            tenant_id=str(current_user.tenant_id),
            scan_id=str(scan.id),
            asset_id=str(asset.id),
            code_path=scan_in.code_path
        )
        return scan
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise KravigilException(message=f"Failed to initiate SAST scan: {str(e)}", status_code=500, error_code="SCAN_INIT_ERROR")

@router.post("/cloud", response_model=ScanResponse, status_code=status.HTTP_202_ACCEPTED)
def start_cloud_scan(
    scan_in: CloudScanCreate,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_tenant_db)
):
    try:
        asset = db.query(Asset).filter(Asset.id == scan_in.asset_id).first()
        if not asset: raise HTTPException(status_code=404, detail="Asset not found")

        scan = Scan(
            tenant_id=current_user.tenant_id,
            target_id=asset.target_id,
            asset_id=asset.id,
            status="PENDING",
            scan_type="CLOUD"
        )
        db.add(scan)
        db.commit()
        db.refresh(scan)

        run_cloud_scan.delay(
            tenant_id=str(current_user.tenant_id),
            scan_id=str(scan.id),
            asset_id=str(asset.id),
            provider=scan_in.provider
        )
        return scan
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise KravigilException(message=f"Failed to initiate Cloud scan: {str(e)}", status_code=500, error_code="SCAN_INIT_ERROR")

@router.get("/", response_model=List[ScanResponse])
def list_scans(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db)
):
    return db.query(Scan).order_by(Scan.created_at.desc()).all()

@router.get("/{scan_id}", response_model=ScanResponse)
def get_scan_status(
    scan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db)
):
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan: raise HTTPException(status_code=404, detail="Scan not found")
    return scan
