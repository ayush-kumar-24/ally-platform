# Founder Memory — AI integration interface (handoff)

For the Ally orchestrator (M7 / Ayush). This is the contract for plugging the
**Founder Memory** layer into the AI loop. The layer is **structured founder
memory — NOT chat history** (conversations live elsewhere). It is deterministic
(no LLM inside), keyed by a plain `founder_id: int`.

Status: the layer is built and now **DB-backed** (tables `founder_memory` +
`founder_memory_events`, created + RLS-enabled). Wiring it into the orchestrator
is the remaining step — that's what this doc is for.

---

## 1. Construct it (DB-backed)

```python
from app.api.v1.ally.memory.sql_repository import build_db_memory_service

memory = build_db_memory_service(db)   # db: a request-scoped SQLAlchemy Session
```

`build_db_memory_service` returns a `MemoryService` backed by Postgres
(`SqlMemoryRepository` + `SqlMemoryEventRepository`). Each write commits. For
tests/offline use, construct `MemoryService(InMemoryMemoryRepository(), ...)`
instead — same interface.

`founder_id` comes from `AllyContext.founder_id` (M1). Nothing else is needed.

---

## 2. The interface (`MemoryService`)

| Method | Signature (essentials) | When the orchestrator calls it |
|---|---|---|
| `store` | `store(founder_id, memory_type, content, *, importance=50, tags=(), key=None, session_id=None, actor="system", correlation_id=None)` | after learning a durable fact worth remembering (a goal, preference, recurring challenge). Returns the `MemoryItem` (or `None` if the policy declines to remember). |
| `retrieve` | `retrieve(memory_id, *, touch=True, actor=..., correlation_id=...)` | fetch one memory by id; `touch` records the access on the audit trail. |
| `search` | `search(MemorySearchRequest(...)) -> MemorySearchResult` | pull relevant memories before composing a response (filter by type/tags/importance/session/keyword). |
| `update` | `update(memory_id, *, content=None, importance=None, tags=None, actor=..., correlation_id=...)` | revise an existing memory; a new audit snapshot is carried forward. |
| `archive` | `archive(memory_id, *, actor=..., correlation_id=...)` | soft-delete (hidden from search, kept in history). |
| `summarize` | `summarize(founder_id) -> MemorySummary` | a compact roll-up (counts by type/retention, strategic goals, preferences, recurring challenges) for context assembly. |
| `sweep_expired` | `sweep_expired(founder_id=None, *, actor=...)` | housekeeping: archive expired temporary/session memories (run on a schedule or session close). |

**Identity / dedup:** a memory's id is deterministic from
`founder_id + memory_type + session_id + (key or normalised content)`
(`compute_memory_id`). So calling `store` again with the same key/content
**updates** rather than duplicates — safe to call idempotently.

---

## 3. DTOs the orchestrator supplies

- `memory_type: MemoryType` — `working | long_term | session | strategic | preference`.
- `content: str` — the fact, in plain language.
- `importance: int` — 0..100 (retrieval ordering hint; **not** an audit field).
- `tags: tuple[str, ...]` — free tags for filtered search.
- `key: str | None` — a stable key (e.g. `"goal:profitability"`) → makes updates idempotent.
- `session_id: int | None` — set it for session-scoped memories (keeps them isolated per session).
- `correlation_id: str | None` — pass the orchestrator's request/interaction id so every memory event from one AI turn correlates across layers (M-layers). Observational only.

Retention/expiry is decided by the built-in **policy** (`MemoryPolicy`): PERMANENT /
TEMPORARY (TTL) / SESSION. The orchestrator does not manage TTLs.

---

## 4. Suggested call points in the AI loop

1. **Context assembly (before the model call):** `search` / `summarize` to load the
   founder's goals, preferences, recurring challenges → feed into the prompt context.
2. **After the model produces a durable insight:** `store` (or `update` via a stable
   `key`) the fact — pass the turn's `correlation_id`.
3. **Session close:** `sweep_expired(founder_id)`.

The service never calls an LLM, never retrieves documents, never builds prompts —
it only manages structured memory. Keep that boundary: extraction of *what* to
remember is the orchestrator/LLM's job; persistence + lifecycle is this layer's.

---

## 5. Notes

- **Deterministic:** given the same inputs + clock, same results. Inject a `Clock`
  for tests (`FakeClock`).
- **Audit vs content:** `MemoryAudit` (created/updated/accessed counts) is
  observational — it never affects retrieval ordering.
- **Timeline:** every operation appends an immutable `MemoryEvent`
  (`created|updated|accessed|archived|expired`); `founder_memory_events` is the
  append-only log.
- **Tables:** `founder_memory`, `founder_memory_events` (RLS deny-all; the backend
  connects as owner and bypasses RLS). FK to `founders(founder_id)` ON DELETE CASCADE.

Questions / changes to the contract → ping the backend owner before the orchestrator
depends on a new shape.
