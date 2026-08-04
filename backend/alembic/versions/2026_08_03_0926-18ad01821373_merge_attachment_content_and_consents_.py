"""merge attachment-content and consents-privacy branches

Revision ID: 18ad01821373
Revises: a7c9e1f3b5d7, d4e0f82a5b31
Create Date: 2026-08-03 09:26:34.834001

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '18ad01821373'
down_revision: Union[str, Sequence[str], None] = ('a7c9e1f3b5d7', 'd4e0f82a5b31')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
