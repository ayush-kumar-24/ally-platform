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
    # ---- doubt (continued) ---------------------------------------------------
    Quote("explaining-badly", "You are not bad at explaining it. It is early, and early things explain badly.",
          ("doubt",), ("ideation", "validation")),
    Quote("smartest-room", "Everyone in the room is also making it up. They have just been doing it longer.",
          ("doubt",)),
    Quote("two-years-in", "Two years in, you are allowed to still not be sure. Most people two years in are not.",
          ("doubt", "resilience"), ("early-traction", "growth")),
    Quote("imposter-at-scale", "The feeling does not go away when it works. It just changes what it is about.",
          ("doubt",), ("early-traction", "growth")),
    Quote("nobody-thinking", "Nobody is thinking about your launch as much as you are. That is freedom, not insult.",
          ("doubt",), ("prototype", "early-traction")),
    Quote("asked-for-help", "Asking for help is not the admission you think it is. Nobody has ever thought less of you for it.",
          ("doubt", "team")),

    # ---- focus (continued) ---------------------------------------------------
    Quote("everything-urgent", "When everything is urgent, nothing has been decided yet.",
          ("focus", "decisions")),
    Quote("open-tabs", "The number of things you are half-doing is the real measure of how the week is going.",
          ("focus",)),
    Quote("two-weeks-from-now", "Two weeks from now, which of today's tasks will you remember? Do that one.",
          ("focus",)),
    Quote("small-fires", "Small fires are comfortable because they are solvable. That is exactly why they eat the day.",
          ("focus",), ("early-traction", "growth")),
    Quote("one-metric", "If you had to pick one number to be wrong about, which would hurt most? Watch that one.",
          ("focus", "money"), ("early-traction", "growth")),
    Quote("said-no-lately", "What have you said no to this week? If nothing, you have not chosen anything either.",
          ("focus", "decisions")),

    # ---- customers (continued) ----------------------------------------------
    Quote("compliments-are-free", "Compliments are free. Attention and money are not.",
          ("customers",), ("validation", "prototype", "early-traction")),
    Quote("watched-them-use-it", "Watching one person use it badly is worth a week of imagining them using it well.",
          ("customers", "execution"), ("prototype", "early-traction")),
    Quote("churn-is-a-sentence", "Every cancellation is a sentence somebody almost said to you first.",
          ("customers",), ("early-traction", "growth")),
    Quote("who-is-it-not-for", "Being clear about who it is not for is how the right people recognise themselves.",
          ("customers",), ("validation", "early-traction")),
    Quote("survey-vs-behaviour", "What people say they want and what they open on a Tuesday are different datasets.",
          ("customers",), ("validation", "early-traction", "growth")),
    Quote("first-ten", "The first ten are found by hand. There is no version of this where they are not.",
          ("customers",), ("ideation", "validation", "prototype")),

    # ---- decisions (continued) -----------------------------------------------
    Quote("waiting-is-a-choice", "Waiting for more information is a decision. It is just one you did not write down.",
          ("decisions",)),
    Quote("who-else-knows", "Before you decide, name the one person who has already made this mistake.",
          ("decisions", "team")),
    Quote("cost-of-being-right", "Being right slowly costs more than being roughly right this week.",
          ("decisions", "execution"), ("validation", "prototype", "early-traction")),
    Quote("two-good-options", "Two genuinely good options means you have already done the hard part.",
          ("decisions",)),
    Quote("sunk", "The months already spent are not an argument. They are just months.",
          ("decisions", "resilience"), ("early-traction", "growth")),
    Quote("decide-then-commit", "The decision is not the hard part. Living with it for a quarter without reopening it is.",
          ("decisions",), ("early-traction", "growth")),

    # ---- execution (continued) ----------------------------------------------
    Quote("finished-is-a-feeling", "Finished is a feeling, not a state. Ship at good enough and find out.",
          ("execution",), ("prototype", "early-traction")),
    Quote("boring-work", "Most of what actually moves it is boring, and boring is not a sign you are off track.",
          ("execution",)),
    Quote("scope-grew", "If it is taking longer than you thought, check whether it is still the same thing you started.",
          ("execution", "focus")),
    Quote("smallest-version", "What is the smallest version of this that a real person could use on Friday?",
          ("execution",), ("ideation", "prototype", "validation")),
    Quote("perfect-demo", "A demo that works once is not a product. It is a promise you now have to keep.",
          ("execution",), ("prototype", "validation")),
    Quote("rebuild-urge", "The urge to rebuild it properly is usually the urge to avoid showing it to anyone.",
          ("execution", "doubt"), ("prototype", "early-traction")),

    # ---- momentum (continued) ------------------------------------------------
    Quote("last-month-you", "Look at what you were worried about last month. You are not standing still.",
          ("momentum",)),
    Quote("streaks-beat-sprints", "Six ordinary weeks beat one heroic one, and are much easier to survive.",
          ("momentum", "rest")),
    Quote("write-it-down", "The version in your head feels finished. The version written down never does, and that is the useful one.",
          ("momentum", "execution")),
    Quote("slow-is-still", "Slow is still a direction. Stopped is the only one that is not.",
          ("momentum", "resilience")),
    Quote("first-draft-of-anything", "Everything good here started as something you would not have shown anyone.",
          ("momentum", "doubt")),

    # ---- resilience (continued) ----------------------------------------------
    Quote("hard-week-not-wrong", "A hard week is not evidence. It is a week.",
          ("resilience",)),
    Quote("nobody-saw-that", "The part nobody saw is the part that made it work.",
          ("resilience",), ("early-traction", "growth")),
    Quote("still-answering", "You are still answering the emails and still making the calls. That is not nothing.",
          ("resilience",)),
    Quote("comparison-timeline", "Their three-year overnight success is on a different clock to your Tuesday.",
          ("resilience", "doubt")),
    Quote("bad-quarter", "A bad quarter tells you about a quarter. It does not tell you about you.",
          ("resilience",), ("early-traction", "growth")),
    Quote("keep-showing-up", "Most of this is just continuing to show up after the part where it stopped being fun.",
          ("resilience",)),

    # ---- money (continued) ---------------------------------------------------
    Quote("cheapest-experiment", "What is the cheapest way to find out you are wrong? Do that before the expensive way.",
          ("money", "decisions"), ("ideation", "validation", "prototype")),
    Quote("first-rupee", "The first rupee someone pays you changes the conversation more than the first thousand users.",
          ("money", "customers"), ("validation", "prototype", "early-traction")),
    Quote("raise-is-not-a-win", "Money raised is a bigger obligation, not a bigger scoreboard.",
          ("money",), ("early-traction", "growth")),
    Quote("spend-on-what", "Look at where the money actually went last month. It is a more honest strategy document than the one you wrote.",
          ("money", "focus"), ("early-traction", "growth")),
    Quote("price-too-low", "The price you are shy about naming is usually the one that is too low.",
          ("money", "doubt"), ("validation", "early-traction")),

    # ---- team (continued) ----------------------------------------------------
    Quote("faster-alone", "Faster alone is real, and it stops being true at exactly the point you cannot see coming.",
          ("team",), ("early-traction", "growth")),
    Quote("told-them-why", "They can do the task. Whether they can make the next decision depends on whether you told them why.",
          ("team",), ("early-traction", "growth")),
    Quote("first-hire", "The first person you bring in learns the company from how you behave in a bad week.",
          ("team",), ("early-traction", "growth")),
    Quote("co-founder-conversation", "The conversation you are avoiding with your co-founder gets more expensive every month.",
          ("team", "decisions"), ("validation", "early-traction", "growth")),
    Quote("thinking-alone", "Thinking out loud to one person beats another hour of thinking alone.",
          ("team", "decisions")),
    Quote("who-would-notice", "If you disappeared for a week, what would break first? That is your real job description.",
          ("team", "focus"), ("growth",)),

    # ---- rest (continued) ----------------------------------------------------
    Quote("tired-decisions", "Decisions made tired get remade rested. You will do this twice either way.",
          ("rest", "decisions")),
    Quote("guilt-does-not-ship", "Guilt about not working has never once shipped anything.",
          ("rest",)),
    Quote("weekend-exists", "The weekend is not a reward for finishing. Nothing here is ever finished.",
          ("rest",)),
    Quote("body-keeps-score", "You can borrow against sleep for a while. The repayment terms are not negotiable.",
          ("rest", "resilience")),
    Quote("stepped-away", "The answer arrives in the shower because you stepped away, not in spite of it.",
          ("rest", "decisions")),
    Quote("long-game", "This is a long game and you are the only piece of equipment you cannot replace.",
          ("rest", "resilience")),

    # ---- early-stage specifics -----------------------------------------------
    Quote("permission", "Nobody is going to give you permission. That is the bad news and the whole opportunity.",
          ("doubt", "momentum"), ("ideation", "validation")),
    Quote("idea-is-cheap", "The idea was never the valuable part. The six months of finding out is.",
          ("execution", "momentum"), ("ideation", "validation")),
    Quote("told-your-parents", "Explaining it to someone who does not work in this is the clearest test it gets.",
          ("doubt", "customers"), ("ideation", "validation")),
    Quote("still-not-started", "The gap between deciding and starting is where most of these quietly end.",
          ("momentum",), ("ideation",)),
    Quote("research-forever", "At some point more research is just a more comfortable way of not starting.",
          ("momentum", "decisions"), ("ideation", "validation")),

    # ---- growth specifics ----------------------------------------------------
    Quote("what-got-you-here", "What worked at ten customers is actively in the way at a hundred.",
          ("execution", "team"), ("growth",)),
    Quote("process-is-not-bureaucracy", "Writing it down is not bureaucracy. It is how you stop being the only one who knows.",
          ("team", "execution"), ("growth",)),
    Quote("meetings-multiplied", "Every recurring meeting was a good idea once. Check which ones still are.",
          ("focus", "team"), ("growth",)),
    Quote("further-from-customer", "The further you get from the customer, the more confident and the more wrong you become.",
          ("customers",), ("growth",)),
    Quote("hardest-to-hear", "The most useful thing anyone tells you this quarter will be the thing you least want to hear.",
          ("team", "doubt"), ("early-traction", "growth")),
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
