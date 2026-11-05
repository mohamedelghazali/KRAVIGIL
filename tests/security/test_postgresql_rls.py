import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool


ADMIN_DATABASE_URL = os.getenv("DATABASE_URL")
APP_DATABASE_URL = os.getenv("RLS_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not ADMIN_DATABASE_URL or not APP_DATABASE_URL,
    reason="PostgreSQL RLS integration credentials are not configured",
)


def _insert_tenant_targets(admin, tenant_a, tenant_b, target_a, target_b):
    with admin.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO organizations (id, name, created_at) "
                "VALUES (:id, :name, NOW())"
            ),
            [
                {"id": tenant_a, "name": f"rls-a-{tenant_a}"},
                {"id": tenant_b, "name": f"rls-b-{tenant_b}"},
            ],
        )
        connection.execute(
            text(
                """
                INSERT INTO targets
                    (id, tenant_id, name, ip_address, domain, is_authorized, created_at)
                VALUES
                    (:id, :tenant_id, :name, :ip, NULL, FALSE, NOW())
                """
            ),
            [
                {
                    "id": target_a,
                    "tenant_id": tenant_a,
                    "name": "tenant-a-target",
                    "ip": "1.1.1.1",
                },
                {
                    "id": target_b,
                    "tenant_id": tenant_b,
                    "name": "tenant-b-target",
                    "ip": "8.8.8.8",
                },
            ],
        )


def _delete_tenant_targets(admin, tenant_a, tenant_b, target_a, target_b):
    with admin.begin() as connection:
        connection.execute(
            text("DELETE FROM targets WHERE id IN (:a, :b)"),
            {"a": target_a, "b": target_b},
        )
        connection.execute(
            text("DELETE FROM organizations WHERE id IN (:a, :b)"),
            {"a": tenant_a, "b": tenant_b},
        )


def test_postgresql_rls_isolates_tenants_and_app_role_cannot_bypass():
    admin = create_engine(ADMIN_DATABASE_URL, poolclass=NullPool)
    app = create_engine(APP_DATABASE_URL, poolclass=NullPool)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    target_a, target_b = uuid.uuid4(), uuid.uuid4()

    try:
        _insert_tenant_targets(admin, tenant_a, tenant_b, target_a, target_b)

        with app.connect() as connection:
            role = connection.execute(
                text(
                    "SELECT rolsuper, rolbypassrls FROM pg_roles "
                    "WHERE rolname = current_user"
                )
            ).one()
            assert role.rolsuper is False
            assert role.rolbypassrls is False

            for table in ("organizations", "targets"):
                rls_state = connection.execute(
                    text(
                        "SELECT relrowsecurity, relforcerowsecurity "
                        "FROM pg_class WHERE oid = to_regclass(:table)"
                    ),
                    {"table": table},
                ).one()
                assert rls_state.relrowsecurity is True
                assert rls_state.relforcerowsecurity is True

            connection.execute(
                text("SELECT set_config('app.tenant_id', :tenant_id, false)"),
                {"tenant_id": str(tenant_a)},
            )
            connection.commit()

            visible_orgs = connection.execute(
                text("SELECT id FROM organizations ORDER BY name")
            ).scalars().all()
            assert visible_orgs == [tenant_a]

            visible_targets = connection.execute(
                text("SELECT id FROM targets ORDER BY name")
            ).scalars().all()
            assert visible_targets == [target_a]

            updated = connection.execute(
                text("UPDATE targets SET name = 'cross-tenant-update' WHERE id = :id"),
                {"id": target_b},
            )
            assert updated.rowcount == 0

            deleted = connection.execute(
                text("DELETE FROM targets WHERE id = :id"),
                {"id": target_b},
            )
            assert deleted.rowcount == 0

            with pytest.raises(DBAPIError):
                connection.execute(
                    text(
                        """
                        INSERT INTO targets
                            (id, tenant_id, name, ip_address, is_authorized, created_at)
                        VALUES
                            (:id, :tenant_id, 'cross-tenant-write', '9.9.9.9', FALSE, NOW())
                        """
                    ),
                    {"id": uuid.uuid4(), "tenant_id": str(tenant_b)},
                )
            connection.rollback()

            # A failed cross-tenant write must not change the rows visible to tenant A.
            visible_after_rejection = connection.execute(
                text("SELECT id FROM targets ORDER BY name")
            ).scalars().all()
            assert visible_after_rejection == [target_a]
    finally:
        _delete_tenant_targets(admin, tenant_a, tenant_b, target_a, target_b)
        app.dispose()
        admin.dispose()


def test_worker_rls_context_is_scoped_and_cleared_between_tasks():
    # Exercise the same helpers used by Celery tasks against the real app role.
    from workers.tasks import _close_worker_session, set_worker_tenant

    admin = create_engine(ADMIN_DATABASE_URL, poolclass=NullPool)
    app = create_engine(APP_DATABASE_URL, pool_size=1, max_overflow=0)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    target_a, target_b = uuid.uuid4(), uuid.uuid4()

    try:
        _insert_tenant_targets(admin, tenant_a, tenant_b, target_a, target_b)

        first_task_session = Session(app)
        try:
            set_worker_tenant(first_task_session, tenant_a)
            backend_pid = first_task_session.execute(
                text("SELECT pg_backend_pid()")
            ).scalar_one()
            visible = first_task_session.execute(
                text("SELECT id FROM targets ORDER BY name")
            ).scalars().all()
            assert visible == [target_a]
        finally:
            _close_worker_session(first_task_session)

        second_task_session = Session(app)
        try:
            # The pool is constrained to one connection: this proves cleanup on
            # the reused PostgreSQL backend, not merely isolation via a new socket.
            assert second_task_session.execute(
                text("SELECT pg_backend_pid()")
            ).scalar_one() == backend_pid
            assert second_task_session.execute(
                text("SELECT id FROM targets ORDER BY name")
            ).scalars().all() == []

            set_worker_tenant(second_task_session, tenant_b)
            visible = second_task_session.execute(
                text("SELECT id FROM targets ORDER BY name")
            ).scalars().all()
            assert visible == [target_b]
        finally:
            _close_worker_session(second_task_session)
    finally:
        _delete_tenant_targets(admin, tenant_a, tenant_b, target_a, target_b)
        app.dispose()
        admin.dispose()
