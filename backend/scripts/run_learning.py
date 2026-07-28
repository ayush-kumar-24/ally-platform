"""Run the Learning Engine and print improvement signals (read-only).

    python scripts/run_learning.py

Runs the Evaluation harness + founder-feedback summary, then the Learning Engine's
analysis. Emits proposals only -- it never changes configuration.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.db.session import SessionLocal
from app.eval.harness import EvaluationHarness
from app.learning import LearningEngine, summarize_feedback


def main() -> int:
    db = SessionLocal()
    try:
        eval_report = EvaluationHarness(db).run()
        rows = [
            dict(r) for r in db.execute(
                text("select feedback_type, rating, outcome_metrics from founder_feedback")
            ).mappings().all()
        ]
    finally:
        db.close()
    feedback = summarize_feedback(rows)
    report = LearningEngine().analyze(eval_report, feedback)
    print(json.dumps(report.as_dict(), indent=2, default=str))
    print(f"\n{len(report.signals)} signal(s); actionable: {report.has_actions}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
