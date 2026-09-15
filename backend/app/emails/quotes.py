"""Founder quotes for the emails Ally sends.

WHY A SECOND COPY OF SOMETHING THE FRONTEND ALSO HAS. The dashboard's quote
card reads frontend/src/data/quotes.js; email is sent from Python and cannot
import it. This is the superset -- all twenty of that file's lines plus thirty
more -- so the two never contradict each other on a line they share, and the
frontend can be pointed at a shared export later without anything here moving.

GROUPED BY TIME OF DAY, NOT POOLED, and the grouping is the frontend's,
deliberately: the same line does not land at 7am and at 11pm. Morning is for
starting, afternoon for staying with a hard thing, evening for closing the
loop, night for putting it down. A founder reading a reminder at midnight does
not need to be told to seize the day.

ATTRIBUTION IS THE FRONTEND'S RULE TOO. Only lines that are well documented as
a particular person's carry a name. Everything written for this product is
left unattributed rather than dressed in a plausible one -- a made-up
attribution in a founder's inbox is worse than no attribution, and inventing
one to fill the slot is exactly how that happens. Every line added here is
original and therefore unnamed; none of the thirty new ones invents a source.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Quote:
    text: str
    by: str = ""


#: Slot boundaries shared with the frontend's timeSlot() so a founder who sees
#: the dashboard card and an email in the same hour is not told two different
#: times of day.
QUOTES: dict[str, tuple[Quote, ...]] = {
    "morning": (
        Quote("The way to get started is to quit talking and begin doing.", "Walt Disney"),
        Quote("Make something people want.", "Paul Graham"),
        Quote("Start where you are. Use what you have. Do what you can.", "Arthur Ashe"),
        Quote("The hardest part of today is choosing what not to do."),
        Quote("One real conversation with a customer beats a morning of guessing."),
        Quote("The first hour is the only one nobody else has a claim on yet."),
        Quote("Pick the thing you are avoiding. That is usually the one that matters."),
        Quote("You do not need a better plan. You need to start the one you have."),
        Quote("Momentum is built, not found."),
        Quote("Ship something small before the day fills up."),
        Quote("A rough version today beats a perfect one next month."),
        Quote("Decide what today is for before someone else decides for you."),
        Quote("Every founder you admire started a morning exactly like this one."),
    ),
    "afternoon": (
        Quote("Ideas are easy. Implementation is hard.", "Guy Kawasaki"),
        Quote("Fall in love with the problem, not the solution."),
        Quote("The best way to predict the future is to invent it.", "Alan Kay"),
        Quote("The middle of the day is where most plans quietly get abandoned. Not today."),
        Quote("Slow progress on the right thing still beats fast progress on the wrong one."),
        Quote("Half done is not the same as failing. Keep going."),
        Quote("The work is boring in the middle. That is what the middle is."),
        Quote("If it is still hard after an hour, it is probably the right problem."),
        Quote("Do not trade the important thing for the urgent one twice in one day."),
        Quote("Progress you cannot see is still progress."),
        Quote("You are further along than you were at nine this morning."),
        Quote("One more honest hour beats three distracted ones."),
        Quote("The plan survives contact with the afternoon, or it was never a plan."),
    ),
    "evening": (
        Quote("If you are not embarrassed by the first version of your product, "
              "you've launched too late.", "Reid Hoffman"),
        Quote("It's not about ideas. It's about making ideas happen.", "Scott Belsky"),
        Quote("Write down what you learned today. Tomorrow you will think you already knew it."),
        Quote("A day where you moved one real thing forward was a good day."),
        Quote("Close the loop on one thing before you open another."),
        Quote("Finish the sentence you are on, then stop."),
        Quote("What went wrong today is tomorrow's advantage if you write it down."),
        Quote("You are building something that did not exist this morning."),
        Quote("Count what you moved, not what is left."),
        Quote("The list will be there tomorrow. So will you."),
        Quote("Good work compounds quietly. Today counted."),
        Quote("Ending the day on purpose is a skill. Practise it."),
    ),
    "night": (
        Quote("Amateurs sit and wait for inspiration, the rest of us just get up "
              "and go to work.", "Stephen King"),
        Quote("The company will still be here in the morning. Rest is part of the work."),
        Quote("Nothing you decide at 1am is better than what you would decide at 9am."),
        Quote("You are allowed to stop for the day with things unfinished. They always are."),
        Quote("Tomorrow needs you thinking clearly more than tonight needs one more hour."),
        Quote("Sleep is the cheapest performance improvement available to you."),
        Quote("No customer was ever won at 2am."),
        Quote("The problem looks smaller after seven hours of sleep. It usually is."),
        Quote("Put it down. It will keep."),
        Quote("Founders burn out quietly, one late night at a time."),
        Quote("You cannot out-work a tired brain. Stop."),
        Quote("Tomorrow is a working day too. Save something for it."),
    ),
}

#: Fifty across the four groups. Asserted rather than commented: a line added
#: to one group without the count being revisited should fail loudly at import,
#: not silently make "fifty quotes" a false statement in a changelog.
TOTAL = sum(len(group) for group in QUOTES.values())
assert TOTAL == 50, f"expected 50 quotes, found {TOTAL}"


def slot_for(moment: datetime) -> str:
    """Which group suits this hour. Boundaries match the frontend's timeSlot()."""
    hour = moment.hour
    if hour < 5:
        return "night"
    if hour < 12:
        return "morning"
    if hour < 18:
        return "afternoon"
    if hour < 22:
        return "evening"
    return "night"


def _index(founder_id: int | None, moment: datetime, kind: str, size: int) -> int:
    seed = f"{founder_id}|{moment.date().isoformat()}|{kind}"
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % size


def quote_for(*, founder_id: int | None, moment: datetime, kind: str = "",
              avoid_kinds: tuple[str, ...] = ()) -> Quote:
    """The line this founder gets on this email.

    DETERMINISTIC, NOT RANDOM, and that is the point. Two founders receiving
    the same reminder in the same minute see different lines -- which is what
    "random to each person" actually asks for -- while the same founder gets a
    stable answer for a given day and email type, so a test can assert exactly
    which line comes out. random.choice() can do neither.

    `kind` separates the emails: without it every email a founder got on one
    day would carry the same line.

    `avoid_kinds` IS WHAT MAKES THAT RELIABLE RATHER THAN LIKELY. Hashing
    `kind` into the seed makes a collision unlikely, not impossible -- with
    thirteen lines in a group, two independent hashes land on the same one
    about once in thirteen, which a founder would notice on the two emails one
    task produces. Because selection is deterministic, a later email can
    RECOMPUTE what an earlier one picked and drop it from the running, even
    though the two are sent hours apart by different processes with nothing
    shared between them. That is worth more here than the theoretical purity of
    a single hash.

    The moment is expected in the FOUNDER'S local time, so the slot matches the
    clock they are looking at rather than UTC. If the two emails fall in
    different slots the exclusion is moot, and harmless.
    """
    group = QUOTES[slot_for(moment)]
    taken = {group[_index(founder_id, moment, other, len(group))].text
             for other in avoid_kinds}
    # Never exclude everything: a group smaller than the avoid list would leave
    # nothing to pick, and an email with no quote is worse than a repeated one.
    candidates = tuple(q for q in group if q.text not in taken) or group
    return candidates[_index(founder_id, moment, kind, len(candidates))]
