"""Founder feedback: validation, ownership, and not duplicating an opinion."""

import types

import pytest
from pydantic import ValidationError

from app.api.v1.feedback.schemas import FeedbackCreate


def _payload(**over):
    base = dict(feedback_type="general", rating=3)
    base.update(over)
    return base


# --- what the API will accept -----------------------------------------------

def test_rating_must_be_one_to_five():
    """Mirrors founder_feedback_rating_check, so a bad rating is a clean 422
    rather than an IntegrityError surfacing as a 500."""
    for bad in (0, 6, -1, 99):
        with pytest.raises(ValidationError):
            FeedbackCreate(**_payload(rating=bad))
    for good in (1, 2, 3, 4, 5):
        assert FeedbackCreate(**_payload(rating=good)).rating == good


def test_report_rating_requires_a_report():
    """A score with nothing attached tells you someone was unhappy but never
    what about."""
    with pytest.raises(ValidationError):
        FeedbackCreate(**_payload(feedback_type="report_rating"))
    ok = FeedbackCreate(**_payload(feedback_type="report_rating", report_id=41))
    assert ok.report_id == 41


def test_diagnosis_rating_requires_a_session():
    with pytest.raises(ValidationError):
        FeedbackCreate(**_payload(feedback_type="diagnosis_rating"))
    assert FeedbackCreate(**_payload(feedback_type="diagnosis_rating", session_id=55)).session_id == 55


def test_general_feedback_needs_no_target():
    assert FeedbackCreate(**_payload()).report_id is None


def test_unknown_feedback_type_is_rejected():
    """The outcome_* types exist in the table for the learning engine to write;
    a founder submitting one from a dialog is not a thing we support."""
    for bad in ("outcome_30day", "nps", "", "REPORT_RATING"):
        with pytest.raises(ValidationError):
            FeedbackCreate(**_payload(feedback_type=bad))


def test_comment_is_bounded():
    with pytest.raises(ValidationError):
        FeedbackCreate(**_payload(comment="x" * 2001))
    assert FeedbackCreate(**_payload(comment="  fine  ")).comment == "fine"


def test_extra_fields_are_refused():
    """extra='forbid' stops a client smuggling in founder_id and filing
    feedback as somebody else."""
    with pytest.raises(ValidationError):
        FeedbackCreate(**_payload(founder_id=1))


# --- ownership --------------------------------------------------------------

class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


def _db(found):
    return types.SimpleNamespace(execute=lambda *_a, **_k: _Result(found))


def test_rating_someone_elses_report_is_refused():
    """The foreign key only asks whether the row exists, not whose it is.
    Without this check a founder could file feedback against another founder's
    report, and a nonexistent id would 500 out of the FK violation."""
    from app.api.v1.feedback.service import UnknownFeedbackTargetError, _assert_target_is_theirs

    payload = FeedbackCreate(**_payload(feedback_type="report_rating", report_id=999))
    with pytest.raises(UnknownFeedbackTargetError):
        _assert_target_is_theirs(_db(None), founder_id=3705, payload=payload)


def test_rating_your_own_report_passes():
    from app.api.v1.feedback.service import _assert_target_is_theirs

    payload = FeedbackCreate(**_payload(feedback_type="report_rating", report_id=41))
    _assert_target_is_theirs(_db(41), founder_id=3705, payload=payload)   # no raise


def test_target_error_is_a_422_not_a_500():
    from app.api.v1.feedback.service import UnknownFeedbackTargetError

    assert UnknownFeedbackTargetError("report").status_code == 422


# --- dedupe policy ----------------------------------------------------------

def test_only_prompted_types_are_deduplicated():
    """Being asked twice about one report is nagging. Choosing to send feedback
    twice from the dashboard is not."""
    from app.api.v1.feedback.service import PROMPTED_TYPES

    assert "report_rating" in PROMPTED_TYPES
    assert "diagnosis_rating" in PROMPTED_TYPES
    assert "general" not in PROMPTED_TYPES
