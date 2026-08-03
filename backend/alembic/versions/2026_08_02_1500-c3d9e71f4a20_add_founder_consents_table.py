"""add founder_consents table (append-only consent ledger)

Revision ID: c3d9e71f4a20
Revises: a182f6ed2ad5
Create Date: 2026-08-02 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d9e71f4a20'
down_revision: Union[str, Sequence[str], None] = 'a182f6ed2ad5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the append-only consent ledger.

    One row per consent event (not per founder) -- GDPR Art 7(1) requires being able
    to demonstrate what was agreed to and when, which an overwritten row destroys.
    The composite index serves the only hot query: "this founder's newest record".
    """
    op.create_table(
        "founder_consents",
        sa.Column("consent_id", sa.String(length=64), primary_key=True),
        sa.Column("founder_id", sa.Integer(),
                  sa.ForeignKey("founders.founder_id", ondelete="CASCADE"), nullable=False),
        sa.Column("terms_version", sa.String(length=20), nullable=False),
        sa.Column("privacy_version", sa.String(length=20), nullable=False),
        sa.Column("agree_terms", sa.Boolean(), nullable=False),
        sa.Column("agree_diagnosis", sa.Boolean(), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_founder_consents_founder_id", "founder_consents", ["founder_id"])
    op.create_index(
        "ix_founder_consents_founder_consented_at",
        "founder_consents",
        ["founder_id", "consented_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_founder_consents_founder_consented_at", table_name="founder_consents")
    op.drop_index("ix_founder_consents_founder_id", table_name="founder_consents")
    op.drop_table("founder_consents")
