import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from backend.core.config import get_settings
from backend.database.session import get_db
from backend.database.models.user import User

logger = logging.getLogger(__name__)
settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

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
            "aud": "kravigil-api"
        })
        try:
            return jwt.encode(to_encode, self.settings.SECRET_KEY, algorithm=self.algorithm)
        except Exception as e:
            logger.error(f"Token creation failed: {e}")
            raise HTTPException(status_code=500, detail="Token generation failed")

    def decode_token(self, token: str) -> Dict[str, Any]:
        try:
            return jwt.decode(
                token,
                self.settings.SECRET_KEY,
                algorithms=[self.algorithm],
                audience="kravigil-api",
                issuer="kravigil-core"
            )
        except JWTError as e:
            logger.warning(f"Invalid token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

security_service = SecurityService()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    payload = security_service.decode_token(token)
    user_id: str = payload.get("sub")
    tenant_id: str = payload.get("tenant")
    
    if not user_id or not tenant_id:
        raise HTTPException(status_code=401, detail="Invalid token claims")
    
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def require_role(required_roles: list[str]):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in required_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return role_checker
