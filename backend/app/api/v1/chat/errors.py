"""Ownership guards for the Chat API (Phase 6, Milestone 6, Part 7).

Each guard loads a resource through its service (which raises the typed NotFound on
a missing id) and enforces founder ownership -- a foreign resource is reported as
NotFound, never disclosed. All raised errors are AppError subclasses, so the global
error handler maps them to consistent JSON (404/409/413/415/422/500).
"""

from __future__ import annotations

from app.ai_chat.attachments.errors import AttachmentNotFoundError
from app.ai_chat.errors import ConversationNotFoundError
from app.ai_chat.suggestions.errors import SuggestionNotFoundError


def owned_conversation(service, conversation_id: str, founder_id: int):
    conversation = service.get_conversation(conversation_id)
    if conversation.founder_id != founder_id:
        raise ConversationNotFoundError(conversation_id)
    return conversation


def owned_attachment(service, attachment_id: str, founder_id: int):
    attachment = service.get_attachment(attachment_id)
    if attachment.founder_id != founder_id:
        raise AttachmentNotFoundError(attachment_id)
    return attachment


def owned_suggestion(service, suggestion_id: str, founder_id: int):
    suggestion = service.get_suggestion(suggestion_id)
    if suggestion.founder_id != founder_id:
        raise SuggestionNotFoundError(suggestion_id)
    return suggestion
