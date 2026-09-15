"""add cognito identity mapping

Revision ID: 719a012becf1
Revises: e7d3f1a90c48
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "719a012becf1"
down_revision = "e7d3f1a90c48"
branch_labels = None
depends_on = None


ALLY_APP_ROLE = "ally_app"

LINK_SIGNATURE = (
    "public.link_cognito_founder("
    "character varying, character varying)"
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


def upgrade() -> None:
    op.add_column(
        "founders",
        sa.Column("cognito_sub", sa.String(length=64), nullable=True),
        schema="public",
    )

    op.create_unique_constraint(
        "uq_founders_cognito_sub",
        "founders",
        ["cognito_sub"],
        schema="public",
    )

    op.execute("""
    CREATE OR REPLACE FUNCTION public.link_cognito_founder(
        p_cognito_sub character varying,
        p_email character varying
    )
    RETURNS TABLE (
        founder_id integer,
        user_id uuid,
        linked boolean
    )
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path TO pg_catalog, public, pg_temp
    AS $function$
    DECLARE
        v_founder_id integer;
        v_user_id uuid;
        v_existing_sub character varying;
        v_request_sub text;
        v_request_email text;
        v_email_verified boolean;
        v_match_count integer;
    BEGIN

        /*
         * SECURITY BOUNDARY:
         * The backend may call this only after Cognito JWT verification.
         * It places the authenticated Cognito subject in a transaction-local
         * setting before calling this SECURITY DEFINER function.
         */
        v_request_sub :=
            NULLIF(
                current_setting(
                    'app.current_cognito_sub',
                    true
                ),
                ''
            );

        IF v_request_sub IS NULL THEN
            RAISE EXCEPTION
                'link_cognito_founder: missing authenticated Cognito subject';
        END IF;

        IF v_request_sub IS DISTINCT FROM p_cognito_sub THEN
            RAISE EXCEPTION
                'link_cognito_founder: authenticated Cognito subject mismatch';
        END IF;

        IF p_cognito_sub IS NULL
           OR btrim(p_cognito_sub) = ''
           OR length(p_cognito_sub) > 64 THEN
            RAISE EXCEPTION
                'link_cognito_founder: invalid Cognito subject';
        END IF;


        /*
         * Once linked, Cognito sub is authoritative.
         * Do not depend on email matching on future logins.
         */
        SELECT
            f.founder_id,
            f.user_id,
            f.cognito_sub
        INTO
            v_founder_id,
            v_user_id,
            v_existing_sub
        FROM public.founders AS f
        WHERE f.cognito_sub = p_cognito_sub
        LIMIT 1;

        IF v_founder_id IS NOT NULL THEN
            RETURN QUERY
            SELECT v_founder_id, v_user_id, false;

            RETURN;
        END IF;


        /*
         * Email is permitted only as the one-time migration bridge and only
         * when Cognito has verified that email address.
         */
        v_email_verified :=
            lower(
                COALESCE(
                    NULLIF(
                        current_setting(
                            'app.current_cognito_email_verified',
                            true
                        ),
                        ''
                    ),
                    'false'
                )
            ) = 'true';

        IF NOT v_email_verified THEN
            RAISE EXCEPTION
                'link_cognito_founder: verified email required for first link';
        END IF;

        v_request_email :=
            NULLIF(
                current_setting(
                    'app.current_cognito_email',
                    true
                ),
                ''
            );

        IF v_request_email IS NULL
           OR p_email IS NULL
           OR btrim(p_email) = '' THEN
            RAISE EXCEPTION
                'link_cognito_founder: email is required for first link';
        END IF;

        IF lower(btrim(v_request_email))
           IS DISTINCT FROM lower(btrim(p_email)) THEN
            RAISE EXCEPTION
                'link_cognito_founder: authenticated email mismatch';
        END IF;


        /*
         * Existing schema has a case-sensitive email uniqueness constraint.
         * Refuse to migrate if historical data contains two addresses that
         * differ only by case instead of guessing which founder is correct.
         */
        SELECT count(*)
        INTO v_match_count
        FROM public.founders AS f
        WHERE lower(f.email) = lower(btrim(p_email));

        IF v_match_count > 1 THEN
            RAISE EXCEPTION
                'link_cognito_founder: ambiguous founder email';
        END IF;

        IF v_match_count = 0 THEN
            RETURN;
        END IF;


        /*
         * Lock the founder row while performing the one-time identity bind.
         */
        SELECT
            f.founder_id,
            f.user_id,
            f.cognito_sub
        INTO
            v_founder_id,
            v_user_id,
            v_existing_sub
        FROM public.founders AS f
        WHERE lower(f.email) = lower(btrim(p_email))
        FOR UPDATE;

        IF v_existing_sub IS NOT NULL
           AND v_existing_sub IS DISTINCT FROM p_cognito_sub THEN
            RAISE EXCEPTION
                'link_cognito_founder: founder already linked to another Cognito identity';
        END IF;

        IF v_existing_sub IS NULL THEN
            UPDATE public.founders AS f
            SET cognito_sub = p_cognito_sub
            WHERE f.founder_id = v_founder_id;

            RETURN QUERY
            SELECT v_founder_id, v_user_id, true;
        ELSE
            RETURN QUERY
            SELECT v_founder_id, v_user_id, false;
        END IF;

    END;
    $function$;
    """)

    op.execute(
        f"REVOKE ALL PRIVILEGES ON FUNCTION {LINK_SIGNATURE} FROM PUBLIC"
    )

    if _ally_app_exists():
        op.execute(
            f"GRANT EXECUTE ON FUNCTION {LINK_SIGNATURE} TO {ALLY_APP_ROLE}"
        )
    else:
        print(
            f"WARNING [{revision}]: role {ALLY_APP_ROLE!r} absent -- "
            "skipping EXECUTE grant on Cognito identity linker."
        )


def downgrade() -> None:
    if _ally_app_exists():
        op.execute(
            f"REVOKE EXECUTE ON FUNCTION {LINK_SIGNATURE} FROM {ALLY_APP_ROLE}"
        )

    op.execute(
        f"DROP FUNCTION IF EXISTS {LINK_SIGNATURE}"
    )

    op.drop_constraint(
        "uq_founders_cognito_sub",
        "founders",
        type_="unique",
        schema="public",
    )

    op.drop_column(
        "founders",
        "cognito_sub",
        schema="public",
    )