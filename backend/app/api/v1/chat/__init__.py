"""Chat HTTP API (Phase 6, Milestone 6) -- transport only.

REST + Server-Sent Events over the complete AI Chat system (conversations, chat,
streaming, attachments, links, suggestions). Every endpoint delegates to an existing
service from the container; no business logic lives in this layer.
"""

from app.api.v1.chat.router import router

__all__ = ["router"]
