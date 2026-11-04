import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List
from backend.database.models.target import Target
from backend.database.models.scan import Scan
from backend.services.evidence.evidence_manager import EvidenceManager
from backend.database.models.user import User
from backend.database.tenant import get_tenant_db
from backend.core.security import get_current_user, require_role
from backend.core.exceptions import KravigilException
from backend.core.audit_service import AuditService
from pydantic import BaseModel, validator, IPvAnyAddress, root_validator
import re
import uuid

router = APIRouter()
logger = logging.getLogger(__name__)

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
            except ValueError as exc:
                raise ValueError("Invalid IP address format") from exc
        return v

    @validator("domain")
    def validate_domain(cls, v):
        if v is None:
            return v
        value = v.strip().rstrip(".")
        if not value or "://" in value or any(ch in value for ch in "/?#@"):
            raise ValueError("Domain must be a hostname without a URL path or scheme")
        try:
            ascii_name = value.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise ValueError("Invalid internationalized domain name") from exc
        labels = ascii_name.split(".")
        if len(ascii_name) > 253 or any(
            not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
            for label in labels
        ):
            raise ValueError("Invalid domain name")
        return ascii_name.lower()

    @root_validator(skip_on_failure=True)
    def require_target(cls, values):
        if not values.get("ip_address") and not values.get("domain"):
            raise ValueError("At least one of ip_address or domain is required")
        return values

class TargetUpdate(BaseModel):
    name: str | None = None
    ip_address: str | None = None
    domain: str | None = None
    is_authorized: bool | None = None

    @validator("ip_address")
    def validate_update_ip(cls, v):
        if v is not None:
            try:
                IPvAnyAddress(v)
            except ValueError as exc:
                raise ValueError("Invalid IP address format") from exc
        return v

    @validator("domain")
    def validate_update_domain(cls, v):
        if v is None:
            return v
        value = v.strip().rstrip(".")
        if not value or "://" in value or any(ch in value for ch in "/?#@"):
            raise ValueError("Domain must be a hostname without a URL path or scheme")
        try:
            ascii_name = value.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise ValueError("Invalid internationalized domain name") from exc
        labels = ascii_name.split(".")
        if len(ascii_name) > 253 or any(
            not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
            for label in labels
        ):
            raise ValueError("Invalid domain name")
        return ascii_name.lower()

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
    request: Request,
    target_in: TargetCreate,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_tenant_db)
):
    if target_in.is_authorized and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only administrators can authorize scan targets")
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
        
        AuditService.log_event(
            action="TARGET_CREATED",
            resource_type="target",
            resource_id=str(new_target.id),
            tenant_id=current_user.tenant_id,
            actor_id=current_user.id,
            source_ip=request.client.host if request.client else "unknown"
        )
        return new_target
    except Exception as e:
        db.rollback()
        raise KravigilException(message="Failed to create target", status_code=500, error_code="DB_ERROR")

@router.get("/", response_model=List[TargetResponse])
def list_targets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db)
):
    return db.query(Target).filter(Target.tenant_id == current_user.tenant_id).all()

@router.get("/{target_id}", response_model=TargetResponse)
def get_target(
    target_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db)
):
    target = db.query(Target).filter(Target.id == target_id, Target.tenant_id == current_user.tenant_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    return target

@router.put("/{target_id}", response_model=TargetResponse)
def update_target(
    target_id: uuid.UUID,
    target_in: TargetUpdate,
    request: Request,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_tenant_db)
):
    target = db.query(Target).filter(Target.id == target_id, Target.tenant_id == current_user.tenant_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    if target_in.is_authorized is True and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only administrators can authorize scan targets")

    address_changed = (
        (target_in.ip_address is not None and target_in.ip_address != target.ip_address)
        or (target_in.domain is not None and target_in.domain != target.domain)
    )
    if target_in.name is not None:
        target.name = target_in.name.strip()
    if target_in.ip_address is not None:
        target.ip_address = target_in.ip_address
    if target_in.domain is not None:
        target.domain = target_in.domain
    if address_changed:
        # Any destination change invalidates the previous authorization.
        target.is_authorized = False
    elif target_in.is_authorized is not None:
        target.is_authorized = target_in.is_authorized

    db.commit()
    db.refresh(target)

    AuditService.log_event(
        action="TARGET_UPDATED",
        resource_type="target",
        resource_id=str(target.id),
        tenant_id=current_user.tenant_id,
        actor_id=current_user.id,
        source_ip=request.client.host if request.client else "unknown"
    )
    return target

@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_target(
    target_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_tenant_db)
):
    target = db.query(Target).filter(Target.id == target_id, Target.tenant_id == current_user.tenant_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    scan_ids = [
        row[0]
        for row in db.query(Scan.id).filter(
            Scan.target_id == target.id,
            Scan.tenant_id == current_user.tenant_id,
        ).all()
    ]
    try:
        EvidenceManager.delete_for_scans(db, scan_ids, current_user.tenant_id)
        if scan_ids:
            db.query(Scan).filter(
                Scan.id.in_(scan_ids), Scan.tenant_id == current_user.tenant_id
            ).delete(synchronize_session=False)
        db.delete(target)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Target deletion blocked while cleaning evidence for %s", target_id)
        raise HTTPException(
            status_code=503,
            detail="Target deletion is pending because associated evidence could not be removed; retry the request",
        ) from exc

    AuditService.log_event(
        action="TARGET_DELETED",
        resource_type="target",
        resource_id=str(target_id),
        tenant_id=current_user.tenant_id,
        actor_id=current_user.id,
        source_ip=request.client.host if request.client else "unknown"
    )
