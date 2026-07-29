"""Evaluation Framework metrics -- unit tests with synthetic records (no DB)."""

from app.eval import metrics as M


SESSIONS = [
    {"session_id": 1, "routing_state": "generate_report", "overall_confidence_score": 82,
     "distress_mode_triggered": False, "session_state": "stable", "status": "completed"},
    {"session_id": 2, "routing_state": "continue", "overall_confidence_score": 40,
     "distress_mode_triggered": False, "session_state": "stable", "status": "completed"},
    {"session_id": 3, "routing_state": "distress_support", "overall_confidence_score": 55,
     "distress_mode_triggered": True, "session_state": "high_distress", "status": "completed"},
]


def test_routing_distribution():
    r = M.routing_distribution(SESSIONS)
    assert r["total"] == 3
    assert r["counts"]["generate_report"] == 1
    assert r["pct"]["continue"] == round(1 / 3, 4)


def test_confidence_stats():
    r = M.confidence_stats(SESSIONS)
    assert r["n"] == 3
    assert r["min"] == 40 and r["max"] == 82
    assert r["below_60_pct"] == round(2 / 3, 4)   # 40 and 55 are < 60


def test_confidence_stats_empty():
    assert M.confidence_stats([{"overall_confidence_score": None}])["n"] == 0


def test_distress_stats():
    r = M.distress_stats(SESSIONS)
    assert r["distress_mode_triggered"] == 1
    assert r["high_distress_state"] == 1
    assert r["distress_rate"] == round(1 / 3, 4)


def test_root_cause_stats():
    dets = [
        {"session_id": 1, "is_top_finding": True},
        {"session_id": 1, "is_top_finding": False},
        {"session_id": 2, "is_top_finding": True},
    ]
    r = M.root_cause_stats(dets)
    assert r["sessions"] == 2
    assert r["max_detections"] == 2
    assert r["avg_top_findings"] == 1.0


def test_business_health_stats():
    reports = [
        {"business_dna": {"overall_score": 80, "red_flags": []}},
        {"business_dna": {"overall_score": 40, "red_flags": ["Founder Readiness"]}},
        {"business_dna": None},
    ]
    r = M.business_health_stats(reports)
    assert r["reports_with_business_dna"] == 2
    assert r["mean_overall"] == 60.0
    assert r["reports_with_red_flag"] == 1
    assert r["red_flags_by_pillar"]["Founder Readiness"] == 1


def test_report_coverage():
    r = M.report_coverage(SESSIONS, report_session_ids=[1])
    assert r["completed_sessions"] == 3
    assert r["with_report"] == 1
    assert r["coverage"] == round(1 / 3, 4)


def test_confidence_calibration_positive():
    pairs = [
        {"confidence": 90, "rating": 5}, {"confidence": 85, "rating": 4},
        {"confidence": 40, "rating": 2}, {"confidence": 30, "rating": 1},
    ]
    r = M.confidence_calibration(pairs)
    assert r["n"] == 4
    assert r["mean_rating_high_conf"] == 4.5     # the two >=80
    assert r["mean_rating_low_conf"] == 1.5      # the two <60
    assert r["pearson"] is not None and r["pearson"] > 0.9


def test_confidence_calibration_empty():
    assert M.confidence_calibration([])["n"] == 0
