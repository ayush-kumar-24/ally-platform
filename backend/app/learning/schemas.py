"""Typed outputs of the Learning Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    INFO = "info"        # observation, no action implied
    WATCH = "watch"      # monitor; act if it persists
    ACTION = "action"    # a concrete calibration/change is proposed (needs sign-off)
    SAFETY = "safety"    # wellbeing/safety issue -- highest priority


@dataclass(frozen=True)
class ImprovementSignal:
    """One thing the loop noticed and what it proposes -- advisory only."""

    code: str
    severity: Severity
    observation: str
    proposed_action: str
    # What/where a human would change (e.g. scoring_rules codes) + the numbers behind it.
    target: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LearningReport:
    """The loop's output for one analysis run: the signals + the inputs they came
    from (so a reviewer can trace every proposal back to its evidence)."""

    signals: tuple[ImprovementSignal, ...]
    metrics: dict[str, Any]     # the evaluation snapshot analysed
    feedback: dict[str, Any]    # the feedback summary analysed

    def by_severity(self, severity: Severity) -> tuple[ImprovementSignal, ...]:
        return tuple(s for s in self.signals if s.severity == severity)

    @property
    def has_actions(self) -> bool:
        return any(s.severity in (Severity.ACTION, Severity.SAFETY) for s in self.signals)

    def as_dict(self) -> dict[str, Any]:
        return {
            "signals": [
                {
                    "code": s.code, "severity": s.severity.value,
                    "observation": s.observation, "proposed_action": s.proposed_action,
                    "target": s.target, "evidence": s.evidence,
                }
                for s in self.signals
            ],
            "metrics": self.metrics,
            "feedback": self.feedback,
        }
