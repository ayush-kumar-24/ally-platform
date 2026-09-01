"""Does session length actually vary with how healthy the founder is?

Runs the real `ConfidenceScoreStrategy` with the weights and routing thresholds
that are live in `scoring_rules`, across founder profiles from perfectly healthy
to badly struggling.

Confidence is what ends a diagnosis early -- a session can only stop before its
question budget runs out once the score reaches CONFIDENCE_GENERATE_REPORT_MIN.
So this is really a measurement of how long each kind of founder is kept talking.

Run:
    DATABASE_URL=postgresql+psycopg://u:p@127.0.0.1:5432/none \
    SECRET_KEY=calibration \
    python backend/scripts/calibration/confidence_calibration.py

Neither env var is connected to -- they only satisfy Settings at import. The
weights below are copied from scoring_rules; re-check them against the database
if this script ever disagrees with a live session.
"""
import os
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:5432/none")
os.environ.setdefault("SECRET_KEY", "calibration-only-not-a-real-secret")

from app.api.v1.reasoning.config import (  # noqa: E402
    ConfidenceInputs,
    ConfidenceScoreWeights,
)
from app.api.v1.reasoning.engines.confidence_score import (  # noqa: E402
    ConfidenceScoreStrategy,
)

D = Decimal

# --- verbatim from scoring_rules ---
WEIGHTS = ConfidenceScoreWeights(
    category_signal=D("0.30"), coverage=D("0.25"), consistency=D("0.20"),
    confirmation=D("0.15"), separation=D("0.10"),
)
VALIDATE_MIN = D("60")
GENERATE_REPORT_MIN = D("80")

strategy = ConfidenceScoreStrategy(
    weights=WEIGHTS,
    stage_coherence_factor=D("1.0"),   # evidence agrees with the self-reported stage
    min_questions_floor=12,
    multi_category_flag_threshold=3,
    continue_max=D("60"),
    generate_report_min=GENERATE_REPORT_MIN,
)


def route(score):
    if score >= GENERATE_REPORT_MIN:
        return "generate_report  -> can end early"
    if score >= VALIDATE_MIN:
        return "validate         -> keeps asking"
    return "continue         -> keeps asking"


def profile(name, *, category_signal, confirmation, separation, flagged,
            answered=30, coverage=D("1.0")):
    """Score one founder profile at a fully-spent question budget."""
    score = strategy.compute(ConfidenceInputs(
        category_signal=category_signal,
        evidence_coverage=coverage,
        confirmation_ratio=confirmation,
        separation=separation,
        consistency_available=True,
        consistency_score=D("1.0"),      # no contradictions in any profile
        reliability_factor=D("1.0"),
        questions_answered=answered,
        flagged_category_count=flagged,
        any_category_flagged=flagged > 0,
        distress_override=False,
        stages_away=0,
    ))
    print(f"  {name:<34} score {str(score):>3}   {route(score)}")
    return score


def run():
    print("=" * 78)
    print("CONFIDENCE BY FOUNDER HEALTH  (budget spent: 30 answers, coverage 1.0)")
    print("=" * 78)
    print("\n  A session can only END EARLY at a score of "
          f"{GENERATE_REPORT_MIN}. Below that it keeps")
    print("  asking until the question budget runs out.\n")

    healthy = profile("Perfectly healthy (all green)",
                      category_signal=D("0"), confirmation=D("0"),
                      separation=D("0"), flagged=0)
    profile("Mostly healthy (one soft spot)",
            category_signal=D("0.25"), confirmation=D("0.25"),
            separation=D("0.30"), flagged=0)
    profile("Mixed (two categories flagged)",
            category_signal=D("0.55"), confirmation=D("0.50"),
            separation=D("0.50"), flagged=2)
    profile("Struggling (clear single cause)",
            category_signal=D("0.85"), confirmation=D("0.75"),
            separation=D("0.70"), flagged=3)
    struggling = profile("Badly struggling (all red)",
                         category_signal=D("1.0"), confirmation=D("1.0"),
                         separation=D("0.90"), flagged=5)

    print("\n" + "=" * 78)
    print("WHY A HEALTHY FOUNDER CANNOT FINISH EARLY")
    print("=" * 78)
    print("""
  A green answer contributes nothing to three of the five signals:

    category_signal (0.30)  measures RISK     -> 0 when nothing is wrong
    confirmation    (0.15)  confirms a CAUSE  -> 0 when none was detected
    separation      (0.10)  ranks CAUSES      -> 0 when there are none

  Only coverage (0.25) and consistency (0.20) can rise for a healthy founder,
  and both cap at 1.0, so the arithmetic ceiling is 0.45 -> 45 / 100.
""")
    print(f"  Healthy founder ceiling:          {healthy}")
    print(f"  Needed to end a session:          {GENERATE_REPORT_MIN}")
    print(f"  Badly struggling founder scores:  {struggling}")
    print("""
  So session length is already variable -- but inverted. A struggling founder
  reaches the threshold and can stop; a healthy one never can, and is asked the
  maximum number of questions the budget allows.
""")


if __name__ == "__main__":
    run()
