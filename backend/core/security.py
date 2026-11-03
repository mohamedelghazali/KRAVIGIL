import logging
import secrets
import hashlib
import pyotp
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.core.config import get_settings
from backend.database.session import get_db
from backend.database.models.user import User
from backend.database.models.api_key import APIKey
from backend.database.models.session import UserSession

logger = logging.getLogger(__name__)
settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

class SecurityService:
    def __init__(self):
        self.settings = settings
        self.algorithm = settings.ALGORITHM
        self.pwd_context = pwd_context

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        try:
            return self.pwd_context.verify(plain_password, hashed_password)
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False

    def get_password_hash(self, password: str) -> str:
        if len(password) < 12:
            raise ValueError("Password must be at least 12 characters")
        if not any(c.isupper() for c in password):
            raise ValueError("Password must contain an uppercase letter")
        if not any(c.islower() for c in password):
            raise ValueError("Password must contain a lowercase letter")
        if not any(c.isdigit() for c in password):
            raise ValueError("Password must contain a digit")
        return self.pwd_context.hash(password)

    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=self.settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "nbf": datetime.utcnow(),
            "iss": "kravigil-core",
            "aud": "kravigil-api",
            "type": "access"
        })
        return jwt.encode(to_encode, self.settings.SECRET_KEY, algorithm=self.algorithm)

    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=7)
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "iss": "kravigil-core",
            "aud": "kravigil-api",
            "type": "refresh"
        })
        return jwt.encode(to_encode, self.settings.SECRET_KEY, algorithm=self.algorithm)

    def decode_token(self, token: str, expected_type: str = "access") -> Dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                self.settings.SECRET_KEY,
                algorithms=[self.algorithm],
                audience="kravigil-api",
                issuer="kravigil-core"
            )
            if payload.get("type") != expected_type:
                raise HTTPException(status_code=401, detail="Invalid token type")
            return payload
        except JWTError as e:
            logger.warning(f"Invalid token: {e}")
            raise HTTPException(status_code=401, detail="Could not validate credentials")

    def generate_mfa_secret(self) -> str:
        return pyotp.random_base32()

    def verify_mfa_token(self, secret: str, token: str) -> bool:
        return pyotp.TOTP(secret).verify(token)

security_service = SecurityService()

def get_current_user(request: Request, token: Optional[str] = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    db.execute(text("SELECT set_config('app.auth_lookup', 'true', true)"))
    api_key_header = request.headers.get("X-API-Key")
    if api_key_header:
        key_hash = hashlib.sha256(api_key_header.encode()).hexdigest()
        api_key = db.query(APIKey).filter(APIKey.key_hash == key_hash, APIKey.is_active == True).first()
        
        if not api_key or (api_key.expires_at and api_key.expires_at < datetime.utcnow()):
            raise HTTPException(status_code=401, detail="Invalid or expired API Key")
            
        user = db.query(User).filter(User.tenant_id == api_key.tenant_id, User.is_active.is_(True)).first()
        if not user:
            raise HTTPException(status_code=401, detail="User associated with API Key not found")
        return user

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = security_service.decode_token(token, "access")
    if payload.get("mfa_required") is True:
        raise HTTPException(status_code=401, detail="MFA verification required")

    user_id = payload.get("sub")
    
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    tenant_claim = payload.get("tenant")
    if tenant_claim and str(user.tenant_id) != str(tenant_claim):
        raise HTTPException(status_code=401, detail="Token tenant does not match user tenant")
    return user

def require_role(required_roles: list[str]):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in required_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return role_checker
