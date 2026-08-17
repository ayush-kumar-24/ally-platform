"""enable founder row level security

Revision ID: d91c6e4b72aa
Revises: 7c4f0f1a9d2e
"""

from alembic import op


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
        "TO ally_app "
        f"USING ({predicate}) "
        f"WITH CHECK ({predicate})"
    )


def upgrade() -> None:
    for table in FOUNDER_TABLES:
        _enable_policy(table, "founder_id")

    # Despite its historical column name, this FK points to
    # founders.founder_id, not to founders.user_id.
    _enable_policy("credit_transactions", "user_id")


def downgrade() -> None:
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