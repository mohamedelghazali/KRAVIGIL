import logging
from backend.database.session import SessionLocal
from backend.database.models.audit import AuditLog
from sqlalchemy import text

logger = logging.getLogger(__name__)

class AuditService:
    @staticmethod
    def log_event(action, resource_type, resource_id=None, tenant_id=None,
                  actor_id=None, actor_type="user", source_ip=None,
                  user_agent=None, status_code=None, details=None):
        session = SessionLocal()
        try:
            if tenant_id is not None and session.get_bind().dialect.name == "postgresql":
                session.execute(
                    text("SELECT set_config('app.tenant_id', :tenant_id, false)"),
                    {"tenant_id": str(tenant_id)},
                )
                session.commit()
            record = AuditLog(
                tenant_id=tenant_id,
                actor_id=actor_id,
                actor_type=actor_type,
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id else None,
                source_ip=source_ip,
                user_agent=user_agent,
                status_code=status_code,
                details=details or {},
            )
            session.add(record)
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.error("Audit event persistence failed: %s", exc, exc_info=True)
        finally:
            if session.get_bind().dialect.name == "postgresql":
                try:
                    session.rollback()
                    session.execute(
                        text("SELECT set_config('app.tenant_id', '', false), set_config('app.auth_lookup', 'false', false)")
                    )
                    session.commit()
                except Exception:
                    session.rollback()
            session.close()
