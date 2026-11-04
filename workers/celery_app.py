import logging
from celery import Celery
from celery.schedules import crontab
from backend.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

celery_app = Celery(
    "kravigil_workers",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["workers.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=7200,
    task_soft_time_limit=7000,
    worker_max_tasks_per_child=50,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
    result_expires=86400,
    beat_schedule={
        "reconcile-pending-evidence-deletions-every-five-minutes": {
            "task": "tasks.reconcile_pending_evidence_deletions",
            "schedule": crontab(minute="*/5"),
        },
        "check-scheduled-scans-every-minute": {
            "task": "tasks.check_scheduled_scans",
            "schedule": crontab(minute="*"),
        }
    }
)

celery_app.autodiscover_tasks(["workers"])
