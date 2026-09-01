"""A Business Health Score must say how much of the business it looked at.

PILLAR_SCORE_FROM_ANSWERS excludes an unanswered pillar and renormalises the
remaining weights to 100. That is the right call -- scoring an unasked pillar 0
would be worse -- but it makes a partial assessment indistinguishable from a
whole one in the number itself.

Stage scoping turned that from an edge case into the normal path. By pillar
weight, a founder is assessed on:

    Ideation           2 of 6 pillars   45% of the model   (no score at all)
    Validation         3 of 6           60%
    Prototype / MVP    4 of 6           80%
    Early Traction+    6 of 6          100%

Ideation already emits nothing. Validation and Prototype emit a score, and the
report used to introduce it as "Across the six readiness pillars..." however few
had been assessed -- telling the founder we had read three pillars we never
asked them a single question about.
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

def _pillar(pillar_id, score, weight):
    return SimpleNamespace(
        pillar_id=pillar_id, pillar_name=f"P{pillar_id}", weight=weight, score=score,
        band=("Strong" if score is not None else None), red_flag_triggered=False,
        red_flag_note=None, assessed_question_count=(3 if score is not None else 0),
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
