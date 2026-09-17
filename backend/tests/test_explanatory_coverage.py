"""Semantic tests for curated `explains` relationships and coverage.

Properties, not numbers. The curated edge set is expected to grow, and a test
that pinned a coverage value would have to be rewritten every time it does.
"""

from decimal import Decimal

import pytest

from app.api.v1.reasoning.explanatory import (
    EXPLAINS,
    ExplanatoryLink,
    _validate,
    explanatory_coverage,
)

D = Decimal


def links(*pairs):
    return tuple(ExplanatoryLink(s, t, D(str(w)), "test fixture")
                 for s, t, w in pairs)


# --- coverage semantics -----------------------------------------------------

def test_a_source_explaining_observed_problems_gains_coverage():
    ls = links(("A", "B", 0.9), ("A", "C", 0.7))
    assert explanatory_coverage("A", {"A", "B", "C"}, ls) > D("0")


def test_a_source_explaining_nothing_observed_gains_none():
    """The edge exists in the catalogue but the target is not this founder's
    problem. Explaining something they do not have is not evidence."""
    ls = links(("A", "B", 0.9))
    assert explanatory_coverage("A", {"A", "Z"}, ls) == D("0")


def test_a_source_with_no_edges_gains_none():
    """No artificial coverage for a candidate simply because it was observed."""
    ls = links(("A", "B", 0.9))
    assert explanatory_coverage("B", {"A", "B"}, ls) == D("0")


def test_explaining_more_observed_problems_gives_more_coverage():
    ls = links(("A", "B", 0.7), ("A", "C", 0.7))
    one = explanatory_coverage("A", {"A", "B"}, ls)
    two = explanatory_coverage("A", {"A", "B", "C"}, ls)
    assert two > one


def test_coverage_saturates_and_never_exceeds_one():
    """A weak edge repeated cannot be stacked into certainty."""
    ls = links(*[("A", f"T{i}", 0.6) for i in range(10)])
    observed = {"A"} | {f"T{i}" for i in range(10)}
    assert explanatory_coverage("A", observed, ls) < D("1")


def test_a_stronger_edge_carries_more_coverage_than_a_weaker_one():
    strong = explanatory_coverage("A", {"A", "B"}, links(("A", "B", 0.9)))
    weak = explanatory_coverage("A", {"A", "B"}, links(("A", "B", 0.3)))
    assert strong > weak


def test_an_unobserved_source_gains_nothing():
    """A problem the founder does not have explains nothing for them, however
    well connected it is in the catalogue."""
    ls = links(("A", "B", 0.9))
    assert explanatory_coverage("A", {"B"}, ls) == D("0")


def test_missing_source_is_handled():
    assert explanatory_coverage(None, {"A", "B"}, links(("A", "B", 0.9))) == D("0")


# --- anti-circularity -------------------------------------------------------

def test_self_explanation_is_rejected():
    with pytest.raises(ValueError, match="explains itself"):
        _validate(links(("A", "A", 0.9)))


def test_a_two_node_cycle_is_rejected():
    """A explains B and B explains A would let each inflate the other the
    moment anyone adds multi-hop reasoning."""
    with pytest.raises(ValueError, match="cycle"):
        _validate(links(("A", "B", 0.9), ("B", "A", 0.9)))


def test_a_longer_cycle_is_rejected():
    with pytest.raises(ValueError, match="cycle"):
        _validate(links(("A", "B", 0.9), ("B", "C", 0.9), ("C", "A", 0.9)))


def test_duplicate_edges_are_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        _validate(links(("A", "B", 0.9), ("A", "B", 0.5)))


def test_a_diamond_is_allowed():
    """Two independent paths to one target are not a cycle and must not be
    rejected -- that shape is common in a real taxonomy."""
    _validate(links(("A", "B", 0.9), ("A", "C", 0.9), ("B", "D", 0.9),
                    ("C", "D", 0.9)))


def test_the_shipped_edge_set_is_acyclic():
    _validate(EXPLAINS)


# --- what the curated set does and does not claim ---------------------------

def test_curated_edges_are_directional():
    """Every shipped edge must be one-way. If a genuine mutual dependency is
    ever found it needs explicit handling, not a quiet pair of edges."""
    pairs = {(link.source, link.target) for link in EXPLAINS}
    for source, target in pairs:
        assert (target, source) not in pairs


def test_every_curated_edge_carries_a_rationale():
    """An edge without a stated reason is an assertion nobody can review."""
    for link in EXPLAINS:
        assert link.rationale.strip()
        assert D("0") < link.strength <= D("1")


def test_icp_explains_the_pipeline_problem_the_taxonomy_says_it_does():
    """GTM-002 -> SAL-001 is the one edge the catalogue states outright:
    SAL-001's description calls an empty pipeline 'a direct downstream
    consequence of failing to define the target buyer'."""
    assert explanatory_coverage("GTM-002", {"GTM-002", "SAL-001"}) > D("0")


def test_icp_does_not_claim_to_explain_the_sales_skill_problem():
    """The regression guard against overfitting.

    The ComplyFlow QA persona's ground truth says unclear ICP is primary and
    weak discovery is its symptom. The taxonomy disagrees: SAL-002 is defined
    as a founder capability gap, compounded by absent feedback loops, not as a
    consequence of undefined targeting. Adding GTM-002 -> SAL-002 would make
    that persona rank as expected, which is exactly why it must not be added
    without the taxonomy changing first.

    If someone later revises SAL-002's definition so the dependency is real,
    this test should be deleted deliberately -- not edited to make a run pass.
    """
    assert explanatory_coverage("GTM-002", {"GTM-002", "SAL-002"}) == D("0")


def test_related_problems_are_not_treated_as_explanatory():
    """`problems.related_problem_ids` is association and is never read here.

    GTM-002 and SAL-002 share the related problem GTM-004 in the catalogue.
    Association through a shared neighbour must not become an explanatory
    claim, or every densely connected problem becomes a root cause.
    """
    assert explanatory_coverage("GTM-002", {"GTM-002", "SAL-002", "GTM-004"}) \
        == explanatory_coverage("GTM-002", {"GTM-002", "GTM-004"})
