"""fix onboarding write-path; emotional_state multi-select

Revision ID: b960b83ab79e
Revises: 5cbf7c8fea1e
Create Date: 2026-07-22 15:05:26.295508

Three coordinated changes to the onboarding write path, all on objects created
by the team's Supabase migrations:

1. consents.updated_at -- add the column its set_updated_at trigger expects
   (any UPDATE to consents failed without it).
2. founders.emotional_state -- convert single varchar to a jsonb array so the
   "how are you feeling" question can be multi-select, restricted by CHECK to
   the eight allowed feelings.
3. complete_onboarding() -- fix the stage->stage_id column bug and accept the
   jsonb emotional_state. Its signature changes, so it is dropped and recreated.

Verified end-to-end in a rolled-back transaction before applying.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b960b83ab79e"
down_revision: Union[str, Sequence[str], None] = "5cbf7c8fea1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ALLOWED_FEELINGS = (
    '["excited","inspired","confident","curious",'
    '"overwhelmed","stuck","determined","hopeful"]'
)

UPGRADE_SQL = f"""
ALTER TABLE public.consents
    ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

ALTER TABLE public.founders DROP CONSTRAINT IF EXISTS founders_emotional_state_check;

ALTER TABLE public.founders
    ALTER COLUMN emotional_state TYPE jsonb
    USING (CASE WHEN emotional_state IS NULL THEN NULL
                ELSE to_jsonb(ARRAY[emotional_state]) END);

ALTER TABLE public.founders
    ALTER COLUMN emotional_state SET DEFAULT '[]'::jsonb;

ALTER TABLE public.founders ADD CONSTRAINT founders_emotional_state_check
    CHECK (
        emotional_state IS NULL
        OR (
            jsonb_typeof(emotional_state) = 'array'
            AND emotional_state <@ '{ALLOWED_FEELINGS}'::jsonb
        )
    );

DROP FUNCTION IF EXISTS public.complete_onboarding(
    integer, character varying, text, text, character varying, character varying,
    integer, jsonb, text, text, text, character varying, jsonb, character varying,
    character varying, boolean, character varying);

CREATE OR REPLACE FUNCTION public.complete_onboarding(
    p_founder_id integer,
    p_stage character varying,
    p_building_summary text,
    p_problem_statement text,
    p_customer_segment character varying,
    p_industry character varying,
    p_industry_mapped_id integer,
    p_current_challenges jsonb,
    p_goal_90_day text,
    p_vision_1_year text,
    p_founder_motivation text,
    p_working_relationship character varying,
    p_support_preferences jsonb,
    p_experience_level character varying,
    p_emotional_state jsonb,
    p_diagnosis_data_consent boolean,
    p_ip_address character varying
) RETURNS boolean
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
DECLARE
    v_stage_id INTEGER;
BEGIN
    SELECT stage_id INTO v_stage_id
    FROM founder_stages
    WHERE lower(stage_name) = lower(btrim(p_stage))
       OR lower(onboarding_label) = lower(btrim(p_stage))
    ORDER BY stage_order
    LIMIT 1;

    IF v_stage_id IS NULL AND p_stage ~ '^[0-9]+$' THEN
        v_stage_id := p_stage::int;
    END IF;

    IF v_stage_id IS NULL THEN
        RAISE EXCEPTION 'complete_onboarding: unknown stage %', p_stage;
    END IF;

    UPDATE founders SET
        stage_id                = v_stage_id,
        building_summary        = p_building_summary,
        problem_statement       = p_problem_statement,
        customer_segment        = p_customer_segment,
        industry                = p_industry,
        industry_mapped_id      = p_industry_mapped_id,
        current_challenges      = p_current_challenges,
        goal_90_day             = p_goal_90_day,
        vision_1_year           = p_vision_1_year,
        founder_motivation      = p_founder_motivation,
        working_relationship    = p_working_relationship,
        support_preferences     = p_support_preferences,
        experience_level        = p_experience_level,
        emotional_state         = p_emotional_state,
        profile_completed       = true,
        onboarding_completed_at = NOW()
    WHERE founder_id = p_founder_id;

    UPDATE consents SET
        diagnosis_data_consent = p_diagnosis_data_consent,
        consented_at = NOW()
    WHERE founder_id = p_founder_id;

    IF p_diagnosis_data_consent = true THEN
        INSERT INTO consent_history (
            founder_id, action, consent_type,
            previous_value, new_value,
            privacy_policy_version, ip_address
        )
        SELECT
            p_founder_id, 'accepted', 'diagnosis_data_consent',
            false, true,
            privacy_policy_version, p_ip_address
        FROM consents WHERE founder_id = p_founder_id;
    END IF;

    INSERT INTO subscriptions (founder_id, plan_type, status, started_at)
    VALUES (p_founder_id, 'free', 'active', NOW())
    ON CONFLICT DO NOTHING;

    INSERT INTO audit_logs (
        founder_id, action, entity_type, entity_id, action_details, ip_address
    )
    VALUES (
        p_founder_id, 'onboarding_completed', 'founder', p_founder_id,
        jsonb_build_object('stage', p_stage, 'industry', p_industry, 'diagnosis_consent', p_diagnosis_data_consent),
        p_ip_address
    );

    RETURN true;

EXCEPTION WHEN OTHERS THEN
    RAISE EXCEPTION 'complete_onboarding failed: %', SQLERRM;
END;
$function$;
"""

# Reverses the schema-level changes. The recreated function is dropped rather
# than restored to its previous (buggy) body -- pull that from Supabase migration
# history if a true rollback is ever needed. Safe today: founders has 0 rows.
DOWNGRADE_SQL = """
DROP FUNCTION IF EXISTS public.complete_onboarding(
    integer, character varying, text, text, character varying, character varying,
    integer, jsonb, text, text, text, character varying, jsonb, character varying,
    jsonb, boolean, character varying);

ALTER TABLE public.founders DROP CONSTRAINT IF EXISTS founders_emotional_state_check;

ALTER TABLE public.founders
    ALTER COLUMN emotional_state DROP DEFAULT;

ALTER TABLE public.founders
    ALTER COLUMN emotional_state TYPE character varying
    USING (emotional_state->>0);

ALTER TABLE public.founders ADD CONSTRAINT founders_emotional_state_check
    CHECK (emotional_state IS NULL OR emotional_state::text = ANY (ARRAY[
        'excited','inspired','confident','curious',
        'overwhelmed','stuck','determined','hopeful']));

ALTER TABLE public.consents DROP COLUMN IF EXISTS updated_at;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
