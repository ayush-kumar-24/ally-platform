"""FOUNDER ANSWER -> CAPABILITY EVIDENCE. An observation, never an assessment.

WHAT THIS MODULE DOES, EXACTLY: given one answer to one capability-mapped
question, decide whether the answer confidently supports a specific level of
that ONE capability (question_capabilities: at most one, per Step 7A), and if
so, record ONE observation. It does not score a capability, does not compare
anything to a requirement, does not rank root causes, and is never the sole
determinant of anything downstream -- Step 7C reads these rows later and
decides how to combine them; this module never combines them itself.

NO EVIDENCE IS NOT LEVEL 0. `extract()` returns None -- not a CapabilityLevel,
not a wrapped "level 0 with low confidence" -- whenever the answer does not
confidently support a specific level. The caller stores nothing on None. This
is the same shape `founder_context.verdict()` and `capability_levels.
is_assessed()` already use: absence is a real state, and it is never spelled
with a number.

FAIL-OPEN, LIKE THE ADVISOR. `LLMCapabilityEvidenceExtractor` is optional
(`CapabilityEvidenceExtractor | None` at every call site) and any failure --
timeout, malformed JSON, an out-of-range level, a criterion_id that does not
belong to the capability offered -- returns None rather than raising. An
extraction failure costs a data point, never a founder's diagnosis; the
question was already answered and scored before this module ever runs.

THE LLM DOES FOUR THINGS AND NO MORE, matching the step brief's own contract
exactly:

    evidence_present   bool
    criterion_id        one of the ids OFFERED, or null
    observed_level      0-3, or null
    evidence_text       one sentence
    confidence          0.0-1.0

It is never told about other capabilities, never asked to invent a criterion,
never asked to compute a level over multiple answers, and never asked about a
target, a gap, or a recommendation. The prompt lists ONLY the criteria of the
ONE capability this question is mapped to -- there is no path for the model to
reach for a different capability, because it is never shown one.

DETERMINISTIC DATA STAYS DETERMINISTIC. Which capability a question maps to,
which criteria that capability has, and whether a returned criterion_id is
legitimate are ALL decided by `question_capabilities` and
`capability_evidence_criteria` -- data the LLM never writes and this module
never lets it override. A criterion_id outside the offered set is treated as
absent, not substituted or corrected.
"""

from __future__ import annotations

import abc
import asyncio
import json
from dataclasses import dataclass
from typing import Sequence

from app.api.v1.diagnosis.capability_levels import CapabilityLevel
from app.core.logger import logger
from app.services.llm import LLMMessage, LLMProvider, LLMProviderError, LLMRequest, LLMRole

#: Below this, the extractor's own uncertainty is the reason to store nothing --
#: not a defect in the model's answer. A hedge is not evidence. Set well above
#: zero deliberately: "no fabricated evidence" (case 9) means the bar for
#: STORING is high, even though the bar for ATTEMPTING is just "the question is
#: mapped and was answered".
#:
#: PUBLIC (no leading underscore) because Step 7C's aggregation reuses this
#: EXACT number as its participation floor -- see capability_assessment.py.
#: Every row that exists in `capability_evidence` already cleared this bar at
#: write time, so in today's single-writer system the floor at aggregation time
#: is a belt, not the buckle: it is what stops a future or alternate writer
#: (there is no DB CHECK requiring >= this, only >= 0) from smuggling a hedge
#: into the current-state read. Reusing the constant, not a second number, is
#: what makes the threshold "justified from existing Step 7B semantics" rather
#: than arbitrary.
MIN_CONFIDENCE = 0.6


@dataclass(frozen=True)
class CapabilityEvidenceObservation:
    """What the extractor found, before persistence. Mirrors AnswerInsight's
    shape: an immutable read, not a write -- the repository does the writing."""

    capability_id: int
    observed_level: CapabilityLevel
    evidence_text: str
    confidence: float
    criterion_id: int | None = None


class CapabilityEvidenceExtractor(abc.ABC):
    @abc.abstractmethod
    async def extract(
        self,
        *,
        question_text: str,
        answer_text: str,
        capability_id: int,
        capability_name: str,
        criteria: Sequence[dict],
    ) -> CapabilityEvidenceObservation | None:
        """Read one answer against one capability's criteria. Returns None on
        any failure or whenever the answer does not confidently support a
        specific level -- never a guessed level, never level 0 for silence."""
        raise NotImplementedError


class LLMCapabilityEvidenceExtractor(CapabilityEvidenceExtractor):
    def __init__(
        self, provider: LLMProvider, *, timeout_seconds: float = 15.0, max_tokens: int = 320,
    ):
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens

    async def extract(self, *, question_text, answer_text, capability_id,
                      capability_name, criteria):
        if not answer_text or not answer_text.strip():
            return None
        request = self._build_request(question_text, answer_text, capability_name, criteria)
        try:
            response = await asyncio.wait_for(
                self.provider.generate(request), timeout=self.timeout_seconds
            )
        except (LLMProviderError, asyncio.TimeoutError) as exc:
            logger.warning(
                "capability evidence extraction failed; storing nothing",
                extra={"stage": "capability_evidence", "capability_id": capability_id},
                exc_info=exc,
            )
            return None
        return self._parse(response.text, capability_id=capability_id, criteria=criteria)

    # --- prompt -------------------------------------------------------------

    def _build_request(self, question_text, answer_text, capability_name, criteria) -> LLMRequest:
        criteria_lines = "\n".join(
            f'- id {c["criterion_id"]}: {c["criterion_text"]}' for c in criteria
        ) or "(no specific criteria offered -- judge the capability as a whole)"
        system = (
            "You extract OBSERVABLE EVIDENCE about one business capability from one "
            "founder's answer to one diagnostic question. You are not diagnosing, "
            "scoring risk, or writing advice -- you are reporting what the answer "
            "DIRECTLY says, nothing it merely implies or that would follow as a "
            "consequence.\n"
            f"THE CAPABILITY: {capability_name}\n"
            "ITS EVIDENCE CRITERIA (you may cite AT MOST ONE, by id, or none):\n"
            f"{criteria_lines}\n\n"
            "LEVELS -- what the answer shows about who this capability depends on:\n"
            "  0 ABSENT      the thing does not happen at all, explicitly\n"
            "  1 PERSONAL    it happens, but only because the founder personally "
            "does it\n"
            "  2 DOCUMENTED  it exists outside the founder's head (written down, "
            "a defined process) but is not described as owned by someone else\n"
            "  3 OWNED       someone other than the founder owns and runs it\n\n"
            "RULES, followed exactly:\n"
            "- evidence_present=false whenever the answer does not DIRECTLY speak "
            "to this capability -- off-topic, evasive, 'I don't know', or about a "
            "different subject. This is the common case; do not strain to find "
            "evidence that is not there.\n"
            "- NEVER infer a level from a consequence or a feeling. 'I'm stressed "
            "about sales' is not evidence of a level. 'I close every deal myself' "
            "is level 1.\n"
            "- NEVER use level 0 for silence, an unmentioned capability, or your "
            "own uncertainty. Absence of evidence is evidence_present=false, not "
            "level 0. Level 0 is reserved for the answer EXPLICITLY stating the "
            "thing does not exist.\n"
            "- cite a criterion_id only when the answer speaks to THAT specific "
            "criterion; use null when it speaks to the capability more generally.\n"
            "- confidence reflects how sure you are of THIS reading, not how "
            "healthy the capability sounds.\n"
            "- If in doubt, evidence_present=false. A missed observation costs "
            "nothing; a fabricated one contaminates every later use of this data.\n"
            "Respond with a single JSON object and nothing else: "
            '{"evidence_present":true|false,"criterion_id":<id or null>,'
            '"observed_level":0|1|2|3|null,"evidence_text":"one sentence",'
            '"confidence":0.0-1.0}'
        )
        user = f"Question asked: {question_text}\nFounder's answer: {answer_text}"
        return LLMRequest(
            messages=(
                LLMMessage(role=LLMRole.SYSTEM, content=system),
                LLMMessage(role=LLMRole.USER, content=user),
            ),
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
        )

    # --- parsing --------------------------------------------------------------

    def _parse(self, text: str, *, capability_id: int, criteria: Sequence[dict],
              ) -> CapabilityEvidenceObservation | None:
        data = self._load_json(text)
        if not isinstance(data, dict):
            logger.warning("evidence extractor response was not a JSON object")
            return None

        if data.get("evidence_present") is not True:
            return None                                   # includes False, missing, junk

        level = self._coerce_level(data.get("observed_level"))
        if level is None:
            # evidence_present=true with no usable level is a malformed response,
            # not "level unknown" -- there is no such state to store.
            return None

        confidence = self._coerce_confidence(data.get("confidence"))
        if confidence < MIN_CONFIDENCE:
            return None                                    # a hedge is not evidence

        criterion_id = self._coerce_criterion(data.get("criterion_id"), criteria)

        evidence_text = str(data.get("evidence_text") or "").strip()
        if not evidence_text:
            return None                                    # nothing to show a founder later

        return CapabilityEvidenceObservation(
            capability_id=capability_id,
            observed_level=level,
            evidence_text=evidence_text[:500],
            confidence=confidence,
            criterion_id=criterion_id,
        )

    @staticmethod
    def _coerce_level(value) -> CapabilityLevel | None:
        if isinstance(value, bool):
            return None
        try:
            level = int(value)
        except (TypeError, ValueError):
            return None
        if level not in (0, 1, 2, 3):
            return None
        return CapabilityLevel(level)

    @staticmethod
    def _coerce_confidence(value) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, confidence))

    @staticmethod
    def _coerce_criterion(value, criteria: Sequence[dict]) -> int | None:
        """A criterion the model named, but ONLY if it is one we actually
        offered for THIS capability. Never trust an id back from the model
        without checking it against the deterministic list that was sent --
        the taxonomy is authoritative, not the LLM's memory of it."""
        if value is None:
            return None
        try:
            criterion_id = int(value)
        except (TypeError, ValueError):
            return None
        offered = {c["criterion_id"] for c in criteria}
        return criterion_id if criterion_id in offered else None

    @staticmethod
    def _load_json(text: str):
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            stripped = (text or "").strip()
            if stripped.startswith("```"):
                stripped = stripped.strip("`")
                stripped = stripped[stripped.find("{"):stripped.rfind("}") + 1]
                try:
                    return json.loads(stripped)
                except (json.JSONDecodeError, TypeError):
                    return None
            return None
