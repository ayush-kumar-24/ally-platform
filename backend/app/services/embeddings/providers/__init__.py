"""Built-in embedding provider adapters.

Importing this package registers the built-in adapters (openai, gemini). The
registry imports it lazily on first `get_provider`, so retrieval-disabled
deployments never import these adapters.
"""

from app.services.embeddings.providers import gemini, openai  # noqa: F401

__all__ = ["openai", "gemini"]
