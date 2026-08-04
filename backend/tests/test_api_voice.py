"""API tests for the voice transcription endpoint.

Transport + plan-gating tests over the real FastAPI app via TestClient. The
transcription provider is a fake (dependency override) -- no network call, no
OpenAI dependency for these tests.
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_founder_record
from app.api.v1.voice.dependencies import get_transcription_provider
from app.api.v1.voice.validators import MAX_AUDIO_SIZE_BYTES
from app.main import app
from app.services.voice.base import TranscriptionError, TranscriptionProvider

BASE = "/api/v1/voice"


class FakeTranscriptionProvider(TranscriptionProvider):
    name = "fake"

    def __init__(self, text: str = "This is my transcribed answer.", raises: Exception | None = None):
        self._text = text
        self._raises = raises

    def transcribe(self, audio: bytes, *, filename: str, content_type: str) -> str:
        if self._raises is not None:
            raise self._raises
        return self._text


def _client(*, plan_type: str, provider: TranscriptionProvider):
    app.dependency_overrides[get_founder_record] = lambda: SimpleNamespace(
        founder_id=1, plan_type=plan_type,
    )
    app.dependency_overrides[get_transcription_provider] = lambda: provider
    return TestClient(app)


def _teardown():
    app.dependency_overrides.pop(get_founder_record, None)
    app.dependency_overrides.pop(get_transcription_provider, None)


def _audio_file(content: bytes = b"fake-audio-bytes"):
    return {"file": ("note.webm", content, "audio/webm")}


# --- plan gating ---------------------------------------------------------------


def test_free_plan_blocked_from_chat_voice():
    client = _client(plan_type="free", provider=FakeTranscriptionProvider())
    try:
        resp = client.post(f"{BASE}/transcribe", data={"context": "chat"}, files=_audio_file())
        assert resp.status_code == 403
        assert resp.json()["error"] == "FeatureNotInPlanError"
    finally:
        _teardown()


def test_free_plan_allowed_in_diagnosis():
    client = _client(plan_type="free", provider=FakeTranscriptionProvider(text="Churn is the issue."))
    try:
        resp = client.post(f"{BASE}/transcribe", data={"context": "diagnosis"}, files=_audio_file())
        assert resp.status_code == 200
        assert resp.json()["text"] == "Churn is the issue."
    finally:
        _teardown()


@pytest.mark.parametrize("plan", ["starter", "pro"])  # "enterprise" is a DB-level value the catalog doesn't model yet (falls back to Free)
def test_paid_plans_allowed_in_chat(plan):
    client = _client(plan_type=plan, provider=FakeTranscriptionProvider(text="Paid plan works."))
    try:
        resp = client.post(f"{BASE}/transcribe", data={"context": "chat"}, files=_audio_file())
        assert resp.status_code == 200
        assert resp.json()["text"] == "Paid plan works."
    finally:
        _teardown()


@pytest.mark.parametrize("plan", ["starter", "pro"])  # "enterprise" is a DB-level value the catalog doesn't model yet (falls back to Free)
def test_paid_plans_allowed_in_diagnosis(plan):
    client = _client(plan_type=plan, provider=FakeTranscriptionProvider())
    try:
        resp = client.post(f"{BASE}/transcribe", data={"context": "diagnosis"}, files=_audio_file())
        assert resp.status_code == 200
    finally:
        _teardown()


# --- validation ------------------------------------------------------------------


def test_empty_audio_rejected():
    client = _client(plan_type="pro", provider=FakeTranscriptionProvider())
    try:
        resp = client.post(f"{BASE}/transcribe", data={"context": "chat"}, files=_audio_file(b""))
        assert resp.status_code == 422
    finally:
        _teardown()


def test_oversized_audio_rejected():
    client = _client(plan_type="pro", provider=FakeTranscriptionProvider())
    try:
        big = b"x" * (MAX_AUDIO_SIZE_BYTES + 1)
        resp = client.post(f"{BASE}/transcribe", data={"context": "chat"}, files=_audio_file(big))
        assert resp.status_code == 413
    finally:
        _teardown()


def test_invalid_context_rejected():
    client = _client(plan_type="pro", provider=FakeTranscriptionProvider())
    try:
        resp = client.post(f"{BASE}/transcribe", data={"context": "not_a_real_context"}, files=_audio_file())
        assert resp.status_code == 422
    finally:
        _teardown()


# --- provider failure --------------------------------------------------------------


def test_provider_failure_returns_503():
    client = _client(plan_type="pro", provider=FakeTranscriptionProvider(
        raises=TranscriptionError("openai: HTTP 500 after retries"),
    ))
    try:
        resp = client.post(f"{BASE}/transcribe", data={"context": "chat"}, files=_audio_file())
        assert resp.status_code == 503
    finally:
        _teardown()


# --- gating checked BEFORE the paid transcription call runs -----------------------


def test_free_plan_chat_never_reaches_provider():
    """The provider must not be invoked at all for a blocked request -- no wasted
    (paid) API call for a request that was always going to be rejected."""
    class ExplodingProvider(TranscriptionProvider):
        name = "exploding"

        def transcribe(self, audio, *, filename, content_type):
            raise AssertionError("provider.transcribe() must not be called for a blocked request")

    client = _client(plan_type="free", provider=ExplodingProvider())
    try:
        resp = client.post(f"{BASE}/transcribe", data={"context": "chat"}, files=_audio_file())
        assert resp.status_code == 403
    finally:
        _teardown()
