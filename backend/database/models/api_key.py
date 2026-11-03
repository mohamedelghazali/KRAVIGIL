import uuid
import hashlib
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Index
from sqlalchemy import Uuid
from backend.database.models.base import Base

class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    prefix = Column(String(10), nullable=False, index=True)
    key_hash = Column(String(64), nullable=False, unique=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime)

    def verify_key(self, raw_key: str) -> bool:
        hashed = hashlib.sha256(raw_key.encode()).hexdigest()
        return hashed == self.key_hash

    @staticmethod
    def generate_key() -> tuple[str, str, str]:
        import secrets
        import hashlib
        raw_key = f"kv_{secrets.token_urlsafe(32)}"
        prefix = raw_key[:8]
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        return raw_key, prefix, key_hash
