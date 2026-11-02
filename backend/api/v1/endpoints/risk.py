import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.models.risk import RiskAssessment
from backend.database.models.user import User
from backend.database.session import get_tenant_db
from backend.core.security import get_current_user, require_role
from backend.services.risk.risk_engine import RiskEngine
from pydantic import BaseModel
from typing import List
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

class RiskAssessmentRequest(BaseModel):
    finding_id: uuid.UUID
    asset_criticality: str = "medium"
    exposure: str = "internal"

class RiskResponse(BaseModel):
    id: uuid.UUID
    finding_id: uuid.UUID
    calculated_risk_score: float
    risk_level: str
    cvss_score: float | None
    epss_score: float | None
    kev_status: bool
    created_at: datetime

    class Config:
        from_attributes = True

@router.post("/calculate", response_model=RiskResponse)
def calculate_risk(
    req: RiskAssessmentRequest,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_tenant_db)
):
    try:
        engine = RiskEngine(db)
        result = engine.calculate_risk(
            tenant_id=current_user.tenant_id,
            finding_id=req.finding_id,
            asset_criticality=req.asset_criticality,
            exposure=req.exposure
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Risk calculation failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/", response_model=List[RiskResponse])
def list_risks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db)
):
    return db.query(RiskAssessment).order_by(RiskAssessment.calculated_risk_score.desc()).all()
