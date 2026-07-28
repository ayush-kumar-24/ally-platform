"""End-to-end integration tests for the Ally AI Foundation (Phase 5, M1-M7 + M2.1).

Unlike the per-milestone unit tests, these compose the WHOLE stack the way a real
request flows and validate cross-subsystem behaviour and the complete founder
journey:

    FounderRequest -> Context (M1) -> Memory recall (M6) -> Retrieval (M3)
      -> Knowledge Graph (M4) -> Prompt (M2) -> AI Execution (M5)
      -> Memory persistence (M6) -> OrchestratorResponse (M7)

They use the REAL subsystems (real context builder over a seeded in-memory
repository, the real built-in prompt library, real retrieval/graph/memory services)
with only the LLM provider mocked (deterministic, offline). No DB, no network.

The emphasis is on things a single-milestone test cannot show: memory persisted on
one turn being recalled on the next, founder isolation, correlation-id threading
end-to-end, determinism of the whole pipeline, and safety under concurrency.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from itertools import count
from types import SimpleNamespace

import pytest

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
    build_offline_orchestrator,
)
from app.api.v1.ally.orchestrator.executor import OrchestratorConfig
from app.api.v1.ally.prompts import default_prompt_manager
from app.api.v1.ally.prompts.grounding import default_grounded_prompt_manager
from app.api.v1.ally.rag import (
    InMemoryVectorRetrievalRepository,
    KnowledgeChunk,
    build_retrieval_service,
)

T0 = datetime(2026, 7, 28, 9, 0, 0, tzinfo=timezone.utc)
ANSWER = "Here is your grounded answer."
VALID_BODY = json.dumps(
    {"content": ANSWER, "response_type": "answer", "confidence": 0.8, "citations": ["rc:10"]}
)

ALL_STEPS = (
    "build_context", "retrieve_memory", "retrieve_knowledge",
    "expand_graph", "build_prompt", "execute_ai", "persist_memory",
)


# --------------------------------------------------------------------------- #
# Deterministic offline "world"                                               #
# --------------------------------------------------------------------------- #


class FakeClock:
    """Monotonic, deterministic clock -- fixed start, fixed step per read."""

    def __init__(self, now: datetime = T0, step: timedelta = timedelta(seconds=1)):
        self._now, self._step = now, step

    def now(self) -> datetime:
        v = self._now
        self._now += self._step
        return v


class WorldContextRepo:
    """A seeded, multi-founder M1 repository.

      * founders 1 & 2 -> answerable (active report + top root cause)
      * founder 3       -> valid founder, NO active report (not answerable)
      * anything else   -> unknown founder (get_founder returns None)
    """

    _STAGES = {5: "Growth / Scaling", 6: "Early Traction"}
    _INDUSTRIES = {3: "SaaS", 4: "Fintech"}

    def __init__(self):
        self._founders = {
            1: dict(full_name="Asha", stage_id=5, industry_mapped_id=3),
            2: dict(full_name="Bo", stage_id=6, industry_mapped_id=4),
            3: dict(full_name="Cara", stage_id=5, industry_mapped_id=3),
        }
        self._has_report = {1, 2}

    def get_founder(self, fid):
        f = self._founders.get(fid)
        return SimpleNamespace(founder_id=fid, **f) if f else None

    def get_stage(self, sid):
        return SimpleNamespace(stage_name=self._STAGES.get(sid, "Growth / Scaling"))

    def get_industry(self, iid):
        return SimpleNamespace(industry_name=self._INDUSTRIES.get(iid, "SaaS"))

    def get_session(self, sid):
        return SimpleNamespace(overall_confidence_score=Decimal("72"), routing_state="validate",
                               distress_mode_triggered=False, session_state="stable")

    def get_latest_active_report(self, fid, session_id=None):
        if fid not in self._has_report:
            return None
        return SimpleNamespace(report_id=90 + fid, session_id=40 + fid, is_active=True,
                               generated_at=T0, summary="Focus on activation.",
                               session_state_at_generation="stable",
                               insights={"executive_summary": "Focus on activation."})

    def get_detected_root_causes(self, sid):
        return [SimpleNamespace(root_cause_id=10, rank=1, is_top_finding=True,
                                confirmation_status="unconfirmed", final_weighted_score=Decimal("0.8"))]

    def get_root_causes_by_ids(self, ids):
        return {10: SimpleNamespace(root_cause_name="Weak activation", root_cause_code="RC-010",
                                    category="Sales & Revenue")}

    def get_internal_report(self, sid):
        return None


def _retrieval_service():
    chunk = KnowledgeChunk("c1", "rag_chunks", 1, "Guided onboarding lifts activation.",
                           Decimal("0.7"), stage="Growth / Scaling", industry="SaaS",
                           category="Sales & Revenue", root_cause_ids=(10,))
    return build_retrieval_service(InMemoryVectorRetrievalRepository([chunk]))


def _kg_service():
    rc = GraphNode("root_cause:10", NodeType.ROOT_CAUSE, 10, "Weak activation")
    prob = GraphNode("problem:5", NodeType.PROBLEM, 5, "Low trial conversion")
    edge = GraphEdge("root_cause:10", "problem:5", RelationshipType.ROOT_CAUSE_TO_PROBLEM)
    return build_knowledge_graph_service(InMemoryKnowledgeGraphRepository([rc, prob], [edge]))


class Boom:
    """A subsystem whose every method raises -- to simulate unavailability."""

    def __getattr__(self, _name):
        def _raise(*a, **k):
            raise RuntimeError("subsystem down")
        return _raise


class World:
    """One fully-composed, isolated Ally stack + handles for assertions."""

    def __init__(self, *, retrieval=None, knowledge_graph=None, execution=None,
                 prompt_manager=None, ids=None):
        self.repo = WorldContextRepo()
        self.memory = build_memory_service(InMemoryMemoryRepository(), clock=FakeClock())
        self.clock = FakeClock()
        orchestrator = AgentOrchestrator(
            context_builder=AllyContextBuilder(self.repo),
            memory=self.memory,
            retrieval=_retrieval_service() if retrieval is None else retrieval,
            knowledge_graph=_kg_service() if knowledge_graph is None else knowledge_graph,
            prompt_manager=prompt_manager or default_prompt_manager(),
            execution=execution or build_execution_service({"mock": MockLLMProvider(content=VALID_BODY)}),
            clock=self.clock,
            id_factory=ids or (lambda c=count(1): f"req-{next(c)}"),
        )
        self.orchestrator = orchestrator
        self.service = OrchestratorService(orchestrator)

    def ask(self, founder_id=1, message="How do I improve activation?", **kw) -> OrchestratorResponse:
        req = FounderRequest(founder_id=founder_id, message=message, session_id=42, **kw)
        return self.service.handle(req)


# --------------------------------------------------------------------------- #
# 1. Happy path                                                               #
# --------------------------------------------------------------------------- #


def test_happy_path_full_journey():
    r = World().ask()
    assert r.ok and r.answer == ANSWER
    assert r.response_type == "answer" and r.confidence == Decimal("0.8")
    assert r.citations == ("rc:10",)
    assert r.trace.failed_step is None
    assert r.trace.completed_steps == ALL_STEPS                 # every stage ran, in order


def test_happy_path_metrics_reflect_every_subsystem():
    m = World().ask().trace.metrics
    assert m.retrieval_hits == 1                                # M3 matched the seeded chunk
    assert m.graph_nodes == 2                                   # M4 expanded rc -> problem
    assert m.prompt_version == 1                                # M2 built the v1 template
    assert m.memory_reads == 0                                  # first turn: nothing to recall
    assert m.token_usage.total_tokens > 0                       # M5 accounted tokens


# --------------------------------------------------------------------------- #
# 2 & 3. Empty vs. existing founder history (memory feedback across turns)     #
# --------------------------------------------------------------------------- #


def test_empty_founder_history_first_turn():
    r = World().ask(message="First ever question.")
    assert r.ok
    assert r.trace.metrics.memory_reads == 0
    assert r.context.memory_items == ()                        # nothing recalled


def test_existing_founder_history_is_recalled_next_turn():
    world = World()
    world.ask(message="How do I fix activation?")              # turn 1 -> persists to memory
    r2 = world.ask(message="What should I do this week?")      # turn 2 -> recalls turn 1

    assert r2.ok and r2.trace.metrics.memory_reads == 1
    recalled = [m.content for m in r2.context.memory_items]
    assert "How do I fix activation?" in recalled              # the earlier turn came back


# --------------------------------------------------------------------------- #
# 4 & 5. Degraded subsystems -- fail closed, keep answering                    #
# --------------------------------------------------------------------------- #


def test_retrieval_unavailable_still_answers():
    r = World(retrieval=Boom()).ask()
    assert r.ok
    assert "retrieve_knowledge" not in r.trace.completed_steps
    assert r.trace.metrics.retrieval_hits == 0


def test_graph_unavailable_still_answers():
    r = World(knowledge_graph=Boom()).ask()
    assert r.ok
    assert "expand_graph" not in r.trace.completed_steps
    assert r.trace.metrics.graph_nodes == 0


def test_both_retrieval_and_graph_down_still_answers():
    r = World(retrieval=Boom(), knowledge_graph=Boom()).ask()
    assert r.ok
    assert set(r.trace.completed_steps) == {
        "build_context", "retrieve_memory", "build_prompt", "execute_ai", "persist_memory"}


# --------------------------------------------------------------------------- #
# 6. AI timeout -- required stage fails -> failed response                     #
# --------------------------------------------------------------------------- #


def test_ai_timeout_returns_failed_response():
    exec_svc = build_execution_service({"mock": MockLLMProvider(timeout_times=99)}, max_retries=1)
    r = World(execution=exec_svc).ask()
    assert r.ok is False and r.is_empty
    assert r.answer == "" and r.confidence is None
    assert r.trace.failed_step == "execute_ai"
    assert "execute_ai" in r.trace.completed_steps             # it ran, but failed closed


# --------------------------------------------------------------------------- #
# 7. Multiple founder conversations -- isolation                              #
# --------------------------------------------------------------------------- #


def test_multiple_founders_are_isolated():
    world = World()
    world.ask(founder_id=1, message="Founder one question.")
    world.ask(founder_id=2, message="Founder two question.")

    f1 = [m.content for m in world.memory.repository.list_for_founder(1)]
    f2 = [m.content for m in world.memory.repository.list_for_founder(2)]
    assert f1 == ["Founder one question."]
    assert f2 == ["Founder two question."]                     # no cross-contamination


# --------------------------------------------------------------------------- #
# 8. Correlation IDs threaded end-to-end                                       #
# --------------------------------------------------------------------------- #


def test_correlation_id_flows_request_to_memory_event():
    world = World()
    r = world.ask(request_id="corr-123", message="Trace me.")
    assert r.trace.request_id == "corr-123"

    events = world.memory.founder_timeline(1)
    created = [e for e in events if e.event_type == MemoryEventType.CREATED]
    assert created and all(e.correlation_id == "corr-123" for e in created)


def test_request_id_generated_when_absent():
    r = World(ids=lambda: "auto-generated").ask(request_id=None)
    assert r.request_id == "auto-generated"


# --------------------------------------------------------------------------- #
# 9. Pipeline trace                                                            #
# --------------------------------------------------------------------------- #


def test_pipeline_trace_is_complete_and_ordered():
    t = World().ask(request_id="req-x").trace
    assert t.request_id == "req-x"
    assert t.started_at < t.finished_at and t.duration_ms > 0
    assert t.provider == "mock" and t.model in ("mock-standard", "mock-careful")
    assert t.failed_step is None
    assert t.completed_steps == ALL_STEPS


# --------------------------------------------------------------------------- #
# 10. Memory persistence                                                       #
# --------------------------------------------------------------------------- #


def test_message_is_persisted_with_created_event():
    world = World()
    world.ask(message="Persist this thought.")
    stored = world.memory.repository.list_for_founder(1)
    assert len(stored) == 1 and stored[0].content == "Persist this thought."
    assert any(e.event_type == MemoryEventType.CREATED for e in world.memory.founder_timeline(1))


# --------------------------------------------------------------------------- #
# 11. Deterministic execution                                                  #
# --------------------------------------------------------------------------- #


def test_deterministic_execution_across_isolated_runs():
    a = World().ask(request_id="same")
    b = World().ask(request_id="same")
    assert a.answer == b.answer
    assert a.trace.completed_steps == b.trace.completed_steps
    assert a.trace.metrics == b.trace.metrics                  # identical hits/nodes/tokens
    assert a.trace.duration_ms == b.trace.duration_ms          # deterministic clock


# --------------------------------------------------------------------------- #
# 12. Multiple sequential requests -- memory accumulates                       #
# --------------------------------------------------------------------------- #


def test_multiple_requests_accumulate_memory():
    world = World()
    reads = []
    for i in range(1, 4):
        r = world.ask(message=f"Question {i}")                 # distinct content -> new memory
        assert r.ok
        reads.append(r.trace.metrics.memory_reads)
    assert reads == [0, 1, 2]                                  # turn N recalls the prior N-1
    assert len(world.memory.repository.list_for_founder(1)) == 3


# --------------------------------------------------------------------------- #
# 13. Invalid requests -- fail closed with the offending step                  #
# --------------------------------------------------------------------------- #


def test_unknown_founder_fails_at_context():
    r = World().ask(founder_id=999)                            # not in the repo
    assert r.ok is False and r.answer == ""
    assert r.trace.failed_step == "build_context"
    assert r.trace.completed_steps == ()                       # nothing after the failure


def test_founder_without_diagnosis_fails_at_prompt():
    r = World().ask(founder_id=3)                              # valid founder, no active report
    assert r.ok is False
    assert r.trace.failed_step == "build_prompt"               # required diagnosis vars absent
    assert "build_context" in r.trace.completed_steps          # context built (not answerable)


# --------------------------------------------------------------------------- #
# 14. Concurrency                                                              #
# --------------------------------------------------------------------------- #


def test_isolated_stacks_run_safely_in_parallel():
    def journey(_):
        r = World().ask(message="parallel isolated")
        return r.ok and r.answer == ANSWER

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(journey, range(24)))
    assert all(results)


def test_shared_service_handles_interleaved_requests():
    world = World()

    def journey(i):
        fid = 1 if i % 2 == 0 else 2
        r = world.ask(founder_id=fid, message=f"interleaved {i}", request_id=f"rid-{i}")
        return r.ok and r.request_id == f"rid-{i}" and r.answer == ANSWER

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(journey, range(16)))
    assert all(results)                                        # every response correct + correlated


# --------------------------------------------------------------------------- #
# Extra: convenience wiring + M2.1 grounded manager compose end-to-end         #
# --------------------------------------------------------------------------- #


def test_build_offline_orchestrator_convenience_path():
    # The shipped convenience wiring (mock provider + in-memory subsystems) runs a
    # full journey when handed only a context builder.
    svc = build_offline_orchestrator(
        context_builder=AllyContextBuilder(WorldContextRepo()),
        execution=build_execution_service({"mock": MockLLMProvider(content=VALID_BODY)}),
        id_factory=lambda: "off-1",
    )
    r = svc.handle(FounderRequest(founder_id=1, message="hello", session_id=42))
    assert r.ok and r.answer == ANSWER


def test_grounded_prompt_manager_composes_in_full_pipeline():
    # M2.1's GroundedPromptManager is a drop-in PromptManager: the frozen orchestrator
    # calls its inherited render() and the journey still succeeds (backward-compat).
    r = World(prompt_manager=default_grounded_prompt_manager()).ask()
    assert r.ok and r.answer == ANSWER
    assert r.trace.completed_steps == ALL_STEPS


def test_custom_config_persists_with_chosen_importance():
    # OrchestratorConfig is honoured end-to-end (a real composition knob).
    world = World()
    world.orchestrator._executor.config = OrchestratorConfig(persist_importance=90)
    world.ask(message="high importance memory")
    stored = world.memory.repository.list_for_founder(1)
    assert stored and stored[0].metadata.importance == 90
