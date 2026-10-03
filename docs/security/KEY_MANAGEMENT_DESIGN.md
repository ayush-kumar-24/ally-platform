# Key Management Design

Part of the Day 1 security design package. Tags are defined in [DATA_CLASSIFICATION.md](DATA_CLASSIFICATION.md). This is a target architecture only; nothing here is implemented.

## 1. Current state `[CODE]`

| Secret | Used for | Storage | Versioned? |
|---|---|---|---|
| `CALENDAR_TOKEN_KEY` | Fernet encryption of calendar OAuth tokens (`app/calendar_sync/crypto.py`) | env var; `lru_cache` for the process lifetime | No. Plain `Fernet`. Rotating the key breaks every connection. |
| `SECRET_KEY` | HS256 backend session JWTs (`app/core/auth/tokens.py`) and calendar OAuth `state` (`app/calendar_sync/state.py`) | env | No `kid` |
| All other secrets | `DATABASE_URL`, API keys, `RAZORPAY_*`, `SUPABASE_*`, `INTERNAL_JOBS_SECRET`, etc. | env, injected by ECS from Secrets Manager (`[CONFIG]` `backend-deploy.yml`) | none |

- The app makes **no** KMS or Secrets Manager SDK calls.
- `boto3` and `cryptography==50.0.0` are already in `requirements.txt`.

## 2. Target architecture `[DECISION D-70]`

```
AWS KMS (per environment, ap-south-1)
 ├─ alias/ally-<env>-data         symmetric CMK: wraps founder DEKs (domains profile…support)
 ├─ alias/ally-<env>-integration  symmetric CMK: wraps integration DEKs (OAuth tokens)
 └─ alias/ally-<env>-index        HMAC_256 KMS key OR a wrapped 256-bit secret: blind indexes and token hashes
        │
        ▼  GenerateDataKey / Decrypt (encryption context bound)
 founder_data_keys (Postgres)  ── one wrapped DEK per (founder_id, domain, key_version)
        │
        ▼  in-process DEK cache (plaintext DEK, TTL ≤ 5 min, max N entries, never logged)
 EncryptionService (app/core/crypto/ — Day 2)
        │  AES-256-GCM, 96-bit random nonce, AAD
        ▼
 "<column>_enc" Text columns / S3 object bodies
```

- **Envelope encryption.** KMS never sees founder data. It only wraps and unwraps 32-byte data keys.
- **Per-founder, per-domain DEKs `[DECISION D-71]`.**
  - Blast radius is limited to one founder and one domain.
  - On erasure, deleting that founder's `founder_data_keys` rows makes **any missed copy unreadable**. This covers missed tables, orphaned S3 objects, and plaintext-free DB copies. It is a safety net for the gaps listed in [RETENTION_AND_ERASURE_POLICY.md](RETENTION_AND_ERASURE_POLICY.md).
  - **Limitation:** DB backups also contain the wrapped DEKs, so crypto-shredding does **not** defeat the backup window. Backups age out (§5 of the retention policy).
- **Shared index key.** The blind-index / token-hash key is per environment, not per founder. Lookups such as share tokens and email must work before the founder is known.

## 3. Domains `[DECISION D-72]`

| Domain | Data ([ENCRYPTION_BOUNDARY.md](ENCRYPTION_BOUNDARY.md)) | CMK |
|---|---|---|
| `profile` | `founders` personal and onboarding fields, `founder_context` | data |
| `chat` | `messages`, `conversations.title`, `file_uploads`, attachment objects | data |
| `memory` | `founder_memory.content` | data |
| `diagnosis` | answers, DNA and problem answers, session state | data |
| `report` | `founder_reports`, `internal_intelligence_reports`, report PDFs | data |
| `workspace` | planning, goals, achievements, vision, framework notes | data |
| `support` | `admin_notes`, `discovery_calls` notes, `support_bot_misses`, `notifications.body`, `privacy_requests` details, `founder_feedback` | data |
| `integration` | `calendar_connections` tokens and `account_email` | integration |
| `index` | HMAC for `share_token_hash`, the email blind index (if D-12 = B), memory rejection fingerprints | index |

Raw chat gets its own domain so a future time-bucketed key (crypto-shred on retention) can replace per-row deletes without touching other domains. This is not planned for Day 2.

## 4. Key versions and rotation `[DECISION D-73]`

| Item | Rule |
|---|---|
| CMK rotation | Enable KMS automatic annual rotation on `data` and `integration`. KMS keeps old backing keys, so nothing needs re-wrapping. **[UNKNOWN]**: check the org KMS policy. |
| DEK version | `founder_data_keys.key_version` is an int, starting at 1. New writes use the highest `active` version. Older versions stay `active_decrypt_only` until no ciphertext references them. |
| Scheduled DEK rotation | Not scheduled by default. It is triggered by compromise, by a CMK change (new alias target), or by policy `[PRODUCT/LEGAL DECISION]`. |
| Re-encrypt | A background job decrypts with the old version and encrypts with the new one, per founder and domain, batched. It is idempotent: the job skips ciphertext that already has `kv = current`. |
| Index key rotation | Requires recomputing all hash/index columns. A `idx_version` is stored alongside each index value. During rotation the code looks up under both versions. |
| `SECRET_KEY` (JWT) | `[DECISION D-74]` Add a `kid` header. `JWT_SIGNING_KEYS` holds the keys as `kid:secret,…`; the first one signs and all of them verify. The calendar `state` gets its own `OAUTH_STATE_KEY`. Optional for Day 2; required before the first rotation. |
| Compromise playbook | 1. Disable the CMK alias target or revoke the IAM grant. 2. Create a new CMK. 3. Bump all DEK versions. 4. Re-encrypt. 5. Rotate the index key if exposed. Day 5 writes the runbook. |

## 5. Ciphertext format `[DECISION D-75]`

A single self-describing string, safe for Text columns and S3 bodies (S3 uses the binary form).

```
ally1.<domain>.<key_version>.<b64url(nonce‖ciphertext‖tag)>
```

| Element | Value |
|---|---|
| Algorithm | AES-256-GCM (`cryptography.hazmat.primitives.ciphers.aead.AESGCM`). The `ally1` prefix pins the algorithm; any change bumps the prefix. |
| Nonce | 12 random bytes per encryption. Never reused. |
| AAD | `ally1|<env>|<domain>|<table>.<column>|<founder_id>`. A row's ciphertext cannot be moved to another founder or column without failing decryption. The row PK is excluded because serial PKs are not known before insert. |
| Binary form (S3) | `b"ALLY1" ‖ u8 domain_id ‖ u32 key_version ‖ nonce ‖ ct ‖ tag`, with S3 object metadata `x-amz-meta-ally-enc: ally1` |
| Empty and NULL | NULL stays NULL. An empty string is encrypted (it is not left as plaintext). |
| Size | Overhead is about 40% (base64) + 28 bytes. `messages.content` is ≤ 8000 characters (`chat/schemas.py`), which fits Text. |

**`founder_data_keys` (Day 2 migration)**

| Column | Type / value |
|---|---|
| `founder_id` | FK `founders`, **no cascade**: deleted explicitly by erasure |
| `domain` | text |
| `key_version` | int |
| `wrapped_dek` | bytea |
| `kms_key_arn` | text |
| `encryption_context` | jsonb |
| `status` | `active` \| `decrypt_only` \| `destroyed` |
| `created_at` | timestamp |
| `destroyed_at` | timestamp |

Primary key: (`founder_id`, `domain`, `key_version`).

## 6. Access control `[DECISION D-76]`

| Principal | KMS permissions | Notes |
|---|---|---|
| ECS task role (runtime `ally_app`) | `GenerateDataKey`, `Decrypt` on `data` and `integration`; HMAC/Decrypt on `index` | Condition: `kms:EncryptionContext:env = <env>` and `kms:EncryptionContext:domain ∈ {…}` |
| Migration task (separate secret, `backend-deploy.yml`) | **none** | Schema changes never need plaintext. Backfill and re-encrypt jobs run as the runtime role through internal jobs. |
| GitHub OIDC deploy role `ally-github-deploy` | none | |
| Human admins (console) | `DescribeKey`, `GetKeyRotationStatus` only. No `Decrypt`. | Break-glass is a separate role with MFA, and use of it is alerted via CloudTrail `[DECISION]`. |
| Admin panel users | none (the app decrypts on their behalf, behind audit) | [DAY1_SECURITY_DECISIONS.md](DAY1_SECURITY_DECISIONS.md) §I |

- **Logging.** CloudTrail data events for KMS `Decrypt` are on for `data` and `integration`. **[UNKNOWN]**: whether CloudTrail is configured.
- **Key deletion.** A CMK can only be deleted with a 30-day waiting period, by a role separate from the runtime role.

## 7. Environment separation `[DECISION D-77]`

| Env | Key provider | Rule |
|---|---|---|
| local / test | `LocalKeyProvider`: a static 32-byte master key from `ALLY_LOCAL_MASTER_KEY`, or one generated per test run | Ciphertext prefix `ally1` with `env=local` in the AAD, so local ciphertext can never decrypt in staging or production. |
| CI | `LocalKeyProvider` with an ephemeral key | |
| staging | KMS, `alias/ally-staging-*` | A separate CMK. **[UNKNOWN]**: whether a separate AWS account exists (recommended). Staging never receives production data or keys. |
| production | KMS, `alias/ally-prod-*` | `KeyProvider` is refused unless `ENVIRONMENT == "production"` **and** `ALLY_KMS_DATA_KEY_ARN` is set. Boot fails rather than falling back to local (same fail-closed rule as auth, D-61). |

Environment variable names (new): `ALLY_KEY_PROVIDER` (`kms` \| `local`), `ALLY_KMS_DATA_KEY_ARN`, `ALLY_KMS_INTEGRATION_KEY_ARN`, `ALLY_KMS_INDEX_KEY_ARN`, `ALLY_LOCAL_MASTER_KEY`, `ALLY_DEK_CACHE_TTL_SECONDS` (default 300), `ALLY_DEK_CACHE_MAX` (default 2048).

## 8. Migrating the Fernet calendar encryption `[DECISION D-78]`

1. **Dual-format decrypt.** Day 2 `EncryptionService.decrypt` accepts both the `ally1.` envelope and legacy Fernet tokens (Fernet tokens start with `gAAAAA`). Legacy Fernet is decrypted with `CALENDAR_TOKEN_KEY` through a `LegacyFernetProvider` that is used only for domain `integration`.
2. **Lazy re-encrypt.** `app/calendar_sync/connections.py` writes the new format on every token refresh and save (`connections.py:56,61,150`).
3. **Backfill job.** An internal job re-encrypts every remaining Fernet token. Metric: the count of legacy rows.
4. **Retire the key.** When the count reaches 0, remove `CALENDAR_TOKEN_KEY` and `LegacyFernetProvider`. The Day 5 checklist covers this.
5. **Error handling.** Decrypt failures keep the `[CODE]` behaviour: the connection is marked `error`, never fall back to plaintext. The error is logged by class name only.

## 9. What stays in Secrets Manager (not KMS envelope)

The following stay as ECS-injected Secrets Manager values:

- `DATABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `SUPABASE_WEBHOOK_SECRET`
- `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`
- `EMAIL_PASSWORD`
- `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_CALENDAR_CREDENTIALS_JSON`
- `INTERNAL_JOBS_SECRET`, `WAITLIST_FORWARD_SECRET`
- `JWT_SIGNING_KEYS`

Rules for these `[DECISION]`:

- every one of them comes from `secrets[]`, never from plain `environment`; **[UNKNOWN]** whether that is true today;
- Secrets Manager rotation is enabled where the vendor supports it;
- each secret has a named owner in the Day 5 runbook.
