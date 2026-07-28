"""Anthropic Claude provider (Messages API) over httpx. No Anthropic SDK.

Thin wiring: the vendor wire format lives in ClaudeAdapter; this class just fixes
the adapter and the default base URL.
"""

from __future__ import annotations

from app.integrations.llm.adapters import ClaudeAdapter
from app.integrations.llm.base import HttpLLMProvider

_DEFAULT_BASE = "https://api.anthropic.com"


class ClaudeProvider(HttpLLMProvider):
    def __init__(self, *, api_key, model="claude-3-5-sonnet-latest", base_url=_DEFAULT_BASE,
                 timeout=30.0, client=None, options=None, health_state=None):
        super().__init__(adapter=ClaudeAdapter(), api_key=api_key, model=model,
                         base_url=base_url, timeout=timeout, client=client,
                         options=options, health_state=health_state)
