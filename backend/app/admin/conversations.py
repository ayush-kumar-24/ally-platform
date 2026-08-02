"""Read-only conversation access for support.

There is no write path in this module -- no edit, no delete, no redact. Support is
allowed to view conversations and nothing else, and the most reliable way to enforce
that is to never build the mutation. A guard can be bypassed by a future caller; a
method that does not exist cannot be.
"""

from __future__ import annotations

import abc
import threading
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import text


@dataclass(frozen=True)
class ConversationMessage:
    message_id: str
    role: str                 # "user" | "assistant" | "system"
    content: str
    created_at: datetime


@dataclass(frozen=True)
class ConversationView:
    conversation_id: str
    founder_id: int
    title: str
    created_at: datetime
    message_count: int
    messages: list[ConversationMessage] = field(default_factory=list)


class ConversationReadRepository(abc.ABC):
    @abc.abstractmethod
    def list_for_founder(self, founder_id: int, *, limit: int = 50,
                         offset: int = 0) -> tuple[list[ConversationView], int]: ...

    @abc.abstractmethod
    def get_with_messages(self, conversation_id: str) -> ConversationView | None: ...


class InMemoryConversationReadRepository(ConversationReadRepository):
    def __init__(self, conversations: list[ConversationView] | None = None):
        self._rows = {c.conversation_id: c for c in (conversations or [])}
        self._lock = threading.RLock()

    def list_for_founder(self, founder_id, *, limit=50, offset=0):
        with self._lock:
            mine = [c for c in self._rows.values() if c.founder_id == founder_id]
        mine.sort(key=lambda c: c.created_at, reverse=True)
        return mine[offset:offset + limit], len(mine)

    def get_with_messages(self, conversation_id):
        with self._lock:
            return self._rows.get(conversation_id)


class SqlAlchemyConversationReadRepository(ConversationReadRepository):
    def __init__(self, db):
        self.db = db

    def _rows(self, sql: str, params: dict) -> list[dict]:
        try:
            return [dict(r) for r in self.db.execute(text(sql), params).mappings().all()]
        except Exception:
            self.db.rollback()
            return []

    def list_for_founder(self, founder_id, *, limit=50, offset=0):
        total_rows = self._rows(
            "select count(*) as n from conversations where founder_id = :fid",
            {"fid": founder_id})
        total = int(total_rows[0]["n"]) if total_rows else 0
        rows = self._rows("""
            select c.conversation_id, c.founder_id, c.title, c.created_at,
                   (select count(*) from messages m
                     where m.conversation_id = c.conversation_id) as message_count
              from conversations c
             where c.founder_id = :fid
             order by c.created_at desc
             limit :lim offset :off""",
            {"fid": founder_id, "lim": limit, "off": offset})
        return [ConversationView(
            conversation_id=str(r["conversation_id"]), founder_id=r["founder_id"],
            title=r.get("title") or "", created_at=r["created_at"],
            message_count=int(r.get("message_count") or 0)) for r in rows], total

    def get_with_messages(self, conversation_id):
        head = self._rows("""select conversation_id, founder_id, title, created_at
                               from conversations where conversation_id = :cid""",
                          {"cid": conversation_id})
        if not head:
            return None
        h = head[0]
        msgs = self._rows("""select message_id, role, content, created_at
                               from messages where conversation_id = :cid
                              order by created_at asc limit 500""",
                          {"cid": conversation_id})
        return ConversationView(
            conversation_id=str(h["conversation_id"]), founder_id=h["founder_id"],
            title=h.get("title") or "", created_at=h["created_at"],
            message_count=len(msgs),
            messages=[ConversationMessage(
                message_id=str(m.get("message_id")), role=str(m.get("role") or ""),
                content=str(m.get("content") or ""), created_at=m["created_at"])
                for m in msgs])
