"""enable founder row level security

Revision ID: d91c6e4b72aa
Revises: 7c4f0f1a9d2e

Every policy here is scoped `TO ally_app`, so this whole migration is
meaningless without that role -- and `CREATE POLICY ... TO ally_app` errors
outright when it is missing. See f2f3d7d7ce11's docstring for why it is
missing on Supabase by design (Supabase enforces the same isolation through
its own native RLS: 95 RLS-enabled tables and 86 policies already live there,
keyed to anon/authenticated rather than to ally_app).

Guarded as a whole, not statement-by-statement: enabling RLS on a table while
skipping its policy would deny all access to that table for any non-BYPASSRLS
role, which is strictly worse than leaving the table as it was. So when
ally_app is absent this migration is a no-op with a loud warning, and the RDS
target -- where the role exists -- gets the full policy set unchanged.
"""

from alembic import op
from sqlalchemy import text


revision = "d91c6e4b72aa"
down_revision = "7c4f0f1a9d2e"
branch_labels = None
depends_on = None


# Tables whose tenant ownership is stored directly in founder_id.
FOUNDER_TABLES = [
    "admin_notes",
    "analytics_events",
    "answers",
    "audit_logs",
    "broadcast_reads",
    "consent_history",
    "consents",
    "conversations",
    "cookie_preferences",
    "daily_actions",
    "daily_token_usage",
    "data_deletion_requests",
    "detected_root_causes",
    "discovery_calls",
    "feature_flag_overrides",
    "file_uploads",
    "founder_consents",
    "founder_context",
    "founder_dimension_profile",
    "founder_feedback",
    "founder_memory",
    "founder_memory_events",
    "founder_reports",
    "founder_settings",
    "founder_visual_choices",
    "founders",
    "internal_intelligence_reports",
    "llm_call_log",
    "messages",
    "notifications",
    "payments",
    "plan_call_usage",
    "planning_goals",
    "planning_plans",
    "planning_reminders",
    "planning_tasks",
    "privacy_requests",
    "rag_retrieval_log",
    "report_shares",
    "sessions",
    "stage_assessments",
    "subscriptions",
    "suggestion_feedback",
    "suggestions",
    "unbilled_usage",
    "user_token_usage",
    "webhook_logs",
]


POLICY_NAME = "ally_founder_isolation"

ALLY_APP_ROLE = "ally_app"


def _ally_app_exists() -> bool:
    """Whether the RDS-only `ally_app` runtime role exists on this target.
    Duplicated per-migration on purpose -- see the note in 7c4f0f1a9d2e."""
    return bool(
        op.get_bind()
        .execute(text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
                 {"role": ALLY_APP_ROLE})
        .scalar()
    )


def _admin_expression() -> str:
    return (
        "COALESCE("
        "NULLIF(current_setting('app.current_admin', true), '')::boolean, "
        "false"
        ")"
    )


def _predicate(column: str) -> str:
    return (
        f"({column} = public.get_founder_id()) "
        f"OR ({_admin_expression()})"
    )


def _enable_policy(table: str, column: str) -> None:
    predicate = _predicate(column)

    op.execute(
        f'ALTER TABLE public."{table}" '
        "ENABLE ROW LEVEL SECURITY"
    )

    op.execute(
        f'DROP POLICY IF EXISTS "{POLICY_NAME}" '
        f'ON public."{table}"'
    )

    op.execute(
        f'CREATE POLICY "{POLICY_NAME}" '
        f'ON public."{table}" '
        "AS PERMISSIVE "
        "FOR ALL "
        f"TO {ALLY_APP_ROLE} "
        f"USING ({predicate}) "
        f"WITH CHECK ({predicate})"
    )


def upgrade() -> None:
    if not _ally_app_exists():
        print(
            f"WARNING [{revision}]: role {ALLY_APP_ROLE!r} does not exist on "
            "this database -- SKIPPING the entire founder-isolation RLS policy "
            f"set ({len(FOUNDER_TABLES) + 1} tables). Every policy here is "
            f"scoped TO {ALLY_APP_ROLE}, so it cannot be created without it. "
            "EXPECTED on Supabase, which enforces the same isolation via its "
            "own native RLS. NOT expected on RDS -- if this is RDS, provision "
            "the role as infrastructure and re-run, or founder isolation is "
            "NOT being enforced at the database layer."
        )
        return

    for table in FOUNDER_TABLES:
        _enable_policy(table, "founder_id")

    # Despite its historical column name, this FK points to
    # founders.founder_id, not to founders.user_id.
    _enable_policy("credit_transactions", "user_id")


def downgrade() -> None:
    # Mirror upgrade()'s guard, and for a sharper reason than symmetry: the
    # DISABLE ROW LEVEL SECURITY below does not distinguish RLS that THIS
    # migration turned on from RLS that was already there. On Supabase --
    # where upgrade() is a no-op and 95 tables carry pre-existing native RLS
    # with 86 policies -- running this ungated would tear down founder
    # isolation this migration never created. A downgrade must not be able to
    # leave a database less protected than it found it.
    if not _ally_app_exists():
        print(
            f"WARNING [{revision}]: role {ALLY_APP_ROLE!r} absent -- skipping "
            "downgrade. upgrade() was a no-op here, so there is nothing of "
            "ours to undo, and disabling RLS would strip protection this "
            "migration did not add."
        )
        return

    tables = FOUNDER_TABLES + ["credit_transactions"]

    for table in reversed(tables):
        op.execute(
            f'DROP POLICY IF EXISTS "{POLICY_NAME}" '
            f'ON public."{table}"'
        )

        op.execute(
            f'ALTER TABLE public."{table}" '
            "DISABLE ROW LEVEL SECURITY"
        )