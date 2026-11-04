"""Track evidence deletion as a retryable two-phase lifecycle."""
from alembic import op
import sqlalchemy as sa

revision = "0009_evidence_deletion_state"
down_revision = "0008_scan_task_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "evidence",
        sa.Column(
            "deletion_status",
            sa.String(length=20),
            nullable=False,
            server_default="ACTIVE",
        ),
    )
    op.add_column(
        "evidence",
        sa.Column("deletion_requested_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_evidence_deletion_status",
        "evidence",
        ["deletion_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_evidence_deletion_status", table_name="evidence")
    op.drop_column("evidence", "deletion_requested_at")
    op.drop_column("evidence", "deletion_status")
