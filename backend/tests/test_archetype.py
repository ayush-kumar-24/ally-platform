"""Founder Archetype engine -- unit tests (no DB).

The engine is deterministic given the catalogue + the founder's text, so the
repository is faked with a small archetype catalogue and assignments are asserted.
"""

from decimal import Decimal

from app.api.v1.reasoning.engines.archetype import ArchetypeEngine, ArchetypeMatch


class _Row:
    def __init__(self, aid, code, name, key_traits, criteria):
        self.archetype_id = aid
        self.archetype_code = code
        self.archetype_name = name
        self.key_traits = key_traits
        self.assignment_criteria = criteria


class _Repo:
    def __init__(self, rows):
        self._rows = rows

    def get_archetypes(self):
        return self._rows


_CATALOG = [
    _Row(1, "ARCH-001", "Operator",
         {"decision_style": "Intuition-led, moves fast", "stress_pattern": "Over-controls",
          "core_motivation": "Mastery"},
         'Likely when the founder personally fixes operational bottlenecks and '
         'optimizes systems and processes. Frequently says: "I\'ll just do it."'),
    _Row(2, "ARCH-003", "Visionary Builder",
         {"decision_style": "Panel-advised", "stress_pattern": "Struggles to delegate strategy",
          "core_motivation": "Legacy"},
         'Likely when the founder discusses long-term impact and recruits around '
         'mission. Repeatedly says: "We\'re building something much bigger than us."'),
    _Row(3, "ARCH-007", "Community Builder",
         {"decision_style": "Relationship-aware", "stress_pattern": "Avoids difficult conversations",
          "core_motivation": "Connection"},
         'Likely when the founder discusses team and culture and mentors people. '
         'Often says: "I don\'t want to lose the team."'),
]


def _engine():
    return ArchetypeEngine(_Repo(list(_CATALOG)))


def test_assigns_by_signature_phrase_and_keywords():
    answers = [
        "Honestly I keep fixing our operational bottlenecks myself.",
        "I'll just do it rather than wait. I optimize our systems and processes constantly.",
    ]
    m = _engine().assign(answers)
    assert isinstance(m, ArchetypeMatch)
    assert m.name == "Operator"
    assert m.archetype_id == 1
    assert m.score > 0
    assert m.is_confident is True
    assert any("just do it" in t for t in m.matched_terms)


def test_assigns_visionary_from_mission_language():
    m = _engine().assign(["We're building something much bigger than us; the long-term impact and mission drive me."])
    assert m is not None and m.name == "Visionary Builder"


def test_thin_margin_is_not_confident():
    # Two archetypes essentially tied -> assign the top one but flag NOT confident
    # (a near-tie must never be presented as a definite archetype).
    from decimal import Decimal
    from app.api.v1.reasoning.engines.archetype import ArchetypeEngine

    rows = [
        _Row(1, "A-1", "Operator",
             {"core_motivation": "Mastery"},
             'Frequently says: "I\'ll just do it." optimize systems processes bottlenecks'),
        _Row(2, "A-2", "Twin",
             {"core_motivation": "Mastery"},
             'Frequently says: "I\'ll just do it." optimize systems processes bottlenecks'),
    ]
    eng = ArchetypeEngine(_Repo(rows), min_margin=Decimal("0.05"))
    m = eng.assign(["I'll just do it and optimize our systems, processes and bottlenecks."])
    assert m is not None
    assert m.is_confident is False        # identical criteria -> zero margin


def test_no_answers_returns_none():
    assert _engine().assign([]) is None
    assert _engine().assign(["", "   "]) is None


def test_no_signal_returns_none():
    # Text with none of the archetypes' distinctive terms/phrases.
    assert _engine().assign(["blah blah zzzz qqqq"]) is None


def test_empty_catalogue_returns_none():
    eng = ArchetypeEngine(_Repo([]))
    assert eng.assign(["I'll just do it"]) is None


def test_as_founder_dna_shape():
    m = _engine().assign(["I'll just do it; I fix operational bottlenecks and optimize systems."])
    dna = m.as_founder_dna()
    assert dna["archetype_name"] == "Operator"
    assert dna["archetype_code"] == "ARCH-001"
    assert dna["core_motivation"] == "Mastery"
    assert isinstance(dna["fit_score"], float)
    assert dna["is_confident"] is True
    assert isinstance(dna["matched_terms"], list)
