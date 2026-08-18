"""harden security definer functions for rls

Revision ID: f2f3d7d7ce11
Revises: bec1d5b06eac

`ally_app` is INFRASTRUCTURE, not something migrations create -- confirmed
with the team: it is provisioned outside Alembic on the RDS target, and no
CREATE ROLE for it exists (or should exist) anywhere in this history.

But it is an RDS-only construct. Verified live against the Supabase database
the app currently runs on: `ally_app` does not exist there, and it should not
-- Supabase already enforces founder isolation through its OWN native RLS
(95 RLS-enabled tables, 86 policies, keyed to the anon/authenticated roles
Supabase issues), whereas this branch's scheme keys to `ally_app` plus
`app.current_founder_uuid`. Two parallel designs for one job; only the RDS one
needs this role.

So the ally_app statements below are guarded on the role actually existing
rather than assumed. On RDS they apply exactly as written. On Supabase they
skip with a loud warning instead of aborting `alembic upgrade head` on
`REVOKE ... FROM ally_app` -- which is what happened, and it blocks every
deploy, since the Dockerfile runs the upgrade on container start.

The search_path hardening and the REVOKE-from-PUBLIC are NOT guarded: they
are role-independent and matter on every target.
"""

from alembic import op
from sqlalchemy import text


revision = "f2f3d7d7ce11"
down_revision = "bec1d5b06eac"
branch_labels = None
depends_on = None


SECURITY_DEFINER_FUNCTIONS = [
    "public.check_and_update_token_usage(integer, integer, character varying)",
    "public.complete_onboarding(integer, character varying, text, text, character varying, character varying, integer, jsonb, text, text, text, character varying, jsonb, character varying, jsonb, boolean, character varying)",
    "public.create_founder_on_signup(uuid, character varying, character varying, character varying, character varying, character varying, text, integer)",
    "public.create_next_month_partitions()",
    "public.get_founder_id()",
    "public.lock_conversation(integer, integer, character varying)",
    "public.request_account_deletion(integer, character varying)",
    "public.send_notification(integer, character varying, character varying, character varying, text, character varying, jsonb)",
    "public.start_conversation(integer, character varying, character varying)",
    "public.withdraw_consent(integer, character varying, character varying, text)",
]


ALLY_APP_ROLE = "ally_app"


def ally_app_exists() -> bool:
    """Whether the `ally_app` runtime role is present on THIS target.

    See the module docstring: present on RDS (provisioned as infrastructure),
    absent on Supabase (which uses its own native RLS instead). Callers skip
    the ally_app-specific grants when absent rather than aborting.
    """
    return bool(
        op.get_bind()
        .execute(text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
                 {"role": ALLY_APP_ROLE})
        .scalar()
    )


def upgrade() -> None:
    has_ally_app = ally_app_exists()
    if not has_ally_app:
        # Loud, not silent: skipping a SECURITY hardening step must never look
        # like it succeeded. Surfaces in the alembic output and in App Runner's
        # deploy logs.
        print(
            f"WARNING [{revision}]: role {ALLY_APP_ROLE!r} does not exist on "
            "this database -- skipping its function grants/revokes. This is "
            "EXPECTED on Supabase (own native RLS) and NOT expected on RDS, "
            "where the role is provisioned as infrastructure. If this is RDS, "
            "provision the role and re-run."
        )

    # SECURITY DEFINER functions run with their owner's privileges.
    # Lock down search_path and remove default PUBLIC execution.
    for function_signature in SECURITY_DEFINER_FUNCTIONS:
        op.execute(
            f"ALTER FUNCTION {function_signature} "
            "SET search_path TO pg_catalog, public, pg_temp"
        )

        op.execute(
            f"REVOKE ALL PRIVILEGES ON FUNCTION "
            f"{function_signature} FROM PUBLIC"
        )

        if has_ally_app:
            op.execute(
                f"REVOKE ALL PRIVILEGES ON FUNCTION "
                f"{function_signature} FROM {ALLY_APP_ROLE}"
            )

    # Runtime application only needs this helper for RLS identity resolution.
    if has_ally_app:
        op.execute(
            "GRANT EXECUTE ON FUNCTION public.get_founder_id() "
            f"TO {ALLY_APP_ROLE}"
        )


def downgrade() -> None:
    # Remove explicit runtime grant first -- same role guard as upgrade().
    if ally_app_exists():
        op.execute(
            "REVOKE EXECUTE ON FUNCTION public.get_founder_id() "
            f"FROM {ALLY_APP_ROLE}"
        )

    # Restore the previous effective behavior:
    # default search_path + PUBLIC EXECUTE.
    for function_signature in SECURITY_DEFINER_FUNCTIONS:
        op.execute(
            f"ALTER FUNCTION {function_signature} RESET search_path"
        )

        op.execute(
            f"GRANT EXECUTE ON FUNCTION "
            f"{function_signature} TO PUBLIC"
        )