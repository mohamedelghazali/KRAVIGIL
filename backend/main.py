import logging
from datetime import datetime
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from backend.core.config import get_settings
from backend.core.logging import setup_logging
from backend.core.exceptions import KravigilException, kravigil_exception_handler, generic_exception_handler
from backend.api.v1.router import api_router
from backend.api.websockets.scans import scan_websocket_endpoint
from backend.database.session import engine
from backend.database.models.base import Base

setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None
)

app.add_exception_handler(KravigilException, kravigil_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(api_router, prefix="/api/v1")

@app.websocket("/ws/scans")
async def websocket_scans(websocket: WebSocket, token: str = None):
    await scan_websocket_endpoint(websocket, token)

@app.on_event("startup")
async def startup_event():
    logger.info("KRAVIGIL Core starting up")
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logger.critical(f"Database init failed: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("KRAVIGIL Core shutting down")

@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}
