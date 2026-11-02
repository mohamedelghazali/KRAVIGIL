from fastapi import APIRouter
from backend.api.v1.endpoints import auth, targets, assets, scans, findings, ai_analysis

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(targets.router, prefix="/targets", tags=["Targets"])
api_router.include_router(assets.router, prefix="/assets", tags=["Assets"])
api_router.include_router(scans.router, prefix="/scans", tags=["Scans"])
api_router.include_router(findings.router, prefix="/findings", tags=["Findings"])
api_router.include_router(ai_analysis.router, prefix="/ai", tags=["AI Analysis"])
