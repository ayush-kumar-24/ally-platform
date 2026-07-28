"""AgentOrchestrator + OrchestratorService -- the composition root of Ally.

This is the ONLY layer that imports and composes all six subsystems (M1-M6). No
subsystem knows about any other; only the orchestrator knows everyone, and it does
nothing but coordinate them through their public interfaces.

  * AgentOrchestrator -- the coordinator: holds the subsystems, assigns a request
    id, and runs the PipelineExecutor.
  * OrchestratorService -- the public entry point callers use.
  * build_offline_orchestrator -- convenience wiring for offline/testing (mock
    provider + in-memory repositories); a real deployment injects DB-backed
    subsystems instead.
"""

from __future__ import annotations

import uuid
from typing import Callable

from app.api.v1.ally.execution.provider import MockLLMProvider
from app.api.v1.ally.execution.service import build_execution_service
from app.api.v1.ally.kg.repository import InMemoryKnowledgeGraphRepository
from app.api.v1.ally.kg.service import build_knowledge_graph_service
from app.api.v1.ally.memory.clock import Clock, SystemClock
from app.api.v1.ally.memory.repository import InMemoryMemoryRepository
from app.api.v1.ally.memory.service import build_memory_service
from app.api.v1.ally.orchestrator.executor import OrchestratorConfig, PipelineExecutor
from app.api.v1.ally.orchestrator.schemas import FounderRequest, OrchestratorResponse
from app.api.v1.ally.prompts.library import default_prompt_manager
from app.api.v1.ally.rag.repository import InMemoryVectorRetrievalRepository
from app.api.v1.ally.rag.service import build_retrieval_service


class AgentOrchestrator:
    def __init__(
        self,
        *,
        context_builder,
        memory,
        retrieval,
        knowledge_graph,
        prompt_manager,
        execution,
        clock: Clock | None = None,
        id_factory: Callable[[], str] | None = None,
        config: OrchestratorConfig | None = None,
    ):
        self._executor = PipelineExecutor(
            context_builder=context_builder, memory=memory, retrieval=retrieval,
            knowledge_graph=knowledge_graph, prompt_manager=prompt_manager,
            execution=execution, clock=clock, config=config,
        )
        self._id_factory = id_factory or (lambda: str(uuid.uuid4()))

    def orchestrate(self, request: FounderRequest) -> OrchestratorResponse:
        request_id = request.request_id or self._id_factory()
        return self._executor.run(request, request_id)


class OrchestratorService:
    """Public entry point. Callers depend on this, not on any subsystem."""

    def __init__(self, orchestrator: AgentOrchestrator):
        self._orchestrator = orchestrator

    def handle(self, request: FounderRequest) -> OrchestratorResponse:
        return self._orchestrator.orchestrate(request)


def build_offline_orchestrator(
    *,
    context_builder,
    memory=None,
    retrieval=None,
    knowledge_graph=None,
    prompt_manager=None,
    execution=None,
    clock: Clock | None = None,
    id_factory: Callable[[], str] | None = None,
    config: OrchestratorConfig | None = None,
) -> OrchestratorService:
    """Wire an OrchestratorService with offline defaults. `context_builder` must be
    supplied (M1 needs a repository); the rest default to in-memory/mock subsystems.
    """
    clock = clock or SystemClock()
    orchestrator = AgentOrchestrator(
        context_builder=context_builder,
        memory=memory or build_memory_service(InMemoryMemoryRepository(), clock=clock),
        retrieval=retrieval or build_retrieval_service(InMemoryVectorRetrievalRepository([])),
        knowledge_graph=knowledge_graph or build_knowledge_graph_service(
            InMemoryKnowledgeGraphRepository([], [])
        ),
        prompt_manager=prompt_manager or default_prompt_manager(),
        execution=execution or build_execution_service({"mock": MockLLMProvider()}),
        clock=clock, id_factory=id_factory, config=config,
    )
    return OrchestratorService(orchestrator)
