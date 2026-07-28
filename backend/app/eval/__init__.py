"""Evaluation Framework -- AI output quality metrics + tooling.

Pure metric functions (`metrics.py`) over the engine's persisted outputs, plus a
harness (`harness.py`) that pulls the data and assembles a report. Deterministic
and provider-free; the LLM-judged / golden-set metrics are a documented extension
(see docs/evaluation_framework.md).
"""

from app.eval.metrics import (
    business_health_stats,
    confidence_calibration,
    confidence_stats,
    distress_stats,
    report_coverage,
    root_cause_stats,
    routing_distribution,
)

__all__ = [
    "routing_distribution",
    "confidence_stats",
    "distress_stats",
    "root_cause_stats",
    "business_health_stats",
    "confidence_calibration",
    "report_coverage",
]
