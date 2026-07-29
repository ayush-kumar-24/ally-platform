"""Tests for the Ally chat HTTP adapter (Phase 5 integration).

Hermetic: exercises route registration, request validation, and the
OrchestratorResponse -> ChatResponse mapping without a DB or auth (the full
request path needs a seeded founder + token, covered by manual/API testing).
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.api.v1.ally.chat.router import _to_response
from app.api.v1.ally.chat.schemas import ChatRequest
from app.api.v1.ally.execution.schemas import TokenUsage
from app.api.v1.ally.orchestrator.schemas import (
    FounderRequest,
    OrchestratorResponse,
    PipelineContext,
    PipelineMetrics,
    PipelineTrace,
)

T = datetime(2026, 7, 27, tzinfo=timezone.utc)


def _resp(ok=True, failed_step=None):
    metrics = PipelineMetrics(memory_reads=2, retrieval_hits=3, graph_nodes=4,
                              prompt_version=1, token_usage=TokenUsage.of(10, 5))
    trace = PipelineTrace(request_id="r1", started_at=T, finished_at=T, duration_ms=12.5,
                          completed_steps=("build_context", "execute_ai"), failed_step=failed_step,
                          provider="mock", model="mock-standard", metrics=metrics)
    ctx = PipelineContext(request=FounderRequest(founder_id=1, message="hi", request_id="r1"))
    return OrchestratorResponse(
        request_id="r1", ok=ok, answer="hello" if ok else "",
        response_type="answer" if ok else "none",
        confidence=Decimal("0.8") if ok else None,
        citations=("rc:10",) if ok else (), trace=trace, context=ctx,
        error=None if ok else "provider_error: boom",
    )


def test_route_registered():
    import app.main as m
    paths = m.app.openapi()["paths"]
    assert "/api/v1/ally/chat" in paths
    assert "post" in paths["/api/v1/ally/chat"]


def test_request_validation():
    ChatRequest(message="hi")                         # ok
    with pytest.raises(ValidationError):
        ChatRequest(message="")                       # empty message rejected


def test_to_response_happy_path():
    r = _to_response(_resp(ok=True))
    assert r.ok and r.answer == "hello"
    assert r.citations == ["rc:10"] and r.error is None


def test_to_response_hides_confidence_and_internal_trace():
    # Scores are never shown mid-session; internal orchestration detail never leaks.
    r = _to_response(_resp(ok=True))
    fields = r.model_dump()
    assert "confidence" not in fields
    assert "trace" not in fields and "metrics" not in fields
    for leak in ("provider", "model", "total_tokens", "memory_reads", "prompt_version"):
        assert leak not in fields


def test_failure_response_hides_internal_error():
    r = _to_response(_resp(ok=False, failed_step="execute_ai"))
    assert r.ok is False and r.answer == ""
    # Founder-safe message; the raw internal error string is never exposed.
    assert r.error == "The assistant is temporarily unavailable. Please try again."
    assert "provider_error" not in (r.error or "")
