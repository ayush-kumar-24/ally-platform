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

# Dimension codes the Founder DNA phase writes as LISTS of answer text.
#
# Three of the fourteen asked dimensions are deliberately NOT here, because
# the `founder_dna` jsonb already has an owner for those keys:
#   * archetype -- archetype.py writes a DICT there (name/code/motivation).
#     The archetype questions exist to give that engine the founder's own
#     language to infer from, not to render a card of their own.
#   * origin, vision -- also onboarding free text, and read as single
#     strings by founder_origin / founder_vision below.
# resolve_phase2_dimensions() enforces the same split at the write end.
_PHASE2_DIMENSION_CODES = frozenset({
    "purpose_mission", "core_values", "mindset_excellence",
    "energy_patterns", "decision_style", "focus_attention",
    "core_motivation", "strengths_blind_spots", "stress_response",
    "communication_preference", "emotional_intelligence",
})

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
    score: int | None                 # engine-internal: NOT exposed in the report
    band: str | None                  # score_bands level (shown)
    red_flag_triggered: bool
    red_flag_note: str | None
    band_description: str | None = None  # score_bands description for `band` (shown)


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

    # Chronic-state adjustment (chronic_state_inference). The engine detects the
    # chronic state; the report applies its recommended_report_adjustment. The
    # adjustment text is GUIDANCE for the narrator -- it is never rendered.
    chronic_state: str | None = None
    chronic_adjustment: str | None = None
    separate_identity: bool = False

    # Founder DNA dimensions beyond archetype -- each absent (None/empty) rather
    # than guessed when `founder_reports.founder_dna` has no key for it. Origin
    # and vision are the founder's own onboarding text passed through close to
    # verbatim; the other three are catalogue findings (blind_spots /
    # behaviour_patterns) resolved by detected root cause. Defaulted (unlike
    # `archetype` above) since every existing caller/test predates these and
    # most sessions today have none of them yet.
    founder_origin: str | None = None
    founder_vision: str | None = None
    strengths_blind_spots: tuple[str, ...] = ()
    stress_response: tuple[str, ...] = ()
    communication_preference: tuple[str, ...] = ()
    # The 6 phase-2 Founder DNA dimensions (purpose_mission, core_values,
    # mindset_excellence, energy_patterns, decision_style, focus_attention),
    # keyed by dimension_code -- a dict rather than 6 more named fields like
    # the ones above, since these came from a single generic engine
    # (app/api/v1/founder_dna/) rather than 6 separately-built ones; adding a
    # 7th dimension later needs no change here, matching the same
    # no-rigid-schema choice already made for that engine.
    phase2_dimensions: dict[str, tuple[str, ...]] = field(default_factory=dict)

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
    # score_bands are the spec-owned band label + written description per pillar.
    # We surface the band + its paragraph and keep the raw number internal, so the
    # report never reduces a founder to a grade (readiness_pillars.score_bands).
    band_desc: dict[tuple, str] = {}
    for row in db.execute(text("select pillar_id, score_bands from readiness_pillars")).mappings():
        for b in (row["score_bands"] or []):
            band_desc[(row["pillar_id"], b.get("level"))] = b.get("description")
    pillars = tuple(
        PillarFinding(
            pillar_id=p.get("pillar_id"), name=p.get("pillar_name"),
            score=p.get("score"), band=p.get("band"),
            band_description=band_desc.get((p.get("pillar_id"), p.get("band"))),
            red_flag_triggered=bool(p.get("red_flag_triggered")),
            red_flag_note=p.get("red_flag_note"),
        )
        for p in (bd.get("pillars") or [])
    )
    red_flag_pillars = tuple(p for p in pillars if p.red_flag_triggered)

    # --- chronic state (engine writes it onto founder_dna; report applies it) ---
    # Detection of the chronic state is the psychological engine's job; the report
    # only CONSUMES it. recommended_report_adjustment steers the narrator and is never
    # printed. Identity Fusion additionally turns on the separation language.
    chronic_state = (report.founder_dna or {}).get("chronic_state")
    chronic_adjustment = None
    separate_identity = False
    if chronic_state:
        chronic_adjustment = db.execute(
            text("select recommended_report_adjustment from chronic_state_inference "
                 "where chronic_state = :c"),
            {"c": chronic_state},
        ).scalar()
        separate_identity = chronic_state.startswith("Identity Fusion")

    # --- archetype + the newer Founder DNA dimensions (all from founder_dna) ---
    fd = report.founder_dna or {}
    archetype = None
    a = fd.get("archetype")
    if a:
        archetype = ArchetypeFinding(
            name=a.get("archetype_name"), code=a.get("archetype_code"),
            core_motivation=a.get("core_motivation"),
            is_confident=bool(a.get("is_confident")), fit_score=a.get("fit_score"),
        )
    founder_origin = (fd.get("origin") or "").strip() or None
    founder_vision = (fd.get("vision") or "").strip() or None
    strengths_blind_spots = tuple(fd.get("strengths_blind_spots") or ())
    stress_response = tuple(fd.get("stress_response") or ())
    communication_preference = tuple(fd.get("communication_preference") or ())
    phase2_dimensions = {
        code: tuple(values)
        for code, values in fd.items()
        if code in _PHASE2_DIMENSION_CODES and values
    }

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
        archetype=archetype,
        founder_origin=founder_origin, founder_vision=founder_vision,
        strengths_blind_spots=strengths_blind_spots, stress_response=stress_response,
        communication_preference=communication_preference,
        phase2_dimensions=phase2_dimensions,
        top_root_causes=top_root_causes,
        confirm_actions=_actions(report.confirm_actions),
        solve_actions=_actions(report.solve_actions),
        category_risk_scores=dict(sess.get("category_risk_scores") or {}),
        cat_risk_threshold=float(thresholds.get("CAT_RISK_THRESHOLD", Decimal("0.30"))),
        generate_report_min=float(thresholds.get("CONFIDENCE_GENERATE_REPORT_MIN", Decimal("80"))),
        chronic_state=chronic_state, chronic_adjustment=chronic_adjustment,
        separate_identity=separate_identity,
    )
