"""merge heads: partition RLS + new tables

Revision ID: 0210ac55cd12
Revises: 055fcff2b6b5, 6d05993bb818
Create Date: 2026-07-27 19:01:14.470229

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0210ac55cd12'
down_revision: Union[str, Sequence[str], None] = ('055fcff2b6b5', '6d05993bb818')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
