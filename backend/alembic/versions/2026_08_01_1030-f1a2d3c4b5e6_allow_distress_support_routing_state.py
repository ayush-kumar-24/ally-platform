"""allow distress_support routing state on sessions

The reasoning pipeline routes a high-distress session to 'distress_support'
(wellbeing before diagnostic completeness), but sessions_routing_state_check only
permitted continue/validate/generate_report -- so persisting a distressed session
raised a CHECK violation and rolled the whole pipeline back (no report, no distress
routing saved). This adds the missing allowed value.

Revision ID: f1a2d3c4b5e6
Revises: e7b3c9d21f4a
Create Date: 2026-08-01 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f1a2d3c4b5e6'
down_revision: Union[str, Sequence[str], None] = 'e7b3c9d21f4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('sessions_routing_state_check', 'sessions', type_='check')
    op.create_check_constraint(
        'sessions_routing_state_check',
        'sessions',
        "routing_state IN ('continue','validate','generate_report','distress_support')",
    )


def downgrade() -> None:
    op.drop_constraint('sessions_routing_state_check', 'sessions', type_='check')
    op.create_check_constraint(
        'sessions_routing_state_check',
        'sessions',
        "routing_state IN ('continue','validate','generate_report')",
    )
