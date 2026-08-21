"""merge latest migration heads

Revision ID: c4f9a82d7e31
Revises: b2d5f8a03c17, b3c9d15e8a47
Create Date: 2026-08-21 12:35:00
"""

from typing import Sequence, Union

revision: str = "c4f9a82d7e31"
down_revision: Union[str, Sequence[str], None] = (
    "b2d5f8a03c17",
    "b3c9d15e8a47",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
