"""expire the trial credit grant 30 days after signup

The testing phase gives each founder a one-month allowance that lapses and does
not come back -- continuing means moving to a paid plan. Nothing implemented
that: credits_expires_at was NULL for every founder, so the grant was permanent.

The expiry engine already exists and is correct (app/credits/expiry.py settles
lazily on read, inside the balance lock, so a job that failed to run cannot cause
credits to outlive their date). Two things stopped it firing.

1. Nobody ever set credits_expires_at.

2. The grant landed in the WRONG BUCKET. settle() expires only `monthly`:

       expiry_due = expires_at is not None and now >= expires_at and monthly > 0
       state = replace(state, monthly=0)

   `bonus` is never expired -- deliberately, it is the bucket for grants that
   should outlive a period. The signup grant was written there, so stamping a
   date on it would have changed nothing and looked like the engine was broken.

So the grant moves to `monthly` with an expiry and NO renewal_date, which is
exactly "an allowance that lapses once and never returns":

    monthly_credits          = the grant      (the bucket that can expire)
    credits_expires_at       = signup + 30d   (when it lapses)
    credits_renewal_date     = NULL           (settle() only renews if this is set)
    monthly_credit_allowance = 0              (nothing to re-grant if it ever were)

30 days from each founder's own signup, not a fixed cohort end date: someone who
joins on day 20 of the testing phase still gets their full month.

credits_balance is denormalised (monthly + bonus, written as :total by the credit
repository), so it is kept in step here rather than left to drift.

Backfills the founders provisioned before this, scoped to Free accounts that hold
an unexpiring grant in the wrong bucket. Paid tiers are untouched: their monthly
allowance is renewed, not expired-and-abandoned, and rewriting their buckets here
would silently cancel that.

Revision ID: c4a71fe38b52
Revises: b8e2d4f60a19
Create Date: 2026-08-06 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'c4a71fe38b52'
down_revision: Union[str, Sequence[str], None] = 'b8e2d4f60a19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SIGNATURE = (
    "create_founder_on_signup(uuid, character varying, character varying, "
    "character varying, character varying, character varying, text, integer)"
)

_FUNCTION = """
CREATE FUNCTION public.create_founder_on_signup(
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
AS $function$
DECLARE
    v_founder_id INTEGER;
BEGIN
    INSERT INTO founders (
        user_id, full_name, email, plan_type,
        onboarding_version, consent_version,
        data_retention_expires_at,
        credits_balance{credit_columns}
    )
    VALUES (
        p_user_id, p_full_name, p_email, 'free',
        'v2.1-final', p_privacy_policy_version,
        NOW() + INTERVAL '2 years',
        p_signup_credits{credit_values}
    )
    RETURNING founder_id INTO v_founder_id;

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

    INSERT INTO consent_history (
        founder_id, action, consent_type, previous_value,
        new_value, privacy_policy_version, ip_address, browser
    )
    VALUES (
        v_founder_id, 'accepted', 'terms_and_privacy', NULL,
        true, p_privacy_policy_version, p_ip_address, p_browser
    );

    INSERT INTO founder_context (founder_id)
    VALUES (v_founder_id);

    INSERT INTO audit_logs (
        founder_id, action, entity_type, entity_id,
        action_details, ip_address, browser
    )
    VALUES (
        v_founder_id, 'profile_created', 'founder', v_founder_id,
        jsonb_build_object('email', p_email, 'plan', 'free',
                           'signup_credits', p_signup_credits{audit_detail}),
        p_ip_address, p_browser
    );

    RETURN v_founder_id;

EXCEPTION WHEN OTHERS THEN
    RAISE EXCEPTION 'create_founder_on_signup failed: %', SQLERRM;
END;
$function$
"""


def upgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS public.{_SIGNATURE}")
    op.execute(_FUNCTION.format(
        credit_columns=", monthly_credits, credits_expires_at",
        credit_values=", p_signup_credits, NOW() + INTERVAL '30 days'",
        audit_detail=", 'credits_expire_at', (NOW() + INTERVAL '30 days')",
    ))

    # Move existing Free grants out of `bonus` (which never expires) into
    # `monthly`, and date them 30 days from that founder's own signup -- so a
    # tester who joined three days ago still gets 27 days, rather than everyone
    # being reset to a fresh 30 from today.
    op.execute("""
        UPDATE founders
           SET monthly_credits = COALESCE(bonus_credits, 0) + COALESCE(monthly_credits, 0),
               bonus_credits = 0,
               credits_expires_at = created_at + INTERVAL '30 days',
               credits_renewal_date = NULL,
               monthly_credit_allowance = 0,
               credits_balance = COALESCE(bonus_credits, 0) + COALESCE(monthly_credits, 0)
         WHERE plan_type = 'free'
           AND COALESCE(bonus_credits, 0) > 0
           AND credits_expires_at IS NULL
    """)


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS public.{_SIGNATURE}")
    op.execute(_FUNCTION.format(
        credit_columns=", bonus_credits",
        credit_values=", p_signup_credits",
        audit_detail="",
    ))
    # Put Free grants back in the non-expiring bucket and clear the date.
    # Restoring the expiry would be worse than dropping it: on the old code path
    # nothing settles `bonus`, so a stale date would sit there doing nothing and
    # read as though expiry were still in force.
    op.execute("""
        UPDATE founders
           SET bonus_credits = COALESCE(monthly_credits, 0) + COALESCE(bonus_credits, 0),
               monthly_credits = 0,
               credits_expires_at = NULL,
               credits_balance = COALESCE(monthly_credits, 0) + COALESCE(bonus_credits, 0)
         WHERE plan_type = 'free'
           AND credits_expires_at IS NOT NULL
    """)
