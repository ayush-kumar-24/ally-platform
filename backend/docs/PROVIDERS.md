# LLM & Embedding Provider Adapters

Production adapters that let the reasoning layer talk to external LLM and
embedding services through the vendor-agnostic `LLMProvider` / `EmbeddingProvider`
interfaces. **Engines never see a provider-specific object** — adapters return
only `LLMResponse` and `list[float]`.

## Supported providers

| Kind | Provider | `*_PROVIDER` value | Default model | Endpoint |
|------|----------|--------------------|---------------|----------|
| LLM | OpenAI | `openai` | `gpt-4o-mini` | Chat Completions |
| LLM | Anthropic | `anthropic` | `claude-haiku-4-5-20251001` | Messages |
| LLM | Google Gemini | `gemini` | `gemini-2.0-flash` | generateContent |
| Embeddings | OpenAI | `openai` | `text-embedding-3-small` | Embeddings |
| Embeddings | Gemini | `gemini` | `text-embedding-004` | embedContent |

## Configuration

Selection is by configuration; nothing is hardcoded into the engines.

```bash
# --- LLM answer classifier ---
ANSWER_CLASSIFIER=llm          # 'stored' (default, deterministic) | 'llm'
LLM_PROVIDER=anthropic         # openai | anthropic | gemini
LLM_MODEL=                     # optional; empty -> the adapter's default model

# --- Retrieval embeddings ---
RETRIEVAL_ENABLED=true
EMBEDDING_PROVIDER=openai       # openai | gemini
EMBEDDING_MODEL=                # optional; empty -> the adapter's default
EMBEDDING_DIMENSION=384         # adapters request exactly this dimensionality

# --- Credentials (read from env, never logged) ---
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...

# --- Robustness (applies to every adapter) ---
PROVIDER_TIMEOUT_SECONDS=30
PROVIDER_MAX_RETRIES=3
PROVIDER_BACKOFF_SECONDS=0.5

# --- Optional base-URL overrides (proxies / gateways) ---
OPENAI_BASE_URL=https://api.openai.com
ANTHROPIC_BASE_URL=https://api.anthropic.com
GEMINI_BASE_URL=https://generativelanguage.googleapis.com
```

A selected provider whose API key is missing raises a configuration error at
resolve time — it never silently degrades.

## Robustness

Every adapter (LLM and embeddings) applies, in the shared HTTP base:

- **Retries with exponential backoff** on transport errors, timeouts, HTTP 429
  (rate limit, honouring `Retry-After`), and 5xx.
- **No retry on 4xx** (auth / bad request) — surfaced immediately.
- **Malformed-response handling** — a non-JSON body is retried, then raised.
- **Timeout** per request (`PROVIDER_TIMEOUT_SECONDS`).
- **Structured logging** of metadata only (provider, model, status, attempt,
  latency). API keys, prompts, and response bodies are never logged.

## Boundaries

- Adapters are the *only* place vendor request/response shapes exist. `generate`
  returns `LLMResponse`; `embed` returns `list[float]`. `LLMResponse.raw` is
  `None` — no vendor JSON structure leaks upward.
- Adapters register **lazily**: the built-in adapter package is imported only on
  the first `get_provider(...)`, so the deterministic pipeline (stored-score
  classifier, retrieval disabled) never imports an adapter or `httpx`.
- HTTP uses `httpx`, imported lazily inside the `_send` seam. Tests inject a fake
  sender, so no network or httpx is needed to test adapter logic.

## Embedding dimension compatibility (important)

The retrieval corpus was embedded with **gte-small (384-d)**. Vectors from a
different model are **not comparable**, even at the same dimension count. To use
the OpenAI or Gemini embedding adapter you must **re-embed the corpus** with that
model and set `EMBEDDING_DIMENSION` to match. The `RetrievalEngine` guards on
dimension count; it cannot detect a model mismatch, so this is an operational
requirement.

## Adding a new provider

1. Subclass `BaseHTTPLLMProvider` (or `BaseHTTPEmbeddingProvider`) and implement
   the vendor hooks (`_endpoint`, `_headers`, `_build_payload`, `_parse`).
2. Add a `from_settings()` classmethod and call `register_provider("name", ...)`
   at module bottom.
3. Import it in the `providers/__init__.py` so it self-registers.

No engine, service, or interface changes are required.
