"""Unit tests for OpenAIWhisperProvider -- HTTP layer mocked via the `sender` seam,
no network call, deterministic."""

import pytest

from app.services.voice.base import TranscriptionError
from app.services.voice.openai_whisper import OpenAIWhisperProvider, _HttpResult, _TransportError


def _provider(sender, **kwargs):
    return OpenAIWhisperProvider(
        api_key="sk-test", base_url="https://api.openai.com", timeout=5,
        max_retries=2, backoff=0.001, sender=sender, **kwargs,
    )


def test_missing_api_key_raises_at_construction():
    with pytest.raises(TranscriptionError):
        OpenAIWhisperProvider(api_key="", base_url="https://api.openai.com")


def test_successful_transcription_returns_text():
    def sender(url, headers, files, data):
        assert url == "https://api.openai.com/v1/audio/transcriptions"
        assert headers["Authorization"] == "Bearer sk-test"
        assert data["model"] == "whisper-1"
        assert files["file"][0] == "note.webm"
        return _HttpResult(200, {"text": "Hello Ally"}, "")

    provider = _provider(sender)
    text = provider.transcribe(b"audio-bytes", filename="note.webm", content_type="audio/webm")
    assert text == "Hello Ally"


def test_missing_text_field_raises():
    def sender(url, headers, files, data):
        return _HttpResult(200, {"unexpected": "shape"}, "")

    provider = _provider(sender)
    with pytest.raises(TranscriptionError):
        provider.transcribe(b"audio", filename="a.webm", content_type="audio/webm")


def test_4xx_raises_immediately_without_retry():
    calls = []

    def sender(url, headers, files, data):
        calls.append(1)
        return _HttpResult(400, {"error": "bad request"}, "bad request")

    provider = _provider(sender)
    with pytest.raises(TranscriptionError):
        provider.transcribe(b"audio", filename="a.webm", content_type="audio/webm")
    assert len(calls) == 1


def test_5xx_retries_then_succeeds():
    calls = []

    def sender(url, headers, files, data):
        calls.append(1)
        if len(calls) < 2:
            return _HttpResult(500, None, "server error")
        return _HttpResult(200, {"text": "recovered"}, "")

    provider = _provider(sender)
    text = provider.transcribe(b"audio", filename="a.webm", content_type="audio/webm")
    assert text == "recovered"
    assert len(calls) == 2


def test_exhausted_retries_raises():
    def sender(url, headers, files, data):
        return _HttpResult(429, None, "rate limited")

    provider = _provider(sender)
    with pytest.raises(TranscriptionError):
        provider.transcribe(b"audio", filename="a.webm", content_type="audio/webm")


def test_transport_error_retries_then_raises():
    def sender(url, headers, files, data):
        raise _TransportError("connection reset")

    provider = _provider(sender)
    with pytest.raises(TranscriptionError):
        provider.transcribe(b"audio", filename="a.webm", content_type="audio/webm")
