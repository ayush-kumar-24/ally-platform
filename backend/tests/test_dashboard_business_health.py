"""Business-health persistence (business_dna serialisation) + dashboard schema.

`ReasoningService._business_dna` doesn't use `self`, so it's called unbound with
a dummy self -- no DB/engine construction needed.
"""

from decimal import Decimal

from types import SimpleNamespace

from app.api.v1.dashboard.service import business_health_from_report
from app.api.v1.reasoning.schemas import BusinessHealthScore, PillarScore
from app.api.v1.reasoning.service import ReasoningService


def _score() -> BusinessHealthScore:
    return BusinessHealthScore(
        overall_score=Decimal("64"),
        band="Needs Attention",
        pillars=(
            PillarScore(
                pillar_id=1, pillar_name="Founder Readiness", weight=Decimal("25.00"),
                score=Decimal("30"), band="Critical Gap", red_flag_triggered=True,
                red_flag_note="below threshold", assessed_question_count=5,
            ),
            PillarScore(
                pillar_id=2, pillar_name="Market Clarity", weight=Decimal("20.00"),
                score=None, band=None, red_flag_triggered=False,
                red_flag_note=None, assessed_question_count=0,
            ),
        ),
        red_flags=("Founder Readiness",),
    )


def test_business_dna_serialisation():
    dna = ReasoningService._business_dna(None, _score())
    assert dna["overall_score"] == 64
    assert dna["band"] == "Needs Attention"
    assert dna["red_flags"] == ["Founder Readiness"]
    assert len(dna["pillars"]) == 2

    p0 = dna["pillars"][0]
    assert p0["pillar_name"] == "Founder Readiness"
    assert p0["score"] == 30
    assert p0["weight"] == 25.0
    assert p0["red_flag_triggered"] is True
    assert dna["pillars"][1]["score"] is None            # unassessed pillar -> null


def test_business_dna_none():
    assert ReasoningService._business_dna(None, None) is None


def test_business_health_surface_is_bands_not_scores():
    """The founder-facing surface exposes bands only -- no raw score field at all."""
    dna = ReasoningService._business_dna(None, _score())
    report = SimpleNamespace(business_dna=dna, report_id=1, generated_at=None)
    bh = business_health_from_report(report)
    assert bh.available is True
    assert bh.band == "Needs Attention"
    assert bh.pillars[0].pillar_name == "Founder Readiness"
    assert bh.pillars[0].red_flag_triggered is True
    assert bh.pillars[1].band is None                 # unassessed pillar -> null, not 0
    # structural guarantee: no score anywhere in the serialised payload
    blob = bh.model_dump_json()
    assert "score" not in blob.lower() and "74" not in blob


def test_business_health_empty_state_is_null_not_zero():
    bh = business_health_from_report(None)
    assert bh.available is False and bh.band is None and bh.pillars == []
