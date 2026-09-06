"""Let a Rs 199 Basic purchase actually be recorded as a subscription.

`d7b1e05a9c34` widened `founders_plan_type_check` for the Basic tier but left
the identically-named constraint on `subscriptions` alone, and `subscriptions`
is written FIRST when a payment is captured (payments/service.py:
create_subscription, then grant_plan). So a captured Rs 199 payment died on the
INSERT before it ever reached the plan grant: Razorpay took the money, the
webhook 500'd, Razorpay retried and got the same 500, and the founder stayed on
Free. Rs 450 and Rs 999 were unaffected -- 'starter' and 'pro' were already in
the list -- which is exactly why this survived: the one tier nobody could buy
was the cheapest one.

`billing_cycle` is widened at the same time and for the same reason. Basic is a
single payment for a single diagnosis, but the only cycles the constraint
allowed were 'monthly' and 'annual', so the service had to claim a monthly
cycle and stamp an expiry 30 days out. Nothing enforces that expiry today, so
it was a reporting lie rather than an outage -- admin revenue views read these
rows -- but it is the kind of lie that becomes an outage the day someone builds
expiry enforcement on top of it and silently revokes a one-time purchase.

Both are widenings: no existing value is removed, so no existing row can be
invalidated.
"""

from alembic import op

revision = "b4d927f1a6c8"
down_revision = "499814b9067a"
branch_labels = None
depends_on = None

_PLAN_CONSTRAINT = "subscriptions_plan_type_check"
_PLAN_OLD = ("free", "starter", "pro", "enterprise")
_PLAN_NEW = ("free", "basic", "starter", "pro", "enterprise")

_CYCLE_CONSTRAINT = "subscriptions_billing_cycle_check"
_CYCLE_OLD = ("monthly", "annual")
_CYCLE_NEW = ("monthly", "annual", "one_time")


def _values(vals: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'::character varying" for v in vals)


def _swap(constraint: str, column: str, vals: tuple[str, ...]) -> None:
    # IF EXISTS so a database provisioned from a snapshot predating the
    # constraint does not fail here; the ADD below is what matters.
    op.execute(f"ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS {constraint}")
    op.execute(
        f"ALTER TABLE subscriptions ADD CONSTRAINT {constraint} "
        f"CHECK ({column}::text = ANY (ARRAY[{_values(vals)}]::text[]))"
    )


def upgrade() -> None:
    _swap(_PLAN_CONSTRAINT, "plan_type", _PLAN_NEW)
    _swap(_CYCLE_CONSTRAINT, "billing_cycle", _CYCLE_NEW)


def downgrade() -> None:
    # Rows written under the wider constraints would violate the narrower ones.
    # Map them to the nearest previously-legal value rather than deleting paid
    # history: a subscription row is a record that money changed hands.
    op.execute("UPDATE subscriptions SET plan_type = 'starter' WHERE plan_type = 'basic'")
    op.execute("UPDATE subscriptions SET billing_cycle = 'monthly' WHERE billing_cycle = 'one_time'")
    _swap(_PLAN_CONSTRAINT, "plan_type", _PLAN_OLD)
    _swap(_CYCLE_CONSTRAINT, "billing_cycle", _CYCLE_OLD)
