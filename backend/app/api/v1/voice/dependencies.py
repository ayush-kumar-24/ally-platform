from __future__ import annotations

from functools import lru_cache

from app.services.voice import OpenAIWhisperProvider, TranscriptionProvider


@lru_cache(maxsize=1)
def _provider() -> TranscriptionProvider:
    """Process-level singleton -- stateless HTTP client, safe to share across
    requests (same reasoning as the embedding/LLM provider singletons)."""
    return OpenAIWhisperProvider.from_settings()


def get_transcription_provider() -> TranscriptionProvider:
    return _provider()
