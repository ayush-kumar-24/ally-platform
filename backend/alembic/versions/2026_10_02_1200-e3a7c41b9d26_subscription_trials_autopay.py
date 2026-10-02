"""Let a Razorpay trial + autopay subscription be recorded.

Starting a trial creates a Razorpay subscription BEFORE the founder has
authorised the mandate or paid the trial fee, and the row that remembers whose
subscription it is has to exist from that moment: the webhook that says
"authorised" carries only Razorpay's subscription id. None of the existing
statuses describes that row honestly -- 'trial' would grant nothing yet claim
a trial was running -- so 'pending' is added.

The partial unique index is the DB-level guard that one Razorpay subscription
maps to exactly one row, the same role payments.gateway_payment_id plays for a
payment.

A widening plus an index: no existing value is removed, so no existing row can
be invalidated.
"""

from alembic import op

revision = "e3a7c41b9d26"
down_revision = "b48e5c12d709"
branch_labels = None
depends_on = None

_CONSTRAINT = "subscriptions_status_check"
_OLD = ("active", "cancelled", "expired", "paused", "trial")
_NEW = ("active", "cancelled", "expired", "paused", "trial", "pending")
_INDEX = "uq_subscriptions_gateway_subscription_id"


def _swap(vals: tuple[str, ...]) -> None:
    listed = ", ".join(f"'{v}'::character varying" for v in vals)
    op.execute(f"ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS {_CONSTRAINT}")
    op.execute(
        f"ALTER TABLE subscriptions ADD CONSTRAINT {_CONSTRAINT} "
        f"CHECK (status::text = ANY (ARRAY[{listed}]::text[]))"
    )


def upgrade() -> None:
    _swap(_NEW)
    op.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS {_INDEX} ON subscriptions (gateway_subscription_id) "
        "WHERE gateway_subscription_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {_INDEX}")
    # A pending row never granted anything and charged nothing.
    op.execute("UPDATE subscriptions SET status = 'expired' WHERE status = 'pending'")
    _swap(_OLD)
