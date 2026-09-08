"""Let a founder clear the notification panel without losing the dedup key.

WHY A COLUMN AND NOT A DELETE. The feed is rebuilt every time the bell is
opened -- `generate_for_founder` re-evaluates standing conditions (a task
overdue, credits expiring, a deletion counting down) on every list call. It is
safe to run repeatedly only because each rule is idempotent on a `dedup_key`,
and the thing that makes it idempotent is the row already existing.

So deleting a notification does not clear it. It removes the dedup key, the
next page load regenerates the identical row, and "Clear all" looks broken in a
way that is worse than not clearing at all.

`dismissed_at` keeps the row -- dedup still suppresses regeneration -- and hides
it from the list. Nullable and additive, so the deploy is a no-op for anything
already running.

Revision ID: a1f4c9b73e05
Revises: c7e4b19d5a20
Create Date: 2026-09-09 09:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "a1f4c9b73e05"
down_revision = "c7e4b19d5a20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # The list query filters on it for every bell open, alongside founder_id.
    # Partial, because the rows worth indexing are the ones still showing.
    op.create_index(
        "idx_notifications_visible",
        "notifications",
        ["founder_id"],
        postgresql_where=sa.text("dismissed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_notifications_visible", table_name="notifications")
    op.drop_column("notifications", "dismissed_at")
