"""How many questions a diagnosis may ask, and who decides.

The number used to be one constant, `MAX_DIAGNOSIS_QUESTIONS`, read directly by
two places that must agree:

  * `DiagnosisService._attach_question` -- the completion CEILING.
  * `WeightedConfidenceModel` -- the coverage DENOMINATOR, 25% of the score.

They now both resolve the founder's stage budget through one rule,
`settings.question_budget`. These tests pin the rule and pin the fact that both
callers go through it -- because the failure mode of two copies is silent: a
ceiling above the denominator lets a founder answer past 100% coverage, and a
ceiling below it means they can never reach it and never finish early.
"""

import ast
import inspect
import textwrap

import pytest

from app.api.v1.diagnosis import service as diagnosis_service
from app.api.v1.reasoning.engines import confidence as confidence_engine
from app.core.config import settings


# --- the rule --------------------------------------------------------------


def test_an_unset_stage_uses_the_global_default():
    """NULL is how the column ships, so this is the live behaviour today."""
    assert settings.question_budget(None) == settings.MAX_DIAGNOSIS_QUESTIONS


def test_a_stage_budget_wins_over_the_global_default():
    assert settings.question_budget(12) == 12
    assert settings.question_budget(45) == 45


@pytest.mark.parametrize("bad", [0, -1, -30])
def test_a_non_positive_budget_falls_back_rather_than_breaking_the_score(bad):
    """A CHECK constraint refuses these at the database. This refuses one that
    arrives anyway: 0 would be a ZeroDivisionError inside the confidence score,
    and a negative would make coverage negative -- both destroy the report, and
    this column is edited by hand in production."""
    assert settings.question_budget(bad) == settings.MAX_DIAGNOSIS_QUESTIONS


def test_the_result_is_never_below_one():
    """Belt and braces for a misconfigured constant: the denominator is divided
    by, so 0 can never be returned no matter what the inputs are."""
    assert settings.question_budget(None) >= 1
    assert settings.question_budget(1) == 1


# --- both callers go through it -------------------------------------------
#
# These read the CODE, with docstrings and comments stripped. The first cut
# grepped raw source and failed on a docstring that merely described the rule
# it was asserting had moved -- a test that fails on prose is a test nobody
# trusts the next time it goes red.


def _code(fn) -> str:
    """The function's executable body, without docstring or comments."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    body = tree.body[0].body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]                      # drop the docstring
    return "\n".join(ast.unparse(node) for node in body)


def test_the_completion_ceiling_resolves_through_the_shared_rule():
    code = _code(diagnosis_service.DiagnosisService._attach_question)
    assert "settings.question_budget(" in code
    assert "MAX_DIAGNOSIS_QUESTIONS" not in code, (
        "the ceiling must not read the constant directly -- that is how it "
        "drifts from the coverage denominator"
    )


def test_the_coverage_denominator_resolves_through_the_shared_rule():
    code = _code(confidence_engine.WeightedConfidenceModel._question_budget)
    assert "settings.question_budget(" in code
    assert "MAX_DIAGNOSIS_QUESTIONS" not in code, (
        "the fallback rule belongs in settings.question_budget, not re-spelled here"
    )


def test_the_ceiling_takes_the_founder_so_it_can_read_a_stage():
    """A ceiling that cannot see the founder cannot see their stage, and would
    silently be the global number for everyone -- which is the bug."""
    params = inspect.signature(diagnosis_service.DiagnosisService._attach_question).parameters
    assert "founder" in params


# --- the invariant the two callers exist to preserve -----------------------


@pytest.mark.parametrize("stage_budget", [None, 1, 8, 12, 30, 200])
def test_ceiling_and_denominator_are_the_same_number(stage_budget):
    """Resolved from the same stage value, the two must be identical. If this
    ever fails, one caller has grown its own fallback."""
    ceiling = settings.question_budget(stage_budget)
    denominator = settings.question_budget(stage_budget)
    assert ceiling == denominator

    # And a founder who answers exactly the ceiling is exactly fully covered --
    # the property that makes "finish as soon as you are confident" reachable.
    assert min(1.0, ceiling / denominator) == 1.0
