"""A second look at the WHOLE session, after every answer has been graded alone.

WHY THIS EXISTS. The per-answer classifier sees one answer at a time. Grading
answer 14 it does not know what the founder said in answers 1 to 13, so it
judges every answer against one fixed bar and cannot tell "early but organised"
from "in trouble". Both readings have shipped: a rubric change on 25 Sep graded
28 of 30 answers red on a founder who could quote his margin per order to the
rupee, and the rubric before it graded candour green on a founder who had no
process at all. Neither is visible from inside a single answer. Both are obvious
from the spread.

WHAT IT MAY DO, AND WHAT IT MAY NOT. The model proposes changes; this module
decides which are allowed, in code rather than in the prompt:

  * ONE BAND AT A TIME. red<->amber and amber<->green. Never red<->green -- a
    two-band jump is re-grading, and if one answer really is that wrong the
    per-answer rubric is what needs fixing.
  * NOT_APPLICABLE IS UNTOUCHABLE, in either direction. It means the subject
    does not exist in this business, which is a fact about the business and not
    a severity judgement.
  * BOTH DIRECTIONS. A pass that can only soften drifts green over time, which
    is the failure this product already had once. It may harshen a green it
    judges too generous by exactly the same rule.
  * A CEILING ON HOW MUCH IT MAY MOVE. If the model proposes changing more than
    _MAX_CHANGED_SHARE of the session, NOTHING is applied and the original
    grades stand. Rewriting half a session is not calibration; it is a second
    grader disagreeing with the first, and the honest response to that is to
    keep the first and say so in the log.
  * EVERY CHANGE CARRIES ITS REASON, onto the classification's rationale, so a
    label a founder was shown can always be traced to the sentence that moved
    it.

FAILS OPEN. Any error, timeout, unparseable reply or missing provider returns
the original classifications unchanged. A calibration pass is never worth
failing a diagnosis over.
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from decimal import Decimal

from app.api.v1.reasoning.schemas import AnswerClassification
from app.core.logger import logger
from app.models.enums import ScoreLabel
from app.services.llm.base import LLMMessage, LLMRequest, LLMRole

#: The most of a session this may move before the whole pass is discarded.
#: A third is already generous for "the spread is off"; beyond it the two
#: graders simply disagree, and the one that saw each answer in full wins.
_MAX_CHANGED_SHARE = 0.34

#: Which single-band moves are legal. Keys and values are both labels; a move
#: not in here is dropped, whatever the model said.
_ALLOWED_MOVES = {
    (ScoreLabel.RED, ScoreLabel.AMBER),
    (ScoreLabel.AMBER, ScoreLabel.RED),
    (ScoreLabel.AMBER, ScoreLabel.GREEN),
    (ScoreLabel.GREEN, ScoreLabel.AMBER),
}

#: How much of an answer the model is shown. Enough to judge what it describes;
#: the per-answer classifier already read it in full.
_ANSWER_CHARS = 600

_SYSTEM = (
    "You are reviewing the grading of a founder diagnosis, not the founder.\n"
    "\n"
    "Every answer below has already been graded on its own, by a classifier "
    "that could not see any of the others. You can see all of them at once. "
    "Your only job is to find grades that the FULL SET shows to be wrong.\n"
    "\n"
    "The bands:\n"
    "  green -- the thing asked about is in good shape, shown with specifics.\n"
    "  amber -- a real practice with a real gap: the founder does something, "
    "and it is incomplete.\n"
    "  red   -- the thing asked about is weak, missing or unmanaged, or the "
    "founder does not know something the business depends on.\n"
    "\n"
    "What the whole set shows that one answer cannot:\n"
    "- A founder who names real numbers, routines and records elsewhere is "
    "unlikely to be genuinely unmanaged everywhere. Reds around a consistent "
    "practice are usually ambers.\n"
    "- A founder whose answers are articulate but describe nothing they "
    "actually do is not doing well. Greens given for candour are usually "
    "ambers or reds.\n"
    "- Being EARLY is not the same as being BROKEN, and being HONEST is not "
    "the same as being HEALTHY.\n"
    "\n"
    "Rules you must follow:\n"
    "- You may move a grade ONE band only: red<->amber, or amber<->green. "
    "Never red<->green.\n"
    "- Never change not_applicable, and never change anything TO "
    "not_applicable.\n"
    "- Change nothing unless the other answers are what make it wrong. If a "
    "grade looks wrong on its own, leave it: that is the other classifier's "
    "job and it read the full answer.\n"
    "- Most sessions need no changes at all. Returning an empty list is a "
    "normal and correct answer.\n"
    "\n"
    'Reply with JSON only: {"changes": [{"id": <answer_id>, "to": '
    '"<green|amber|red>", "why": "<one sentence naming the other answers that '
    'make this grade wrong>"}]}'
)


def _prompt(rows: list[dict]) -> str:
    lines = ["Here is the whole session. Current grade in brackets.", ""]
    for r in rows:
        answer = (r["answer"] or "").strip().replace("\n", " ")
        if len(answer) > _ANSWER_CHARS:
            answer = answer[:_ANSWER_CHARS].rsplit(" ", 1)[0] + "…"
        lines.append(f'[{r["label"]}] id={r["id"]}')
        lines.append(f'  Q: {r["question"]}')
        lines.append(f'  A: {answer}')
        lines.append("")
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["label"]] = counts.get(r["label"], 0) + 1
    spread = ", ".join(f"{n} {label}" for label, n in sorted(counts.items()))
    lines.append(f"Spread as graded: {spread}, across {len(rows)} answers.")
    return "\n".join(lines)


def _parse(text: str) -> list[dict]:
    """The changes array, or [] for anything unparseable."""
    if not text:
        return []
    blob = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", blob, re.DOTALL)
    if fenced:
        blob = fenced.group(1).strip()
    start, end = blob.find("{"), blob.rfind("}")
    if start == -1 or end == -1:
        return []
    try:
        data = json.loads(blob[start:end + 1])
    except (ValueError, TypeError):
        return []
    changes = data.get("changes")
    return changes if isinstance(changes, list) else []


class SessionCalibrator:
    """Reviews a graded session as a whole. Never raises."""

    def __init__(self, provider, *, timeout_seconds: float = 30.0):
        self._provider = provider
        self._timeout = timeout_seconds

    async def calibrate(
        self,
        classifications: list[AnswerClassification],
        answers,
        questions,
        bands,
    ) -> list[AnswerClassification]:
        try:
            return await self._calibrate(classifications, answers, questions, bands)
        except Exception as exc:  # noqa: BLE001 -- never worth failing a diagnosis
            logger.warning("session calibration failed, keeping original grades: %s", exc)
            return classifications

    async def _calibrate(self, classifications, answers, questions, bands):
        by_id = {c.answer_id: c for c in classifications}
        answer_text = {a.answer_id: a.answer_text for a in answers}

        rows = []
        for c in classifications:
            if c.label is ScoreLabel.NOT_APPLICABLE:
                continue
            question = questions.get(c.question_id)
            rows.append({
                "id": c.answer_id,
                "label": c.label.value,
                "question": getattr(question, "question_text", "") or "",
                "answer": answer_text.get(c.answer_id, ""),
            })
        if len(rows) < 2:
            # Nothing to compare against is the one case where this cannot help.
            return classifications

        reply = await self._provider.generate(LLMRequest(
            messages=(
                LLMMessage(role=LLMRole.SYSTEM, content=_SYSTEM),
                LLMMessage(role=LLMRole.USER, content=_prompt(rows)),
            ),
            temperature=0.0,
            max_tokens=1200,
        ))

        proposed = _parse(getattr(reply, "text", "") or "")
        if not proposed:
            return classifications

        allowed: dict[int, tuple[ScoreLabel, str]] = {}
        for change in proposed:
            if not isinstance(change, dict):
                continue
            current = by_id.get(change.get("id"))
            if current is None:
                continue
            try:
                to = ScoreLabel(str(change.get("to", "")).strip().lower())
            except ValueError:
                continue
            if (current.label, to) not in _ALLOWED_MOVES:
                continue
            why = str(change.get("why") or "").strip()
            allowed[current.answer_id] = (to, why)

        if not allowed:
            return classifications

        share = len(allowed) / len(rows)
        if share > _MAX_CHANGED_SHARE:
            logger.warning(
                "session calibration proposed %d/%d changes (%.0f%%); keeping the "
                "original grades -- that is a second grader disagreeing, not a "
                "calibration",
                len(allowed), len(rows), share * 100,
            )
            return classifications

        out = []
        for c in classifications:
            move = allowed.get(c.answer_id)
            if move is None:
                out.append(c)
                continue
            to, why = move
            note = f"[session calibration: {c.label.value} -> {to.value}] {why}".strip()
            out.append(replace(
                c,
                label=to,
                score=_score_for(to, bands),
                rationale=f"{c.rationale}\n{note}" if c.rationale else note,
            ))
        logger.info(
            "session calibration adjusted %d of %d graded answers",
            len(allowed), len(rows),
        )
        return out


def _score_for(label: ScoreLabel, bands) -> Decimal | None:
    """The numeric band for a label -- the same map the classifier uses.

    NOT_APPLICABLE is None rather than zero, because zero is Green's band and
    would enter the risk numerator as positive evidence. It cannot be reached
    from here (the move table forbids it) and is present so this map cannot
    disagree with diagnostic._score_for_label if the table ever changes.
    """
    return {
        ScoreLabel.GREEN: bands.green,
        ScoreLabel.AMBER: bands.amber,
        ScoreLabel.RED: bands.red,
        ScoreLabel.NOT_APPLICABLE: None,
    }[label]
