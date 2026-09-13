"""Who a payment is for, and the GST invoice details they gave for it.

The checkout screen (Billing.jsx) now asks personal or business use before
Pay, and for a business, offers three optional fields -- company name, GSTIN,
billing address -- so the invoice can be raised correctly the first time
instead of the accounts team chasing the founder for them afterwards.

One JSONB column, mirroring `plan_tier` (d7f4c2e91a63): nullable, no
backfill, and nothing about it may ever affect what is charged or granted --
see app/payments/billing.py. It is set via `PATCH /payments/{id}/billing`
when the checkout screen is filled in, not at order creation: the order (and
its payment row) is created the moment the screen opens, before the founder
has had a chance to answer the question.

Revision ID: f8a3c26e4b91
Revises: e5b2d47a91c3
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f8a3c26e4b91"
down_revision = "e5b2d47a91c3"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    if not _has_column("payments", "billing"):
        op.add_column(
            "payments",
            sa.Column("billing", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )


def downgrade() -> None:
    if _has_column("payments", "billing"):
        op.drop_column("payments", "billing")
