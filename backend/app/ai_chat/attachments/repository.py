"""Attachment persistence seam. In-memory + thread-safe; DB swap = replacement only."""

from __future__ import annotations

import abc
import threading

from app.ai_chat.attachments.schemas import Attachment, AttachmentStatus


class AttachmentRepository(abc.ABC):
    @abc.abstractmethod
    def add(self, attachment: Attachment) -> None: ...

    @abc.abstractmethod
    def get(self, attachment_id: str) -> Attachment | None: ...

    @abc.abstractmethod
    def replace(self, attachment: Attachment) -> None: ...

    @abc.abstractmethod
    def list_for_conversation(
        self, conversation_id: str, *, statuses: tuple[AttachmentStatus, ...]
    ) -> tuple[Attachment, ...]: ...

    @abc.abstractmethod
    def purge(self, attachment_id: str) -> bool: ...

    @abc.abstractmethod
    def add_content(self, attachment_id: str, content: bytes) -> None: ...

    @abc.abstractmethod
    def get_content(self, attachment_id: str) -> bytes | None: ...


class InMemoryAttachmentRepository(AttachmentRepository):
    def __init__(self) -> None:
        self._items: dict[str, Attachment] = {}
        self._content: dict[str, bytes] = {}
        self._lock = threading.RLock()

    def add(self, attachment: Attachment) -> None:
        with self._lock:
            self._items[attachment.attachment_id] = attachment

    def get(self, attachment_id: str) -> Attachment | None:
        with self._lock:
            return self._items.get(attachment_id)

    def replace(self, attachment: Attachment) -> None:
        with self._lock:
            self._items[attachment.attachment_id] = attachment

    def list_for_conversation(self, conversation_id, *, statuses):
        with self._lock:
            found = [a for a in self._items.values()
                     if a.conversation_id == conversation_id and a.status in statuses]
        # Deterministic: creation order, then id as a stable tiebreak.
        found.sort(key=lambda a: (a.created_at, a.attachment_id))
        return tuple(found)

    def purge(self, attachment_id: str) -> bool:
        with self._lock:
            self._content.pop(attachment_id, None)
            return self._items.pop(attachment_id, None) is not None

    def add_content(self, attachment_id: str, content: bytes) -> None:
        with self._lock:
            self._content[attachment_id] = content

    def get_content(self, attachment_id: str) -> bytes | None:
        with self._lock:
            return self._content.get(attachment_id)
