from typing import List
import uuid

from fastapi import APIRouter, Depends, Query, HTTPException, status, Request
from sqlalchemy.orm import Session
from backend.database.models.finding import Finding
from backend.database.models.user import User
from backend.database.tenant import get_tenant_db
from backend.core.security import get_current_user, require_permission
from backend.security.rbac import Permission
from backend.core.audit_service import AuditService
from backend.schemas.finding import FindingRead as FindingResponse
from backend.schemas.finding import FindingUpdate

router = APIRouter()

@router.get("/", response_model=List[FindingResponse])
def list_findings(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    severity: str = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db)
):
    query = db.query(Finding).filter(Finding.tenant_id == current_user.tenant_id)
    if severity:
        query = query.filter(Finding.severity == severity)
    return query.offset(skip).limit(limit).all()

@router.get("/{finding_id}", response_model=FindingResponse)
def get_finding(
    finding_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db)
):
    finding = db.query(Finding).filter(Finding.id == finding_id, Finding.tenant_id == current_user.tenant_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    return finding

@router.put("/{finding_id}", response_model=FindingResponse)
def update_finding(
    finding_id: uuid.UUID,
    finding_in: FindingUpdate,
    request: Request,
    current_user: User = Depends(require_permission(Permission.FINDING_UPDATE)),
    db: Session = Depends(get_tenant_db)
):
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    if finding_in.workflow_status is not None: finding.workflow_status = finding_in.workflow_status
    if finding_in.validation_status is not None: finding.validation_status = finding_in.validation_status
    if finding_in.disposition is not None: finding.disposition = finding_in.disposition
    if finding_in.remediation is not None: finding.remediation = finding_in.remediation

    db.commit()
    db.refresh(finding)

    AuditService.log_event(
        action="FINDING_UPDATED",
        resource_type="finding",
        resource_id=str(finding.id),
        tenant_id=current_user.tenant_id,
        actor_id=current_user.id,
        source_ip=request.client.host if request.client else "unknown",
        details=finding_in.model_dump(exclude_unset=True)
    )
    return finding

@router.delete("/{finding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_finding(
    finding_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permission(Permission.FINDING_DELETE)),
    db: Session = Depends(get_tenant_db)
):
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    db.delete(finding)
    db.commit()

    AuditService.log_event(
        action="FINDING_DELETED",
        resource_type="finding",
        resource_id=str(finding_id),
        tenant_id=current_user.tenant_id,
        actor_id=current_user.id,
        source_ip=request.client.host if request.client else "unknown"
    )
