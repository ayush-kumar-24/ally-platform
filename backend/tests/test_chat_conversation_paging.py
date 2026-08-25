"""Paging, rename, delete and read-marking on the chat conversation endpoints.

These cover behaviour that did not exist before: the list endpoints were
unbounded, and rename / delete / mark-read lived in the service with no route.

The sequence assertions matter more than they look. `sequence` is
position-in-conversation and is derived from position in the result set, so a
paged read that renumbered from zero would hand back message 400 labelled as
message 0 -- and attachments and idempotent-retry matching both key off it.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.ai_chat.repositories.conversation import InMemoryConversationRepository
from app.ai_chat.schemas.conversation import ConversationMessage, MessageRole
from app.ai_chat.services.conversation import ConversationService

FOUNDER = 4242
T0 = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)


def _service() -> ConversationService:
    return ConversationService(repository=InMemoryConversationRepository())


def _seed_messages(service: ConversationService, conversation_id: str, count: int) -> None:
    """Straight into the repository: the service's append_message also touches
    counters and unread state, and this fixture is about ordering alone."""
    for i in range(count):
        service.repository.add_message(ConversationMessage(
            message_id=f"m{i:03d}", conversation_id=conversation_id, founder_id=FOUNDER,
            role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
            content=f"message {i:03d}", sequence=i, created_at=T0 + timedelta(minutes=i)))


# --- message paging ---------------------------------------------------------


def test_history_unpaged_returns_everything():
    """The default has to stay unbounded: summarise and export both call this."""
    s = _service()
    conv = s.create_conversation(FOUNDER).conversation_id
    _seed_messages(s, conv, 25)
    assert len(s.get_history(conv)) == 25


def test_history_limit_returns_the_newest_page():
    s = _service()
    conv = s.create_conversation(FOUNDER).conversation_id
    _seed_messages(s, conv, 25)

    page = s.get_history(conv, limit=10)
    assert len(page) == 10
    # The LAST ten, not the first -- a transcript is read from the bottom.
    assert page[0].content == "message 015"
    assert page[-1].content == "message 024"


def test_history_page_keeps_absolute_sequence():
    s = _service()
    conv = s.create_conversation(FOUNDER).conversation_id
    _seed_messages(s, conv, 25)

    page = s.get_history(conv, limit=10)
    assert [m.sequence for m in page] == list(range(15, 25))


def test_history_explicit_offset_walks_backwards():
    s = _service()
    conv = s.create_conversation(FOUNDER).conversation_id
    _seed_messages(s, conv, 25)

    page = s.get_history(conv, limit=10, offset=5)
    assert page[0].content == "message 005"
    assert [m.sequence for m in page] == list(range(5, 15))


def test_history_pages_tile_the_whole_transcript():
    """Every message appears exactly once across consecutive pages -- no gap at
    a boundary, no message served twice."""
    s = _service()
    conv = s.create_conversation(FOUNDER).conversation_id
    _seed_messages(s, conv, 25)

    seen = []
    for offset in (0, 10, 20):
        seen.extend(m.content for m in s.get_history(conv, limit=10, offset=offset))
    assert seen == [f"message {i:03d}" for i in range(25)]


def test_history_limit_larger_than_transcript():
    s = _service()
    conv = s.create_conversation(FOUNDER).conversation_id
    _seed_messages(s, conv, 3)

    page = s.get_history(conv, limit=50)
    assert [m.sequence for m in page] == [0, 1, 2]


def test_count_history():
    s = _service()
    conv = s.create_conversation(FOUNDER).conversation_id
    _seed_messages(s, conv, 7)
    assert s.count_history(conv) == 7


# --- conversation paging ----------------------------------------------------


def test_conversation_paging_does_not_overlap_or_skip():
    s = _service()
    for i in range(12):
        s.create_conversation(FOUNDER, title=f"conversation {i:02d}")

    first = s.list_conversations(FOUNDER, limit=5, offset=0)
    second = s.list_conversations(FOUNDER, limit=5, offset=5)
    third = s.list_conversations(FOUNDER, limit=5, offset=10)

    ids = [c.conversation_id for c in (*first, *second, *third)]
    assert len(ids) == 12
    assert len(set(ids)) == 12                       # nothing served twice
    assert set(ids) == {c.conversation_id for c in s.list_conversations(FOUNDER)}


def test_conversation_page_is_a_window_on_the_unpaged_order():
    """Paging must not reorder. If it did, a conversation could sit on two
    pages and never on a third."""
    s = _service()
    for i in range(8):
        s.create_conversation(FOUNDER, title=f"conversation {i:02d}")

    full = [c.conversation_id for c in s.list_conversations(FOUNDER)]
    assert [c.conversation_id for c in s.list_conversations(FOUNDER, limit=3)] == full[:3]
    assert [c.conversation_id for c in s.list_conversations(FOUNDER, limit=3, offset=3)] == full[3:6]


def test_count_conversations_ignores_paging():
    s = _service()
    for i in range(9):
        s.create_conversation(FOUNDER)
    assert s.count_conversations(FOUNDER) == 9
    assert len(s.list_conversations(FOUNDER, limit=4)) == 4


def test_count_conversations_excludes_archived_by_default():
    s = _service()
    keep = s.create_conversation(FOUNDER).conversation_id
    gone = s.create_conversation(FOUNDER).conversation_id
    s.archive_conversation(gone)

    assert s.count_conversations(FOUNDER) == 1
    assert s.count_conversations(FOUNDER, include_archived=True) == 2
    assert [c.conversation_id for c in s.list_conversations(FOUNDER)] == [keep]


# --- lifecycle --------------------------------------------------------------


def test_rename_changes_the_title():
    s = _service()
    conv = s.create_conversation(FOUNDER, title="our churn is 9% monthly and I don't know").conversation_id
    renamed = s.rename_conversation(conv, "Churn investigation")
    assert renamed.title == "Churn investigation"
    assert s.get_conversation(conv).title == "Churn investigation"


def test_deleted_conversation_leaves_the_default_list():
    s = _service()
    conv = s.create_conversation(FOUNDER).conversation_id
    s.delete_conversation(conv)

    assert [c.conversation_id for c in s.list_conversations(FOUNDER)] == []
    # Deleted is distinct from archived: "show me my archived ones" must not
    # resurrect something the founder deleted.
    assert [c.conversation_id for c in s.list_conversations(FOUNDER, include_archived=True)] == []
    assert [c.conversation_id
            for c in s.list_conversations(FOUNDER, include_deleted=True)] == [conv]


def test_mark_read_clears_an_unread_reply():
    """The reason mark_read needed a route at all: unread_count is incremented
    by every assistant message and, with nothing calling this, only ever went
    up -- for every founder, forever."""
    s = _service()
    conv = s.create_conversation(FOUNDER).conversation_id
    s.append_message(conv, MessageRole.USER, "why are we churning?")
    s.append_message(conv, MessageRole.ASSISTANT, "month two onboarding.")
    assert s.get_conversation(conv).unread_count == 1

    assert s.mark_read(conv).unread_count == 0
    assert s.get_conversation(conv).unread_count == 0


def test_mark_read_is_idempotent():
    s = _service()
    conv = s.create_conversation(FOUNDER).conversation_id
    s.append_message(conv, MessageRole.ASSISTANT, "hello")
    s.mark_read(conv)
    assert s.mark_read(conv).unread_count == 0


@pytest.mark.parametrize("count", [0, 1, 49, 50, 51])
def test_paging_holds_at_the_boundaries(count):
    """Off-by-one around the page size is where this kind of code fails."""
    s = _service()
    conv = s.create_conversation(FOUNDER).conversation_id
    _seed_messages(s, conv, count)

    page = s.get_history(conv, limit=50)
    assert len(page) == min(count, 50)
    if count:
        assert page[-1].content == f"message {count - 1:03d}"
        assert page[-1].sequence == count - 1
