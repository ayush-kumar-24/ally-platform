"""Merge the privacy-audit branch back onto the plan-ladder branch.

Two heads existed at once, which is why `alembic upgrade head` had nothing
unambiguous to do and the plan-ladder branch sat unapplied:

    c6a4e83f19d7 ─┬─ ... ─ a3f81c05e6d7 ─ f2c7a91d4e83   (privacy audit labels)
                  └─ d7b1e05a9c34 ─ e8c2f16b0d45 ─ 6d380713f84f
                     (Rs 199 'basic' tier, discovery priority + 30-minute calls)

The consequence was not theoretical. `discovery_calls.is_priority` is declared
on the model and added by e8c2f16b0d45, which had never run -- so every attempt
to book a discovery call died at the INSERT with `column "is_priority" of
relation "discovery_calls" does not exist`, after the Google Meet link had
already been created. Founders got a 500 and an orphaned meeting.

The same branch carries the Rs 199 'basic' plan tier, which the new pricing
needs.

This merge is empty by design: both branches touch different tables and neither
needs reconciling. It exists so there is one head again and the unapplied branch
can finally land.

Revision ID: 499814b9067a
Revises: 6d380713f84f, f2c7a91d4e83
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '499814b9067a'
down_revision: Union[str, Sequence[str], None] = ('6d380713f84f', 'f2c7a91d4e83')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
