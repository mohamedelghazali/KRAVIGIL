from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.database.session import get_db
from backend.core.config import get_settings
from backend.core.version import __version__, __build__, __codename__
from backend.services.evidence.minio_client import MinIOClient
import redis
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/health")
def system_health(db: Session = Depends(get_db)):
    settings = get_settings()
    status = {"app": "ok", "database": "ok", "redis": "ok", "minio": "ok"}

    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"DB health check failed: {e}")
        status["database"] = "error"

    try:
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        status["redis"] = "error"

    try:
        storage = MinIOClient()
        if not storage.client.bucket_exists(settings.MINIO_BUCKET):
            raise Exception("Bucket missing")
    except Exception as e:
        logger.error(f"MinIO health check failed: {e}")
        status["minio"] = "error"

    overall = "ok" if all(v == "ok" for v in status.values()) else "degraded"
    return {"status": overall, "components": status}

@router.get("/version")
def system_version():
    return {
        "version": __version__,
        "build": __build__,
        "codename": __codename__
    }
