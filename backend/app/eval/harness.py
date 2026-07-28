"""Evaluation harness -- pulls persisted engine outputs and runs the metrics.

Read-only. Assembles one report dict from the deterministic metrics in
`metrics.py`. Handles the current empty-data case gracefully (every metric returns
its zero/empty shape), so it can run in CI as a smoke check and against production
for a real quality snapshot.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.eval import metrics as M


class EvaluationHarness:
    def __init__(self, db: Session):
        self.db = db

    def _rows(self, sql: str) -> list[dict]:
        return [dict(r) for r in self.db.execute(text(sql)).mappings().all()]

    def run(self) -> dict:
        sessions = self._rows(
            "select session_id, routing_state, overall_confidence_score, "
            "distress_mode_triggered, session_state, status from sessions"
        )
        detections = self._rows(
            "select session_id, is_top_finding from detected_root_causes"
        )
        reports = self._rows(
            "select report_id, session_id, business_dna from founder_reports where is_active is true"
        )
        # Calibration: the founder's report_rating against the session's confidence
        # (confidence lives on sessions; the report links them).
        pairs = self._rows(
            "select s.overall_confidence_score as confidence, f.rating as rating "
            "from founder_feedback f "
            "join founder_reports r on r.report_id = f.report_id "
            "join sessions s on s.session_id = r.session_id "
            "where f.feedback_type = 'report_rating' and f.rating is not null "
            "and s.overall_confidence_score is not null"
        )

        return {
            "sample": {
                "sessions": len(sessions),
                "detections": len(detections),
                "active_reports": len(reports),
                "rated_reports": len(pairs),
            },
            "routing_distribution": M.routing_distribution(sessions),
            "confidence": M.confidence_stats(sessions),
            "distress": M.distress_stats(sessions),
            "root_causes": M.root_cause_stats(detections),
            "business_health": M.business_health_stats(reports),
            "report_coverage": M.report_coverage(
                sessions, [r["session_id"] for r in reports]
            ),
            "confidence_calibration": M.confidence_calibration(pairs),
        }
