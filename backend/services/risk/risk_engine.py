import uuid
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from backend.database.models.finding import Finding
from backend.database.models.risk import RiskAssessment
from backend.services.vulnerability_intelligence.nvd_client import VulnerabilityIntelligence

logger = logging.getLogger(__name__)

class RiskEngine:
    def __init__(self, db: Session):
        self.db = db
        self.intel = VulnerabilityIntelligence()

    def calculate_risk(self, tenant_id: uuid.UUID, finding_id: uuid.UUID, asset_criticality: str = "medium", exposure: str = "internal") -> RiskAssessment:
        finding = self.db.query(Finding).filter(
            Finding.id == finding_id,
            Finding.tenant_id == tenant_id
        ).first()
        
        if not finding:
            raise ValueError(f"Finding {finding_id} not found for tenant {tenant_id}")

        cvss = 0.0
        epss = 0.0
        kev = False

        if finding.cve_id:
            cve_details = self.intel.get_cve_details(finding.cve_id)
            if cve_details:
                cvss = cve_details.get("cvss_score", 0.0)
            
            epss = self.intel.get_epss_score(finding.cve_id)
            kev = self.intel.is_in_kev(finding.cve_id)
        else:
            cvss = self._heuristic_cvss(finding.severity)

        base_score = cvss * 10.0
        
        if kev:
            base_score += 20.0
        
        base_score += (epss * 30.0)
        
        criticality_weight = {"low": 1.0, "medium": 1.2, "high": 1.5, "critical": 2.0}
        exposure_weight = {"internal": 1.0, "partner": 1.2, "internet": 1.5}
        
        c_weight = criticality_weight.get(asset_criticality, 1.0)
        e_weight = exposure_weight.get(exposure, 1.0)
        
        final_score = base_score * c_weight * e_weight
        final_score = min(final_score, 100.0)

        if final_score >= 80.0:
            risk_level = "CRITICAL"
        elif final_score >= 60.0:
            risk_level = "HIGH"
        elif final_score >= 40.0:
            risk_level = "MEDIUM"
        elif final_score >= 20.0:
            risk_level = "LOW"
        else:
            risk_level = "INFO"

        existing = self.db.query(RiskAssessment).filter(
            RiskAssessment.tenant_id == tenant_id,
            RiskAssessment.finding_id == finding_id
        ).first()

        explanation = {
            "cvss_score": cvss,
            "epss_score": epss,
            "kev_status": kev,
            "asset_criticality": asset_criticality,
            "exposure": exposure,
            "criticality_weight": c_weight,
            "exposure_weight": e_weight,
            "formula": "(base_score * criticality_weight * exposure_weight) clamped to 100"
        }

        if existing:
            existing.cvss_score = cvss
            existing.epss_score = epss
            existing.kev_status = kev
            existing.asset_criticality = asset_criticality
            existing.exposure = exposure
            existing.calculated_risk_score = final_score
            existing.risk_level = risk_level
            existing.explanation = explanation
            existing.created_at = datetime.utcnow()
            self.db.commit()
            return existing

        assessment = RiskAssessment(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            finding_id=finding_id,
            cvss_score=cvss,
            epss_score=epss,
            kev_status=kev,
            asset_criticality=asset_criticality,
            exposure=exposure,
            calculated_risk_score=final_score,
            risk_level=risk_level,
            explanation=explanation
        )
        
        self.db.add(assessment)
        self.db.commit()
        self.db.refresh(assessment)
        
        logger.info(f"Risk calculated for finding {finding_id}: {risk_level} ({final_score:.2f})")
        return assessment

    def _heuristic_cvss(self, severity: str) -> float:
        mapping = {
            "CRITICAL": 9.5,
            "HIGH": 8.0,
            "MEDIUM": 5.5,
            "LOW": 2.5,
            "INFO": 0.0
        }
        return mapping.get(severity.upper(), 5.0)
