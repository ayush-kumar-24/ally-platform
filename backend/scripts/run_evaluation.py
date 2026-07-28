"""Run the Evaluation Framework and print a quality snapshot (read-only).

    python scripts/run_evaluation.py

Prints a JSON report of AI-output quality metrics over the persisted engine
outputs. With no diagnosis data yet it prints the empty/zero baseline.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.eval.harness import EvaluationHarness


def main() -> int:
    db = SessionLocal()
    try:
        report = EvaluationHarness(db).run()
    finally:
        db.close()
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
