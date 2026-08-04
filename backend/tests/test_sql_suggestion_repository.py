"""SqlSuggestionRepository -- live DB conformance + the actual resume proof.

Ranking/generation logic is already covered against the in-memory repository in
test_ai_chat_suggestions.py and is repository-independent. This file exercises
what IS repository-specific: durable persistence of suggestions AND their
feedback audit trail, and -- the actual point of this fix -- that a suggestion
generated in one DB session is found and can receive feedback from a completely
separate session.

suggestions.conversation_id is a real FK to conversations.external_id, so each
test persists a real conversation via SqlConversationRepository first.
"""

from datetime import datetime, timedelta, timezone
from itertools import count
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.ai_chat.repositories.sql_conversation import SqlConversationRepository
from app.ai_chat.services.conversation import build_conversation_service
from app.ai_chat.suggestions.schemas import (
    SuggestionFeedbackType,
    SuggestionPriority,
    SuggestionReason,
    SuggestionSource,
    SuggestionStatus,
    SuggestionType,
)
from app.ai_chat.suggestions.service import build_suggestion_service
from app.ai_chat.suggestions.sql_repository import SqlSuggestionRepository
from app.db.session import SessionLocal

T0 = datetime(2026, 7, 28, 14, 0, 0, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self, start=T0, step=timedelta(seconds=1)):
        self._now, self._step = start, step

    def now(self):
        v = self._now
        self._now += self._step
        return v


def _ids(prefix="s"):
    c = count(1)
    return lambda: f"{prefix}-{uuid4().hex[:8]}-{next(c)}"


@pytest.fixture
def founder_and_conversation():
    db = SessionLocal()
    uid = uuid4()
    email = f"suggrepo+{uid.hex[:8]}@verify.test"
    db.execute(text(
        "insert into auth.users (id,instance_id,aud,role,email) values "
        "(:i,'00000000-0000-0000-0000-000000000000','authenticated','authenticated',:e)"
    ), {"i": str(uid), "e": email})
    db.commit()
    fid = db.execute(text(
        "insert into founders (user_id,full_name,email) values (:u,:n,:e) returning founder_id"
    ), {"u": str(uid), "n": "Suggestion Repo Test", "e": email}).scalar()
    db.commit()
    conv = build_conversation_service(
        SqlConversationRepository(db), clock=FakeClock(), id_factory=_ids("conv")
    ).create_conversation(fid)
    db.commit()
    db.close()
    yield fid, conv.conversation_id
    cleanup = SessionLocal()
    cleanup.execute(text(
        "delete from suggestion_feedback where founder_id=:f"
    ), {"f": fid})
    cleanup.execute(text("delete from suggestions where founder_id=:f"), {"f": fid})
    cleanup.execute(text("delete from conversations where founder_id=:f"), {"f": fid})
    cleanup.execute(text("delete from founders where founder_id=:f"), {"f": fid})
    cleanup.execute(text("delete from auth.users where id=:u"), {"u": str(uid)})
    cleanup.commit()
    residue = {
        t: cleanup.execute(text(f"select count(*) from {t} where founder_id=:f"), {"f": fid}).scalar()
        for t in ("suggestions", "suggestion_feedback", "conversations")
    }
    cleanup.close()
    assert all(v == 0 for v in residue.values()), f"residue left behind: {residue}"


def _draft_suggestion(conv_id, fid):
    """Build a raw Suggestion directly (bypassing the rule engine -- that logic is
    already covered elsewhere) so the repository can be exercised in isolation."""
    from app.ai_chat.suggestions.schemas import Suggestion
    now = T0
    return Suggestion(
        suggestion_id=f"s-{uuid4().hex[:8]}",
        conversation_id=conv_id,
        founder_id=fid,
        suggestion_type=SuggestionType.FOLLOW_UP,
        title="Ask about pricing",
        body="Consider asking what pricing model they have in mind.",
        priority=SuggestionPriority.HIGH,
        source=SuggestionSource.CONVERSATION,
        reason=SuggestionReason(code="R1", description="No pricing discussed yet"),
        dedup_key="pricing-followup",
        created_at=now,
        updated_at=now,
        relevance_score=0.75,
        rank=1,
    )


# --- create / read round-trip -------------------------------------------------

def test_add_persists_and_reads_back(founder_and_conversation):
    fid, conv_id = founder_and_conversation
    db = SessionLocal()
    s = _draft_suggestion(conv_id, fid)
    repo = SqlSuggestionRepository(db)
    repo.add(s)
    db.commit()
    fetched = repo.get(s.suggestion_id)
    assert fetched.title == "Ask about pricing"
    assert fetched.priority is SuggestionPriority.HIGH
    assert fetched.relevance_score == 0.75 and fetched.rank == 1
    assert fetched.reason.code == "R1" and fetched.reason.description == "No pricing discussed yet"
    db.close()


def test_list_for_conversation_ordered_by_rank(founder_and_conversation):
    fid, conv_id = founder_and_conversation
    db = SessionLocal()
    repo = SqlSuggestionRepository(db)
    s1 = _draft_suggestion(conv_id, fid)
    from dataclasses import replace
    s2 = replace(s1, suggestion_id=f"s-{uuid4().hex[:8]}", rank=0, dedup_key="other")
    repo.add(s1)  # rank=1
    repo.add(s2)  # rank=0
    db.commit()
    listed = repo.list_for_conversation(conv_id, statuses=(SuggestionStatus.ACTIVE,))
    assert [s.suggestion_id for s in listed] == [s2.suggestion_id, s1.suggestion_id]
    db.close()


# --- feedback audit trail ------------------------------------------------------

def test_feedback_persists_and_updates_suggestion(founder_and_conversation):
    fid, conv_id = founder_and_conversation
    db = SessionLocal()
    repo = SqlSuggestionRepository(db)
    draft = _draft_suggestion(conv_id, fid)
    repo.add(draft)
    db.commit()

    # record_feedback goes through the SERVICE (repository-independent logic),
    # backed by our SQL repository this time instead of in-memory.
    service2 = build_suggestion_service(repo, clock=FakeClock(), id_factory=_ids("fb"))
    fb = service2.record_feedback(draft.suggestion_id, SuggestionFeedbackType.ACCEPTED)
    db.commit()
    assert fb.feedback_type is SuggestionFeedbackType.ACCEPTED

    fetched = repo.get(draft.suggestion_id)
    assert fetched.feedback is SuggestionFeedbackType.ACCEPTED   # persisted on the row

    history = repo.list_feedback(draft.suggestion_id)
    assert len(history) == 1 and history[0].feedback_type is SuggestionFeedbackType.ACCEPTED
    db.close()


# --- THE ACTUAL FIX: resume across a completely separate DB session ---------

def test_suggestion_and_feedback_found_across_separate_sessions(founder_and_conversation):
    fid, conv_id = founder_and_conversation
    db1 = SessionLocal()
    repo1 = SqlSuggestionRepository(db1)
    draft = _draft_suggestion(conv_id, fid)
    repo1.add(draft)
    db1.commit()
    db1.close()   # the "process" that generated it is gone

    db2 = SessionLocal()
    repo2 = SqlSuggestionRepository(db2)
    fetched = repo2.get(draft.suggestion_id)
    assert fetched is not None and fetched.title == draft.title

    service2 = build_suggestion_service(repo2, clock=FakeClock(), id_factory=_ids("fb2"))
    service2.record_feedback(draft.suggestion_id, SuggestionFeedbackType.DISMISSED)
    db2.commit()
    db2.close()

    db3 = SessionLocal()
    repo3 = SqlSuggestionRepository(db3)
    final = repo3.get(draft.suggestion_id)
    assert final.feedback is SuggestionFeedbackType.DISMISSED
    db3.close()


# --- lifecycle + purge --------------------------------------------------------

def test_list_excludes_deleted_by_default(founder_and_conversation):
    fid, conv_id = founder_and_conversation
    db = SessionLocal()
    repo = SqlSuggestionRepository(db)
    keep = _draft_suggestion(conv_id, fid)
    from dataclasses import replace
    gone = replace(keep, suggestion_id=f"s-{uuid4().hex[:8]}", dedup_key="gone",
                   status=SuggestionStatus.DELETED)
    repo.add(keep)
    repo.add(gone)
    db.commit()
    visible = {s.suggestion_id for s in repo.list_for_conversation(conv_id, statuses=(SuggestionStatus.ACTIVE,))}
    assert visible == {keep.suggestion_id}
    db.close()


def test_purge_removes_suggestion_and_its_feedback(founder_and_conversation):
    fid, conv_id = founder_and_conversation
    db = SessionLocal()
    repo = SqlSuggestionRepository(db)
    draft = _draft_suggestion(conv_id, fid)
    repo.add(draft)
    db.commit()
    service = build_suggestion_service(repo, clock=FakeClock(), id_factory=_ids("fb3"))
    service.record_feedback(draft.suggestion_id, SuggestionFeedbackType.IGNORED)
    db.commit()

    assert repo.purge(draft.suggestion_id) is True
    db.commit()
    remaining_s = db.execute(text(
        "select count(*) from suggestions where suggestion_id=:s"
    ), {"s": draft.suggestion_id}).scalar()
    remaining_f = db.execute(text(
        "select count(*) from suggestion_feedback where suggestion_id=:s"
    ), {"s": draft.suggestion_id}).scalar()
    assert remaining_s == 0 and remaining_f == 0   # CASCADE removed the feedback
    db.close()
