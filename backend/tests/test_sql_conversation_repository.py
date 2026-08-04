"""SqlConversationRepository -- live DB conformance + the actual resume proof.

Business-logic behaviour (title derivation, unread counting, state-machine rules)
is already covered against the in-memory repository in test_ai_chat_conversation.py
and is repository-independent -- it is not re-tested here. This file exercises what
IS repository-specific: durable persistence, the string<->integer id mapping, JSONB
round-tripping of fields the original table didn't carry, and -- the actual point of
this fix -- that a conversation started in one DB session/process is found and
continuable from a completely separate session, unlike the in-memory repository.

Uses a throwaway founder (real auth.users + founders rows), deleted in reverse-FK
order, with an explicit zero-residue check.
"""

from datetime import datetime, timedelta, timezone
from itertools import count
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.ai_chat.repositories.sql_conversation import SqlConversationRepository
from app.ai_chat.schemas.conversation import DEFAULT_TITLE, ConversationStatus, MessageRole, MessageTokenUsage
from app.ai_chat.services.conversation import build_conversation_service
from app.db.session import SessionLocal

U, A = MessageRole.USER, MessageRole.ASSISTANT
T0 = datetime(2026, 7, 28, 10, 0, 0, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self, start=T0, step=timedelta(seconds=1)):
        self._now, self._step = start, step

    def now(self):
        v = self._now
        self._now += self._step
        return v


def _ids():
    c = count(1)
    return lambda: f"id-{uuid4().hex[:8]}-{next(c)}"


@pytest.fixture
def founder_id():
    """A throwaway founder for one test, cleaned up in reverse-FK order."""
    db = SessionLocal()
    uid = uuid4()
    email = f"chatrepo+{uid.hex[:8]}@verify.test"
    db.execute(text(
        "insert into auth.users (id,instance_id,aud,role,email) values "
        "(:i,'00000000-0000-0000-0000-000000000000','authenticated','authenticated',:e)"
    ), {"i": str(uid), "e": email})
    db.commit()
    fid = db.execute(text(
        "insert into founders (user_id,full_name,email) values (:u,:n,:e) returning founder_id"
    ), {"u": str(uid), "n": "Chat Repo Test", "e": email}).scalar()
    db.commit()
    db.close()
    yield fid
    cleanup = SessionLocal()
    for t in ("messages", "conversations"):
        cleanup.execute(text(f"delete from {t} where founder_id=:f"), {"f": fid})
    cleanup.execute(text("delete from founders where founder_id=:f"), {"f": fid})
    cleanup.execute(text("delete from auth.users where id=:u"), {"u": str(uid)})
    cleanup.commit()
    residue = {
        t: cleanup.execute(text(f"select count(*) from {t} where founder_id=:f"), {"f": fid}).scalar()
        for t in ("messages", "conversations")
    }
    cleanup.execute(text("select count(*) from founders where founder_id=:f"), {"f": fid})
    cleanup.close()
    assert all(v == 0 for v in residue.values()), f"residue left behind: {residue}"


def svc(db):
    return build_conversation_service(SqlConversationRepository(db), clock=FakeClock(), id_factory=_ids())


# --- create / append / history round-trip -----------------------------------

def test_create_persists_and_reads_back(founder_id):
    db = SessionLocal()
    conv = svc(db).create_conversation(founder_id, title="My chat")
    db.commit()
    fetched = svc(db).get_conversation(conv.conversation_id)
    assert fetched.title == "My chat" and fetched.status is ConversationStatus.ACTIVE
    db.close()


def test_default_title_when_blank(founder_id):
    db = SessionLocal()
    conv = svc(db).create_conversation(founder_id)
    assert conv.title == DEFAULT_TITLE
    db.close()


def test_append_and_history_order(founder_id):
    db = SessionLocal()
    s = svc(db)
    conv = s.create_conversation(founder_id)
    s.append_message(conv.conversation_id, U, "First")
    s.append_message(conv.conversation_id, A, "Second")
    s.append_message(conv.conversation_id, U, "Third")
    db.commit()
    hist = s.get_history(conv.conversation_id)
    assert [m.content for m in hist] == ["First", "Second", "Third"]
    assert [m.sequence for m in hist] == [0, 1, 2]     # derived from row order, not stored
    db.close()


def test_important_and_token_usage_round_trip(founder_id):
    db = SessionLocal()
    s = svc(db)
    conv = s.create_conversation(founder_id)
    s.append_message(
        conv.conversation_id, A, "flagged reply",
        token_usage=MessageTokenUsage(prompt_tokens=120, completion_tokens=45),
        important=True, metadata={"caller_key": "caller_value"},
    )
    db.commit()
    msg = s.get_history(conv.conversation_id)[0]
    assert msg.important is True
    assert msg.token_usage.prompt_tokens == 120 and msg.token_usage.completion_tokens == 45
    assert msg.metadata == {"caller_key": "caller_value"}   # internal _keys stripped back out
    db.close()


def test_token_stats_roll_up_persists(founder_id):
    db = SessionLocal()
    s = svc(db)
    conv = s.create_conversation(founder_id)
    s.append_message(conv.conversation_id, U, "q1", token_usage=MessageTokenUsage(10, 0))
    s.append_message(conv.conversation_id, A, "a1", token_usage=MessageTokenUsage(0, 25))
    db.commit()
    fetched = s.get_conversation(conv.conversation_id)
    assert fetched.token_stats.prompt_tokens == 10
    assert fetched.token_stats.completion_tokens == 25
    assert fetched.token_stats.total_tokens == 35
    db.close()


def test_unread_increments_only_for_assistant(founder_id):
    db = SessionLocal()
    s = svc(db)
    conv = s.create_conversation(founder_id)
    s.append_message(conv.conversation_id, U, "hi")
    s.append_message(conv.conversation_id, A, "hello")
    db.commit()
    assert s.get_conversation(conv.conversation_id).unread_count == 1
    db.close()


# --- THE ACTUAL FIX: resume across a completely separate DB session ---------

def test_resume_across_separate_sessions_and_processes(founder_id):
    """The one the in-memory repository could never pass: a conversation started
    in one DB session (simulating one server process) is fully readable and
    continuable from a totally independent session (simulating another)."""
    db1 = SessionLocal()
    s1 = svc(db1)
    conv = s1.create_conversation(founder_id, title="Cross-process chat")
    s1.append_message(conv.conversation_id, U, "Message from visit 1")
    db1.commit()
    db1.close()   # the "process" that started the conversation is gone

    # --- a brand new session, as a genuinely separate request/worker would open ---
    db2 = SessionLocal()
    s2 = svc(db2)
    found = s2.list_conversations(founder_id)
    assert len(found) == 1 and found[0].conversation_id == conv.conversation_id
    history = s2.get_history(conv.conversation_id)
    assert len(history) == 1 and history[0].content == "Message from visit 1"

    s2.append_message(conv.conversation_id, A, "Reply from visit 2")
    db2.commit()
    final = s2.get_history(conv.conversation_id)
    assert len(final) == 2 and final[1].content == "Reply from visit 2"
    db2.close()


# --- lifecycle + purge --------------------------------------------------------

def test_archive_delete_restore_persist(founder_id):
    db = SessionLocal()
    s = svc(db)
    conv = s.create_conversation(founder_id)
    s.archive_conversation(conv.conversation_id)
    db.commit()
    assert s.get_conversation(conv.conversation_id).status is ConversationStatus.ARCHIVED

    s.restore_conversation(conv.conversation_id)
    db.commit()
    assert s.get_conversation(conv.conversation_id).status is ConversationStatus.ACTIVE

    s.delete_conversation(conv.conversation_id)
    db.commit()
    assert s.get_conversation(conv.conversation_id).status is ConversationStatus.DELETED
    db.close()


def test_list_conversations_excludes_deleted_by_default(founder_id):
    db = SessionLocal()
    s = svc(db)
    keep = s.create_conversation(founder_id, title="keep")
    gone = s.create_conversation(founder_id, title="gone")
    s.delete_conversation(gone.conversation_id)
    db.commit()
    visible = {c.conversation_id for c in s.list_conversations(founder_id)}
    assert visible == {keep.conversation_id}
    db.close()


def test_purge_hard_removes_conversation_and_messages(founder_id):
    db = SessionLocal()
    s = svc(db)
    conv = s.create_conversation(founder_id)
    s.append_message(conv.conversation_id, U, "will be purged")
    db.commit()
    repo = SqlConversationRepository(db)
    assert repo.purge_conversation(conv.conversation_id) is True
    db.commit()
    remaining_conv = db.execute(text(
        "select count(*) from conversations where external_id=:c"
    ), {"c": conv.conversation_id}).scalar()
    remaining_msgs = db.execute(text(
        "select count(*) from messages where founder_id=:f"
    ), {"f": founder_id}).scalar()
    assert remaining_conv == 0 and remaining_msgs == 0   # CASCADE removed the messages
    db.close()


def test_founder_isolation(founder_id):
    # conversations.founder_id has a real FK to founders -- isolation must be
    # checked against a second genuine founder, not a made-up id.
    db = SessionLocal()
    uid2 = uuid4()
    email2 = f"chatrepo2+{uid2.hex[:8]}@verify.test"
    db.execute(text(
        "insert into auth.users (id,instance_id,aud,role,email) values "
        "(:i,'00000000-0000-0000-0000-000000000000','authenticated','authenticated',:e)"
    ), {"i": str(uid2), "e": email2})
    other_founder_id = db.execute(text(
        "insert into founders (user_id,full_name,email) values (:u,:n,:e) returning founder_id"
    ), {"u": str(uid2), "n": "Other Founder", "e": email2}).scalar()
    db.commit()
    try:
        s = svc(db)
        mine = s.create_conversation(founder_id)
        other = s.create_conversation(other_founder_id)
        db.commit()
        visible = {c.conversation_id for c in s.list_conversations(founder_id)}
        assert mine.conversation_id in visible and other.conversation_id not in visible
    finally:
        db.execute(text("delete from conversations where external_id=:c"), {"c": other.conversation_id})
        db.execute(text("delete from founders where founder_id=:f"), {"f": other_founder_id})
        db.execute(text("delete from auth.users where id=:u"), {"u": str(uid2)})
        db.commit()
        db.close()
