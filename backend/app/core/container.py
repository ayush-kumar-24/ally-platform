"""Composition root for the Ally AI stack.

One place that owns the long-lived subsystem instances (repositories, prompt
library, LLM execution) and assembles per-request services from the FROZEN M1-M7
public interfaces. It modifies no subsystem -- it only wires them.

Why this exists: as real backends arrive (Redis, PostgreSQL, pgvector,
OpenAI/Claude/Gemini) the wiring grows. Keeping it here means every caller stays a
single line -- `container.chat_execution(db)` -- and swapping a backend (e.g. an
in-memory repository for a durable one, or MockLLMProvider for a real provider) is
a change in exactly one file, driven by settings.

Boundaries: composes the AI layer's public interfaces only. It does NOT reach
into any subsystem's internals.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.api.v1.ally.context.builder import AllyContextBuilder
from app.api.v1.ally.context.repository import AllyContextRepository
from app.integrations.llm.routing import build_failover_execution
from app.api.v1.ally.kg.repository import InMemoryKnowledgeGraphRepository
from app.api.v1.ally.kg.service import build_knowledge_graph_service
from app.api.v1.ally.memory.sql_repository import build_db_memory_service
from app.api.v1.ally.prompts.library import default_prompt_manager
from app.api.v1.ally.rag.repository import InMemoryVectorRetrievalRepository
from app.api.v1.ally.rag.service import build_retrieval_service
from app.api.v1.ally.rag.sql_repository import SqlVectorRetrievalRepository
from app.api.v1.ally.prompts.grounding import default_grounded_prompt_manager
from app.ai_chat.builders.context_window import ContextWindowBuilder
from app.ai_chat.execution.chat_execution import ChatExecutionService
from app.ai_chat.execution.llm_call_logging import record_chat_llm_call
from app.ai_chat.repositories.sql_conversation import SqlConversationRepository
from app.ai_chat.services.conversation import build_conversation_service
from app.ai_chat.streaming.service import StreamingChatService
from app.ai_chat.attachments.service import AttachmentService
from app.ai_chat.attachments.sql_repository import SqlAttachmentRepository
from app.ai_chat.links.extractor import LinkExtractor
from app.ai_chat.suggestions.service import SuggestionService
from app.ai_chat.suggestions.sql_repository import SqlSuggestionRepository
from app.settings.repository import SqlAlchemySettingsRepository
from app.settings.service import SettingsService
from app.admin.audit import InMemoryAuditRepository
from app.admin.permissions import AdminRegistry
from app.admin.repository import InMemoryAdminRepository, InMemoryAnnouncementRepository
from app.admin.service import AdminService
from app.planning.db_repository import SqlAlchemyPlanningRepository
from app.planning.service import PlanningService
from app.founder_goals.db_repository import SqlAlchemyFounderGoalRepository
from app.founder_goals.service import FounderGoalService
from app.achievements.db_repository import SqlAlchemyAchievementRepository
from app.achievements.service import AchievementService
from app.vision.db_repository import SqlAlchemyVisionRepository
from app.vision.service import VisionService
from app.framework_usage.db_repository import SqlAlchemyFrameworkUsageRepository
from app.framework_usage.service import FrameworkUsageService
from app.consents.db_repository import SqlAlchemyConsentRepository
from app.consents.service import ConsentService
from app.privacy.db_repository import SqlAlchemyPrivacyRepository
from app.privacy.service import PrivacyService
from app.core.config import settings
from app.services import embeddings
from app.admin.panel_audit import AuditRecorder, SqlAlchemyPanelAuditRepository
from app.admin.panel_service import AdminPanelService
from app.admin.users_db_repository import SqlAlchemyAdminUserRepository
from app.credits.db_repository import SqlAlchemyCreditRepository
from app.credits.service import CreditService


class Container:
    """Owns the AI subsystem singletons and builds orchestrators.

    Stateful stores (memory / retrieval corpus / knowledge graph) are process-level
    singletons so their state persists across requests. Stateless services are
    built once. The context builder is the only per-request piece (it needs the
    request's DB session).
    """

    def __init__(self):
        # --- Repositories / stores (swap these for Redis / Postgres / pgvector) ---
        # Founder memory is DB-backed and REQUEST-SCOPED (see memory(db)); it needs
        # the request's session, so it is NOT built here as a held singleton.
        self._retrieval_repository = InMemoryVectorRetrievalRepository([])
        self._kg_repository = InMemoryKnowledgeGraphRepository([], [])

        # --- Services built over those stores (stateless wrappers) ---
        self._retrieval_service = build_retrieval_service(self._retrieval_repository)
        self._kg_service = build_knowledge_graph_service(self._kg_repository)

        # --- Prompt library + LLM execution (register real providers here) ---
        self._prompt_manager = default_prompt_manager()
        self._execution_service = self._build_execution()

        # --- Phase 6 AI Chat flow (Milestone 2) -- additive, composes the frozen
        # foundation. The orchestrator wiring above is untouched. Conversations are
        # DB-backed and REQUEST-SCOPED (see conversation_service(db)) -- they persist
        # to conversations/messages, so they must never be held as a process-level
        # singleton (that would pin one DB session for the process lifetime, and is
        # exactly the bug this replaced: an in-memory store that lost every founder's
        # chat history on restart / could not be shared across worker processes).
        self._grounded_prompt_manager = default_grounded_prompt_manager()
        # The context-window builder reads founder memory, so it too is built
        # PER-REQUEST (see context_window_builder(db)) -- never a held singleton
        # that would pin the old in-memory store after the DB swap.

        # --- Phase 6 attachments + links (Milestone 4) -- additive, metadata only.
        # Attachments are DB-backed and REQUEST-SCOPED (see attachment_service(db)) --
        # same reasoning as conversations: a process-level singleton would lose every
        # attachment's metadata on restart. The link extractor is pure/stateless.
        self._link_extractor = LinkExtractor()

        # --- Phase 6 AI suggestions (Milestone 5) -- additive, deterministic,
        # rule-based; composes chat artifacts, never executes actions or calls an LLM.
        # DB-backed and REQUEST-SCOPED (see suggestion_service(db)) -- same reasoning
        # as conversations/attachments: a process-level singleton would lose every
        # suggestion and every founder's feedback on restart.

        # --- Phase 12 admin & operations (independent) -- process-level in-memory
        # repositories (a production adapter reads the DB + ai_chat stores). The admin
        # registry (email -> role allowlist) is loaded from the environment.
        self._admin_repository = InMemoryAdminRepository()
        self._announcement_repository = InMemoryAnnouncementRepository()
        self._audit_repository = InMemoryAuditRepository()
        self._admin_registry = AdminRegistry()
        # Admin Panel allowlist -- built lazily so tests can set the env var first.
        self._panel_registry = None

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

    def memory(self, db: Session):
        """Request-scoped, DB-backed founder memory -- persists to founder_memory /
        founder_memory_events. Resilient: a DB failure degrades + logs (see
        build_db_memory_service) rather than failing the founder's conversation."""
        return build_db_memory_service(db)

    def retrieval(self, db: Session | None = None):
        """SQL-backed (pgvector, rag_chunks) when retrieval is configured and a
        request DB session is available; otherwise the empty in-memory fallback,
        same fail-open convention as reasoning/deps.py's _build_enricher -- a
        misconfigured or disabled deployment gets no retrieved knowledge, not a
        crash. Request-scoped (not held in __init__) because it needs the
        request's own DB session, same reasoning as memory/conversation/
        attachments/suggestions above."""
        if db is None or not settings.RETRIEVAL_ENABLED or not settings.EMBEDDING_PROVIDER:
            return self._retrieval_service
        provider = embeddings.get_provider(settings.EMBEDDING_PROVIDER)
        repository = SqlVectorRetrievalRepository(
            db, provider, expected_dimension=settings.EMBEDDING_DIMENSION
        )
        return build_retrieval_service(
            repository,
            default_top_k=settings.RETRIEVAL_TOP_K,
            default_min_similarity=Decimal(str(settings.RETRIEVAL_MIN_SIMILARITY)),
        )

    def knowledge_graph(self, db: Session | None = None):
        """SQL-backed (root_cause<->problem via root_causes.problem_id,
        root_cause<->intervention via interventions.root_cause_ids/
        secondary_root_cause_ids -- real FK-shaped data, no new schema) when a
        request DB session is available; otherwise the empty in-memory
        fallback, same convention as retrieval(db)/memory(db). Partial
        coverage: blind_spot and recommendation edges have no backing data
        anywhere in the pipeline yet (see sql_repository.py's own note) and
        stay empty either way. Request-scoped, not held in __init__, for the
        same reason retrieval/memory aren't: it needs the request's own DB
        session."""
        if db is None:
            return self._kg_service
        from app.api.v1.ally.kg.sql_repository import SqlKnowledgeGraphRepository
        return build_knowledge_graph_service(SqlKnowledgeGraphRepository(db))

    def prompt_manager(self):
        return self._prompt_manager

    def execution(self):
        return self._execution_service

    def context_builder(self, db: Session):
        return AllyContextBuilder(AllyContextRepository(db))

    # --- Phase 6 chat flow accessors --------------------------------------

    def conversation_service(self, db: Session):
        """Request-scoped, DB-backed conversation store -- persists to
        conversations / messages. Fails loud on error (no resilient-degrade
        wrapper): this repository IS the founder's message storage, so a silent
        degrade would mean 'your message was sent' while it was actually lost."""
        return build_conversation_service(SqlConversationRepository(db))

    def context_window_builder(self, db: Session):
        """Request-scoped: the builder reads founder memory, uploaded attachments,
        the founder's active plan/tasks, and the DB-backed conversation store, so
        it is assembled entirely from the request's session."""
        return ContextWindowBuilder(
            conversation_service=self.conversation_service(db),
            memory=self.memory(db),
            retrieval=self.retrieval(db),
            knowledge_graph=self.knowledge_graph(db),
            attachments=self.attachment_service(db),
            planning=self.planning_service(db),
            founder_profile=lambda founder_id: self._founder_profile_text(db, founder_id),
        )

    @staticmethod
    def _founder_profile_text(db: Session, founder_id: int) -> str:
        """What onboarding established about this founder, for the chat prompt.

        Reuses the diagnosis advisor's brief so the two surfaces cannot describe
        the same founder differently -- one renderer, one truth. Chat asks for
        the profile half only: the Founder DNA and Current Problem excerpts are
        sized for choosing the next diagnostic question, and chat already
        receives the finished diagnosis separately.
        """
        from app.api.v1.diagnosis.founder_brief import build_founder_brief
        from app.models import Founder

        founder = db.get(Founder, founder_id)
        if founder is None:
            return ""
        return build_founder_brief(db, founder, include_dna=False, include_problem=False)

    def grounded_prompt_manager(self):
        return self._grounded_prompt_manager

    def chat_execution(self, db: Session) -> ChatExecutionService:
        """Assemble a request-scoped ChatExecutionService: the per-request context
        builder, DB-backed conversation store, context-window builder, grounded
        prompt manager and execution service. suggestion_service is wired here too
        so send_message can generate suggestions right after a turn, while its
        context_window/ai_response are actually available -- see
        ChatExecutionService.send_message step 8."""
        return ChatExecutionService(
            context_builder=self.context_builder(db),
            conversation_service=self.conversation_service(db),
            context_window_builder=self.context_window_builder(db),
            prompt_manager=self._grounded_prompt_manager,
            execution=self._execution_service,
            suggestion_service=self.suggestion_service(db),
            call_logger=lambda ai, **kw: record_chat_llm_call(
                ai,
                founder_uuid=db.info.get("current_founder_uuid"),
                **kw,
            ),
            memory=self.memory(db),
        )

    def streaming_chat(self, db: Session) -> StreamingChatService:
        """Assemble a request-scoped StreamingChatService that wraps the chat flow.
        Additive: it composes the existing ChatExecutionService and the same
        request's DB-backed conversation store; no existing service is changed."""
        return StreamingChatService(
            chat_service=self.chat_execution(db),
            conversation_service=self.conversation_service(db),
        )

    # --- Phase 6 attachments + links accessors ----------------------------

    def attachment_service(self, db: Session) -> AttachmentService:
        """Request-scoped, DB-backed attachment store -- persists to file_uploads.
        Fails loud on error, same reasoning as conversation_service: this
        repository IS the attachment storage.

        The object store is resolved once per process (see _object_storage):
        building a boto3 client per request is pure latency, and it is
        stateless and thread-safe. None means no bucket configured, in which
        case file bytes stay inline in Postgres."""
        return AttachmentService(SqlAttachmentRepository(db, self._object_storage()))

    def _object_storage(self):
        # Cached on the container so the client (and its connection pool) is
        # shared, matching how the LLM/embedding providers are held.
        if not hasattr(self, "_object_storage_cached"):
            from app.ai_chat.attachments.storage import build_object_storage
            self._object_storage_cached = build_object_storage()
        return self._object_storage_cached

    def link_extractor(self) -> LinkExtractor:
        return self._link_extractor

    def suggestion_service(self, db: Session) -> SuggestionService:
        """Request-scoped, DB-backed suggestion store -- persists to suggestions /
        suggestion_feedback. Fails loud on error, same reasoning as the other
        chat repositories: this IS the suggestion/feedback storage."""
        return SuggestionService(SqlSuggestionRepository(db))

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

    # --- Planning accessor (DB-backed, per-request) -----------------------

    def planning_service(self, db: Session) -> PlanningService:
        """Request-scoped PlanningService over the SQLAlchemy repository. Tests
        override the endpoint dependency with an in-memory-backed service."""
        return PlanningService(SqlAlchemyPlanningRepository(db))

    # --- Founder Goals accessor (DB-backed, per-request) -------------------

    def founder_goal_service(self, db: Session) -> FounderGoalService:
        """Request-scoped FounderGoalService over the SQLAlchemy repository.
        Tests override the endpoint dependency with an in-memory-backed
        service. Deliberately separate from planning_service() above -- see
        app/founder_goals/models.py for why the two "Goal" concepts don't
        share a repository."""
        return FounderGoalService(SqlAlchemyFounderGoalRepository(db))

    # --- Achievements accessor (DB-backed, per-request) --------------------

    def achievement_service(self, db: Session) -> AchievementService:
        """Request-scoped AchievementService over the SQLAlchemy repository.
        Tests override the endpoint dependency with an in-memory-backed
        service."""
        return AchievementService(SqlAlchemyAchievementRepository(db))

    # --- Vision accessor (DB-backed, per-request) ---------------------------

    def vision_service(self, db: Session) -> VisionService:
        """Request-scoped VisionService over the SQLAlchemy repository. Tests
        override the endpoint dependency with an in-memory-backed service."""
        return VisionService(SqlAlchemyVisionRepository(db))

    # --- Framework Usage accessor (DB-backed, per-request) ------------------

    def framework_usage_service(self, db: Session) -> FrameworkUsageService:
        """Request-scoped FrameworkUsageService over the SQLAlchemy
        repository. Tests override the endpoint dependency with an
        in-memory-backed service."""
        return FrameworkUsageService(SqlAlchemyFrameworkUsageRepository(db))

    # --- Consents accessor (DB-backed, per-request) -----------------------

    def consent_service(self, db: Session) -> ConsentService:
        """Request-scoped ConsentService over the SQLAlchemy repository. Tests
        override the endpoint dependency with an in-memory-backed service."""
        return ConsentService(SqlAlchemyConsentRepository(db))

    # --- Privacy Center accessor (DB-backed, per-request) ------------------

    def privacy_service(self, db: Session) -> PrivacyService:
        """Request-scoped PrivacyService. Composed with the consent service so a
        withdrawal is written to the consent ledger as well as the privacy log."""
        return PrivacyService(
            SqlAlchemyPrivacyRepository(db),
            consent_service=self.consent_service(db),
        )

    # --- Admin Panel (DB-backed, per-request) -----------------------------

    def panel_registry(self):
        """email -> PanelRole allowlist. Built once; empty unless granted via env."""
        if self._panel_registry is None:
            from app.api.v1.admin.panel_dependencies import PanelRegistry
            self._panel_registry = PanelRegistry()
        return self._panel_registry

    def credit_service(self, db: Session) -> CreditService:
        return CreditService(SqlAlchemyCreditRepository(db))

    def admin_panel_service(self, db: Session) -> AdminPanelService:
        """Request-scoped panel service. The audit repository is DB-backed so the
        trail survives restarts."""
        from app.admin.conversations import SqlAlchemyConversationReadRepository
        from app.admin.feedback import SqlAlchemyFeedbackReadRepository
        from app.api.v1.reasoning.trigger import regenerate_report_for_founder
        from app.privacy.db_repository import SqlAlchemyPrivacyRepository
        return AdminPanelService(
            SqlAlchemyAdminUserRepository(db),
            credits=self.credit_service(db),
            audit=AuditRecorder(SqlAlchemyPanelAuditRepository(db)),
            conversations=SqlAlchemyConversationReadRepository(db),
            # Finds the founder's most recent completed session and re-runs
            # the reasoning pipeline with force=True. This is the recovery
            # path for a founder whose session completed but the best-effort
            # inline reasoning run that should have produced a report never
            # did (LLM hiccup, transient error) -- previously there was no
            # way, self-service or admin, to get them a report at all.
            report_regenerator=lambda founder_id: regenerate_report_for_founder(db, founder_id),
            privacy=SqlAlchemyPrivacyRepository(db),
            feedback=SqlAlchemyFeedbackReadRepository(db),
        )

    def insights_service(self, db: Session):
        from app.admin.insights import InsightsService, SqlAlchemyInsightsRepository
        return InsightsService(SqlAlchemyInsightsRepository(db))

    def feature_flag_service(self, db: Session):
        from app.admin.feature_flags import (
            FeatureFlagService,
            SqlAlchemyFeatureFlagRepository,
        )
        return FeatureFlagService(SqlAlchemyFeatureFlagRepository(db))

    def entitlement_service(self, db: Session):
        """Plan gate for one request. Composed with the credit service so the
        chat guard can check features, the daily ceiling and the balance in one
        place."""
        from app.plans.service import EntitlementService
        from app.plans.usage import SqlAlchemyUsageRepository
        return EntitlementService(SqlAlchemyUsageRepository(db),
                                  credit_service=self.credit_service(db))

    def broadcast_service(self, db: Session):
        from app.admin.broadcasts import BroadcastService, SqlAlchemyBroadcastRepository
        return BroadcastService(SqlAlchemyBroadcastRepository(db))


# Application-wide container instance. Import and use `container.chat_execution(db)`.
container = Container()
