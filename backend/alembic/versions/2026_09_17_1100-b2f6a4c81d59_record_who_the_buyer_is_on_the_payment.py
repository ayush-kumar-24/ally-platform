"""Record whether a payment was personal or for a business, and who that business is.

Every plan was sold to one kind of buyer: a person. The invoice addressed them
by the name and email on their founder row, and a company buying a seat had
nothing to hand their accountant -- no GSTIN on the document means no input tax
credit, so the business paid 18% GST it could not reclaim.

FOUR COLUMNS, ALL ON THE PAYMENT, ALL NULLABLE.

`purchase_type` is the choice itself ('personal' or 'business'). The other
three are the business's tax identity and are meaningful only alongside it.

On the payment rather than on `founders`, for the same reason `buyer_state` and
`plan_tier` are: an invoice is the record of ONE transaction and must not
re-render differently because the buyer's details changed afterwards. A founder
who buys personally in March and through their company in June has two payments
with two different buyers on them, and both invoices stay correct forever. A
column on `founders` would rewrite the March document in June.

NULLABLE WITH NO BACKFILL, and `purchase_type` NULL is not a synonym for
'personal'. It means the payment predates the question being asked. The invoice
treats it as the personal layout because that is what those founders actually
received, but the distinction is kept so that "we never asked" stays
distinguishable from "they said personal" -- see app/payments/invoice.py.

No CHECK constraint on `purchase_type`: the allowed values live in
PurchaseType (app/payments/models.py) and are enforced by the API schema before
anything reaches here, which is where a founder gets a readable error rather
than an IntegrityError. The columns that follow are the same shape as
`buyer_state` from f3a8c61d9e47.

Revision ID: b2f6a4c81d59
Revises: f3a8c61d9e47
"""

from alembic import op
import sqlalchemy as sa

revision = "b2f6a4c81d59"
down_revision = "f3a8c61d9e47"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("purchase_type", sa.String(length=20), nullable=True))
    # Exactly 15 characters by statute, so the column says so. A value that is
    # not 15 alphanumerics never reaches here -- gst_states.normalise_gstin
    # refuses it at checkout.
    op.add_column("payments", sa.Column("buyer_gstin", sa.String(length=15), nullable=True))
    # The REGISTERED name, which is frequently not the founder's own name and
    # is what has to appear on a tax invoice for the credit to be claimable.
    op.add_column("payments", sa.Column("buyer_legal_name", sa.String(length=200), nullable=True))
    # Free text: Indian registered addresses do not decompose reliably into
    # line/city/pincode, and this is printed verbatim rather than queried.
    op.add_column("payments", sa.Column("buyer_address", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("payments", "buyer_address")
    op.drop_column("payments", "buyer_legal_name")
    op.drop_column("payments", "buyer_gstin")
    op.drop_column("payments", "purchase_type")
