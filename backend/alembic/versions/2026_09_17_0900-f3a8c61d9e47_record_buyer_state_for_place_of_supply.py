"""Record the buyer's state on the payment, for the GST place of supply.

WHY IT LIVES ON THE PAYMENT AND NOT ON THE FOUNDER. The place of supply is a
fact about ONE TRANSACTION, fixed at the moment it happened. A founder who
moves from Gujarat to Karnataka next year must not cause last year's invoice to
re-render as IGST -- the tax on that sale was CGST+SGST and the document is the
record of it. Storing it on `founders` would make every past invoice follow the
founder around; storing it here freezes it, the same way `plan_tier` and
`list_amount_inr` freeze what the payment was for and what it cost.

WHY IT IS NULLABLE WITH NO BACKFILL. Payments taken before this column existed
have no recoverable place of supply, and inventing one would be a guess about
tax. `app/payments/invoice.py` treats NULL as "cannot determine", which makes
it fall back to IGST and say nothing about a place of supply -- see
gst_states.is_intra_state, where "unknown" is deliberately a third answer
rather than a synonym for "inter-state".

Revision ID: f3a8c61d9e47
Revises: e9b4d72c5a18
"""

from alembic import op
import sqlalchemy as sa

revision = "f3a8c61d9e47"
down_revision = "e9b4d72c5a18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 60 rather than a tight bound: the longest canonical name in the statutory
    # list, "Dadra and Nagar Haveli and Daman and Diu", is 41 characters, and a
    # column that has to be widened later is a migration nobody wants for the
    # sake of a few bytes.
    op.add_column(
        "payments",
        sa.Column("buyer_state", sa.String(length=60), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("payments", "buyer_state")
