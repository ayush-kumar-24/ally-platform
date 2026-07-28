"""OpenAI GPT provider (Chat Completions API) over httpx. No OpenAI SDK.

Thin wiring: the vendor wire format lives in OpenAIAdapter; this class just fixes
the adapter and the default base URL.
"""

from __future__ import annotations

from app.integrations.llm.adapters import OpenAIAdapter
from app.integrations.llm.base import HttpLLMProvider

_DEFAULT_BASE = "https://api.openai.com/v1"


class OpenAIProvider(HttpLLMProvider):
    def __init__(self, *, api_key, model="gpt-4o-mini", base_url=_DEFAULT_BASE,
                 timeout=30.0, client=None, options=None, health_state=None):
        super().__init__(adapter=OpenAIAdapter(), api_key=api_key, model=model,
                         base_url=base_url, timeout=timeout, client=client,
                         options=options, health_state=health_state)
