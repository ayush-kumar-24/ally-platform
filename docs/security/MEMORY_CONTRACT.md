# Founder Memory Contract (L3)

Part of the Day 1 security design package. Tags are defined in [DATA_CLASSIFICATION.md](DATA_CLASSIFICATION.md).

> **Principle:** Ally remembers what is useful, not everything that was said. A memory is a short, structured statement about the founder that the founder can see, correct, delete or turn off. Raw conversation is never memory.

## 1. Current state `[CODE]`

Live writers:

| Writer | What it stores |
|---|---|
| `ChatExecutionService.send_message` (`app/ai_chat/execution/chat_execution.py:215-226`) | **Every founder message verbatim** as `MemoryType.WORKING`, importance 50, `Retention.TEMPORARY`, `expires_at = now + 7d` (`app/api/v1/ally/memory/policy.py`) |
| `ReasoningService._record_diagnosis_memory` (`app/api/v1/reasoning/service.py`) | The report executive summary as STRATEGIC / 90 / PERMANENT, key `diagnosis_summary` |

Readers and gaps:

- **Reader:** `ContextWindowBuilder._safe_memory` searches by `founder_id` only (limit 5), across all conversations. The results go into the grounded chat prompt under "What we remember about them".
- **Expiry hides, never deletes.** `sweep_expired` has no caller.
- **No founder API.** There is no way for the founder to view, edit, delete or disable memory.
- **Plaintext storage.** The `memory_id` is a sha256 of the content.
- **Dead code:** `app/api/v1/ally/orchestrator/*`.

## 2. Memory kinds `[DECISION D-50]`

A new column `memory_kind` replaces `memory_type` semantics for all new rows.

| `memory_kind` | Meaning | Example `content` | Typical sources | Default expiry |
|---|---|---|---|---|
| `fact` | Stable fact about the founder or business | "Runs a B2B SaaS for clinics; 6 people." | onboarding, chat extraction | none (review prompt at 12 months) |
| `goal` | Something the founder is working towards, with an optional `target_date` | "Close seed round by March 2027." | `founders.goal_90_day`, `vision_1_year`, `founder_goals`, chat extraction | `target_date + 30d`; no date means 180 days |
| `preference` | How they want Ally to work with them | "Prefers blunt feedback, short answers." | settings, chat extraction | none |
| `constraint` | A limit Ally must respect | "Cannot raise outside capital." | chat extraction | none (review at 12 months) |
| `context` | Time-bound situation | "Co-founder leaving next month." | chat extraction | 90 days |
| `diagnosis_summary` | System-generated: latest report summary | executive summary of the active report | `ReasoningService` | replaced when a new report is persisted |

**What a memory never contains `[DECISION]`:**

- verbatim message text;
- any S4 data (emotional state, distress, psychological state, socio-economic context; [DATA_CLASSIFICATION.md](DATA_CLASSIFICATION.md) rule 3);
- contact details or identity data;
- third-party personal data beyond a role ("co-founder", "first hire");
- attachment content;
- credentials.

## 3. Record shape (target, implemented on Day 3)

| Field | Type | Rule |
|---|---|---|
| `memory_id` | random id (uuid4 hex) | `[DECISION]` Replaces the content-hash id (`memory/schemas.py:compute_memory_id`), which leaks equality. |
| `founder_id` | FK `founders` CASCADE | Owner. Every query filters on it. |
| `memory_kind` | enum (§2) | required |
| `content` | ciphertext (APP-ENCRYPT, domain `memory`) | ≤ 500 characters of plaintext; a single statement |
| `source_type` | enum `founder_entered` \| `onboarding` \| `chat_extraction` \| `diagnosis` \| `admin` | required. `admin` is reserved and not used. |
| `source_conversation_id`, `source_message_id` | nullable | Set for `chat_extraction`. Set to NULL when the founder confirms the memory and the source is later deleted (see the lifecycle in §4). |
| `confidence` | numeric 0–1 | Required for `chat_extraction` (extractor output). `1.0` for `founder_entered` and `onboarding`. |
| `status` | `proposed` \| `confirmed` \| `rejected` \| `archived` | §4 |
| `confirmed_at`, `confirmed_by` | timestamp, `founder` \| `auto` | |
| `expires_at` | nullable | §2 defaults |
| `importance` | 0–100 | Kept for ordering only. No longer drives retention. |
| `key` | nullable | Upsert key for system kinds (`diagnosis_summary`) |
| `created_at`, `updated_at`, `access_count`, `accessed_at` | | keep `[CODE]` |

`founder_memory_events` stays append-only and **never holds content**: event type, actor, `memory_id`, correlation id, and `details` with no text (`[CODE]` already).

## 4. Lifecycle

```
                 founder confirms
 extraction ──► proposed ─────────────► confirmed ──► archived (expiry / superseded)
                 │   │                     │
     rejects ────┘   └─ 14d unconfirmed    └─ founder edits → stays confirmed, updated_at
        ▼               ▼ (hard delete)
     rejected (content wiped, row kept for 30d to suppress re-proposal, then deleted)

 founder_entered / onboarding ──► confirmed directly
 diagnosis ──► confirmed (system), key='diagnosis_summary', replaced per report
 any state ──founder delete──► hard delete (+ event)
```

| Rule | Contract |
|---|---|
| Confirmation | `[DECISION D-51]` Only `confirmed` memories enter AI context. A `chat_extraction` memory starts as `proposed` and is shown to the founder, e.g. "Ally noticed… keep this?". |
| Auto-confirm | `[PRODUCT/LEGAL DECISION]` Whether proposals with `confidence ≥ 0.9` may auto-confirm after the founder is notified. Default: **off**. |
| Unconfirmed expiry | A `proposed` memory is hard-deleted after 14 days if not confirmed `[DECISION]`. |
| Rejected | Content is wiped immediately. A content-free fingerprint (`HMAC(index_key, normalised_text)`, a blind index) is kept for 30 days so the same proposal is not re-raised. |
| Expiry | `expires_at` passes, then `archived`. Archived memories are excluded from context and hard-deleted after 30 days. The sweep is the internal job `purge-memory`, which replaces the uncalled `MemoryService.sweep_expired`. |
| Source deleted | Per [DATA_LIFECYCLE.md](DATA_LIFECYCLE.md) RC-2: `proposed` rows are hard-deleted; `confirmed` rows survive with their source ids nulled. RC-9 "forget" deletes both. |
| Erasure | Hard delete of all rows and events (already in `_HARD_DELETE_TABLES`, `[CODE]`). |

## 5. Founder controls (target API, Day 3)

All routes take the founder from the token (`get_founder_record`) and filter by `founder_id`. A foreign `memory_id` returns **404**.

| Method | Path | Effect |
|---|---|---|
| GET | `/api/v1/memory` | List the founder's memories: confirmed and proposed, with kind, source and created date |
| POST | `/api/v1/memory` | Founder adds a memory (`source_type=founder_entered`, `confirmed`) |
| PATCH | `/api/v1/memory/{memory_id}` | Edit content or kind; confirm or reject a proposal |
| DELETE | `/api/v1/memory/{memory_id}` | Hard delete |
| DELETE | `/api/v1/memory` | Delete all (needs `{"confirm": true}`) |
| GET/PATCH | `/api/v1/settings/memory` | `founder_settings.memory_enabled` (default `true` `[PRODUCT/LEGAL DECISION]`) |

**Disable `[DECISION D-52]`:** when `memory_enabled=false`:

- no extraction runs;
- no memory is injected into any prompt;
- `diagnosis_summary` is still written, because the report needs it, but it is not injected into chat;
- existing rows are kept until the founder chooses "delete all".

Privacy export (`GET /privacy/export`) must decrypt and include memories (`[CODE]` already exports `founder_memory`).

## 6. How memory is created from chat `[DECISION D-53]`

1. **No inline writes.** A chat turn never writes memory. `chat_execution.py:215-226` is removed (RC-11).
2. **Extraction job.** A new task, `LLMTask.MEMORY_EXTRACTION`, runs asynchronously over conversations with new messages. It runs either at most once per conversation per hour, or when the conversation is idle for 30 minutes.
3. **Skipped messages.** It skips messages with `memory_opt_out`, conversations with `memory_opt_out`, and founders with `memory_enabled=false` or a processing restriction.
4. **Input (see [LLM_DATA_BOUNDARY.md](LLM_DATA_BOUNDARY.md)):**
   - the founder's own messages from that conversation only, never the assistant replies;
   - the list of existing confirmed memory **kinds and contents** for de-duplication;
   - no S4 fields and no names.
5. **Output:** at most 3 candidate memories per run, as JSON `{kind, content, confidence}`. Each candidate is validated against §2 (length, kind, and a forbidden-content check). Invalid candidates are dropped.
6. **Storage.** Valid candidates are stored as `proposed`, with `source_conversation_id` and `source_message_id`.
7. **Logging.** The extraction prompt and response are never logged. `llm_call_log` holds metadata only.

Onboarding (`founders.goal_90_day`, `vision_1_year`, `building_summary`) and `founder_goals` may seed `goal` and `fact` memories as `confirmed`, because the founder typed them into a form whose purpose is shown to them. `[PRODUCT/LEGAL DECISION]` Whether this needs explicit opt-in.

## 7. How memory enters AI context `[DECISION D-54]`

| Rule | Contract |
|---|---|
| Who reads | `ContextWindowBuilder` for `ally_chat` only. No other LLM task receives memory. |
| Filter | `founder_id = :fid AND status = 'confirmed' AND (expires_at IS NULL OR expires_at > now())`. The founder must also have `memory_enabled`. |
| Budget | ≤ 8 items, ≤ 280 characters each (keeps `[CODE]` `flatteners.memory_summary` clamp), ordered by kind priority (`constraint` > `goal` > `preference` > `fact` > `context` > `diagnosis_summary`), then by `updated_at`. |
| Rendering | As a labelled list: `- [goal] …`. Never as quoted founder speech. |
| Access stats | Update `access_count` and `accessed_at` without writing an event per read (avoids event-table growth). |

## 8. Migration away from raw WORKING memory `[DECISION D-55]`

Each phase ships independently. No phase needs the next one to be safe.

| Phase | Day | Change | Verification |
|---|---|---|---|
| M0: stop the bleed | Day 3 | Remove the `memory.store(... MemoryType.WORKING, request.message ...)` call in `ChatExecutionService.send_message`. Change `_safe_memory` to search `memory_type IN ('strategic','long_term','preference')`, which excludes `working` and `session`. | Test: a chat turn writes 0 `founder_memory` rows. Test: a WORKING row is never in the prompt. Update `tests/test_chat_llm_call_logging.py:296`, which asserts the old behaviour. |
| M1: purge legacy | Day 4 | One-off internal job: hard-delete all `founder_memory` rows with `memory_type IN ('working','session')`, plus their `founder_memory_events` content (events hold no content today). Record counts only. Rows in backups expire with the backup window ([RETENTION_AND_ERASURE_POLICY.md](RETENTION_AND_ERASURE_POLICY.md) §5). | Count = 0 after the job. Audit event recorded. |
| M2: new schema | Day 3 (migration) | Add the columns in §3. Backfill `diagnosis_summary` rows as `memory_kind='diagnosis_summary'`, `source_type='diagnosis'`, `status='confirmed'`. Re-encrypt `content` under the `memory` domain. Replace the content-hash `memory_id` with a random id. | Migration test on a copy of the schema |
| M3: founder controls | Day 3–4 | §5 API + settings flag | Cross-founder tests ([DAY1_SECURITY_DECISIONS.md](DAY1_SECURITY_DECISIONS.md) §I) |
| M4: extraction | after Day 5 `[PRODUCT/LEGAL DECISION]` | §6 job behind flag `MEMORY_EXTRACTION_ENABLED` (default off) | Eval set; no S4 leakage test |
| M5: clean up | Day 5 | Delete dead code: `app/api/v1/ally/orchestrator/*`, `MemoryType.WORKING`/`SESSION` writers, `MemoryPolicy` TTL rules for WORKING. Update `backend/docs/founder_memory_integration.md`. | grep finds no writers |
