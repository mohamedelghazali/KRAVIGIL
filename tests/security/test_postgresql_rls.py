import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool


ADMIN_DATABASE_URL = os.getenv("DATABASE_URL")
APP_DATABASE_URL = os.getenv("RLS_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not ADMIN_DATABASE_URL or not APP_DATABASE_URL,
    reason="PostgreSQL RLS integration credentials are not configured",
)


def test_postgresql_rls_isolates_tenants_and_app_role_cannot_bypass():
    admin = create_engine(ADMIN_DATABASE_URL, poolclass=NullPool)
    app = create_engine(APP_DATABASE_URL, poolclass=NullPool)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    target_a, target_b = uuid.uuid4(), uuid.uuid4()

    try:
        with admin.begin() as connection:
            connection.execute(
                text("INSERT INTO organizations (id, name, created_at) VALUES (:id, :name, NOW())"),
                [{"id": tenant_a, "name": f"rls-a-{tenant_a}"}, {"id": tenant_b, "name": f"rls-b-{tenant_b}"}],
            )
            connection.execute(
                text("""
                    INSERT INTO targets (id, tenant_id, name, ip_address, domain, is_authorized, created_at)
                    VALUES (:id, :tenant_id, :name, :ip, NULL, FALSE, NOW())
                """),
                [
                    {"id": target_a, "tenant_id": tenant_a, "name": "tenant-a-target", "ip": "1.1.1.1"},
                    {"id": target_b, "tenant_id": tenant_b, "name": "tenant-b-target", "ip": "8.8.8.8"},
                ],
            )

        with app.connect() as connection:
            bypass_rls = connection.execute(
                text("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user")
            ).scalar_one()
            assert bypass_rls is False

            connection.execute(
                text("SELECT set_config('app.tenant_id', :tenant_id, false)"),
                {"tenant_id": str(tenant_a)},
            )
            connection.commit()

            visible = connection.execute(
                text("SELECT id FROM targets ORDER BY name")
            ).scalars().all()
            assert visible == [target_a]

            with pytest.raises(DBAPIError):
                connection.execute(
                    text("""
                        INSERT INTO targets (id, tenant_id, name, ip_address, is_authorized, created_at)
                        VALUES (:id, :tenant_id, 'cross-tenant-write', '9.9.9.9', FALSE, NOW())
                    """),
                    {"id": uuid.uuid4(), "tenant_id": str(tenant_b)},
                )
                connection.commit()
    finally:
        with admin.begin() as connection:
            connection.execute(text("DELETE FROM targets WHERE id IN (:a, :b)"), {"a": target_a, "b": target_b})
            connection.execute(text("DELETE FROM organizations WHERE id IN (:a, :b)"), {"a": tenant_a, "b": tenant_b})
        app.dispose()
        admin.dispose()
