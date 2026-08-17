"""onboarding redesign: product_description, reality-check signals, invisible
gaps, current_challenges_other

Backs the 4-section onboarding rebuild (Path 1 = Stage 0/Ideation, Path 2 =
everyone beyond it):

  - product_description: Path 2's "What is it?" -- a one-line description
    distinct from building_summary (which already holds the product/idea NAME
    and is reused as-is for both paths).
  - founder_reality_signals: the 5 always-asked Founder Reality yes/no checks,
    one JSONB object rather than 5 separate boolean columns.
  - business_reality_signals: the matching Business Reality checks, Path 2
    only. Deliberately no server_default -- stays genuinely NULL for a Stage 0
    founder (the section does not apply to them at all) rather than an empty
    object, so "not applicable" and "not answered yet" stay distinguishable
    downstream.
  - invisible_gaps: multi-select, both paths, same JSONB-array-of-strings
    convention as customer_segment/current_challenges.
  - current_challenges_other: the free text behind an "Other" pick on the
    biggest-challenge question, same `<field>_other` convention as
    customer_segment_other. Also fixes a real bug: `current_challenges`
    already offered an "Other" option with nowhere for the typed text to go.

Revision ID: f3c8a92e5d61
Revises: a91f4c2d8b17
Create Date: 2026-08-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f3c8a92e5d61'
down_revision: Union[str, Sequence[str], None] = 'a91f4c2d8b17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'founders',
        sa.Column('product_description', sa.Text(), nullable=True),
    )
    op.add_column(
        'founders',
        sa.Column('founder_reality_signals', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        'founders',
        # No server_default on purpose -- see module docstring.
        sa.Column('business_reality_signals', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        'founders',
        sa.Column(
            'invisible_gaps', postgresql.JSONB(astext_type=sa.Text()),
            nullable=True, server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        'founders',
        sa.Column('current_challenges_other', sa.String(length=200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('founders', 'current_challenges_other')
    op.drop_column('founders', 'invisible_gaps')
    op.drop_column('founders', 'business_reality_signals')
    op.drop_column('founders', 'founder_reality_signals')
    op.drop_column('founders', 'product_description')
