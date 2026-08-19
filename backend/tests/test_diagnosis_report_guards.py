"""Guards on the diagnosis -> report path. Hermetic: no DB, no network.

Three defects motivated every test here, and each one was silent in production:

  1. Answers were classified by an LLM TWICE -- once by the submit-time advisor
     (which persists answers.score_label) and again, from scratch, by the
     reasoning pipeline. Thirty redundant provider calls per diagnosis, measured
     as 161s of a 203s pipeline.

  2. A session whose answers were all unscored produced a report containing
     nothing at all -- no exception, no error log, a 200 response. Reachable from
     configuration alone (ADAPTIVE_QUESTIONS=false + ANSWER_CLASSIFIER=stored,
     which is the pair .env.example ships).

  3. That whole pipeline ran inside the founder's final HTTP request, so a
     load-balancer timeout severed it and left a COMPLETED session with no report
     and no way back.

These assert the fixes hold, not that the code is written a particular way.
"""

import asyncio
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.api.v1.diagnosis.notifications import (
    NullSessionCompletionNotifier,
    SessionCompletionNotifier,
)
from app.api.v1.reasoning.engines.diagnostic import (
    StoredFirstAnswerClassifier,
    StoredScoreAnswerClassifier,
)
from app.api.v1.reasoning.errors import DiagnosisDataError, NoClassifiableAnswersError
from app.api.v1.reasoning.interfaces import AnswerClassifier
from app.api.v1.reasoning.schemas import AnswerClassification
from app.core.config import settings
from app.models.enums import ScoreLabel


# --- minimal doubles --------------------------------------------------------

def _context():
    """Just enough ReasoningContext for the stored classifier: the score bands."""
    bands = SimpleNamespace(green=Decimal(2), amber=Decimal(1), red=Decimal(0))
    return SimpleNamespace(config=SimpleNamespace(question_scores=bands))


def _answer(answer_id=1, question_id=10, score_label=None, score=None):
    return SimpleNamespace(
        answer_id=answer_id, question_id=question_id,
        score_label=score_label, score=score,
        is_distress_flagged=False, is_follow_up=False,
        triggered_follow_up_id=None, answer_text="something the founder said",
    )


class CountingClassifier(AnswerClassifier):
    """Stands in for the LLM classifier and records whether it was reached.

    The count IS the assertion for finding (1): a stored label must never cost a
    provider call.
    """

    def __init__(self):
        self.calls = 0

    async def classify(self, answer, question, context, *, previous_conversation=None):
        self.calls += 1
        return AnswerClassification(
            answer_id=answer.answer_id, question_id=answer.question_id,
            label=ScoreLabel.AMBER, score=Decimal(1),
            is_distress_flagged=False, is_follow_up=False,
            triggered_follow_up_id=None,
        )


# --- (1) stored labels are reused, never re-derived -------------------------

def test_stored_label_is_reused_without_calling_the_llm():
    llm = CountingClassifier()
    classifier = StoredFirstAnswerClassifier(
        stored=StoredScoreAnswerClassifier(), fallback=llm
    )
    answer = _answer(score_label="green")

    result = asyncio.run(classifier.classify(answer, None, _context()))

    assert result.label is ScoreLabel.GREEN
    assert llm.calls == 0, "an answer already scored at submit time must not be re-classified"


def test_thirty_stored_answers_cost_zero_provider_calls():
    """The finding, at the scale it actually occurred: a full 30-question
    diagnosis where the advisor scored every answer."""
    llm = CountingClassifier()
    classifier = StoredFirstAnswerClassifier(
        stored=StoredScoreAnswerClassifier(), fallback=llm
    )
    answers = [_answer(answer_id=i, score_label="amber") for i in range(30)]

    for answer in answers:
        asyncio.run(classifier.classify(answer, None, _context()))

    assert llm.calls == 0


def test_unscored_answer_still_reaches_the_llm():
    """Not "always use stored" -- an answer with no band must still be classified,
    or it is dropped from the evidence set entirely."""
    llm = CountingClassifier()
    classifier = StoredFirstAnswerClassifier(
        stored=StoredScoreAnswerClassifier(), fallback=llm
    )

    result = asyncio.run(classifier.classify(_answer(), None, _context()))

    assert llm.calls == 1
    assert result.label is ScoreLabel.AMBER


def test_mixed_session_is_fully_classified():
    """A session spanning a config change: some answers labelled, some not. Every
    answer comes out classified, and only the unlabelled ones cost a call."""
    llm = CountingClassifier()
    classifier = StoredFirstAnswerClassifier(
        stored=StoredScoreAnswerClassifier(), fallback=llm
    )
    answers = [_answer(answer_id=1, score_label="green"), _answer(answer_id=2),
               _answer(answer_id=3, score_label="red"), _answer(answer_id=4)]

    results = [asyncio.run(classifier.classify(a, None, _context())) for a in answers]

    assert len(results) == 4
    assert llm.calls == 2


def test_numeric_score_alone_counts_as_stored():
    """score_label is the authoritative band, but a bare numeric score is enough
    to resolve one -- and must not trigger a provider call either."""
    llm = CountingClassifier()
    classifier = StoredFirstAnswerClassifier(
        stored=StoredScoreAnswerClassifier(), fallback=llm
    )

    result = asyncio.run(classifier.classify(_answer(score=0), None, _context()))

    assert llm.calls == 0
    assert result.label is ScoreLabel.RED


# --- (2) an empty evidence set must not become a report ---------------------

def test_stored_classifier_refuses_to_guess_an_unscored_answer():
    """The behaviour the empty-report bug was built on: this raises rather than
    inventing a band. Correct on its own -- the bug was what the caller did with it."""
    with pytest.raises(DiagnosisDataError):
        asyncio.run(StoredScoreAnswerClassifier().classify(_answer(), None, _context()))


def test_no_classifiable_answers_error_is_a_422_reasoning_error():
    from app.api.v1.reasoning.errors import ReasoningError

    exc = NoClassifiableAnswersError()
    assert isinstance(exc, ReasoningError)
    assert exc.status_code == 422


def test_pipeline_raises_rather_than_persisting_an_empty_report(monkeypatch):
    """The guard itself: answers present, zero classifications -> refuse.

    Asserted against the real _run_pipeline so it cannot be satisfied by a
    reimplementation of the check somewhere that does not run.
    """
    from app.api.v1.reasoning.service import ReasoningService

    session = SimpleNamespace(session_id=54, founder_id=7)
    founder = SimpleNamespace(founder_id=7, full_name="Test Founder", stage_id=None,
                              industry_mapped_id=None)

    class EmptyDiagnosisEngine:
        async def diagnose(self, answers, questions, context):
            # What classify_answers returns when every answer is unscored: it
            # skips them individually, so the batch comes back empty.
            return SimpleNamespace(
                classifications=(), category_risks=(), symptoms=(),
                distress_mode=False,
                stage_detection=SimpleNamespace(stage_id=None),
            )

    service = ReasoningService.__new__(ReasoningService)
    service.db = SimpleNamespace(rollback=lambda: None)
    service.repository = SimpleNamespace(
        get_answers_for_session=lambda sid: [_answer(answer_id=i) for i in range(30)],
        get_questions_by_ids=lambda ids: {},
    )
    service.diagnosis_engine = EmptyDiagnosisEngine()
    monkeypatch.setattr(
        ReasoningService, "_build_context",
        lambda self, s, f: SimpleNamespace(stage_id=None, industry_id=None,
                                           config=_context().config),
    )

    with pytest.raises(NoClassifiableAnswersError):
        asyncio.run(service._run_pipeline(session, founder))


@pytest.mark.parametrize(
    "adaptive, classifier, expected",
    [
        # The pair .env.example ships and DEPLOY_AWS.md does not mention. Nothing
        # writes a band, nothing derives one: every report comes out empty.
        (False, "stored", False),
        # Either one alone is sufficient.
        (True, "stored", True),    # advisor writes it at submit time
        (False, "llm", True),      # pipeline derives it at report time
        (True, "llm", True),       # both (what this deployment runs)
    ],
)
def test_scoring_configuration_predicate(monkeypatch, adaptive, classifier, expected):
    """The coupling that caused the empty reports, asserted directly. main.py logs
    at ERROR on boot when this is False, so the misconfiguration is answerable
    before a founder spends an assessment on it."""
    monkeypatch.setattr(settings, "ADAPTIVE_QUESTIONS", adaptive)
    monkeypatch.setattr(settings, "ANSWER_CLASSIFIER", classifier)
    assert settings.diagnosis_scoring_configured is expected


# --- (3) reasoning must not ride on the request --------------------------------

def test_notifier_port_takes_ids_not_orm_objects():
    """Load-bearing, not stylistic: the listener now runs after get_db has closed
    the request session, so a Founder passed across that boundary is detached and
    raises on first attribute access."""
    import inspect

    params = list(
        inspect.signature(
            NullSessionCompletionNotifier.notify_session_completed
        ).parameters
    )
    assert params == ["self", "founder_id", "session_id", "founder_uuid"]


def test_background_session_sets_rls_context_before_querying():
    """The subtlest part of moving off the request path. A fresh session carries
    no RLS context, and the founder-isolation policies resolve through
    get_founder_id() -> app.current_founder_uuid -- so an unscoped session sees
    zero rows on sessions/answers/founder_reports and the pipeline would
    'succeed' having analysed nothing at all."""
    import inspect

    from app.api.v1.reasoning.trigger import ReasoningTrigger

    source = inspect.getsource(ReasoningTrigger.notify_session_completed)
    assert "set_founder_rls_context(" in source
    # Ordering is the whole point: after the first query it is already too late.
    assert source.index("set_founder_rls_context(") < source.index("db.get(Founder")


def test_sweep_uses_admin_context_because_it_spans_founders():
    """The sweep must find orphaned sessions before it can know whose they are.
    Unscoped, RLS would hide every row and it would report a clean 'nothing
    pending' while founders sat without reports."""
    import inspect

    from app.api.v1.reasoning.trigger import reconcile_missing_reports

    source = inspect.getsource(reconcile_missing_reports)
    assert "set_admin_rls_context(" in source
    assert source.index("set_admin_rls_context(") < source.index(
        "find_sessions_missing_reports("
    )


def test_admin_rls_context_is_transaction_local():
    """`is_local = true` in set_config, so it dies with the transaction. A
    session-scoped admin flag would leak the bypass to whoever gets this pooled
    connection next."""
    import inspect

    from app.db.session import set_admin_rls_context

    source = inspect.getsource(set_admin_rls_context)
    assert "'app.current_admin', 'true', true" in source


def test_reasoning_trigger_satisfies_the_port():
    from app.api.v1.reasoning.trigger import ReasoningTrigger

    assert isinstance(ReasoningTrigger(), SessionCompletionNotifier)


def test_submit_answer_schedules_the_notifier_instead_of_calling_it():
    """The fix for the 203s request. The endpoint must hand the notifier to
    BackgroundTasks -- which runs after the response -- not invoke it inline."""
    import inspect

    from app.api.v1.diagnosis.router import submit_answer

    source = inspect.getsource(submit_answer)
    assert "background_tasks.add_task(" in source
    assert "BackgroundTasks" in str(inspect.signature(submit_answer))
    # The inline call is what made the request 203 seconds long.
    assert "completion_notifier.notify_session_completed(" not in source


def test_trigger_opens_its_own_session():
    """It can no longer borrow the request's -- that session is closed by the time
    a background task runs."""
    import inspect

    from app.api.v1.reasoning.trigger import ReasoningTrigger

    source = inspect.getsource(ReasoningTrigger.notify_session_completed)
    assert "SessionLocal()" in source
    assert "db.close()" in source, "a leaked session per diagnosis exhausts a pool of 5"


def test_trigger_is_sync_so_starlette_runs_it_off_the_event_loop():
    """Starlette routes sync background callables to a threadpool. Making this
    async would put a multi-minute blocking pipeline on the event loop and stall
    every other request in the process."""
    import inspect

    from app.api.v1.reasoning.trigger import ReasoningTrigger

    assert not inspect.iscoroutinefunction(ReasoningTrigger.notify_session_completed)


def test_reconciliation_sweep_is_exposed_and_fails_closed(client):
    """The durability guarantee: a background task dies with its container, so
    the sweep is what makes the outcome recoverable. Unauthenticated callers must
    never reach it."""
    response = client.post("/api/v1/internal/jobs/reconcile-reports")
    assert response.status_code == 401

    response = client.post(
        "/api/v1/internal/jobs/reconcile-reports",
        headers={"X-Internal-Secret": "not-the-secret"},
    )
    assert response.status_code == 401


def test_sweep_query_excludes_recent_and_reported_sessions():
    """Reads the emitted SQL rather than hitting a database: the two conditions
    that matter are the active-report exclusion (idempotency) and the age cutoff
    (which stops the sweep racing the background task it backs up)."""
    from app.api.v1.reasoning.trigger import find_sessions_missing_reports

    captured = {}

    class FakeDb:
        def execute(self, stmt):
            captured["sql"] = str(stmt)
            return SimpleNamespace(all=lambda: [])

    assert find_sessions_missing_reports(FakeDb(), older_than_minutes=15, limit=25) == []
    sql = captured["sql"].lower()
    assert "not in" in sql, "must exclude sessions that already have an active report"
    assert "completed_at" in sql, "must apply an age cutoff"
    assert "limit" in sql, "one sweep must be bounded"
