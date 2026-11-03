from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from backend.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=2,
    max_overflow=1,
    pool_recycle=1800,
    echo=settings.DEBUG
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def _reset_rls_context(db: Session) -> None:
    if db.get_bind().dialect.name != "postgresql":
        return
    try:
        db.rollback()
        db.execute(
            text("SELECT set_config('app.tenant_id', '', false), set_config('app.auth_lookup', 'false', false)")
        )
        db.commit()
    except Exception:
        db.rollback()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        _reset_rls_context(db)
        db.close()

