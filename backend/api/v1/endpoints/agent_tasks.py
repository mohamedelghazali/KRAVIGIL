import uuid
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List
from backend.database.models.agent_task import AgentTask
from backend.database.models.agent import Agent
from backend.database.models.scan import Scan
from backend.database.models.observation import Observation
from backend.database.models.user import User
from backend.database.tenant import get_tenant_db
from backend.core.exceptions import KravigilException
from backend.services.normalization.normalizer import Normalizer
from backend.core.audit_service import AuditService
from pydantic import BaseModel
import json

logger = logging.getLogger(__name__)
router = APIRouter()

class TaskResponse(BaseModel):
    id: uuid.UUID
    scan_id: uuid.UUID
    command_type: str
    parameters: dict

    class Config:
        from_attributes = True

class TaskResultSubmit(BaseModel):
    status: str
    error_message: str | None = None
    observations: List[dict] = []

@router.get("/poll", response_model=List[TaskResponse])
def poll_tasks(
    request: Request,
    db: Session = Depends(get_tenant_db)
):
    cert_fingerprint = request.headers.get("X-Agent-Fingerprint")
    if not cert_fingerprint:
        raise HTTPException(status_code=401, detail="Agent fingerprint missing")

    agent = db.query(Agent).filter(
        Agent.certificate_fingerprint == cert_fingerprint,
        Agent.status != "REVOKED",
    ).first()
    if not agent:
        raise HTTPException(status_code=401, detail="Agent not found or revoked")

    tasks = db.query(AgentTask).filter(
        AgentTask.agent_id == agent.id,
        AgentTask.status == "PENDING"
    ).limit(5).all()

    for task in tasks:
        task.status = "DISPATCHED"
        task.dispatched_at = datetime.utcnow()

    db.commit()
    return tasks

@router.post("/{task_id}/submit", status_code=status.HTTP_200_OK)
def submit_task_result(
    task_id: uuid.UUID,
    result_in: TaskResultSubmit,
    request: Request,
    db: Session = Depends(get_tenant_db)
):
    cert_fingerprint = request.headers.get("X-Agent-Fingerprint")
    if not cert_fingerprint:
        raise HTTPException(status_code=401, detail="Agent fingerprint missing")

    agent = db.query(Agent).filter(
        Agent.certificate_fingerprint == cert_fingerprint,
        Agent.status != "REVOKED",
    ).first()
    if not agent:
        raise HTTPException(status_code=401, detail="Agent not found or revoked")

    task = db.query(AgentTask).filter(
        AgentTask.id == task_id,
        AgentTask.agent_id == agent.id,
        AgentTask.tenant_id == agent.tenant_id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "DISPATCHED":
        raise HTTPException(status_code=400, detail="Task is not in dispatched state")

    try:
        task.status = result_in.status
        task.error_message = result_in.error_message
        task.completed_at = datetime.utcnow()

        if result_in.status == "COMPLETED":
            for obs_data in result_in.observations:
                obs = Observation(
                    id=uuid.uuid4(),
                    tenant_id=task.tenant_id,
                    scan_id=task.scan_id,
                    asset_id=task.parameters.get("asset_id"),
                    engine_id="agent_network",
                    event_type=obs_data.get("event_type", "PORT_OPEN"),
                    raw_data=obs_data
                )
                db.add(obs)

            scan = db.query(Scan).filter(Scan.id == task.scan_id, Scan.tenant_id == task.tenant_id).first()
            if scan:
                scan.status = "COMPLETED"
                scan.finished_at = datetime.utcnow()

        db.commit()

        AuditService.log_event(
            action="AGENT_TASK_COMPLETED",
            resource_type="agent_task",
            resource_id=str(task.id),
            tenant_id=task.tenant_id,
            details={"status": result_in.status, "findings": len(result_in.observations)}
        )

        return {"status": "acknowledged"}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to process task result {task_id}: {e}")
        raise KravigilException(message=str(e), status_code=500, error_code="TASK_SUBMIT_ERROR")
