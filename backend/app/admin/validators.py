"""Fail-closed validation for admin inputs (search, announcements)."""

from __future__ import annotations

from app.admin.errors import InvalidAnnouncementError, InvalidSearchError

_MAX_QUERY = 100
_MAX_TITLE = 200
_MAX_BODY = 5000


def validate_search_query(query: str) -> str:
    q = (query or "").strip()
    if not q:
        raise InvalidSearchError("query must not be empty")
    if len(q) > _MAX_QUERY:
        raise InvalidSearchError(f"query must be at most {_MAX_QUERY} characters")
    return q


def validate_announcement(title: str, body: str) -> None:
    if not title or not title.strip():
        raise InvalidAnnouncementError("title must not be empty")
    if len(title) > _MAX_TITLE:
        raise InvalidAnnouncementError(f"title must be at most {_MAX_TITLE} characters")
    if not body or not body.strip():
        raise InvalidAnnouncementError("body must not be empty")
    if len(body) > _MAX_BODY:
        raise InvalidAnnouncementError(f"body must be at most {_MAX_BODY} characters")
