"""Learning Engine -- unit tests (pure, no DB)."""

from app.learning import LearningEngine, Severity, summarize_feedback


def _eval(**over):
    base = {
        "confidence_calibration": {"n": 10, "pearson": 0.6,
                                   "mean_rating_high_conf": 4.5, "mean_rating_low_conf": 1.5},
        "report_coverage": {"completed_sessions": 100, "coverage": 1.0},
        "routing_distribution": {"total": 100, "pct": {"validate": 0.4, "continue": 0.4, "generate_report": 0.2}},
        "distress": {"sessions": 100, "distress_mode_triggered": 0, "distress_rate": 0.0},
    }
    base.update(over)
    return base


def test_healthy_inputs_produce_no_actions():
    r = LearningEngine().analyze(_eval(), {"recommendation_helpful": {"total": 0}})
    assert r.has_actions is False


def test_confidence_miscalibration_flagged():
    r = LearningEngine().analyze(
        _eval(confidence_calibration={"n": 20, "pearson": 0.05,
                                      "mean_rating_high_conf": 2.0, "mean_rating_low_conf": 3.0}),
        {"recommendation_helpful": {"total": 0}},
    )
    codes = {s.code for s in r.signals}
    assert "confidence_miscalibrated" in codes
    sig = next(s for s in r.signals if s.code == "confidence_miscalibrated")
    assert sig.severity == Severity.ACTION and "CONFIDENCE_WEIGHT" in sig.target


def test_low_coverage_flagged_as_watch():
    r = LearningEngine().analyze(
        _eval(report_coverage={"completed_sessions": 50, "coverage": 0.5}),
        {"recommendation_helpful": {"total": 0}},
    )
    s = next(s for s in r.signals if s.code == "low_report_coverage")
    assert s.severity == Severity.WATCH


def test_unhelpful_recommendations_flagged():
    r = LearningEngine().analyze(
        _eval(), {"recommendation_helpful": {"total": 20, "helpful": 4, "helpful_rate": 0.2}},
    )
    assert any(s.code == "recommendations_unhelpful" and s.severity == Severity.ACTION for s in r.signals)


def test_routing_skew_flagged():
    r = LearningEngine().analyze(
        _eval(routing_distribution={"total": 100, "pct": {"continue": 0.95, "validate": 0.05}}),
        {"recommendation_helpful": {"total": 0}},
    )
    assert any(s.code == "routing_skew" for s in r.signals)


def test_distress_is_safety_not_auto_tuned():
    r = LearningEngine().analyze(
        _eval(distress={"sessions": 100, "distress_mode_triggered": 8, "distress_rate": 0.08}),
        {"recommendation_helpful": {"total": 0}},
    )
    s = next(s for s in r.signals if s.code == "distress_review")
    assert s.severity == Severity.SAFETY
    assert "Do NOT tune" in s.proposed_action
    assert r.by_severity(Severity.SAFETY)  # helper works


def test_summarize_feedback():
    rows = [
        {"feedback_type": "report_rating", "rating": 5},
        {"feedback_type": "report_rating", "rating": 3},
        {"feedback_type": "recommendation_helpful", "rating": 5},
        {"feedback_type": "recommendation_helpful", "rating": 2},
        {"feedback_type": "outcome_30day", "rating": None},
    ]
    s = summarize_feedback(rows)
    assert s["report_ratings"] == {"n": 2, "mean": 4.0}
    assert s["recommendation_helpful"]["helpful"] == 1        # only the rating>=4
    assert s["recommendation_helpful"]["helpful_rate"] == 0.5
    assert s["outcomes"]["total"] == 1
