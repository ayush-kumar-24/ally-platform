# Data Classification

Part of the Day 1 security design package. Index and decision register: [DAY1_SECURITY_DECISIONS.md](DAY1_SECURITY_DECISIONS.md).

## Tags used across this package

| Tag | Meaning |
|---|---|
| `[CODE]` | What the repo does today (as of commit `78f7655`). |
| `[DECISION]` | A proposed engineering, product or security decision, identified as `D-xx`. |
| `[UNKNOWN]` | Needs confirmation of infrastructure or product facts. |
| `[PRODUCT/LEGAL DECISION]` | We will not choose the value. A named owner must sign it off. |

Paths are relative to `backend/`.

## 1. Data layers `[DECISION D-01]`

Every founder-related column belongs to exactly one layer. The layer sets the defaults below; per-class exceptions are listed in §3.

| Layer | Name | Lifetime | Default protection | Default retention |
|---|---|---|---|---|
| **L1** | Account and onboarding | Persistent | DB/infrastructure encryption. App-encrypt free text and personal fields | Life of the account |
| **L2** | Raw chat (conversations, messages, attachments) | **Temporary** | App-encrypt | `RAW_CHAT_RETENTION_DAYS` (see [DATA_LIFECYCLE.md](DATA_LIFECYCLE.md)) |
| **L3** | Founder memory (structured) | Persistent | App-encrypt | Until the founder deletes it, or the per-kind expiry |
| **L4** | Diagnosis and reports | Persistent and versioned | App-encrypt | Life of the account |
| **W** | Founder workspace (planning, goals, achievements, vision, frameworks) | Persistent | App-encrypt free text | Life of the account |
| **X** | Integration secrets (OAuth tokens) | Persistent | App-encrypt (already done for calendar, `[CODE]`) | Until disconnect or erasure |
| **O** | Operational, ledger and audit (billing, consents, audit, webhooks, usage, telemetry) | Persistent | Infrastructure only, plus scrubbing | Per [RETENTION_AND_ERASURE_POLICY.md](RETENTION_AND_ERASURE_POLICY.md) |
| **R** | Reference (question banks, root_causes, archetypes, rag_chunks, model_task_routing) | Persistent | None needed | n/a, not founder data |

## 2. Sensitivity levels `[DECISION D-02]`

| Level | Meaning | Examples |
|---|---|---|
| **S4 Special** | Mental-state, distress or socio-economic inference about a person | `internal_intelligence_reports.*`, `sessions.session_distress_score`, `founders.emotional_state`, `founder_context.economic_background` |
| **S3 Confidential** | The founder's own words and business content, and anything derived from them | `answers.answer_text`, `messages.content`, `founder_reports.*`, `founders.problem_statement` |
| **S2 Personal** | Identifies or contacts a person | `founders.email`, `full_name`, `phone`, `linkedin_url`, `consents.ip_address`, avatars |
| **S1 Internal** | Operational metadata with no content | `llm_call_log` (excluding `error`), usage counters, `revoked_tokens.jti` |
| **SECRET** | A credential or capability | `calendar_connections.*_token_encrypted`, `report_shares.share_token`, refresh cookie |

## 3. Classification table

**Column abbreviations:**
- **T/P:** T = temporary, P = persistent.
- **Enc:** the encryption class, defined in [ENCRYPTION_BOUNDARY.md](ENCRYPTION_BOUNDARY.md).
- **Owner:** the owner key. `fid` = `founder_id`. The founder is always derived from the token via `app/api/deps.py:get_founder_record` (`[CODE]`).

**Delete:** what happens on account erasure. Per-table detail is in the retention policy.

**LLM / Memory / Logs:** whether the data may go to an LLM, enter memory, or appear in logs.
- **Y:** allowed.
- **N:** forbidden.
- **Y\*:** allowed only in the restricted form given in [LLM_DATA_BOUNDARY.md](LLM_DATA_BOUNDARY.md).
- **Ref:** only as an opaque identifier, never the content.

| # | Data class | Tables.columns | Layer | T/P | Sens | Enc | Owner | Retention | Delete | LLM | Memory | Logs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Login identity | `founders.user_id`, `cognito_sub` | L1 | P | S2 | KEEP-PLAINTEXT | PK | account | Anonymise: user_id becomes a tombstone UUID; IdP user deleted | N | N | N (log `founder_id` only) |
| 2 | Email | `founders.email` | L1 | P | S2 | PRODUCT-DECISION (D-12) | PK | account | Anonymise | N | N | N |
| 3 | Name | `founders.full_name` | L1 | P | S2 | APP-ENCRYPT | PK | account | Anonymise | Y\* (first name only) | N | N |
| 4 | Contact and social | `founders.phone`, `business_name`, `linkedin_url`, `website`, `social_profiles` | L1 | P | S2 | APP-ENCRYPT | PK | account | Null | N | N | N |
| 5 | Avatar | `founders.avatar_url`, `avatar_storage_path`; S3 `attachments/avatars/{fid}/…` | L1 | P | S2 | INFRASTRUCTURE-ENCRYPTION-ONLY plus authenticated serving | fid | account | Null columns, delete the object | N | N | N (filenames are capabilities) |
| 6 | Business profile (structured) | `founders.stage_id`, `industry`, `industry_mapped_id` | L1 | P | S3 | KEEP-PLAINTEXT (used in SQL joins and filters, `[CODE]` `quotes/service.py:168`, `dashboard/repository.py:110`) | PK | account | Retain on the tombstone (not identifying; see retention policy §3) | Y | Y (as context) | N |
| 7 | Business profile (bands) | `founders.team_size`, `current_revenue`, `business_model`, `customer_segment`, `current_challenges` | L1 | P | S3 | APP-ENCRYPT (read in Python only, `[CODE]`) | PK | account | Null | Y | Y | N |
| 8 | Onboarding free text | `founders.building_summary`, `product_description`, `problem_statement`, `founder_motivation`, `goal_90_day`, `vision_1_year`, `customer_segment_other`, `current_challenges_other`, `adaptive_reflection` | L1 | P | S3 | APP-ENCRYPT | PK | account | Null | Y | Y (founder-entered source, see Memory Contract) | N |
| 9 | Self-assessment / psych | `founders.emotional_state`, `founder_reality_signals`, `business_reality_signals`, `invisible_gaps`, `decision_making_style`, `working_relationship`, `support_preferences`, `experience_level` | L1 | P | **S4** | APP-ENCRYPT | PK | account | Null | Y\* (diagnosis and chat tone only) | N | N |
| 10 | Socio-economic context | `founder_context.*` | L1 | P | **S4** | APP-ENCRYPT | fid | account | Delete | Y\* (diagnosis only) | N | N |
| 11 | LLM first impression | `founders.first_impression` | L1 | P | S3 | APP-ENCRYPT | PK | account | Null | N (it is an LLM output; never re-sent) | N | N |
| 12 | Founder DNA answers | `founder_dna_answers.answer_text` | L4 | P | S3 | APP-ENCRYPT | fid | account | Delete | Y | N (only via an extracted, confirmed memory) | N |
| 13 | Current Problem answers | `current_problem_answers.answer_text` | L4 | P | S3 | APP-ENCRYPT | fid | account | Delete | Y | N | N |
| 14 | Diagnosis answers | `answers.answer_text` (+ `score`, `score_label`) | L4 | P | S3 | APP-ENCRYPT (text); KEEP-PLAINTEXT (score, label) | fid | account | Delete | Y | N | N |
| 15 | Session state and distress | `sessions.session_distress_score`, `distress_mode_triggered`, `session_state`, `routing_state`, `category_risk_scores`, `training_notes` | L4 | P | **S4** | APP-ENCRYPT (distress, state, notes); KEEP-PLAINTEXT (`status`, timestamps, `overall_confidence_score`) | fid | account | Delete | Y\* (distress routing only) | N | N |
| 16 | Root causes / stage | `detected_root_causes.*`, `stage_assessments.*` | L4 | P | S3 | KEEP-PLAINTEXT (ids and scores against reference tables); APP-ENCRYPT `stage_assessments.assessment_basis` | fid | account | Delete | Y | N | N |
| 17 | Founder report | `founder_reports.summary`, `insights`, `founder_dna`, `business_dna`, `narrative_snapshot`, `session_state_at_generation`, actions | L4 | P | S3/S4 | APP-ENCRYPT (+ plaintext projection of `business_dna.band`, D-14) | fid | account; versioned | Delete | Y\* | Y (diagnosis summary only, as a system memory) | N |
| 18 | Internal intelligence | `internal_intelligence_reports.psychological_state`, `distress_signals`, `internal_notes` | L4 | P | **S4** | APP-ENCRYPT | fid | account | Delete | **N** for chat; Y\* for the reasoning pipeline that produces it | N | N |
| 19 | Report PDF | S3 `reports/{report_id}/clarity-report.pdf`; `founder_reports.pdf_storage_key` | L4 | P | S3/S4 | APP-ENCRYPT the object body + bucket SSE-KMS | fid | same as its report row | Delete the object | N | N | N |
| 20 | Share link | `report_shares.share_token`, `share_url` | L4 | P | SECRET | HASH (token); drop `share_url` storage | fid | 30 days (`[CODE]`) | Delete | N | N | **Never** (D-31) |
| 21 | Raw chat | `conversations.title`, `metadata`; `messages.content`, `metadata` | **L2** | **T** | S3/S4 | APP-ENCRYPT | fid | `RAW_CHAT_RETENTION_DAYS` | Hard delete | Y (own conversation only) | **N** (only via extraction, see Memory Contract) | N |
| 22 | Attachments | `file_uploads.content` (BYTEA), S3 `attachments/{fid}/{id}.{ext}`, `file_name` | **L2** | **T** | S3 | APP-ENCRYPT (body + `file_name`) | fid | same as the parent conversation | Hard delete + object delete | Y\* (extracted text, own conversation) | N | N |
| 23 | Founder memory (target) | `founder_memory.content` | **L3** | P | S3 | APP-ENCRYPT | fid | per kind ([MEMORY_CONTRACT.md](MEMORY_CONTRACT.md)) | Delete | Y\* (confirmed memories only) | n/a | N |
| 24 | Memory events | `founder_memory_events` | L3 | P | S1 | KEEP-PLAINTEXT (must never hold content) | fid | account | Delete | N | N | Ref |
| 25 | Workspace text | `planning_*` titles and notes, `founder_goals`, `achievements`, `vision_territories.statement`, `vision_summary`, `framework_usage.note` | W | P | S3 | APP-ENCRYPT free text | fid | account | Delete | Y\* (`planning_tasks` titles to chat only) | Y (goals via founder-entered source) | N |
| 26 | Vision images | S3 `attachments/vision/{fid}/…`; `vision_territories.image_*` | W | P | S2/S3 | INFRASTRUCTURE-ENCRYPTION-ONLY plus authenticated serving | fid | account | Delete the object | N | N | N |
| 27 | Calendar OAuth | `calendar_connections.access_token_encrypted`, `refresh_token_encrypted`, `account_email`, `last_error` | X | P | SECRET/S2 | APP-ENCRYPT (migrate from Fernet) | fid | until disconnect | Revoke with Google, then delete | N | N | N |
| 28 | Consent evidence | `founder_consents`, `consents`, `consent_history`, `cookie_preferences` (`ip_address`, `browser`) | O | P | S2 | INFRASTRUCTURE-ENCRYPTION-ONLY | fid | [PRODUCT/LEGAL DECISION] | Scrub IP and browser, keep the row | N | N | N |
| 29 | Billing | `payments`, `subscriptions`, `credit_transactions`, `coupon_redemptions` | O | P | S2 | INFRASTRUCTURE-ENCRYPTION-ONLY | fid / `user_id` | [PRODUCT/LEGAL DECISION] | Retain; scrub free text | N | N | Ref |
| 30 | Audit | `audit_logs` (`action_details`), `admin_audit_log`, `privacy_requests`, `data_deletion_requests` | O | P | S2 | INFRASTRUCTURE-ENCRYPTION-ONLY + scrub | fid / `target_user_id` | [PRODUCT/LEGAL DECISION] | Scrub email and IP, keep the event | N | N | Ref |
| 31 | Webhook payloads | `webhook_logs.payload` | O | P | S2 | Store a minimised payload only (D-34) | fid | 90 days [PRODUCT/LEGAL DECISION] | Scrub | N | N | N |
| 32 | Telemetry | `llm_call_log`, `daily_token_usage`, `plan_call_usage`, `unbilled_usage`, `user_token_usage`, `analytics_events`, `rag_retrieval_log` | O | P | S1 (S3 for `rag_retrieval_log.query_text`, `llm_call_log.error`) | KEEP-PLAINTEXT; never store content | fid | 90 days to 13 months [PRODUCT/LEGAL DECISION] | Delete | N | N | Ref |
| 33 | Founder support content | `support_bot_misses.question`, `founder_feedback.outcome_text`, `notifications.body`, `suggestion_feedback.note`, `discovery_calls.notes_*`, `admin_notes.note_content` | O/W | P | S3 | APP-ENCRYPT | fid | account | Delete | Y\* (`support_bot_misses` question to support tasks only) | N | N |
| 34 | Waitlist | `waitlist_registrations` (`email`, `full_name`, `company`, `ip_address`, `user_agent`, `note`) | O | P | S2 | INFRASTRUCTURE-ENCRYPTION-ONLY | none (pre-account) | [PRODUCT/LEGAL DECISION] | Delete on erasure, matched by email | N | N | N |
| 35 | Voice audio | request body of `/voice/transcribe` | L2 | **T** (request only) | S3 | n/a (never persisted, `[CODE]`) | fid | 0 | n/a | Y (Whisper only) | N | N |
| 36 | Session tokens | browser `ally.access_token`, cookie `ally_refresh_token`; `revoked_tokens.jti` | O | T | SECRET / S1 | n/a | fid | 30 min / 30 days | Revoke | N | N | **Never** |
| 37 | Daily quotes / dimension profile | `founder_daily_quotes`, `founder_dimension_profile.display_value` | W | P | S1/S3 | KEEP-PLAINTEXT / APP-ENCRYPT `display_value` | fid | 60 days (`[CODE]` prune) / account | Delete | N | N | N |

## 4. Rules that follow from this table `[DECISION]`

1. **Every new column needs a classification.** A migration that adds a founder-related column must add a row here. The row gives its class, Enc, LLM, Memory and Logs values (D-03).
2. **Precedence:** if a value is copied from one class into another, the stricter class's rules win. For example, the text of `answers.answer_text` quoted inside `founder_reports.narrative_snapshot` is governed by class 14 and class 17.
3. **S4 data:**
   - never goes to `daily_quote_selection`, `support_*` or embeddings;
   - never enters memory;
   - is never shown in admin list views. It may appear in the single-founder admin detail view only, and only with an audit row.
4. **Memory entry:** "Memory = Y" only means the data may be **proposed** as a structured memory under [MEMORY_CONTRACT.md](MEMORY_CONTRACT.md). Nothing is copied into memory verbatim.
