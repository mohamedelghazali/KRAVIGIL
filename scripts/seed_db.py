import os
import sys
import logging
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.database.session import SessionLocal, engine
from backend.database.models.base import Base
from backend.database.models.user import Organization, User
from backend.core.security import security_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_database():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        org = db.query(Organization).filter(Organization.name == "Default Organization").first()
        if not org:
            org = Organization(id=uuid.uuid4(), name="Default Organization")
            db.add(org)
            db.commit()
            db.refresh(org)
            logger.info("Created Default Organization")
        else:
            logger.info("Default Organization already exists")

        db.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": str(org.id)})

        admin_email = os.getenv("ADMIN_EMAIL")
        admin_password = os.getenv("ADMIN_PASSWORD")
        if not admin_email or not admin_password:
            raise RuntimeError("ADMIN_EMAIL and ADMIN_PASSWORD must be configured before seeding")

        admin = db.query(User).filter(User.email == admin_email).first()
        if not admin:
            admin = User(
                id=uuid.uuid4(),
                tenant_id=org.id,
                email=admin_email,
                hashed_password=security_service.get_password_hash(admin_password),
                role="admin",
                is_active=True
            )
            db.add(admin)
            db.commit()
            logger.info("Created initial administrator account: %s", admin_email)
        else:
            logger.info(f"Admin User {admin_email} already exists")

    except Exception as e:
        db.rollback()
        logger.error(f"Seeding failed: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
