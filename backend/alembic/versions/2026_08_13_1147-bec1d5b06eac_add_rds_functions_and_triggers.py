"""add_rds_functions_and_triggers

Revision ID: bec1d5b06eac
Revises: 905bddfc6aff
Create Date: 2026-08-13 11:47:22.985099

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "bec1d5b06eac"
down_revision: Union[str, Sequence[str], None] = "905bddfc6aff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_trigger_if_missing(table_name: str, trigger_name: str, ddl: str) -> None:
    """Create a trigger only when that table does not already have it."""
    bind = op.get_bind()
    exists = bind.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM pg_trigger t
                JOIN pg_class c ON c.oid = t.tgrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relname = :table_name
                  AND t.tgname = :trigger_name
                  AND NOT t.tgisinternal
            )
            """
        ),
        {"table_name": table_name, "trigger_name": trigger_name},
    ).scalar()
    if not exists:
        op.execute(ddl)


def upgrade() -> None:
    """Add the reviewed RDS functions and triggers missing from revision 905bddfc6aff."""
    # ---------------------------------------------------------
    # 4. Functions (18) -- exact live Supabase definitions,
    #    ONE correction: get_founder_id() rewritten for RDS
    #    (session variable instead of auth.uid())
    # ---------------------------------------------------------

    # update_updated_at_column
    op.execute("""CREATE OR REPLACE FUNCTION public.update_updated_at_column()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$function$
""")

    # set_dpdp_computed_fields
    op.execute("""CREATE OR REPLACE FUNCTION public.set_dpdp_computed_fields()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    IF TG_TABLE_NAME = 'privacy_requests' THEN
        NEW.due_by = NEW.requested_at + INTERVAL '30 days';
    END IF;
    IF TG_TABLE_NAME = 'data_deletion_requests' THEN
        NEW.grace_period_ends_at = NEW.requested_at + INTERVAL '30 days';
    END IF;
    RETURN NEW;
END;
$function$
""")

    # log_stage_assessment_on_change
    op.execute("""CREATE OR REPLACE FUNCTION public.log_stage_assessment_on_change()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  IF (NEW.stage_id IS NOT NULL) AND (OLD.stage_id IS DISTINCT FROM NEW.stage_id) THEN

    UPDATE stage_assessments
    SET is_current = FALSE
    WHERE founder_id = NEW.founder_id AND is_current = TRUE;

    INSERT INTO stage_assessments (founder_id, stage_id, is_current, assessed_at, assessment_basis)
    VALUES (
      NEW.founder_id,
      NEW.stage_id,
      TRUE,
      now(),
      CASE WHEN OLD.stage_id IS NULL THEN 'Initial stage set during onboarding' ELSE 'Stage updated by founder' END
    );

  END IF;
  RETURN NEW;
END;
$function$
""")

    # increment_message_count
    op.execute("""CREATE OR REPLACE FUNCTION public.increment_message_count()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    UPDATE conversations SET
        message_count   = message_count + 1,
        last_message_at = NOW()
    WHERE conversation_id = NEW.conversation_id;
    RETURN NEW;
END;
$function$
""")

    # check_severity_range
    op.execute("""CREATE OR REPLACE FUNCTION public.check_severity_range()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    IF NEW.severity_min > NEW.severity_max THEN
        RAISE EXCEPTION 'severity_min (%) cannot be greater than severity_max (%) for problem %',
            NEW.severity_min, NEW.severity_max, NEW.problem_code;
    END IF;
    RETURN NEW;
END;
$function$
""")

    # check_pillar_weightage_sum
    op.execute("""CREATE OR REPLACE FUNCTION public.check_pillar_weightage_sum()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_total DECIMAL(5,2);
BEGIN
    SELECT SUM(pillar_weightage) INTO v_total
    FROM readiness_pillars;

    IF (SELECT COUNT(*) FROM readiness_pillars) = 6 THEN
        IF ABS(v_total - 100.00) > 0.01 THEN
            RAISE EXCEPTION 'Pillar weightages must sum to 100. Current sum: %', v_total;
        END IF;
    END IF;
    RETURN NEW;
END;
$function$
""")

    # check_confidence_weight
    op.execute("""CREATE OR REPLACE FUNCTION public.check_confidence_weight()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    IF NEW.confidence_weight < 0.0 OR NEW.confidence_weight > 1.0 THEN
        RAISE EXCEPTION 'confidence_weight (%) must be between 0.0 and 1.0 for root cause %',
            NEW.confidence_weight, NEW.root_cause_code;
    END IF;
    RETURN NEW;
END;
$function$
""")

    # check_scoring_weights_sum
    op.execute("""CREATE OR REPLACE FUNCTION public.check_scoring_weights_sum()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_total DECIMAL(8,4);
BEGIN
    SELECT SUM(rule_value) INTO v_total
    FROM scoring_rules
    WHERE rule_code IN (
        'WEIGHT_CATEGORY_RISK',
        'WEIGHT_CONFIRMATION_STATUS',
        'WEIGHT_STAGE_PROBABILITY',
        'WEIGHT_INDUSTRY_PROBABILITY'
    );

    IF v_total IS NOT NULL AND ABS(v_total - 1.0000) > 0.0001 THEN
        RAISE EXCEPTION 'Scoring weight factors must sum to 1.0. Current sum: %', v_total;
    END IF;
    RETURN NEW;
END;
$function$
""")

    # check_and_update_token_usage
    op.execute("""CREATE OR REPLACE FUNCTION public.check_and_update_token_usage(p_founder_id integer, p_tokens_to_add integer, p_plan_type character varying DEFAULT 'free'::character varying)
 RETURNS boolean
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
DECLARE
    v_limit     INTEGER;
    v_current   INTEGER;
    v_today     DATE := CURRENT_DATE;
BEGIN
    v_limit := CASE p_plan_type
        WHEN 'free'       THEN 10000
        WHEN 'starter'    THEN 50000
        WHEN 'pro'        THEN 200000
        WHEN 'enterprise' THEN 1000000
        ELSE 10000
    END;

    INSERT INTO user_token_usage (
        founder_id, usage_date, tokens_used, tokens_limit,
        plan_type, limit_reached, reset_at
    )
    VALUES (
        p_founder_id, v_today, p_tokens_to_add, v_limit,
        p_plan_type, false,
        (v_today + 1)::TIMESTAMPTZ
    )
    ON CONFLICT (founder_id, usage_date) DO UPDATE SET
        tokens_used = user_token_usage.tokens_used + p_tokens_to_add;

    SELECT tokens_used INTO v_current
    FROM user_token_usage
    WHERE founder_id = p_founder_id AND usage_date = v_today;

    IF v_current > v_limit THEN
        UPDATE user_token_usage SET
            limit_reached    = true,
            limit_reached_at = NOW()
        WHERE founder_id = p_founder_id AND usage_date = v_today;
        RETURN false;
    END IF;

    RETURN true;
END;
$function$
""")

    # complete_onboarding
    op.execute("""CREATE OR REPLACE FUNCTION public.complete_onboarding(p_founder_id integer, p_stage character varying, p_building_summary text, p_problem_statement text, p_customer_segment character varying, p_industry character varying, p_industry_mapped_id integer, p_current_challenges jsonb, p_goal_90_day text, p_vision_1_year text, p_founder_motivation text, p_working_relationship character varying, p_support_preferences jsonb, p_experience_level character varying, p_emotional_state jsonb, p_diagnosis_data_consent boolean, p_ip_address character varying)
 RETURNS boolean
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
$function$
""")

    # create_founder_on_signup
    op.execute("""CREATE OR REPLACE FUNCTION public.create_founder_on_signup(p_user_id uuid, p_full_name character varying, p_email character varying, p_privacy_policy_version character varying, p_terms_version character varying, p_ip_address character varying, p_browser text DEFAULT NULL::text, p_signup_credits integer DEFAULT 0)
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
        credits_balance, monthly_credits, credits_expires_at
    )
    VALUES (
        p_user_id, p_full_name, p_email, 'free',
        'v2.1-final', p_privacy_policy_version,
        NOW() + INTERVAL '2 years',
        p_signup_credits, p_signup_credits, NOW() + INTERVAL '30 days'
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
                           'signup_credits', p_signup_credits, 'credits_expire_at', (NOW() + INTERVAL '30 days')),
        p_ip_address, p_browser
    );

    RETURN v_founder_id;

EXCEPTION WHEN OTHERS THEN
    RAISE EXCEPTION 'create_founder_on_signup failed: %', SQLERRM;
END;
$function$
""")

    # create_next_month_partitions -- RDS-safe guard.
    # The reconciled RDS currently has regular (non-partitioned) parent tables.
    # Preserve the function for compatibility, but only create child partitions
    # after all three parents have explicitly been migrated to partitioned tables.
    op.execute("""CREATE OR REPLACE FUNCTION public.create_next_month_partitions()
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
DECLARE
    v_next_month  DATE := DATE_TRUNC('month', NOW()) + INTERVAL '1 month';
    v_month_after DATE := v_next_month + INTERVAL '1 month';
    v_suffix      TEXT := TO_CHAR(v_next_month, 'YYYY_MM');
    v_partitioned_parent_count INTEGER;
BEGIN
    SELECT COUNT(*)
      INTO v_partitioned_parent_count
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relname IN ('messages', 'analytics_events', 'audit_logs')
      AND c.relkind = 'p';

    IF v_partitioned_parent_count <> 3 THEN
        RAISE NOTICE 'Skipping partition creation: messages, analytics_events, and audit_logs are not all partitioned tables on this RDS.';
        RETURN;
    END IF;

    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS messages_%s PARTITION OF messages FOR VALUES FROM (%L) TO (%L)',
        v_suffix, v_next_month, v_month_after
    );
    EXECUTE format('ALTER TABLE messages_%s ENABLE ROW LEVEL SECURITY', v_suffix);

    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS analytics_events_%s PARTITION OF analytics_events FOR VALUES FROM (%L) TO (%L)',
        v_suffix, v_next_month, v_month_after
    );
    EXECUTE format('ALTER TABLE analytics_events_%s ENABLE ROW LEVEL SECURITY', v_suffix);

    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS audit_logs_%s PARTITION OF audit_logs FOR VALUES FROM (%L) TO (%L)',
        v_suffix, v_next_month, v_month_after
    );
    EXECUTE format('ALTER TABLE audit_logs_%s ENABLE ROW LEVEL SECURITY', v_suffix);

    RAISE NOTICE 'Partitions created for %', v_suffix;
END;
$function$
""")

    # get_founder_id -- CORRECTED for RDS (was: auth.uid(), Supabase-only)
    op.execute("""CREATE OR REPLACE FUNCTION public.get_founder_id()
 RETURNS integer
 LANGUAGE sql
 STABLE SECURITY DEFINER
AS $function$
  SELECT founder_id
  FROM founders
  WHERE user_id = NULLIF(current_setting('app.current_founder_uuid', true), '')::uuid
  LIMIT 1;
$function$
""")

    # lock_conversation
    op.execute("""CREATE OR REPLACE FUNCTION public.lock_conversation(p_conversation_id integer, p_founder_id integer, p_reason character varying DEFAULT 'report_generated'::character varying)
 RETURNS boolean
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
BEGIN
    UPDATE conversations SET
        is_locked   = true,
        locked_at   = NOW(),
        lock_reason = p_reason,
        status      = 'completed'
    WHERE conversation_id = p_conversation_id
      AND founder_id = p_founder_id
      AND is_locked = false;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Conversation not found or already locked';
    END IF;

    UPDATE founders SET
        diagnosis_used      = true,
        diagnosis_locked_at = NOW()
    WHERE founder_id = p_founder_id;

    INSERT INTO audit_logs (
        founder_id, action, entity_type, entity_id,
        action_details, ip_address
    )
    VALUES (
        p_founder_id, 'report_generated', 'conversation',
        p_conversation_id,
        jsonb_build_object('lock_reason', p_reason),
        '0.0.0.0'
    );

    RETURN true;
END;
$function$
""")

    # request_account_deletion
    op.execute("""CREATE OR REPLACE FUNCTION public.request_account_deletion(p_founder_id integer, p_ip_address character varying)
 RETURNS boolean
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
BEGIN
    IF EXISTS (
        SELECT 1 FROM data_deletion_requests
        WHERE founder_id = p_founder_id
          AND status NOT IN ('completed', 'cancelled')
    ) THEN
        RAISE EXCEPTION 'A deletion request is already in progress for this founder';
    END IF;

    INSERT INTO data_deletion_requests (
        founder_id, requested_at, otp_verified, status
    )
    VALUES (
        p_founder_id, NOW(), false, 'pending_otp'
    );

    UPDATE founders SET
        deletion_requested_at   = NOW(),
        deletion_scheduled_at   = NOW() + INTERVAL '30 days'
    WHERE founder_id = p_founder_id;

    INSERT INTO audit_logs (
        founder_id, action, entity_type, entity_id,
        action_details, ip_address
    )
    VALUES (
        p_founder_id, 'deletion_requested', 'founder', p_founder_id,
        jsonb_build_object('grace_period_days', 30),
        p_ip_address
    );

    RETURN true;
END;
$function$
""")

    # send_notification
    op.execute("""CREATE OR REPLACE FUNCTION public.send_notification(p_founder_id integer, p_type character varying, p_channel character varying, p_title character varying, p_body text, p_action_url character varying DEFAULT NULL::character varying, p_metadata jsonb DEFAULT '{}'::jsonb)
 RETURNS integer
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
DECLARE
    v_notification_id INTEGER;
    v_prefs           JSONB;
    v_should_send     BOOLEAN := true;
BEGIN
    SELECT notification_preferences INTO v_prefs
    FROM founders WHERE founder_id = p_founder_id;

    IF p_channel = 'email' AND p_type = 'report_ready' THEN
        v_should_send := COALESCE((v_prefs->>'email_report_ready')::boolean, true);
    ELSIF p_channel = 'in_app' THEN
        v_should_send := COALESCE((v_prefs->>'in_app_all')::boolean, true);
    END IF;

    IF NOT v_should_send THEN
        RETURN NULL;
    END IF;

    INSERT INTO notifications (
        founder_id, type, channel, title, body,
        action_url, metadata, sent_at
    )
    VALUES (
        p_founder_id, p_type, p_channel, p_title, p_body,
        p_action_url, p_metadata, NOW()
    )
    RETURNING notification_id INTO v_notification_id;

    RETURN v_notification_id;
END;
$function$
""")

    # start_conversation
    op.execute("""CREATE OR REPLACE FUNCTION public.start_conversation(p_founder_id integer, p_type character varying, p_title character varying DEFAULT NULL::character varying)
 RETURNS integer
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
DECLARE
    v_conversation_id INTEGER;
BEGIN
    IF p_type = 'diagnosis' THEN
        IF EXISTS (
            SELECT 1 FROM conversations
            WHERE founder_id = p_founder_id
              AND conversation_type = 'diagnosis'
              AND is_locked = false
        ) THEN
            RAISE EXCEPTION 'An active diagnosis session already exists for this founder';
        END IF;
    END IF;

    INSERT INTO conversations (
        founder_id, conversation_type, title, status
    )
    VALUES (
        p_founder_id, p_type,
        COALESCE(p_title, 'Conversation ' || TO_CHAR(NOW(), 'DD Mon YYYY')),
        'active'
    )
    RETURNING conversation_id INTO v_conversation_id;

    INSERT INTO audit_logs (
        founder_id, action, entity_type, entity_id,
        action_details, ip_address
    )
    VALUES (
        p_founder_id, 'conversation_started', 'conversation',
        v_conversation_id,
        jsonb_build_object('type', p_type),
        '0.0.0.0'
    );

    RETURN v_conversation_id;

EXCEPTION WHEN OTHERS THEN
    RAISE EXCEPTION 'start_conversation failed: %', SQLERRM;
END;
$function$
""")

    # withdraw_consent
    op.execute("""CREATE OR REPLACE FUNCTION public.withdraw_consent(p_founder_id integer, p_consent_type character varying, p_ip_address character varying, p_browser text DEFAULT NULL::text)
 RETURNS boolean
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
DECLARE
    v_old_value         BOOLEAN;
    v_policy_version    VARCHAR(20);
BEGIN
    SELECT
        CASE p_consent_type
            WHEN 'analytics'               THEN analytics
            WHEN 'marketing'               THEN marketing
            WHEN 'diagnosis_data_consent'  THEN diagnosis_data_consent
            WHEN 'cookie_consent'          THEN cookie_consent
        END,
        privacy_policy_version
    INTO v_old_value, v_policy_version
    FROM consents
    WHERE founder_id = p_founder_id;

    EXECUTE format(
        'UPDATE consents SET %I = false, consented_at = NOW() WHERE founder_id = $1',
        p_consent_type
    ) USING p_founder_id;

    INSERT INTO consent_history (
        founder_id, action, consent_type,
        previous_value, new_value,
        privacy_policy_version, ip_address, browser
    )
    VALUES (
        p_founder_id, 'withdrawn', p_consent_type,
        v_old_value, false,
        v_policy_version, p_ip_address, p_browser
    );

    INSERT INTO audit_logs (
        founder_id, action, entity_type, entity_id,
        action_details, ip_address, browser
    )
    VALUES (
        p_founder_id, 'consent_withdrawn', 'consent', p_founder_id,
        jsonb_build_object('consent_type', p_consent_type),
        p_ip_address, p_browser
    );

    RETURN true;
END;
$function$
""")
    # ---------------------------------------------------------
    # 5. Triggers (duplicate-safe)
    # ---------------------------------------------------------
    _create_trigger_if_missing(
        "admin_notes",
        "set_updated_at",
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON admin_notes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "agent_interpretations",
        "set_updated_at",
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON agent_interpretations FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "archetypes",
        "trg_archetypes_updated_at",
        "CREATE TRIGGER trg_archetypes_updated_at BEFORE UPDATE ON archetypes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "behaviour_patterns",
        "set_updated_at",
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON behaviour_patterns FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "blind_spots",
        "set_updated_at",
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON blind_spots FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "consents",
        "set_updated_at",
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON consents FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "conversations",
        "set_updated_at",
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON conversations FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "cookie_preferences",
        "set_updated_at",
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON cookie_preferences FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "daily_actions",
        "trg_daily_actions_updated_at",
        "CREATE TRIGGER trg_daily_actions_updated_at BEFORE UPDATE ON daily_actions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "data_deletion_requests",
        "set_deletion_grace_period",
        "CREATE TRIGGER set_deletion_grace_period BEFORE INSERT ON data_deletion_requests FOR EACH ROW EXECUTE FUNCTION set_dpdp_computed_fields()",
    )
    _create_trigger_if_missing(
        "discovery_calls",
        "set_updated_at",
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON discovery_calls FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "founder_context",
        "set_updated_at",
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON founder_context FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "founder_reports",
        "trg_founder_reports_updated_at",
        "CREATE TRIGGER trg_founder_reports_updated_at BEFORE UPDATE ON founder_reports FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "founder_stages",
        "set_updated_at",
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON founder_stages FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "founders",
        "set_updated_at",
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON founders FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "founders",
        "trg_founders_stage_change",
        "CREATE TRIGGER trg_founders_stage_change AFTER UPDATE OF stage_id ON founders FOR EACH ROW EXECUTE FUNCTION log_stage_assessment_on_change()",
    )
    _create_trigger_if_missing(
        "frameworks",
        "set_updated_at",
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON frameworks FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "industries",
        "set_updated_at",
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON industries FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "internal_intelligence_reports",
        "trg_internal_reports_updated_at",
        "CREATE TRIGGER trg_internal_reports_updated_at BEFORE UPDATE ON internal_intelligence_reports FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "interventions",
        "set_updated_at",
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON interventions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "messages",
        "after_message_insert",
        "CREATE TRIGGER after_message_insert AFTER INSERT ON messages FOR EACH ROW EXECUTE FUNCTION increment_message_count()",
    )
    _create_trigger_if_missing(
        "privacy_requests",
        "set_privacy_request_due_by",
        "CREATE TRIGGER set_privacy_request_due_by BEFORE INSERT ON privacy_requests FOR EACH ROW EXECUTE FUNCTION set_dpdp_computed_fields()",
    )
    _create_trigger_if_missing(
        "problems",
        "set_updated_at",
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON problems FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "problems",
        "validate_severity_range",
        "CREATE TRIGGER validate_severity_range BEFORE INSERT OR UPDATE ON problems FOR EACH ROW EXECUTE FUNCTION check_severity_range()",
    )
    _create_trigger_if_missing(
        "prompt_library",
        "trg_prompt_library_updated_at",
        "CREATE TRIGGER trg_prompt_library_updated_at BEFORE UPDATE ON prompt_library FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "rag_documents",
        "set_updated_at",
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON rag_documents FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "readiness_pillars",
        "set_updated_at",
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON readiness_pillars FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "readiness_pillars",
        "validate_pillar_weightage_sum",
        "CREATE TRIGGER validate_pillar_weightage_sum AFTER INSERT OR UPDATE ON readiness_pillars FOR EACH ROW EXECUTE FUNCTION check_pillar_weightage_sum()",
    )
    _create_trigger_if_missing(
        "root_causes",
        "set_updated_at",
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON root_causes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "root_causes",
        "validate_confidence_weight",
        "CREATE TRIGGER validate_confidence_weight BEFORE INSERT OR UPDATE ON root_causes FOR EACH ROW EXECUTE FUNCTION check_confidence_weight()",
    )
    _create_trigger_if_missing(
        "scoring_rules",
        "set_updated_at",
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON scoring_rules FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "scoring_rules",
        "validate_scoring_weights",
        "CREATE TRIGGER validate_scoring_weights AFTER INSERT OR UPDATE ON scoring_rules FOR EACH ROW EXECUTE FUNCTION check_scoring_weights_sum()",
    )
    _create_trigger_if_missing(
        "sessions",
        "trg_sessions_updated_at",
        "CREATE TRIGGER trg_sessions_updated_at BEFORE UPDATE ON sessions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "stage_diagnosis_logic",
        "trg_stage_diagnosis_logic_updated_at",
        "CREATE TRIGGER trg_stage_diagnosis_logic_updated_at BEFORE UPDATE ON stage_diagnosis_logic FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "subscriptions",
        "set_updated_at",
        "CREATE TRIGGER set_updated_at BEFORE UPDATE ON subscriptions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )
    _create_trigger_if_missing(
        "visual_question_bank",
        "trg_visual_question_bank_updated_at",
        "CREATE TRIGGER trg_visual_question_bank_updated_at BEFORE UPDATE ON visual_question_bank FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()",
    )


def downgrade() -> None:
    """Remove triggers/functions introduced by this revision without deleting the 3 functions that predated it."""
    # Drop triggers introduced by this revision.
    trigger_drops = [
        ("messages", "after_message_insert"),
        ("admin_notes", "set_updated_at"),
        ("agent_interpretations", "set_updated_at"),
        ("archetypes", "trg_archetypes_updated_at"),
        ("behaviour_patterns", "set_updated_at"),
        ("blind_spots", "set_updated_at"),
        ("consents", "set_updated_at"),
        ("conversations", "set_updated_at"),
        ("cookie_preferences", "set_updated_at"),
        ("daily_actions", "trg_daily_actions_updated_at"),
        ("data_deletion_requests", "set_deletion_grace_period"),
        ("discovery_calls", "set_updated_at"),
        ("founder_context", "set_updated_at"),
        ("founder_reports", "trg_founder_reports_updated_at"),
        ("founder_stages", "set_updated_at"),
        ("founders", "set_updated_at"),
        ("founders", "trg_founders_stage_change"),
        ("frameworks", "set_updated_at"),
        ("industries", "set_updated_at"),
        ("internal_intelligence_reports", "trg_internal_reports_updated_at"),
        ("interventions", "set_updated_at"),
        ("privacy_requests", "set_privacy_request_due_by"),
        ("problems", "set_updated_at"),
        ("problems", "validate_severity_range"),
        ("prompt_library", "trg_prompt_library_updated_at"),
        ("rag_documents", "set_updated_at"),
        ("readiness_pillars", "set_updated_at"),
        ("readiness_pillars", "validate_pillar_weightage_sum"),
        ("root_causes", "set_updated_at"),
        ("root_causes", "validate_confidence_weight"),
        ("scoring_rules", "set_updated_at"),
        ("scoring_rules", "validate_scoring_weights"),
        ("sessions", "trg_sessions_updated_at"),
        ("stage_diagnosis_logic", "trg_stage_diagnosis_logic_updated_at"),
        ("subscriptions", "set_updated_at"),
        ("visual_question_bank", "trg_visual_question_bank_updated_at"),
    ]
    for table_name, trigger_name in trigger_drops:
        op.execute(f'DROP TRIGGER IF EXISTS "{trigger_name}" ON public."{table_name}"')

    # These 15 functions were absent before this revision on the reconciled RDS.
    op.execute("DROP FUNCTION IF EXISTS public.check_and_update_token_usage(integer, integer, character varying)")
    op.execute("DROP FUNCTION IF EXISTS public.check_confidence_weight()")
    op.execute("DROP FUNCTION IF EXISTS public.check_pillar_weightage_sum()")
    op.execute("DROP FUNCTION IF EXISTS public.check_scoring_weights_sum()")
    op.execute("DROP FUNCTION IF EXISTS public.check_severity_range()")
    op.execute("DROP FUNCTION IF EXISTS public.get_founder_id()")
    op.execute("DROP FUNCTION IF EXISTS public.increment_message_count()")
    op.execute("DROP FUNCTION IF EXISTS public.lock_conversation(integer, integer, character varying)")
    op.execute("DROP FUNCTION IF EXISTS public.log_stage_assessment_on_change()")
    op.execute("DROP FUNCTION IF EXISTS public.request_account_deletion(integer, character varying)")
    op.execute("DROP FUNCTION IF EXISTS public.send_notification(integer, character varying, character varying, character varying, text, character varying, jsonb)")
    op.execute("DROP FUNCTION IF EXISTS public.set_dpdp_computed_fields()")
    op.execute("DROP FUNCTION IF EXISTS public.start_conversation(integer, character varying, character varying)")
    op.execute("DROP FUNCTION IF EXISTS public.update_updated_at_column()")
    op.execute("DROP FUNCTION IF EXISTS public.withdraw_consent(integer, character varying, character varying, text)")

    # complete_onboarding, create_founder_on_signup, and create_next_month_partitions
    # existed before this revision, so this downgrade intentionally leaves them in place.