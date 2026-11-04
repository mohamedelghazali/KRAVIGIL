"""Add the missing Celery task identifier column to scans."""
from alembic import op
import sqlalchemy as sa

revision = "0008_scan_task_id"
down_revision = "0007_api_key_owner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scans",
        sa.Column("task_id", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scans", "task_id")
