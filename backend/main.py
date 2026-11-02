"""FastAPI application entry point."""
from fastapi import FastAPI
from backend.api.v1.router import api_router
from backend.core.config import settings

app = FastAPI(title=settings.app_name)
app.include_router(api_router, prefix=settings.api_v1_prefix)

@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
