"""FastAPI dependencies for the Chat API (Phase 6, Milestone 6, Part 6).

Transport-only wiring: every dependency pulls an already-composed service from the
container (no manual construction, no duplicated services). Tests override these via
`app.dependency_overrides` to inject offline-wired doubles.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.ai_chat.attachments.service import AttachmentService
from app.ai_chat.execution.chat_execution import ChatExecutionService
from app.ai_chat.links.extractor import LinkExtractor
from app.ai_chat.services.conversation import ConversationService
from app.ai_chat.streaming.service import StreamingChatService
from app.ai_chat.suggestions.service import SuggestionService
from app.api.v1.plans.dependencies import get_current_founder_id
from app.core.container import container
from app.db.session import get_db

# get_current_founder_id re-exported from plans.dependencies (not redefined here)
# so both modules share the exact same function object -- FastAPI's
# dependency_overrides key by identity, and chat_gate (plans.dependencies) also
# depends on it. Defining it separately in each module breaks existing test
# overrides of THIS name silently (the override would apply to one copy but
# chat_gate would still resolve the real founder via the other).
# plans.dependencies is the canonical owner because the reverse direction --
# plans importing from chat -- is what created the circular import in the first
# place: chat.router imports ChatGate/chat_gate from plans.dependencies.


def get_conversation_service(db: Session = Depends(get_db)) -> ConversationService:
    return container.conversation_service(db)


def get_attachment_service(db: Session = Depends(get_db)) -> AttachmentService:
    return container.attachment_service(db)


def get_link_extractor() -> LinkExtractor:
    return container.link_extractor()


def get_suggestion_service(db: Session = Depends(get_db)) -> SuggestionService:
    return container.suggestion_service(db)


def get_chat_service(db: Session = Depends(get_db)) -> ChatExecutionService:
    return container.chat_execution(db)


def get_streaming_service(db: Session = Depends(get_db)) -> StreamingChatService:
    return container.streaming_chat(db)
