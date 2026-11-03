from typing import Generator

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.core.security import get_current_user
from backend.database.models.user import User
from backend.database.session import SessionLocal


def get_tenant_db(
    current_user: User = Depends(get_current_user),
) -> Generator[Session, None, None]:
    """Yield a database session with the authenticated tenant set for RLS."""
    db = SessionLocal()
    try:
        if db.get_bind().dialect.name == "postgresql":
            db.execute(
                text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                {"tenant_id": str(current_user.tenant_id)},
            )
        yield db
    finally:
        db.close()
