"""Let notifications be delivered by email, per type, to founders on Pro.

TWO COLUMNS, ONE OF WHICH ALREADY EXISTED.

`notifications.sent_at` has been on the table since it was created and nothing
has ever read or written it. It is exactly the right name for "this went out",
so the email fan-out claims it rather than adding a near-duplicate beside it.
A NULL means not yet emailed; a timestamp means the worker is done with the row,
whether it sent, skipped it for plan or preference, or dropped it as stale.
That is what makes the worker idempotent -- nothing is ever emailed twice.

`notification_types.email_enabled` is the per-type switch, and the reason this
change is safe to ship with every type on. Eighteen types share one bell but not
one urgency: "your plan renews in three days" earns an email, "your profile is
incomplete" probably does not. Rather than guess now, every type starts enabled
and any of them is silenced for everyone with one UPDATE and no deploy -- the
same shape, and the same reasoning, as the `is_active` kill switch next to it.

WHY NOT A SECOND ROW PER NOTIFICATION. The obvious design is to write a
`channel='email'` row alongside each `in_app` one; the table has a channel
column and a CHECK that permits both. It does not work: `uq_notifications_dedup`
is unique on (founder_id, dedup_key) WITHOUT channel, so the second row collides
with the first on every notification that carries a dedup key -- which is all of
the standing conditions. Stamping the existing row sidesteps that entirely and
leaves the bell's queries untouched.

Revision ID: c8f2b16d3a05
Revises: b7e3a05c9f12
Create Date: 2026-09-09 14:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "c8f2b16d3a05"
down_revision = "b7e3a05c9f12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notification_types",
        sa.Column("email_enabled", sa.Boolean(), nullable=False,
                  server_default=sa.text("true")),
    )

    # The worker's queue: unsent rows, newest-first, across all founders. Partial
    # on sent_at IS NULL because a stamped row is finished forever -- the index
    # only ever holds the backlog, not the entire notification history, and
    # empties itself as the worker catches up.
    op.create_index(
        "ix_notifications_pending_email",
        "notifications",
        ["created_at"],
        postgresql_where=sa.text("sent_at IS NULL"),
    )

    # Every notification that already exists predates the fan-out. Without this
    # the first run of the worker treats the entire backlog as new and emails a
    # founder about every bell item they have ever received.
    op.execute("UPDATE public.notifications SET sent_at = now() WHERE sent_at IS NULL")


def downgrade() -> None:
    op.drop_index("ix_notifications_pending_email", table_name="notifications")
    op.drop_column("notification_types", "email_enabled")
