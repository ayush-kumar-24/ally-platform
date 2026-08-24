"""Balance the free report's 3+3 action plan.

`GoXL_Stage_Adaptive_Diagnosis_Framework_2.docx` s6 defines the free tier as
"one diagnosed root cause with a 3+3 action plan (3 lines to confirm/isolate
the problem further, 3 lines to solve it)", and every one of its three example
reports shows both halves filled. The engine cannot produce that shape.

StandardRecommendationEngine types a recommendation SOLVE when its lead
supporting cause is CONFIRMED and CONFIRM otherwise. That is a coherent rule
for a RANKED LIST of causes -- confirm the ones still in doubt, solve the ones
that are settled. But the free report diagnoses exactly ONE cause, so every
recommendation in it shares a lead cause and therefore a type: all CONFIRM or
all SOLVE, never both. Reproduced live on goxlally.ai -- an unconfirmed lead
cause produced three confirm lines and zero solve lines, and the founder read a
report with half its plan missing and no indication anything was absent.

The split the doc wants is a property of the ACTION, not of the cause: "track
how many days this month were spent reading versus talking to a real person"
confirms, "give yourself a 7-day deadline" solves, and both belong to the same
diagnosis. Nothing in the schema carries that distinction -- interventions have
`section` (a business domain) and `capability_domain` (free text, ~400 distinct
values across 416 rows), neither of which separates measuring from changing --
so it cannot be derived deterministically from the curated library as it
stands. Labelling `immediate_next_steps` per line would be the data fix and is
content work, not a code change.

What this does instead, and what it deliberately does not do:

* Curated lines are NEVER discarded, rewritten or reordered. They are assigned
  to the side they belong to, and only the SHORTFALL is authored. A reviewed
  intervention line always outranks a generated one, the same rule
  LLMRecommendationFallback follows for whole recommendations.

* It never runs when both sides already hold three lines, so a report the
  library can fill on its own costs nothing.

* On any failure -- provider error, timeout, malformed JSON, too few lines
  back -- it returns its input untouched. The worst case is the lopsided plan
  that ships today.

Gated on its own flag, default off, for the same reason RECOMMENDATION_FALLBACK_LLM
is: this puts founder-facing advice on the page with no reviewed intervention
behind it. That should be switchable on its own and off by default, not folded
into a general diagnosis flag.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence

from app.core.logger import logger
from app.services.llm.base import LLMError, LLMMessage, LLMRequest, LLMRole
from app.services.llm.text import run_sync

#: The doc's 3+3. Mirrors _ACTION_LINES_PER_SIDE in reports/generator.py, which
#: caps what is rendered; this decides what is available to render.
LINES_PER_SIDE = 3

_SYSTEM = (
    "You complete a founder's action plan. It has two halves for ONE diagnosed "
    "problem: CONFIRM lines, which help the founder verify the diagnosis is "
    "really theirs by observing or measuring what is actually happening; and "
    "SOLVE lines, which change something. "
    "A confirm line asks them to look, count, ask or track. A solve line asks "
    "them to decide, stop, commit or hand off. "
    "You are given the lines that already exist and which half each belongs to. "
    "Keep every existing line EXACTLY as written -- never reword, merge or drop "
    "one. Write only the lines still missing. "
    "Each new line is one concrete action this founder could start this week, "
    "in second person, under 20 words, specific to their situation and never "
    "generic advice. "
    'Reply with JSON only: {"confirm": ["..."], "solve": ["..."]} -- each array '
    "holding the COMPLETE half including the existing lines, in order."
)


class LLMActionPlanBalancer:
    """Fills the empty half of the 3+3 plan. Never touches the filled one."""

    def __init__(self, provider, *, timeout_seconds: float = 25.0,
                 temperature: float = 0.3):
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature

    def balance(
        self,
        confirm: Sequence[str],
        solve: Sequence[str],
        *,
        root_cause: str | None = None,
        stage_name: str | None = None,
        evidence: Sequence[str] = (),
    ) -> tuple[list[str], list[str]]:
        """(confirm, solve), each up to LINES_PER_SIDE. Input is returned
        unchanged whenever balancing is unnecessary or fails."""
        have_confirm = [c for c in confirm if c and c.strip()][:LINES_PER_SIDE]
        have_solve = [s for s in solve if s and s.strip()][:LINES_PER_SIDE]

        if len(have_confirm) >= LINES_PER_SIDE and len(have_solve) >= LINES_PER_SIDE:
            return have_confirm, have_solve
        if not have_confirm and not have_solve:
            # Nothing diagnosed to build on. Authoring both halves from the root
            # cause name alone would be advice with no evidence behind it at all,
            # which is further than this is meant to go.
            return have_confirm, have_solve

        try:
            payload = self._ask(have_confirm, have_solve, root_cause, stage_name, evidence)
            return self._merge(payload, have_confirm, have_solve)
        except (LLMError, asyncio.TimeoutError, json.JSONDecodeError,
                ValueError, TypeError, KeyError, AttributeError) as exc:
            logger.warning(
                "Action-plan balancing failed; leaving the plan as the library built it",
                extra={"error": str(exc), "confirm": len(have_confirm),
                       "solve": len(have_solve)},
            )
            return have_confirm, have_solve

    # --- internals ---------------------------------------------------------

    def _ask(self, confirm, solve, root_cause, stage_name, evidence) -> dict:
        def _block(label: str, lines: Sequence[str]) -> str:
            body = "\n".join(f"- {line}" for line in lines) or "- (none yet)"
            return f"{label} lines that already exist:\n{body}"

        context_bits = []
        if root_cause:
            context_bits.append(f"Diagnosed problem: {root_cause}")
        if stage_name:
            context_bits.append(f"Founder's stage: {stage_name}")
        if evidence:
            quoted = "\n".join(f"- {e}" for e in list(evidence)[:6])
            context_bits.append(f"From the founder's own answers:\n{quoted}")

        request = LLMRequest(
            messages=(
                LLMMessage(role=LLMRole.SYSTEM, content=_SYSTEM),
                LLMMessage(
                    role=LLMRole.USER,
                    content=(
                        "\n\n".join(context_bits)
                        + f"\n\n{_block('CONFIRM', confirm)}"
                        + f"\n\n{_block('SOLVE', solve)}"
                        + f"\n\nReturn {LINES_PER_SIDE} lines in each half."
                    ),
                ),
            ),
            temperature=self.temperature,
            max_tokens=600,
            response_format={"type": "json_object"},
        )
        # run_sync rather than asyncio.run: this runs inside
        # ReasoningService.analyze_session, already on a live event loop. Same
        # note as archetype_llm.py, where a bare asyncio.run raised "cannot be
        # called from a running event loop" every time.
        response = run_sync(
            asyncio.wait_for(self.provider.generate(request), self.timeout_seconds)
        )
        return json.loads(response.text)

    def _merge(self, payload: dict, have_confirm: list[str], have_solve: list[str]):
        """Existing lines first and verbatim; generated ones only fill behind them.

        Rebuilt from `have_*` rather than trusting the reply's copy of them, so a
        model that quietly reworded a curated line cannot get that edit onto the
        page -- the reply is read ONLY for lines that are genuinely new.
        """
        merged = []
        for side, existing in (("confirm", have_confirm), ("solve", have_solve)):
            returned = payload.get(side)
            fresh: list[str] = []
            if isinstance(returned, list):
                kept = list(existing)
                for item in returned:
                    if not isinstance(item, str):
                        continue
                    line = item.strip()
                    if not line or _is_restatement(line, kept + fresh):
                        continue
                    fresh.append(line)
            merged.append((list(existing) + fresh)[:LINES_PER_SIDE])
        return merged[0], merged[1]


#: Share of the SHORTER line's distinctive words that must also appear in the
#: other before the two count as the same instruction.
#:
#: Exact matching is not enough on its own. The model is told to echo existing
#: lines verbatim; when it lightly rewords one instead, an exact check reads the
#: reworded copy as NEW and the founder gets the same action twice in slightly
#: different words. Caught by test_a_curated_line_is_never_reworded.
_RESTATEMENT_OVERLAP = 0.6

#: Containment (shared / shorter), not Jaccard. The failure mode is a line that
#: RESTATES another more briefly or more verbosely, and Jaccard punishes exactly
#: that: the live example -- "Count the days spent reading versus talking to a
#: customer." against a truncated rewrite of it -- scores 0.36 by Jaccard and
#: 0.67 by containment. Only the second reads it as the duplicate it is.

#: Dropped before comparing, because they are shared by almost any two
#: instructions and inflate containment on short lines -- without this,
#: "Set a deadline." and "Give yourself a 7-day deadline." collide on "a".
_IGNORED_WORDS = frozenset({
    "a", "an", "and", "the", "to", "of", "in", "on", "for", "by", "with",
    "your", "you", "yourself", "it", "this", "that", "is", "are", "be",
})


def _tokens(line: str) -> set[str]:
    """Distinctive lowercase words, punctuation stripped."""
    words = "".join(
        c if c.isalnum() or c.isspace() else " " for c in line.casefold()
    ).split()
    return {w for w in words if w and w not in _IGNORED_WORDS}


def _is_restatement(line: str, existing: Sequence[str]) -> bool:
    """Whether `line` says what one of `existing` already says.

    Crude, and the right kind of crude: a false positive costs one generated
    line that never appears, a false negative costs the founder reading the
    same instruction twice in the plan they were handed.
    """
    new = _tokens(line)
    if not new:
        return True  # nothing distinctive left; not worth a slot
    for other in existing:
        prior = _tokens(other)
        if not prior:
            continue
        shared = len(new & prior)
        if shared / min(len(new), len(prior)) >= _RESTATEMENT_OVERLAP:
            return True
    return False
