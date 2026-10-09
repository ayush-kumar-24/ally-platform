"""Hand-written descriptions for the schema documents.

Only 2 of 104 tables and 3 of 1,185 columns carry a COMMENT in the database,
so nothing machine-readable says what any of this is FOR. Types, keys and
relationships come out of the database exactly; meaning has to be written, and
this is where it lives. Both documents read from here, so a purpose written
once is correct in both.

A table whose purpose is unknown gets "" rather than a guess. The renderer
prints "-- not yet described --" for those, which is honest and shows up as a
gap to close instead of reading as documentation.

If these ever move into the database as real COMMENT ON statements, delete
this file and let the extractor pick them up -- a description that lives in
the schema cannot drift from it.
"""

TABLES: dict[str, str] = {
    # ---- Part A: pre-filled intelligence -------------------------------
    "founder_stages": "The eight lifecycle stages, in order, each with its entry and exit criteria, typical operational problems and psychological challenges, and the question budget a diagnosis at that stage is allowed to spend.",
    "readiness_pillars": "The six scoring dimensions of the Business Health Score. Weightages sum to 100 and are the weights for that score.",
    "problems": "The pain-point library. Each row is one problem a founder can have, categorised and embedded for semantic retrieval.",
    "problem_stage_mapping": "Which problems are plausible at which stage. Keeps a stage-0 founder from being matched to a scaling problem.",
    "root_causes": "The root-cause library: what sits underneath a problem, with a confidence weight and an embedding.",
    "root_cause_weights": "Stage-adjusted probability multipliers. The same root cause is more or less likely depending on the founder's stage, and this is where that is expressed.",
    "questions": "The diagnosis question bank. One row per question, carrying its pillar, stage group, priority, distress tag, and the six scope columns that decide which founders may be asked it.",
    "question_tags": "Tag vocabulary for categorising questions.",
    "question_tag_mapping": "Many-to-many link between questions and tags.",
    "question_industry_mapping": "Links a question to an industry and stage. A question with no row here is universal. `applicability_type` separates a defining question for an industry from one that is merely relevant.",
    "behaviour_patterns": "Founder behaviour and communication patterns, embedded, used to characterise how someone is operating rather than what they are doing.",
    "blind_spots": "Blind-spot patterns -- the things founders systematically cannot see about their own business.",
    "industries": "The thirty industry verticals, each with diagnostic weights and benchmarks.",
    "industry_stage_thresholds": "Revenue thresholds (INR) per stage per industry. What counts as early traction in textiles is not what counts in SaaS.",
    "agent_interpretations": "Maps a founder's own statement to the probe worth asking and the root cause it may indicate.",
    "scoring_rules": "Configurable scoring thresholds, weights and multipliers, held as data so grading can be retuned without a deploy.",
    "interventions": "Frameworks and next steps per pain point -- the raw material the report's recommendations are built from.",
    "frameworks": "Validated frameworks, linked to stage, industry and root cause.",
    "archetypes": "The founder archetypes a session can resolve to.",
    "prompt_library": "LLM prompts held as data rather than in code, so wording can be changed without a deploy.",
    "psychological_state_signals": "The signals that indicate a founder's psychological state, used to decide whether a wellbeing claim has evidence behind it.",
    "session_state_bands": "The bands a whole session's state can fall into, and the caveat each band carries into the report.",
    "chronic_state_inference": "Rules for inferring a chronic (rather than momentary) state from a session.",
    "stage_diagnosis_logic": "Stage-specific diagnosis logic held as data.",
    "model_task_routing": "Which LLM provider and model serves each of the twelve named tasks. Changing a model is a row update, not a deploy.",
    "notification_types": "The catalogue of notification kinds the platform can send.",
    "support_bot_answers": "Founder-facing help content for the support bot, one row per question. Edited here rather than in code -- no deploy needed.",
    "visual_question_bank": "Image-based questions. Defined and not yet in use.",
    "founder_dna_questions": "The Founder DNA question bank: narrative questions grouped by dimension and stage group, with arc position and closing flags.",
    "current_problem_questions": "The short question set for the Current Problem flow.",
    "founder_dimensions": "Legacy dimension definitions, superseded. Retained in the schema, holds no rows.",
    "business_dimensions": "Superseded by `readiness_pillars`, which the comment on that table records. Retained in the schema, holds no rows.",

    # ---- Part B: authentication ----------------------------------------
    "revoked_tokens": "Session tokens that have been explicitly revoked, so a logout or a forced sign-out cannot be undone by replaying an old token.",

    # ---- Part C: profile and onboarding --------------------------------
    "founders": "The founder. One row per account, holding identity, the full onboarding profile, plan and credit state, consent and retention timestamps, and the phase-completion markers the journey reads to decide what comes next. The widest table in the schema at 69 columns.",
    "founder_context": "Inferred geographic, economic and network context per founder -- the circumstances around the business rather than the business itself.",
    "founder_settings": "Per-founder application settings.",
    "founder_memory": "Durable facts Ally has learned about a founder, carried across conversations.",
    "founder_memory_events": "The append-only log of how that memory changed, so a remembered fact can be traced to where it came from.",
    "founder_dimension_profile": "Legacy per-founder dimension scores, superseded. Retained in the schema, holds no rows.",

    # ---- Part D: chat --------------------------------------------------
    "conversations": "An Ally Chat conversation: its container, token accounting and lock state.",
    "messages": "Individual messages within a conversation, founder and assistant alike, with the AI's reasoning and confidence held as their own columns. Monthly partitioned.",
    "user_token_usage": "Per-founder daily chat token usage, which is what the plan's chat allowance is measured against.",
    "daily_token_usage": "Daily token totals used for cost reporting.",
    "file_uploads": "Files a founder has attached, and the processing state of each.",

    # ---- Part E: retrieval ---------------------------------------------
    "rag_documents": "The document corpus Ally retrieves from.",
    "rag_chunks": "Chunk-level embeddings of those documents -- the unit retrieval actually matches against.",
    "rag_retrieval_log": "What was retrieved for which query, kept so retrieval quality can be tuned against real traffic.",

    # ---- Part F: consent and data protection ---------------------------
    "consents": "The founder's current consent state.",
    "consent_history": "Every consent change, append-only. A withdrawal does not erase the record that consent was once given.",
    "founder_consents": "The consent records the diagnosis gate actually reads: terms and privacy versions, the diagnosis opt-in, and age confirmation, timestamped per grant.",
    "cookie_preferences": "Cookie choices per founder or visitor.",
    "privacy_requests": "DPDP rights requests -- access, correction, export -- and their handling state.",
    "data_deletion_requests": "Deletion requests and where each one is in its lifecycle: pending OTP, grace period, processing, completed or cancelled.",
    "audit_logs": "Append-only audit trail of actions taken on founder data. Monthly partitioned.",

    # ---- Part G: platform ----------------------------------------------
    "notifications": "Notifications queued for or delivered to a founder.",
    "subscriptions": "A founder's plan subscription and its billing state.",
    "payments": "Payment attempts and their outcomes.",
    "discovery_calls": "Discovery call bookings, their slots and their status.",
    "report_shares": "Share tokens for a report, so a founder can send their report to someone without that person having an account.",
    "coupons": "Discount coupons and their constraints.",
    "coupon_redemptions": "Which founder redeemed which coupon, and when.",
    "credit_transactions": "The credit ledger -- every grant, spend and adjustment, so a balance can be explained rather than just read.",
    "gateway_plans": "The payment gateway's own plan objects, mapped to our tiers. One row per (gateway, tier, amount, period) so an autopay subscription can be created against the right gateway plan without creating a duplicate each time. Added with autopay subscriptions in 5b8e2f4a7c19.",
    "plan_call_usage": "Calls consumed against a plan's allowance.",
    "unbilled_usage": "Usage recorded but not yet billed.",
    "calendar_connections": "Connected external calendars per founder.",
    "feature_flags": "Global feature flags.",
    "feature_flag_overrides": "Per-founder overrides of those flags, for staged rollout.",
    "broadcasts": "Messages sent to many founders at once.",
    "broadcast_reads": "Which founder has read which broadcast.",
    "launch_state": "The launch state machine -- armed, counting down, launched, aborted -- plus how many launches have run and how many are allowed.",
    "direct_signup_capacity": "How many direct signups remain available, which is what the public signup gate reads.",
    "waitlist_registrations": "Waitlist entries and their approval state.",
    "waitlist_slot_openings": "Batches of waitlist slots opened by an admin.",

    # ---- Part H: admin and operations ----------------------------------
    "admin_notes": "Staff notes on a founder. Never founder-readable.",
    "admin_audit_log": "What staff did in the admin panel, append-only.",
    "analytics_events": "Product analytics events. Monthly partitioned.",
    "webhook_logs": "Inbound webhook deliveries and how each was handled.",
    "llm_call_log": "Every LLM call: its task, model, token counts, measured latency and estimated cost. The only place real per-task latency and spend can be read.",
    "founder_feedback": "Feedback founders submitted, with what they were looking at when they sent it.",
    "support_bot_misses": "Questions the support bot could not answer, so the gap can be filled in `support_bot_answers`.",

    # ---- Part I: diagnosis engine --------------------------------------
    "sessions": "One diagnosis session: its state, stage, progress and answered count. The row the engine reads to decide what to ask next.",
    "answers": "Every answer a founder gave within a session, graded green, amber or red, with the interpretation behind the grade.",
    "session_context_facts": "Things learned about a founder DURING this session only -- for example that a team question does not apply to them. Deliberately never written back to `founders`: it affects question selection for this session and nothing beyond it.",
    "stage_assessments": "Stage classification for a session, with history, so a re-assessment does not erase the earlier reading.",
    "detected_root_causes": "The final weighted root-cause ranking for a session.",
    "founder_reports": "The founder-facing Clarity Report: scores, bands, narrative and the actions it recommends.",
    "internal_intelligence_reports": "The staff-only diagnostic layer for the same session. Locked from founders by design.",
    "founder_dna_answers": "Answers to the Founder DNA questions, which is what resolves each of the fifteen dimensions.",
    "current_problem_answers": "Answers to the Current Problem flow.",
    "founder_visual_choices": "Answers to image-based questions. Defined and not yet in use.",

    # ---- Part J: planning, goals and vision ----------------------------
    "planning_plans": "A plan a founder is working to. Can be seeded from a diagnosis.",
    "planning_goals": "Goals within a plan.",
    "planning_tasks": "Tasks under a goal, with their status and due dates.",
    "planning_reminders": "Reminders attached to a task.",
    "daily_actions": "Plan Your Day: the daily action list, its priorities, due dates and completion.",
    "founder_goals": "Founder-level goals held outside the plan structure.",
    "achievements": "Achievements a founder has unlocked.",
    "vision_territories": "The territories of the Vision exercise.",
    "vision_summary": "The synthesised output of that exercise.",
    "framework_usage": "Which frameworks a founder has used, for relevance ranking.",
    "founder_daily_quotes": "The two pre-written lines picked for a founder each night.",
    "suggestions": "Suggestions generated for a founder, with the reasoning behind each.",
    "suggestion_feedback": "Whether a suggestion landed, used to improve later ones.",

    # ---- Part K: schema management -------------------------------------
    "alembic_version": "The single row naming the migration revision this database is at. The first thing to compare when two environments disagree.",
}

#: Column descriptions, for the tables where column-level meaning carries real
#: weight: the question bank and its scopes, the founder profile, and the
#: session and report rows. Elsewhere the column name plus its type, key and
#: nullability is the documentation, and inventing prose for `created_at`
#: would pad the document without informing anybody.
COLUMNS: dict[str, dict[str, str]] = {
    "questions": {
        "question_code": "Stable business key, e.g. IVA-061 or S0-HLT-004. This, not question_id, is how a question is referred to across environments -- the surrogate ids have diverged between databases.",
        "category": "The pillar this question scores.",
        "primary_stage_group": "Which bank the question belongs to: Stage 0, Stage 0->1, Stage 1->10+, or Exit. Exit is additive -- an Exit founder draws from it as well as Stage 1->10+.",
        "difficulty_level": "How demanding the question is to answer, used in ordering.",
        "priority": "Selection priority within its pillar.",
        "is_distress_tagged": "Whether this question is actually asking about wellbeing. The report may only claim distress on evidence from a question tagged here -- not from an operational question that happens to sound bleak.",
        "red_flag_pattern": "What a concerning answer looks like.",
        "green_flag_pattern": "What a healthy answer looks like.",
        "follow_up_question_id": "The question to ask next if this one lands.",
        "industry_relevance": "Which industries this applies to. `[\"all\"]` means universal.",
        "min_team_size": "Team-size floor. NULL means no floor -- the permissive value.",
        "max_team_size": "Team-size ceiling, used for questions written for a founder who has not hired yet. NULL means no ceiling.",
        "requires_trading": "True if the question presumes the founder has already sold something. Withheld from founders who have not.",
        "requires_operating_role": "True if the question presumes the founder operates the business rather than supplying it. Separates someone running a clinic from someone selling software to clinics.",
        "requires_multiple_locations": "True if the question presumes more than one site.",
        "embedding": "Vector embedding for semantic matching.",
    },
    "sessions": {
        "questions_answered_count": "Derived from the answer rows when an answer is submitted. The opening block reads this to decide how long to reserve questions for under-covered pillars.",
        "session_state_at_generation": "The session's state when the report was built, frozen so a later change cannot silently rewrite what the report was based on.",
    },
    "answers": {
        "grade": "Green, amber or red. Set by the interpretation engine, not by the founder.",
    },
    "founders": {
        "user_id": "The identity-provider subject. Carries the link to auth; the application never stores a password.",
        "stage_id": "The founder's stage, which selects the question bank the diagnosis draws from.",
        "team_size": "Banded team size from onboarding. Deliberately NOT required for profile completion: every founder who onboarded before the question existed has it NULL, and whatever reads it must treat NULL as 'not known' regardless.",
        "current_revenue": "Banded monthly revenue. Only asked from stage order 3 upward -- a Validation founder has none to report, so onboarding stops asking and completion stops requiring it.",
        "product_description": "What the founder says the business is. Read by the business-model scope to infer supplier versus operator.",
        "founder_reality_signals": "The five yes/no answers about the founder themselves.",
        "business_reality_signals": "The five yes/no answers about the business. Path 2 only -- there is no business to assess at stage 0.",
        "invisible_gaps": "Which of the named gaps the founder said resonated.",
        "profile_completed": "Whether onboarding is finished. Computed from the required field set for this founder's path and stage, never set by hand.",
        "processing_restricted_at": "Set when the founder restricts AI processing. While set, no route that calls an LLM on their behalf will run.",
        "data_retention_expires_at": "When this founder's data becomes eligible for deletion under the retention policy.",
        "deletion_requested_at": "When a deletion was asked for.",
        "deletion_scheduled_at": "When it becomes eligible to execute, after the grace period.",
        "deletion_executed_at": "When it actually ran. Kept separate from scheduled so 'due' and 'done' cannot be confused.",
        "diagnosis_locked_at": "When the diagnosis was locked, after which answers can no longer be changed.",
        "founder_dna_completed_at": "When the Founder DNA phase finished. The diagnosis will not start until this is set.",
        "founder_dna_resolved_dimensions": "Which of the fifteen dimensions have been resolved.",
    },
    "founder_reports": {
        "not_assessed_reason": "Why a pillar has no score: solo, stage, or thin evidence. Added so an unscored pillar shows the founder a reason instead of a blank card. NULL on reports generated before it existed, which falls back to the generic line rather than guessing.",
    },
    "llm_call_log": {
        "latency_ms": "Measured call latency. The source for any real latency figure in the API and LLM documents.",
        "estimated_cost_usd": "Estimated cost of the call, summed for per-founder and per-task spend.",
    },
}
