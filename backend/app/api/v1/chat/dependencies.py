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
from app.api.deps import get_founder_record
from app.core.container import container
from app.db.session import get_db
from app.models import Founder


def get_current_founder_id(founder: Founder = Depends(get_founder_record)) -> int:
    """The authenticated founder's id -- the authoritative identity for every
    chat request. Tests override this dependency directly."""
    return founder.founder_id


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
