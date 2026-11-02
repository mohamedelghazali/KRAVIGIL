from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from backend.database.session import get_db
from backend.database.models.user import User
from backend.core.security import security_service, get_settings
from backend.core.exceptions import KravigilException
from backend.core.audit_service import AuditService

router = APIRouter()
settings = get_settings()

@router.post("/login")
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(),
          db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    try:
        user = db.query(User).filter(User.email == form_data.username).first()
        if not user or not security_service.verify_password(form_data.password, user.hashed_password):
            AuditService.log_event(
                action="LOGIN_FAILED", resource_type="user",
                resource_id=form_data.username, source_ip=client_ip,
                user_agent=user_agent, status_code="401",
                details={"reason": "Invalid credentials"},
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Incorrect email or password",
                                headers={"WWW-Authenticate": "Bearer"})
        if not user.is_active:
            AuditService.log_event(
                action="LOGIN_FAILED", resource_type="user",
                resource_id=str(user.id), tenant_id=user.tenant_id,
                source_ip=client_ip, user_agent=user_agent, status_code="403",
                details={"reason": "Account disabled"},
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="User account is disabled")
        token = security_service.create_access_token(
            data={"sub": str(user.id), "tenant": str(user.tenant_id), "role": user.role},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        AuditService.log_event(
            action="LOGIN_SUCCESS", resource_type="user",
            resource_id=str(user.id), tenant_id=user.tenant_id,
            actor_id=user.id, source_ip=client_ip, user_agent=user_agent,
            status_code="200",
        )
        return {"access_token": token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as exc:
        raise KravigilException(message=str(exc), status_code=500, error_code="AUTH_ERROR")
