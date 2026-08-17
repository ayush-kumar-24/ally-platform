"""merge production reconciliation and main migration histories

Revision ID: 6f1d2c9a4b70
Revises: e29b1b0a58f6, f3c8a92e5d61
Create Date: 2026-08-17 15:30:00

This is intentionally a no-op merge revision.

Production RDS already contains the verified schema effects from both
migration branches. This revision only reunifies Alembic history so that
future migrations have one canonical parent.
"""

from typing import Sequence, Union


revision: str = "6f1d2c9a4b70"
down_revision: Union[str, Sequence[str], None] = (
    "e29b1b0a58f6",
    "f3c8a92e5d61",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass