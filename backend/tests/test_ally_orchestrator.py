"""Unit tests for the Ally Agent Orchestration Layer (Phase 5, Milestone 7).

Fully offline: real M1-M6 subsystems wired with in-memory repos + MockLLMProvider,
and stub subsystems to simulate failures. No DB, no network.
"""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.api.v1.ally.context.builder import AllyContextBuilder
from app.api.v1.ally.execution import MockLLMProvider, build_execution_service
from app.api.v1.ally.kg import (
    GraphEdge,
    GraphNode,
    InMemoryKnowledgeGraphRepository,
    NodeType,
    RelationshipType,
    build_knowledge_graph_service,
)
from app.api.v1.ally.memory import (
    InMemoryMemoryRepository,
    MemoryEventType,
    build_memory_service,
)
from app.api.v1.ally.orchestrator import (
    AgentOrchestrator,
    FounderRequest,
    OrchestratorResponse,
    OrchestratorService,
)
from app.api.v1.ally.prompts import (
    InMemoryPromptRepository,
    PromptManager,
    PromptTemplate,
)
from app.api.v1.ally.rag import (
    InMemoryVectorRetrievalRepository,
    KnowledgeChunk,
    build_retrieval_service,
)

T0 = datetime(2026, 7, 27, 12, 0, 0, tzinfo=timezone.utc)
VALID_BODY = json.dumps({"content": "Here is your grounded answer.", "response_type": "answer",
                         "confidence": 0.8, "citations": ["rc:10"]})


class FakeClock:
    def __init__(self, now=T0, step=timedelta(seconds=1)):
        self._now, self._step = now, step

    def now(self):
        v = self._now
        self._now += self._step
        return v


# --- Fake M1 context repository (answerable context with a root cause) -------


class FakeContextRepo:
    def get_founder(self, fid):
        return SimpleNamespace(founder_id=fid, full_name="Asha", stage_id=5, industry_mapped_id=3)

    def get_stage(self, sid):
        return SimpleNamespace(stage_name="Growth / Scaling")

    def get_industry(self, iid):
        return SimpleNamespace(industry_name="SaaS")

    def get_session(self, sid):
        return SimpleNamespace(overall_confidence_score=Decimal("72"), routing_state="validate",
                               distress_mode_triggered=False, session_state="stable")

    def get_latest_active_report(self, fid, session_id=None):
        return SimpleNamespace(report_id=99, session_id=42, is_active=True, generated_at=T0,
                               summary="Focus on activation.", session_state_at_generation="stable",
                               insights={"executive_summary": "Focus on activation."})

    def get_detected_root_causes(self, sid):
        return [SimpleNamespace(root_cause_id=10, rank=1, is_top_finding=True,
                                confirmation_status="unconfirmed", final_weighted_score=Decimal("0.8"))]

    def get_root_causes_by_ids(self, ids):
        return {10: SimpleNamespace(root_cause_name="Weak activation", root_cause_code="RC-010",
                                    category="Sales & Revenue")}

    def get_internal_report(self, sid):
        return None


def context_builder():
    return AllyContextBuilder(FakeContextRepo())


def prompt_manager():
    tmpl = PromptTemplate(
        template_key="answer.v1", version=1, category="diagnosis_answer",
        system_prompt="You are Ally.", user_prompt="Answer {{founder_name}} at {{stage_name}}.",
        required_variables=("founder_name", "stage_name"),
    )
    return PromptManager(InMemoryPromptRepository([tmpl]))


def retrieval_service():
    chunk = KnowledgeChunk("c1", "rag", 1, "activation tips", Decimal("0.7"),
                           stage="Growth / Scaling", industry="SaaS",
                           category="Sales & Revenue", root_cause_ids=(10,))
    return build_retrieval_service(InMemoryVectorRetrievalRepository([chunk]))


def kg_service():
    rc, prob = GraphNode("root_cause:10", NodeType.ROOT_CAUSE, 10, "rc"), GraphNode("problem:5", NodeType.PROBLEM, 5, "p")
    edges = [GraphEdge("root_cause:10", "problem:5", RelationshipType.ROOT_CAUSE_TO_PROBLEM)]
    return build_knowledge_graph_service(InMemoryKnowledgeGraphRepository([rc, prob], edges))


def make(*, memory=None, retrieval=None, knowledge_graph=None, execution=None, clock=None):
    clock = clock or FakeClock()
    mem = memory or build_memory_service(InMemoryMemoryRepository(), clock=FakeClock())
    return AgentOrchestrator(
        context_builder=context_builder(),
        memory=mem,
        retrieval=retrieval or retrieval_service(),
        knowledge_graph=knowledge_graph or kg_service(),
        prompt_manager=prompt_manager(),
        execution=execution or build_execution_service({"mock": MockLLMProvider(content=VALID_BODY)}),
        clock=clock,
        id_factory=lambda: "generated-id",
    ), mem


def request(**kw):
    base = dict(founder_id=1, message="I want to raise funding.", session_id=42, request_id="req-1")
    base.update(kw)
    return FounderRequest(**base)


class Boom:
    """A subsystem stub whose every method raises -- to simulate unavailability."""
    def __getattr__(self, _name):
        def _raise(*a, **k):
            raise RuntimeError("subsystem down")
        return _raise


# --- Happy path -------------------------------------------------------------


def test_complete_happy_path():
    orch, _ = make()
    r = orch.orchestrate(request())
    assert r.ok and r.answer == "Here is your grounded answer."
    assert r.response_type == "answer" and r.confidence == Decimal("0.8")
    assert r.trace.failed_step is None
    assert r.trace.completed_steps == (
        "build_context", "retrieve_memory", "retrieve_knowledge",
        "expand_graph", "build_prompt", "execute_ai", "persist_memory",
    )


def test_pipeline_metrics_populated():
    r, _ = make()[0].orchestrate(request()), None
    m = r.trace.metrics
    assert m.retrieval_hits == 1
    assert m.graph_nodes == 2
    assert m.memory_reads == 0                    # fresh memory, nothing to recall yet
    assert m.prompt_version == 1
    assert m.token_usage.total_tokens > 0


def test_pipeline_trace_fields():
    r = make()[0].orchestrate(request())
    t = r.trace
    assert t.request_id == "req-1"
    assert t.finished_at > t.started_at and t.duration_ms > 0
    assert t.provider == "mock" and t.model in ("mock-standard", "mock-careful")


def test_request_id_used_or_generated():
    orch, _ = make()
    assert orch.orchestrate(request(request_id="explicit")).request_id == "explicit"
    assert orch.orchestrate(request(request_id=None)).request_id == "generated-id"


# --- Fail-closed: continue on subsystem failure -----------------------------


def test_retrieval_unavailable_continues():
    orch, _ = make(retrieval=Boom())
    r = orch.orchestrate(request())
    assert r.ok                                    # AI still answered
    assert "retrieve_knowledge" not in r.trace.completed_steps
    assert r.trace.metrics.retrieval_hits == 0


def test_graph_unavailable_continues():
    orch, _ = make(knowledge_graph=Boom())
    r = orch.orchestrate(request())
    assert r.ok
    assert "expand_graph" not in r.trace.completed_steps
    assert r.trace.metrics.graph_nodes == 0


def test_memory_unavailable_continues():
    orch, _ = make(memory=Boom())
    r = orch.orchestrate(request())
    assert r.ok
    assert "retrieve_memory" not in r.trace.completed_steps
    assert "persist_memory" not in r.trace.completed_steps


def test_multiple_subsystem_failures_still_answers():
    orch, _ = make(retrieval=Boom(), knowledge_graph=Boom())
    r = orch.orchestrate(request())
    assert r.ok
    assert set(r.trace.completed_steps) == {"build_context", "retrieve_memory", "build_prompt",
                                            "execute_ai", "persist_memory"}


# --- AI failure -------------------------------------------------------------


def test_ai_timeout_returns_failed_response():
    orch, _ = make(execution=build_execution_service({"mock": MockLLMProvider(timeout_times=99)}, max_retries=1))
    r = orch.orchestrate(request())
    assert r.ok is False and r.is_empty
    assert r.answer == "" and r.confidence is None
    assert r.trace.failed_step == "execute_ai"
    assert "execute_ai" in r.trace.completed_steps       # it ran, but failed


# --- Memory persistence + correlation ---------------------------------------


def test_memory_persisted_after_response_with_correlation_id():
    orch, mem = make()
    orch.orchestrate(request(request_id="req-xyz"))
    stored = mem.repository.list_for_founder(1)
    assert len(stored) == 1 and stored[0].content == "I want to raise funding."
    events = mem.founder_timeline(1)
    assert any(e.event_type == MemoryEventType.CREATED and e.correlation_id == "req-xyz" for e in events)


# --- Determinism + no-duplicate-orchestration -------------------------------


def test_deterministic_execution():
    a = make()[0].orchestrate(request())
    b = make()[0].orchestrate(request())
    assert a.answer == b.answer
    assert a.trace.completed_steps == b.trace.completed_steps
    assert a.trace.metrics == b.trace.metrics


def test_no_duplicate_orchestration_calls_each_subsystem_once():
    calls = {"execute": 0, "retrieve": 0}
    real_exec = build_execution_service({"mock": MockLLMProvider(content=VALID_BODY)})
    real_retr = retrieval_service()

    class CountingExec:
        def execute(self, req):
            calls["execute"] += 1
            return real_exec.execute(req)

    class CountingRetr:
        def retrieve(self, ctx, query, **kw):
            calls["retrieve"] += 1
            return real_retr.retrieve(ctx, query, **kw)

    orch = AgentOrchestrator(
        context_builder=context_builder(), memory=build_memory_service(InMemoryMemoryRepository(), clock=FakeClock()),
        retrieval=CountingRetr(), knowledge_graph=kg_service(), prompt_manager=prompt_manager(),
        execution=CountingExec(), clock=FakeClock(), id_factory=lambda: "x",
    )
    orch.orchestrate(request())
    assert calls == {"execute": 1, "retrieve": 1}


# --- Public entry point -----------------------------------------------------


def test_orchestrator_service_entry_point():
    orch, _ = make()
    svc = OrchestratorService(orch)
    r = svc.handle(request())
    assert isinstance(r, OrchestratorResponse) and r.ok
