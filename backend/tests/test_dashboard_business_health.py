"""Business-health persistence (business_dna serialisation) + dashboard schema.

`ReasoningService._business_dna` doesn't use `self`, so it's called unbound with
a dummy self -- no DB/engine construction needed.
"""

from decimal import Decimal

from app.api.v1.reasoning.schemas import BusinessHealthScore, PillarScore
from app.api.v1.reasoning.service import ReasoningService
from app.schemas.dashboard import BusinessHealthDashboard, PillarHealth


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


def test_dashboard_schema_round_trips_snapshot():
    dna = ReasoningService._business_dna(None, _score())
    dash = BusinessHealthDashboard(
        available=True, report_id=1, overall_score=dna["overall_score"],
        band=dna["band"], red_flags=dna["red_flags"],
        pillars=[PillarHealth(**p) for p in dna["pillars"]],
    )
    assert dash.available is True
    assert dash.overall_score == 64
    assert dash.pillars[0].red_flag_triggered is True
    assert dash.pillars[1].score is None


def test_dashboard_empty_state():
    dash = BusinessHealthDashboard(available=False)
    assert dash.available is False and dash.pillars == [] and dash.overall_score is None
