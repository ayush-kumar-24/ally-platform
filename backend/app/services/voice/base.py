"""Provider-agnostic speech-to-text interface. Mirrors the embeddings/LLM layers:
the voice endpoint depends only on `TranscriptionProvider`, never on a vendor."""

from __future__ import annotations

import abc


class TranscriptionError(Exception):
    """The provider was reached but failed, or is not configured."""


class TranscriptionProvider(abc.ABC):
    name: str

    @abc.abstractmethod
    def transcribe(self, audio: bytes, *, filename: str, content_type: str) -> str:
        """Return the transcribed text. Raises TranscriptionError on failure."""
        raise NotImplementedError
