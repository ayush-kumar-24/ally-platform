"""Tests for AI Suggestions (Phase 6, Milestone 5). Deterministic, rule-based, no LLM."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from itertools import count
from types import SimpleNamespace

import pytest

from app.ai_chat.schemas.conversation import Conversation, ConversationStatus
from app.ai_chat.suggestions import (
    InMemorySuggestionRepository,
    Suggestion,
    SuggestionFeedbackType,
    SuggestionNotFoundError,
    SuggestionPriority,
    SuggestionRankingService,
    SuggestionReason,
    SuggestionSource,
    SuggestionStatus,
    SuggestionType,
    build_suggestion_service,
)

T0 = datetime(2026, 7, 28, 14, 0, 0, tzinfo=timezone.utc)
P, TY = SuggestionPriority, SuggestionType


class FakeClock:
    def __init__(self, start=T0, step=timedelta(seconds=1)):
        self._now, self._step = start, step

    def now(self):
        v = self._now
        self._now += self._step
        return v


def _ids(prefix="s"):
    c = count(1)
    return lambda: f"{prefix}-{next(c)}"


def svc(**kw):
    return build_suggestion_service(clock=FakeClock(), id_factory=_ids(), **kw)


def conv(*, cid="c1", founder=1, messages=2):
    return Conversation(cid, founder, "Chat", ConversationStatus.ACTIVE, T0, T0, message_count=messages)


def window(*, has_diagnosis=True, next_steps=(), root_cause="Weak activation"):
    ally = SimpleNamespace(
        has_diagnosis=has_diagnosis,
        diagnosis=SimpleNamespace(next_steps=tuple(next_steps), priority_actions=()),
        root_causes=(SimpleNamespace(name=root_cause, is_top_finding=True),),
    )
    return SimpleNamespace(ally_context=ally)


def ai(ok=True):
    return SimpleNamespace(ok=ok, response_type="answer" if ok else "none")


def _types(collection):
    return {s.suggestion_type for s in collection.suggestions}


# --- rule firing ------------------------------------------------------------


def test_follow_up_suggestion_when_answered():
    col = svc().generate_suggestions(conv(), ai_response=ai(True))
    assert TY.FOLLOW_UP in _types(col)


def test_clarification_when_not_answered():
    col = svc().generate_suggestions(conv(), ai_response=ai(False))
    assert TY.CLARIFICATION in _types(col) and TY.FOLLOW_UP not in _types(col)


def test_missing_information_when_no_diagnosis():
    col = svc().generate_suggestions(conv(), context_window=window(has_diagnosis=False))
    assert TY.MISSING_INFORMATION in _types(col)


def test_summarization_when_conversation_is_long():
    assert TY.SUMMARIZATION in _types(svc().generate_suggestions(conv(messages=9)))
    assert TY.SUMMARIZATION not in _types(svc().generate_suggestions(conv(messages=3)))


def test_attachment_review_when_attachments_present():
    atts = (SimpleNamespace(is_active=True), SimpleNamespace(is_active=True))
    col = svc().generate_suggestions(conv(), attachments=atts)
    review = next(s for s in col.suggestions if s.suggestion_type == TY.ATTACHMENT_REVIEW)
    assert "2 file" in review.body


def test_link_discussion_when_links_present():
    links = (SimpleNamespace(link_type=SimpleNamespace(value="github")),)
    assert TY.LINK_DISCUSSION in _types(svc().generate_suggestions(conv(), links=links))


def test_goal_reminder_from_diagnosis_next_step():
    col = svc().generate_suggestions(conv(), context_window=window(next_steps=("Book a discovery call",)))
    goal = next(s for s in col.suggestions if s.suggestion_type == TY.GOAL_REMINDER)
    assert "Book a discovery call" in goal.body and goal.priority == P.HIGH


def test_continue_conversation_when_messages_exist():
    assert TY.CONTINUE_CONVERSATION in _types(svc().generate_suggestions(conv(messages=1)))


# --- ranking ----------------------------------------------------------------


def _sug(priority=P.MEDIUM, relevance=0.5, dedup="k", stype=TY.FOLLOW_UP, created=T0, sid="s", title="t"):
    return Suggestion(
        suggestion_id=sid, conversation_id="c1", founder_id=1, suggestion_type=stype,
        title=title, body="b", priority=priority, source=SuggestionSource.SYSTEM,
        reason=SuggestionReason("r", "d"), dedup_key=dedup, created_at=created, updated_at=created,
        relevance_score=relevance,
    )


def test_ranking_orders_by_priority():
    ranked = SuggestionRankingService().rank([
        _sug(priority=P.LOW, dedup="a", sid="1"),
        _sug(priority=P.HIGH, dedup="b", sid="2"),
        _sug(priority=P.MEDIUM, dedup="c", sid="3"),
    ]).ranked
    assert [s.priority for s in ranked] == [P.HIGH, P.MEDIUM, P.LOW]
    assert [s.rank for s in ranked] == [0, 1, 2]


def test_ranking_recency_breaks_ties():
    ranked = SuggestionRankingService().rank([
        _sug(dedup="a", sid="1", created=T0),
        _sug(dedup="b", sid="2", created=T0 + timedelta(seconds=10)),
    ]).ranked
    assert ranked[0].suggestion_id == "2"                 # newer first when priority+relevance equal


def test_duplicate_suppression_keeps_strongest():
    result = SuggestionRankingService().rank([
        _sug(priority=P.LOW, dedup="same", sid="1"),
        _sug(priority=P.HIGH, dedup="same", sid="2"),
    ])
    assert result.suppressed_duplicates == 1 and len(result.ranked) == 1
    assert result.ranked[0].suggestion_id == "2" and result.ranked[0].priority == P.HIGH


def test_maximum_suggestions_limit():
    result = SuggestionRankingService().rank(
        [_sug(dedup=k, sid=k) for k in ("a", "b", "c", "d")], max_count=2)
    assert len(result.ranked) == 2 and result.limited is True


def test_service_respects_max_count():
    col = svc().generate_suggestions(
        conv(messages=9), context_window=window(next_steps=("Do X",)), ai_response=ai(True),
        links=(SimpleNamespace(link_type=SimpleNamespace(value="github")),), max_count=2)
    assert col.metrics.returned == 2 and col.trace.limited is True


# --- feedback ---------------------------------------------------------------


def test_feedback_accepted_recorded():
    s = svc()
    col = s.generate_suggestions(conv(), ai_response=ai(True))
    sid = col.top.suggestion_id
    fb = s.record_feedback(sid, SuggestionFeedbackType.ACCEPTED, note="useful")
    assert fb.feedback_type == SuggestionFeedbackType.ACCEPTED
    assert s.get_suggestion(sid).feedback == SuggestionFeedbackType.ACCEPTED
    assert len(s.feedback_history(sid)) == 1


def test_feedback_dismissed_recorded():
    s = svc()
    sid = s.generate_suggestions(conv(), ai_response=ai(True)).top.suggestion_id
    s.record_feedback(sid, SuggestionFeedbackType.DISMISSED)
    assert s.get_suggestion(sid).feedback == SuggestionFeedbackType.DISMISSED


def test_feedback_on_missing_raises():
    with pytest.raises(SuggestionNotFoundError):
        svc().record_feedback("nope", SuggestionFeedbackType.IGNORED)


# --- lifecycle --------------------------------------------------------------


def test_archive_restore_delete():
    s = svc()
    sid = s.generate_suggestions(conv(), ai_response=ai(True)).top.suggestion_id

    s.archive_suggestion(sid)
    assert all(x.suggestion_id != sid for x in s.list_suggestions("c1"))
    assert any(x.suggestion_id == sid for x in s.list_suggestions("c1", include_archived=True))

    s.restore_suggestion(sid)
    assert s.get_suggestion(sid).status == SuggestionStatus.ACTIVE

    s.delete_suggestion(sid)
    assert s.get_suggestion(sid).is_deleted
    assert any(x.suggestion_id == sid for x in s.history("c1"))


def test_lifecycle_missing_raises():
    s = svc()
    for op in (s.archive_suggestion, s.restore_suggestion, s.delete_suggestion, s.get_suggestion):
        with pytest.raises(SuggestionNotFoundError):
            op("nope")


# --- metrics + trace --------------------------------------------------------


def test_metrics_and_trace():
    col = svc().generate_suggestions(
        conv(messages=9), context_window=window(next_steps=("Do X",)), ai_response=ai(True))
    assert col.metrics.returned == len(col.suggestions)
    assert col.metrics.by_priority.get("high", 0) >= 1
    assert "rule_goal_reminder" in col.trace.rules_fired


# --- determinism + concurrency + isolation ----------------------------------


def _run(service):
    return service.generate_suggestions(
        conv(messages=9), context_window=window(next_steps=("Do X",)), ai_response=ai(True),
        links=(SimpleNamespace(link_type=SimpleNamespace(value="github")),))


def test_deterministic_execution():
    a = _run(svc())
    b = _run(svc())
    assert [(s.suggestion_id, s.suggestion_type, s.rank, s.relevance_score) for s in a.suggestions] == \
           [(s.suggestion_id, s.suggestion_type, s.rank, s.relevance_score) for s in b.suggestions]
    assert a.metrics == b.metrics and a.trace.rules_fired == b.trace.rules_fired


def test_concurrent_requests():
    service = build_suggestion_service()                  # uuid ids, thread-safe repo

    def gen(i):
        col = service.generate_suggestions(conv(cid=f"c{i}", founder=i), ai_response=ai(True))
        return col.conversation_id == f"c{i}" and not col.is_empty

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert all(pool.map(gen, range(1, 25)))


def test_independent_founders_isolated():
    service = build_suggestion_service(id_factory=_ids())
    service.generate_suggestions(conv(cid="c1", founder=1), ai_response=ai(True))
    service.generate_suggestions(conv(cid="c2", founder=2), ai_response=ai(True))
    c1 = service.list_suggestions("c1")
    c2 = service.list_suggestions("c2")
    assert all(s.founder_id == 1 for s in c1) and all(s.founder_id == 2 for s in c2)
    assert {s.conversation_id for s in c1} == {"c1"} and {s.conversation_id for s in c2} == {"c2"}
