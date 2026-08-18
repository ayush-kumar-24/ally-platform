"""Join the Current Problem branch with the RDS Founder DNA schema branch.

Empty on purpose -- a merge revision carries no DDL. It exists only to give
Alembic a single head again.

Two lines of work branched from the same point on 18 Aug 2026:

  * a91f4c76b2d8 -- Current Problem phase, pillar round-robin, and the two
    question re-tags (this branch)
  * b4e9a17c6d32 -- brings production RDS up to the Founder DNA phase-2
    schema (landed on main separately)

They touch different tables and do not conflict, but with two heads
`alembic upgrade head` refuses to run at all -- which would have blocked the
deploy rather than corrupting anything. This joins them.

Revision ID: bb6617156c6c
Revises: a91f4c76b2d8, b4e9a17c6d32
Create Date: 2026-08-18 14:35:37.016524

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bb6617156c6c'
down_revision: Union[str, Sequence[str], None] = ('a91f4c76b2d8', 'b4e9a17c6d32')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
