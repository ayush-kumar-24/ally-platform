"""Preserve ally_app runtime access after RLS hardening.

Revision ID: 8f6c2a1d9b7e
Revises: 4aa14aee3a4e

Production RDS migrations are executed by the schema-owner/migration role,
while the FastAPI runtime connects as the least-privileged `ally_app` role.

Revision 4aa14aee3a4e enables RLS on additional tables. Its public SELECT
policies protect direct-client reads, but `ally_app` also needs its existing
founder-scoped read/write access for backend operations.

This migration adds separate, additive policies for `ally_app` without
removing or weakening the public/Supabase-facing RLS policies created by the
previous revision.

On targets where `ally_app` does not exist (for example Supabase), this
migration is intentionally a no-op.
"""

from alembic import op
from sqlalchemy import text


revision = "8f6c2a1d9b7e"
down_revision = "4aa14aee3a4e"
branch_labels = None
depends_on = None


ALLY_APP_ROLE = "ally_app"

FOUNDER_POLICY = "ally_runtime_founder_access_v2"
INTERNAL_POLICY = "ally_runtime_internal_access_v2"


# table -> column that identifies the owning founder.
FOUNDER_OWNED = {
    "achievements": "founder_id",
    "broadcast_reads": "founder_id",
    "calendar_connections": "founder_id",
    "credit_transactions": "user_id",
    "current_problem_answers": "founder_id",
    "daily_token_usage": "founder_id",
    "feature_flag_overrides": "founder_id",
    "founder_consents": "founder_id",
    "founder_dna_answers": "founder_id",
    "founder_goals": "founder_id",
    "founder_settings": "founder_id",
    "framework_usage": "founder_id",
    "llm_call_log": "founder_id",
    "plan_call_usage": "founder_id",
    "planning_goals": "founder_id",
    "planning_plans": "founder_id",
    "planning_reminders": "founder_id",
    "planning_tasks": "founder_id",
    "suggestion_feedback": "founder_id",
    "suggestions": "founder_id",
    "unbilled_usage": "founder_id",
    "vision_summary": "founder_id",
    "vision_territories": "founder_id",
}


# These tables are backend-internal rather than founder-owned.
# Revision 4aa enables RLS with no public policy, which is correct for
# direct clients. ally_app still needs its pre-existing backend access.
INTERNAL_TABLES = (
    "admin_audit_log",
    "broadcasts",
    "feature_flags",
    "model_task_routing",
    "revoked_tokens",
)


def _ally_app_exists() -> bool:
    return bool(
        op.get_bind()
        .execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
            {"role": ALLY_APP_ROLE},
        )
        .scalar()
    )


def _admin_expression() -> str:
    return (
        "COALESCE("
        "NULLIF(current_setting('app.current_admin', true), '')::boolean, "
        "false"
        ")"
    )


def _founder_predicate(column: str) -> str:
    return (
        f'("{column}" = public.get_founder_id()) '
        f"OR ({_admin_expression()})"
    )


def upgrade() -> None:
    if not _ally_app_exists():
        print(
            f"WARNING [{revision}]: role {ALLY_APP_ROLE!r} does not exist; "
            "skipping RDS runtime policies."
        )
        return

    # Keep founder-owned backend operations tenant-isolated.
    # These policies are additive and do not replace the public SELECT
    # policies created by revision 4aa14aee3a4e.
    for table, column in FOUNDER_OWNED.items():
        predicate = _founder_predicate(column)

        op.execute(
            f'DROP POLICY IF EXISTS "{FOUNDER_POLICY}" '
            f'ON public."{table}"'
        )

        op.execute(
            f'CREATE POLICY "{FOUNDER_POLICY}" '
            f'ON public."{table}" '
            "AS PERMISSIVE "
            "FOR ALL "
            f"TO {ALLY_APP_ROLE} "
            f"USING ({predicate}) "
            f"WITH CHECK ({predicate})"
        )

    # calendar_connections is created by the privileged migration role.
    # Explicitly give the runtime role the DML privileges needed by the
    # Calendar feature. RLS above still restricts rows to the current founder.
    op.execute(
        'GRANT SELECT, INSERT, UPDATE, DELETE '
        'ON TABLE public."calendar_connections" '
        f"TO {ALLY_APP_ROLE}"
    )

    # Keep direct clients locked out of internal tables while restoring the
    # backend role's pre-RLS access.
    for table in INTERNAL_TABLES:
        op.execute(
            f'DROP POLICY IF EXISTS "{INTERNAL_POLICY}" '
            f'ON public."{table}"'
        )

        op.execute(
            f'CREATE POLICY "{INTERNAL_POLICY}" '
            f'ON public."{table}" '
            "AS PERMISSIVE "
            "FOR ALL "
            f"TO {ALLY_APP_ROLE} "
            "USING (true) "
            "WITH CHECK (true)"
        )


def downgrade() -> None:
    if not _ally_app_exists():
        return

    for table in INTERNAL_TABLES:
        op.execute(
            f'DROP POLICY IF EXISTS "{INTERNAL_POLICY}" '
            f'ON public."{table}"'
        )

    for table in FOUNDER_OWNED:
        op.execute(
            f'DROP POLICY IF EXISTS "{FOUNDER_POLICY}" '
            f'ON public."{table}"'
        )
