"""Built-in LLM provider adapters.

Importing this package registers every built-in adapter (openai, anthropic,
gemini) with the LLM registry. The registry imports it lazily on first
`get_provider`, so the deterministic pipeline never imports these adapters.
"""

from app.services.llm.providers import anthropic, gemini, openai  # noqa: F401

__all__ = ["openai", "anthropic", "gemini"]
