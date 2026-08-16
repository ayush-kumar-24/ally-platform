"""account deletion execution: track completion, admit supabase as a webhook source

Erasure requests (self-service DPDP and, going forward, a Supabase Auth
"user.deleted" webhook) have always been schedulable via
founders.deletion_requested_at / deletion_scheduled_at -- but nothing ever
consumed the schedule. A founder past their grace window sat there forever,
indistinguishable from one who was never touched. This is the missing half:
somewhere to record that the sweep actually ran for a given founder, so a
scheduled job can find "due and not yet done" instead of re-processing
(or silently never processing) every row every time it runs.

deletion_executed_at is deliberately separate from deletion_scheduled_at --
the schedule is "when this becomes eligible", the execution stamp is "when it
actually happened". Collapsing them would make it impossible to tell a
founder whose sweep ran from one whose sweep is merely overdue.

webhook_logs.source did not include 'supabase' -- the table was scoped to
payment/calendar providers before there was any reason to receive a webhook
from the identity provider. Account-deletion identity events are the first
Supabase-originated webhook this backend will receive.

Revision ID: d2f6b91ac073
Revises: c4a71fe38b52
Create Date: 2026-08-11 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd2f6b91ac073'
down_revision: Union[str, Sequence[str], None] = 'c4a71fe38b52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'founders',
        sa.Column('deletion_executed_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.drop_constraint('webhook_logs_source_check', 'webhook_logs', type_='check')
    op.create_check_constraint(
        'webhook_logs_source_check',
        'webhook_logs',
        "source::text = ANY (ARRAY['razorpay'::character varying, 'calendly'::character varying, "
        "'stripe'::character varying, 'supabase'::character varying, 'other'::character varying]::text[])",
    )


def downgrade() -> None:
    op.drop_constraint('webhook_logs_source_check', 'webhook_logs', type_='check')
    op.create_check_constraint(
        'webhook_logs_source_check',
        'webhook_logs',
        "source::text = ANY (ARRAY['razorpay'::character varying, 'calendly'::character varying, "
        "'stripe'::character varying, 'other'::character varying]::text[])",
    )
    op.drop_column('founders', 'deletion_executed_at')
