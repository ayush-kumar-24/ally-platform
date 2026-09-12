"""Estimating what a turn will cost, BEFORE it is spent.

WHY THIS EXISTS. The daily ceiling used to be enforced with one test -- `used <
limit` -- and the real cost was only charged after the model had replied,
because the true count does not exist until the answer does. That admitted any
request from a founder with a single token left, and a founder at 7,516 of
8,000 could land at 9,894: measured live, 2,378 tokens past a ceiling they had
already been told they were near. They then saw "484 tokens left today" beside
"Daily limit reached (9,894 of 8,000)" and had no way to read either number.

So the turn is now priced before it runs. The prompt exists by then -- it has
been assembled and rendered -- so the only unknown is the reply, and that is
bounded by the max_tokens the router asks for. Prompt + reply cap against what
is left is a number we can check, and a turn that cannot fit is refused without
calling the provider at all: no spend, no overshoot, and the founder is told
what was needed rather than being handed a wall with a contradiction on it.

ON THE ESTIMATE BEING AN ESTIMATE. There is no shared tokeniser here: chat
routes across three providers (see app/services/llm/providers) and each counts
slightly differently, so any exact count would be right for one and wrong for
the other two. A character heuristic is used instead, deliberately biased to
OVER-estimate: under-estimating would let exactly the overshoot this module
exists to prevent back in, while over-estimating only refuses a turn slightly
earlier than strictly necessary -- visible, explainable, and recoverable at
midnight. The meter itself is never estimated; it still records what the
provider actually charged.
"""

from __future__ import annotations

import math

#: Characters per token. English averages ~4 across these providers; 3.5 prices
#: a turn ~14% above that on purpose (see the module docstring on the direction
#: of the bias). Code, JSON and non-Latin scripts tokenise denser than prose,
#: and the founder context this app sends carries all three.
_CHARS_PER_TOKEN = 3.5


def estimate_tokens(*texts: str | None) -> int:
    """Roughly how many tokens these strings will cost, rounded up.

    Takes several strings because a prompt is a system part and a user part and
    both are billed; summing the characters before dividing avoids rounding each
    fragment up separately, which would drift by the number of fragments.
    """
    chars = sum(len(t) for t in texts if t)
    return math.ceil(chars / _CHARS_PER_TOKEN)


def turn_cost_estimate(system: str | None, user: str | None, reply_cap: int) -> int:
    """What one turn could cost at worst: the prompt, plus the whole reply cap.

    The reply is priced at its ceiling rather than at anything typical. A budget
    check is only worth making if the answer it gives holds for the turn that
    actually happens, and the only reply length guaranteed not to be exceeded is
    the one the provider was told not to exceed.
    """
    return estimate_tokens(system, user) + max(0, reply_cap)
