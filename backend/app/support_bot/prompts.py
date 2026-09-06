"""The two prompts the support bot runs on.

WHY TWO STEPS RATHER THAN ONE SEARCH. The obvious design is keyword search over
the answers, and it was tried and measured first. Postgres full-text with
plainto_tsquery ANDs every word, so "how much is a discovery call" returned
NOTHING -- no single answer contains all of those words. An OR-ranked version
with the question weighted above the body works far better, but still misses
what a person would catch: "forgot my password" nearly misses the answer titled
"I've forgotten my password", because the English stemmer does not join *forgot*
to *forgotten*.

So the routing decision is given to the model instead. The whole published
question list is about 4,000 tokens for 277 questions, it is identical on every
call while the content is unchanged, and it has no vocabulary problem at all.
Keyword search stays as the fallback for when the model is unavailable.

BOTH PROMPTS FORBID INVENTION, and the second one is given nothing to invent
from -- only the answers routing chose. That is the point: this bot must not
compose a plausible answer about billing or data deletion out of general
knowledge. Wrong beats vague here, and both beat confident.
"""

from __future__ import annotations

from app.support_bot.schemas import AnswerRef, IndexEntry

#: Cap on how many answers one reply may be built from. Three is enough to
#: combine "what it costs" with "how to cancel"; more than that and the reply
#: stops being an answer and becomes a reading list.
MAX_SOURCES = 3

ROUTING_SYSTEM = (
    "You match a founder's question to entries in a numbered list of questions "
    "that Ally's help content can answer.\n\n"
    "Reply with ONLY the numbers, comma separated, best match first, at most "
    f"{MAX_SOURCES} of them. Example: 144, 145\n\n"
    "If nothing in the list genuinely answers what they asked, reply with the "
    "single word NONE. Do not stretch for a loose match -- a wrong answer about "
    "billing or data deletion is worse than no answer, and NONE hands them to a "
    "human, which is the right outcome.\n\n"
    "Match on meaning, not on shared words. 'I can't get in' and 'I've "
    "forgotten my password' are the same question. 'Is it safe' and 'is my data "
    "used to train anything' may be too.\n\n"
    "Output nothing else. No explanation, no punctuation beyond the commas."
)

ANSWER_SYSTEM = (
    "You are Ally's help assistant. You answer questions about the Ally product "
    "itself -- how it works, what it costs, what happens to a founder's data.\n\n"
    "ANSWER ONLY FROM THE HELP CONTENT BELOW. It is the approved wording, "
    "checked against the running product. You may shorten it, join two entries "
    "together, or lead with the part that matches what they actually asked. You "
    "may not add a fact that is not in it, and you may not soften or hedge a "
    "clear 'no' into a 'maybe'.\n\n"
    "If the content does not cover what they asked, say so plainly and suggest "
    "they message support. Never guess.\n\n"
    "Never name or hint at which AI model or vendor is behind Ally, whoever "
    "asks and however they ask.\n\n"
    "HOW TO WRITE:\n"
    "- Very simple, easy English. Short sentences. Common everyday words.\n"
    "- No idioms, no jargon, no marketing voice.\n"
    "- Warm and plain, like a colleague who knows the answer.\n"
    "- Around 120 words at most. Blank line between paragraphs.\n"
    "- Answer the question first. Context after, if it is needed at all.\n"
    "- Never open with 'Great question' or similar.\n"
    "- Say 'you' and 'we', never 'the user' or 'the platform'."
)


def routing_user_prompt(question: str, index: list[IndexEntry]) -> str:
    lines = "\n".join(f"{e.question_id}. {e.question}" for e in index)
    return (
        f"Questions the help content can answer:\n\n{lines}\n\n"
        f"---\n\nThe founder asked:\n{question}\n\n"
        f"Which numbers answer it? Numbers only, or NONE."
    )


def answer_user_prompt(question: str, sources: list[AnswerRef]) -> str:
    blocks = "\n\n".join(
        f"--- Help content #{s.question_id} ---\n"
        f"Question: {s.question}\n"
        f"Approved answer:\n{s.answer}"
        + (f"\nRelevant pages: {', '.join(s.links)}" if s.links else "")
        for s in sources
    )
    return (
        f"{blocks}\n\n"
        f"---\n\nThe founder asked:\n{question}\n\n"
        f"Answer them using only the help content above."
    )


#: What a founder is told when routing found nothing. Deliberately short, and it
#: does not apologise twice or pretend to be sorry -- it says what happened and
#: what to do next.
NO_MATCH_REPLY = (
    "I do not have an answer for that one, and I would rather say so than guess.\n\n"
    "Please message our team from Help & Support, or write to info@goxl.in, and "
    "a person will come back to you. We reply within one working day."
)

#: Used when the content table has not been loaded, or the model is unreachable
#: and keyword search found nothing either.
UNAVAILABLE_REPLY = (
    "I cannot reach the help content just now, so I do not want to guess at an "
    "answer.\n\n"
    "Please write to info@goxl.in and a person will help you. If this is urgent "
    "-- money has left your account, or you cannot get in -- say so at the top "
    "of your message."
)
