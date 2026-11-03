import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.database.models.webhook import Webhook
from backend.database.models.user import User
from backend.database.session import get_tenant_db
from backend.core.security import require_role, get_current_user
from backend.core.exceptions import KravigilException
from pydantic import BaseModel, HttpUrl

logger = logging.getLogger(__name__)
router = APIRouter()

class WebhookCreate(BaseModel):
    name: str
    url: str
    secret: str
    events: List[str]

class WebhookUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    secret: str | None = None
    events: List[str] | None = None
    is_active: bool | None = None

class WebhookResponse(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    events: List[str]
    is_active: bool

    class Config:
        from_attributes = True

@router.post("/", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
def create_webhook(
    webhook_in: WebhookCreate,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_tenant_db)
):
    try:
        webhook = Webhook(
            tenant_id=current_user.tenant_id,
            name=webhook_in.name,
            url=webhook_in.url,
            secret=webhook_in.secret,
            events=webhook_in.events,
            is_active=True
        )
        db.add(webhook)
        db.commit()
        db.refresh(webhook)
        return webhook
    except Exception as e:
        db.rollback()
        raise KravigilException(message=str(e), status_code=500, error_code="WEBHOOK_CREATE_ERROR")

@router.get("/", response_model=List[WebhookResponse])
def list_webhooks(
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_tenant_db)
):
    return db.query(Webhook).all()

@router.put("/{webhook_id}", response_model=WebhookResponse)
def update_webhook(
    webhook_id: uuid.UUID,
    webhook_in: WebhookUpdate,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_tenant_db)
):
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    if webhook_in.name is not None: webhook.name = webhook_in.name
    if webhook_in.url is not None: webhook.url = webhook_in.url
    if webhook_in.secret is not None: webhook.secret = webhook_in.secret
    if webhook_in.events is not None: webhook.events = webhook_in.events
    if webhook_in.is_active is not None: webhook.is_active = webhook_in.is_active
    db.commit()
    db.refresh(webhook)
    return webhook

@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook(
    webhook_id: uuid.UUID,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_tenant_db)
):
    webhook = db.query(Webhook).filter(Webhook.id == webhook_id).first()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")
    db.delete(webhook)
    db.commit()
