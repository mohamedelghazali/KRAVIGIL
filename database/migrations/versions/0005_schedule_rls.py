"""Enforce tenant isolation for scheduled scans and association rows."""
from alembic import op

revision = "0005_schedule_rls"
down_revision = "0004_threat_indicators"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE scheduled_scans ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE scheduled_scans FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_scheduled_scans ON scheduled_scans "
        "FOR ALL USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
    )

    # The many-to-many table has no tenant_id; authorize each relationship by
    # checking both parent records against the active tenant.
    op.execute("ALTER TABLE finding_observations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE finding_observations FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_finding_observations ON finding_observations "
        "FOR ALL USING (EXISTS ("
        "SELECT 1 FROM findings f JOIN observations o ON o.id = observation_id "
        "WHERE f.id = finding_id "
        "AND f.tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid "
        "AND o.tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"
        ")) WITH CHECK (EXISTS ("
        "SELECT 1 FROM findings f JOIN observations o ON o.id = observation_id "
        "WHERE f.id = finding_id "
        "AND f.tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid "
        "AND o.tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"
        "))"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_finding_observations ON finding_observations")
    op.execute("ALTER TABLE finding_observations DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_scheduled_scans ON scheduled_scans")
    op.execute("ALTER TABLE scheduled_scans DISABLE ROW LEVEL SECURITY")
