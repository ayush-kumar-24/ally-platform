"""The lifetime cap on completing a diagnosis.

Diagnosis is deliberately unmetered by tokens -- a founder must never hit a wall
partway through an assessment -- which leaves the number of runs as the only
thing bounding what it costs (~24,400 tokens each). Free is capped at one
diagnosis for the LIFETIME of the account, counted by completion, not by month:
these cover that bound.

The service is built with object.__new__ and a fake repository: the check is pure
logic over a count and a plan, and standing up a real DiagnosisService would drag
in a database session, the question engine and the advisor to test none of them.
"""

from types import SimpleNamespace

import pytest

from app.api.v1.diagnosis.service import DiagnosisService
from app.plans.errors import DiagnosisAlreadyCompletedError


class FakeRepo:
    def __init__(self, count: int = 0, raises: Exception | None = None):
        self.count = count
        self.raises = raises

    def count_completed_sessions(self, founder_id: int) -> int:
        if self.raises is not None:
            raise self.raises
        return self.count


def _service(count: int = 0, raises: Exception | None = None) -> DiagnosisService:
    service = object.__new__(DiagnosisService)
    service.repository = FakeRepo(count, raises)
    return service


def _founder(plan_type: str = "free"):
    return SimpleNamespace(founder_id=1, plan_type=plan_type)


def test_a_founder_who_has_never_completed_one_is_allowed():
    _service(count=0)._check_diagnosis_allowance(_founder())


def test_a_founder_who_has_completed_one_is_refused():
    with pytest.raises(DiagnosisAlreadyCompletedError) as exc:
        _service(count=1)._check_diagnosis_allowance(_founder())
    assert exc.value.status_code == 429
    assert exc.value.used == 1 and exc.value.limit == 1


def test_there_is_no_reset_date():
    """Unlike the daily token ceiling, this cap never lifts on its own -- the
    error carries no resets_at, because there is nothing to wait out."""
    with pytest.raises(DiagnosisAlreadyCompletedError) as exc:
        _service(count=1)._check_diagnosis_allowance(_founder())
    assert not hasattr(exc.value, "resets_at")


def test_message_says_the_diagnosis_is_done_and_points_at_the_report():
    with pytest.raises(DiagnosisAlreadyCompletedError) as exc:
        _service(count=1)._check_diagnosis_allowance(_founder())
    # AppError keeps the text on .message and does not override __str__, so
    # str(exc) is the args tuple -- assert the field the API actually serialises.
    message = exc.value.message
    assert "completed" in message
    assert "report" in message


def test_a_broken_count_fails_open():
    """A cost control, not a security boundary. Refusing a founder their diagnosis
    because a lookup failed is worse than serving one extra."""
    _service(raises=RuntimeError("db down"))._check_diagnosis_allowance(_founder())


def test_an_unknown_plan_is_bounded_by_free():
    """get_plan falls back to Free for an unrecognised plan_type, by design: a
    typo in the database must grant the least, never the most. So an unknown tier
    is still bounded rather than waved through -- the opposite of the broken-count
    case above, and deliberately so. A lookup that FAILED is an outage; a value we
    simply do not recognise is data we should not trust."""
    with pytest.raises(DiagnosisAlreadyCompletedError):
        _service(count=99)._check_diagnosis_allowance(_founder(plan_type="nonsense"))


@pytest.mark.parametrize("plan_type", ["free", "starter", "pro"])
def test_every_tier_is_bounded(plan_type):
    """No tier may complete diagnoses without limit -- each run is real money."""
    with pytest.raises(DiagnosisAlreadyCompletedError):
        _service(count=50)._check_diagnosis_allowance(_founder(plan_type))
