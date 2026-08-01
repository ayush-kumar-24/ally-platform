"""LLM task->model routing + per-call telemetry -- hermetic (no DB, no network)."""

import asyncio
from decimal import Decimal

import pytest

from app.services.llm.base import (
    LLMConfigurationError,
    LLMMessage,
    LLMProviderError,
    LLMRequest,
    LLMResponse,
    LLMRole,
    LLMUsage,
)
from app.services.llm.router import LLMTask, resolve_task_model
from app.services.llm.telemetry import LoggingLLMProvider, estimate_cost

REQ = LLMRequest(messages=(LLMMessage(role=LLMRole.USER, content="hi"),))


# --- pricing ----------------------------------------------------------------

def test_estimate_cost_sonnet():
    # (1000*3 + 1000*15) / 1e6 = 0.018
    assert estimate_cost("claude-sonnet-5", 1000, 1000) == Decimal("0.018")


def test_estimate_cost_unknown_or_missing_tokens_is_none():
    assert estimate_cost("no-such-model", 1, 1) is None
    assert estimate_cost("claude-sonnet-5", None, 5) is None


# --- router -----------------------------------------------------------------

class _Result:
    def __init__(self, v): self._v = v
    def scalar_one_or_none(self): return self._v


class _FakeDB:
    def __init__(self, row): self._row = row; self.added = []
    def execute(self, stmt): return _Result(self._row)
    def add(self, obj): self.added.append(obj)
    def commit(self): pass
    def close(self): pass


class _Row:
    provider = "anthropic"
    model_id = "claude-sonnet-5"


def test_resolve_task_model_ok():
    tm = resolve_task_model(_FakeDB(_Row()), LLMTask.REPORT_NARRATIVE)
    assert tm.provider == "anthropic" and tm.model_id == "claude-sonnet-5"


def test_resolve_task_model_missing_raises():
    with pytest.raises(LLMConfigurationError):
        resolve_task_model(_FakeDB(None), "unmapped_task")


def test_all_seven_tasks_registered_in_enum():
    assert set(LLMTask.ALL) == {
        "answer_interpretation", "next_question_selection", "distress_detection",
        "diagnosis_reasoning", "answer_consistency", "archetype_assignment", "report_narrative",
    }


# --- telemetry wrapper ------------------------------------------------------

class _FakeProvider:
    name = "fake"
    def __init__(self, resp=None, err=None): self._resp, self._err = resp, err
    async def generate(self, req):
        if self._err: raise self._err
        return self._resp


def _wrap(inner, db):
    return LoggingLLMProvider(inner, task="t", provider="anthropic", model_id="claude-sonnet-5",
                              founder_id=42, session_id=7, session_factory=lambda: db)


def test_ok_call_logs_row_with_cost():
    db = _FakeDB(None)
    resp = LLMResponse(text="ok", model="claude-sonnet-5", provider="anthropic",
                       usage=LLMUsage(input_tokens=1000, output_tokens=1000))
    out = asyncio.run(_wrap(_FakeProvider(resp=resp), db).generate(REQ))
    assert out.text == "ok"
    assert len(db.added) == 1
    row = db.added[0]
    assert row.status == "ok" and row.input_tokens == 1000 and row.output_tokens == 1000
    assert row.estimated_cost_usd == Decimal("0.018")
    assert row.founder_id == 42 and row.session_id == 7 and row.latency_ms is not None


def test_error_call_logs_error_and_reraises():
    db = _FakeDB(None)
    with pytest.raises(LLMProviderError):
        asyncio.run(_wrap(_FakeProvider(err=LLMProviderError("boom")), db).generate(REQ))
    assert len(db.added) == 1 and db.added[0].status == "error" and db.added[0].estimated_cost_usd is None


def test_logging_failure_never_breaks_the_call():
    class _BadDB(_FakeDB):
        def add(self, obj): raise RuntimeError("db down")
    resp = LLMResponse(text="ok", model="m", provider="anthropic",
                       usage=LLMUsage(input_tokens=1, output_tokens=1))
    out = asyncio.run(_wrap(_FakeProvider(resp=resp), _BadDB(None)).generate(REQ))
    assert out.text == "ok"  # telemetry failure swallowed
