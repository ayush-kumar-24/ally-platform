"""Unit tests for the Conversation Engine (Phase 6, Milestone 1).

Hermetic and deterministic: injected FakeClock + counter id_factory over the
in-memory repository. No DB, no LLM, no Phase 5 composition.
"""

from datetime import datetime, timedelta, timezone
from itertools import count

import pytest

from app.ai_chat import (
    ConversationNotFoundError,
    ConversationStatus,
    InvalidConversationStateError,
    InvalidMessageError,
    MessageRole,
    MessageTokenUsage,
    TokenStats,
    build_conversation_service,
)
from app.ai_chat.schemas.conversation import DEFAULT_TITLE, Conversation

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


def svc(clock=None):
    return build_conversation_service(clock=clock or FakeClock(), id_factory=_ids())


# --- entities ---------------------------------------------------------------


def test_token_stats_add_accumulates():
    s = TokenStats().add(10, 4).add(3, 2)
    assert (s.prompt_tokens, s.completion_tokens, s.total_tokens) == (13, 6, 19)


def test_message_token_usage_total():
    assert MessageTokenUsage(prompt_tokens=7, completion_tokens=5).total_tokens == 12


def test_conversation_status_helpers():
    c = Conversation("c", 1, "t", ConversationStatus.ARCHIVED, T0, T0)
    assert c.is_archived and not c.is_active and not c.is_deleted


def test_default_title_constant():
    assert DEFAULT_TITLE == "New conversation"


# --- create -----------------------------------------------------------------


def test_create_conversation_defaults():
    c = svc().create_conversation(1)
    assert c.conversation_id == "id-1" and c.founder_id == 1
    assert c.title == DEFAULT_TITLE and c.status == ConversationStatus.ACTIVE
    assert c.created_at == T0 and c.message_count == 0 and c.unread_count == 0


def test_create_with_title():
    assert svc().create_conversation(1, title="  Fundraising  ").title == "Fundraising"


def test_create_blank_title_falls_back():
    assert svc().create_conversation(1, title="   ").title == DEFAULT_TITLE


def test_create_registers_in_repo():
    s = svc()
    c = s.create_conversation(1)
    assert s.list_conversations(1) == (c,)


def test_multiple_conversations_per_founder():
    s = svc()
    s.create_conversation(1)
    s.create_conversation(1)
    assert len(s.list_conversations(1)) == 2


def test_conversations_isolated_by_founder():
    s = svc()
    s.create_conversation(1)
    s.create_conversation(2)
    assert len(s.list_conversations(1)) == 1 and len(s.list_conversations(2)) == 1


# --- append -----------------------------------------------------------------


def test_append_increments_count_and_sequence():
    s = svc()
    c = s.create_conversation(1)
    m0 = s.append_message(c.conversation_id, U, "hi")
    m1 = s.append_message(c.conversation_id, A, "hello")
    assert (m0.sequence, m1.sequence) == (0, 1)
    assert s.get_conversation(c.conversation_id).message_count == 2


def test_append_sets_last_message_at():
    s = svc()
    c = s.create_conversation(1)
    s.append_message(c.conversation_id, U, "hi")
    assert s.get_conversation(c.conversation_id).last_message_at is not None


def test_history_is_in_sequence_order():
    s = svc()
    c = s.create_conversation(1)
    s.append_message(c.conversation_id, U, "one")
    s.append_message(c.conversation_id, A, "two")
    assert [m.content for m in s.get_history(c.conversation_id)] == ["one", "two"]


def test_assistant_message_increments_unread():
    s = svc()
    c = s.create_conversation(1)
    s.append_message(c.conversation_id, A, "reply")
    assert s.get_conversation(c.conversation_id).unread_count == 1


def test_user_message_does_not_increment_unread():
    s = svc()
    c = s.create_conversation(1)
    s.append_message(c.conversation_id, U, "ask")
    assert s.get_conversation(c.conversation_id).unread_count == 0


def test_append_accumulates_token_stats():
    s = svc()
    c = s.create_conversation(1)
    s.append_message(c.conversation_id, A, "reply", token_usage=MessageTokenUsage(10, 4))
    s.append_message(c.conversation_id, U, "again")
    s.append_message(c.conversation_id, A, "reply2", token_usage=MessageTokenUsage(2, 3))
    stats = s.get_conversation(c.conversation_id).token_stats
    assert (stats.prompt_tokens, stats.completion_tokens, stats.total_tokens) == (12, 7, 19)


def test_first_user_message_auto_titles_conversation():
    s = svc()
    c = s.create_conversation(1)
    s.append_message(c.conversation_id, U, "How do I improve activation?")
    assert s.get_conversation(c.conversation_id).title == "How do I improve activation?"


def test_auto_title_only_applies_while_default():
    s = svc()
    c = s.create_conversation(1, title="Kept")
    s.append_message(c.conversation_id, U, "should not change title")
    assert s.get_conversation(c.conversation_id).title == "Kept"


def test_append_empty_content_fails_closed():
    s = svc()
    c = s.create_conversation(1)
    with pytest.raises(InvalidMessageError):
        s.append_message(c.conversation_id, U, "   ")


def test_append_to_missing_conversation_raises():
    with pytest.raises(ConversationNotFoundError):
        svc().append_message("nope", U, "hi")


def test_append_to_archived_raises():
    s = svc()
    c = s.create_conversation(1)
    s.archive_conversation(c.conversation_id)
    with pytest.raises(InvalidConversationStateError):
        s.append_message(c.conversation_id, U, "hi")


def test_append_to_deleted_raises():
    s = svc()
    c = s.create_conversation(1)
    s.delete_conversation(c.conversation_id)
    with pytest.raises(InvalidConversationStateError):
        s.append_message(c.conversation_id, U, "hi")


def test_append_important_and_metadata_preserved():
    s = svc()
    c = s.create_conversation(1)
    m = s.append_message(c.conversation_id, U, "keep me", important=True, metadata={"k": "v"})
    assert m.important is True and m.metadata == {"k": "v"}


# --- read -------------------------------------------------------------------


def test_get_history_empty():
    s = svc()
    c = s.create_conversation(1)
    assert s.get_history(c.conversation_id) == ()


def test_get_history_missing_raises():
    with pytest.raises(ConversationNotFoundError):
        svc().get_history("missing")


def test_get_conversation_missing_raises():
    with pytest.raises(ConversationNotFoundError):
        svc().get_conversation("missing")


def test_mark_read_resets_unread():
    s = svc()
    c = s.create_conversation(1)
    s.append_message(c.conversation_id, A, "reply")
    assert s.mark_read(c.conversation_id).unread_count == 0


def test_mark_read_idempotent_when_already_zero():
    s = svc()
    c = s.create_conversation(1)
    same = s.mark_read(c.conversation_id)
    assert same.unread_count == 0 and same.updated_at == c.updated_at


# --- lifecycle --------------------------------------------------------------


def test_rename():
    s = svc()
    c = s.create_conversation(1)
    assert s.rename_conversation(c.conversation_id, "Growth plan").title == "Growth plan"


def test_rename_blank_fails():
    s = svc()
    c = s.create_conversation(1)
    with pytest.raises(InvalidMessageError):
        s.rename_conversation(c.conversation_id, "  ")


def test_rename_truncates_overlong_title():
    s = svc()
    c = s.create_conversation(1)
    assert len(s.rename_conversation(c.conversation_id, "x" * 200).title) == 60


def test_archive_excluded_from_default_list():
    s = svc()
    c = s.create_conversation(1)
    s.archive_conversation(c.conversation_id)
    assert s.list_conversations(1) == ()
    assert len(s.list_conversations(1, include_archived=True)) == 1


def test_archive_deleted_raises():
    s = svc()
    c = s.create_conversation(1)
    s.delete_conversation(c.conversation_id)
    with pytest.raises(InvalidConversationStateError):
        s.archive_conversation(c.conversation_id)


def test_soft_delete_hidden_by_default():
    s = svc()
    c = s.create_conversation(1)
    s.delete_conversation(c.conversation_id)
    assert s.list_conversations(1) == ()
    assert len(s.list_conversations(1, include_deleted=True)) == 1
    assert s.get_conversation(c.conversation_id).status == ConversationStatus.DELETED


def test_restore_from_archived():
    s = svc()
    c = s.create_conversation(1)
    s.archive_conversation(c.conversation_id)
    assert s.restore_conversation(c.conversation_id).status == ConversationStatus.ACTIVE


def test_restore_from_deleted():
    s = svc()
    c = s.create_conversation(1)
    s.delete_conversation(c.conversation_id)
    assert s.restore_conversation(c.conversation_id).is_active


def test_restore_active_is_idempotent():
    s = svc()
    c = s.create_conversation(1)
    restored = s.restore_conversation(c.conversation_id)
    assert restored.status == ConversationStatus.ACTIVE and restored.updated_at == c.updated_at


def test_lifecycle_on_missing_raises():
    s = svc()
    for op in (s.archive_conversation, s.delete_conversation, s.restore_conversation):
        with pytest.raises(ConversationNotFoundError):
            op("missing")


# --- summarize (deterministic, no LLM) --------------------------------------


def test_summarize_empty_conversation():
    s = svc()
    c = s.create_conversation(1)
    summ = s.summarize_conversation(c.conversation_id)
    assert summ.summary == "No messages yet." and summ.covered_through_sequence == -1


def test_summarize_reports_counts_and_latest():
    s = svc()
    c = s.create_conversation(1)
    s.append_message(c.conversation_id, U, "How do I raise a seed round?")
    s.append_message(c.conversation_id, A, "Start with warm intros.")
    summ = s.summarize_conversation(c.conversation_id)
    assert "2 messages (1 from founder, 1 from Ally)" in summ.summary
    assert "How do I raise a seed round?" in summ.summary
    assert summ.covered_through_sequence == 1


def test_summarize_persisted_and_retrievable():
    s = svc()
    c = s.create_conversation(1)
    s.append_message(c.conversation_id, U, "hi")
    s.summarize_conversation(c.conversation_id)
    assert s.repository.get_summary(c.conversation_id) is not None


def test_summarize_is_deterministic():
    def run():
        s = svc()
        c = s.create_conversation(1)
        s.append_message(c.conversation_id, U, "same question")
        s.append_message(c.conversation_id, A, "same answer")
        return s.summarize_conversation(c.conversation_id)
    assert run() == run()


# --- context window (deterministic truncation) ------------------------------


def _seed(s, n, founder=1):
    c = s.create_conversation(founder)
    for i in range(n):
        s.append_message(c.conversation_id, U if i % 2 == 0 else A, f"m{i}")
    return c


def test_build_context_returns_all_when_small():
    s = svc()
    c = _seed(s, 3)
    ctx = s.build_context(c.conversation_id, max_messages=10)
    assert ctx.total_messages == 3 and not ctx.truncated
    assert len(ctx.recent_messages) == 3 and ctx.summary is None


def test_build_context_truncates_to_recent():
    s = svc()
    c = _seed(s, 5)
    ctx = s.build_context(c.conversation_id, max_messages=2)
    assert ctx.truncated and ctx.total_messages == 5
    assert [m.sequence for m in ctx.recent_messages] == [3, 4]


def test_build_context_preserves_important_messages():
    s = svc()
    c = s.create_conversation(1)
    s.append_message(c.conversation_id, U, "pin me", important=True)   # seq 0
    for i in range(1, 5):
        s.append_message(c.conversation_id, U, f"m{i}")
    ctx = s.build_context(c.conversation_id, max_messages=2)
    assert [m.sequence for m in ctx.recent_messages] == [0, 3, 4]      # important + recent


def test_build_context_empty_conversation():
    s = svc()
    c = s.create_conversation(1)
    ctx = s.build_context(c.conversation_id)
    assert ctx.is_empty and ctx.recent_messages == () and not ctx.truncated


def test_build_context_attaches_summary_when_truncated():
    s = svc()
    c = _seed(s, 5)
    s.summarize_conversation(c.conversation_id)
    ctx = s.build_context(c.conversation_id, max_messages=2)
    assert ctx.truncated and ctx.summary is not None
