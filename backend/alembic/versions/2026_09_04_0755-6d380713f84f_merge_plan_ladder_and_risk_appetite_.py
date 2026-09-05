"""merge plan ladder and risk appetite heads

Revision ID: 6d380713f84f
Revises: a3f81c05e6d7, e8c2f16b0d45
Create Date: 2026-09-04 07:55:04.619623

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6d380713f84f'
down_revision: Union[str, Sequence[str], None] = ('a3f81c05e6d7', 'e8c2f16b0d45')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
