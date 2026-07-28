"""The strict report input payload -- assembled ENTIRELY from engine outputs.

Everything here was computed and persisted by the reasoning pipeline (founder_reports,
detected_root_causes, sessions.category_risk_scores, business_dna, founder_dna). The
narrative layer reads these facts; it never recomputes them. Any value that is
absent stays None and its section is later omitted -- never guessed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.repositories import intelligence_repository

# Stage onboarding_label -> report tone (prompt_library code + persona name).
_STAGE_TONE = {
    "Stage 0": ("PROMPT-STAGE0-TONE", "Validator"),
    "Stage 0→1": ("PROMPT-STAGE01-TONE", "Compass"),
    "Stage 1→10+": ("PROMPT-STAGE10PLUS-TONE", "Auditor"),
}


@dataclass(frozen=True)
class RootCauseFinding:
    root_cause_id: int
    name: str | None
    category: str | None
    confirmation_status: str | None   # confirmed / unconfirmed / not_tested
    is_top_finding: bool
    rank: int | None


@dataclass(frozen=True)
class PillarFinding:
    pillar_id: int
    name: str
    score: int | None
    band: str | None
    red_flag_triggered: bool
    red_flag_note: str | None


@dataclass(frozen=True)
class ArchetypeFinding:
    name: str | None
    code: str | None
    core_motivation: str | None
    is_confident: bool
    fit_score: float | None


@dataclass(frozen=True)
class ActionItem:
    intervention_id: int | None
    priority: int | None
    next_actions: tuple[str, ...]
    rationale: str | None


@dataclass(frozen=True)
class ReportPayload:
    report_id: int
    founder_id: int
    session_id: int
    founder_name: str | None
    tone_code: str | None
    tone_persona: str | None          # Validator / Compass / Auditor

    session_state: str | None         # session_state_at_generation
    distress_acknowledged_first: bool
    overall_confidence_score: float | None

    business_health_overall: int | None
    business_health_band: str | None
    pillars: tuple[PillarFinding, ...]
    red_flag_pillars: tuple[PillarFinding, ...]

    archetype: ArchetypeFinding | None
    top_root_causes: tuple[RootCauseFinding, ...]
    confirm_actions: tuple[ActionItem, ...]
    solve_actions: tuple[ActionItem, ...]

    # Sources for the variant decision (engine-owned).
    category_risk_scores: dict[str, Any] = field(default_factory=dict)
    cat_risk_threshold: float = 0.30
    generate_report_min: float = 80.0

    @property
    def psychology_flagged(self) -> bool:
        """Founder Psychology takes narrative precedence when the psychology
        category is flagged OR the Founder Readiness pillar red-flagged (Section H)."""
        cat = self._category_value("Founder Psychology")
        if cat is not None and cat >= self.cat_risk_threshold:
            return True
        return any(p.name == "Founder Readiness" and p.red_flag_triggered for p in self.pillars)

    @property
    def any_category_flagged(self) -> bool:
        return any(
            (self._to_float(v) or 0.0) >= self.cat_risk_threshold
            for v in self.category_risk_scores.values()
        )

    @property
    def top_sub_threshold_categories(self) -> list[tuple[str, float]]:
        """Highest 2-3 categories that are still below threshold -- 'areas to monitor'."""
        scored = [
            (k, self._to_float(v) or 0.0) for k, v in self.category_risk_scores.items()
        ]
        scored.sort(key=lambda kv: -kv[1])
        return scored[:3]

    def _category_value(self, name: str) -> float | None:
        return self._to_float(self.category_risk_scores.get(name))

    @staticmethod
    def _to_float(v) -> float | None:
        try:
            return float(v)
        except (TypeError, ValueError):
            return None


def _actions(raw) -> tuple[ActionItem, ...]:
    out: list[ActionItem] = []
    for a in raw or []:
        if not isinstance(a, dict):
            continue
        out.append(ActionItem(
            intervention_id=a.get("intervention_id"),
            priority=a.get("priority"),
            next_actions=tuple(a.get("next_actions") or ()),
            rationale=a.get("rationale"),
        ))
    return tuple(out)


def build_report_payload(db: Session, report) -> ReportPayload:
    """Assemble the strict payload for one founder_reports row. Read-only."""
    sess = db.execute(
        text("select category_risk_scores, session_state, overall_confidence_score, "
             "founder_stage_id from sessions where session_id = :sid"),
        {"sid": report.session_id},
    ).mappings().first() or {}

    stage_label = None
    if sess.get("founder_stage_id") is not None:
        stage_label = db.execute(
            text("select onboarding_label from founder_stages where stage_id = :s"),
            {"s": sess["founder_stage_id"]},
        ).scalar()
    tone_code, tone_persona = _STAGE_TONE.get(stage_label or "", (None, None))

    thresholds = dict(db.execute(text(
        "select rule_code, rule_value from scoring_rules where rule_code in "
        "('CAT_RISK_THRESHOLD','CONFIDENCE_GENERATE_REPORT_MIN') and is_active is true"
    )).all())

    founder_name = db.execute(
        text("select full_name from founders where founder_id = :f"),
        {"f": report.founder_id},
    ).scalar()

    # --- business health (from the persisted business_dna snapshot) ---
    bd = report.business_dna or {}
    pillars = tuple(
        PillarFinding(
            pillar_id=p.get("pillar_id"), name=p.get("pillar_name"),
            score=p.get("score"), band=p.get("band"),
            red_flag_triggered=bool(p.get("red_flag_triggered")),
            red_flag_note=p.get("red_flag_note"),
        )
        for p in (bd.get("pillars") or [])
    )
    red_flag_pillars = tuple(p for p in pillars if p.red_flag_triggered)

    # --- archetype (from founder_dna) ---
    archetype = None
    a = (report.founder_dna or {}).get("archetype")
    if a:
        archetype = ArchetypeFinding(
            name=a.get("archetype_name"), code=a.get("archetype_code"),
            core_motivation=a.get("core_motivation"),
            is_confident=bool(a.get("is_confident")), fit_score=a.get("fit_score"),
        )

    # --- top root causes (detected_root_causes + labels) ---
    rows = db.execute(
        text("select root_cause_id, confirmation_status, is_top_finding, rank "
             "from detected_root_causes where session_id = :sid and is_top_finding is true "
             "order by rank asc"),
        {"sid": report.session_id},
    ).mappings().all()
    labels = intelligence_repository.root_cause_labels(db, [r["root_cause_id"] for r in rows])
    top_root_causes = tuple(
        RootCauseFinding(
            root_cause_id=r["root_cause_id"],
            name=labels.get(r["root_cause_id"], (None, None))[0],
            category=labels.get(r["root_cause_id"], (None, None))[1],
            confirmation_status=r["confirmation_status"],
            is_top_finding=r["is_top_finding"], rank=r["rank"],
        )
        for r in rows
    )

    return ReportPayload(
        report_id=report.report_id, founder_id=report.founder_id,
        session_id=report.session_id, founder_name=founder_name,
        tone_code=tone_code, tone_persona=tone_persona,
        session_state=report.session_state_at_generation,
        distress_acknowledged_first=bool(report.distress_acknowledged_first),
        overall_confidence_score=(
            float(sess["overall_confidence_score"])
            if sess.get("overall_confidence_score") is not None else None
        ),
        business_health_overall=bd.get("overall_score"),
        business_health_band=bd.get("band"),
        pillars=pillars, red_flag_pillars=red_flag_pillars,
        archetype=archetype, top_root_causes=top_root_causes,
        confirm_actions=_actions(report.confirm_actions),
        solve_actions=_actions(report.solve_actions),
        category_risk_scores=dict(sess.get("category_risk_scores") or {}),
        cat_risk_threshold=float(thresholds.get("CAT_RISK_THRESHOLD", Decimal("0.30"))),
        generate_report_min=float(thresholds.get("CONFIDENCE_GENERATE_REPORT_MIN", Decimal("80"))),
    )
