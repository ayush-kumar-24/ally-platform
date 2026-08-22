"""Merge duplicate migration heads.

Revision ID: d5a7c91e2f64
Revises: c4f9a82d7e31, c1d9e4b73f28
Create Date: 2026-08-22 12:05:00
"""

from typing import Sequence, Union

revision: str = "d5a7c91e2f64"

down_revision: Union[str, Sequence[str], None] = (
    "c4f9a82d7e31",
    "c1d9e4b73f28",
)

branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
