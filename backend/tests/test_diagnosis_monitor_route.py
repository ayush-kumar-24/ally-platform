"""The monitor route: how a healthy founder finishes a diagnosis.

Before this existed they could not. Three of the five confidence signals measure
pathology -- category risk, confirmation of a detected cause, separation between
competing causes -- so all three read 0 when nothing is wrong. Only coverage
(0.25) and consistency (0.20) can rise, which caps a perfectly healthy founder
at 45 against a report threshold of 80; CONFIDENCE_HARD_RULES rule 4 then caps
an unflagged session at 59, so `validate` is out of reach too. They answered
every question in their budget and completed carrying `continue` -- the state
that means keep asking -- while a report got written off their highest
sub-threshold category anyway.

`monitor` is the missing stopping point, and the other half of
NO_CATEGORY_ABOVE_THRESHOLD_ACTION.
"""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.api.v1.diagnosis import incremental_confidence as ic
from app.api.v1.diagnosis.service import DiagnosisService
from app.api.v1.reasoning.schemas import SessionAssessment
from app.models import RoutingState, SessionStatus


# --- the healthy-stop predicate -------------------------------------------

def _assessment(*, flagged, score="45"):
    return SessionAssessment(
        score=Decimal(score), any_category_flagged=flagged, questions_answered=0,
    )


def _founder(budget=30):
    return SimpleNamespace(founder_id=1, stage=SimpleNamespace(question_budget=budget))


@pytest.fixture
def coverage_rule(monkeypatch):
    """Pin MONITOR_MIN_COVERAGE at 0.75 without a database."""
    monkeypatch.setattr(ic, "_monitor_min_coverage", lambda db: Decimal("0.75"))


def test_a_flagged_category_never_stops_early(coverage_rule):
    """Something IS wrong -- the diagnosis has a problem to pursue."""
    assert not ic._healthy_enough_to_stop(
        None, _assessment(flagged=True), answered=30, founder=_founder())


def test_a_clean_session_stops_once_coverage_is_met(coverage_rule):
    assert ic._healthy_enough_to_stop(
        None, _assessment(flagged=False), answered=23, founder=_founder(30))


def test_a_clean_session_keeps_going_below_coverage(coverage_rule):
    """22 of 30 is 73%, under the 75% bar -- not yet enough to call an all-clear."""
    assert not ic._healthy_enough_to_stop(
        None, _assessment(flagged=False), answered=22, founder=_founder(30))


def test_coverage_follows_the_stage_budget(coverage_rule):
    """An ideation founder's 75% is 11 questions, not 23."""
    assert ic._healthy_enough_to_stop(
        None, _assessment(flagged=False), answered=11, founder=_founder(14))
    assert not ic._healthy_enough_to_stop(
        None, _assessment(flagged=False), answered=10, founder=_founder(14))


def test_the_minimum_answer_floor_still_applies(coverage_rule):
    """A tiny budget must not let an all-clear be called after three questions.
    The floor that governs reports generally does not relax because the answers
    came back clean."""
    tiny = _founder(4)                       # 75% of 4 is 3
    assert ic.MIN_ANSWERS_BEFORE_COMPLETION > 3
    assert not ic._healthy_enough_to_stop(
        None, _assessment(flagged=False), answered=3, founder=tiny)


def test_an_unavailable_threshold_keeps_asking(monkeypatch):
    """Fails CLOSED, unlike the rest of this module. Asking a few more questions
    costs a founder time; a wrong all-clear tells them their business is fine
    when nobody checked."""
    def boom(db):
        raise RuntimeError("scoring_rules unreachable")
    monkeypatch.setattr(ic, "_monitor_min_coverage", boom)
    assert not ic._healthy_enough_to_stop(
        None, _assessment(flagged=False), answered=30, founder=_founder())


def test_the_default_coverage_is_stricter_than_the_report_threshold_floor():
    """An all-clear is a stronger claim than a diagnosis, so it takes more
    evidence -- not the bare minimum a report needs."""
    from app.api.v1.reasoning.config import DEFAULT_MONITOR_MIN_COVERAGE

    assert DEFAULT_MONITOR_MIN_COVERAGE >= Decimal("0.5")


def test_both_routing_paths_share_one_eligibility_rule():
    """The in-loop scorer ends the session; the pipeline then recomputes routing
    from the same low score moments later. Two copies of this condition would
    drift invisibly -- the session stopping correctly and being relabelled
    `continue` on the report."""
    import inspect

    from app.api.v1.reasoning import service as reasoning_service

    assert "monitor_eligible" in inspect.getsource(ic._healthy_enough_to_stop)
    assert "monitor_eligible" in inspect.getsource(
        reasoning_service.ReasoningService._monitor_eligible)


# --- routing ---------------------------------------------------------------

def test_monitor_is_a_distinct_routing_state():
    assert RoutingState.MONITOR.value == "monitor"
    assert RoutingState.MONITOR.value not in {
        RoutingState.CONTINUE.value,
        RoutingState.VALIDATE.value,
        RoutingState.GENERATE_REPORT.value,
    }


def test_distress_support_is_on_the_enum_now():
    """It was a loose string constant in reasoning.service while the DB CHECK
    already allowed it -- exactly how the enum and the constraint drifted."""
    from app.api.v1.reasoning.service import DISTRESS_SUPPORT_ROUTE

    assert DISTRESS_SUPPORT_ROUTE == RoutingState.DISTRESS_SUPPORT.value


# --- completion ------------------------------------------------------------

def _session(routing, answered=5):
    return SimpleNamespace(
        session_id=1, routing_state=routing, questions_answered_count=answered,
        current_question_id=99, current_category="Product",
        status=SessionStatus.IN_PROGRESS.value, completed_at=None,
    )


def _attach(session, question, founder):
    return DiagnosisService._attach_question(
        SimpleNamespace(), session, question, founder)


def test_monitor_completes_the_session():
    session = _session(RoutingState.MONITOR.value)
    _attach(session, SimpleNamespace(question_id=7, category="Product"), _founder())

    assert session.status == SessionStatus.COMPLETED.value
    assert session.current_question_id is None
    assert session.completed_at is not None


def test_monitor_survives_completion_rather_than_being_overwritten():
    """The state is the conclusion. Stamping `continue` over it would lose the
    only record that this founder was cleared rather than merely stopped."""
    session = _session(RoutingState.MONITOR.value)
    _attach(session, SimpleNamespace(question_id=7, category="Product"), _founder())
    assert session.routing_state == RoutingState.MONITOR.value


def test_continue_with_budget_left_keeps_asking():
    """The regression guard: an ordinary mid-session state must not complete."""
    session = _session(RoutingState.CONTINUE.value, answered=5)
    _attach(session, SimpleNamespace(question_id=7, category="Product"), _founder(30))

    assert session.status == SessionStatus.IN_PROGRESS.value
    assert session.current_question_id == 7


def test_generate_report_still_completes():
    session = _session(RoutingState.GENERATE_REPORT.value)
    _attach(session, SimpleNamespace(question_id=7, category="Product"), _founder())
    assert session.status == SessionStatus.COMPLETED.value
