"""'All' is a wildcard tag in rag_documents, not the name of an industry.

The stage clause had always honoured its wildcard:

    d.stage_relevance IS NULL OR d.stage_relevance = 'All' OR = ANY(:stages)

The industry clause had not:

    d.industry_tag IS NULL OR d.industry_tag = :industry

25 of the 30 approved documents carry industry_tag='All', so every founder whose
industry was not literally the string "All" (or one of the two specifically
tagged industries) retrieved NOTHING. Measured live: the same query returned 20
chunks unfiltered and 0 with industry="Technology & SaaS", so chat and reasoning
ran with retrieval_hits=0 and no citations -- silently, because an empty
retrieval is indistinguishable from "nothing relevant was found".

These assert on the SQL text rather than a live pgvector query: the suite is
hermetic (no database), and the defect was entirely in the predicate. A query
test would need a real pgvector index and would not have caught it any earlier.
"""

from __future__ import annotations

import re

from app.api.v1.ally.rag import sql_repository as repo


def _norm(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip()


def test_industry_clause_treats_all_as_a_wildcard():
    clause = _norm(repo._INDUSTRY_CLAUSE)

    assert "d.industry_tag = 'All'" in clause, (
        "industry_tag='All' documents must match every founder; without this arm "
        "25 of 30 approved documents are unreachable."
    )
    # The specific-industry and untagged arms must both survive the fix.
    assert "d.industry_tag IS NULL" in clause
    assert "d.industry_tag = :industry" in clause


def test_industry_and_stage_clauses_agree_on_the_wildcard():
    """The two filters are the same shape; they must stay that way.

    This is the assertion that would have caught the original bug: stage handled
    'All', industry did not, and nothing held them to the same rule.
    """
    industry = _norm(repo._INDUSTRY_CLAUSE)
    stage = _norm(repo._STAGE_CLAUSE)

    assert "= 'All'" in stage
    assert "= 'All'" in industry


def test_industry_arms_are_ored_not_anded():
    """A wildcard AND a specific match would exclude everything instead."""
    clause = _norm(repo._INDUSTRY_CLAUSE)

    # One leading AND joining this clause to the rest of the WHERE, then ORs.
    assert clause.startswith("AND (")
    assert clause.count(" OR ") == 2
    assert " AND " not in clause[len("AND ("):]


def test_restricted_content_is_still_excluded_by_default():
    """Guard against a careless edit to the neighbouring clause."""
    restricted = _norm(repo._RESTRICTED_CLAUSE)

    assert "recommendation_only" in restricted
    assert "sales_collateral" in restricted
