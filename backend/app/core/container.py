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
from app.api.v1.ally.prompts.grounding import default_grounded_prompt_manager
from app.ai_chat.builders.context_window import ContextWindowBuilder
from app.ai_chat.execution.chat_execution import ChatExecutionService
from app.ai_chat.services.conversation import build_conversation_service
from app.ai_chat.streaming.service import StreamingChatService
from app.ai_chat.attachments.repository import InMemoryAttachmentRepository
from app.ai_chat.attachments.service import AttachmentService
from app.ai_chat.links.extractor import LinkExtractor
from app.ai_chat.suggestions.repository import InMemorySuggestionRepository
from app.ai_chat.suggestions.service import SuggestionService
from app.settings.repository import SqlAlchemySettingsRepository
from app.settings.service import SettingsService
from app.admin.audit import InMemoryAuditRepository
from app.admin.permissions import AdminRegistry
from app.admin.repository import InMemoryAdminRepository, InMemoryAnnouncementRepository
from app.admin.service import AdminService


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

        # --- Phase 6 AI Chat flow (Milestone 2) -- additive, composes the frozen
        # foundation. The orchestrator wiring above is untouched. Conversations are
        # a process-level store (swap for a DB repository later); the grounded
        # prompt manager is separate from the orchestrator's standard manager.
        self._conversation_service = build_conversation_service()
        self._grounded_prompt_manager = default_grounded_prompt_manager()
        self._context_window_builder = ContextWindowBuilder(
            conversation_service=self._conversation_service,
            memory=self._memory_service,
            retrieval=self._retrieval_service,
            knowledge_graph=self._kg_service,
        )

        # --- Phase 6 attachments + links (Milestone 4) -- additive, metadata only.
        # Attachments are a process-level store (swap for a DB repository later); the
        # link extractor is pure/stateless.
        self._attachment_repository = InMemoryAttachmentRepository()
        self._attachment_service = AttachmentService(self._attachment_repository)
        self._link_extractor = LinkExtractor()

        # --- Phase 6 AI suggestions (Milestone 5) -- additive, deterministic,
        # rule-based; composes chat artifacts, never executes actions or calls an LLM.
        self._suggestion_repository = InMemorySuggestionRepository()
        self._suggestion_service = SuggestionService(self._suggestion_repository)

        # --- Phase 12 admin & operations (independent) -- process-level in-memory
        # repositories (a production adapter reads the DB + ai_chat stores). The admin
        # registry (email -> role allowlist) is loaded from the environment.
        self._admin_repository = InMemoryAdminRepository()
        self._announcement_repository = InMemoryAnnouncementRepository()
        self._audit_repository = InMemoryAuditRepository()
        self._admin_registry = AdminRegistry()

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

    # --- Phase 6 chat flow accessors --------------------------------------

    def conversation_service(self):
        return self._conversation_service

    def context_window_builder(self):
        return self._context_window_builder

    def grounded_prompt_manager(self):
        return self._grounded_prompt_manager

    def chat_execution(self, db: Session) -> ChatExecutionService:
        """Assemble a request-scoped ChatExecutionService: the per-request context
        builder (needs the DB session) over the process-level conversation store,
        context-window builder, grounded prompt manager and execution service."""
        return ChatExecutionService(
            context_builder=self.context_builder(db),
            conversation_service=self._conversation_service,
            context_window_builder=self._context_window_builder,
            prompt_manager=self._grounded_prompt_manager,
            execution=self._execution_service,
        )

    def streaming_chat(self, db: Session) -> StreamingChatService:
        """Assemble a request-scoped StreamingChatService that wraps the chat flow.
        Additive: it composes the existing ChatExecutionService and the shared
        conversation store; no existing service is changed."""
        return StreamingChatService(
            chat_service=self.chat_execution(db),
            conversation_service=self._conversation_service,
        )

    # --- Phase 6 attachments + links accessors ----------------------------

    def attachment_service(self) -> AttachmentService:
        return self._attachment_service

    def link_extractor(self) -> LinkExtractor:
        return self._link_extractor

    def suggestion_service(self) -> SuggestionService:
        return self._suggestion_service

    # --- Phase 11 settings (DB-backed, per-request) -----------------------

    def settings_service(self, db: Session) -> SettingsService:
        """Request-scoped SettingsService over the SQLAlchemy repository. Tests
        override the endpoint dependency with an in-memory-backed service."""
        return SettingsService(SqlAlchemySettingsRepository(db))

    # --- Phase 12 admin accessors -----------------------------------------

    def admin_registry(self) -> AdminRegistry:
        return self._admin_registry

    def admin_service(self) -> AdminService:
        return AdminService(
            admin_repository=self._admin_repository,
            announcement_repository=self._announcement_repository,
            audit_repository=self._audit_repository,
        )


# Application-wide container instance. Import and use `container.orchestrator(db)`.
container = Container()
