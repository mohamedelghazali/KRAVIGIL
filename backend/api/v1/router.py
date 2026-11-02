from fastapi import APIRouter
from backend.api.v1.endpoints import auth, targets, assets

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(targets.router, prefix="/targets", tags=["Targets"])
api_router.include_router(assets.router, prefix="/assets", tags=["Assets"])
