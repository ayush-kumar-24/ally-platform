"""add achievements table

Revision ID: 4eae90a3e06b
Revises: f7a3d5b1ef52
Create Date: 2026-08-20 10:30:00.000000

Backs the "Your Achievements" page. Every row is founder-authored (there is
no automatic achievement-detection feature yet); the page itself is gated
client- and server-side (see app/achievements/service.py's
AchievementsLockedError) on the founder's real total message_count across
`conversations`, not stored here.

RLS: same guarded ally_founder_isolation pattern as f7a3d5b1ef52 (which
added founder_goals) -- see that migration's docstring, and d91c6e4b72aa's,
for why this is a no-op on Supabase by design and what still needs adding
there separately.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4eae90a3e06b'
down_revision: Union[str, Sequence[str], None] = 'f7a3d5b1ef52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


POLICY_NAME = "ally_founder_isolation"
ALLY_APP_ROLE = "ally_app"


def _ally_app_exists() -> bool:
    """Duplicated per-migration on purpose -- see d91c6e4b72aa's docstring."""
    return bool(
        op.get_bind()
        .execute(text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": ALLY_APP_ROLE})
        .scalar()
    )


def upgrade() -> None:
    op.create_table(
        "achievements",
        sa.Column("achievement_id", sa.String(length=64), primary_key=True),
        sa.Column("founder_id", sa.Integer(),
                  sa.ForeignKey("founders.founder_id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("category", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("occurred_on", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_achievements_founder_id", "achievements", ["founder_id"])

    if not _ally_app_exists():
        print(
            f"WARNING [{revision}]: role {ALLY_APP_ROLE!r} does not exist on this "
            "database -- SKIPPING the founder-isolation RLS policy for achievements. "
            "EXPECTED on Supabase (native RLS handles this instead, but a policy for "
            "achievements still needs adding there separately -- see module docstring). "
            "NOT expected on RDS."
        )
        return

    predicate = (
        "(founder_id = public.get_founder_id()) OR "
        "(COALESCE(NULLIF(current_setting('app.current_admin', true), '')::boolean, false))"
    )
    op.execute('ALTER TABLE public."achievements" ENABLE ROW LEVEL SECURITY')
    op.execute(f'DROP POLICY IF EXISTS "{POLICY_NAME}" ON public."achievements"')
    op.execute(
        f'CREATE POLICY "{POLICY_NAME}" ON public."achievements" '
        f'AS PERMISSIVE FOR ALL TO {ALLY_APP_ROLE} '
        f'USING ({predicate}) WITH CHECK ({predicate})'
    )


def downgrade() -> None:
    if _ally_app_exists():
        op.execute(f'DROP POLICY IF EXISTS "{POLICY_NAME}" ON public."achievements"')
    op.drop_index("ix_achievements_founder_id", table_name="achievements")
    op.drop_table("achievements")
