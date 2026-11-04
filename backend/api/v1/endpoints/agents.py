import uuid
import logging
from datetime import datetime
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database.models.agent import Agent
from backend.database.models.user import User
from backend.database.tenant import get_tenant_db
from backend.database.session import get_db
from backend.security.agent_auth import get_authenticated_agent
from backend.core.security import require_role
from backend.core.exceptions import KravigilException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

class AgentEnrollRequest(BaseModel):
    name: str
    certificate_fingerprint: str
    public_key: str
    version: str
    ip_address: str

class AgentHeartbeatRequest(BaseModel):
    status: Literal["ONLINE", "DEGRADED"]
    ip_address: str

class AgentResponse(BaseModel):
    id: uuid.UUID
    name: str
    status: str
    last_heartbeat: datetime | None
    version: str | None

    class Config:
        from_attributes = True

@router.post("/enroll", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def enroll_agent(
    agent_in: AgentEnrollRequest,
    current_user: User = Depends(require_role(["admin"])),
    db: Session = Depends(get_tenant_db)
):
    try:
        existing = db.query(Agent).filter(Agent.certificate_fingerprint == agent_in.certificate_fingerprint).first()
        if existing:
            raise HTTPException(status_code=409, detail="Agent already enrolled")

        agent = Agent(
            tenant_id=current_user.tenant_id,
            name=agent_in.name,
            certificate_fingerprint=agent_in.certificate_fingerprint,
            public_key=agent_in.public_key,
            version=agent_in.version,
            ip_address=agent_in.ip_address,
            status="ENROLLED",
            last_heartbeat=datetime.utcnow()
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        return agent
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise KravigilException(message=str(e), status_code=500, error_code="AGENT_ENROLL_ERROR")

@router.post("/heartbeat")
def agent_heartbeat(
    heartbeat_in: AgentHeartbeatRequest,
    agent: Agent = Depends(get_authenticated_agent),
    db: Session = Depends(get_db),
):
    try:
        agent.last_heartbeat = datetime.utcnow()
        agent.status = heartbeat_in.status
        # The agent-reported address is informational; do not treat it as an
        # authenticated network identity.
        agent.ip_address = heartbeat_in.ip_address
        db.commit()
        return {"status": "acknowledged"}
    except Exception as exc:
        db.rollback()
        logger.exception("Agent heartbeat update failed")
        raise KravigilException(
            message="Agent heartbeat update failed",
            status_code=500,
            error_code="AGENT_HEARTBEAT_ERROR",
        ) from exc

@router.get("/", response_model=list[AgentResponse])
def list_agents(
    current_user: User = Depends(require_role(["admin", "analyst"])),
    db: Session = Depends(get_tenant_db)
):
    return db.query(Agent).filter(Agent.tenant_id == current_user.tenant_id).all()
