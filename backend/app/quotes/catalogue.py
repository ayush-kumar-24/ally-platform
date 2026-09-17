"""The lines a founder might read on their own dashboard and think "that's me".

WHAT THIS IS FOR. The quote card used to pick by day-of-year and time-of-day and
nothing else, so every founder on the platform read the same line at the same
moment. The point of this catalogue is that a founder at ideation with no
customers yet and a founder at growth with a hiring problem should not be handed
the same sentence.

NOBODY IS QUOTED HERE, DELIBERATELY. Every line is written for this product and
carries no attribution, because the purpose is recognition, not authority -- the
founder should think "this is my thing", not "ah, someone said that". It also
removes the only way this could go badly wrong: a real person's name under a
line they never said.

EVERY LINE IS TIME-NEUTRAL, and that is a real constraint on what can be written
here. A founder's two lines are chosen once at midnight and stay put all day, so
anything that assumes an hour -- "start the day with", "before you sleep" --
would be wrong for most of the time it is on screen. The card used to rotate
four times a day; it did that because day-of-year and clock were the only
signals it had. It has the founder's actual situation now, which is a better
one.

HOW A LINE GETS CHOSEN. `stages` and `themes` are what a line is ABOUT. The
selector narrows the catalogue to the lines that fit a founder's situation, and
the model picks two from that shortlist -- it never writes one. See service.py.

TAGGING RULES, so this stays consistent as it grows:
  * `stages=ANY` means the line lands whatever stage they are at. Use it freely;
    a catalogue where everything is stage-specific leaves narrow founders with
    nothing to read.
  * `themes` is what the founder is FEELING or FACING, not what the line is
    grammatically about. "The idea felt obvious yesterday" is tagged `doubt`,
    not `ideas`.
  * A line that would read as advice from a stranger does not belong here.
    These are for recognition. Instructions live elsewhere in the product.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Lifecycle stages, as the founder_stages table names them, lowercased and
#: hyphenated. `ANY` is the wildcard.
STAGES = ("ideation", "validation", "prototype", "early-traction", "growth")
ANY: tuple[str, ...] = ()

#: What a founder is facing. Kept small on purpose -- twenty themes would make
#: the shortlist too narrow and the tagging too arbitrary to stay consistent.
THEMES = (
    "focus", "doubt", "decisions", "customers", "execution",
    "momentum", "rest", "resilience", "money", "team",
)


@dataclass(frozen=True)
class Quote:
    """One line. `stages=ANY` (the default) means it fits any stage."""

    id: str
    text: str
    themes: tuple[str, ...]
    stages: tuple[str, ...] = field(default=ANY)


QUOTES: tuple[Quote, ...] = (
    # ---- doubt ---------------------------------------------------------------
    Quote("obvious-again", "The idea felt obvious yesterday. It will feel obvious again once you start.",
          ("doubt",), ("ideation", "validation")),
    Quote("first-version", "Nobody's first version made sense to anyone else either.",
          ("doubt",), ("ideation", "prototype")),
    Quote("middle-vs-announcement", "Comparing your middle to somebody else's announcement is not information.",
          ("doubt",)),
    Quote("doubt-not-new", "The doubt is not new information. It has been saying the same thing for months.",
          ("doubt",)),
    Quote("quiet-not-wrong", "Quiet is not the same as wrong. Most of this work happens with nobody watching.",
          ("doubt", "resilience")),

    # ---- focus ---------------------------------------------------------------
    Quote("one-thing", "You already know the one thing this week is actually about.",
          ("focus",)),
    Quote("short-list", "A short list you finish beats a long list you abandon.",
          ("focus",)),
    Quote("hardest-part", "The hardest part is not choosing what to do. It is choosing what not to.",
          ("focus", "decisions")),
    Quote("busy-vs-moving", "Busy and moving are different things, and only one of them shows up later.",
          ("focus", "momentum"), ("early-traction", "growth")),

    # ---- customers -----------------------------------------------------------
    Quote("would-be-annoyed", "Ten people who would be annoyed if you shut down are worth more than a thousand who signed up.",
          ("customers",), ("validation", "early-traction")),
    Quote("one-payer", "One person who would pay tells you more than ten who say it sounds great.",
          ("customers",), ("ideation", "validation", "prototype")),
    Quote("one-call-away", "The thing you have been guessing at is usually one phone call away.",
          ("customers", "decisions"), ("validation", "prototype", "early-traction")),
    Quote("what-did-they-say", "The most useful sentence this week will come out of a customer's mouth, not yours.",
          ("customers",), ("validation", "early-traction", "growth")),

    # ---- decisions -----------------------------------------------------------
    Quote("not-stuck", "You are not stuck. You are choosing between two things that both cost something.",
          ("decisions",), ("early-traction", "growth")),
    Quote("reversible", "If you can undo it, the slow decision is the expensive one.",
          ("decisions",)),
    Quote("decided-alone", "A decision you have told nobody about is one you made alone.",
          ("decisions", "team"), ("early-traction", "growth")),
    Quote("no-clean-option", "There is no clean option. There is the one you can live with and the one you cannot.",
          ("decisions",), ("early-traction", "growth")),

    # ---- execution -----------------------------------------------------------
    Quote("half-built", "Half-built is not broken. It is just half-built.",
          ("execution",)),
    Quote("ugly-and-real", "Ugly and real teaches you more this month than polished and imagined.",
          ("execution",), ("prototype", "validation")),
    Quote("one-real-thing", "One real thing moved forward is a full day's work.",
          ("execution", "momentum")),
    Quote("plan-vs-first-draft", "The plan was never the work. It was the first draft of the work.",
          ("execution",)),

    # ---- momentum ------------------------------------------------------------
    Quote("compound-quietly", "The weeks that felt like nothing are usually the ones compounding quietly.",
          ("momentum", "resilience"), ("early-traction", "growth")),
    Quote("always-knew", "Write down what you work out today. Next month you will swear you always knew it.",
          ("momentum",)),
    Quote("started-is-different", "Started is a different category from planned, and only one of them compounds.",
          ("momentum",), ("ideation", "validation", "prototype")),

    # ---- resilience ----------------------------------------------------------
    Quote("stops-exciting", "It stops being exciting long before it stops being worth doing.",
          ("resilience",)),
    Quote("tired-not-failing", "Tired is not the same as failing, though some days they wear the same face.",
          ("resilience", "rest")),
    Quote("survived-is-progress", "Some quarters the honest win is that you are still here and still building.",
          ("resilience",), ("early-traction", "growth")),

    # ---- money ---------------------------------------------------------------
    Quote("not-polite", "Revenue is the only feedback that cannot be polite.",
          ("money", "customers"), ("early-traction", "growth")),
    Quote("runway-is-a-number", "Runway is a number, not a mood. Look at it on a good day, not only a bad one.",
          ("money",), ("validation", "early-traction", "growth")),

    # ---- team ----------------------------------------------------------------
    Quote("untaught", "The work you keep doing yourself is the work nobody else has been taught yet.",
          ("team",), ("early-traction", "growth")),
    Quote("hired-the-gap", "You hired for the gap you had six months ago. Check whether it is still the gap.",
          ("team",), ("growth",)),

    # ---- rest ----------------------------------------------------------------
    Quote("still-here-tomorrow", "The company will still be here tomorrow. So will the problem.",
          ("rest",)),
    Quote("always-unfinished", "You are allowed to stop with things unfinished. They always are.",
          ("rest",)),
    Quote("part-of-the-work", "Rest is not time away from the work. It is part of the work.",
          ("rest",)),
)


#: id -> Quote, so a stored pick can be read back without scanning.
BY_ID: dict[str, Quote] = {q.id: q for q in QUOTES}

# Two lines sharing an id would make a stored pick ambiguous -- the second one
# would silently win on read and nobody would ever see the first.
assert len(BY_ID) == len(QUOTES), "duplicate quote id in the catalogue"

# A typo in a tag silently removes a line from every shortlist it should have
# been in, which is invisible in production and obvious here.
for _q in QUOTES:
    assert _q.themes, f"{_q.id}: needs at least one theme"
    assert all(t in THEMES for t in _q.themes), f"{_q.id}: unknown theme"
    assert all(s in STAGES for s in _q.stages), f"{_q.id}: unknown stage"

# Every stage must have enough to choose from, counting the stage-agnostic
# lines. Two founders at the same stage reading the same pair of lines is the
# bug this whole catalogue exists to fix, and a thin stage is how it comes back.
for _stage in STAGES:
    _n = sum(1 for q in QUOTES if not q.stages or _stage in q.stages)
    assert _n >= 12, f"only {_n} lines available at stage {_stage}"
