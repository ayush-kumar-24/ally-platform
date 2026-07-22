"""baseline adopt existing supabase schema

Revision ID: 5cbf7c8fea1e
Revises: 
Create Date: 2026-07-20 20:06:38.904925

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5cbf7c8fea1e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Intentionally empty.

    This is a marker, not a migration. When it was written the database already
    held 56 tables (plus 36 partitions, 87 RLS policies and a set of database
    functions) created by five Supabase migrations. Stamping this revision
    records "Alembic is now tracking a database that is already at this state"
    without attempting to recreate any of it.

    Every schema change from here on is a new Alembic revision. Do not add DDL
    to this file.
    """
    pass


def downgrade() -> None:
    """No-op -- there is nothing below the baseline to fall back to."""
    pass
