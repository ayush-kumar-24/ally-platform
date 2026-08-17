"""secure founder provisioning for rls

Revision ID: 7c4f0f1a9d2e
Revises: f2f3d7d7ce11
"""

from alembic import op


revision = "7c4f0f1a9d2e"
down_revision = "f2f3d7d7ce11"
branch_labels = None
depends_on = None


SIGNATURE = (
    "public.create_founder_on_signup("
    "uuid, character varying, character varying, "
    "character varying, character varying, "
    "character varying, text, integer)"
)


def upgrade() -> None:

    op.execute("""
    CREATE OR REPLACE FUNCTION public.create_founder_on_signup(
        p_user_id uuid,
        p_full_name character varying,
        p_email character varying,
        p_privacy_policy_version character varying,
        p_terms_version character varying,
        p_ip_address character varying,
        p_browser text DEFAULT NULL::text,
        p_signup_credits integer DEFAULT 0
    )
    RETURNS integer
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path TO pg_catalog, public, pg_temp
    AS $function$
    DECLARE
        v_founder_id INTEGER;
        v_request_user uuid;
    BEGIN

        /*
         * SECURITY BOUNDARY:
         * The UUID supplied to this SECURITY DEFINER function must be the
         * UUID attached to the authenticated request by the backend.
         */
        v_request_user :=
            NULLIF(
                current_setting(
                    'app.current_founder_uuid',
                    true
                ),
                ''
            )::uuid;

        IF v_request_user IS NULL THEN
            RAISE EXCEPTION
                'create_founder_on_signup: missing authenticated user context';
        END IF;

        IF v_request_user IS DISTINCT FROM p_user_id THEN
            RAISE EXCEPTION
                'create_founder_on_signup: authenticated user mismatch';
        END IF;


        /*
         * Idempotency protection.
         * A repeated /auth/session request should not create another founder.
         */
        SELECT founder_id
          INTO v_founder_id
          FROM public.founders
         WHERE user_id = p_user_id
         LIMIT 1;

        IF v_founder_id IS NOT NULL THEN
            RETURN v_founder_id;
        END IF;


        INSERT INTO public.founders (
            user_id,
            full_name,
            email,
            plan_type,
            onboarding_version,
            consent_version,
            data_retention_expires_at,
            credits_balance,
            monthly_credits,
            credits_expires_at
        )
        VALUES (
            p_user_id,
            p_full_name,
            p_email,
            'free',
            'v2.1-final',
            p_privacy_policy_version,
            NOW() + INTERVAL '2 years',
            p_signup_credits,
            p_signup_credits,
            NOW() + INTERVAL '30 days'
        )
        RETURNING founder_id
        INTO v_founder_id;


        INSERT INTO public.consents (
            founder_id,
            privacy_policy_version,
            terms_version,
            cookie_consent,
            analytics,
            marketing,
            functional,
            diagnosis_data_consent,
            ip_address,
            browser,
            consented_at
        )
        VALUES (
            v_founder_id,
            p_privacy_policy_version,
            p_terms_version,
            false,
            false,
            false,
            true,
            false,
            p_ip_address,
            p_browser,
            NOW()
        );


        INSERT INTO public.consent_history (
            founder_id,
            action,
            consent_type,
            previous_value,
            new_value,
            privacy_policy_version,
            ip_address,
            browser
        )
        VALUES (
            v_founder_id,
            'accepted',
            'terms_and_privacy',
            NULL,
            true,
            p_privacy_policy_version,
            p_ip_address,
            p_browser
        );


        INSERT INTO public.founder_context (
            founder_id
        )
        VALUES (
            v_founder_id
        );


        INSERT INTO public.audit_logs (
            founder_id,
            action,
            entity_type,
            entity_id,
            action_details,
            ip_address,
            browser
        )
        VALUES (
            v_founder_id,
            'profile_created',
            'founder',
            v_founder_id,
            jsonb_build_object(
                'email',
                p_email,
                'plan',
                'free',
                'signup_credits',
                p_signup_credits,
                'credits_expire_at',
                NOW() + INTERVAL '30 days'
            ),
            p_ip_address,
            p_browser
        );


        RETURN v_founder_id;

    EXCEPTION
        WHEN OTHERS THEN
            RAISE EXCEPTION
                'create_founder_on_signup failed: %',
                SQLERRM;
    END;
    $function$;
    """)

    # No default access.
    op.execute(
        f"REVOKE ALL PRIVILEGES ON FUNCTION {SIGNATURE} FROM PUBLIC"
    )

    # Only the application runtime may invoke founder provisioning.
    op.execute(
        f"GRANT EXECUTE ON FUNCTION {SIGNATURE} TO ally_app"
    )


def downgrade() -> None:

    op.execute(
        f"REVOKE EXECUTE ON FUNCTION {SIGNATURE} FROM ally_app"
    )

    op.execute(
        f"GRANT EXECUTE ON FUNCTION {SIGNATURE} TO PUBLIC"
    )