"""A Business Health Score must say how much of the business it looked at.

PILLAR_SCORE_FROM_ANSWERS excludes a pillar it cannot score and renormalises the
remaining weights to 100. That is the right call -- scoring an unasked pillar 0
would be worse -- but it makes a partial assessment indistinguishable from a
whole one in the number itself.

Stage scoping turned that from an edge case into the normal path, and there are
now two ways a pillar drops out:

    OUT OF SCOPE   Business DNA Part 3 does not put it at this stage. Ideation
                   is diagnosed on four of the six -- Revenue Maturity and Team
                   & Leadership are genuinely inapplicable before there is
                   revenue or a team. Every stage from Validation on is on all
                   six.
    TOO THIN       The session produced fewer than MIN_ANSWERS_PER_PILLAR_SCORE
                   answers for it. Can happen at any stage.

Both come back as score=None and both are excluded from the overall. The
report used to introduce whatever survived as "Across the six readiness
pillars..." however few had been assessed -- telling the founder we had read
pillars we never asked them a single question about.
"""

from types import SimpleNamespace

from app.api.v1.reports.narrator import TemplateNarrator

TONE = SimpleNamespace(persona=None)


def _slots(assessed, total=6, band="Developing", pillars=None):
    return {
        "overall_band": band,
        "pillars": pillars if pillars is not None else [],
        "pillars_assessed": assessed,
        "pillars_total": total,
    }


# --- what the founder is told the score covers ----------------------------

def test_a_full_assessment_still_says_all_six():
    prose = TemplateNarrator()._business_dna(_slots(6), TONE)
    assert "all six readiness pillars" in prose


def test_a_partial_assessment_says_how_many_applied():
    """The bug. A Validation founder was told six pillars had been read."""
    prose = TemplateNarrator()._business_dna(_slots(3), TONE)

    assert "three readiness pillars that apply at your stage" in prose
    assert "six" not in prose


def test_a_prototype_founder_sees_four():
    prose = TemplateNarrator()._business_dna(_slots(4), TONE)
    assert "four readiness pillars that apply at your stage" in prose


def test_the_count_is_spelled_out_not_printed_as_a_digit():
    prose = TemplateNarrator()._business_dna(_slots(3), TONE)
    assert "3 readiness" not in prose


def test_the_band_still_leads_the_sentence():
    """The regression guard: the reading itself is unchanged, only its scope."""
    prose = TemplateNarrator()._business_dna(_slots(3, band="Strong"), TONE)
    assert '"Strong"' in prose


def test_each_persona_keeps_its_own_voice():
    narrator = TemplateNarrator()
    auditor = narrator._business_dna(_slots(3), SimpleNamespace(persona="Auditor"))
    validator = narrator._business_dna(_slots(3), SimpleNamespace(persona="Validator"))

    assert "business health reads as" in auditor
    assert "where you stand reads as" in validator
    for prose in (auditor, validator):
        assert "three readiness pillars that apply at your stage" in prose


def test_missing_counts_fall_back_to_the_whole_model():
    """An older report row has no counts stored. It must still read correctly
    rather than printing None."""
    prose = TemplateNarrator()._business_dna(
        {"overall_band": "Developing", "pillars": []}, TONE)
    assert "all six readiness pillars" in prose
    assert "None" not in prose


def test_no_band_produces_no_claim_at_all():
    prose = TemplateNarrator()._business_dna(_slots(3, band=None), TONE)
    assert "readiness pillars" not in prose


# --- the persisted snapshot carries the coverage --------------------------

def _pillar(pillar_id, score, weight, covered=("a", "b", "c"), total=3):
    return SimpleNamespace(
        pillar_id=pillar_id, pillar_name=f"P{pillar_id}", weight=weight, score=score,
        band=("Strong" if score is not None else None), red_flag_triggered=False,
        red_flag_note=None, assessed_question_count=(3 if score is not None else 0),
        dimensions_in_scope=covered, dimensions_total=total,
    )


def _health(pillars):
    return SimpleNamespace(overall_score=70, band="Developing", red_flags=[],
                           pillars=pillars)


def test_the_snapshot_records_how_many_pillars_were_assessed():
    from app.api.v1.reasoning.service import ReasoningService

    health = _health([
        _pillar(1, 80, 25), _pillar(2, 60, 20), _pillar(4, 70, 15),   # assessed
        _pillar(3, None, 20), _pillar(5, None, 10), _pillar(6, None, 10),
    ])
    dna = ReasoningService._business_dna(None, health)

    assert dna["pillars_assessed"] == 3
    assert dna["pillars_total"] == 6
    assert dna["assessed_weight_pct"] == 60.0        # 25 + 20 + 15


def test_a_full_assessment_records_the_whole_model():
    from app.api.v1.reasoning.service import ReasoningService

    health = _health([_pillar(i, 70, 10) for i in range(1, 7)])
    dna = ReasoningService._business_dna(None, health)

    assert dna["pillars_assessed"] == dna["pillars_total"] == 6


# --- ideation is scored, and the floor is what makes that safe -------------

def test_ideation_emits_a_business_health_score():
    """It used to emit nothing, so an ideation founder's report had no "Where
    you stand" section at all -- while Part 1 of the document promises exactly
    that read. The case for suppressing it was that two pillars renormalised to
    100 reads as a verdict on a business that does not exist; Part 3 puts four
    pillars at ideation, and the narrator now scopes the sentence to them."""
    from app.api.v1.diagnosis.stage_scope import SCOPE_BY_STAGE_ORDER

    assert SCOPE_BY_STAGE_ORDER[1].emits_business_health


def test_every_stage_emits_a_business_health_score():
    from app.api.v1.diagnosis.stage_scope import SCOPE_BY_STAGE_ORDER

    assert all(s.emits_business_health for s in SCOPE_BY_STAGE_ORDER.values())


def test_an_ideation_report_says_four_pillars_applied():
    """End of the chain: four in-scope pillars reach the founder as a sentence
    about four, not about six."""
    prose = TemplateNarrator()._business_dna(_slots(4), TONE)
    assert "four readiness pillars that apply at your stage" in prose
    assert "six" not in prose


def test_the_snapshot_carries_each_pillars_dimension_coverage():
    """So the report can qualify a pillar name that stands for part of the
    pillar -- see test_pillar_dimension_coverage.py."""
    from app.api.v1.reasoning.service import ReasoningService

    health = _health([
        _pillar(4, 60, 15, covered=("Execution Velocity",), total=3),
        _pillar(2, 80, 20, covered=("a", "b", "c", "d"), total=4),
    ])
    dna = ReasoningService._business_dna(None, health)

    assert dna["pillars"][0]["dimensions_in_scope"] == ["Execution Velocity"]
    assert dna["pillars"][0]["dimensions_total"] == 3
    assert dna["pillars"][1]["dimensions_total"] == 4
