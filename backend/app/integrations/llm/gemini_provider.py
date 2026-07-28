"""Google Gemini provider (generateContent API) over httpx. No Google SDK.

Thin wiring: the vendor wire format lives in GeminiAdapter; this class just fixes
the adapter and the default base URL.
"""

from __future__ import annotations

from app.integrations.llm.adapters import GeminiAdapter
from app.integrations.llm.base import HttpLLMProvider

_DEFAULT_BASE = "https://generativelanguage.googleapis.com"


class GeminiProvider(HttpLLMProvider):
    def __init__(self, *, api_key, model="gemini-1.5-flash", base_url=_DEFAULT_BASE,
                 timeout=30.0, client=None, options=None, health_state=None):
        super().__init__(adapter=GeminiAdapter(), api_key=api_key, model=model,
                         base_url=base_url, timeout=timeout, client=client,
                         options=options, health_state=health_state)
