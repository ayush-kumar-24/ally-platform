"""The Help & Support bot.

Answers questions about the Ally PRODUCT -- what it costs, how the diagnosis
works, what happens to a founder's data -- from 277 published answers held in
`support_bot_answers`. It does not answer questions about the founder's
business; that is Ally chat, and the two are deliberately separate.

Three properties this module is built around, in order of importance:

1. **It cannot invent.** Every reply is composed from published answers and
   nothing else. The routing step chooses from a list; the answering step is
   given only what routing chose. A bot that improvises about billing or data
   deletion is worse than one that says "I don't know" -- so when nothing
   matches, it hands over to a person rather than reaching.

2. **It never costs the founder anything.** Ally chat meters against a daily
   token allowance. Charging someone to ask "how do I cancel" would be
   indefensible, so this runs unmetered and is protected by a per-founder rate
   limit instead.

3. **It degrades instead of failing.** Content not loaded, model unreachable,
   routing empty -- each has a defined, honest fallback ending in "message a
   person", never a 500 and never a guess.

    schemas.py     domain DTOs. `finding` and `note` are absent by design.
    repository.py  reads over the table. Every query filters is_published.
    prompts.py     the two prompts, and the fallback replies.
    service.py     the flow, the fallbacks, and the rate limit.
"""

from app.support_bot.schemas import AnswerRef, FaqEntry, IndexEntry, SupportReply
from app.support_bot.service import SupportBotService, build_support_bot_service

__all__ = [
    "AnswerRef",
    "FaqEntry",
    "IndexEntry",
    "SupportReply",
    "SupportBotService",
    "build_support_bot_service",
]
