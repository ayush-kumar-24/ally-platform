"""grant signup credits when a founder is provisioned

The plan catalog has always declared Free's one-time grant (signup_credits=120),
but nothing ever applied it. create_founder_on_signup inserted the founder row
and never touched the credit columns, so every founder created by a real OAuth
login started at credits_balance = 0. The only rows with a balance were seeded
by hand, which is why this stayed invisible: the seeded founders looked correct
and the real ones were never exercised, because PLAN_ENFORCEMENT_ENABLED is off
and nothing reads the balance while it is.

The moment enforcement is switched on, check_chat_allowed reads that balance and
every genuinely-new founder is refused on their first message. So this is the
prerequisite for that flag, not a tidy-up.

The amount is a PARAMETER, not a literal in the function body. catalog.py is
explicit that nothing should hard-code a tier's limits, and a number baked into
a stored procedure is the least visible place to duplicate one -- it would drift
from the catalog silently and there would be no test that could notice. The
caller passes PLANS[FREE].signup_credits, so the catalog stays the only source
of truth and this function stays the single atomic provisioning path.

The grant lands in bonus_credits, matching how the existing free founder is
shaped (balance 130 / bonus 130 / monthly 0): monthly_credits is the recurring
allowance a paid tier renews into, bonus is where one-time grants live. Free's
monthly_credits is 0 by design -- a renewing free tier is unbounded.

Deliberately NOT written to credit_transactions: that table is admin-scoped
(admin_id NOT NULL, balance_before/after modelled on manual adjustment) and its
only rows are admin QA. A signup grant is not an admin action; the audit_logs
entry this function already writes is extended to record it instead.

Also backfills founders who were created by the buggy path -- scoped to rows
that have never been granted anything (all three credit columns zero), so it
cannot disturb a founder whose balance was deliberately set or already spent.

Revision ID: a7c3f9e21d84
Revises: c1e4a6b8d0f3
Create Date: 2026-08-05 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'a7c3f9e21d84'
down_revision: Union[str, Sequence[str], None] = 'c1e4a6b8d0f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_OLD_SIGNATURE = (
    "create_founder_on_signup(uuid, character varying, character varying, "
    "character varying, character varying, character varying, text)"
)

_NEW_SIGNATURE = (
    "create_founder_on_signup(uuid, character varying, character varying, "
    "character varying, character varying, character varying, text, integer)"
)

# Body shared by both directions; only the credit columns and the audit detail
# differ, so the diff between them is the whole change and nothing else.
_FUNCTION = """
CREATE FUNCTION public.create_founder_on_signup(
    p_user_id uuid,
    p_full_name character varying,
    p_email character varying,
    p_privacy_policy_version character varying,
    p_terms_version character varying,
    p_ip_address character varying,
    p_browser text DEFAULT NULL::text{extra_params}
)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
AS $function$
DECLARE
    v_founder_id INTEGER;
BEGIN
    -- 1. Create founder profile
    INSERT INTO founders (
        user_id, full_name, email, plan_type,
        onboarding_version, consent_version,
        data_retention_expires_at{credit_columns}
    )
    VALUES (
        p_user_id, p_full_name, p_email, 'free',
        'v2.1-final', p_privacy_policy_version,
        NOW() + INTERVAL '2 years'{credit_values}
    )
    RETURNING founder_id INTO v_founder_id;

    -- 2. Create consent record
    INSERT INTO consents (
        founder_id, privacy_policy_version, terms_version,
        cookie_consent, analytics, marketing, functional,
        diagnosis_data_consent, ip_address, browser, consented_at
    )
    VALUES (
        v_founder_id, p_privacy_policy_version, p_terms_version,
        false, false, false, true,
        false, p_ip_address, p_browser, NOW()
    );

    -- 3. Log consent given in consent_history
    INSERT INTO consent_history (
        founder_id, action, consent_type, previous_value,
        new_value, privacy_policy_version, ip_address, browser
    )
    VALUES (
        v_founder_id, 'accepted', 'terms_and_privacy', NULL,
        true, p_privacy_policy_version, p_ip_address, p_browser
    );

    -- 4. Create empty founder_context record
    INSERT INTO founder_context (founder_id)
    VALUES (v_founder_id);

    -- 5. Write audit log
    INSERT INTO audit_logs (
        founder_id, action, entity_type, entity_id,
        action_details, ip_address, browser
    )
    VALUES (
        v_founder_id, 'profile_created', 'founder', v_founder_id,
        jsonb_build_object('email', p_email, 'plan', 'free'{audit_detail}),
        p_ip_address, p_browser
    );

    RETURN v_founder_id;

EXCEPTION WHEN OTHERS THEN
    RAISE EXCEPTION 'create_founder_on_signup failed: %', SQLERRM;
END;
$function$
"""


def upgrade() -> None:
    # Adding a parameter creates an overload rather than replacing, and an
    # overload whose extra argument has a DEFAULT makes every 7-argument call
    # ambiguous. Drop first so exactly one signature exists.
    op.execute(f"DROP FUNCTION IF EXISTS public.{_OLD_SIGNATURE}")
    op.execute(_FUNCTION.format(
        extra_params=",\n    p_signup_credits integer DEFAULT 0",
        credit_columns=",\n        credits_balance, bonus_credits",
        credit_values=",\n        p_signup_credits, p_signup_credits",
        audit_detail=", 'signup_credits', p_signup_credits",
    ))

    # Backfill the founders provisioned before this fix. Restricted to rows that
    # have never been granted anything, so a deliberately-zeroed or fully-spent
    # balance is left alone.
    op.execute("""
        UPDATE founders
           SET credits_balance = 120,
               bonus_credits = 120
         WHERE plan_type = 'free'
           AND COALESCE(credits_balance, 0) = 0
           AND COALESCE(bonus_credits, 0) = 0
           AND COALESCE(monthly_credits, 0) = 0
    """)


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS public.{_NEW_SIGNATURE}")
    op.execute(_FUNCTION.format(
        extra_params="",
        credit_columns="",
        credit_values="",
        audit_detail="",
    ))
    # The backfilled credits are deliberately NOT reversed: by the time anyone
    # downgrades, a founder may have spent them, and clawing back a balance is
    # worse than leaving a grant in place.
