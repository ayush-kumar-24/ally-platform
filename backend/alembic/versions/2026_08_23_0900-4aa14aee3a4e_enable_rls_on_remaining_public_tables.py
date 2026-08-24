"""enable RLS on the 30 tables the security advisor flagged as exposed

Revision ID: 4aa14aee3a4e
Revises: e2b5c8d47f63

Supabase's database linter (`rls_disabled_in_public`, ERROR level) flagged 30
public tables with no row-level security at all -- including founder_consents,
founder_dna_answers, founder_settings, credit_transactions and every table
added in the last two days of feature work (achievements, founder_goals,
vision_summary, vision_territories, framework_usage, calendar_connections).

Why this is a real gap and not noise: this app's own backend connects as the
`postgres` superuser (confirmed live), which bypasses RLS unconditionally --
enabling RLS here changes nothing for the FastAPI backend's own queries. What
it protects is Supabase's auto-generated PostgREST API, which authenticates as
`anon`/`authenticated` and IS subject to RLS. A table with RLS disabled is
readable and writable by anyone who can reach that API directly with a valid
(or, for `anon`-permitted tables, no) Supabase session -- entirely bypassing
this backend's own authorization.

d91c6e4b72aa ("enable founder RLS") already covers a large set of tables, but
every policy there is scoped `TO ally_app`, an RDS-only role that does not
exist on Supabase (see that file's docstring) -- so it no-ops here by design.
Several NEWER tables (founder_goals, achievements, vision_territories,
vision_summary, framework_usage) even tried the same ally_app-gated pattern in
their own creation migrations and hit the identical no-op for the same reason,
which is exactly how they ended up on this list.

This migration is deliberately NOT gated on ally_app: it writes plain
Postgres RLS (ENABLE ROW LEVEL SECURITY + CREATE POLICY ... TO public /
authenticated), which is valid syntax and enforces identically on ANY Postgres
target, RDS included. On RDS it simply sits alongside the existing ally_app
policies as a second permissive policy checking the same predicate --
permissive policies OR together, so this is additive, never a conflict.

Policy shape mirrors the ALREADY-LIVE native policies on `answers`, `sessions`
and `founder_reports` (`{table}_select_own`, `founder_id = get_founder_id()`,
role `public`) -- that convention already works correctly in production, so
this extends it rather than inventing a new one. `get_founder_id()` returns
NULL for a caller with no `app.current_founder_uuid` set (the anon case), and
`founder_id = NULL` is never true, so `public` and `authenticated` behave
identically here; `public` is used to match the existing tables exactly.

Deliberately SELECT-only, no INSERT/UPDATE/DELETE policies anywhere in this
migration. The frontend never talks to Supabase's PostgREST API for data --
VITE_SUPABASE_URL/ANON_KEY are used for Supabase Auth only (see DEPLOY.md);
every read and write goes through this FastAPI backend, which bypasses RLS
entirely as noted above. Granting write access through a surface nothing uses
today is pure unreviewed exposure with no offsetting benefit; the same
founder_reports table already ships SELECT-only for exactly this reason. If a
future feature needs direct-Supabase writes (Realtime, offline-first sync),
add that INSERT/UPDATE policy deliberately, with the access pattern it
actually needs, rather than pre-granting it here.

Three shapes, matched to what each table actually is:

  * FOUNDER_OWNED  -- founder_id (or, for credit_transactions, the
    confusingly-named user_id -- see d91c6e4b72aa's own comment on that
    column) scopes a row to one founder. SELECT-own only.
  * REFERENCE      -- current_problem_questions, founder_dna_questions: the
    question banks. No founder scoping; readable when active, matching the
    exact `is_active = true` policy shape already live on other reference
    tables in this project.
  * INTERNAL       -- admin_audit_log, broadcasts, feature_flags,
    model_task_routing, revoked_tokens: no founder column, no legitimate
    direct-client read today. RLS enabled with NO policy, which is a hard
    default-deny for anon/authenticated -- the backend (postgres) is
    unaffected. `broadcasts` in particular reads as built for direct
    Supabase Realtime later; deliberately left closed rather than guessed
    open, since that is a product decision for whoever builds that feature.

downgrade() drops exactly what upgrade() created and nothing else -- it does
not touch RLS state on any table this migration did not itself enable,
mirroring d91c6e4b72aa's own rule about never leaving a database less
protected than it found it.
"""

from alembic import op


revision = "4aa14aee3a4e"
down_revision = "e2b5c8d47f63"
branch_labels = None
depends_on = None


# table -> the column that scopes a row to one founder.
FOUNDER_OWNED: dict[str, str] = {
    "achievements": "founder_id",
    "broadcast_reads": "founder_id",
    "calendar_connections": "founder_id",
    "credit_transactions": "user_id",  # points at founders.founder_id -- see module docstring
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

REFERENCE_TABLES: tuple[str, ...] = (
    "current_problem_questions",
    "founder_dna_questions",
)

# No founder column, no direct-client read case today -- RLS on, no policy.
INTERNAL_TABLES: tuple[str, ...] = (
    "admin_audit_log",
    "broadcasts",
    "feature_flags",
    "model_task_routing",
    "revoked_tokens",
)


def _enable_rls(table: str) -> None:
    op.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')


def _disable_rls(table: str) -> None:
    op.execute(f'ALTER TABLE public."{table}" DISABLE ROW LEVEL SECURITY')


def _founder_select_policy(table: str, column: str) -> None:
    policy = f"{table}_select_own"
    _enable_rls(table)
    op.execute(f'DROP POLICY IF EXISTS "{policy}" ON public."{table}"')
    op.execute(
        f'CREATE POLICY "{policy}" ON public."{table}" '
        "AS PERMISSIVE FOR SELECT TO public "
        f'USING ("{column}" = get_founder_id())'
    )


def _reference_select_policy(table: str) -> None:
    policy = f"{table}_select_active"
    _enable_rls(table)
    op.execute(f'DROP POLICY IF EXISTS "{policy}" ON public."{table}"')
    op.execute(
        f'CREATE POLICY "{policy}" ON public."{table}" '
        "AS PERMISSIVE FOR SELECT TO public "
        "USING (is_active = true)"
    )


def upgrade() -> None:
    for table, column in FOUNDER_OWNED.items():
        _founder_select_policy(table, column)

    for table in REFERENCE_TABLES:
        _reference_select_policy(table)

    # No policy: RLS enabled alone is a full default-deny for every role
    # except a BYPASSRLS role (superuser) or the table owner.
    for table in INTERNAL_TABLES:
        _enable_rls(table)


def downgrade() -> None:
    for table in FOUNDER_OWNED:
        op.execute(f'DROP POLICY IF EXISTS "{table}_select_own" ON public."{table}"')
        _disable_rls(table)

    for table in REFERENCE_TABLES:
        op.execute(f'DROP POLICY IF EXISTS "{table}_select_active" ON public."{table}"')
        _disable_rls(table)

    for table in INTERNAL_TABLES:
        _disable_rls(table)
