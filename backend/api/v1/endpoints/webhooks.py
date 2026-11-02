import uuid
import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from backend.database.models.webhook import Webhook
from backend.database.models.user import User
from backend.database.session import get_tenant_db
from backend.core.security import require_role
from backend.core.exceptions import KravigilException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

class WebhookCreate(BaseModel):
    name: str
    url: str
    secret: str
    events: List[str]

class WebhookResponse(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    events: List[str]
    is_active: bool

    class Config:
        from_attributes = True

@router.post("/", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
def create_webhook(webhook_in: WebhookCreate,
                   current_user: User = Depends(require_role(["admin"])),
                   db: Session = Depends(get_tenant_db)):
    try:
        webhook = Webhook(
            tenant_id=current_user.tenant_id, name=webhook_in.name,
            url=webhook_in.url, secret=webhook_in.secret,
            events=webhook_in.events, is_active=True
        )
        db.add(webhook)
        db.commit()
        db.refresh(webhook)
        return webhook
    except Exception as exc:
        db.rollback()
        raise KravigilException(message=str(exc), status_code=500,
                                 error_code="WEBHOOK_CREATE_ERROR")

@router.get("/", response_model=List[WebhookResponse])
def list_webhooks(current_user: User = Depends(require_role(["admin", "analyst"])),
                  db: Session = Depends(get_tenant_db)):
    return db.query(Webhook).all()
