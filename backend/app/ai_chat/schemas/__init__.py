"""ai_chat domain schemas."""

from app.ai_chat.schemas.chat import (
    ChatMetrics,
    ChatRequest,
    ChatResponse,
    ConversationContextWindow,
    ConversationExecutionTrace,
    GroundingRequest,
)
from app.ai_chat.schemas.conversation import (
    DEFAULT_TITLE,
    Conversation,
    ConversationContext,
    ConversationMessage,
    ConversationStatus,
    ConversationSummary,
    MessageRole,
    MessageTokenUsage,
    TokenStats,
)

__all__ = [
    # M1 conversation entities
    "Conversation",
    "ConversationMessage",
    "ConversationSummary",
    "ConversationContext",
    "ConversationStatus",
    "MessageRole",
    "TokenStats",
    "MessageTokenUsage",
    "DEFAULT_TITLE",
    # M2 chat-flow schemas
    "ChatRequest",
    "ChatResponse",
    "ConversationContextWindow",
    "ConversationExecutionTrace",
    "ChatMetrics",
    "GroundingRequest",
]
