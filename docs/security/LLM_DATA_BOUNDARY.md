# LLM Data Boundary

Part of the Day 1 security design package. Tags are defined in [DATA_CLASSIFICATION.md](DATA_CLASSIFICATION.md).

## 1. Global rules `[DECISION D-80]`

| # | Rule |
|---|---|
| G1 | **No direct identifiers to any model.** Never send `email`, `phone`, `linkedin_url`, `website`, `social_profiles`, `business_name`, `user_id`, `cognito_sub`, `avatar_*`, or IP/UA. The full name is never sent. Only `ally_chat` and `first_impression` may send the **first name**. |
| G2 | **Name placeholders.** Where a model output must address the founder by name (for example `report_narrative`), send the placeholder `{{founder_first_name}}` and substitute after generation. |
| G3 | **No internal intelligence in founder-facing prompts.** `internal_intelligence_reports.*` (psychological state, distress signals, `internal_notes`) is forbidden in any prompt whose output the founder sees. It may reach only the reasoning tasks that produce or consume it internally. |
| G4 | **Raw chat stays in its conversation.** Raw chat may only go to `ally_chat` for **the same conversation**, and to `memory_extraction` (the founder's own messages only). |
| G5 | **Confirmed memory only.** Memory may only go to `ally_chat`, and only `confirmed` items ([MEMORY_CONTRACT.md](MEMORY_CONTRACT.md) §7). |
| G6 | **Prompts are never persisted or logged.** This applies to prompts and completions everywhere. `llm_call_log` keeps metadata only (`[CODE]` already). Its `error` field is redacted (D-62). |
| G7 | **Restriction gate.** Every task honours `founders.processing_restricted_at` and `deletion_requested_at`. One central check (`may_process`) runs inside `provider_for_task` (`app/services/llm/tasks.py`) and inside `AIExecutionService` for chat, rather than per route. `[CODE]` today this applies only to chat, founder-dna and diagnosis routes. |
| G8 | **Approved vendors only.** A vendor may be configured only if it is listed as approved in the vendor register below. For chat failover (`ALLY_LLM_FALLBACK`), each vendor in the chain must be approved on its own. |
| G9 | **No end-user identifiers to vendors.** Do not send vendor `user`/metadata fields carrying founder ids. If abuse monitoring requires one, use `HMAC(index_key, founder_id)`. |
| G10 | **Gemini key in the header.** The Gemini adapter must send its key in `x-goog-api-key`, not in the URL (`[CODE]` `integrations/llm/adapters.py:184-185`). This prevents URL logging. |

### Vendor register

| Vendor | Current use `[CODE]/[CONFIG]` | Approved? |
|---|---|---|
| Anthropic | All reasoning tasks (`model_task_routing` seeds `claude-sonnet-5`); chat reasoning tier; chat fallback | `[PRODUCT/LEGAL DECISION]` DPA, zero-data-retention (ZDR) and no-training terms `[UNKNOWN]` |
| OpenAI | Chat primary (`ALLY_LLM_PROVIDER=openai`, `gpt-4o-mini`); `daily_quote_selection` (`gpt-5.4-nano`); Whisper; embeddings (off) | `[PRODUCT/LEGAL DECISION]` DPA, ZDR, `store` default `[UNKNOWN]` |
| Google Gemini | Code paths only, not configured | Not approved until decided |
| Gotenberg (self-hosted sidecar) | Report HTML to PDF over `http://localhost:3000` | Approved, because it is in-task. Must stay on localhost (D-81). |

## 2. Per-task contract

**Column definitions:**

- **Current** is `[CODE]`, what the repo sends today.
- **Allowed** and **Forbidden** are `[DECISION]`.
- **Mem** = memory allowed.
- **Chat** = raw chat allowed.
- **Retention/log** is the provider-side retention and local logging requirement.

| Task (`LLMTask` / site) | Provider `[CODE]` | Current input `[CODE]` | Allowed input | Forbidden input | Mem | Chat | PII minimisation | Retention / log |
|---|---|---|---|---|---|---|---|---|
| `ally_chat` (`ChatExecutionService` → `ContextWindowBuilder`, `integrations/llm`) | OpenAI → Anthropic → mock (env); reasoning tier to Anthropic | Current message + last 20 turns; ≤5 raw memory rows from any conversation; founder brief (stage, industry, revenue, team, model, product, problem, goals, vision, motivation, **emotional state**, gaps); **full name**; diagnosis block including internal intelligence; ≤10 task titles; attachment text ≤6000 characters ×5 | Same-conversation turns (≤20); confirmed memories (≤8); brief **without** S4 fields except `emotional_state` as a single coarse tone hint `[PRODUCT/LEGAL DECISION]`; first name; founder-facing report summary + top root-cause names; task titles; attachment text from this conversation's active attachments | Other conversations; deleted or opted-out content; `internal_intelligence_reports.*`; `founder_context.*`; contact fields; full name; `first_impression` | Y (confirmed) | Y (own) | First name only. Revenue stays as a band label. | No local prompt logging. `llm_call_log` holds metadata only. |
| `memory_extraction` (new, [MEMORY_CONTRACT.md](MEMORY_CONTRACT.md) §6) | `[DECISION]` Same vendor as `ally_chat` | n/a | The founder's own messages from one conversation, excluding opted-out ones; existing confirmed memory contents for de-duplication | Assistant replies; S4; names; attachments; other conversations | Y (de-dup only) | Y (own messages) | Strip names, emails and phones from the input with a regex pre-filter | Output validated; nothing logged |
| `next_question_selection` (`diagnosis/advisor.py`) | Anthropic | Founder brief incl. DNA and problem answers, last 5 Q/A, current answer | Same, minus identifiers (already absent) | Name, contact, chat, memory | N | N | Already name-free `[CODE]` | metadata only |
| `answer_interpretation` (`reasoning/engines/diagnostic.py`) | Anthropic | Answer, question, history, brief | Same | Name, contact, chat, memory | N | N | name-free | metadata only |
| `answer_consistency` (`reasoning/engines/consistency.py`) | Anthropic | All Q/A pairs | Same | Name, chat, memory | N | N | | metadata only |
| `distress_detection` (`reasoning/.../distress_language.py`) | Anthropic | Founder's own words + signal catalogue | Same | Name, contact, chat, memory | N | N | | metadata only. The output goes to `internal_intelligence_reports` (APP-ENCRYPT). |
| `diagnosis_reasoning` (recommendation fallback, action-plan balancer, stage inference, calibration) | Anthropic | Root-cause context; answer texts; stage catalogue | Same | Name, contact, chat, memory, `founder_context` | N | N | | The local log may contain the model's stage label only (`stage_detection_llm.py:249`). Never answer text. |
| `archetype_assignment` (`archetype_llm.py`) | Anthropic | Answer texts + archetype catalogue | Same | Name, chat, memory | N | N | | metadata only |
| `report_narrative` (`reports/narrator.py`, gated by `REPORT_NARRATIVE_LLM`) | Anthropic | Section slots incl. **`founder_name` (full name)**, findings, stated symptom, answer quotes, DNA answers | Same slots with `founder_name` replaced by the `{{founder_first_name}}` placeholder (G2) | Full name, contact, chat, memory, `internal_intelligence_reports` | N | N | Placeholder substitution after generation | Output → `founder_reports.narrative_snapshot` (APP-ENCRYPT) |
| `founder_dna_dimension_resolution` (`founder_dna/advisor.py`, `reports/dna_summaries.py`, `founder_dna_summary.py`, `founder_dna_reads.py`) | Anthropic | DNA questions + raw DNA answers | Same | Name, chat, memory | N | N | | Output → `founder_reports.founder_dna._summaries/_reads` (APP-ENCRYPT). Failures are logged by exception class only. |
| `first_impression` (`api/v1/impression/service.py`, `facts.py`) | Anthropic | First name + onboarding free text + emotional state + reflection | First name + onboarding free text | `emotional_state` and `*_reality_signals` `[PRODUCT/LEGAL DECISION]`; contact; chat | N | N | First name only (already `[CODE]`) | Output → `founders.first_impression` (APP-ENCRYPT) |
| `support_routing`, `support_answer` (`support_bot/service.py`) | Anthropic | Founder question + published FAQ | Question + FAQ | Any founder profile, diagnosis, chat or memory data | N | N | Regex-strip emails and phones from the question | `support_bot_misses.question` APP-ENCRYPT; retention per policy |
| `daily_quote_selection` (`quotes/jobs.py`, `quotes/service.py`) | OpenAI | Stage, industry, themes, concern flag | Same (no identifiers) | Anything S3/S4, free text. `current_challenges` may be sent only as **enum codes**, never `_other` text. | N | N | Already id-free | metadata only. Must honour G7 (`[CODE]` the nightly job ignores restriction). |
| Voice transcription (`services/voice/openai_whisper.py`) | OpenAI `whisper-1` | Raw audio | Raw audio (founder-initiated) | — | N | n/a | none possible | Audio never persisted (`[CODE]`). Provider error bodies are not logged verbatim (D-62). |
| Embeddings, chat query (`ally/rag/sql_repository.py`, off by default) | OpenAI / Gemini | Current chat message | Current message, **only if** `RETRIEVAL_ENABLED` and the vendor is approved | History, memory, attachments | N | Y (current msg) | | Vector not stored (`[CODE]`) |
| Embeddings, reasoning enrichment (`reasoning/enrichment.py`) | same | Root-cause catalogue text | Reference text only | Any founder data | N | N | | — |
| PDF render (`reports/gotenberg.py`) | Gotenberg sidecar | Full report HTML | Same | — | — | — | — | D-81: `GOTENBERG_URL` must resolve to localhost or the same task. Reject non-loopback hosts in production. |

**Dead or unwired code** (`app/api/v1/ally/orchestrator/executor.py`) must be deleted (D-55 M5) so it cannot be wired up with the old raw-memory behaviour.

## 3. Enforcement points for Day 3

| Contract | Where |
|---|---|
| G1/G2 name rules | `app/api/v1/ally/prompts/grounding/context_variables.py` (`founder_name`); `reports/plain_words.py` (`_HIDDEN_SLOTS`); `reports/generator.py:449` |
| G3 internal intelligence | `app/api/v1/ally/context/repository.py:49-75` (the chat diagnosis block) |
| G4/G5 chat and memory | `app/ai_chat/builders/context_window.py` (`_safe_memory`, `_compose_message`) |
| G7 restriction | `app/services/llm/tasks.py:provider_for_task`; `app/api/v1/ally/execution/service.py`; `app/quotes/jobs.py` |
| G10 Gemini key | `app/integrations/llm/adapters.py` |
| Prompt never logged | `app/services/llm/telemetry.py`, `app/ai_chat/execution/llm_call_logging.py`. Covered by a test that asserts no prompt substring in any log record (D-63). |
