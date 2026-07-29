"""Template-variant selection.

These are different TEMPLATES, not different wording. Selection is deterministic
from the engine facts on the payload. Precedence (first match wins):

    DISTRESS  >  NO_CLEAR_DIAGNOSIS  >  LOW_CONFIDENCE  >  STANDARD

Distress is first because wellbeing overrides diagnostic completeness in all
cases. No-clear-diagnosis outranks low-confidence because both mean "do not
assert a diagnosis", and the no-diagnosis framing is the safer of the two.
"""

from __future__ import annotations

from enum import Enum

from app.api.v1.reports.payload import ReportPayload


class ReportVariant(str, Enum):
    STANDARD = "standard"
    DISTRESS = "distress"
    NO_CLEAR_DIAGNOSIS = "no_clear_diagnosis"
    LOW_CONFIDENCE = "low_confidence"


def select_variant(payload: ReportPayload) -> ReportVariant:
    # B. DISTRESS -- distress acknowledged first, or generated in High Distress.
    if payload.distress_acknowledged_first or payload.session_state == "high_distress":
        return ReportVariant.DISTRESS

    # C. NO CLEAR DIAGNOSIS -- all 8 categories below CAT_RISK_THRESHOLD. Only
    # decidable when we actually have category scores; otherwise fall through.
    if payload.category_risk_scores and not payload.any_category_flagged:
        return ReportVariant.NO_CLEAR_DIAGNOSIS

    # D. LOW CONFIDENCE -- generated below the generate_report threshold.
    if (
        payload.overall_confidence_score is not None
        and payload.overall_confidence_score < payload.generate_report_min
    ):
        return ReportVariant.LOW_CONFIDENCE

    # A. STANDARD.
    return ReportVariant.STANDARD
