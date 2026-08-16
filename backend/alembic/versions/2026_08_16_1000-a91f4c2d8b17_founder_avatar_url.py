"""add founders.avatar_url

Live-reproduced: the profile photo camera button had no onClick at all, and
there was no backend support for it whatsoever -- no upload endpoint, no
storage, no column. This is the storage half of making it real; the upload
endpoint itself is POST /profile/avatar.

Revision ID: a91f4c2d8b17
Revises: e5a19c3b7f42
Create Date: 2026-08-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a91f4c2d8b17'
down_revision: Union[str, Sequence[str], None] = 'e5a19c3b7f42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'founders',
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('founders', 'avatar_url')
