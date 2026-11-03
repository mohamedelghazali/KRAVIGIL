"""Bind API keys to the user that created them.

Legacy tenant-wide keys have no trustworthy owner and are revoked rather than
being mapped to an arbitrary tenant user during authentication.
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_api_key_owner"
down_revision = "0006_merge_rls_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column("created_by_user_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_api_keys_created_by_user_id_users",
        "api_keys",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_api_keys_created_by_user_id",
        "api_keys",
        ["created_by_user_id"],
    )
    # Existing keys were tenant-wide and cannot safely inherit a user identity.
    op.execute("UPDATE api_keys SET is_active = FALSE WHERE created_by_user_id IS NULL")


def downgrade() -> None:
    op.drop_index("ix_api_keys_created_by_user_id", table_name="api_keys")
    op.drop_constraint(
        "fk_api_keys_created_by_user_id_users",
        "api_keys",
        type_="foreignkey",
    )
    op.drop_column("api_keys", "created_by_user_id")
