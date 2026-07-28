"""Composition root for the Ally AI stack.

One place that owns the long-lived subsystem instances (repositories, prompt
library, LLM execution) and assembles a per-request AgentOrchestrator from the
FROZEN M1-M7 public interfaces. It modifies no subsystem -- it only wires them.

Why this exists: as real backends arrive (Redis, PostgreSQL, pgvector,
OpenAI/Claude/Gemini) the wiring grows. Keeping it here means every caller stays a
single line -- `container.orchestrator(db)` -- and swapping a backend (e.g. an
in-memory repository for a durable one, or MockLLMProvider for a real provider) is
a change in exactly one file, driven by settings.

Boundaries: composes the AI layer's public interfaces only. It does NOT reach
into any subsystem's internals.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.api.v1.ally.context.builder import AllyContextBuilder
from app.api.v1.ally.context.repository import AllyContextRepository
from app.integrations.llm.routing import build_failover_execution
from app.api.v1.ally.kg.repository import InMemoryKnowledgeGraphRepository
from app.api.v1.ally.kg.service import build_knowledge_graph_service
from app.api.v1.ally.memory.repository import InMemoryMemoryRepository
from app.api.v1.ally.memory.service import build_memory_service
from app.api.v1.ally.orchestrator import AgentOrchestrator, OrchestratorService
from app.api.v1.ally.prompts.library import default_prompt_manager
from app.api.v1.ally.rag.repository import InMemoryVectorRetrievalRepository
from app.api.v1.ally.rag.service import build_retrieval_service


class Container:
    """Owns the AI subsystem singletons and builds orchestrators.

    Stateful stores (memory / retrieval corpus / knowledge graph) are process-level
    singletons so their state persists across requests. Stateless services are
    built once. The context builder is the only per-request piece (it needs the
    request's DB session).
    """

    def __init__(self):
        # --- Repositories / stores (swap these for Redis / Postgres / pgvector) ---
        self._memory_repository = InMemoryMemoryRepository()
        self._retrieval_repository = InMemoryVectorRetrievalRepository([])
        self._kg_repository = InMemoryKnowledgeGraphRepository([], [])

        # --- Services built over those stores (stateless wrappers) ---
        self._memory_service = build_memory_service(self._memory_repository)
        self._retrieval_service = build_retrieval_service(self._retrieval_repository)
        self._kg_service = build_knowledge_graph_service(self._kg_repository)

        # --- Prompt library + LLM execution (register real providers here) ---
        self._prompt_manager = default_prompt_manager()
        self._execution_service = self._build_execution()

    # --- Provider registry ------------------------------------------------

    def _build_execution(self):
        """Wire the LLM execution service from environment + routing configuration.

        `mock` is always registered (deterministic/offline default and the final
        fallback link); OpenAI, Claude and Gemini are registered only when their API
        key is present. LLMRoutingConfig declares the default provider + ordered
        fallback chain; a FailoverLLMProvider (registered as "auto") tries them in
        order, preferring healthy providers. The AIRouter is used unchanged.
        """
        return build_failover_execution()

    # --- Subsystem accessors (seams for future backends) ------------------

    def memory(self):
        return self._memory_service

    def retrieval(self):
        return self._retrieval_service

    def knowledge_graph(self):
        return self._kg_service

    def prompt_manager(self):
        return self._prompt_manager

    def execution(self):
        return self._execution_service

    def context_builder(self, db: Session):
        return AllyContextBuilder(AllyContextRepository(db))

    # --- Composition ------------------------------------------------------

    def orchestrator(self, db: Session) -> OrchestratorService:
        """Assemble a request-scoped OrchestratorService from the owned subsystems."""
        agent = AgentOrchestrator(
            context_builder=self.context_builder(db),
            memory=self.memory(),
            retrieval=self.retrieval(),
            knowledge_graph=self.knowledge_graph(),
            prompt_manager=self.prompt_manager(),
            execution=self.execution(),
        )
        return OrchestratorService(agent)


# Application-wide container instance. Import and use `container.orchestrator(db)`.
container = Container()
