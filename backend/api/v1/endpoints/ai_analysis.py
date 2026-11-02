import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.models.finding import Finding
from backend.database.models.user import User
from backend.database.session import get_tenant_db
from backend.core.security import require_role
from workers.tasks import analyze_finding_with_ai

router = APIRouter()

@router.post("/analyze/{finding_id}", status_code=202)
def trigger_ai_analysis(
    finding_id: uuid.UUID,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_tenant_db),
):
    tenant_id = getattr(current_user, "organization_id", None)
    if tenant_id is None:
        tenant_id = getattr(current_user, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=403, detail="Tenant context missing")
    finding = db.query(Finding).filter(
        Finding.id == finding_id,
        Finding.tenant_id == tenant_id,
    ).first()
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    analyze_finding_with_ai.delay(
        tenant_id=str(tenant_id),
        finding_id=str(finding.id),
    )
    return {"status": "queued", "finding_id": str(finding_id)}
