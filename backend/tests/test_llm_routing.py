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


def test_every_task_is_registered_in_the_enum():
    """ALL is what seeds model_task_routing, so a task missing from it has no
    active routing row and raises at first use rather than falling back."""
    assert set(LLMTask.ALL) == {
        "answer_interpretation", "next_question_selection", "distress_detection",
        "diagnosis_reasoning", "answer_consistency", "archetype_assignment",
        "report_narrative", "first_impression",
        "founder_dna_dimension_resolution",
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


def test_reasoning_telemetry_applies_founder_rls_context():
    class _RlsDB(_FakeDB):
        def __init__(self):
            super().__init__(None)
            self.info = {}

        def in_transaction(self):
            return False

    db = _RlsDB()
    founder_uuid = "11111111-1111-1111-1111-111111111111"

    resp = LLMResponse(
        text="ok",
        model="claude-sonnet-5",
        provider="anthropic",
        usage=LLMUsage(input_tokens=10, output_tokens=5),
    )

    wrapped = LoggingLLMProvider(
        _FakeProvider(resp=resp),
        task="archetype_assignment",
        provider="anthropic",
        model_id="claude-sonnet-5",
        founder_id=42,
        founder_uuid=founder_uuid,
        session_id=7,
        session_factory=lambda: db,
    )

    asyncio.run(wrapped.generate(REQ))

    assert db.info["current_founder_uuid"] == founder_uuid
    assert db.added[0].founder_id == 42


def test_provider_for_task_propagates_founder_identity(monkeypatch):
    from app.services.llm import tasks as tasks_module
    from app.services.llm.router import TaskModel

    founder_uuid = "33333333-3333-3333-3333-333333333333"

    class FounderResult:
        def scalar_one_or_none(self):
            return 42

    class FounderDB:
        info = {"current_founder_uuid": founder_uuid}

        def execute(self, stmt):
            return FounderResult()

    base = _FakeProvider()

    monkeypatch.setattr(
        tasks_module,
        "resolve_task_model",
        lambda db, task: TaskModel(
            task=task,
            provider="anthropic",
            model_id="claude-sonnet-5",
        ),
    )
    monkeypatch.setattr(
        tasks_module,
        "get_provider",
        lambda provider: base,
    )

    wrapped = tasks_module.provider_for_task(
        FounderDB(),
        LLMTask.ARCHETYPE_ASSIGNMENT,
    )

    assert wrapped._founder_id == 42
    assert wrapped._founder_uuid == founder_uuid
