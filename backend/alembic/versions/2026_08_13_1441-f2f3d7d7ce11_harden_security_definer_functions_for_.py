"""harden security definer functions for rls

Revision ID: f2f3d7d7ce11
Revises: bec1d5b06eac
"""

from alembic import op


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


def upgrade() -> None:
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

        op.execute(
            f"REVOKE ALL PRIVILEGES ON FUNCTION "
            f"{function_signature} FROM ally_app"
        )

    # Runtime application only needs this helper for RLS identity resolution.
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.get_founder_id() TO ally_app"
    )


def downgrade() -> None:
    # Remove explicit runtime grant first.
    op.execute(
        "REVOKE EXECUTE ON FUNCTION public.get_founder_id() FROM ally_app"
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