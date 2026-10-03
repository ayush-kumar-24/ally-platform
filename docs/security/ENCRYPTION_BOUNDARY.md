# Encryption Boundary

Part of the Day 1 security design package. Tags are defined in [DATA_CLASSIFICATION.md](DATA_CLASSIFICATION.md). The key domains used below (`profile`, `chat`, …) are defined in [KEY_MANAGEMENT_DESIGN.md](KEY_MANAGEMENT_DESIGN.md) §3.

## 1. Classes

| Class | Meaning |
|---|---|
| **APP-ENCRYPT** | AES-256-GCM in the application via the Day 2 encryption service. The ciphertext is stored in the DB or S3. The DB never sees plaintext. |
| **KEEP-PLAINTEXT** | Stays plaintext. It is needed for joins, RLS, filtering or uniqueness, or it is not sensitive. It is still covered by infrastructure encryption. |
| **HASH** | A one-way keyed hash (HMAC-SHA256 with the `index` key). The plaintext is never stored. Used for credentials looked up by value. |
| **BLIND-INDEX** | APP-ENCRYPT for the value, plus an HMAC column for equality lookup. |
| **INFRASTRUCTURE-ENCRYPTION-ONLY** | Relies on RDS/S3 KMS at-rest encryption, which is `[UNKNOWN]` and must be verified ([DAY1_SECURITY_DECISIONS.md](DAY1_SECURITY_DECISIONS.md) §J). |
| **PRODUCT-DECISION** | The choice changes product behaviour such as search or login. It is blocked on a decision. |
| **UNKNOWN** | Usage could not be fully established from the repo. Verify before Day 3. |

`[CODE]` Today only `calendar_connections.access_token_encrypted` and `refresh_token_encrypted` are app-encrypted (Fernet, `app/calendar_sync/crypto.py`).

## 2. Field decisions

### `founders` (L1)

| Column | Class | Domain | Why / constraint `[CODE]` |
|---|---|---|---|
| `founder_id` | KEEP-PLAINTEXT | — | PK, owner key everywhere |
| `user_id` | KEEP-PLAINTEXT | — | `get_founder_id()` resolves RLS from it; every policy depends on it (migrations `bec1d5b06eac`, `d91c6e4b72aa`) |
| `cognito_sub` | KEEP-PLAINTEXT | — | UNIQUE, looked up by value (`link_cognito_founder`) |
| `email` | **PRODUCT-DECISION (D-12)** | `profile` | Used by: UNIQUE `founders_email_key`; `lower(email)` in `link_cognito_founder`; `get_by_email`; admin `ilike` search (`admin/users_db_repository.py:159`); admin role and team plan resolution (`panel_dependencies.py`, `plans/team.py`); written in plaintext by SECURITY DEFINER `create_founder_on_signup`. **Option A** (recommended for Day 3): KEEP-PLAINTEXT, and remove email from role/plan resolution (D-60). **Option B**: BLIND-INDEX (`email_bidx = HMAC(lower(trim(email)))`). This requires rewriting `create_founder_on_signup` and `link_cognito_founder`, plus exact-match-only admin search. |
| `full_name` | APP-ENCRYPT | `profile` | Admin `ilike` search on name is dropped. Admin search becomes exact email / `founder_id` (D-13). |
| `phone`, `business_name` | APP-ENCRYPT | `profile` | Drop them from admin `ilike` search (D-13) |
| `linkedin_url`, `website`, `social_profiles` | APP-ENCRYPT | `profile` | Read in Python only |
| `avatar_url`, `avatar_storage_path` | KEEP-PLAINTEXT | — | Object keys only. The object itself is INFRASTRUCTURE-ENCRYPTION-ONLY plus authenticated serving (D-35). |
| `stage_id`, `industry`, `industry_mapped_id` | KEEP-PLAINTEXT | — | SQL joins and filters (`quotes/service.py:168`, `dashboard/repository.py:110`, `ally/rag/sql_repository.py:101`) |
| `team_size`, `current_revenue`, `business_model`, `customer_segment`, `current_challenges` | APP-ENCRYPT | `profile` | Read into Python (`diagnosis/founder_brief.py`, scope gates). `quotes/service.py:168` selects `current_challenges`, which is fine because it is decrypted in the app. **UNKNOWN**: confirm no SQL predicate on them (grep found none). |
| `building_summary`, `product_description`, `problem_statement`, `founder_motivation`, `goal_90_day`, `vision_1_year`, `customer_segment_other`, `current_challenges_other`, `adaptive_reflection` | APP-ENCRYPT | `profile` | Free text. `complete_onboarding` (DB function) writes some of these; the code says it is unused (`repositories/founder.py:90`). **UNKNOWN**: confirm, then drop the function. |
| `emotional_state`, `founder_reality_signals`, `business_reality_signals`, `invisible_gaps`, `decision_making_style`, `working_relationship`, `support_preferences`, `experience_level` | APP-ENCRYPT | `profile` | S4 / S3 |
| `first_impression` | APP-ENCRYPT | `profile` | LLM output about the founder |
| `admin_notes` | APP-ENCRYPT | `support` | Never exported to the founder (D-37) |
| `plan_type`, `status`, credits columns, `notification_preferences` | KEEP-PLAINTEXT | — | Entitlement and operations |
| `deletion_*`, `processing_restricted_at`, `data_retention_expires_at`, `consent_version`, `last_active_at`, timestamps | KEEP-PLAINTEXT | — | Lifecycle predicates |

### Context and onboarding answers

| Table.column | Class | Domain | Note |
|---|---|---|---|
| `founder_context.economic_background`, `education_level`, `geographic_type`, `language_comfort`, `network_access`, `context_notes` | APP-ENCRYPT | `profile` | S4 |
| `founder_dna_answers.answer_text` | APP-ENCRYPT | `diagnosis` | UQ is on (`founder_id`, `question_id`), not on the text, so this is safe |
| `current_problem_answers.answer_text` | APP-ENCRYPT | `diagnosis` | same |
| `founder_visual_choices.*` | KEEP-PLAINTEXT | — | Reference ids. **UNKNOWN**: confirm there is no free text. |

### Diagnosis and reports (L4)

| Table.column | Class | Domain | Note |
|---|---|---|---|
| `answers.answer_text` | APP-ENCRYPT | `diagnosis` | UQ `uq_answers_session_question` is on ids |
| `answers.score`, `score_label`, `is_distress_flagged`, `question_id`, `session_id` | KEEP-PLAINTEXT | — | Scoring pipeline reads and aggregates |
| `sessions.session_distress_score`, `distress_mode_triggered`, `session_state`, `routing_state`, `category_risk_scores`, `training_notes` | APP-ENCRYPT | `diagnosis` | **UNKNOWN**: confirm no SQL predicate on `distress_mode_triggered` and `routing_state` (admin metrics / reconcile sweep). If one exists, keep a plaintext boolean only. |
| `sessions.status`, `current_question_id`, `completed_at`, `overall_confidence_score`, `founder_stage_id`, `founder_industry_id` | KEEP-PLAINTEXT | — | Used by `get_active_session_for_founder` and the reconcile job |
| `detected_root_causes.*` | KEEP-PLAINTEXT | — | Ids and scores against reference `root_causes`. Sensitivity comes from the founder link, which is protected by access control. |
| `stage_assessments.assessment_basis` | APP-ENCRYPT | `diagnosis` | Other columns stay plaintext |
| `founder_reports.summary`, `insights`, `founder_dna`, `business_dna`, `narrative_snapshot`, `session_state_at_generation`, action columns, `title` | APP-ENCRYPT (JSONB is stored as encrypted JSON text) | `report` | Encrypted as a **single envelope per column** |
| `founder_reports.business_dna->>'band'` | KEEP-PLAINTEXT via a new projection column `business_health_band` (D-14) | — | `[CODE]` `dashboard/repository.py:94` filters in SQL |
| `founder_reports.business_dna->'red_flags'` | APP-ENCRYPT; decrypt in the app | `report` | `[CODE]` `quotes/service.py:182` must move from SQL to Python. Only the count or flag is needed. |
| `founder_reports.is_active`, `report_version` (new), `pdf_storage_key`, `pdf_requested_at`, ids | KEEP-PLAINTEXT | — | |
| `internal_intelligence_reports.psychological_state`, `distress_signals`, `internal_notes`, blind-spot and pattern ids | APP-ENCRYPT (ids KEEP-PLAINTEXT) | `report` | S4 |
| S3 `reports/{report_id}/clarity-report.pdf` | APP-ENCRYPT (body) + bucket SSE-KMS | `report` | `[CODE]` `pdf_delivery.py` stores raw bytes |
| `report_shares.share_token` | **HASH** (`share_token_hash`) | `index` | Looked up by exact value, which a hash supports. The raw token is shown once at creation. `share_url` is no longer stored; it is rebuilt from config at creation time only (D-31). |
| `founder_feedback.outcome_text`, `outcome_metrics` | APP-ENCRYPT | `support` | |

### Raw chat (L2)

| Table.column | Class | Domain | Note |
|---|---|---|---|
| `messages.content` | APP-ENCRYPT | `chat` | `[CODE]` DB trigger `increment_message_count` does not read content |
| `messages.metadata` | KEEP-PLAINTEXT, but it must not hold content | — | It holds provider, model, tokens, `request_id` and `memory_opt_out`. Assert no free text. |
| `messages.ai_reasoning` | APP-ENCRYPT (unused today) | `chat` | |
| `conversations.title` | APP-ENCRYPT | `chat` | Titles are derived from the message (RC-7) |
| `conversations.external_id`, `status`, `message_count`, `last_message_at`, `token_stats` | KEEP-PLAINTEXT | — | API ids and lifecycle |
| `file_uploads.content` (BYTEA) | APP-ENCRYPT | `chat` | |
| S3 `attachments/{fid}/{attachment_id}.{ext}` | APP-ENCRYPT (body) + bucket SSE-KMS | `chat` | |
| `file_uploads.file_name` | APP-ENCRYPT | `chat` | File names leak content |
| `file_uploads.checksum` | **PRODUCT-DECISION** | — | sha256 of plaintext, which leaks equality across founders. Proposal: change to `HMAC(index_key, founder_id‖bytes)` or drop it. **UNKNOWN**: confirm it is used for de-duplication only. |
| `file_uploads.file_type`, `storage_path`, `status`, `external_id` | KEEP-PLAINTEXT | — | |
| `suggestions.*`, `suggestion_feedback.note` | KEEP-PLAINTEXT / APP-ENCRYPT (`note`) | `support` | Suggestions are templated text |

### Memory (L3)

| Table.column | Class | Domain | Note |
|---|---|---|---|
| `founder_memory.content` | APP-ENCRYPT | `memory` | |
| `founder_memory.memory_id` | Becomes a random id (D-55 M2) | — | Today it is sha256(content), which leaks equality |
| rejected-proposal fingerprint | BLIND-INDEX (HMAC only) | `index` | [MEMORY_CONTRACT.md](MEMORY_CONTRACT.md) §4 |
| `founder_memory.tags`, `key`, `memory_kind`, `status`, `confidence`, `expires_at`, source ids | KEEP-PLAINTEXT | — | Filtering. `tags` must not hold content. |
| `founder_memory_events.*` | KEEP-PLAINTEXT | — | Must never hold content |

### Workspace (W)

| Table.column | Class | Domain |
|---|---|---|
| `planning_plans/goals/tasks/reminders` title, description and note columns | APP-ENCRYPT. **UNKNOWN**: task titles are used in reminder emails (`task_reminders.py`); decryption happens in the job, which is fine. | `workspace` |
| `founder_goals`, `achievements` free text | APP-ENCRYPT | `workspace` |
| `vision_territories.statement`, `vision_summary` text | APP-ENCRYPT | `workspace` |
| `framework_usage.note` | APP-ENCRYPT | `workspace` |
| `founder_dimension_profile.display_value` | APP-ENCRYPT | `workspace` |
| `vision_territories.image_*`, S3 `attachments/vision/...` | KEEP-PLAINTEXT (keys) / INFRASTRUCTURE-ENCRYPTION-ONLY (objects) | — |

### Integrations, support and operational

| Table.column | Class | Domain | Note |
|---|---|---|---|
| `calendar_connections.access_token_encrypted`, `refresh_token_encrypted` | APP-ENCRYPT (migrate from Fernet, [KEY_MANAGEMENT_DESIGN.md](KEY_MANAGEMENT_DESIGN.md) §8) | `integration` | |
| `calendar_connections.account_email` | APP-ENCRYPT | `integration` | |
| `calendar_connections.last_error` | KEEP-PLAINTEXT, **truncated and redacted** to the exception class + Google error code | — | Today it stores `str(exc)` |
| `support_bot_misses.question` | APP-ENCRYPT | `support` | |
| `notifications.body` | APP-ENCRYPT. **UNKNOWN**: confirm no SQL search; the `send_notification` DB function writes `body` in plaintext and must be updated or retired. | `support` |
| `discovery_calls.notes_pre_call`, `notes_post_call`; `admin_notes.note_content` | APP-ENCRYPT | `support` |
| `privacy_requests.request_details`, `processing_notes` | APP-ENCRYPT | `support` | Can hold the new email address |
| `consents`, `consent_history`, `founder_consents`, `cookie_preferences` (`ip_address`, `browser`) | INFRASTRUCTURE-ENCRYPTION-ONLY (+ scrub on erasure) | — | `ip_address` is NOT NULL (the scrub sentinel is `[CODE]`) |
| `audit_logs.action_details`, `admin_audit_log.old_value/new_value` | INFRASTRUCTURE-ENCRYPTION-ONLY; must not store email or content (D-36) | — | |
| `webhook_logs.payload` | INFRASTRUCTURE-ENCRYPTION-ONLY; store a minimised payload (D-34) | — | |
| `payments`, `subscriptions`, `credit_transactions`, `coupon_redemptions` | INFRASTRUCTURE-ENCRYPTION-ONLY | — | Ledger; `[PRODUCT/LEGAL DECISION]` on retention |
| `llm_call_log.*` | KEEP-PLAINTEXT; `error` is redacted (D-62) | — | |
| `rag_retrieval_log.query_text` | **PRODUCT-DECISION**: stop writing it, or APP-ENCRYPT. **UNKNOWN**: no live writer was found. | `chat` |
| `analytics_events.properties` | KEEP-PLAINTEXT; must not hold content | — | |
| `waitlist_registrations.*` | INFRASTRUCTURE-ENCRYPTION-ONLY | — | Pre-account. Email UNIQUE and looked up by value. |
| `revoked_tokens.jti` | KEEP-PLAINTEXT | — | A random id |
| `webhook_logs.gateway_event_id`, `notifications.dedup_key`, `conversations.external_id` | KEEP-PLAINTEXT | — | Non-secret ids |

## 3. What app-level encryption does not cover

1. **Already-plaintext copies.** Backups taken before the cut-over; the old Supabase database (`[UNKNOWN]`, §J); CloudWatch logs; Sentry events; LLM provider retention.
2. **DB functions.** Any DB function that writes or reads an APP-ENCRYPT column in SQL must be rewritten or retired before that column is encrypted: `create_founder_on_signup`, `complete_onboarding`, `send_notification`, `start_conversation`. Day 3 must check each one.
3. **Searching.** Encrypted columns cannot be searched with `ilike`. Admin search is reduced to exact email (or its blind index) and `founder_id` (D-13).

## 4. Column layout rule for Day 3 `[DECISION D-15]`

- **New column, not in-place.** Each APP-ENCRYPT column gets a sibling `<column>_enc` (Text, the envelope string from [KEY_MANAGEMENT_DESIGN.md](KEY_MANAGEMENT_DESIGN.md) §5). The plaintext column is dropped in a later migration once backfill shows 0 plaintext rows.
- **Reads during the transition.** Prefer `_enc`, fall back to plaintext, and emit a counter metric for every fallback (never the value).
- **JSONB columns** are encrypted whole, as a serialised JSON string. Any key needed in SQL gets a dedicated plaintext projection column (D-14).
