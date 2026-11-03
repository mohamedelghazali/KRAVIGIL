"""Tenant-scoped threat intelligence indicators."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_threat_indicators"
down_revision = "0003_runtime_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "threat_indicators",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("indicator_type", sa.String(50), nullable=False),
        sa.Column("indicator_value", sa.String(512), nullable=False),
        sa.Column("threat_type", sa.String(255), nullable=False, server_default="unknown"),
        sa.Column("source", sa.String(100), nullable=False, server_default="alienvault_otx"),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id", "indicator_type", "indicator_value", "source",
            name="uq_threat_indicator_tenant_value_source",
        ),
    )
    op.create_index("ix_threat_indicators_tenant_id", "threat_indicators", ["tenant_id"])
    op.create_index("ix_threat_indicators_tenant_created", "threat_indicators", ["tenant_id", "created_at"])
    op.execute("ALTER TABLE threat_indicators ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE threat_indicators FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation_threat_indicators ON threat_indicators "
        "FOR ALL USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
        "WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
    )


def downgrade() -> None:
    op.drop_table("threat_indicators")
