"""Enforce tenant isolation on the organization registry."""

from alembic import op

revision = "0005_organization_rls"
down_revision = "0004_threat_indicators"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE organizations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE organizations FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_organizations ON organizations "
        "FOR ALL USING (id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
        "WITH CHECK (id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
    )
    op.execute(
        "CREATE POLICY auth_lookup_organizations ON organizations "
        "FOR SELECT USING (current_setting('app.auth_lookup', true) = 'true')"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS auth_lookup_organizations ON organizations")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_organizations ON organizations")
