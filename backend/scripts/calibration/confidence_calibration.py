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
    DEFAULT_MONITOR_MIN_COVERAGE,
    ConfidenceInputs,
    ConfidenceScoreWeights,
    monitor_eligible,
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
MIN_ANSWERS_FLOOR = 12

strategy = ConfidenceScoreStrategy(
    weights=WEIGHTS,
    stage_coherence_factor=D("1.0"),   # evidence agrees with the self-reported stage
    min_questions_floor=12,
    multi_category_flag_threshold=3,
    continue_max=D("60"),
    generate_report_min=GENERATE_REPORT_MIN,
)


def route(score, *, flagged, answered, budget):
    """Routing as the engine decides it, monitor route included."""
    if score >= GENERATE_REPORT_MIN:
        return "generate_report  -> can end"
    if monitor_eligible(
        any_category_flagged=flagged > 0,
        answered=answered,
        budget=budget,
        min_coverage=DEFAULT_MONITOR_MIN_COVERAGE,
        min_answers=MIN_ANSWERS_FLOOR,
    ):
        return "monitor          -> can end (all clear)"
    if score >= VALIDATE_MIN:
        return "validate         -> keeps asking"
    return "continue         -> keeps asking"


def profile(name, *, category_signal, confirmation, separation, flagged,
            answered=30, coverage=D("1.0"), budget=30):
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
    outcome = route(score, flagged=flagged, answered=answered, budget=budget)
    print(f"  {name:<34} score {str(score):>3}   {outcome}")
    return score


def run():
    print("=" * 78)
    print("CONFIDENCE BY FOUNDER HEALTH  (budget spent: 30 answers, coverage 1.0)")
    print("=" * 78)
    print(f"\n  Two ways to end: a score of {GENERATE_REPORT_MIN} (we found the problem), or the")
    print("  monitor route (we looked hard enough and there isn't one). Anything")
    print("  in between keeps asking until the question budget runs out.\n")

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
    print("WHY THE SCORE ALONE CANNOT END A HEALTHY SESSION")
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
    print(f"  Needed to generate a report:      {GENERATE_REPORT_MIN}")
    print(f"  Badly struggling founder scores:  {struggling}")
    print(f"""
  The number can never say "this founder is fine" -- and rule 4 caps an
  unflagged session at 59, so `validate` is unreachable too. Before the monitor
  route these founders answered every question in their budget and completed
  carrying `continue`, the state meaning KEEP ASKING, while a report was written
  off their highest sub-threshold category anyway.

  The monitor route reads the fact the score cannot carry: nothing was flagged.
  With coverage at {DEFAULT_MONITOR_MIN_COVERAGE} of the stage budget and no category above its
  risk threshold, the session ends as an all-clear instead of running out.
""")

    print("=" * 78)
    print("HOW EARLY A CLEAN SESSION CAN NOW STOP")
    print("=" * 78)
    print()
    for stage, budget in (("Ideation", 14), ("Validation", 20),
                          ("Prototype / MVP", 24), ("Growth / Scaling", 30)):
        needed = next(
            (n for n in range(1, budget + 1)
             if monitor_eligible(any_category_flagged=False, answered=n,
                                 budget=budget, min_coverage=DEFAULT_MONITOR_MIN_COVERAGE,
                                 min_answers=MIN_ANSWERS_FLOOR)),
            None,
        )
        saved = budget - needed if needed else 0
        print(f"  {stage:<20} budget {budget:>2}   all-clear at {needed:>2} "
              f"({saved} question{'' if saved == 1 else 's'} saved)")
    print(f"""
  Ideation is bound by the {MIN_ANSWERS_FLOOR}-answer floor rather than by coverage: below
  that the confidence score sits on too few signals to mean anything, and a
  clean answer does not change that.
""")


if __name__ == "__main__":
    run()
