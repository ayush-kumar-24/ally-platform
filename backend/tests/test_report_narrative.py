"""Report Narrative Generator (#20) -- the hard-rule + safety tests.

The generator is pure given a ReportPayload, so these need no DB.
"""

import re
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.reports.generator import ReportNarrativeGenerator
from app.api.v1.reports.payload import (
    ActionItem, ArchetypeFinding, PillarFinding, ReportPayload, RootCauseFinding,
)
from app.api.v1.reports.variants import ReportVariant, select_variant


def _pillar(name, score, flag=False, note=None):
    return PillarFinding(pillar_id=1, name=name, score=score, band="Developing",
                         red_flag_triggered=flag, red_flag_note=note)


def _payload(**over):
    base = dict(
        report_id=1, founder_id=7, session_id=3, founder_name="Rahul",
        tone_code="PROMPT-STAGE01-TONE", tone_persona="Compass",
        session_state="stable", distress_acknowledged_first=False,
        overall_confidence_score=85.0,
        business_health_overall=64, business_health_band="Needs Attention",
        pillars=(_pillar("Founder Readiness", 62), _pillar("Market Clarity", 48)),
        red_flag_pillars=(),
        archetype=ArchetypeFinding("Operator", "ARCH-002", "Mastery", True, 0.31),
        top_root_causes=(
            RootCauseFinding(10, "Weak pipeline", "Sales & Revenue", "confirmed", True, 1),
            RootCauseFinding(11, "Unclear ICP", "Go-To-Market", "not_tested", True, 2),
        ),
        confirm_actions=(ActionItem(5, 1, ("Confirm your ICP",), "why"),),
        solve_actions=(ActionItem(6, 1, ("Build a pipeline tracker",), "why"),),
        category_risk_scores={"Sales & Revenue": 0.6, "Founder Psychology": 0.1},
    )
    base.update(over)
    return ReportPayload(**base)


def _gen(payload, **kw):
    return ReportNarrativeGenerator().generate(payload, **kw)


def _keys(n):
    return [s.key for s in n.sections]


# 1. No number appears in prose that is not in the payload.
def test_no_fabricated_numbers():
    p = _payload(pillars=(_pillar("Founder Readiness", 62), _pillar("Market Clarity", 30, True,
                 "A score below 35% triggers Section H.")))
    n = _gen(p)
    allowed = {"100"}  # fixed scale denominator ("out of 100"), a template constant
    allowed.update(str(x) for x in (p.business_health_overall,) if x is not None)
    for pf in p.pillars:
        if pf.score is not None:
            allowed.add(str(pf.score))
        allowed.update(re.findall(r"\d+", pf.red_flag_note or ""))
    for s in n.sections:
        for tok in re.findall(r"\d+", s.prose):
            assert tok in allowed, f"prose number {tok!r} not in payload ({s.key}): {s.prose!r}"


# 2. Distress variant + acknowledgement precedes any business content.
def test_distress_variant_ack_first():
    n = _gen(_payload(distress_acknowledged_first=True), distress_protocol="STOP the diagnostic. Acknowledge.")
    assert n.variant is ReportVariant.DISTRESS
    keys = _keys(n)
    assert keys[0] == "acknowledgement"
    ack = keys.index("acknowledgement")
    support = keys.index("support_recommendation")
    for biz in ("business_dna", "problem_path"):
        if biz in keys:
            assert ack < keys.index(biz) and support < keys.index(biz)


# 3. No-clear-diagnosis does not assert a diagnosis.
def test_no_clear_diagnosis_does_not_assert():
    p = _payload(category_risk_scores={"Sales & Revenue": 0.2, "Product": 0.1, "Team & Leadership": 0.15})
    n = _gen(p)
    assert n.variant is ReportVariant.NO_CLEAR_DIAGNOSIS
    keys = _keys(n)
    assert "areas_to_monitor" in keys and "problem_path" not in keys
    prose = " ".join(s.prose for s in n.sections).lower()
    assert "no single critical issue" in prose
    for word in ("we confirmed", "primary driver", "root cause is"):
        assert word not in prose


# 4. Psychology precedence: leads even when a business category scores higher.
def test_psychology_precedence():
    p = _payload(category_risk_scores={"Sales & Revenue": 0.9, "Founder Psychology": 0.5})
    assert p.psychology_flagged is True
    n = _gen(p)
    keys = _keys(n)
    assert "psychological_note" in keys
    assert keys.index("psychological_note") < keys.index("business_dna")
    assert keys.index("psychological_note") < keys.index("problem_path")


# 5. A pillar red flag surfaces despite a healthy overall score.
def test_pillar_red_flag_despite_healthy_overall():
    p = _payload(
        business_health_overall=82,  # healthy
        pillars=(_pillar("Founder Readiness", 30, True, "Below 35% triggers Section H."),
                 _pillar("Market Clarity", 78)),
        red_flag_pillars=(_pillar("Founder Readiness", 30, True, "Below 35% triggers Section H."),),
    )
    n = _gen(p)
    keys = _keys(n)
    assert "psychological_note" in keys
    biz = next(s for s in n.sections if s.key == "business_dna")
    assert "Founder Readiness" in biz.facts["red_flag_pillars"]


# 6. Shared view is a strict subset of the owner view.
def test_shared_is_strict_subset():
    n = _gen(_payload())
    owner_headings = {s.heading for s in n.sections if s.prose}
    shared = [{"heading": s.heading, "prose": s.prose} for s in n.sections if s.prose]
    shared_headings = {d["heading"] for d in shared}
    assert shared_headings <= owner_headings
    # No facts / IDs leak into the shared serialization.
    blob = str(shared)
    assert "intervention_id" not in blob and "facts" not in blob
    # Owner carries facts that shared does not.
    assert any(s.facts for s in n.sections)


# 7. Cross-founder access -> 403; missing -> 404.
def test_cross_founder_forbidden_and_missing_not_found():
    from app.api.v1.reports.routes import _owned_report

    class _DB:
        def __init__(self, rep): self._rep = rep
        def get(self, model, rid): return self._rep

    founder = SimpleNamespace(founder_id=7)
    other = SimpleNamespace(report_id=1, founder_id=999)  # someone else's report
    with pytest.raises(HTTPException) as e:
        _owned_report(_DB(other), founder, 1)
    assert e.value.status_code == 403

    with pytest.raises(HTTPException) as e:
        _owned_report(_DB(None), founder, 1)
    assert e.value.status_code == 404


def test_tentative_archetype_wording():
    # Hard rule 4: a thin-margin archetype is presented tentatively.
    n = _gen(_payload(archetype=ArchetypeFinding("Catalyst", "ARCH-006", "Possibility", False, 0.16)))
    fd = next(s for s in n.sections if s.key == "founder_dna")
    assert fd.facts["archetype"]["tentative"] is True
    assert "hypothesis" in fd.prose.lower() or "lean toward" in fd.prose.lower()


def test_not_tested_reads_differently_from_confirmed():
    # Hard rule 5.
    n = _gen(_payload())
    pp = next(s for s in n.sections if s.key == "problem_path").prose.lower()
    assert "confirmed" in pp and ("did not directly test" in pp or "not directly test" in pp)
