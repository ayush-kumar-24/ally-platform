"""Whether a chat turn should route to the reasoning-tier model (Claude) instead
of the fast default (see AIRequest.reasoning_required, AIRouter.route).

Deterministic, no extra LLM call -- a founder should not pay a second model call
just to find out which model answers their first one. Two gates, both required:

  1. Grounded data actually exists for this turn (a diagnosis, or real retrieval
     hits). Nothing to reason over otherwise, so a founder with no diagnosis yet
     always gets the cheap model regardless of what they ask.
  2. The message itself reads as a substantive ask -- a question, or long enough
     and touching a recognisable "help me think about my business" pattern --
     not small talk. A diagnosed founder saying "thanks" still gets the cheap
     model; the same founder asking "why do my demos keep stalling" does not.
"""

from __future__ import annotations

# Deliberately broad and lowercase-matched rather than a tight grammar: false
# positives (routing something borderline to the stronger model) cost a few
# cents; false negatives (a real strategic question landing on the fast model)
# cost the founder a worse answer. Bias toward the former.
_REASONING_SIGNAL_WORDS = (
    "why", "how do i", "how should i", "how can i", "what should",
    "help me", "advice", "recommend", "strategy", "improve", "fix",
    "root cause", "problem", "analyze", "analyse", "diagnos", "should i",
    "what's wrong", "what is wrong", "next step", "priorit", "figure out",
)

# Below this, a message is essentially a greeting/acknowledgement ("hi",
# "thanks!", "ok sounds good") whatever data happens to be available.
_MIN_SUBSTANTIVE_LENGTH = 8


def needs_reasoning(message: str, ally_context, window) -> bool:
    """`message` is the founder's raw text this turn. `ally_context` is the
    AllyContext built for this turn (or None); `window` is the built
    ConversationContextWindow, read for whether retrieval actually found
    anything -- not just whether it was attempted (retrieval_injected can be
    True with zero items on a fail-open degrade)."""
    if not _has_grounded_data(ally_context, window):
        return False
    return _reads_as_substantive(message)


def _has_grounded_data(ally_context, window) -> bool:
    has_diagnosis = bool(ally_context is not None and ally_context.has_diagnosis)
    retrieval = getattr(window, "retrieval", None)
    has_retrieval = bool(retrieval is not None and not retrieval.is_empty)
    return has_diagnosis or has_retrieval


def _reads_as_substantive(message: str) -> bool:
    text = (message or "").strip().lower()
    if len(text) < _MIN_SUBSTANTIVE_LENGTH:
        return False
    if text.endswith("?"):
        return True
    return any(word in text for word in _REASONING_SIGNAL_WORDS)
