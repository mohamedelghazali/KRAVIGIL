import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.database.models.schedule import ScheduledScan
from backend.database.models.target import Target
from backend.database.models.user import User
from backend.database.tenant import get_tenant_db
from backend.core.security import require_role, get_current_user
from backend.core.exceptions import KravigilException
from backend.services.scheduler.cron_parser import CronParser
from backend.core.audit_service import AuditService
from pydantic import BaseModel
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

class ScheduleCreate(BaseModel):
    target_id: uuid.UUID
    name: str
    scan_type: str
    cron_expression: str
    parameters: dict

class ScheduleUpdate(BaseModel):
    name: str | None = None
    cron_expression: str | None = None
    parameters: dict | None = None
    is_active: bool | None = None

class ScheduleResponse(BaseModel):
    id: uuid.UUID
    target_id: uuid.UUID
    name: str
    scan_type: str
    cron_expression: str
    is_active: bool
    next_run: datetime

    class Config:
        from_attributes = True

@router.post("/", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(
    schedule_in: ScheduleCreate,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_tenant_db)
):
    try:
        target = db.query(Target).filter(Target.id == schedule_in.target_id, Target.tenant_id == current_user.tenant_id).first()
        if not target:
            raise HTTPException(status_code=404, detail="Target not found")
        next_run = CronParser.get_next_run(schedule_in.cron_expression)
        schedule = ScheduledScan(
            tenant_id=current_user.tenant_id,
            target_id=schedule_in.target_id,
            name=schedule_in.name,
            scan_type=schedule_in.scan_type,
            cron_expression=schedule_in.cron_expression,
            parameters=schedule_in.parameters,
            next_run=next_run
        )
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
        AuditService.log_event(
            action="SCHEDULE_CREATED",
            resource_type="schedule",
            resource_id=str(schedule.id),
            tenant_id=current_user.tenant_id,
            actor_id=current_user.id
        )
        return schedule
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise KravigilException(message=str(e), status_code=500, error_code="SCHEDULE_CREATE_ERROR")

@router.get("/", response_model=List[ScheduleResponse])
def list_schedules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_tenant_db)
):
    return db.query(ScheduledScan).filter(ScheduledScan.tenant_id == current_user.tenant_id).all()

@router.put("/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(
    schedule_id: uuid.UUID,
    schedule_in: ScheduleUpdate,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_tenant_db)
):
    schedule = db.query(ScheduledScan).filter(ScheduledScan.id == schedule_id, ScheduledScan.tenant_id == current_user.tenant_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    if schedule_in.name is not None:
        schedule.name = schedule_in.name
    if schedule_in.cron_expression is not None:
        schedule.cron_expression = schedule_in.cron_expression
        schedule.next_run = CronParser.get_next_run(schedule_in.cron_expression)
    if schedule_in.parameters is not None:
        schedule.parameters = schedule_in.parameters
    if schedule_in.is_active is not None:
        schedule.is_active = schedule_in.is_active
    db.commit()
    db.refresh(schedule)
    return schedule

@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: uuid.UUID,
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_tenant_db)
):
    schedule = db.query(ScheduledScan).filter(ScheduledScan.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(schedule)
    db.commit()
    AuditService.log_event(
        action="SCHEDULE_DELETED",
        resource_type="schedule",
        resource_id=str(schedule_id),
        tenant_id=current_user.tenant_id,
        actor_id=current_user.id
    )
