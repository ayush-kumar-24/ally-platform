"""Ally AI Chat (Phase 6) -- a production conversational layer over the frozen
Phase 5 AI Foundation.

Milestone 1 (this package's current scope): the Conversation Engine -- conversation
entities, a repository-driven ConversationService (create / append / history /
rename / archive / delete / restore / summarize), deterministic context-window
truncation, and unread/token metadata. It composes NOTHING from Phase 5 and does no
LLM work; later milestones add the chat flow (memory + retrieval + graph + grounded
prompt + execution), streaming, attachments, links and suggestions.

Reserved for later milestones (not yet implemented): streaming/, attachments/,
links/, suggestions/, api/.
"""

from app.ai_chat.builders.context_window import ContextWindowBuilder, ContextWindowConfig
from app.ai_chat.errors import (
    ChatError,
    ConversationNotFoundError,
    InvalidConversationStateError,
    InvalidMessageError,
)
from app.ai_chat.execution.chat_execution import (
    ChatExecutionService,
    build_chat_execution_service,
)
from app.ai_chat.repositories.conversation import (
    ConversationRepository,
    InMemoryConversationRepository,
)
from app.ai_chat.schemas.chat import (
    ChatMetrics,
    ChatRequest,
    ChatResponse,
    ConversationContextWindow,
    ConversationExecutionTrace,
    GroundingRequest,
)
from app.ai_chat.schemas.conversation import (
    Conversation,
    ConversationContext,
    ConversationMessage,
    ConversationStatus,
    ConversationSummary,
    MessageRole,
    MessageTokenUsage,
    TokenStats,
)
from app.ai_chat.services.conversation import (
    ConversationService,
    build_conversation_service,
)

__all__ = [
    # M1 conversation schemas
    "Conversation",
    "ConversationMessage",
    "ConversationSummary",
    "ConversationContext",
    "ConversationStatus",
    "MessageRole",
    "TokenStats",
    "MessageTokenUsage",
    # M2 chat-flow schemas
    "ChatRequest",
    "ChatResponse",
    "ConversationContextWindow",
    "ConversationExecutionTrace",
    "ChatMetrics",
    "GroundingRequest",
    # repository
    "ConversationRepository",
    "InMemoryConversationRepository",
    # services / builders
    "ConversationService",
    "build_conversation_service",
    "ContextWindowBuilder",
    "ContextWindowConfig",
    "ChatExecutionService",
    "build_chat_execution_service",
    # errors
    "ChatError",
    "ConversationNotFoundError",
    "InvalidConversationStateError",
    "InvalidMessageError",
]
