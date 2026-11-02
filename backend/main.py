from fastapi import FastAPI
from backend.core.config import get_settings
from backend.api.v1.router import api_router
from backend.database.session import engine
from backend.database.models.base import Base

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION
)

app.include_router(api_router, prefix="/api/v1")

@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)

@app.get("/health")
def health():
    return {"status": "ok", "version": settings.APP_VERSION}
