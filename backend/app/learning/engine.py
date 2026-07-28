"""LearningEngine -- deterministic analysis stage of the improvement loop.

Given an evaluation snapshot (`app/eval`) and a founder-feedback summary, it emits
`ImprovementSignal`s: what looks off, and what calibration a human should consider.
It NEVER changes configuration -- proposals against `scoring_rules` / prompts go
through review + sign-off (the loop's apply stage is out-of-band). Thresholds are
constructor args so the sensitivity is tunable and testable.
"""

from __future__ import annotations

from app.learning.schemas import ImprovementSignal, LearningReport, Severity


class LearningEngine:
    def __init__(
        self,
        *,
        min_rated: int = 5,          # need this many rated reports before trusting calibration
        min_pearson: float = 0.3,    # confidence should positively track satisfaction
        min_coverage: float = 0.98,  # completed sessions should almost always produce a report
        min_helpful_rate: float = 0.5,
        routing_skew: float = 0.9,   # >90% of sessions in one routing state = skew
    ):
        self.min_rated = min_rated
        self.min_pearson = min_pearson
        self.min_coverage = min_coverage
        self.min_helpful_rate = min_helpful_rate
        self.routing_skew = routing_skew

    def analyze(self, eval_report: dict, feedback: dict) -> LearningReport:
        signals: list[ImprovementSignal] = []

        # 1. Confidence calibration -- the core learning signal.
        cal = eval_report.get("confidence_calibration", {})
        if cal.get("n", 0) >= self.min_rated:
            p = cal.get("pearson")
            hi, lo = cal.get("mean_rating_high_conf"), cal.get("mean_rating_low_conf")
            miscalibrated = (p is not None and p < self.min_pearson) or (
                hi is not None and lo is not None and hi <= lo
            )
            if miscalibrated:
                signals.append(ImprovementSignal(
                    code="confidence_miscalibrated", severity=Severity.ACTION,
                    observation=f"Engine confidence does not track founder satisfaction "
                                f"(pearson={p}, high-conf rating={hi}, low-conf rating={lo}).",
                    proposed_action="Recalibrate the confidence model weights and/or routing "
                                    "thresholds; re-run evaluation after each change.",
                    target="scoring_rules: CONFIDENCE_WEIGHT_* / CONFIDENCE_CONTINUE_MAX / "
                           "CONFIDENCE_VALIDATE_MIN / CONFIDENCE_VALIDATE_MAX",
                    evidence=cal,
                ))

        # 2. Report coverage -- silent pipeline failures.
        cov = eval_report.get("report_coverage", {})
        if cov.get("completed_sessions", 0) > 0 and cov.get("coverage", 1.0) < self.min_coverage:
            signals.append(ImprovementSignal(
                code="low_report_coverage", severity=Severity.WATCH,
                observation=f"Only {cov.get('coverage')} of completed sessions produced a report.",
                proposed_action="Investigate reasoning-pipeline failures (it is best-effort and "
                                "swallows errors); this is an ops fix, not a rule change.",
                target="reasoning pipeline (service/trigger), not scoring_rules",
                evidence=cov,
            ))

        # 3. Recommendation usefulness -> root-cause / intervention accuracy.
        rec = feedback.get("recommendation_helpful", {})
        if rec.get("total", 0) >= self.min_rated and (rec.get("helpful_rate") or 1.0) < self.min_helpful_rate:
            signals.append(ImprovementSignal(
                code="recommendations_unhelpful", severity=Severity.ACTION,
                observation=f"Founders marked only {rec.get('helpful_rate')} of recommendations helpful.",
                proposed_action="Review root-cause ranking weights and the intervention mapping "
                                "(primary vs secondary root_cause_ids).",
                target="scoring_rules: WEIGHT_* (ranking) + interventions mapping",
                evidence=rec,
            ))

        # 4. Routing skew -- everything in one bucket suggests threshold miscalibration.
        rd = eval_report.get("routing_distribution", {})
        pct = rd.get("pct") or {}
        if rd.get("total", 0) >= self.min_rated and pct:
            top_state, top_share = max(pct.items(), key=lambda kv: kv[1])
            if top_share >= self.routing_skew and top_state != "distress_support":
                signals.append(ImprovementSignal(
                    code="routing_skew", severity=Severity.WATCH,
                    observation=f"{round(top_share*100)}% of sessions route to '{top_state}'.",
                    proposed_action="Review the routing thresholds / minimum-question floor.",
                    target="scoring_rules: CONFIDENCE_* thresholds, CONFIDENCE_MIN_QUESTIONS_FLOOR",
                    evidence=rd,
                ))

        # 5. Distress safety -- wellbeing overrides everything. A high distress rate is
        #    surfaced for human review (never auto-tuned away).
        dist = eval_report.get("distress", {})
        if dist.get("sessions", 0) >= self.min_rated and dist.get("distress_rate", 0) > 0:
            signals.append(ImprovementSignal(
                code="distress_review", severity=Severity.SAFETY,
                observation=f"{dist.get('distress_mode_triggered')} distress-mode session(s) "
                            f"(rate {dist.get('distress_rate')}). Verify none were missed or mis-routed.",
                proposed_action="Human review of distress-flagged sessions; confirm no State-D signal "
                                "was routed to 'continue'. Do NOT tune distress thresholds to reduce the rate.",
                target="review only (session_state / distress detection), not a weight change",
                evidence=dist,
            ))

        return LearningReport(tuple(signals), metrics=eval_report, feedback=feedback)
