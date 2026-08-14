"""cache the generated report narrative instead of rebuilding it per view

_build_narrative() (app/api/v1/reports/routes.py) is called fresh on every
hit to GET /reports/{id}, /founder-dna, /business-dna, /insights,
/recommendations, POST /export, and the public /shared/{token} page --
five founder-facing endpoints plus the public share page, all rebuilding
the SAME narrative from scratch. Live-measured: with REPORT_NARRATIVE_LLM
on, that means the full LLM section narrator (7 sequential provider calls)
re-runs on every single page view or PDF download of a report that was
already generated and has not changed -- ~27s and 7 billed LLM calls to
view a report a founder already looked at a minute ago.

A founder_report's underlying facts are fixed at generation time (the
reasoning pipeline already treats the report row itself as a frozen
artifact -- see FounderReport creation in reasoning/service.py, and the
dashboard already reads report.title/summary as, per its own comment,
"cached prose only, never regenerated"). The narrative sections deserve
the same treatment: generate once, persist, serve the same content on
every subsequent read. narrative_snapshot is nullable and lazily
populated -- existing reports keep working unchanged on their first view
after this migration, which is also when they get cached.

Revision ID: e5a19c3b7f42
Revises: d2f6b91ac073
Create Date: 2026-08-14 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'e5a19c3b7f42'
down_revision: Union[str, Sequence[str], None] = 'd2f6b91ac073'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'founder_reports',
        sa.Column('narrative_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('founder_reports', 'narrative_snapshot')
