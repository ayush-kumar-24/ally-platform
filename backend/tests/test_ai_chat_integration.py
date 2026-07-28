"""Integration tests for the Conversation Engine (Phase 6, Milestone 1).

Exercise whole conversation journeys over the real ConversationService +
InMemoryConversationRepository: multi-turn flow, founder isolation, concurrent
chats, full lifecycle (create -> chat -> summarize -> archive -> restore ->
delete), context trimming across a long conversation, and end-to-end determinism.
"""

from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from itertools import count

from app.ai_chat import (
    ConversationStatus,
    InMemoryConversationRepository,
    MessageRole,
    MessageTokenUsage,
    build_conversation_service,
)
from app.ai_chat.services.conversation import ConversationService

T0 = datetime(2026, 7, 28, 10, 0, 0, tzinfo=timezone.utc)
U, A = MessageRole.USER, MessageRole.ASSISTANT


class FakeClock:
    def __init__(self, start=T0, step=timedelta(seconds=1)):
        self._now, self._step = start, step

    def now(self):
        v = self._now
        self._now += self._step
        return v


def _ids():
    c = count(1)
    return lambda: f"id-{next(c)}"


def det_service():
    """Deterministic service (fake clock + counter ids)."""
    return build_conversation_service(clock=FakeClock(), id_factory=_ids())


# --- multi-turn -------------------------------------------------------------


def test_multi_turn_conversation_flow():
    s = det_service()
    c = s.create_conversation(1)
    turns = [
        (U, "How do I improve activation?"),
        (A, "Focus on guided onboarding."),
        (U, "What metric should I watch?"),
        (A, "Day-1 activation rate."),
    ]
    for role, text in turns:
        usage = MessageTokenUsage(5, 3) if role == A else None
        s.append_message(c.conversation_id, role, text, token_usage=usage)

    conv = s.get_conversation(c.conversation_id)
    assert conv.message_count == 4
    assert conv.unread_count == 2                             # two Ally replies unread
    assert conv.token_stats.total_tokens == 16               # 2 * (5+3)
    assert conv.title == "How do I improve activation?"       # auto-titled from turn 1
    assert [m.content for m in s.get_history(c.conversation_id)] == [t[1] for t in turns]


def test_two_conversations_keep_independent_histories():
    s = det_service()
    a = s.create_conversation(1, title="A")
    b = s.create_conversation(1, title="B")
    s.append_message(a.conversation_id, U, "alpha")
    s.append_message(b.conversation_id, U, "beta")
    assert [m.content for m in s.get_history(a.conversation_id)] == ["alpha"]
    assert [m.content for m in s.get_history(b.conversation_id)] == ["beta"]


def test_reading_a_conversation_marks_it_read():
    s = det_service()
    c = s.create_conversation(1)
    s.append_message(c.conversation_id, A, "welcome")
    assert s.get_conversation(c.conversation_id).unread_count == 1
    s.mark_read(c.conversation_id)
    assert s.get_conversation(c.conversation_id).unread_count == 0


# --- full lifecycle ---------------------------------------------------------


def test_full_lifecycle_create_chat_summarize_archive_restore_delete():
    s = det_service()
    c = s.create_conversation(1)
    cid = c.conversation_id
    s.append_message(cid, U, "let's talk strategy")
    s.append_message(cid, A, "happy to help")

    summ = s.summarize_conversation(cid)
    assert summ.message_count == 2

    s.archive_conversation(cid)
    assert s.list_conversations(1) == ()                     # hidden when archived

    s.restore_conversation(cid)
    assert s.get_conversation(cid).is_active
    s.append_message(cid, U, "back again")                   # append works after restore
    assert s.get_conversation(cid).message_count == 3

    s.delete_conversation(cid)
    assert s.get_conversation(cid).status == ConversationStatus.DELETED
    s.restore_conversation(cid)
    assert s.get_conversation(cid).is_active                 # recoverable


def test_archived_chats_listing_variants():
    s = det_service()
    active = s.create_conversation(1, title="active")
    archived = s.create_conversation(1, title="archived")
    deleted = s.create_conversation(1, title="deleted")
    s.archive_conversation(archived.conversation_id)
    s.delete_conversation(deleted.conversation_id)

    assert {c.title for c in s.list_conversations(1)} == {"active"}
    assert {c.title for c in s.list_conversations(1, include_archived=True)} == {"active", "archived"}
    assert {c.title for c in s.list_conversations(1, include_archived=True, include_deleted=True)} == {
        "active", "archived", "deleted"}


# --- context trimming across a long conversation ----------------------------


def test_context_trimming_across_long_conversation():
    s = det_service()
    c = s.create_conversation(1)
    cid = c.conversation_id
    s.append_message(cid, U, "the founding thesis", important=True)   # seq 0, pinned
    for i in range(1, 30):
        s.append_message(cid, U if i % 2 else A, f"turn {i}")
    s.summarize_conversation(cid)

    ctx = s.build_context(cid, max_messages=5)
    seqs = [m.sequence for m in ctx.recent_messages]
    assert ctx.total_messages == 30 and ctx.truncated
    assert seqs == [0, 25, 26, 27, 28, 29]                   # pinned thesis + last 5
    assert ctx.summary is not None


# --- concurrency (concurrent chats = independent conversations) -------------


def test_concurrent_distinct_conversations_are_consistent():
    # Real "concurrent chats": many independent conversations progressing in
    # parallel. Uses uuid ids (thread-safe) over the locked in-memory repo.
    svc = build_conversation_service(clock=FakeClock())        # default uuid id_factory

    def journey(i):
        c = svc.create_conversation(founder_id=i)
        for k in range(5):
            svc.append_message(c.conversation_id, U if k % 2 == 0 else A, f"msg {k}")
        return svc.get_conversation(c.conversation_id).message_count

    with ThreadPoolExecutor(max_workers=8) as pool:
        counts = list(pool.map(journey, range(1, 25)))

    assert counts == [5] * 24
    # 24 founders, one conversation each, all intact.
    assert all(len(svc.list_conversations(i)) == 1 for i in range(1, 25))


def test_concurrent_chats_across_founders_stay_isolated():
    svc = build_conversation_service(clock=FakeClock())

    def chat(founder):
        c = svc.create_conversation(founder)
        svc.append_message(c.conversation_id, U, f"hello from {founder}")
        return founder

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(chat, range(1, 17)))

    for founder in range(1, 17):
        history = svc.get_history(svc.list_conversations(founder)[0].conversation_id)
        assert [m.content for m in history] == [f"hello from {founder}"]


# --- determinism ------------------------------------------------------------


def _script(s):
    c = s.create_conversation(7, title=None)
    cid = c.conversation_id
    s.append_message(cid, U, "How do I reduce churn?")
    s.append_message(cid, A, "Interview churned users.", token_usage=MessageTokenUsage(9, 4))
    s.append_message(cid, U, "Any framework?")
    s.append_message(cid, A, "Start with the JTBD interview.", token_usage=MessageTokenUsage(6, 5))
    s.summarize_conversation(cid)
    return s.get_conversation(cid), s.get_history(cid), s.repository.get_summary(cid)


def test_deterministic_execution_end_to_end():
    conv_a, hist_a, sum_a = _script(det_service())
    conv_b, hist_b, sum_b = _script(det_service())
    assert conv_a == conv_b                                   # identical ids, timestamps, stats, title
    assert hist_a == hist_b
    assert sum_a == sum_b


def test_repository_swap_only_contract():
    # The service depends solely on the repository interface; a hand-built repo +
    # explicit ConversationService construct the same way build_* does.
    s = ConversationService(InMemoryConversationRepository(), clock=FakeClock(), id_factory=_ids())
    c = s.create_conversation(1)
    s.append_message(c.conversation_id, U, "works")
    assert s.get_history(c.conversation_id)[0].content == "works"
