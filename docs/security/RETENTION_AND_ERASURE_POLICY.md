# Retention and Erasure Policy

Part of the Day 1 security design package. Tags are defined in [DATA_CLASSIFICATION.md](DATA_CLASSIFICATION.md).

## 1. Erasure flow (target) `[DECISION D-90]`

`[CODE]` today: `DELETE /privacy/account` sets `deletion_scheduled_at = now + 30d` (`app/privacy/service.py:388-402`). Then `POST /internal/jobs/process-deletions` runs `AccountDeletionExecutor.run` (`app/privacy/deletion_executor.py`). That executor:

- hard-deletes 35 tables;
- scrubs IP addresses on 3 tables;
- retains 5 tables;
- anonymises 11 `founders` columns;
- makes no S3, IdP or OAuth calls;
- skips non-FK errors.

Target order, all inside `AccountDeletionExecutor`, one founder at a time:

1. **Lock and gate.** Set `deletion_in_progress`. Block login for any founder with `deletion_requested_at` set (except cancel during the grace period) or `deletion_executed_at` set (D-91; `app/core/auth/dependencies.py`).
2. **External revocation.** These calls must succeed or be queued:
   - Google: revoke and delete `calendar_connections` (reuse `calendar_sync/connections.py:disconnect`).
   - Supabase Auth: delete the auth user via the service-role admin API (`app/services/supabase_admin.py`, new `delete_user`).
   - Cognito, if live: `AdminDeleteUser`.
3. **Object storage.** List and delete every object under these prefixes. Failures go onto `pending_object_deletions` and the sweep retries them. The founder is not stamped as erased until the queue for that founder is empty.
   - `attachments/{founder_id}/`
   - `attachments/avatars/{founder_id}/`
   - `attachments/vision/{founder_id}/`
   - `reports/{report_id}/`, for every `founder_reports` row (`report_id`s are collected before the DB deletes)
   - local `uploads/avatars|vision/{founder_id}.*`
4. **DB delete, anonymise and scrub** per §3, in one transaction.
5. **Crypto-shred.** Delete that founder's `founder_data_keys` rows ([KEY_MANAGEMENT_DESIGN.md](KEY_MANAGEMENT_DESIGN.md) D-71).
6. **Completeness check.** Count each founder-scoped table listed in §3 for the founder, and require the expected state. **Any** error, not only `IntegrityError`, aborts the run, which is retried on the next sweep (D-92). This changes the `[CODE]` behaviour that logs and continues.
7. **Stamp.** Write `deletion_executed_at` and an `audit_logs` event with no PII.

**Schedule.** `[CODE]` GitHub cron `internal-job-sweeps.yml` (`20 19 * * *`); EventBridge is documented but `[UNKNOWN]`. `[DECISION]` The production schedule must be EventBridge (or equivalent) **and** alert if no `process-deletions` heartbeat is seen for 48 hours.

**Grace period.** `[CODE]` 30 days (`DELETION_GRACE_DAYS`). `[PRODUCT/LEGAL DECISION]` Confirm against the published privacy policy.

**Supabase `user.deleted` webhook.** `[CODE]` `webhooks/supabase.py` sets no RLS context. `[DECISION]` Set the admin RLS context after the secret check, and use `hmac.compare_digest` (D-101).

## 2. Retention jobs (target)

| Job (`/api/v1/internal/jobs/…`) | Purges | Period |
|---|---|---|
| `purge-raw-chat` (new) | `messages`, `conversations`, `file_uploads` and S3 attachment objects past `RAW_CHAT_RETENTION_DAYS` since `last_message_at`; drains `pending_object_deletions` | `[PRODUCT/LEGAL DECISION]` proposal 90 days |
| `purge-memory` (new) | `proposed` memories older than 14 days; `archived` memories older than 30 days; rejected fingerprints older than 30 days | [MEMORY_CONTRACT.md](MEMORY_CONTRACT.md) |
| `purge-telemetry` (new) | `llm_call_log`, `rag_retrieval_log`, `analytics_events`, `daily_token_usage`, `plan_call_usage` | `[PRODUCT/LEGAL DECISION]` proposal: 90 days for `llm_call_log` and `rag_retrieval_log`; 13 months for usage counters (billing reconciliation) |
| `purge-webhook-logs` (new) | `webhook_logs` | `[PRODUCT/LEGAL DECISION]` proposal 90 days |
| `assign-daily-quotes` (`[CODE]`) | `founder_daily_quotes` older than 60 days | keep |
| revoke path (`[CODE]` `session_store.py:84`) | expired `revoked_tokens` | keep |
| `founders.data_retention_expires_at` | `[CODE]` set to signup + 2 years and never read | `[PRODUCT/LEGAL DECISION]` Either define inactive-account deletion using it, or drop the column. |

## 3. Authoritative table policy

**Action column:**

- **DELETE**: hard delete of the founder's rows.
- **ANON**: anonymise in place.
- **RETAIN**: keep, with any scrubbing named.

**Today:** `HD` = in `_HARD_DELETE_TABLES`; `SCRUB` = in `_SCRUB_COLUMNS_RETAIN_ROW`; `RET` = in `_RETAIN_AS_IS_PENDING_LEGAL`; `—` = not touched.

**Backup column:** every DB row lives on in RDS automated backups for the backup retention window (`[DOC]` 7 days, `[UNKNOWN]` verified). The column says what a restore requires (§5).

| Table | Today | Action | Reason | Storage cleanup | LLM / external cleanup | Backup |
|---|---|---|---|---|---|---|
| `founders` | anon (11 cols) | **ANON** (full) | Tombstone keeps FK targets for ledgers. **Null:** every APP-ENCRYPT column in [ENCRYPTION_BOUNDARY.md](ENCRYPTION_BOUNDARY.md), plus `avatar_url`, `avatar_storage_path`, `phone`, `business_name`, `admin_notes`, `cognito_sub`, `linkedin_url`, `website`, `first_impression`. **Replace:** `email` → `deleted-founder-{id}@erased.ally.local` (keeps `[CODE]`); `full_name` → `Deleted Founder`; `user_id` → a fresh random UUID that is not linked to any IdP user. **Keep:** `founder_id`, `plan_type`, `stage_id`, `industry`, timestamps, `deletion_*` | avatar objects | Delete IdP user; revoke Google | Replay erasure after restore |
| `founder_context` | HD | DELETE | Content | — | — | replay |
| `founder_dna_answers`, `current_problem_answers` | HD | DELETE | Content | — | — | replay |
| `sessions`, `answers`, `detected_root_causes`, `stage_assessments` | HD | DELETE | Content | — | — | replay |
| `founder_reports` | HD | DELETE | Content | `reports/{report_id}/*` objects | — | replay |
| `internal_intelligence_reports` | HD | DELETE | S4 | — | — | replay |
| `report_shares` | HD | DELETE | Credential | — | — | replay |
| `founder_feedback` | HD | DELETE | Content | — | — | replay |
| `conversations`, `messages`, `file_uploads` | HD | DELETE | Raw chat | `attachments/{fid}/*` objects | — | replay |
| `suggestions`, `suggestion_feedback` | HD | DELETE | | — | — | replay |
| `founder_memory`, `founder_memory_events` | HD | DELETE | | — | — | replay |
| `rag_retrieval_log`, `llm_call_log`, `daily_token_usage`, `plan_call_usage`, `unbilled_usage` | HD | DELETE | Telemetry | — | Provider-side retention: `[UNKNOWN]` (vendor ZDR) | replay |
| `user_token_usage` | — | **DELETE** | Telemetry | — | — | replay |
| `analytics_events`, `cookie_preferences` | HD | DELETE | | — | — | replay |
| `notifications`, `daily_actions`, `founder_visual_choices` | HD | DELETE | | — | — | replay |
| `planning_plans`, `planning_goals`, `planning_tasks`, `planning_reminders` | HD | DELETE | Workspace | — | Google Calendar events created by task sync (`calendar_event_id`) are deleted via the API before the revoke. `[UNKNOWN]`: confirm the sync creates events in the founder's calendar. | replay |
| `founder_goals`, `achievements`, `framework_usage` | — | **DELETE** | Workspace | — | — | replay |
| `vision_territories`, `vision_summary` | — | **DELETE** | Workspace | `attachments/vision/{fid}/*` objects | — | replay |
| `founder_dimension_profile`, `founder_daily_quotes`, `founder_settings`, `feature_flag_overrides`, `broadcast_reads` | — | **DELETE** | | — | — | replay |
| `calendar_connections` | — | **DELETE** after revoke | Secret | — | Google token revoke | replay |
| `support_bot_misses` | — | **DELETE** | Content | — | — | replay |
| `discovery_calls`, `admin_notes` | HD | DELETE | | — | Google Calendar event on the team calendar (`services/calendar.py`) is cancelled or deleted. `[UNKNOWN]`: confirm the attendee email is removed. | replay |
| `data_deletion_requests` | HD | **RETAIN** (changed) | Proof that erasure ran. `[PRODUCT/LEGAL DECISION]` | — | — | — |
| `privacy_requests` | RET | RETAIN; null `request_details`, `processing_notes` | Accountability for DPDP requests. `[PRODUCT/LEGAL DECISION]` on the period | — | — | — |
| `founder_consents` | RET | RETAIN; scrub `ip_address` (new) | Consent proof. `[PRODUCT/LEGAL DECISION]` on the period | — | — | — |
| `consents`, `consent_history` | SCRUB | RETAIN; scrub IP and browser | same | — | — | — |
| `audit_logs` | SCRUB | RETAIN; scrub IP and browser **and** strip `action_details.email` (new) | Accountability | — | — | — |
| `admin_audit_log` | — | RETAIN; replace email values in `old_value` / `new_value` with `[erased]` | Admin accountability. `[PRODUCT/LEGAL DECISION]` on the period | — | — | — |
| `webhook_logs` | — | **ANON**: null `payload` for the founder (keep event id, type, status) | Payment reconciliation needs ids, not payloads | — | — | — |
| `payments`, `subscriptions`, `credit_transactions`, `coupon_redemptions` | RET | RETAIN; null `cancellation_reason`, `reason` (free text) | Tax and accounting. `[PRODUCT/LEGAL DECISION]` on the period (e.g. statutory years) | Invoices at `payments.invoice_url` are Razorpay-hosted. `[UNKNOWN]`: Razorpay customer deletion. | Razorpay retains its own records (vendor) | — |
| `waitlist_registrations` | — | **DELETE**, matched by the original email captured before anonymisation | Pre-account PII | — | — | replay |
| `revoked_tokens` | n/a | (pruned) | No PII | — | — | — |
| `founder_data_keys` (Day 2) | n/a | **DELETE** (crypto-shred) | | — | — | the restored DB contains wrapped DEKs: replay |
| `session_context_facts` | — | **UNKNOWN**: no app reference found; verify the contents | | | | |

**Local disk:** `backend/uploads/avatars`, `uploads/vision` (local fallback). Delete the founder's files. `[DECISION]` Production must not use the local fallback, because ECS storage is ephemeral (D-35).

## 4. Logs and third parties

| Store | Founder data present `[CODE]` | Policy |
|---|---|---|
| CloudWatch `/ecs/ally-backend-task` | `founder_id`, emails in some lines, request paths (share tokens), frontend error URLs and stacks, task titles | After the logging contract (D-62–D-66) lands, it holds no content or emails. Retention `[PRODUCT/LEGAL DECISION]`, proposal 30 days. Logs are not erased per founder; they expire. |
| Sentry (if `SENTRY_DSN`) | Possibly request bodies and frame locals | Scrubber (D-65). Retention per Sentry org setting `[UNKNOWN]`. |
| LLM vendors | Prompts | Covered by vendor ZDR/DPA `[UNKNOWN]`. No per-founder deletion API is assumed. |
| Google (OAuth grant, calendar events) | Tokens, events | Revoke and delete in erasure step 2 |
| Supabase Auth | Auth user (email) | Delete in erasure step 2 |
| Old Supabase Postgres | `[UNKNOWN]` whether founder rows from before the RDS migration remain | Must be verified, then purged (§J of [DAY1_SECURITY_DECISIONS.md](DAY1_SECURITY_DECISIONS.md)) |
| Razorpay | Customer and payment records | Vendor-retained. `[PRODUCT/LEGAL DECISION]` |

## 5. Backups `[DECISION D-95]`

1. RDS automated backups age out at the retention window. `[DOC]` 7 days; `[UNKNOWN]` verify. Erasure is **not** applied to backups in place.
2. **Erasure replay.** `data_deletion_requests` (now retained) is the replay list. Any restore of production data to any environment must run `process-deletions` for every founder with `deletion_executed_at` set **before** the restored DB serves traffic. Day 5 adds this to `backend/docs/RESTORE.md`.
3. Manual snapshots, cross-region copies and S3 versioning are each `[UNKNOWN]`. If any exist, each needs an expiry no longer than the backup window, or a documented reason.
4. **Production data copies.** Copying production data to staging or local is forbidden `[DECISION]`. Reference-data dumps (`scripts/dump_reference_data.py`) stay restricted to their allowlist (`[CODE]` already).
