# Day 1 Security Decisions

This is the index and decision register for the Ally 5-day "Encryption, Privacy & Memory Architecture" work. It also holds the logging contract (§H), access-control contract (§I), the infrastructure checklist (§J) and the **Day 2 Implementation Contract** (§K).

## Tags

| Tag | Meaning |
|---|---|
| `[CODE]` | What the repo does today (commit `78f7655`). |
| `[DECISION]` | Proposed and accepted for engineering, unless it is overturned. |
| `[UNKNOWN]` | Needs infrastructure or product confirmation. |
| `[PRODUCT/LEGAL DECISION]` | Blocked; needs a named owner. |

## Package

| File | Covers |
|---|---|
| [DATA_CLASSIFICATION.md](DATA_CLASSIFICATION.md) | A: layers, sensitivity, per-class rules |
| [DATA_LIFECYCLE.md](DATA_LIFECYCLE.md) | B: raw chat contract; report versioning |
| [MEMORY_CONTRACT.md](MEMORY_CONTRACT.md) | C: structured memory, plus the migration off raw WORKING memory |
| [ENCRYPTION_BOUNDARY.md](ENCRYPTION_BOUNDARY.md) | D: per-field class |
| [KEY_MANAGEMENT_DESIGN.md](KEY_MANAGEMENT_DESIGN.md) | E: KMS, DEKs, format, rotation, Fernet migration |
| [RETENTION_AND_ERASURE_POLICY.md](RETENTION_AND_ERASURE_POLICY.md) | F: per-table erasure, jobs, backups |
| [LLM_DATA_BOUNDARY.md](LLM_DATA_BOUNDARY.md) | G: per-task LLM contract |
| this file | H, I, J, K and the decision register |

---

## Decision register

| ID | Decision | Status | Day |
|---|---|---|---|
| D-01 | Four data layers plus W/X/O/R; every founder column belongs to one | DECISION | 1 |
| D-02 | Sensitivity levels S1–S4 + SECRET | DECISION | 1 |
| D-03 | A new founder column requires a classification row, enforced in review | DECISION | 3+ |
| D-12 | `founders.email`: Option A (plaintext; email no longer drives authz) vs B (blind index) | **PRODUCT DECISION**; A recommended | 1→3 |
| D-13 | Admin search reduced to exact email / `founder_id`; no `ilike` on encrypted fields | DECISION (product to acknowledge) | 3 |
| D-14 | `business_health_band` plaintext projection column; `red_flags` read in the app | DECISION | 3 |
| D-15 | `<col>_enc` sibling columns, dual-read, then drop plaintext | DECISION | 3 |
| D-20 | Raw chat purged after `RAW_CHAT_RETENTION_DAYS` | Mechanism DECISION; **value PRODUCT/LEGAL** (proposal 90) | 4 |
| D-21 | Conversation delete is a hard delete (rows + S3 + proposed memory) | DECISION | 3 |
| D-22 | Archive stays reversible | DECISION | — |
| D-23 | Deleted conversations are never restorable; backfill-purge existing `deleted` rows | DECISION | 3–4 |
| D-24 | Deleted chat never reaches any prompt | DECISION | 3 |
| D-25 | Attachments follow their conversation; delete is hard | DECISION | 3 |
| D-26 | Titles encrypted; listings show `active` only | DECISION | 3 |
| D-27 | Prompt history is limited to the same conversation | DECISION | 3 |
| D-28 | "Don't Remember This" at message, conversation and account level | DECISION | 3 |
| D-29 | Every admin chat read is audited with a reason; deleted chat is invisible | DECISION | 3 |
| D-29b | Support standing `VIEW_CHATS` vs founder-granted access | **PRODUCT/LEGAL** (recommend a grant) | — |
| D-30 | No raw text written to memory from chat | DECISION | 3 |
| D-31 | Share tokens stored only as a hash; never logged; `share_url` not stored | DECISION | 3 |
| D-32 | Restriction gate also covers attachments and extraction | DECISION | 3 |
| D-34 | `webhook_logs` stores a minimised payload; Razorpay verifies before persisting | DECISION | 3 |
| D-35 | Avatars and vision images served through authenticated, owner-checked routes; `Cache-Control: private`; no `/uploads` static mount in production | DECISION | 3/5 |
| D-36 | `audit_logs` and `admin_audit_log` never store email or content | DECISION | 3 |
| D-37 | Privacy export uses a column allowlist (no `admin_notes`, `cognito_sub`, `user_id`) | DECISION | 3 |
| D-40 | Report versions: `report_version`, write-once derived columns, no share re-pointing | DECISION | 3 |
| D-41 | No founder per-report delete | **PRODUCT/LEGAL** | — |
| D-50…D-55 | Memory kinds, confirmation, controls, extraction, context rules, M0–M5 migration | DECISION (auto-confirm, default-enabled and seeding opt-in are PRODUCT/LEGAL) | 3–5 |
| D-60 | Admin role and team plan resolve from an immutable identity (`founders.user_id` allowlist), not mutable `email`; admin PATCH cannot change `email` | DECISION | 3 |
| D-61 | Auth fails closed: the `dev` provider requires `ENVIRONMENT ∈ {local,test}`, not "anything except `production`" | DECISION | 3/5 |
| D-62…D-66 | Logging contract (§H) | DECISION (CloudWatch retention value is PRODUCT/LEGAL) | 3/5 |
| D-70…D-78 | KMS envelope, per-founder per-domain DEKs, domains, versions, format, IAM, env separation, Fernet migration | DECISION | 2 |
| D-80, D-81 | LLM global rules; Gotenberg loopback-only | DECISION (vendor approval is PRODUCT/LEGAL) | 3 |
| D-90…D-95 | Erasure order, login block, abort-on-any-error, retention jobs, backup replay | DECISION (periods are PRODUCT/LEGAL) | 4 |
| D-100…D-108 | Access control (§I) | DECISION | 3–5 |

---

## H. Logging contract `[DECISION D-62…D-66]`

**Current state** `[CODE]`:

- `app/core/logger.py:JSONFormatter` emits every `extra` key.
- `RequestLoggingMiddleware` logs the raw `request.url.path`.
- Emails are logged in `services/email.py`, `supabase_admin.py`, `waitlist.py`, `provisioning.py` and `calendar.py`.
- Task titles are logged in `task_reminders.py:363`.
- Frontend errors are logged with their unsanitised URL.
- `create_engine` is called without `hide_parameters`.
- Sentry runs without `before_send`.

| # | Contract |
|---|---|
| D-62 **Allowed fields** | The `JSONFormatter` emits only standard fields plus an allowlist of `extra` keys, and drops any other key with a counter. Allowlist: `request_id`, `route` (template), `method`, `status_code`, `duration_ms`, `founder_id`, `conversation_id`, `session_id`, `report_id`, `attachment_id`, `memory_id`, `job`, `task`, `provider`, `model`, `stage`, `count`/`*_count`, `error_type`, `error_code`, `table`, `impact`, `environment`, `url` (config URLs only). Ids are logged; content never is. |
| D-62 **Forbidden** | Message, answer, memory, report or attachment text; prompts and completions; email; phone; names; IP; user agent; tokens (access, refresh, share, OAuth, `state`); request and response bodies; headers; query strings; filenames of avatars, vision images or attachments; raw `str(exc)` from DB, HTTP or provider errors. |
| D-62 **Error redaction** | Log `error_type = type(exc).__name__`, plus `error_code` (Postgres `pgcode`, HTTP status, provider error type). `llm_call_log.error` and `calendar_connections.last_error` store the same, ≤ 200 characters, with no response bodies. |
| D-64 **Share tokens / capability URLs** | `RequestLoggingMiddleware` logs `request.scope["route"].path` (for example `/api/v1/reports/shared/{token}/view`), never the concrete path. 404s without a route log the literal `"unmatched"`. Tokens are never logged by any handler (D-31). |
| D-62 **Email** | Never logged. When correlation is needed, log `founder_id`, or `email_hash = HMAC(index_key, lower(email))[:16]` for pre-account flows (waitlist, provisioning). |
| D-62 **SQL exceptions** | `create_engine(..., hide_parameters=True)` (`app/db/session.py`). DB errors are logged as `error_type` + `pgcode`. The `exc_info` traceback is allowed only for `unhandled_exception_handler`, after `hide_parameters`. |
| D-62 **Frontend errors** | `/frontend-errors` strips the query string and fragment from `url`, truncates `message` and `stack`, and applies the same JWT/Bearer redaction as the browser (`frontend/src/services/errorReporting.js`). Rate limit: 30/min per founder or IP. |
| D-65 **Sentry** | Allowed only with: `send_default_pii=False` (`[CODE]`); `max_request_body_size="never"`; `include_local_variables=False`; a `before_send` that drops `request.data`, `request.query_string`, `request.cookies` and all of `request.headers`, applies the D-62 allowlist to `extra`, and replaces the transaction name with the route template; and `before_breadcrumb` dropping `httpx` URLs. Otherwise `SENTRY_DSN` stays unset. Whether Sentry is used at all is a product decision. |
| D-66 **CloudWatch** | Log group `/ecs/ally-backend-task` must have a retention setting (`[PRODUCT/LEGAL DECISION]`; proposal 30 days) and KMS encryption `[UNKNOWN]`. Never "Never expire". |
| D-62 **Libraries** | The `httpx` logger is set to WARNING (it logs full URLs at INFO). The `uvicorn.access` logger stays at WARNING (`[CODE]`). |
| D-63 **Tests** | A test drives a chat turn, a diagnosis answer, a share view, a waitlist signup and an email send under a capturing handler. It asserts that none of the submitted content, emails or tokens appear in any record. `tests/test_logger.py:27`, which asserts that arbitrary extras pass through, is rewritten. |

## I. Access-control contract `[DECISION D-100…D-108]`

| # | Contract |
|---|---|
| D-100 **Founder ownership** | The founder is derived only from the token (`get_founder_record`, `[CODE]`). Any route taking a resource id returns **404** for both missing and foreign ids. Fix `reports/routes.py:_owned_report`, which currently returns 403. |
| D-103 **Repository rule** | New and changed repository methods that read founder-scoped rows take `founder_id` and filter in SQL. Today many methods fetch by id only and rely on the caller to check (`achievements`, `founder_goals`, `sql_conversation`, attachments, suggestions, `FounderReport`, `founder_memory`). Day 3 converts the ones it touches; the rest are tracked. |
| D-60 **Admin identity** | The admin role comes from an allowlist of `founders.user_id` (or IdP `sub`), not email. `PATCH /admin/users/{id}` drops `email` (email change goes through the founder's own verified flow). The team plan follows the same rule. |
| D-105 **Admin audit** | Every admin read of a single founder's data (`users/{id}` detail, timeline, conversations, conversation view, usage, feedback, privacy requests) writes `admin_audit_log` with action, target and reason (reason is mandatory for raw-chat reads, RC-10). List endpoints log one row per call. |
| D-105 **Admin data minimisation** | Admin list views never show S4 fields or raw chat. `internal_intelligence_reports` is visible only to `super_admin`, and audited. |
| D-102 **RLS** | Required as a second layer in production. The runtime connects as `ally_app`; `ally_app` is `NOBYPASSRLS` and does not own founder tables; `ALTER TABLE … FORCE ROW LEVEL SECURITY` on founder tables `[UNKNOWN]` until §J confirms. Admin and system RLS (`set_admin_rls_context`) only after a capability or secret check (`[CODE]` order is correct). Share routes must stop using admin RLS; they use a narrow SECURITY DEFINER lookup by `share_token_hash` instead. |
| D-104 **Cross-founder tests** | A CI job runs with a Postgres service, migrates to head, and `SET ROLE ally_app`. With founders A and B, it asserts that B gets 404 or no rows for A's: report (GET, export, share, shares), conversation (GET, messages, archive, restore, stream, suggestions), attachment (GET, DELETE, link), memory (GET, PATCH, DELETE), plan/goal/task/reminder, goal, achievement, discovery call, notification, feedback target, vision, framework, intelligence report. It also asserts the raw RLS: B's context selects 0 of A's rows on each founder table in [RETENTION_AND_ERASURE_POLICY.md](RETENTION_AND_ERASURE_POLICY.md) §3. And a non-admin token gets 403 on every `/admin/*` route, using the real `PanelRegistry`, not an override. `[CODE]` today CI runs only `tests/test_rls_context.py` (mocks). |
| D-101 **Service-to-service** | Every shared secret (`INTERNAL_JOBS_SECRET`, `SUPABASE_WEBHOOK_SECRET`, `WAITLIST_FORWARD_SECRET`) is compared with `hmac.compare_digest`. Internal jobs move to per-job secrets or a signed request (HMAC over method + path + timestamp, ±5 min) `[DECISION]`. The Razorpay webhook verifies the HMAC **before** writing `webhook_logs` (D-34). |
| D-61 **Auth fail-closed** | The `dev` provider is refused unless `ENVIRONMENT ∈ {"local","test"}`. Unknown values of `ENVIRONMENT` are refused at boot. Supabase JWT verification adds an `iss` check. Backend JWTs add `iss`/`aud` and `kid` (D-74). Login is blocked for erased or pending-deletion founders (D-91). |
| D-106 **Public surfaces** | Share view: rate-limited, renders the founder-approved share scope ([DATA_LIFECYCLE.md](DATA_LIFECYCLE.md) §3), never the S4 wellbeing note `[PRODUCT/LEGAL DECISION]`. Avatars and vision images: D-35. `/frontend-errors`: rate-limited. |
| D-107 **Calendar OAuth** | The `state` is bound to the browser by a nonce in a short-lived, HttpOnly, SameSite=Lax cookie checked on `/calendar/callback`. |
| D-108 **Client IP** | Rate limits use the client IP appended by the ALB (the right-most untrusted hop) or the CloudFront header `[UNKNOWN]`, never the first `X-Forwarded-For` entry. The `--forwarded-allow-ips "*"` in `Dockerfile` is narrowed to the VPC CIDR. |

## J. Infrastructure / vendor checklist

These items **cannot** be established from the repo. Each one needs a manual check. Record the answer and date in this table on completion.

| # | Check | Where | Blocks |
|---|---|---|---|
| J-1 | Production and staging `ENVIRONMENT` and `AUTH_PROVIDER` values; whether any internet-reachable environment runs `dev` | ECS task definitions, all services | D-61 |
| J-2 | Runtime DB role: `select rolname, rolbypassrls, rolsuper from pg_roles where rolname in ('ally_app','postgres')`; owner of each founder table; `select * from pg_policies`; `relforcerowsecurity` | RDS (production) | D-102 |
| J-3 | RDS `StorageEncrypted`, KMS key id and key policy; automated backup retention; manual snapshots; cross-region copies; `rds.force_ssl` | RDS console | D-95, E |
| J-4 | `DATABASE_URL` secret includes `sslmode=verify-full` (or `require`) and the RDS CA | Secrets Manager | Day 5 hardening |
| J-5 | S3 bucket (`ATTACHMENT_S3_BUCKET`): default encryption (SSE-S3 vs SSE-KMS + key), Block Public Access (account and bucket), bucket policy, versioning, lifecycle rules, object ownership / ACLs | S3 console | D-35, D-90 |
| J-6 | ECS task role IAM: S3 actions and prefixes (`attachments/*` vs `reports/*`), any KMS permissions | IAM | D-76, PDF storage |
| J-7 | Which secrets are in `secrets[]` vs plain `environment` in the task definition; rotation enabled | ECS + Secrets Manager | §9 KMD |
| J-8 | CloudWatch `/ecs/ally-backend-task` retention and KMS; CloudTrail enabled with KMS data events | CloudWatch / CloudTrail | D-66, D-76 |
| J-9 | Whether `SENTRY_DSN` is set; Sentry org data-scrubbing and retention settings | ECS env, Sentry | D-65 |
| J-10 | Live `model_task_routing` rows; production `ALLY_LLM_PROVIDER`, `ALLY_LLM_FALLBACK`, `OPENAI_MODEL`, `REPORT_NARRATIVE_LLM`, `DISTRESS_LLM`, `ANSWER_CLASSIFIER`, `RETRIEVAL_ENABLED`, `EMBEDDING_PROVIDER` | RDS + ECS env | G |
| J-11 | OpenAI and Anthropic organisation: DPA signed, zero-data-retention status, training opt-out, data region | Vendor dashboards / contracts | D-80 vendor register |
| J-12 | Whether the old Supabase Postgres still holds founder tables or rows from before the RDS move; Supabase backups / PITR on that project | Supabase dashboard | F §4 |
| J-13 | Supabase Auth: email change requires verification; the admin API can delete users with the service-role key; auth hooks / webhooks configured | Supabase dashboard | D-60, D-90 |
| J-14 | EventBridge (or other) schedule for `process-deletions` and other internal jobs exists and targets production | EventBridge | D-90 |
| J-15 | ALB / CloudFront: whether `X-Forwarded-For` is overwritten or appended; access logging enabled (logs contain `/r/{token}` paths) and its retention | ALB, CloudFront, Vercel | D-64, D-108 |
| J-16 | `GOXL_ADMIN_PANEL_USERS` entries, and that each maps to an existing, verified founder | ECS env | D-60 |
| J-17 | Google Workspace service account (domain-wide delegation) scopes; Google OAuth consent-screen scopes for founder calendars | Google Cloud console | Calendar erasure |
| J-18 | Whether the share token committed in `backend/docs/PRODUCTION-RDS-CHECKS.md` is still active; revoke it | RDS `report_shares` | G-01 |
| J-19 | Whether staging or local environments have ever received copies of production data | Team | D-95 |
| J-20 | AWS account structure: separate accounts for staging and production | AWS Organizations | D-77 |

## Blocked product/legal decisions (owner required)

| ID | Question |
|---|---|
| P-1 | `RAW_CHAT_RETENTION_DAYS` value. Engineering proposal: 90. |
| P-2 | Account erasure grace period (code: 30 days) vs the privacy policy. |
| P-3 | Retention periods for billing, consent, audit, `privacy_requests`, `data_deletion_requests`, `webhook_logs`, telemetry, CloudWatch. |
| P-4 | `founders.email` storage: Option A vs B (D-12). |
| P-5 | Support standing access to raw chat vs a founder grant (D-29b). |
| P-6 | Memory: default enabled? auto-confirm? onboarding seeding without explicit opt-in? |
| P-7 | Approved LLM vendors and chat failover across vendors (G8); whether `emotional_state` may go to chat and `first_impression`. |
| P-8 | Shared report scope: may the public share include the wellbeing / psychological note? |
| P-9 | Founder per-report delete (D-41); pruning old report versions. |
| P-10 | Inactive-account deletion using `data_retention_expires_at`. |
| P-11 | Whether Sentry is used at all. |

---

## K. DAY 2 IMPLEMENTATION CONTRACT

Day 2 builds **one** encryption service and its key storage. It does **not** change any existing read or write path, except the calendar token migration (step 8). Integration is Day 3.

### K.1 Module and surface

Location: `backend/app/core/crypto/` (new package). Public API:

```text
EncryptionService
  encrypt(domain, founder_id, plaintext: str|bytes, *, table, column) -> str
  decrypt(domain, founder_id, envelope: str, *, table, column) -> str|bytes
  encrypt_bytes(domain, founder_id, data: bytes, *, table, column) -> bytes     # S3 binary form
  decrypt_bytes(domain, founder_id, blob: bytes, *, table, column) -> bytes
  encrypt_json / decrypt_json(…)                                               # JSONB columns
  is_envelope(value) -> bool                                                   # dual-read support
  token_hash(purpose, token: str) -> str            # HASH class (share tokens)
  blind_index(field, value: str) -> str             # BLIND-INDEX class; caller normalises
  destroy_founder_keys(founder_id) -> int           # crypto-shred, used by erasure
  rewrap(founder_id, domain, to_version) -> int     # rotation job primitive
get_encryption_service() -> EncryptionService       # FastAPI dependency + plain function for jobs
```

`domain` is one of the 9 domains in [KEY_MANAGEMENT_DESIGN.md](KEY_MANAGEMENT_DESIGN.md) §3. Use an enum and reject unknown values.

### K.2 Required behaviour

| # | Requirement |
|---|---|
| 1 | AES-256-GCM via `cryptography` `AESGCM`; 12-byte random nonce per call; AAD = `ally1|<env>|<domain>|<table>.<column>|<founder_id>`. |
| 2 | The envelope format is exactly `ally1.<domain>.<key_version>.<b64url(nonce‖ct‖tag)>`. The binary form is as specified in KMD §5. Round-trip and cross-founder/column AAD-mismatch tests must fail decryption. |
| 3 | `KeyProvider` interface with `KmsKeyProvider` (boto3 `GenerateDataKey` / `Decrypt`, encryption context `{env, domain, founder_id}`), `LocalKeyProvider` (local/test/CI) and `LegacyFernetProvider` (decrypt only, domain `integration`). |
| 4 | Provider selection is fail-closed: production requires `ALLY_KEY_PROVIDER=kms` and the ARNs present, otherwise the app refuses to boot. Local is refused when `ENVIRONMENT=production`. |
| 5 | `founder_data_keys` table and migration (KMD §5). DEK created lazily on first encrypt, per (founder, domain). Concurrent first-use is safe: unique PK, insert-or-select. |
| 6 | In-process DEK cache: TTL `ALLY_DEK_CACHE_TTL_SECONDS` (default 300), LRU max `ALLY_DEK_CACHE_MAX`. Cleared for a founder on `destroy_founder_keys`. Plaintext DEKs never leave the cache, and are never logged or serialised. |
| 7 | Key versions: encrypt uses the highest `active` version; decrypt uses the version in the envelope; `decrypt_only` and `destroyed` states are honoured. Decrypting with a `destroyed` key raises `KeyDestroyedError`. |
| 8 | **Calendar migration:** `app/calendar_sync/crypto.py` delegates to the service (domain `integration`). It reads legacy Fernet and writes `ally1`. Backfill internal job `reencrypt-calendar-tokens`. `CALENDAR_TOKEN_KEY` is kept only for legacy decrypt. |
| 9 | `token_hash` and `blind_index`: HMAC-SHA256 under the `index` key, output `h1.<idx_version>.<b64url>`. Deterministic; constant-time compare helper. |
| 10 | **Errors** (typed): `EncryptionUnavailableError`, `DecryptionError`, `KeyDestroyedError`, `UnknownDomainError`. All fail closed: never return plaintext on error, and never fall back to storing plaintext. Messages contain domain, version and founder_id only. |
| 11 | **Observability:** counters for encrypt, decrypt, KMS calls, cache hit/miss, legacy-format reads, failures by type. No values. The logging allowlist (§H) is respected. |
| 12 | **Performance:** a cache hit adds ≤ 1 ms per field for ≤ 8 KB. KMS is called at most once per (founder, domain) per TTL. |
| 13 | **Tests (run in CI without AWS):** round trip per domain; AAD binding; tamper → `DecryptionError`; version selection; `destroy_founder_keys` then decrypt → `KeyDestroyedError`; Fernet legacy read + rewrite; provider fail-closed in production config; DEK cache TTL; no plaintext or DEK in captured logs; KMS provider tested with a stubbed boto3 client. |
| 14 | **Config names (new):** `ALLY_KEY_PROVIDER`, `ALLY_KMS_DATA_KEY_ARN`, `ALLY_KMS_INTEGRATION_KEY_ARN`, `ALLY_KMS_INDEX_KEY_ARN`, `ALLY_LOCAL_MASTER_KEY`, `ALLY_DEK_CACHE_TTL_SECONDS`, `ALLY_DEK_CACHE_MAX`. Added to `backend/app/core/config.py` and `backend/.env.example` with no values. |
| 15 | **Optional, if time allows:** `JWT_SIGNING_KEYS` with `kid` (D-74) and a separate `OAUTH_STATE_KEY`. |

### K.3 Out of scope for Day 2

- Encrypting any existing table column (Day 3).
- Changing memory, chat, report or erasure behaviour (Days 3–4).
- Creating the KMS keys or IAM policies in AWS: these are infrastructure tasks once J-3/J-6/J-20 are answered. Day 2 ships code and the IaC/console runbook only.

### K.4 Day 2 done when

1. All K.2 tests pass in CI.
2. Calendar tokens round-trip through the service in a local run, with legacy Fernet rows still readable.
3. `founder_data_keys` migration applies cleanly on top of `head`.
4. No existing test changes behaviour.
