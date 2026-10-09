# Founder Alley — Database Entity Mapping and Domain Model

**GoXL Consulting Solutions Pvt. Ltd.**  
*Clarity Before Action*

CONFIDENTIAL — INTERNAL USE ONLY

Version 2 · 105 tables · complete reference

| | |
| --- | --- |
| **Schema revision** | `5b8e2f4a7c19` (Alembic head) |
| **Generated** | 2026-10-09 06:46:59 |
| **Companion document** | Entity Relationship Diagram (`ER_Diagram.md`) — field-level detail for every table |
| **Supersedes** | Database Entity Mapping, July 2026 (47 tables) |

This document is about **meaning**. For each entity: what it is, which part of the application writes it, which reads it, and which screen it reaches. The ER document is the field-level companion — types, keys and constraints live there and are not repeated here.

## What changed since the July 2026 version

- **47 tables became 105.** Whole domains are new: Founder DNA, planning and goals, vision, credits and coupons, feature flags, broadcasts, the launch state machine, the support bot, and the LLM call log.
- **The question bank grew from 208 rows to 7,190**, gained a fourth stage group (Exit) and six scope columns that decide which founders may be asked what.
- **A mandatory phase was added between onboarding and diagnosis.** Founder DNA resolves fifteen dimensions, and `POST /diagnosis/start` refuses until it is complete. Any description of the journey that goes straight from onboarding to diagnosis is now wrong.
- **The RLS position has changed and is no longer uniform.** The previous document stated RLS was enabled on all 47 tables. See the access section below, which reports what is actually true and where it differs by environment.

## The domain model

The 105 tables fall into 11 clusters. Read this as the shape of the system before the table-by-table detail.

**Part A — Pre-filled Intelligence** · 32 tables · 39,974 rows

Populated before any founder signs up. Read-only during a live session. This is the content the engine reasons over -- the question bank, the problem and root-cause library, the industry and scoring reference data.

**Part B — Authentication** · 1 table · 520 rows

Identity. Managed by the configured auth provider; the application stores only the link to it.

**Part C — Profile and Onboarding** · 6 tables · 64 rows

Who the founder is and what they told us before any diagnosis ran. Every later phase reads from here.

**Part D — Chat and Conversation** · 5 tables · 0 rows

Ally Chat: the conversation container, the messages in it, and the token accounting that bounds it.

**Part E — Retrieval (RAG)** · 3 tables · 0 rows

The document corpus Ally retrieves from, its chunk-level embeddings, and the retrieval audit trail.

**Part F — Consent and Data Protection (DPDP)** · 7 tables · 31 rows

What the founder agreed to, when, and the machinery that honours a withdrawal or a deletion request.

**Part G — Platform** · 20 tables · 3 rows

Notifications, commerce and scheduling -- everything around the product rather than inside it.

**Part H — Admin and Operations** · 7 tables · 640 rows

Staff-facing records and the operational telemetry behind the admin panel. Not founder-readable.

**Part I — Diagnosis Engine** · 10 tables · 1,172 rows

The live session and everything it produces. This is the USP: the session state, every graded answer, the reasoning output and the two reports built from it.

**Part J — Planning, Goals and Vision** · 13 tables · 0 rows

What the founder does with the report: plans, goals, tasks, reminders and the longer-range vision work.

**Part K — Schema Management** · 1 table · 1 row

Not application data. Listed for completeness because it exists in every environment and is the first thing to check when two databases disagree.

Two relationships hold the whole thing together. **`founders` is the hub**: almost every founder-scoped table carries a `founder_id` and cascades from it, which is what makes a deletion request executable in the first place. **`sessions` is the second hub**: the diagnosis, its answers, its reasoning output and both reports all hang off one session row, so a session is the unit a diagnosis can be reasoned about, re-run or thrown away as a whole.

## The founder data lifecycle

The path a founder's data actually travels, in order. Each step names the tables it writes.

**1. Sign-up** — The identity provider issues a token; the application stores only the link to it.

  Writes: `founders`, `revoked_tokens`

**2. Consent** — Terms and privacy are accepted, and the diagnosis opt-in is taken separately. Both are recorded; the diagnosis gate reads the second one and fails closed when it is absent.

  Writes: `founder_consents`, `consents`, `consent_history`

**3. Onboarding** — Four sections write the profile: stage and experience, what the founder is building, what they know, where they are headed. Required fields differ by path and stage, and `profile_completed` is computed from that set rather than set by hand.

  Writes: `founders`, `founder_context`

**4. Founder DNA** — Fifteen dimensions resolved from a narrative question bank. The diagnosis will not open until every one is resolved.

  Writes: `founder_dna_answers`, `founders`

  Reads: `founder_dna_questions`

**5. Diagnosis** — A session is opened against the stage's question budget. Each question is chosen by the six scope axes and each answer is graded green, amber or red.

  Writes: `sessions`, `answers`, `session_context_facts`

  Reads: `questions`, `question_industry_mapping`, `founder_stages`

**6. Reasoning** — The graded session is scored per pillar, a stage is assessed, root causes are ranked and an archetype is resolved.

  Writes: `stage_assessments`, `detected_root_causes`

  Reads: `archetypes`, `root_causes`, `root_cause_weights`, `scoring_rules`

**7. Report** — Two reports are written from the same session: the founder-facing Clarity Report and the staff-only intelligence layer.

  Writes: `founder_reports`, `internal_intelligence_reports`, `report_shares`

**8. Acting on it** — The founder turns the report into plans, goals and daily actions, and Ally proposes suggestions against them.

  Writes: `planning_plans`, `planning_goals`, `planning_tasks`, `daily_actions`, `suggestions`

  Reads: `interventions`, `frameworks`

**9. Withdrawal or deletion** — Restricting processing stops every route that would call an LLM. A deletion request runs a state machine from OTP through a grace period to execution.

  Writes: `privacy_requests`, `data_deletion_requests`, `founders`

The order matters in two places that are enforced rather than conventional. Onboarding must complete before Founder DNA can start, and Founder DNA must complete before a diagnosis can start — five separate gates sit on `POST /diagnosis/start`: plan entitlement, profile completion, diagnosis consent, AI-processing permission, and Founder DNA completion.

## Complete entity mapping

All 105 entities. **Owned by** is the application area that writes the table; **Reaches** is the screen or screens where it surfaces.

| # | Entity | Part | Purpose | Owned by | Reaches |
| --: | --- | --- | --- | --- | --- |
| 1 | `agent_interpretations` | A | Maps a founder's own statement to the probe worth asking and the root cause it may... | `models` | — |
| 2 | `archetypes` | A | The founder archetypes a session can resolve to | `api/reasoning`, `models` | (server-side, feeds /app/report) |
| 3 | `behaviour_patterns` | A | Founder behaviour and communication patterns, embedded, used to characterise how s... | `api/reasoning`, `models` | (server-side, feeds /app/report) |
| 4 | `blind_spots` | A | Blind-spot patterns -- the things founders systematically cannot see about their o... | `api/reasoning`, `models` | (server-side, feeds /app/report) |
| 5 | `business_dimensions` | A | Superseded by `readiness_pillars`, which the comment on that table records | `models` | — |
| 6 | `chronic_state_inference` | A | Rules for inferring a chronic (rather than momentary) state from a session | `api/reports` | /app/report, /app/business-dna |
| 7 | `current_problem_questions` | A | The short question set for the Current Problem flow | `api/current_problem`, `api/diagnosis`, `api/reports` +2 | /app/current-problem, /app/diagnosis, /app/thinking +5 |
| 8 | `founder_dimensions` | A | Legacy dimension definitions, superseded | — | — |
| 9 | `founder_dna_questions` | A | The Founder DNA question bank: narrative questions grouped by dimension and stage ... | `api/diagnosis`, `api/founder_dna`, `api/reasoning` +2 | /app/diagnosis, /app/thinking, /app/founder-dna +5 |
| 10 | `founder_stages` | A | The eight lifecycle stages, in order, each with its entry and exit criteria, typic... | `api/dashboard`, `api/reasoning`, `api/reports` +3 | /app/journey, (server-side, feeds /app/report), /app/report +1 |
| 11 | `frameworks` | A | Validated frameworks, linked to stage, industry and root cause | `framework_usage`, `models` | /app/frameworks |
| 12 | `industries` | A | The thirty industry verticals, each with diagnostic weights and benchmarks | `api/diagnosis`, `models`, `repositories` | /app/diagnosis, /app/thinking |
| 13 | `industry_stage_thresholds` | A | Revenue thresholds (INR) per stage per industry | `models` | — |
| 14 | `interventions` | A | Frameworks and next steps per pain point -- the raw material the report's recommen... | `api/ally`, `api/knowledge`, `api/reasoning` +2 | /app/knowledge/:section, (server-side, feeds /app/report), /app/report +1 |
| 15 | `model_task_routing` | A | Which LLM provider and model serves each of the twelve named tasks | `api/founder_dna`, `models`, `services` | /app/founder-dna, /app/founder-dna-journey |
| 16 | `notification_types` | A | The catalogue of notification kinds the platform can send | `notifications`, `services` | /app (global) |
| 17 | `problem_stage_mapping` | A | Which problems are plausible at which stage | `models` | — |
| 18 | `problems` | A | The pain-point library | `api/diagnosis`, `api/knowledge`, `api/reasoning` +1 | /app/diagnosis, /app/thinking, /app/knowledge/:section +1 |
| 19 | `prompt_library` | A | LLM prompts held as data rather than in code, so wording can be changed without a ... | `api/reasoning`, `api/reports`, `models` | (server-side, feeds /app/report), /app/report, /app/business-dna |
| 20 | `psychological_state_signals` | A | The signals that indicate a founder's psychological state, used to decide whether ... | `api/reasoning` | (server-side, feeds /app/report) |
| 21 | `question_industry_mapping` | A | Links a question to an industry and stage | `api/diagnosis` | /app/diagnosis, /app/thinking |
| 22 | `question_tag_mapping` | A | Many-to-many link between questions and tags | `models` | — |
| 23 | `question_tags` | A | Tag vocabulary for categorising questions | `models` | — |
| 24 | `questions` | A | The diagnosis question bank | `api/admin`, `api/current_problem`, `api/diagnosis` +6 | /admin/*, /app/current-problem, /app/diagnosis +10 |
| 25 | `readiness_pillars` | A | The six scoring dimensions of the Business Health Score | `api/reasoning`, `api/reports`, `models` +1 | (server-side, feeds /app/report), /app/report, /app/business-dna |
| 26 | `root_cause_weights` | A | Stage-adjusted probability multipliers | `api/knowledge`, `api/reasoning`, `models` | /app/knowledge/:section, (server-side, feeds /app/report) |
| 27 | `root_causes` | A | The root-cause library: what sits underneath a problem, with a confidence weight a... | `api/ally`, `api/diagnosis`, `api/knowledge` +2 | /app/diagnosis, /app/thinking, /app/knowledge/:section +1 |
| 28 | `scoring_rules` | A | Configurable scoring thresholds, weights and multipliers, held as data so grading ... | `api/reasoning`, `api/reports`, `models` | (server-side, feeds /app/report), /app/report, /app/business-dna |
| 29 | `session_state_bands` | A | The bands a whole session's state can fall into, and the caveat each band carries ... | `api/reasoning`, `api/reports` | (server-side, feeds /app/report), /app/report, /app/business-dna |
| 30 | `stage_diagnosis_logic` | A | Stage-specific diagnosis logic held as data | `api/reasoning`, `models` | (server-side, feeds /app/report) |
| 31 | `support_bot_answers` | A | Founder-facing help content for the support bot, one row per question | — | — |
| 32 | `visual_question_bank` | A | Image-based questions | `models` | — |
| 33 | `revoked_tokens` | B | Session tokens that have been explicitly revoked, so a logout or a forced sign-out... | `core`, `models` | — |
| 34 | `founder_context` | C | Inferred geographic, economic and network context per founder -- the circumstances... | `models`, `privacy`, `quotes` +1 | /app/profile, /privacy, /admin/privacy +1 |
| 35 | `founder_dimension_profile` | C | Legacy per-founder dimension scores, superseded | — | — |
| 36 | `founder_memory` | C | Durable facts Ally has learned about a founder, carried across conversations | `api/ally`, `models`, `privacy` | /app/profile, /privacy, /admin/privacy |
| 37 | `founder_memory_events` | C | The append-only log of how that memory changed, so a remembered fact can be traced... | `api/ally`, `models`, `privacy` | /app/profile, /privacy, /admin/privacy |
| 38 | `founder_settings` | C | Per-founder application settings | `privacy`, `settings` | /app/profile, /privacy, /admin/privacy |
| 39 | `founders` | C | The founder | `api/admin`, `api/current_problem`, `api/dashboard` +19 | /admin/*, /app/current-problem, /app/journey +18 |
| 40 | `conversations` | D | An Ally Chat conversation: its container, token accounting and lock state | `api/dashboard`, `achievements`, `admin` +4 | /app/journey, /app/achievements, /admin/* +4 |
| 41 | `daily_token_usage` | D | Daily token totals used for cost reporting | `admin`, `plans` | /admin/*, /app/plan, /app/billing |
| 42 | `file_uploads` | D | Files a founder has attached, and the processing state of each | `ai_chat`, `models` | /app/ally-chat |
| 43 | `messages` | D | Individual messages within a conversation, founder and assistant alike, with the A... | `admin`, `ai_chat`, `models` +1 | /admin/*, /app/ally-chat, /app/profile +2 |
| 44 | `user_token_usage` | D | Per-founder daily chat token usage, which is what the plan's chat allowance is mea... | `models`, `privacy` | /app/profile, /privacy, /admin/privacy |
| 45 | `rag_chunks` | E | Chunk-level embeddings of those documents -- the unit retrieval actually matches a... | `api/ally`, `models` | — |
| 46 | `rag_documents` | E | The document corpus Ally retrieves from | `api/ally`, `models` | — |
| 47 | `rag_retrieval_log` | E | What was retrieved for which query, kept so retrieval quality can be tuned against... | `models` | — |
| 48 | `audit_logs` | F | Append-only audit trail of actions taken on founder data | `models`, `services` | — |
| 49 | `consent_history` | F | Every consent change, append-only | `models` | — |
| 50 | `consents` | F | The founder's current consent state | `api/consents`, `consents`, `core` +1 | /guided/welcome, /app/profile |
| 51 | `cookie_preferences` | F | Cookie choices per founder or visitor | `api/consents`, `admin`, `models` | /guided/welcome, /app/profile, /admin/* |
| 52 | `data_deletion_requests` | F | Deletion requests and where each one is in its lifecycle: pending OTP, grace perio... | `models`, `notifications` | /app (global) |
| 53 | `founder_consents` | F | The consent records the diagnosis gate actually reads: terms and privacy versions,... | `admin`, `consents`, `privacy` | /admin/*, /guided/welcome, /app/profile +2 |
| 54 | `privacy_requests` | F | DPDP rights requests -- access, correction, export -- and their handling state | `admin`, `models`, `privacy` +1 | /admin/*, /app/profile, /privacy +1 |
| 55 | `broadcast_reads` | G | Which founder has read which broadcast | `admin` | /admin/* |
| 56 | `broadcasts` | G | Messages sent to many founders at once | `admin` | /admin/* |
| 57 | `calendar_connections` | G | Connected external calendars per founder | `calendar_sync`, `notifications` | /app/discovery-call, /app (global) |
| 58 | `coupon_redemptions` | G | Which founder redeemed which coupon, and when | `coupons` | /app/billing, /admin/coupons |
| 59 | `coupons` | G | Discount coupons and their constraints | `coupons` | /app/billing, /admin/coupons |
| 60 | `credit_transactions` | G | The credit ledger -- every grant, spend and adjustment, so a balance can be explai... | `admin`, `credits` | /admin/*, /app/billing, /admin/users/:id |
| 61 | `direct_signup_capacity` | G | How many direct signups remain available, which is what the public signup gate reads | `api/waitlist`, `models`, `services` | /, /admin/waitlist |
| 62 | `discovery_calls` | G | Discovery call bookings, their slots and their status | `api/admin`, `api/dashboard`, `api/discovery` +4 | /admin/*, /app/journey, /app/discovery-call +3 |
| 63 | `feature_flag_overrides` | G | Per-founder overrides of those flags, for staged rollout | `admin` | /admin/* |
| 64 | `feature_flags` | G | Global feature flags | `admin` | /admin/* |
| 65 | `gateway_plans` | G | The payment gateway's own plan objects, mapped to our tiers | `payments` | /app/billing |
| 66 | `launch_state` | G | The launch state machine -- armed, counting down, launched, aborted -- plus how ma... | `launch`, `models` | /, /admin/launch |
| 67 | `notifications` | G | Notifications queued for or delivered to a founder | `models`, `notifications`, `privacy` +2 | /app (global), /app/profile, /privacy +1 |
| 68 | `payments` | G | Payment attempts and their outcomes | `core`, `models`, `payments` +1 | /app/billing |
| 69 | `plan_call_usage` | G | Calls consumed against a plan's allowance | `plans` | /app/plan, /app/billing |
| 70 | `report_shares` | G | Share tokens for a report, so a founder can send their report to someone without t... | `api/reasoning`, `api/reports`, `models` | (server-side, feeds /app/report), /app/report, /app/business-dna |
| 71 | `subscriptions` | G | A founder's plan subscription and its billing state | `api/plans`, `admin`, `models` +2 | /app/plan, /app/billing, /admin/* +1 |
| 72 | `unbilled_usage` | G | Usage recorded but not yet billed | `admin`, `plans` | /admin/*, /app/plan, /app/billing |
| 73 | `waitlist_registrations` | G | Waitlist entries and their approval state | `api/admin`, `models`, `services` | /admin/* |
| 74 | `waitlist_slot_openings` | G | Batches of waitlist slots opened by an admin | `models`, `services` | — |
| 75 | `admin_audit_log` | H | What staff did in the admin panel, append-only | `admin` | /admin/* |
| 76 | `admin_notes` | H | Staff notes on a founder | `models` | — |
| 77 | `analytics_events` | H | Product analytics events | `models` | — |
| 78 | `founder_feedback` | H | Feedback founders submitted, with what they were looking at when they sent it | `api/feedback`, `admin`, `eval` +2 | /app/feedback, /admin/*, (offline, no screen) +3 |
| 79 | `llm_call_log` | H | Every LLM call: its task, model, token counts, measured latency and estimated cost | `admin`, `ai_chat`, `models` +1 | /admin/*, /app/ally-chat |
| 80 | `support_bot_misses` | H | Questions the support bot could not answer, so the gap can be filled in `support_b... | `api/admin` | /admin/* |
| 81 | `webhook_logs` | H | Inbound webhook deliveries and how each was handled | `api/webhooks`, `models` | (inbound, no screen) |
| 82 | `answers` | I | Every answer a founder gave within a session, graded green, amber or red, with the... | `api/current_problem`, `api/diagnosis`, `api/founder_dna` +5 | /app/current-problem, /app/diagnosis, /app/thinking +10 |
| 83 | `current_problem_answers` | I | Answers to the Current Problem flow | `api/current_problem`, `api/diagnosis`, `api/reports` +2 | /app/current-problem, /app/diagnosis, /app/thinking +5 |
| 84 | `detected_root_causes` | I | The final weighted root-cause ranking for a session | `api/diagnosis`, `api/reports`, `eval` +2 | /app/diagnosis, /app/thinking, /app/report +5 |
| 85 | `founder_dna_answers` | I | Answers to the Founder DNA questions, which is what resolves each of the fifteen d... | `api/diagnosis`, `api/founder_dna`, `api/reasoning` +2 | /app/diagnosis, /app/thinking, /app/founder-dna +5 |
| 86 | `founder_reports` | I | The founder-facing Clarity Report: scores, bands, narrative and the actions it rec... | `api/dashboard`, `api/feedback`, `api/reasoning` +7 | /app/journey, /app/feedback, (server-side, feeds /app/report) +8 |
| 87 | `founder_visual_choices` | I | Answers to image-based questions | `models` | — |
| 88 | `internal_intelligence_reports` | I | The staff-only diagnostic layer for the same session | `models` | — |
| 89 | `session_context_facts` | I | Things learned about a founder DURING this session only -- for example that a team... | — | — |
| 90 | `sessions` | I | One diagnosis session: its state, stage, progress and answered count | `api/dashboard`, `api/diagnosis`, `api/feedback` +6 | /app/journey, /app/diagnosis, /app/thinking +9 |
| 91 | `stage_assessments` | I | Stage classification for a session, with history, so a re-assessment does not eras... | `api/dashboard`, `models`, `privacy` | /app/journey, /app/profile, /privacy +1 |
| 92 | `achievements` | J | Achievements a founder has unlocked | `achievements` | /app/achievements |
| 93 | `daily_actions` | J | Plan Your Day: the daily action list, its priorities, due dates and completion | `api/dashboard`, `models` | /app/journey |
| 94 | `founder_daily_quotes` | J | The two pre-written lines picked for a founder each night | `quotes` | /app/journey |
| 95 | `founder_goals` | J | Founder-level goals held outside the plan structure | `founder_goals` | /app/goals |
| 96 | `framework_usage` | J | Which frameworks a founder has used, for relevance ranking | `framework_usage` | /app/frameworks |
| 97 | `planning_goals` | J | Goals within a plan | `notifications`, `planning`, `privacy` | /app (global), /app/next-steps, /app/goals +3 |
| 98 | `planning_plans` | J | A plan a founder is working to | `planning`, `privacy` | /app/next-steps, /app/goals, /app/profile +2 |
| 99 | `planning_reminders` | J | Reminders attached to a task | `planning` | /app/next-steps, /app/goals |
| 100 | `planning_tasks` | J | Tasks under a goal, with their status and due dates | `notifications`, `planning`, `privacy` | /app (global), /app/next-steps, /app/goals +3 |
| 101 | `suggestion_feedback` | J | Whether a suggestion landed, used to improve later ones | `ai_chat`, `models` | /app/ally-chat |
| 102 | `suggestions` | J | Suggestions generated for a founder, with the reasoning behind each | `ai_chat`, `models`, `notifications` | /app/ally-chat, /app (global) |
| 103 | `vision_summary` | J | The synthesised output of that exercise | `vision` | /app/vision |
| 104 | `vision_territories` | J | The territories of the Vision exercise | `vision` | /app/vision |
| 105 | `alembic_version` | K | The single row naming the migration revision this database is at | — | — |

---

## Part A — Pre-filled Intelligence

Populated before any founder signs up. Read-only during a live session. This is the content the engine reasons over -- the question bank, the problem and root-cause library, the industry and scoring reference data.

### 1. `agent_interpretations`

Maps a founder's own statement to the probe worth asking and the root cause it may indicate.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 11 |
| ORM model | `AgentInterpretations` |
| Written / read by | `models` |
| Reaches | — no screen — |
| Depends on | — nothing — |
| Depended on by | — nothing — |

### 2. `archetypes`

The founder archetypes a session can resolve to.

| | |
| --- | --- |
| Rows (local) | 8 |
| Columns | 13 |
| ORM model | `Archetypes` |
| Written / read by | `api/reasoning`, `models` |
| Reaches | (server-side, feeds /app/report) |
| Depends on | — nothing — |
| Depended on by | — nothing — |

### 3. `behaviour_patterns`

Founder behaviour and communication patterns, embedded, used to characterise how someone is operating rather than what they are doing.

| | |
| --- | --- |
| Rows (local) | 27 |
| Columns | 16 |
| ORM model | `BehaviourPatterns` |
| Written / read by | `api/reasoning`, `models` |
| Reaches | (server-side, feeds /app/report) |
| Depends on | — nothing — |
| Depended on by | — nothing — |

### 4. `blind_spots`

Blind-spot patterns -- the things founders systematically cannot see about their own business.

| | |
| --- | --- |
| Rows (local) | 20 |
| Columns | 11 |
| ORM model | `BlindSpots` |
| Written / read by | `api/reasoning`, `models` |
| Reaches | (server-side, feeds /app/report) |
| Depends on | — nothing — |
| Depended on by | — nothing — |

### 5. `business_dimensions`

Superseded by `readiness_pillars`, which the comment on that table records. Retained in the schema, holds no rows.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 8 |
| ORM model | `BusinessDimensions` |
| Written / read by | `models` |
| Reaches | — no screen — |
| Depends on | — nothing — |
| Depended on by | — nothing — |

### 6. `chronic_state_inference`

Rules for inferring a chronic (rather than momentary) state from a session.

| | |
| --- | --- |
| Rows (local) | 5 |
| Columns | 8 |
| ORM model | **none — raw SQL only** |
| Written / read by | `api/reports` |
| Reaches | /app/report, /app/business-dna |
| Depends on | — nothing — |
| Depended on by | — nothing — |

### 7. `current_problem_questions`

The short question set for the Current Problem flow.

| | |
| --- | --- |
| Rows (local) | 12 |
| Columns | 7 |
| ORM model | `CurrentProblemQuestions` |
| Written / read by | `api/current_problem`, `api/diagnosis`, `api/reports`, `models`, `privacy` |
| Reaches | /app/current-problem, /app/diagnosis, /app/thinking, /app/report, /app/business-dna, /app/profile, /privacy, /admin/privacy |
| Depends on | — nothing — |
| Depended on by | `current_problem_answers` |

### 8. `founder_dimensions`

Legacy dimension definitions, superseded. Retained in the schema, holds no rows.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 10 |
| ORM model | **none — raw SQL only** |
| Written / read by | — no reference found — |
| Reaches | — no screen — |
| Depends on | — nothing — |
| Depended on by | `founder_dimension_profile`, `visual_question_bank` |

### 9. `founder_dna_questions`

The Founder DNA question bank: narrative questions grouped by dimension and stage group, with arc position and closing flags.

| | |
| --- | --- |
| Rows (local) | 67 |
| Columns | 14 |
| ORM model | `FounderDnaQuestions` |
| Written / read by | `api/diagnosis`, `api/founder_dna`, `api/reasoning`, `models`, `privacy` |
| Reaches | /app/diagnosis, /app/thinking, /app/founder-dna, /app/founder-dna-journey, (server-side, feeds /app/report), /app/profile, /privacy, /admin/privacy |
| Depends on | — nothing — |
| Depended on by | `founder_dna_answers` |

### 10. `founder_stages`

The eight lifecycle stages, in order, each with its entry and exit criteria, typical operational problems and psychological challenges, and the question budget a diagnosis at that stage is allowed to spend.

| | |
| --- | --- |
| Rows (local) | 8 |
| Columns | 14 |
| ORM model | `FounderStages` |
| Written / read by | `api/dashboard`, `api/reasoning`, `api/reports`, `models`, `quotes`, `repositories` |
| Reaches | /app/journey, (server-side, feeds /app/report), /app/report, /app/business-dna |
| Depends on | — nothing — |
| Depended on by | `founders`, `industry_stage_thresholds`, `problem_stage_mapping`, `root_cause_weights`, `sessions`, `stage_assessments` |

### 11. `frameworks`

Validated frameworks, linked to stage, industry and root cause.

| | |
| --- | --- |
| Rows (local) | 83 |
| Columns | 15 |
| ORM model | `Frameworks` |
| Written / read by | `framework_usage`, `models` |
| Reaches | /app/frameworks |
| Depends on | — nothing — |
| Depended on by | — nothing — |

### 12. `industries`

The thirty industry verticals, each with diagnostic weights and benchmarks.

| | |
| --- | --- |
| Rows (local) | 30 |
| Columns | 18 |
| ORM model | `Industries` |
| Written / read by | `api/diagnosis`, `models`, `repositories` |
| Reaches | /app/diagnosis, /app/thinking |
| Depends on | — nothing — |
| Depended on by | `founders`, `industry_stage_thresholds`, `question_industry_mapping`, `sessions` |

### 13. `industry_stage_thresholds`

Revenue thresholds (INR) per stage per industry. What counts as early traction in textiles is not what counts in SaaS.

| | |
| --- | --- |
| Rows (local) | 32 |
| Columns | 6 |
| ORM model | `IndustryStageThresholds` |
| Written / read by | `models` |
| Reaches | — no screen — |
| Depends on | `founder_stages`, `industries` |
| Depended on by | — nothing — |

### 14. `interventions`

Frameworks and next steps per pain point -- the raw material the report's recommendations are built from.

| | |
| --- | --- |
| Rows (local) | 2,051 |
| Columns | 15 |
| ORM model | `Interventions` |
| Written / read by | `api/ally`, `api/knowledge`, `api/reasoning`, `api/reports`, `models` |
| Reaches | /app/knowledge/:section, (server-side, feeds /app/report), /app/report, /app/business-dna |
| Depends on | `problems` |
| Depended on by | `daily_actions`, `founder_feedback` |

### 15. `model_task_routing`

Which LLM provider and model serves each of the twelve named tasks. Changing a model is a row update, not a deploy.

| | |
| --- | --- |
| Rows (local) | 12 |
| Columns | 6 |
| ORM model | `ModelTaskRouting` |
| Written / read by | `api/founder_dna`, `models`, `services` |
| Reaches | /app/founder-dna, /app/founder-dna-journey |
| Depends on | — nothing — |
| Depended on by | — nothing — |

### 16. `notification_types`

The catalogue of notification kinds the platform can send.

| | |
| --- | --- |
| Rows (local) | 48 |
| Columns | 6 |
| ORM model | **none — raw SQL only** |
| Written / read by | `notifications`, `services` |
| Reaches | /app (global) |
| Depends on | — nothing — |
| Depended on by | `notifications` |

### 17. `problem_stage_mapping`

Which problems are plausible at which stage. Keeps a stage-0 founder from being matched to a scaling problem.

| | |
| --- | --- |
| Rows (local) | 553 |
| Columns | 5 |
| ORM model | `ProblemStageMapping` |
| Written / read by | `models` |
| Reaches | — no screen — |
| Depends on | `founder_stages`, `problems` |
| Depended on by | — nothing — |

### 18. `problems`

The pain-point library. Each row is one problem a founder can have, categorised and embedded for semantic retrieval.

| | |
| --- | --- |
| Rows (local) | 1,039 |
| Columns | 20 |
| ORM model | `Problems` |
| Written / read by | `api/diagnosis`, `api/knowledge`, `api/reasoning`, `models` |
| Reaches | /app/diagnosis, /app/thinking, /app/knowledge/:section, (server-side, feeds /app/report) |
| Depends on | `readiness_pillars` |
| Depended on by | `interventions`, `problem_stage_mapping`, `questions`, `root_causes` |

### 19. `prompt_library`

LLM prompts held as data rather than in code, so wording can be changed without a deploy.

| | |
| --- | --- |
| Rows (local) | 7 |
| Columns | 10 |
| ORM model | `PromptLibrary` |
| Written / read by | `api/reasoning`, `api/reports`, `models` |
| Reaches | (server-side, feeds /app/report), /app/report, /app/business-dna |
| Depends on | — nothing — |
| Depended on by | — nothing — |

### 20. `psychological_state_signals`

The signals that indicate a founder's psychological state, used to decide whether a wellbeing claim has evidence behind it.

| | |
| --- | --- |
| Rows (local) | 20 |
| Columns | 12 |
| ORM model | **none — raw SQL only** |
| Written / read by | `api/reasoning` |
| Reaches | (server-side, feeds /app/report) |
| Depends on | — nothing — |
| Depended on by | — nothing — |

### 21. `question_industry_mapping`

Links a question to an industry and stage. A question with no row here is universal. `applicability_type` separates a defining question for an industry from one that is merely relevant.

| | |
| --- | --- |
| Rows (local) | 3,630 |
| Columns | 7 |
| ORM model | **none — raw SQL only** |
| Written / read by | `api/diagnosis` |
| Reaches | /app/diagnosis, /app/thinking |
| Depends on | `industries`, `questions` |
| Depended on by | — nothing — |

### 22. `question_tag_mapping`

Many-to-many link between questions and tags.

| | |
| --- | --- |
| Rows (local) | 3,506 |
| Columns | 3 |
| ORM model | `QuestionTagMapping` |
| Written / read by | `models` |
| Reaches | — no screen — |
| Depends on | `question_tags`, `questions` |
| Depended on by | — nothing — |

### 23. `question_tags`

Tag vocabulary for categorising questions.

| | |
| --- | --- |
| Rows (local) | 88 |
| Columns | 5 |
| ORM model | `QuestionTags` |
| Written / read by | `models` |
| Reaches | — no screen — |
| Depends on | — nothing — |
| Depended on by | `question_tag_mapping` |

### 24. `questions`

The diagnosis question bank. One row per question, carrying its pillar, stage group, priority, distress tag, and the six scope columns that decide which founders may be asked it.

| | |
| --- | --- |
| Rows (local) | 7,190 |
| Columns | 26 |
| ORM model | `Questions` |
| Written / read by | `api/admin`, `api/current_problem`, `api/diagnosis`, `api/founder_dna`, `api/reasoning`, `api/reports`, `models`, `privacy`, `support_bot` |
| Reaches | /admin/*, /app/current-problem, /app/diagnosis, /app/thinking, /app/founder-dna, /app/founder-dna-journey, (server-side, feeds /app/report), /app/report, /app/business-dna, /app/profile, /privacy, /admin/privacy, /app/help |
| Depends on | `problems`, `questions`, `root_causes` |
| Depended on by | `answers`, `question_industry_mapping`, `question_tag_mapping`, `questions`, `sessions` |

**Fields worth knowing**

- `question_code` — Stable business key, e.g. IVA-061 or S0-HLT-004. This, not question_id, is how a question is referred to across environments -- the surrogate ids have diverged between databases.
- `category` — The pillar this question scores.
- `primary_stage_group` — Which bank the question belongs to: Stage 0, Stage 0->1, Stage 1->10+, or Exit. Exit is additive -- an Exit founder draws from it as well as Stage 1->10+.
- `difficulty_level` — How demanding the question is to answer, used in ordering.
- `priority` — Selection priority within its pillar.
- `is_distress_tagged` — Whether this question is actually asking about wellbeing. The report may only claim distress on evidence from a question tagged here -- not from an operational question that happens to sound bleak.
- `red_flag_pattern` — What a concerning answer looks like.
- `green_flag_pattern` — What a healthy answer looks like.
- `follow_up_question_id` — The question to ask next if this one lands.
- `industry_relevance` — Which industries this applies to. `["all"]` means universal.
- `min_team_size` — Team-size floor. NULL means no floor -- the permissive value.
- `max_team_size` — Team-size ceiling, used for questions written for a founder who has not hired yet. NULL means no ceiling.
- `requires_trading` — True if the question presumes the founder has already sold something. Withheld from founders who have not.
- `requires_operating_role` — True if the question presumes the founder operates the business rather than supplying it. Separates someone running a clinic from someone selling software to clinics.
- `requires_multiple_locations` — True if the question presumes more than one site.
- `embedding` — Vector embedding for semantic matching.

### 25. `readiness_pillars`

The six scoring dimensions of the Business Health Score. Weightages sum to 100 and are the weights for that score.

| | |
| --- | --- |
| Rows (local) | 6 |
| Columns | 12 |
| ORM model | `ReadinessPillars` |
| Written / read by | `api/reasoning`, `api/reports`, `models`, `repositories` |
| Reaches | (server-side, feeds /app/report), /app/report, /app/business-dna |
| Depends on | — nothing — |
| Depended on by | `problems` |

### 26. `root_cause_weights`

Stage-adjusted probability multipliers. The same root cause is more or less likely depending on the founder's stage, and this is where that is expressed.

| | |
| --- | --- |
| Rows (local) | 16,256 |
| Columns | 5 |
| ORM model | `RootCauseWeights` |
| Written / read by | `api/knowledge`, `api/reasoning`, `models` |
| Reaches | /app/knowledge/:section, (server-side, feeds /app/report) |
| Depends on | `founder_stages`, `root_causes` |
| Depended on by | — nothing — |

### 27. `root_causes`

The root-cause library: what sits underneath a problem, with a confidence weight and an embedding.

| | |
| --- | --- |
| Rows (local) | 4,922 |
| Columns | 16 |
| ORM model | `RootCauses` |
| Written / read by | `api/ally`, `api/diagnosis`, `api/knowledge`, `api/reasoning`, `models` |
| Reaches | /app/diagnosis, /app/thinking, /app/knowledge/:section, (server-side, feeds /app/report) |
| Depends on | `problems` |
| Depended on by | `answers`, `detected_root_causes`, `questions`, `root_cause_weights` |

### 28. `scoring_rules`

Configurable scoring thresholds, weights and multipliers, held as data so grading can be retuned without a deploy.

| | |
| --- | --- |
| Rows (local) | 47 |
| Columns | 9 |
| ORM model | `ScoringRules` |
| Written / read by | `api/reasoning`, `api/reports`, `models` |
| Reaches | (server-side, feeds /app/report), /app/report, /app/business-dna |
| Depends on | — nothing — |
| Depended on by | — nothing — |

### 29. `session_state_bands`

The bands a whole session's state can fall into, and the caveat each band carries into the report.

| | |
| --- | --- |
| Rows (local) | 4 |
| Columns | 10 |
| ORM model | **none — raw SQL only** |
| Written / read by | `api/reasoning`, `api/reports` |
| Reaches | (server-side, feeds /app/report), /app/report, /app/business-dna |
| Depends on | — nothing — |
| Depended on by | — nothing — |

### 30. `stage_diagnosis_logic`

Stage-specific diagnosis logic held as data.

| | |
| --- | --- |
| Rows (local) | 3 |
| Columns | 9 |
| ORM model | `StageDiagnosisLogic` |
| Written / read by | `api/reasoning`, `models` |
| Reaches | (server-side, feeds /app/report) |
| Depends on | — nothing — |
| Depended on by | — nothing — |

### 31. `support_bot_answers`

Founder-facing help content for the support bot, one row per question. Edited here rather than in code -- no deploy needed.

| | |
| --- | --- |
| Rows (local) | 300 |
| Columns | 18 |
| ORM model | **none — raw SQL only** |
| Written / read by | — no reference found — |
| Reaches | — no screen — |
| Depends on | — nothing — |
| Depended on by | — nothing — |

### 32. `visual_question_bank`

Image-based questions. Defined and not yet in use.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 14 |
| ORM model | `VisualQuestionBank` |
| Written / read by | `models` |
| Reaches | — no screen — |
| Depends on | `founder_dimensions` |
| Depended on by | `founder_visual_choices` |

---

## Part B — Authentication

Identity. Managed by the configured auth provider; the application stores only the link to it.

### 33. `revoked_tokens`

Session tokens that have been explicitly revoked, so a logout or a forced sign-out cannot be undone by replaying an old token.

| | |
| --- | --- |
| Rows (local) | 520 |
| Columns | 3 |
| ORM model | `RevokedTokenRow` |
| Written / read by | `core`, `models` |
| Reaches | — no screen — |
| Depends on | — nothing — |
| Depended on by | — nothing — |

---

## Part C — Profile and Onboarding

Who the founder is and what they told us before any diagnosis ran. Every later phase reads from here.

### 34. `founder_context`

Inferred geographic, economic and network context per founder -- the circumstances around the business rather than the business itself.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 11 |
| ORM model | `FounderContext` |
| Written / read by | `models`, `privacy`, `quotes`, `repositories` |
| Reaches | /app/profile, /privacy, /admin/privacy, /app/journey |
| Depends on | `founders` |
| Depended on by | — nothing — |

### 35. `founder_dimension_profile`

Legacy per-founder dimension scores, superseded. Retained in the schema, holds no rows.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 10 |
| ORM model | **none — raw SQL only** |
| Written / read by | — no reference found — |
| Reaches | — no screen — |
| Depends on | `founder_dimensions`, `founders` |
| Depended on by | — nothing — |

### 36. `founder_memory`

Durable facts Ally has learned about a founder, carried across conversations.

| | |
| --- | --- |
| Rows (local) | 15 |
| Columns | 18 |
| ORM model | `FounderMemory` |
| Written / read by | `api/ally`, `models`, `privacy` |
| Reaches | /app/profile, /privacy, /admin/privacy |
| Depends on | `founders` |
| Depended on by | — nothing — |

### 37. `founder_memory_events`

The append-only log of how that memory changed, so a remembered fact can be traced to where it came from.

| | |
| --- | --- |
| Rows (local) | 15 |
| Columns | 9 |
| ORM model | `FounderMemoryEvent` |
| Written / read by | `api/ally`, `models`, `privacy` |
| Reaches | /app/profile, /privacy, /admin/privacy |
| Depends on | `founders` |
| Depended on by | — nothing — |

### 38. `founder_settings`

Per-founder application settings.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 10 |
| ORM model | **none — raw SQL only** |
| Written / read by | `privacy`, `settings` |
| Reaches | /app/profile, /privacy, /admin/privacy |
| Depends on | `founders` |
| Depended on by | — nothing — |

### 39. `founders`

The founder. One row per account, holding identity, the full onboarding profile, plan and credit state, consent and retention timestamps, and the phase-completion markers the journey reads to decide what comes next. The widest table in the schema at 69 columns.

| | |
| --- | --- |
| Rows (local) | 34 |
| Columns | 69 |
| ORM model | `Founders` |
| Written / read by | `api/admin`, `api/current_problem`, `api/dashboard`, `api/diagnosis`, `api/founder_dna`, `api/plans`, `api/reports`, `admin`, `core`, `coupons`, `credits`, `emails`, `learning`, `models`, `notifications`, `payments`, `planning`, `plans`, `privacy`, `quotes`, `services`, `support_bot` |
| Reaches | /admin/*, /app/current-problem, /app/journey, /app/diagnosis, /app/thinking, /app/founder-dna, /app/founder-dna-journey, /app/plan, /app/billing, /app/report, /app/business-dna, /admin/coupons, /admin/users/:id, (background, no screen), /app (global), /app/next-steps, /app/goals, /app/profile, /privacy, /admin/privacy, /app/help |
| Depends on | `founder_stages`, `industries` |
| Depended on by | `achievements`, `admin_notes`, `analytics_events`, `answers`, `audit_logs`, `broadcast_reads`, `calendar_connections`, `consent_history`, `consents`, `conversations`, `cookie_preferences`, `coupon_redemptions`, `credit_transactions`, `current_problem_answers`, `daily_actions`, `daily_token_usage`, `data_deletion_requests`, `detected_root_causes`, `discovery_calls`, `feature_flag_overrides`, `file_uploads`, `founder_consents`, `founder_context`, `founder_daily_quotes`, `founder_dimension_profile`, `founder_dna_answers`, `founder_feedback`, `founder_goals`, `founder_memory`, `founder_memory_events`, `founder_reports`, `founder_settings`, `founder_visual_choices`, `framework_usage`, `internal_intelligence_reports`, `messages`, `notifications`, `payments`, `plan_call_usage`, `planning_plans`, `privacy_requests`, `rag_retrieval_log`, `report_shares`, `sessions`, `stage_assessments`, `subscriptions`, `suggestion_feedback`, `suggestions`, `support_bot_misses`, `user_token_usage`, `vision_summary`, `vision_territories`, `webhook_logs` |

**Fields worth knowing**

- `user_id` — The identity-provider subject. Carries the link to auth; the application never stores a password.
- `stage_id` — The founder's stage, which selects the question bank the diagnosis draws from.
- `team_size` — Banded team size from onboarding. Deliberately NOT required for profile completion: every founder who onboarded before the question existed has it NULL, and whatever reads it must treat NULL as 'not known' regardless.
- `current_revenue` — Banded monthly revenue. Only asked from stage order 3 upward -- a Validation founder has none to report, so onboarding stops asking and completion stops requiring it.
- `product_description` — What the founder says the business is. Read by the business-model scope to infer supplier versus operator.
- `founder_reality_signals` — The five yes/no answers about the founder themselves.
- `business_reality_signals` — The five yes/no answers about the business. Path 2 only -- there is no business to assess at stage 0.
- `invisible_gaps` — Which of the named gaps the founder said resonated.
- `profile_completed` — Whether onboarding is finished. Computed from the required field set for this founder's path and stage, never set by hand.
- `processing_restricted_at` — Set when the founder restricts AI processing. While set, no route that calls an LLM on their behalf will run.
- `data_retention_expires_at` — When this founder's data becomes eligible for deletion under the retention policy.
- `deletion_requested_at` — When a deletion was asked for.
- `deletion_scheduled_at` — When it becomes eligible to execute, after the grace period.
- `deletion_executed_at` — When it actually ran. Kept separate from scheduled so 'due' and 'done' cannot be confused.
- `diagnosis_locked_at` — When the diagnosis was locked, after which answers can no longer be changed.
- `founder_dna_completed_at` — When the Founder DNA phase finished. The diagnosis will not start until this is set.
- `founder_dna_resolved_dimensions` — Which of the fifteen dimensions have been resolved.

---

## Part D — Chat and Conversation

Ally Chat: the conversation container, the messages in it, and the token accounting that bounds it.

### 40. `conversations`

An Ally Chat conversation: its container, token accounting and lock state.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 16 |
| ORM model | `Conversations` |
| Written / read by | `api/dashboard`, `achievements`, `admin`, `ai_chat`, `core`, `models`, `privacy` |
| Reaches | /app/journey, /app/achievements, /admin/*, /app/ally-chat, /app/profile, /privacy, /admin/privacy |
| Depends on | `founders` |
| Depended on by | `file_uploads`, `messages`, `rag_retrieval_log`, `suggestions` |

### 41. `daily_token_usage`

Daily token totals used for cost reporting.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 5 |
| ORM model | **none — raw SQL only** |
| Written / read by | `admin`, `plans` |
| Reaches | /admin/*, /app/plan, /app/billing |
| Depends on | `founders` |
| Depended on by | — nothing — |

### 42. `file_uploads`

Files a founder has attached, and the processing state of each.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 21 |
| ORM model | `FileUploads` |
| Written / read by | `ai_chat`, `models` |
| Reaches | /app/ally-chat |
| Depends on | `conversations`, `founders` |
| Depended on by | — nothing — |

### 43. `messages`

Individual messages within a conversation, founder and assistant alike, with the AI's reasoning and confidence held as their own columns. Monthly partitioned.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 13 |
| ORM model | `Message` |
| Written / read by | `admin`, `ai_chat`, `models`, `privacy` |
| Reaches | /admin/*, /app/ally-chat, /app/profile, /privacy, /admin/privacy |
| Depends on | `conversations`, `founders` |
| Depended on by | — nothing — |

### 44. `user_token_usage`

Per-founder daily chat token usage, which is what the plan's chat allowance is measured against.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 10 |
| ORM model | `UserTokenUsage` |
| Written / read by | `models`, `privacy` |
| Reaches | /app/profile, /privacy, /admin/privacy |
| Depends on | `founders` |
| Depended on by | — nothing — |

---

## Part E — Retrieval (RAG)

The document corpus Ally retrieves from, its chunk-level embeddings, and the retrieval audit trail.

### 45. `rag_chunks`

Chunk-level embeddings of those documents -- the unit retrieval actually matches against.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 10 |
| ORM model | `RagChunks` |
| Written / read by | `api/ally`, `models` |
| Reaches | — no screen — |
| Depends on | `rag_documents` |
| Depended on by | — nothing — |

### 46. `rag_documents`

The document corpus Ally retrieves from.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 13 |
| ORM model | `RagDocuments` |
| Written / read by | `api/ally`, `models` |
| Reaches | — no screen — |
| Depends on | — nothing — |
| Depended on by | `rag_chunks` |

### 47. `rag_retrieval_log`

What was retrieved for which query, kept so retrieval quality can be tuned against real traffic.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 12 |
| ORM model | `RagRetrievalLog` |
| Written / read by | `models` |
| Reaches | — no screen — |
| Depends on | `conversations`, `founders`, `sessions` |
| Depended on by | — nothing — |

---

## Part F — Consent and Data Protection (DPDP)

What the founder agreed to, when, and the machinery that honours a withdrawal or a deletion request.

### 48. `audit_logs`

Append-only audit trail of actions taken on founder data. Monthly partitioned.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 9 |
| ORM model | `AuditLog` |
| Written / read by | `models`, `services` |
| Reaches | — no screen — |
| Depends on | `founders` |
| Depended on by | — nothing — |

### 49. `consent_history`

Every consent change, append-only. A withdrawal does not erase the record that consent was once given.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 10 |
| ORM model | `ConsentHistory` |
| Written / read by | `models` |
| Reaches | — no screen — |
| Depends on | `founders` |
| Depended on by | — nothing — |

### 50. `consents`

The founder's current consent state.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 14 |
| ORM model | `Consents` |
| Written / read by | `api/consents`, `consents`, `core`, `models` |
| Reaches | /guided/welcome, /app/profile |
| Depends on | `founders` |
| Depended on by | — nothing — |

### 51. `cookie_preferences`

Cookie choices per founder or visitor.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 12 |
| ORM model | `CookiePreferences` |
| Written / read by | `api/consents`, `admin`, `models` |
| Reaches | /guided/welcome, /app/profile, /admin/* |
| Depends on | `founders` |
| Depended on by | — nothing — |

### 52. `data_deletion_requests`

Deletion requests and where each one is in its lifecycle: pending OTP, grace period, processing, completed or cancelled.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 12 |
| ORM model | `DataDeletionRequests` |
| Written / read by | `models`, `notifications` |
| Reaches | /app (global) |
| Depends on | `founders` |
| Depended on by | — nothing — |

### 53. `founder_consents`

The consent records the diagnosis gate actually reads: terms and privacy versions, the diagnosis opt-in, and age confirmation, timestamped per grant.

| | |
| --- | --- |
| Rows (local) | 31 |
| Columns | 9 |
| ORM model | `ConsentRow` |
| Written / read by | `admin`, `consents`, `privacy` |
| Reaches | /admin/*, /guided/welcome, /app/profile, /privacy, /admin/privacy |
| Depends on | `founders` |
| Depended on by | — nothing — |

### 54. `privacy_requests`

DPDP rights requests -- access, correction, export -- and their handling state.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 12 |
| ORM model | `PrivacyRequests` |
| Written / read by | `admin`, `models`, `privacy`, `repositories` |
| Reaches | /admin/*, /app/profile, /privacy, /admin/privacy |
| Depends on | `founders` |
| Depended on by | — nothing — |

---

## Part G — Platform

Notifications, commerce and scheduling -- everything around the product rather than inside it.

### 55. `broadcast_reads`

Which founder has read which broadcast.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 3 |
| ORM model | **none — raw SQL only** |
| Written / read by | `admin` |
| Reaches | /admin/* |
| Depends on | `broadcasts`, `founders` |
| Depended on by | — nothing — |

### 56. `broadcasts`

Messages sent to many founders at once.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 11 |
| ORM model | **none — raw SQL only** |
| Written / read by | `admin` |
| Reaches | /admin/* |
| Depends on | — nothing — |
| Depended on by | `broadcast_reads` |

### 57. `calendar_connections`

Connected external calendars per founder.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 11 |
| ORM model | `CalendarConnectionRow` |
| Written / read by | `calendar_sync`, `notifications` |
| Reaches | /app/discovery-call, /app (global) |
| Depends on | `founders` |
| Depended on by | — nothing — |

### 58. `coupon_redemptions`

Which founder redeemed which coupon, and when.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 8 |
| ORM model | **none — raw SQL only** |
| Written / read by | `coupons` |
| Reaches | /app/billing, /admin/coupons |
| Depends on | `coupons`, `founders`, `payments` |
| Depended on by | — nothing — |

### 59. `coupons`

Discount coupons and their constraints.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 15 |
| ORM model | **none — raw SQL only** |
| Written / read by | `coupons` |
| Reaches | /app/billing, /admin/coupons |
| Depends on | — nothing — |
| Depended on by | `coupon_redemptions`, `payments` |

### 60. `credit_transactions`

The credit ledger -- every grant, spend and adjustment, so a balance can be explained rather than just read.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 10 |
| ORM model | `CreditTransactionRow` |
| Written / read by | `admin`, `credits` |
| Reaches | /admin/*, /app/billing, /admin/users/:id |
| Depends on | `founders` |
| Depended on by | — nothing — |

### 61. `direct_signup_capacity`

How many direct signups remain available, which is what the public signup gate reads.

| | |
| --- | --- |
| Rows (local) | 1 |
| Columns | 3 |
| ORM model | `DirectSignupCapacity` |
| Written / read by | `api/waitlist`, `models`, `services` |
| Reaches | /, /admin/waitlist |
| Depends on | — nothing — |
| Depended on by | — nothing — |

### 62. `discovery_calls`

Discovery call bookings, their slots and their status.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 21 |
| ORM model | `DiscoveryCalls` |
| Written / read by | `api/admin`, `api/dashboard`, `api/discovery`, `models`, `privacy`, `repositories`, `services` |
| Reaches | /admin/*, /app/journey, /app/discovery-call, /app/profile, /privacy, /admin/privacy |
| Depends on | `discovery_calls`, `founders` |
| Depended on by | `admin_notes`, `discovery_calls` |

### 63. `feature_flag_overrides`

Per-founder overrides of those flags, for staged rollout.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 5 |
| ORM model | **none — raw SQL only** |
| Written / read by | `admin` |
| Reaches | /admin/* |
| Depends on | `feature_flags`, `founders` |
| Depended on by | — nothing — |

### 64. `feature_flags`

Global feature flags.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 5 |
| ORM model | **none — raw SQL only** |
| Written / read by | `admin` |
| Reaches | /admin/* |
| Depends on | — nothing — |
| Depended on by | `feature_flag_overrides` |

### 65. `gateway_plans`

The payment gateway's own plan objects, mapped to our tiers. One row per (gateway, tier, amount, period) so an autopay subscription can be created against the right gateway plan without creating a duplicate each time. Added with autopay subscriptions in 5b8e2f4a7c19.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 6 |
| ORM model | **none — raw SQL only** |
| Written / read by | `payments` |
| Reaches | /app/billing |
| Depends on | — nothing — |
| Depended on by | — nothing — |

### 66. `launch_state`

The launch state machine -- armed, counting down, launched, aborted -- plus how many launches have run and how many are allowed.

| | |
| --- | --- |
| Rows (local) | 1 |
| Columns | 11 |
| ORM model | `LaunchStateRow` |
| Written / read by | `launch`, `models` |
| Reaches | /, /admin/launch |
| Depends on | — nothing — |
| Depended on by | — nothing — |

### 67. `notifications`

Notifications queued for or delivered to a founder.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 14 |
| ORM model | `Notifications` |
| Written / read by | `models`, `notifications`, `privacy`, `repositories`, `services` |
| Reaches | /app (global), /app/profile, /privacy, /admin/privacy |
| Depends on | `founders`, `notification_types` |
| Depended on by | — nothing — |

### 68. `payments`

Payment attempts and their outcomes.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 20 |
| ORM model | `Payments` |
| Written / read by | `core`, `models`, `payments`, `schemas` |
| Reaches | /app/billing |
| Depends on | `coupons`, `founders`, `subscriptions` |
| Depended on by | `coupon_redemptions` |

### 69. `plan_call_usage`

Calls consumed against a plan's allowance.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 4 |
| ORM model | **none — raw SQL only** |
| Written / read by | `plans` |
| Reaches | /app/plan, /app/billing |
| Depends on | `founders` |
| Depended on by | — nothing — |

### 70. `report_shares`

Share tokens for a report, so a founder can send their report to someone without that person having an account.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 10 |
| ORM model | `ReportShares` |
| Written / read by | `api/reasoning`, `api/reports`, `models` |
| Reaches | (server-side, feeds /app/report), /app/report, /app/business-dna |
| Depends on | `founders` |
| Depended on by | — nothing — |

### 71. `subscriptions`

A founder's plan subscription and its billing state.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 16 |
| ORM model | `Subscriptions` |
| Written / read by | `api/plans`, `admin`, `models`, `notifications`, `payments` |
| Reaches | /app/plan, /app/billing, /admin/*, /app (global) |
| Depends on | `founders` |
| Depended on by | `payments` |

### 72. `unbilled_usage`

Usage recorded but not yet billed.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 9 |
| ORM model | **none — raw SQL only** |
| Written / read by | `admin`, `plans` |
| Reaches | /admin/*, /app/plan, /app/billing |
| Depends on | — nothing — |
| Depended on by | — nothing — |

### 73. `waitlist_registrations`

Waitlist entries and their approval state.

| | |
| --- | --- |
| Rows (local) | 1 |
| Columns | 19 |
| ORM model | `WaitlistRegistration` |
| Written / read by | `api/admin`, `models`, `services` |
| Reaches | /admin/* |
| Depends on | — nothing — |
| Depended on by | — nothing — |

### 74. `waitlist_slot_openings`

Batches of waitlist slots opened by an admin.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 6 |
| ORM model | `WaitlistSlotOpening` |
| Written / read by | `models`, `services` |
| Reaches | — no screen — |
| Depends on | — nothing — |
| Depended on by | — nothing — |

---

## Part H — Admin and Operations

Staff-facing records and the operational telemetry behind the admin panel. Not founder-readable.

### 75. `admin_audit_log`

What staff did in the admin panel, append-only.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 13 |
| ORM model | **none — raw SQL only** |
| Written / read by | `admin` |
| Reaches | /admin/* |
| Depends on | — nothing — |
| Depended on by | — nothing — |

### 76. `admin_notes`

Staff notes on a founder. Never founder-readable.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 9 |
| ORM model | `AdminNotes` |
| Written / read by | `models` |
| Reaches | — no screen — |
| Depends on | `discovery_calls`, `founders` |
| Depended on by | — nothing — |

### 77. `analytics_events`

Product analytics events. Monthly partitioned.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 10 |
| ORM model | `AnalyticsEvent` |
| Written / read by | `models` |
| Reaches | — no screen — |
| Depends on | `founders` |
| Depended on by | — nothing — |

### 78. `founder_feedback`

Feedback founders submitted, with what they were looking at when they sent it.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 11 |
| ORM model | `FounderFeedback` |
| Written / read by | `api/feedback`, `admin`, `eval`, `models`, `privacy` |
| Reaches | /app/feedback, /admin/*, (offline, no screen), /app/profile, /privacy, /admin/privacy |
| Depends on | `founder_reports`, `founders`, `interventions`, `sessions` |
| Depended on by | — nothing — |

### 79. `llm_call_log`

Every LLM call: its task, model, token counts, measured latency and estimated cost. The only place real per-task latency and spend can be read.

| | |
| --- | --- |
| Rows (local) | 637 |
| Columns | 13 |
| ORM model | `LLMCallLog` |
| Written / read by | `admin`, `ai_chat`, `models`, `services` |
| Reaches | /admin/*, /app/ally-chat |
| Depends on | — nothing — |
| Depended on by | — nothing — |

**Fields worth knowing**

- `latency_ms` — Measured call latency. The source for any real latency figure in the API and LLM documents.
- `estimated_cost_usd` — Estimated cost of the call, summed for per-founder and per-task spend.

### 80. `support_bot_misses`

Questions the support bot could not answer, so the gap can be filled in `support_bot_answers`.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 6 |
| ORM model | **none — raw SQL only** |
| Written / read by | `api/admin` |
| Reaches | /admin/* |
| Depends on | `founders` |
| Depended on by | — nothing — |

### 81. `webhook_logs`

Inbound webhook deliveries and how each was handled.

| | |
| --- | --- |
| Rows (local) | 3 |
| Columns | 13 |
| ORM model | `WebhookLogs` |
| Written / read by | `api/webhooks`, `models` |
| Reaches | (inbound, no screen) |
| Depends on | `founders` |
| Depended on by | — nothing — |

---

## Part I — Diagnosis Engine

The live session and everything it produces. This is the USP: the session state, every graded answer, the reasoning output and the two reports built from it.

### 82. `answers`

Every answer a founder gave within a session, graded green, amber or red, with the interpretation behind the grade.

| | |
| --- | --- |
| Rows (local) | 552 |
| Columns | 14 |
| ORM model | `Answers` |
| Written / read by | `api/current_problem`, `api/diagnosis`, `api/founder_dna`, `api/reasoning`, `api/reports`, `models`, `privacy`, `support_bot` |
| Reaches | /app/current-problem, /app/diagnosis, /app/thinking, /app/founder-dna, /app/founder-dna-journey, (server-side, feeds /app/report), /app/report, /app/business-dna, /app/profile, /privacy, /admin/privacy, /app/help, /admin/* |
| Depends on | `founders`, `questions`, `root_causes`, `sessions` |
| Depended on by | — nothing — |

**Fields worth knowing**

- `grade` — Green, amber or red. Set by the interpretation engine, not by the founder.

### 83. `current_problem_answers`

Answers to the Current Problem flow.

| | |
| --- | --- |
| Rows (local) | 80 |
| Columns | 6 |
| ORM model | `CurrentProblemAnswers` |
| Written / read by | `api/current_problem`, `api/diagnosis`, `api/reports`, `models`, `privacy` |
| Reaches | /app/current-problem, /app/diagnosis, /app/thinking, /app/report, /app/business-dna, /app/profile, /privacy, /admin/privacy |
| Depends on | `current_problem_questions`, `founders` |
| Depended on by | — nothing — |

### 84. `detected_root_causes`

The final weighted root-cause ranking for a session.

| | |
| --- | --- |
| Rows (local) | 120 |
| Columns | 13 |
| ORM model | `DetectedRootCauses` |
| Written / read by | `api/diagnosis`, `api/reports`, `eval`, `models`, `privacy` |
| Reaches | /app/diagnosis, /app/thinking, /app/report, /app/business-dna, (offline, no screen), /app/profile, /privacy, /admin/privacy |
| Depends on | `founders`, `root_causes`, `sessions` |
| Depended on by | — nothing — |

### 85. `founder_dna_answers`

Answers to the Founder DNA questions, which is what resolves each of the fifteen dimensions.

| | |
| --- | --- |
| Rows (local) | 361 |
| Columns | 6 |
| ORM model | `FounderDnaAnswers` |
| Written / read by | `api/diagnosis`, `api/founder_dna`, `api/reasoning`, `models`, `privacy` |
| Reaches | /app/diagnosis, /app/thinking, /app/founder-dna, /app/founder-dna-journey, (server-side, feeds /app/report), /app/profile, /privacy, /admin/privacy |
| Depends on | `founder_dna_questions`, `founders` |
| Depended on by | — nothing — |

### 86. `founder_reports`

The founder-facing Clarity Report: scores, bands, narrative and the actions it recommends.

| | |
| --- | --- |
| Rows (local) | 15 |
| Columns | 22 |
| ORM model | `FounderReports` |
| Written / read by | `api/dashboard`, `api/feedback`, `api/reasoning`, `api/reports`, `admin`, `eval`, `models`, `notifications`, `privacy`, `quotes` |
| Reaches | /app/journey, /app/feedback, (server-side, feeds /app/report), /app/report, /app/business-dna, /admin/*, (offline, no screen), /app (global), /app/profile, /privacy, /admin/privacy |
| Depends on | `founders`, `sessions` |
| Depended on by | `founder_feedback`, `internal_intelligence_reports` |

**Fields worth knowing**

- `not_assessed_reason` — Why a pillar has no score: solo, stage, or thin evidence. Added so an unscored pillar shows the founder a reason instead of a blank card. NULL on reports generated before it existed, which falls back to the generic line rather than guessing.

### 87. `founder_visual_choices`

Answers to image-based questions. Defined and not yet in use.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 6 |
| ORM model | `FounderVisualChoices` |
| Written / read by | `models` |
| Reaches | — no screen — |
| Depends on | `founders`, `visual_question_bank` |
| Depended on by | — nothing — |

### 88. `internal_intelligence_reports`

The staff-only diagnostic layer for the same session. Locked from founders by design.

| | |
| --- | --- |
| Rows (local) | 15 |
| Columns | 14 |
| ORM model | `InternalIntelligenceReports` |
| Written / read by | `models` |
| Reaches | — no screen — |
| Depends on | `founder_reports`, `founders`, `sessions` |
| Depended on by | — nothing — |

### 89. `session_context_facts`

Things learned about a founder DURING this session only -- for example that a team question does not apply to them. Deliberately never written back to `founders`: it affects question selection for this session and nothing beyond it.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 6 |
| ORM model | **none — raw SQL only** |
| Written / read by | — no reference found — |
| Reaches | — no screen — |
| Depends on | — nothing — |
| Depended on by | — nothing — |

### 90. `sessions`

One diagnosis session: its state, stage, progress and answered count. The row the engine reads to decide what to ask next.

| | |
| --- | --- |
| Rows (local) | 23 |
| Columns | 24 |
| ORM model | `Sessions` |
| Written / read by | `api/dashboard`, `api/diagnosis`, `api/feedback`, `api/reports`, `admin`, `eval`, `models`, `notifications`, `privacy` |
| Reaches | /app/journey, /app/diagnosis, /app/thinking, /app/feedback, /app/report, /app/business-dna, /admin/*, (offline, no screen), /app (global), /app/profile, /privacy, /admin/privacy |
| Depends on | `founder_stages`, `founders`, `industries`, `questions` |
| Depended on by | `answers`, `detected_root_causes`, `founder_feedback`, `founder_reports`, `internal_intelligence_reports`, `rag_retrieval_log`, `stage_assessments` |

**Fields worth knowing**

- `questions_answered_count` — Derived from the answer rows when an answer is submitted. The opening block reads this to decide how long to reserve questions for under-covered pillars.
- `session_state_at_generation` — The session's state when the report was built, frozen so a later change cannot silently rewrite what the report was based on.

### 91. `stage_assessments`

Stage classification for a session, with history, so a re-assessment does not erase the earlier reading.

| | |
| --- | --- |
| Rows (local) | 6 |
| Columns | 9 |
| ORM model | `StageAssessments` |
| Written / read by | `api/dashboard`, `models`, `privacy` |
| Reaches | /app/journey, /app/profile, /privacy, /admin/privacy |
| Depends on | `founder_stages`, `founders`, `sessions` |
| Depended on by | — nothing — |

---

## Part J — Planning, Goals and Vision

What the founder does with the report: plans, goals, tasks, reminders and the longer-range vision work.

### 92. `achievements`

Achievements a founder has unlocked.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 8 |
| ORM model | `AchievementRow` |
| Written / read by | `achievements` |
| Reaches | /app/achievements |
| Depends on | `founders` |
| Depended on by | — nothing — |

### 93. `daily_actions`

Plan Your Day: the daily action list, its priorities, due dates and completion.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 14 |
| ORM model | `DailyActions` |
| Written / read by | `api/dashboard`, `models` |
| Reaches | /app/journey |
| Depends on | `founders`, `interventions` |
| Depended on by | — nothing — |

### 94. `founder_daily_quotes`

The two pre-written lines picked for a founder each night.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 6 |
| ORM model | **none — raw SQL only** |
| Written / read by | `quotes` |
| Reaches | /app/journey |
| Depends on | `founders` |
| Depended on by | — nothing — |

### 95. `founder_goals`

Founder-level goals held outside the plan structure.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 7 |
| ORM model | `FounderGoalRow` |
| Written / read by | `founder_goals` |
| Reaches | /app/goals |
| Depends on | `founders` |
| Depended on by | — nothing — |

### 96. `framework_usage`

Which frameworks a founder has used, for relevance ranking.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 4 |
| ORM model | `FrameworkUsageRow` |
| Written / read by | `framework_usage` |
| Reaches | /app/frameworks |
| Depends on | `founders` |
| Depended on by | — nothing — |

### 97. `planning_goals`

Goals within a plan.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 12 |
| ORM model | `GoalRow` |
| Written / read by | `notifications`, `planning`, `privacy` |
| Reaches | /app (global), /app/next-steps, /app/goals, /app/profile, /privacy, /admin/privacy |
| Depends on | `planning_plans` |
| Depended on by | `planning_tasks` |

### 98. `planning_plans`

A plan a founder is working to. Can be seeded from a diagnosis.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 7 |
| ORM model | `PlanRow` |
| Written / read by | `planning`, `privacy` |
| Reaches | /app/next-steps, /app/goals, /app/profile, /privacy, /admin/privacy |
| Depends on | `founders` |
| Depended on by | `planning_goals` |

### 99. `planning_reminders`

Reminders attached to a task.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 12 |
| ORM model | `ReminderRow` |
| Written / read by | `planning` |
| Reaches | /app/next-steps, /app/goals |
| Depends on | `planning_tasks` |
| Depended on by | — nothing — |

### 100. `planning_tasks`

Tasks under a goal, with their status and due dates.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 16 |
| ORM model | `TaskRow` |
| Written / read by | `notifications`, `planning`, `privacy` |
| Reaches | /app (global), /app/next-steps, /app/goals, /app/profile, /privacy, /admin/privacy |
| Depends on | `planning_goals` |
| Depended on by | `planning_reminders` |

### 101. `suggestion_feedback`

Whether a suggestion landed, used to improve later ones.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 6 |
| ORM model | `SuggestionFeedbackRow` |
| Written / read by | `ai_chat`, `models` |
| Reaches | /app/ally-chat |
| Depends on | `founders`, `suggestions` |
| Depended on by | — nothing — |

### 102. `suggestions`

Suggestions generated for a founder, with the reasoning behind each.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 18 |
| ORM model | `SuggestionRow` |
| Written / read by | `ai_chat`, `models`, `notifications` |
| Reaches | /app/ally-chat, /app (global) |
| Depends on | `conversations`, `founders` |
| Depended on by | `suggestion_feedback` |

### 103. `vision_summary`

The synthesised output of that exercise.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 5 |
| ORM model | `VisionSummaryRow` |
| Written / read by | `vision` |
| Reaches | /app/vision |
| Depends on | `founders` |
| Depended on by | — nothing — |

### 104. `vision_territories`

The territories of the Vision exercise.

| | |
| --- | --- |
| Rows (local) | 0 |
| Columns | 9 |
| ORM model | `VisionTerritoryRow` |
| Written / read by | `vision` |
| Reaches | /app/vision |
| Depends on | `founders` |
| Depended on by | — nothing — |

---

## Part K — Schema Management

Not application data. Listed for completeness because it exists in every environment and is the first thing to check when two databases disagree.

### 105. `alembic_version`

The single row naming the migration revision this database is at. The first thing to compare when two environments disagree.

| | |
| --- | --- |
| Rows (local) | 1 |
| Columns | 1 |
| ORM model | **none — raw SQL only** |
| Written / read by | — no reference found — |
| Reaches | — no screen — |
| Depends on | — nothing — |
| Depended on by | — nothing — |

---

## Access and Row Level Security

The previous version of this document stated that RLS was enabled on all 47 tables. That is no longer the position, and the position now **differs by environment** — so this section reports what was measured, where, rather than a single claim.

Measured on the local database at `5b8e2f4a7c19`:

| | Count |
| --- | --: |
| Tables with RLS enabled | 40 of 104 |
| Policies defined | 30 across 29 tables |
| **RLS enabled with no policy (deny-all)** | 11 |

### The deny-all tables, and why they are probably not a bug

These eleven have RLS switched on and no policy, which in Postgres means deny by default — every `SELECT` returns zero rows and every write fails:

`admin_audit_log`, `alembic_version`, `broadcasts`, `coupon_redemptions`, `coupons`, `feature_flags`, `model_task_routing`, `notification_types`, `revoked_tokens`, `support_bot_answers`, `support_bot_misses`

**This is a local artefact, not a production finding.** Several migrations create their policies conditionally, because `CREATE POLICY ... TO <role>` errors when the role does not exist, while `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` is unconditional. None of `ally_app`, `authenticated`, `anon` or `service_role` exists in this database, so the policies were skipped and the enable was not. Migration `a2d5f74c8e13` documents this exact mechanism, which caused a production sign-up outage on `waitlist_registrations` and was fixed by creating those policies `FOR PUBLIC` instead.

**It does mean RLS cannot be verified from this database.** Two things follow. Production has the roles, so its policies will have been created — but that should be confirmed, not assumed. And the Supabase database shows the *opposite* problem: six tables there have RLS **disabled** entirely (`support_bot_answers`, `support_bot_misses`, `coupons`, `coupon_redemptions`, `notification_types`, `_perf_baseline`), which Supabase itself flags as critical because anyone holding the anon key can read or write every row. Enabling RLS on them without writing policies first would reproduce the outage above, so each needs a policy designed before the switch is thrown.

### The founder-scoping pattern

Where policies do exist, most follow one shape: the row is visible when its `founder_id` matches the caller's, resolved through a helper function rather than repeated in each policy. Three groups sit outside that pattern:

- **Staff-only, no founder-facing policy** — `admin_notes`, `admin_audit_log`, `internal_intelligence_reports`, `webhook_logs`, `llm_call_log`. A founder cannot read these by any route.
- **Read-only for the founder** — `detected_root_causes` and the other reasoning outputs. A founder may see their diagnosis results and cannot alter them.
- **Reference data** — everything in Part A. Read-only for everyone at runtime; written only by migrations.

## Appendix A — How the mapping was derived, and where it is weak

The **Owned by** and **Reaches** columns are derived from the source by `scripts/docs/extract_usage.py`, over 572 Python files. A table is reported as used by an area only because the source shows it: either the table name in SQL context (after `FROM`, `JOIN`, `INTO`, `UPDATE`, `DELETE FROM`, or in a `__tablename__`), or the name of the ORM class bound to it.

**Why not a simple name search.** The first version of this script searched for the table's name as a whole word, and the result was unusable: `answers` matched `api/payments`, `sessions` matched `api/auth` — which is auth sessions, an unrelated thing — and `questions`, `problems`, `messages` and `notifications` matched much of the codebase, because they are ordinary English words that appear in comments. It also under-matched: `planning_tasks` came back touched by nothing, because that module refers to it only through its ORM class. A keyword screen was wrong in both directions at once, which is the same lesson the question bank taught three times.

**Two weaknesses remain, stated rather than hidden.** A table reached by some third route — dynamic SQL, a name built at runtime — is missed. And **Reaches** lists screens whose area touches the table at all, including indirectly: `planning_tasks` lists `/privacy` because the deletion executor must clear it, not because anything is displayed there. Treat the column as *where this data is involved*, not *where it is shown*.

**5 tables matched nothing at all**: `alembic_version`, `founder_dimension_profile`, `founder_dimensions`, `session_context_facts`, `support_bot_answers`. Of those, `alembic_version` is Alembic's own, `founder_dimensions` and `founder_dimension_profile` are superseded, and `session_context_facts` and `support_bot_answers` are reached in ways this method does not see — both are live.

## Appendix B — Entities with no ORM model

24 of 105 tables have no SQLAlchemy model and are reached only by raw SQL. Listed in the ER document's Appendix B. The one to look at first is `question_industry_mapping`: 3,630 rows, core to industry question selection, and no model to type-check a change against.

