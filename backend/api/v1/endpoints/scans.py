from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import text
from datetime import datetime
from sqlalchemy.orm import Session
from typing import List
from backend.database.models.target import Target
from backend.database.models.asset import Asset
from backend.database.models.scan import Scan
from backend.database.models.user import User
from backend.database.tenant import get_tenant_db
from backend.core.security import get_current_user, require_role
from backend.core.exceptions import KravigilException, ScopeViolationException
from backend.core.audit_service import AuditService
from backend.security.scope_guard import ScopeGuard
from backend.core.config import get_settings
import ipaddress
from workers.tasks import run_network_scan, run_web_scan, run_sast_scan, run_cloud_scan
from workers.celery_app import celery_app
from engines.network_cpp.grpc_client import NetworkEngineClient
import os
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
    target_id: uuid.UUID
    provider: str = "aws"

class ScanResponse(BaseModel):
    id: uuid.UUID
    scan_type: str
    status: str

    class Config:
        from_attributes = True

def _init_scan(db: Session, tenant_id: uuid.UUID, target_id: uuid.UUID, scan_type: str) -> tuple[Scan, Asset]:
    target = db.query(Target).filter(Target.id == target_id, Target.tenant_id == tenant_id).first()
    if not target: raise HTTPException(status_code=404, detail="Target not found")
    if not target.is_authorized: raise ScopeViolationException("Target is not authorized")

    guard = ScopeGuard(get_settings().ALLOWED_SCAN_CIDRS)
    resolved_addresses = guard.validate_target(target.ip_address or target.domain)
    try:
        scan_ip = str(ipaddress.ip_address(target.ip_address)) if target.ip_address else resolved_addresses[0]
    except ValueError as exc:
        raise ScopeViolationException("Target must resolve to a valid IP address") from exc

    asset = db.query(Asset).filter(Asset.target_id == target.id, Asset.tenant_id == tenant_id).first()
    if not asset:
        asset = Asset(
            tenant_id=tenant_id,
            target_id=target.id,
            ip_address=scan_ip
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
    elif asset.ip_address != scan_ip:
        asset.ip_address = scan_ip
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
        task = run_network_scan.delay(
            tenant_id=str(current_user.tenant_id),
            scan_id=str(scan.id),
            asset_id=str(asset.id),
            target_ip=asset.ip_address,
            ports=scan_in.ports
        )
        scan.task_id = task.id
        db.commit()
        return scan
    except (HTTPException, ScopeViolationException):
        raise
    except Exception as e:
        db.rollback()
        raise KravigilException(message=f"Failed to initiate scan: {str(e)}", status_code=500, error_code="SCAN_INIT_ERROR")

@router.post("/web", response_model=ScanResponse, status_code=status.HTTP_202_ACCEPTED)
def start_web_scan(scan_in: WebScanCreate, current_user: User = Depends(require_role(["admin", "analyst"])), db: Session = Depends(get_tenant_db)):
    scan = None
    try:
        scan, asset = _init_scan(db, current_user.tenant_id, scan_in.target_id, "WEB")
        target = db.query(Target).filter(Target.id == scan_in.target_id, Target.tenant_id == current_user.tenant_id).first()
        hostname = target.domain or asset.ip_address
        target_url = hostname if hostname.startswith(("http://", "https://")) else f"https://{hostname}"
        task = run_web_scan.delay(str(current_user.tenant_id), str(scan.id), str(asset.id), target_url)
        scan.task_id = task.id
        db.commit()
        return scan
    except (HTTPException, ScopeViolationException):
        raise
    except Exception as exc:
        db.rollback()
        if scan is not None:
            failed = db.query(Scan).filter(Scan.id == scan.id, Scan.tenant_id == current_user.tenant_id).first()
            if failed:
                failed.status = "FAILED"
                failed.error_message = str(exc)[:2048]
                failed.finished_at = datetime.utcnow()
                db.commit()
        raise KravigilException(message="Failed to initiate web scan", status_code=500, error_code="SCAN_INIT_ERROR")


@router.post("/cloud", response_model=ScanResponse, status_code=status.HTTP_202_ACCEPTED)
def start_cloud_scan(scan_in: CloudScanCreate, current_user: User = Depends(require_role(["admin", "analyst"])), db: Session = Depends(get_tenant_db)):
    provider = scan_in.provider.lower()
    if provider not in {"aws", "azure", "gcp"}:
        raise HTTPException(status_code=422, detail="Unsupported cloud provider")
    scan = None
    try:
        scan, asset = _init_scan(db, current_user.tenant_id, scan_in.target_id, "CLOUD")
        task = run_cloud_scan.delay(str(current_user.tenant_id), str(scan.id), str(asset.id), provider)
        scan.task_id = task.id
        db.commit()
        return scan
    except (HTTPException, ScopeViolationException):
        raise
    except Exception as exc:
        db.rollback()
        if scan is not None:
            failed = db.query(Scan).filter(Scan.id == scan.id, Scan.tenant_id == current_user.tenant_id).first()
            if failed:
                failed.status = "FAILED"
                failed.error_message = str(exc)[:2048]
                failed.finished_at = datetime.utcnow()
                db.commit()
        raise KravigilException(message="Failed to initiate cloud scan", status_code=500, error_code="SCAN_INIT_ERROR")

@router.post("/sast", response_model=ScanResponse, status_code=status.HTTP_202_ACCEPTED)
def start_sast_scan(scan_in: SASTScanCreate, current_user: User = Depends(require_role(["admin", "analyst"])), db: Session = Depends(get_tenant_db)):
    from pathlib import PurePosixPath
    requested_path = PurePosixPath(scan_in.code_path)
    if not requested_path.is_absolute() or not str(requested_path).startswith("/workspace/") or ".." in requested_path.parts:
        raise HTTPException(status_code=422, detail="SAST path must be inside /workspace")
    asset = db.query(Asset).filter(Asset.id == scan_in.asset_id, Asset.tenant_id == current_user.tenant_id).first()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    target = db.query(Target).filter(Target.id == asset.target_id, Target.tenant_id == current_user.tenant_id, Target.is_authorized.is_(True)).first()
    if target is None:
        raise ScopeViolationException("SAST asset must belong to an authorized target")
    scan = Scan(tenant_id=current_user.tenant_id, target_id=target.id, asset_id=asset.id, status="PENDING", scan_type="SAST")
    db.add(scan)
    db.commit()
    db.refresh(scan)
    try:
        task = run_sast_scan.delay(str(current_user.tenant_id), str(scan.id), str(asset.id), str(requested_path))
        scan.task_id = task.id
        db.commit()
        return scan
    except Exception as exc:
        db.rollback()
        failed = db.query(Scan).filter(Scan.id == scan.id, Scan.tenant_id == current_user.tenant_id).first()
        if failed:
            failed.status = "FAILED"
            failed.error_message = str(exc)[:2048]
            failed.finished_at = datetime.utcnow()
            db.commit()
        raise KravigilException(message="Failed to initiate SAST scan", status_code=500, error_code="SCAN_INIT_ERROR")

@router.post("/{scan_id}/cancel")
def cancel_scan(
    scan_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_tenant_db)
):
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    if scan.status not in ["PENDING", "RUNNING"]:
        raise HTTPException(status_code=400, detail="Scan cannot be cancelled in its current state")

    if scan.task_id:
        if scan.scan_type == "NETWORK":
            try:
                with NetworkEngineClient(host=os.getenv("KRAVIGIL_ENGINE_HOST", "network_engine")) as client:
                    if not client.cancel_scan(str(scan.id)):
                        celery_app.control.revoke(scan.task_id, terminate=False)
            except Exception:
                celery_app.control.revoke(scan.task_id, terminate=False)
        else:
            celery_app.control.revoke(scan.task_id, terminate=False)

    scan.status = "CANCELLED"
    scan.finished_at = datetime.utcnow()
    db.commit()

    AuditService.log_event(
        action="SCAN_CANCELLED",
        resource_type="scan",
        resource_id=str(scan.id),
        tenant_id=current_user.tenant_id,
        actor_id=current_user.id,
        source_ip=request.client.host if request.client else "unknown"
    )
    return {"status": "cancelled"}

@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scan(
    scan_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_tenant_db)
):
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    db.delete(scan)
    db.commit()

    AuditService.log_event(
        action="SCAN_DELETED",
        resource_type="scan",
        resource_id=str(scan_id),
        tenant_id=current_user.tenant_id,
        actor_id=current_user.id,
        source_ip=request.client.host if request.client else "unknown"
    )
