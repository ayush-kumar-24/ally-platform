"""add founders.processing_restricted_at (Art 18 restriction of processing)

Revision ID: d4e0f82a5b31
Revises: c3d9e71f4a20
Create Date: 2026-08-02 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e0f82a5b31'
down_revision: Union[str, Sequence[str], None] = 'c3d9e71f4a20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the restriction flag next to the existing deletion_* columns.

    Nullable timestamp rather than a boolean: "restricted since when" is the fact
    worth keeping -- a bare boolean would lose the moment the pause began, which is
    exactly what an accountability audit asks for.
    """
    op.add_column(
        "founders",
        sa.Column("processing_restricted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("founders", "processing_restricted_at")
