"""Record on the payment itself which plan it buys.

WHY. Nothing on our side stored it. `start_checkout` put the tier in the
Razorpay ORDER's notes and `_grant_for_captured` read it back off the captured
PAYMENT entity, on the premise -- stated in gateway.py -- that Razorpay copies
order notes onto the payment. The browser's Checkout options carry their own
`notes`, and ours sent `{plan_name: ...}`, so the payment entity arrived with no
`plan_tier` at all: the grant was refused, the founder was charged, and no plan
was given. That is not a theoretical failure; it is what happened to a founder
who paid Rs 999.

The second reason is worse than the first. Those notes come from the browser,
so what the founder is charged and what they are granted had different
authorities: pay for the cheapest tier, put `plan_tier: pro` in the notes, get
Pro. The tier has to be OUR record, written when the order is priced, and that
is what this column is.

Nullable, with no backfill. Payments already captured cannot have their intent
recovered from here, and inventing one would be a guess about money.

Revision ID: d7f4c2e91a63
Revises: c5e1a83b642d
"""

from alembic import op
import sqlalchemy as sa

revision = "d7f4c2e91a63"
down_revision = "c5e1a83b642d"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    if not _has_column("payments", "plan_tier"):
        op.add_column("payments", sa.Column("plan_tier", sa.String(20), nullable=True))


def downgrade() -> None:
    if _has_column("payments", "plan_tier"):
        op.drop_column("payments", "plan_tier")
