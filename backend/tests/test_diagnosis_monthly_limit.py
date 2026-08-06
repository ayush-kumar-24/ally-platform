"""The per-month cap on starting a diagnosis.

Diagnosis is deliberately unmetered by tokens -- a founder must never hit a wall
partway through an assessment -- which leaves the number of runs as the only
thing bounding what it costs (~24,400 tokens each). These cover that bound.

The service is built with object.__new__ and a fake repository: the check is pure
logic over a count and a plan, and standing up a real DiagnosisService would drag
in a database session, the question engine and the advisor to test none of them.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1.diagnosis.service import DiagnosisService
from app.plans.errors import MonthlyDiagnosisLimitError


class FakeRepo:
    def __init__(self, count: int = 0, raises: Exception | None = None):
        self.count = count
        self.raises = raises
        self.asked_since: datetime | None = None

    def count_sessions_started_since(self, founder_id: int, since: datetime) -> int:
        if self.raises is not None:
            raise self.raises
        self.asked_since = since
        return self.count


def _service(count: int = 0, raises: Exception | None = None) -> DiagnosisService:
    service = object.__new__(DiagnosisService)
    service.repository = FakeRepo(count, raises)
    return service


def _founder(plan_type: str = "free"):
    return SimpleNamespace(founder_id=1, plan_type=plan_type)


def test_first_diagnosis_of_the_month_is_allowed():
    _service(count=0)._check_monthly_diagnosis_limit(_founder())


def test_second_diagnosis_in_the_same_month_is_refused():
    with pytest.raises(MonthlyDiagnosisLimitError) as exc:
        _service(count=1)._check_monthly_diagnosis_limit(_founder())
    assert exc.value.status_code == 429
    assert exc.value.used == 1 and exc.value.limit == 1


def test_the_window_is_the_calendar_month():
    """'Available from 1 September' is predictable; a rolling 30 days is not."""
    service = _service(count=0)
    service._check_monthly_diagnosis_limit(_founder())
    since = service.repository.asked_since
    assert since.day == 1
    assert (since.hour, since.minute, since.second, since.microsecond) == (0, 0, 0, 0)
    assert since.tzinfo is not None, "must be timezone-aware or the month boundary drifts"


def test_reset_date_is_the_first_of_next_month():
    with pytest.raises(MonthlyDiagnosisLimitError) as exc:
        _service(count=1)._check_monthly_diagnosis_limit(_founder())
    resets = exc.value.resets_at
    now = datetime.now(timezone.utc)
    assert resets.day == 1
    assert resets > now
    # December must roll to January, not to month 13.
    assert 1 <= resets.month <= 12


def test_message_names_the_limit_and_when_it_lifts():
    with pytest.raises(MonthlyDiagnosisLimitError) as exc:
        _service(count=1)._check_monthly_diagnosis_limit(_founder())
    # AppError keeps the text on .message and does not override __str__, so
    # str(exc) is the args tuple -- assert the field the API actually serialises.
    message = exc.value.message
    assert "diagnosis" in message           # singular when the limit is 1
    assert "diagnoses" not in message
    assert "available from" in message


def test_a_broken_count_fails_open():
    """A cost control, not a security boundary. Refusing a founder their diagnosis
    because a lookup failed is worse than serving one extra."""
    _service(raises=RuntimeError("db down"))._check_monthly_diagnosis_limit(_founder())


def test_an_unknown_plan_is_bounded_by_free():
    """get_plan falls back to Free for an unrecognised plan_type, by design: a
    typo in the database must grant the least, never the most. So an unknown tier
    is still bounded rather than waved through -- the opposite of the broken-count
    case above, and deliberately so. A lookup that FAILED is an outage; a value we
    simply do not recognise is data we should not trust."""
    with pytest.raises(MonthlyDiagnosisLimitError):
        _service(count=99)._check_monthly_diagnosis_limit(_founder(plan_type="nonsense"))


@pytest.mark.parametrize("plan_type", ["free", "starter", "pro"])
def test_every_tier_is_bounded(plan_type):
    """No tier may start diagnoses without limit -- each run is real money."""
    with pytest.raises(MonthlyDiagnosisLimitError):
        _service(count=50)._check_monthly_diagnosis_limit(_founder(plan_type))
