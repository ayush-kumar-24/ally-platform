"""Adaptive next-question advisor (Hybrid mode).

The deterministic QuestionSelectionEngine still produces the ordered shortlist of
what to ask next. This advisor lets an LLM READ the founder's actual answer, judge
it Green/Amber/Red, and RE-RANK that shortlist -- choosing the most informative next
probe given what they just said.

It is strictly optional and fail-open: when no advisor is wired, or the LLM errors,
times out, or returns an id outside the shortlist, the caller falls back to the
deterministic pick, so the flow always progresses and never dead-ends. The Green/
Amber/Red read is returned too, so the answer can be scored once at submit time
(feeding the reasoning pipeline without a second LLM pass).

Vendor-neutral: it talks only to the injected `LLMProvider` (app.services.llm).
"""

from __future__ import annotations

import abc
import asyncio
import json
from dataclasses import dataclass
from typing import Sequence

from app.core.logger import logger
from app.services.llm import (
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMRequest,
    LLMRole,
)

#: The advisor may return the same four bands the stored classifier uses.
#:
#: "not_applicable" was missing here, and that was the whole bug behind N/A
#: answers scoring Red. ScoreLabel.NOT_APPLICABLE, the reasoning engines and
#: the answers_score_label_check constraint have supported a fourth UNSCORED
#: state all along -- diagnostic.py excludes it from both the numerator and the
#: denominator, symptom_detection.py does not count it as a symptom, and
#: root_cause.py never turns it into evidence. But the ADVISOR is what writes
#: answers.score_label whenever ADAPTIVE_QUESTIONS is on, and it only knew
#: three. So "N/A -- we have no free tier" came back Red, the strongest
#: negative signal available, and was then quoted to the founder as a symptom.
#: Measured on a keyed run: both N/A answers scored red at score 2.0.
_VALID_LABELS = {"green", "amber", "red", "not_applicable"}
#: answers.score is a 0/1/2 CHECK carrying RISK, not health: HIGHER IS WORSE.
#:
#: This is not a local convention -- it is the scoring schema, stored in
#: `scoring_rules` and sourced from the "Question-Level Scoring Schema"
#: document: QUESTION_SCORE_GREEN=0 (Low Risk), QUESTION_SCORE_AMBER=1
#: (Moderate Risk), QUESTION_SCORE_RED=2 (High Risk). Every reader of
#: answers.score assumes it -- reasoning/engines/diagnostic.py bands answers by
#: `score >= bands.red`, symptom_detection.py counts reds by the same band, and
#: business_health.py computes `risk_ratio = sum(scores) / (n * 2)`.
#:
#: This map was inverted (green:2 … red:0), which silently flipped every
#: downstream risk calculation. Verified end to end on 2026-08-19: a founder
#: whose 30 answers scored 25 red + 5 amber summed to 5 instead of 55, giving
#: risk_ratio 0.083 and a Business Health of 92/100 -- so a pre-revenue founder
#: who had never spoken to a customer was told all six pillars were "Strong".
#: business_health.py's own docstring names the failure exactly: "an
#: exactly-backwards score that still looks plausible".
#: "not_applicable" is deliberately absent: `.score` uses .get(), so it
#: yields None rather than a number. None, never zero -- zero is Green's
#: band, and scoring an inapplicable question as Green would be just as
#: wrong as scoring it Red.
_LABEL_TO_SCORE = {"green": 0, "amber": 1, "red": 2}


@dataclass(frozen=True)
class AnswerInsight:
    """The LLM's read of one answer plus its next-question recommendation.

    `next_question_id` is only a suggestion -- the caller MUST validate it against
    the shortlist before honouring it. `score_label` is None when unparseable.
    """

    score_label: str | None
    confidence: float
    next_question_id: int | None
    rationale: str
    #: Did the answer actually answer the question that was asked?
    #:
    #: Defaults True and is only ever set False by an explicit verdict, because
    #: every failure here must fail OPEN: an unparseable response, an older model
    #: that does not know the field, a timeout -- none of those are evidence that
    #: a founder wrote something irrelevant, and refusing a real answer is far
    #: worse than accepting a poor one.
    responsive: bool = True

    @property
    def score(self) -> int | None:
        return _LABEL_TO_SCORE.get(self.score_label) if self.score_label else None


def resolve_next(ordered, shortlist, insight: AnswerInsight | None):
    """Pure hybrid decision: honour the LLM's pick only when it is inside the
    shortlist; otherwise take the deterministic head. `ordered` is every candidate
    in deterministic order; `shortlist` is its bounded head handed to the LLM.

    Deterministic and side-effect free so it can be unit-tested without a DB or a
    provider.
    """
    if not ordered:
        return None
    deterministic = ordered[0]
    if insight is None or insight.next_question_id is None:
        return deterministic
    by_id = {q.question_id: q for q in shortlist}
    return by_id.get(insight.next_question_id, deterministic)


class NextQuestionAdvisor(abc.ABC):
    @abc.abstractmethod
    async def analyze(
        self, *, answered_question, answer_text: str, shortlist: Sequence, history,
        founder_brief: str = "",
    ) -> AnswerInsight | None:
        """Read the answer and recommend the next question from `shortlist`.
        Returns None on any failure (caller falls back to deterministic).

        `founder_brief` is who this founder is -- stage, industry, revenue, what
        they are building, the problem they arrived with, how they operate (see
        founder_brief.py). Optional so a caller with no database handy still
        works, but without it every founder in a stage group is asked the same
        questions in the same order, because the last five Q&A pairs are the
        only thing distinguishing them."""
        raise NotImplementedError


class LLMNextQuestionAdvisor(NextQuestionAdvisor):
    def __init__(
        self,
        provider: LLMProvider,
        *,
        timeout_seconds: float = 20.0,
        max_tokens: int = 512,
    ):
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens

    async def analyze(self, *, answered_question, answer_text, shortlist, history,
                      founder_brief=""):
        if not shortlist:
            return None
        request = self._build_request(answered_question, answer_text, shortlist,
                                      history, founder_brief)
        try:
            response = await asyncio.wait_for(
                self.provider.generate(request), timeout=self.timeout_seconds
            )
        except (LLMProviderError, asyncio.TimeoutError) as exc:
            logger.warning(
                "next-question advisor failed; using deterministic pick",
                extra={"stage": "adaptive_questions"},
                exc_info=exc,
            )
            return None
        return self._parse(response.text)

    # --- prompt -----------------------------------------------------------

    def _build_request(self, answered_question, answer_text, shortlist, history,
                       founder_brief: str = "") -> LLMRequest:
        options = "\n".join(
            f"- id {q.question_id} [{q.category}] {q.question_text}" for q in shortlist
        )
        hist = (
            "\n".join(f"Q: {qt}\nA: {at}" for qt, at in history) if history else "(none yet)"
        )
        system = (
            "You are guiding a startup founder's diagnostic interview. Read the "
            "founder's latest answer and classify it. "
            # THE N/A CASE, and why this now uses the fourth label rather than
            # Amber.
            #
            # session_01J2N7sy5i6pf8RBY96jGBtU found this bug and fixed it by
            # scoring N/A as Amber, for a stated reason: "There is no
            # not_applicable in _VALID_LABELS, and adding one reaches the stored
            # classifier, category risk, pillar banding and the report."
            #
            # That reasoning was right about the blast radius and wrong about the
            # blast: every one of those readers was already built for the fourth
            # band and handles it correctly. diagnostic.py excludes
            # NOT_APPLICABLE from BOTH the numerator and the denominator of the
            # pillar score, symptom_detection.py does not count it as a symptom,
            # root_cause.py never turns it into evidence, and _LABEL_TO_SCORE
            # maps it to None rather than zero.
            #
            # What actually blocked it was narrower and invisible:
            # answers.score_label was varchar(10) and 'not_applicable' is
            # fourteen characters, so migration c7d18a3f420b added the value to
            # the CHECK constraint but never widened the column. Every write
            # failed with StringDataRightTruncation and took the whole session
            # down with a 500. Migration d4a91c7e2b83 widens it.
            #
            # With the column fixed, the fourth label is the better answer:
            # Amber still carries score 1, so an inapplicable question still
            # drags the pillar it landed in downwards. NOT_APPLICABLE is
            # excluded from the denominator, which is the treatment "this does
            # not apply to my business" actually deserves. The instruction text
            # below is kept almost verbatim from that session's fix -- it is
            # specific and well chosen -- with the band changed.
            "An answer that says the question does not apply to this business -- "
            "\"N/A\", \"we don't have that\", \"there is no free tier\" -- is NOT "
            "avoidance and must NEVER be Red. Label it not_applicable: it is a "
            "true statement about the business, not a failure to answer, and that "
            "band is excluded from the diagnosis rather than counted against "
            "them. Judge it Red only when the founder dodges a question that DOES "
            "apply to them. "
            "Then choose which of the CANDIDATE questions to ask next -- "
            "the one that will most improve the diagnosis given what they just said "
            "(e.g. probe deeper on a weak/avoidant answer, move on after a strong one). "
            "FOUNDER CONTEXT, when present, is what onboarding already established "
            "about them -- their stage, what they are building, the problem they came "
            "in with, how they operate. Use it: prefer a candidate that fits THIS "
            "founder's situation, and do not spend a question re-establishing "
            "something they have already told us. "
            "You MUST pick next_question_id from the candidate ids listed; never invent "
            "one.\n"
            # This rubric is deliberately the same one
            # reasoning/engines/diagnostic.py uses for the stored classifier.
            # It used to be a single parenthetical here -- "Green = concrete
            # evidence/ownership" -- and that was measurably too generous.
            # On a keyed run, of eight answers a human author had graded weak,
            # this advisor returned FOUR green: among them "No. Every demo is
            # me. I've tried to write down what I say but it's still in my
            # head, so if I'm not on the call there is no call", which
            # describes total founder dependency, and "Zero paid, zero
            # committed." The old wording rewarded candour and specificity
            # instead of judging what the answer said about the business.
            "CLASSIFY BY SEMANTIC STATE FIRST. These are distinct and must not "
            "be collapsed:\n"
            "  POSITIVE_EVIDENCE   -- the thing asked about is in good shape, "
            "and the answer shows it with specifics.\n"
            "  NEGATIVE_EVIDENCE   -- the thing asked about is weak, missing or "
            "unmanaged.\n"
            "  UNKNOWN/NOT_MEASURED -- the thing EXISTS for this business but "
            "the founder does not track or know it.\n"
            "  NOT_APPLICABLE      -- the thing asked about is not part of how "
            "this business works at all.\n"
            "  AMBIGUOUS           -- partial or mixed.\n"
            "Then map the state to a label:\n"
            "- green: POSITIVE_EVIDENCE.\n"
            "- amber: AMBIGUOUS.\n"
            "- red: NEGATIVE_EVIDENCE, or UNKNOWN/NOT_MEASURED -- not knowing "
            "something your business depends on IS a real gap.\n"
            "- not_applicable: NOT_APPLICABLE only. It carries NO score and is "
            "excluded from the diagnosis rather than counted against the "
            "founder.\n"
            "NOT_APPLICABLE IS NARROW. Use it ONLY when the subject genuinely "
            "does not exist in this business -- free-plan questions to a "
            "business with no free tier, hiring questions to a founder with no "
            "employees, app-onboarding questions to a company with no app. It "
            "is NOT for something they simply have not built yet, do not "
            "measure, or would rather not answer: those are red or amber.\n"
            "SPECIFICITY IS NOT HEALTH. An articulate, honest, self-aware "
            "account of a problem is still a problem. Judge WHAT THE ANSWER "
            "DESCRIBES about the business, not how well it is expressed. "
            "\"Every demo is me, so if I am not on the call there is no call\" "
            "is specific, honest and owned -- and it is NEGATIVE_EVIDENCE, so "
            "it is red. \"Zero paid, zero committed\" is an admirable admission "
            "and still red. Reserve green for answers describing something that "
            "is actually working.\n"
            "Also judge whether the answer is RESPONSIVE: whether it is an attempt "
            "to answer THIS question at all, as opposed to text about a different "
            "topic, the question pasted back, or filler. Judge TOPIC ONLY, never "
            "quality -- a short answer, a vague answer, an uncomfortable admission "
            "and an explicit \"I don't know\" are all responsive, and belong in "
            "score_label rather than here. Set responsive=false ONLY when the "
            "answer does not engage with what was asked. When in doubt, true.\n"
            "Respond with a single JSON object and nothing else: "
            '{"score_label":"green|amber|red|not_applicable","confidence":0.0-1.0,'
            '"next_question_id":<candidate id>,"rationale":"one sentence",'
            '"responsive":true|false}'
        )
        # First, so the model reads who it is talking to before it reads what
        # they just said. Omitted entirely when empty rather than sent as a bare
        # header, which would read as "we checked and know nothing about them".
        brief = f"{founder_brief}\n\n" if founder_brief else ""
        user = (
            f"{brief}"
            f"Recent Q&A:\n{hist}\n\n"
            f"Just asked [{getattr(answered_question, 'category', '')}]: "
            f"{getattr(answered_question, 'question_text', '')}\n"
            f"Founder's answer: {answer_text}\n\n"
            f"CANDIDATE next questions (choose exactly one id):\n{options}"
        )
        return LLMRequest(
            messages=(
                LLMMessage(role=LLMRole.SYSTEM, content=system),
                LLMMessage(role=LLMRole.USER, content=user),
            ),
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
        )

    # --- parsing ----------------------------------------------------------

    def _parse(self, text: str) -> AnswerInsight | None:
        data = self._load_json(text)
        if not isinstance(data, dict):
            logger.warning("advisor response was not a JSON object; deterministic fallback")
            return None

        raw_label = str(data.get("score_label") or "").strip().lower()
        label = raw_label if raw_label in _VALID_LABELS else None

        nid = self._coerce_int(data.get("next_question_id"))
        confidence = self._coerce_confidence(data.get("confidence"))
        rationale = str(data.get("rationale") or "").strip()
        # Absent or non-boolean -> True. Only an explicit `false` rejects an
        # answer; see AnswerInsight.responsive for why this fails open.
        responsive = data.get("responsive") is not False
        return AnswerInsight(
            score_label=label, confidence=confidence, next_question_id=nid,
            rationale=rationale, responsive=responsive,
        )

    @staticmethod
    def _coerce_int(value) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().lstrip("-").isdigit():
            return int(value.strip())
        return None

    @staticmethod
    def _coerce_confidence(value) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _load_json(text: str):
        raw = text.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw[:4].lower() == "json":
                raw = raw[4:]
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            raw = raw[start : end + 1]
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return None
