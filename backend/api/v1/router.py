from fastapi import APIRouter
from backend.api.v1.endpoints import auth, targets, assets, scans, findings, ai_analysis, evidence, reports, risk, agents, webhooks

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(targets.router, prefix="/targets", tags=["Targets"])
api_router.include_router(assets.router, prefix="/assets", tags=["Assets"])
api_router.include_router(scans.router, prefix="/scans", tags=["Scans"])
api_router.include_router(findings.router, prefix="/findings", tags=["Findings"])
api_router.include_router(ai_analysis.router, prefix="/ai", tags=["AI Analysis"])
api_router.include_router(evidence.router, prefix="/evidence", tags=["Evidence"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
api_router.include_router(risk.router, prefix="/risk", tags=["Risk Assessment"])
api_router.include_router(agents.router, prefix="/agents", tags=["Agents"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
