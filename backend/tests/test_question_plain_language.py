"""The plain-language rewrites must change the wording and nothing else.

Migration c5e18b3f9a04 rewords the diagnosis questions founders could not
understand. Every answer is scored against what its question asks, so a rewrite
that changed the question's shape would quietly change what the scores mean.
These tests pin the properties that can be checked without a database; the
meaning itself was reviewed by hand (see the migration docstring).
"""

import re

MIGRATION = "c5e18b3f9a04"

#: Questions that test whether a founder knows a term. Explaining the term
#: in brackets would answer the question for them.
_TESTS_THE_TERM = {
    "FIN-201": "fixed costs",
    "GTM-033": "go-to-market strategy",
    "S10-FIN-055": "unit economics",
    "S0-BFS-001": "RBI, IRDAI or SEBI",
}

#: Knowledge tests whose only rewrite explained the answer, so the current
#: text stays. Pinned so a later edit does not reintroduce the giveaway.
_LEFT_ALONE = {"SAL-012", "S0-BFS-010"}


def _migration():
    """Load the migration by path -- alembic revisions are not importable."""
    import importlib.util
    from pathlib import Path

    from app.core.paths import BACKEND_DIR

    matches = sorted(Path(BACKEND_DIR, "alembic", "versions").glob(f"*{MIGRATION}*.py"))
    assert len(matches) == 1, f"expected one {MIGRATION} migration, found {matches}"
    spec = importlib.util.spec_from_file_location(f"_mig_{MIGRATION}", matches[0])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rewrites():
    return _migration()._REWRITES


def test_each_question_is_rewritten_at_most_once():
    codes = [code for code, _, _ in _rewrites()]
    assert len(codes) == len(set(codes))


def test_every_rewrite_actually_changes_the_text():
    """A no-op row would make the downgrade guard ambiguous."""
    assert all(old != new for _, old, new in _rewrites())


def test_rewrites_are_clean_single_line_text():
    for code, _, new in _rewrites():
        assert new == " ".join(new.split()), code
        assert new[:1] not in "\"'“", code


def test_rewrites_stay_short_enough_to_read():
    for code, _, new in _rewrites():
        assert len(new.split()) <= 42, code


def test_a_question_is_still_a_question():
    instruction = re.compile(r"^(Rate|Describe|Tell|Think|Walk|Imagine|If|You|Is)\b")
    for code, old, new in _rewrites():
        if old.rstrip().endswith("?"):
            assert new.endswith("?") or instruction.match(new), code


def test_rating_scale_questions_keep_their_answer_shape():
    """A founder asked to "Rate from 1 to 5" answers with a number; the scorer
    reading that answer depends on it staying a number."""
    for code, old, new in _rewrites():
        if old.startswith("Rate from 1 to 5"):
            assert new.startswith("Rate from 1 to 5"), code
        if not old.startswith(("Rate", "On a scale")):
            assert not new.startswith("Rate from 1 to 5"), code


def test_questions_that_test_a_term_do_not_explain_it():
    by_code = {code: new for code, _, new in _rewrites()}
    for code, term in _TESTS_THE_TERM.items():
        if code in by_code:
            assert term in by_code[code]
            assert "(" not in by_code[code], code


def test_knowledge_tests_that_could_not_be_reworded_stay_as_they_are():
    codes = {code for code, _, _ in _rewrites()}
    assert not codes & _LEFT_ALONE


def test_it_follows_the_previous_head():
    assert _migration().down_revision == "a2e7c481f96b"
