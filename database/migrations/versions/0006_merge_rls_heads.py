"""Merge the independent RLS migration branches.

Revision ID: 0006_merge_rls_heads
Revises: 0005_organization_rls, 0005_schedule_rls

This is a graph-only merge. Both parent migrations have already been applied
independently by installations that reached either branch head.
"""
revision = "0006_merge_rls_heads"
down_revision = ("0005_organization_rls", "0005_schedule_rls")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No schema operations: both parent revisions contain their own changes.
    pass


def downgrade() -> None:
    # A merge revision has no independent schema state to reverse.
    pass
