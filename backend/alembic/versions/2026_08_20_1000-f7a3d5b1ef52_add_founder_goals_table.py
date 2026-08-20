"""add founder_goals table

Revision ID: f7a3d5b1ef52
Revises: f2a86d41c7b9
Create Date: 2026-08-20 10:00:00.000000

Backs the standalone "Goals" page (longer-horizon founder/business/life
outcomes, free from the start) -- deliberately NOT the same table as
`planning_goals` (app.planning's nested Plan -> Goal -> Task hierarchy,
gated behind the paid Plan Your Day feature). See
app/founder_goals/models.py's docstring for the full reasoning; this
migration just needs the two names to stay visibly distinct in the schema
the way they already are in code.

RLS: this repo's `ally_founder_isolation` policy set (see d91c6e4b72aa) is
scoped `TO ally_app`, a role that exists on the RDS target but not on
Supabase -- Supabase enforces the same founder isolation through its own
native RLS instead. This migration adds `founder_goals` to that same guarded
policy pattern for RDS; on Supabase the guard makes it a no-op, and a native
Supabase RLS policy for `founder_goals` still needs to be added separately
(via the Supabase dashboard/SQL editor) since Alembic has no reach into that
mechanism. Flagging that here rather than silently leaving the table
unprotected on the production target.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7a3d5b1ef52'
down_revision: Union[str, Sequence[str], None] = 'f2a86d41c7b9'
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
    """Create founder_goals (see module docstring for why this isn't planning_goals)."""
    op.create_table(
        "founder_goals",
        sa.Column("goal_id", sa.String(length=64), primary_key=True),
        sa.Column("founder_id", sa.Integer(),
                  sa.ForeignKey("founders.founder_id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("subtitle", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_founder_goals_founder_id", "founder_goals", ["founder_id"])

    if not _ally_app_exists():
        print(
            f"WARNING [{revision}]: role {ALLY_APP_ROLE!r} does not exist on this "
            "database -- SKIPPING the founder-isolation RLS policy for founder_goals. "
            "EXPECTED on Supabase (native RLS handles this instead, but a policy for "
            "founder_goals still needs adding there separately -- see module docstring). "
            "NOT expected on RDS."
        )
        return

    predicate = (
        "(founder_id = public.get_founder_id()) OR "
        "(COALESCE(NULLIF(current_setting('app.current_admin', true), '')::boolean, false))"
    )
    op.execute('ALTER TABLE public."founder_goals" ENABLE ROW LEVEL SECURITY')
    op.execute(f'DROP POLICY IF EXISTS "{POLICY_NAME}" ON public."founder_goals"')
    op.execute(
        f'CREATE POLICY "{POLICY_NAME}" ON public."founder_goals" '
        f'AS PERMISSIVE FOR ALL TO {ALLY_APP_ROLE} '
        f'USING ({predicate}) WITH CHECK ({predicate})'
    )


def downgrade() -> None:
    if _ally_app_exists():
        op.execute(f'DROP POLICY IF EXISTS "{POLICY_NAME}" ON public."founder_goals"')
    op.drop_index("ix_founder_goals_founder_id", table_name="founder_goals")
    op.drop_table("founder_goals")
