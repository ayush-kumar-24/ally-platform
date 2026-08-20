"""add vision tables

Revision ID: a1c4e7f92d38
Revises: 4eae90a3e06b
Create Date: 2026-08-20 11:00:00.000000

Backs the "Your Vision" page. Two tables:
- vision_territories: one row per (founder, territory) -- the six fixed
  territory keys are validated in app.vision.service, not enforced by a DB
  CHECK constraint (same tradeoff as other founder-authored free-text
  tables in this schema).
- vision_summary: one row per founder (target/current/unit).

RLS: same guarded ally_founder_isolation pattern as f7a3d5b1ef52 (which
added founder_goals) and 4eae90a3e06b (achievements) -- see those
migrations' docstrings, and d91c6e4b72aa's, for why this is a no-op on
Supabase by design and what still needs adding there separately.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c4e7f92d38'
down_revision: Union[str, Sequence[str], None] = '4eae90a3e06b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


POLICY_NAME = "ally_founder_isolation"
ALLY_APP_ROLE = "ally_app"
TABLES = ("vision_territories", "vision_summary")


def _ally_app_exists() -> bool:
    """Duplicated per-migration on purpose -- see d91c6e4b72aa's docstring."""
    return bool(
        op.get_bind()
        .execute(text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": ALLY_APP_ROLE})
        .scalar()
    )


def _enable_rls(table: str) -> None:
    predicate = (
        "(founder_id = public.get_founder_id()) OR "
        "(COALESCE(NULLIF(current_setting('app.current_admin', true), '')::boolean, false))"
    )
    op.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'DROP POLICY IF EXISTS "{POLICY_NAME}" ON public."{table}"')
    op.execute(
        f'CREATE POLICY "{POLICY_NAME}" ON public."{table}" '
        f'AS PERMISSIVE FOR ALL TO {ALLY_APP_ROLE} '
        f'USING ({predicate}) WITH CHECK ({predicate})'
    )


def upgrade() -> None:
    op.create_table(
        "vision_territories",
        sa.Column("founder_id", sa.Integer(),
                  sa.ForeignKey("founders.founder_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("territory", sa.String(length=20), primary_key=True),
        sa.Column("statement", sa.Text(), nullable=False, server_default=""),
        sa.Column("tag1", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("tag2", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_vision_territories_founder_id", "vision_territories", ["founder_id"])

    op.create_table(
        "vision_summary",
        sa.Column("founder_id", sa.Integer(),
                  sa.ForeignKey("founders.founder_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("target", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("current", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("unit", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    if not _ally_app_exists():
        print(
            f"WARNING [{revision}]: role {ALLY_APP_ROLE!r} does not exist on this "
            "database -- SKIPPING the founder-isolation RLS policy for vision. "
            "EXPECTED on Supabase (native RLS handles this instead, but a policy "
            "for vision still needs adding there separately -- see module "
            "docstring). NOT expected on RDS."
        )
        return

    for table in TABLES:
        _enable_rls(table)


def downgrade() -> None:
    if _ally_app_exists():
        for table in TABLES:
            op.execute(f'DROP POLICY IF EXISTS "{POLICY_NAME}" ON public."{table}"')
    op.drop_table("vision_summary")
    op.drop_index("ix_vision_territories_founder_id", table_name="vision_territories")
    op.drop_table("vision_territories")
