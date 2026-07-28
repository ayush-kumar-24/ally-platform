"""Deterministic aggregation of founder_feedback into a summary the loop reads.

Pure function: rows in -> summary dict out. Rows are `founder_feedback` records
with at least `feedback_type`, `rating`, `outcome_metrics`.
"""

from __future__ import annotations

from collections.abc import Sequence
from statistics import mean
from typing import Any


def summarize_feedback(rows: Sequence[dict]) -> dict[str, Any]:
    ratings = [r["rating"] for r in rows
               if r.get("feedback_type") == "report_rating" and r.get("rating") is not None]
    helpful = [r for r in rows if r.get("feedback_type") == "recommendation_helpful"]
    # `recommendation_helpful` convention: rating >= 4 (of 5) counts as "helpful".
    helpful_yes = sum(1 for r in helpful if (r.get("rating") or 0) >= 4)

    outcome_types = ("outcome_30day", "outcome_60day", "outcome_90day")
    outcomes = [r for r in rows if r.get("feedback_type") in outcome_types]

    return {
        "report_ratings": {
            "n": len(ratings),
            "mean": round(mean(ratings), 3) if ratings else None,
        },
        "recommendation_helpful": {
            "total": len(helpful),
            "helpful": helpful_yes,
            "helpful_rate": round(helpful_yes / len(helpful), 4) if helpful else None,
        },
        "outcomes": {"total": len(outcomes)},
    }
