"""Learning Engine -- the continuous-improvement loop.

Turns quality signals (the Evaluation Framework, `app/eval`) + real founder
feedback into structured **improvement signals** and calibration **proposals**.

Design principle: the loop *proposes*, humans *approve*, and only then are
`scoring_rules` / prompts changed. Nothing here mutates configuration -- weight
changes require sign-off (see docs/learning_engine.md). This module is the
deterministic analysis + structure; the review/apply stages are deliberately
out-of-band.
"""

from app.learning.engine import LearningEngine
from app.learning.feedback import summarize_feedback
from app.learning.schemas import ImprovementSignal, LearningReport, Severity

__all__ = [
    "LearningEngine",
    "summarize_feedback",
    "ImprovementSignal",
    "LearningReport",
    "Severity",
]
