"""Deterministic AI-output quality metrics.

Each function is pure: it takes plain records (dicts) and returns a JSON-able
result. No DB, no LLM -- the harness supplies the data. This makes every metric
unit-testable with synthetic inputs and keeps the definitions auditable.

Records used (all optional keys tolerated):
  session: {routing_state, overall_confidence_score, distress_mode_triggered,
            session_state, status}
  detection: {session_id, is_top_finding}
  report:  {report_id, business_dna, founder_dna}
  pair (calibration): {confidence: 0-100, rating: 1-5}
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from statistics import mean, median
from typing import Any


def _num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def routing_distribution(sessions: Sequence[dict]) -> dict[str, Any]:
    """How completed sessions route (continue / validate / generate_report /
    distress_support). A healthy engine should not pile everything into one bucket."""
    counts = Counter(s["routing_state"] for s in sessions if s.get("routing_state"))
    total = sum(counts.values())
    return {
        "total": total,
        "counts": dict(counts),
        "pct": {k: round(v / total, 4) for k, v in counts.items()} if total else {},
    }


def confidence_stats(sessions: Sequence[dict]) -> dict[str, Any]:
    """Distribution of overall_confidence_score (0-100)."""
    vals = [_num(s.get("overall_confidence_score")) for s in sessions]
    vals = [v for v in vals if v is not None]
    if not vals:
        return {"n": 0}
    return {
        "n": len(vals),
        "mean": round(mean(vals), 2),
        "median": round(median(vals), 2),
        "min": min(vals),
        "max": max(vals),
        "below_60_pct": round(sum(1 for v in vals if v < 60) / len(vals), 4),
    }


def distress_stats(sessions: Sequence[dict]) -> dict[str, Any]:
    """How often distress mode / high-distress fired -- a safety signal, not a KPI."""
    n = len(sessions)
    triggered = sum(1 for s in sessions if s.get("distress_mode_triggered"))
    high = sum(1 for s in sessions if s.get("session_state") == "high_distress")
    return {
        "sessions": n,
        "distress_mode_triggered": triggered,
        "high_distress_state": high,
        "distress_rate": round(triggered / n, 4) if n else 0.0,
    }


def root_cause_stats(detections: Sequence[dict]) -> dict[str, Any]:
    """Detections per session + top-finding focus. The focusing rule should keep
    per-session detection counts bounded (the report flagged 35 -> <=8)."""
    by_session: dict[Any, list[dict]] = defaultdict(list)
    for d in detections:
        by_session[d.get("session_id")].append(d)
    if not by_session:
        return {"sessions": 0}
    per = [len(v) for v in by_session.values()]
    tops = [sum(1 for d in v if d.get("is_top_finding")) for v in by_session.values()]
    return {
        "sessions": len(by_session),
        "avg_detections": round(mean(per), 2),
        "max_detections": max(per),
        "avg_top_findings": round(mean(tops), 2),
    }


def business_health_stats(reports: Sequence[dict]) -> dict[str, Any]:
    """Distribution of the overall business-health score + red-flag frequency,
    read from each report's business_dna snapshot."""
    scores, redflag_reports, pillar_flags = [], 0, Counter()
    for r in reports:
        bd = r.get("business_dna")
        if not bd:
            continue
        s = _num(bd.get("overall_score"))
        if s is not None:
            scores.append(s)
        flags = bd.get("red_flags") or []
        if flags:
            redflag_reports += 1
            pillar_flags.update(flags)
    if not scores:
        return {"reports_with_business_dna": 0}
    return {
        "reports_with_business_dna": len(scores),
        "mean_overall": round(mean(scores), 2),
        "median_overall": round(median(scores), 2),
        "min": min(scores),
        "max": max(scores),
        "reports_with_red_flag": redflag_reports,
        "red_flags_by_pillar": dict(pillar_flags),
    }


def report_coverage(sessions: Sequence[dict], report_session_ids: Sequence[Any]) -> dict[str, Any]:
    """Of completed sessions, how many produced a report. The reasoning pipeline is
    best-effort, so a low ratio signals silent pipeline failures."""
    completed = [s for s in sessions if s.get("status") == "completed"]
    have = set(report_session_ids)
    covered = sum(1 for s in completed if s.get("session_id") in have)
    n = len(completed)
    return {
        "completed_sessions": n,
        "with_report": covered,
        "coverage": round(covered / n, 4) if n else 0.0,
    }


def confidence_calibration(pairs: Sequence[dict]) -> dict[str, Any]:
    """Does higher engine confidence track higher founder satisfaction?

    `pairs` = report confidence (0-100) alongside the founder's report_rating (1-5).
    Reports mean rating for high (>=80) vs low (<60) confidence, and a simple
    Pearson correlation. A positive gap / correlation = the confidence score is
    meaningful; near-zero or negative = it is miscalibrated and worth recalibrating
    (feeds the Learning Engine)."""
    conf = [(_num(p.get("confidence")), _num(p.get("rating"))) for p in pairs]
    conf = [(c, r) for c, r in conf if c is not None and r is not None]
    n = len(conf)
    if n == 0:
        return {"n": 0}
    high = [r for c, r in conf if c >= 80]
    low = [r for c, r in conf if c < 60]
    result: dict[str, Any] = {
        "n": n,
        "mean_rating_high_conf": round(mean(high), 3) if high else None,
        "mean_rating_low_conf": round(mean(low), 3) if low else None,
    }
    if n >= 2:
        result["pearson"] = _pearson([c for c, _ in conf], [r for _, r in conf])
    return result


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    mx, my = mean(xs), mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return round(num / (dx * dy), 4)
