"""add framework_usage table

Revision ID: b2d5f8a03c17
Revises: a1c4e7f92d38
Create Date: 2026-08-20 11:30:00.000000

Backs the "last used" date and personal note on the Frameworks page.
framework_id is a plain string, not a foreign key -- the framework content
itself stays static on the frontend (data/frameworks.js); see
app/framework_usage/models.py's docstring.

RLS: same guarded ally_founder_isolation pattern as f7a3d5b1ef52
(founder_goals), 4eae90a3e06b (achievements) and a1c4e7f92d38 (vision) --
see those migrations' docstrings, and d91c6e4b72aa's, for why this is a
no-op on Supabase by design and what still needs adding there separately.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2d5f8a03c17'
down_revision: Union[str, Sequence[str], None] = 'a1c4e7f92d38'
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
        "framework_usage",
        sa.Column("founder_id", sa.Integer(),
                  sa.ForeignKey("founders.founder_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("framework_id", sa.String(length=64), primary_key=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_framework_usage_founder_id", "framework_usage", ["founder_id"])

    if not _ally_app_exists():
        print(
            f"WARNING [{revision}]: role {ALLY_APP_ROLE!r} does not exist on this "
            "database -- SKIPPING the founder-isolation RLS policy for "
            "framework_usage. EXPECTED on Supabase (native RLS handles this "
            "instead, but a policy for framework_usage still needs adding "
            "there separately -- see module docstring). NOT expected on RDS."
        )
        return

    predicate = (
        "(founder_id = public.get_founder_id()) OR "
        "(COALESCE(NULLIF(current_setting('app.current_admin', true), '')::boolean, false))"
    )
    op.execute('ALTER TABLE public."framework_usage" ENABLE ROW LEVEL SECURITY')
    op.execute(f'DROP POLICY IF EXISTS "{POLICY_NAME}" ON public."framework_usage"')
    op.execute(
        f'CREATE POLICY "{POLICY_NAME}" ON public."framework_usage" '
        f'AS PERMISSIVE FOR ALL TO {ALLY_APP_ROLE} '
        f'USING ({predicate}) WITH CHECK ({predicate})'
    )


def downgrade() -> None:
    if _ally_app_exists():
        op.execute(f'DROP POLICY IF EXISTS "{POLICY_NAME}" ON public."framework_usage"')
    op.drop_index("ix_framework_usage_founder_id", table_name="framework_usage")
    op.drop_table("framework_usage")
