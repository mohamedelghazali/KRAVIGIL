import uuid
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.database.session import get_db
from backend.database.models.user import User
from backend.database.models.session import UserSession, PasswordResetToken
from backend.core.security import security_service, get_settings, get_current_user
from backend.core.exceptions import KravigilException
from backend.core.audit_service import AuditService
from backend.services.notifications.email_dispatcher import EmailDispatcher
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


def _set_auth_lookup(db: Session) -> None:
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT set_config('app.auth_lookup', 'true', true)"))


def _set_tenant_context(db: Session, tenant_id) -> None:
    if db.get_bind().dialect.name != "postgresql":
        return
    db.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, false)"),
        {"tenant_id": str(tenant_id)},
    )
    db.execute(text("SELECT set_config('app.auth_lookup', 'false', false)"))
    db.commit()

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class MFAVerifyRequest(BaseModel):
    mfa_token: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@router.post("/login", response_model=TokenResponse)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    _set_auth_lookup(db)
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not security_service.verify_password(form_data.password, user.hashed_password):
        AuditService.log_event("LOGIN_FAILED", "user", form_data.username, source_ip=client_ip, status_code="401")
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is disabled")
    _set_tenant_context(db, user.tenant_id)

    if user.is_mfa_enabled:
        temp_token = security_service.create_access_token(
            data={"sub": str(user.id), "mfa_required": True},
            expires_delta=timedelta(minutes=5)
        )
        return {"access_token": temp_token, "refresh_token": "", "token_type": "bearer"}

    access_token = security_service.create_access_token(
        data={"sub": str(user.id), "tenant": str(user.tenant_id), "role": user.role}
    )
    refresh_token = security_service.create_refresh_token(
        data={"sub": str(user.id), "tenant": str(user.tenant_id)}
    )
    
    session = UserSession(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        user_id=user.id,
        refresh_token_hash=hashlib.sha256(refresh_token.encode()).hexdigest(),
        ip_address=client_ip,
        user_agent=user_agent,
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    db.add(session)
    db.commit()

    AuditService.log_event("LOGIN_SUCCESS", "user", str(user.id), user.tenant_id, user.id, source_ip=client_ip)
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@router.post("/login/mfa", response_model=TokenResponse)
def login_mfa(request: Request, mfa_in: MFAVerifyRequest, db: Session = Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing temporary token")
        
    temp_token = auth_header.split(" ")[1]
    payload = security_service.decode_token(temp_token, "access")
    
    if not payload.get("mfa_required"):
        raise HTTPException(status_code=400, detail="MFA not required for this token")

    _set_auth_lookup(db)
    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user or not user.is_mfa_enabled:
        raise HTTPException(status_code=401, detail="Invalid MFA state")
    _set_tenant_context(db, user.tenant_id)

    if not security_service.verify_mfa_token(user.mfa_secret, mfa_in.mfa_token):
        raise HTTPException(status_code=401, detail="Invalid MFA token")

    access_token = security_service.create_access_token(
        data={"sub": str(user.id), "tenant": str(user.tenant_id), "role": user.role}
    )
    refresh_token = security_service.create_refresh_token(
        data={"sub": str(user.id), "tenant": str(user.tenant_id)}
    )
    
    session = UserSession(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        user_id=user.id,
        refresh_token_hash=hashlib.sha256(refresh_token.encode()).hexdigest(),
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent", "unknown"),
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    db.add(session)
    db.commit()

    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@router.post("/refresh", response_model=TokenResponse)
def refresh_token(request: Request, refresh_in: RefreshRequest, db: Session = Depends(get_db)):
    payload = security_service.decode_token(refresh_in.refresh_token, "refresh")
    
    try:
        token_user_id = uuid.UUID(str(payload.get("sub")))
        token_tenant_id = uuid.UUID(str(payload.get("tenant")))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=401, detail="Invalid refresh token claims")

    _set_auth_lookup(db)
    token_hash = hashlib.sha256(refresh_in.refresh_token.encode()).hexdigest()
    session = db.query(UserSession).filter(
        UserSession.refresh_token_hash == token_hash,
        UserSession.user_id == token_user_id,
        UserSession.tenant_id == token_tenant_id,
        UserSession.is_revoked.is_(False),
    ).first()

    if not session or session.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    _set_tenant_context(db, token_tenant_id)
    user = db.query(User).filter(
        User.id == token_user_id,
        User.tenant_id == token_tenant_id,
    ).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    session.last_used_at = datetime.utcnow()
    db.commit()

    access_token = security_service.create_access_token(
        data={"sub": str(user.id), "tenant": str(user.tenant_id), "role": user.role}
    )
    return {"access_token": access_token, "refresh_token": refresh_in.refresh_token, "token_type": "bearer"}

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, refresh_in: RefreshRequest, db: Session = Depends(get_db)):
    _set_auth_lookup(db)
    token_hash = hashlib.sha256(refresh_in.refresh_token.encode()).hexdigest()
    session = db.query(UserSession).filter(UserSession.refresh_token_hash == token_hash).first()
    
    if session:
        _set_tenant_context(db, session.tenant_id)
        session.is_revoked = True
        db.commit()
        
    AuditService.log_event("LOGOUT", "user", "unknown", source_ip=request.client.host if request.client else "unknown")

@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(req: ForgotPasswordRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    _set_auth_lookup(db)
    user = db.query(User).filter(User.email == req.email, User.is_active == True).first()
    if not user:
        return {"status": "accepted"}

    _set_tenant_context(db, user.tenant_id)
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    
    reset_token = PasswordResetToken(
        tenant_id=user.tenant_id,
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(hours=1)
    )
    db.add(reset_token)
    db.commit()

    if not settings.SMTP_HOST or not settings.SMTP_FROM_ADDRESS:
        logger.error("Password reset email is not configured; SMTP_HOST and SMTP_FROM_ADDRESS are required")
        db.delete(reset_token)
        db.commit()
        return {"status": "accepted"}

    reset_link = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={raw_token}"
    email_config = {
        "host": settings.SMTP_HOST,
        "port": settings.SMTP_PORT,
        "username": settings.SMTP_USERNAME,
        "password": settings.SMTP_PASSWORD,
        "from_address": settings.SMTP_FROM_ADDRESS,
        "use_tls": settings.SMTP_USE_TLS,
    }
    background_tasks.add_task(
        EmailDispatcher.send_alert,
        smtp_config=email_config,
        to_addresses=[user.email],
        event_type="PASSWORD_RESET",
        data={"link": reset_link}
    )
    
    return {"status": "accepted"}

@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    _set_auth_lookup(db)
    token_hash = hashlib.sha256(req.token.encode()).hexdigest()
    reset_entry = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.is_used == False,
        PasswordResetToken.expires_at > datetime.utcnow()
    ).first()

    if not reset_entry:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    _set_tenant_context(db, reset_entry.tenant_id)
    user = db.query(User).filter(User.id == reset_entry.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        user.hashed_password = security_service.get_password_hash(req.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    reset_entry.is_used = True
    db.query(UserSession).filter(
        UserSession.user_id == user.id,
        UserSession.tenant_id == user.tenant_id,
        UserSession.is_revoked.is_(False),
    ).update({"is_revoked": True}, synchronize_session=False)
    # Password change, one-time token consumption, and session revocation must
    # commit atomically; otherwise a failed second commit can leave live sessions.
    db.commit()

    return {"status": "success"}

@router.post("/change-password")
def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _set_tenant_context(db, current_user.tenant_id)
    db_user = db.query(User).filter(
        User.id == current_user.id,
        User.tenant_id == current_user.tenant_id,
    ).first()
    if db_user is None:
        raise HTTPException(status_code=401, detail="User not found")

    if not security_service.verify_password(req.current_password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    try:
        db_user.hashed_password = security_service.get_password_hash(req.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.tenant_id == current_user.tenant_id,
        UserSession.is_revoked.is_(False),
    ).update({"is_revoked": True}, synchronize_session=False)
    db.commit()

    AuditService.log_event(
        "PASSWORD_CHANGED", "user", str(current_user.id),
        current_user.tenant_id, current_user.id
    )
    return {"status": "success"}
