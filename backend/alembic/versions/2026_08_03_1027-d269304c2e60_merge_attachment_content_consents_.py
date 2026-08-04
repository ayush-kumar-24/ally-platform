"""merge attachment-content-consents-privacy and admin-panel-plans-credits branches

Revision ID: d269304c2e60
Revises: 18ad01821373, c9d5e7a1b344
Create Date: 2026-08-03 10:27:54.433187

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd269304c2e60'
down_revision: Union[str, Sequence[str], None] = ('18ad01821373', 'c9d5e7a1b344')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
