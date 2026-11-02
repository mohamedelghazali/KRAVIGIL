from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.models.finding import Finding
from backend.database.models.observation import Observation
from backend.database.models.user import User
from backend.database.session import get_tenant_db
from backend.core.security import get_current_user
from ai.gateway.ai_gateway import AIGateway
import uuid

router = APIRouter()

@router.post("/analyze/{finding_id}")
async def analyze_finding(
    finding_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db)
):
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    observations = db.query(Observation).filter(
        Observation.id.in_([obs.id for obs in finding.observations])
    ).all()
    
    evidence_text = " ".join([str(obs.raw_data) for obs in observations])
    
    finding_data = {
        "title": finding.title,
        "severity": finding.severity,
        "engine": finding.engine_id,
        "cve": finding.cve_id
    }

    gateway = AIGateway()
    try:
        result = await gateway.process_finding_analysis(finding_data, evidence_text)
        
        if result["is_true_positive"] and result["confidence_score"] > 0.8:
            finding.confidence = "high"
        elif result["is_true_positive"]:
            finding.confidence = "medium"
        else:
            finding.confidence = "low"
            
        finding.remediation = result["remediation"]
        db.commit()
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
