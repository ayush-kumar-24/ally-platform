"""Founder DNA: every stage-dependent read is scoped to ONE stage group.

A founder's Founder DNA journey belongs to the stage group they are in. The
repository has four methods that depend on that, and `count_answered` was the
only one that did not scope to it -- it counted every answer the founder had
ever given, across every stage group. It gates two things: the follow-up
budget in the engine, and the "questions answered" number the founder is
shown.

That matters for a founder who edits their stage mid-journey. The new stage
group starts a fresh journey (its own 15 base questions and its own close),
but the old group's answers were still counted against the budget. Measured on
the seeded bank: 16 questions asked where an uninterrupted founder gets 18 --
exactly the two follow-up slots the adaptive phase has to work with.

Current Problem's method of the same name has always been stage-scoped; this
was the one sibling that disagreed.
"""

import inspect

import pytest

from app.api.v1.founder_dna.repository import FounderDnaRepository

# The repository reads that must never span stage groups.
STAGE_SCOPED_METHODS = [
    "count_answered",
    "answers_per_dimension",
    "closing_answered",
    "pool_size_per_dimension",
    "list_candidate_questions",
]


@pytest.mark.parametrize("method_name", STAGE_SCOPED_METHODS)
def test_method_takes_a_stage_group(method_name):
    sig = inspect.signature(getattr(FounderDnaRepository, method_name))
    assert "stage_group" in sig.parameters, (
        f"{method_name}() does not take a stage_group, so it cannot be scoped "
        "to the founder's journey"
    )


class _CapturingDb:
    """Stands in for a Session just long enough to catch the built query."""

    def __init__(self):
        self.stmt = None

    def execute(self, stmt):
        self.stmt = stmt
        return self

    def scalars(self):
        return self

    def all(self):
        return []

    def first(self):
        return None


def _sql(method_name, **kwargs):
    db = _CapturingDb()
    getattr(FounderDnaRepository(db), method_name)(**kwargs)
    return str(db.stmt.compile(compile_kwargs={"literal_binds": True})).replace("\n", " ")


def test_count_answered_filters_on_the_stage_group():
    sql = _sql("count_answered", founder_id=1, stage_group="Stage 0")
    assert "founder_dna_questions" in sql, (
        "count_answered no longer joins the question table, so it cannot know "
        "which stage group an answer belongs to:\n" + sql
    )
    assert "'Stage 0'" in sql, sql


def test_count_answered_is_scoped_to_the_founder_too():
    """The stage filter must narrow the founder's own answers, not replace
    that filter -- otherwise it counts every founder's answers in the group."""
    sql = _sql("count_answered", founder_id=42, stage_group="Stage 0")
    assert "founder_id = 42" in sql, sql


@pytest.mark.parametrize("group", ["Stage 0", "Stage 0→1", "Stage 1→10+"])
def test_each_stage_group_reaches_its_own_query(group):
    sql = _sql("count_answered", founder_id=1, stage_group=group)
    assert repr(group).strip("'\"") in sql or group in sql, sql
