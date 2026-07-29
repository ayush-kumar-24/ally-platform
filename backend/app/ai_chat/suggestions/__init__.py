"""Ally AI Chat -- AI Suggestions (Phase 6, Milestone 5).

A deterministic, rule-based suggestion engine that composes existing chat artifacts
(conversation, context window, AI response, attachments, links) into a ranked
SuggestionCollection. It NEVER executes actions, plans, or calls an LLM -- structured
proposals only.
"""

from app.ai_chat.suggestions.engine import SuggestionEngine
from app.ai_chat.suggestions.errors import SuggestionError, SuggestionNotFoundError
from app.ai_chat.suggestions.ranking import RankResult, SuggestionRankingService
from app.ai_chat.suggestions.repository import (
    InMemorySuggestionRepository,
    SuggestionRepository,
)
from app.ai_chat.suggestions.rules import DEFAULT_RULES
from app.ai_chat.suggestions.schemas import (
    Suggestion,
    SuggestionCollection,
    SuggestionContext,
    SuggestionDraft,
    SuggestionFeedback,
    SuggestionFeedbackType,
    SuggestionMetrics,
    SuggestionPriority,
    SuggestionReason,
    SuggestionSource,
    SuggestionStatus,
    SuggestionTrace,
    SuggestionType,
)
from app.ai_chat.suggestions.service import (
    SuggestionService,
    SuggestionServiceConfig,
    build_suggestion_service,
)

__all__ = [
    # models
    "Suggestion",
    "SuggestionType",
    "SuggestionPriority",
    "SuggestionReason",
    "SuggestionSource",
    "SuggestionStatus",
    "SuggestionCollection",
    "SuggestionFeedback",
    "SuggestionFeedbackType",
    "SuggestionMetrics",
    "SuggestionTrace",
    "SuggestionContext",
    "SuggestionDraft",
    # engine / ranking / repo / service
    "SuggestionEngine",
    "SuggestionRankingService",
    "RankResult",
    "SuggestionRepository",
    "InMemorySuggestionRepository",
    "SuggestionService",
    "SuggestionServiceConfig",
    "build_suggestion_service",
    "DEFAULT_RULES",
    # errors
    "SuggestionError",
    "SuggestionNotFoundError",
]
