"""A kept answer is never left unscored.

An unscored answer is not neutral. StoredScoreAnswerClassifier refuses to guess
a band, so classify_answers logs "Skipping unscored answer" and drops it: the
founder's answer is accepted, shown back to them as answered, and then
contributes nothing to their diagnosis. Measured on one live session, six
answers went that way. Enough of them and NoClassifiableAnswersError takes the
whole report down with a 422.

submit_answer guards against that with a neutral AMBER fallback -- and the
guard had a hole. It asked `insight is None`, on the assumption that an
advisor insight always carries a usable band. advisor._parse deliberately
breaks that assumption: a label outside {green, amber, red} nulls score_label
while still returning the insight, because the responsiveness verdict and the
next-question pick in the same reply are still good. In that state
_apply_insight no-ops and the `else` never runs, so the exact silent data loss
the fallback exists to prevent happened anyway -- just via a different route
than an advisor outage.

The predicate is about the SCORE, not the object carrying it.
"""

from __future__ import annotations

from app.api.v1.diagnosis.advisor import AnswerInsight, LLMNextQuestionAdvisor
from app.api.v1.diagnosis.service import needs_fallback_score


def _parse(payload: str) -> AnswerInsight | None:
    return LLMNextQuestionAdvisor.__dict__["_parse"](
        LLMNextQuestionAdvisor(provider=None), payload
    )


# --- the hole this closes ---------------------------------------------------

def test_an_unparseable_label_takes_the_fallback():
    """The regression. A non-vocabulary label is exactly the case that fell
    between the two branches."""
    insight = _parse('{"score_label":"moderate","confidence":0.7,"next_question_id":3}')
    assert insight is not None, "the insight itself survives -- only the band is dropped"
    assert insight.score_label is None
    assert needs_fallback_score(insight) is True


def test_a_missing_label_takes_the_fallback():
    insight = _parse('{"confidence":0.7,"next_question_id":3}')
    assert insight is not None
    assert needs_fallback_score(insight) is True


# --- the cases that already worked, pinned so they keep working -------------

def test_no_insight_at_all_takes_the_fallback():
    """No advisor wired, or the call failed/timed out."""
    assert needs_fallback_score(None) is True


def test_a_real_band_is_kept():
    for label in ("green", "amber", "red"):
        insight = _parse(f'{{"score_label":"{label}","confidence":0.8}}')
        assert insight is not None
        assert insight.score_label is not None
        assert needs_fallback_score(insight) is False, label


def test_an_answer_judged_unresponsive_but_scored_keeps_its_score():
    """Responsiveness and quality are separate axes. An answer accepted over the
    one-reprompt bound still carries the band the model gave it."""
    insight = _parse('{"score_label":"red","responsive":false}')
    assert insight is not None
    assert needs_fallback_score(insight) is False


# --- the advisor-scored branch reaches names that exist ----------------------

def test_submit_answer_references_no_undefined_name():
    """`submit_answer` must not reference a name that does not exist in its scope.

    The regression this closes shipped as a two-token typo: the advisor-scored
    branch called `_learn_session_facts(session, answer, answered)` and
    `_extract_capability_evidence(session, answer, answered)`, but `answered` is
    the parameter name of `_choose_next_question`, not a local of
    `submit_answer` -- where the same Question is bound as `question`.

    It survived because nothing reached it. That branch runs only when the
    advisor returns a USABLE score (`not needs_fallback_score(insight)`), so
    with ADAPTIVE_QUESTIONS=false -- the default, and what the whole suite runs
    under -- control always takes the `else`. Every test passed; the first
    real advisor-scored answer raised NameError instead.

    A static check rather than an integration test on purpose: the failure mode
    is a name that is never bound, which no amount of DB fixture setup makes
    more visible, and this stays hermetic like the rest of this file. There is
    no Python linter in the venv or in CI, so nothing else catches this class.
    """
    import ast
    import builtins
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "app/api/v1/diagnosis/service.py"
    tree = ast.parse(path.read_text())

    known = set(dir(builtins))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            known |= {(a.asname or a.name.split(".")[0]) for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            known |= {(a.asname or a.name) for a in node.names}
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            known.add(node.name)
        elif isinstance(node, ast.Assign):
            known |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            known.add(node.target.id)

    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name == "submit_answer"
    )

    args = fn.args
    known |= {a.arg for a in [*args.posonlyargs, *args.args, *args.kwonlyargs]}
    if args.vararg:
        known.add(args.vararg.arg)
    if args.kwarg:
        known.add(args.kwarg.arg)
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            known.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            known.add(node.name)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            known.add(node.name)
        elif isinstance(node, ast.alias):
            known.add(node.asname or node.name.split(".")[0])

    undefined = sorted({
        n.id for n in ast.walk(fn)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in known
    })
    assert undefined == [], f"submit_answer references undefined name(s): {undefined}"
