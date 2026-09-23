"""Walk one founder through the whole journey and report what actually happened.

Onboarding -> Founder DNA -> Current Problem -> Diagnosis -> Report, over the
real HTTP API, against a real database, with whatever LLM configuration the
environment carries. Nothing is stubbed except authentication, which is
overridden because there is no browser here to log in with.

WHY THIS EXISTS. The unit suite covers the engines in isolation and never calls
a model. This is the other half: it proves the phases connect, that the gates
fire in the right order, and -- when a key is configured -- that the model is
genuinely being called rather than silently falling back to MockLLMProvider.
That last one is the point. `llm_call_log` is counted before and after, so a
run that produces plausible-looking output on a dead key is caught rather than
believed.

TWO WAYS TO GET A FOUNDER, because `founders.user_id` may or may not carry a
foreign key to `auth.users`:

  --stage N          Creates a synthetic founder with a random user_id. Works
                      on a database with NO such FK -- a disposable local
                      Postgres provisioned by `alembic upgrade heads` alone,
                      since that FK is not created by any migration in this
                      repo (verified: no alembic version references
                      auth.users or founders_user_id_fkey for the founders
                      table itself). It fails, correctly, against a database
                      where that FK exists.

  --founder-email E   Looks up an EXISTING founder by email instead of
  --founder-id N      creating one -- required for a real Supabase project,
                      where `founders.user_id` genuinely references
                      `auth.users` (added outside this repo's migration
                      history, presumably via the Supabase dashboard). This
                      script will not, and should not, fabricate a row in
                      Supabase's own managed auth schema: it can't see the
                      password-hash format, confirmation tokens, or GoTrue
                      triggers that schema depends on, and a raw INSERT that
                      merely satisfies the FK's type is not the same thing as
                      a real identity. Use an account you already control --
                      ideally your own, signed up through the app the normal
                      way -- not a stranger's real data. --founder-id is the
                      same lookup keyed on the primary key instead of email,
                      for when you already know the id and would rather not
                      pass an email on the command line at all.

    python -m scripts.e2e_journey_check --database-url "postgresql+psycopg2://..." --stage 1 --confirm-writes
    python -m scripts.e2e_journey_check --database-url "..." --founder-email you@example.com --confirm-writes
    python -m scripts.e2e_journey_check --database-url "..." --founder-id 12345 --confirm-writes
    python -m scripts.e2e_journey_check --database-url "..." --cleanup
    python -m scripts.e2e_journey_check --database-url "..." --cleanup-founder-email you@example.com
    python -m scripts.e2e_journey_check --database-url "..." --cleanup-founder-id 12345

IT WRITES. In --stage mode: a founder, consent, a Founder DNA run, a Current
Problem run, a diagnosis session and its answers, and a report. Every founder
it creates is named `e2e+<timestamp>@ally-e2e.local`; `--cleanup` deletes every
founder at that domain and everything cascading from them.

In --founder-email / --founder-id mode it never creates or deletes a
`founders` or `founder_consents` row -- it writes only a Founder DNA run, a
Current Problem run, a diagnosis session and its answers, and a report, all
against the founder_id that account already owns.
`--cleanup-founder-email` / `--cleanup-founder-id` remove exactly those
(sessions, answers, DNA answers, current-problem answers, reports) and leave
the founder and their consent in place -- that account is real and outlives
this script.

The one exception, and it matters: cleanup also sets
`founders.founder_dna_completed_at` and `current_problem_completed_at` back
to null. Those two columns are journey state living on the founder row, not
identity. Cleanup used to skip them to keep a "writes nothing to founders"
promise, and the result was a founder with the answers deleted but still
flagged as having finished: founder-dna/start and current-problem/start then
returned no question at all, both phases walked zero questions, and the run
still printed a full-looking report built on the diagnosis alone.

THREE PERSONAS, ON TWO DIFFERENT AXES. weak and strong differ in QUALITY at
one stage, and that pair is the discrimination test. traction differs in
STAGE at one quality, and exists because quality cannot be measured with
answers that do not fit the questions: run at Early Traction, the strong set
fell back on nine of thirty diagnosis questions and eleven of sixteen Founder
DNA ones, the fallback scored red, and report #96 returned Founder Readiness
and Product & Execution at Critical Gap off findings that belonged to this
script. Use weak/strong at Ideation and Validation; use traction from
Prototype/MVP up.

TWO PERSONAS, AND WHY BOTH MATTER. `--persona weak` (the default) answers as
a founder who has not done the work; `--persona strong` answers the same six
dimensions done properly. One run on its own cannot tell a working classifier
from a harsh one: the weak set produced nine reds and five ambers with every
assessed pillar at Critical Gap, which is the right answer for those inputs and
is also exactly what a scorer stuck on "bad" would print. Run both against the
same founder and compare. Bands that separate mean the model is reading the
answers; bands that do not mean it is not, whatever the report says.

The strong set stays deliberately early-stage -- rigorous, not big. Answers
describing a funded, scaled company would be measured against the confidence
engine's stage_coherence_factor and the comparison would come back reflecting
stage mismatch rather than answer quality.

The database URL must be passed explicitly -- it deliberately does NOT read
DATABASE_URL, so pointing this at a real project has to be a decision rather
than an accident. `--confirm-writes` is required on top of that.

COST. A full diagnosis is roughly one model call per question plus the
reasoning pipeline. The repository's own estimate is about Rs 14-15 per run;
this prints the measured cost from `llm_call_log` at the end, so you can check
that against reality rather than trusting the estimate.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

TEST_DOMAIN = "ally-e2e.local"

#: Answers with enough substance for a classifier to have an opinion. A run
#: answering "test" to everything tells you the plumbing works and nothing
#: about whether the scoring does.
#: Answers tagged with the question topics they actually answer.
#:
#: WHY TAGGED AT ALL. Answers used to be handed out round-robin by question
#: index, so which answer met which question was luck, and the luck was bad:
#: the strong run's analytics question drew the cofounder paragraph, and
#: "explain this idea in one breath" drew the one about planning rhythm. The
#: engine then read an answer that genuinely did not address the question,
#: scored it red, and RC-441 Weak Product Analytics was detected against a
#: founder whose answer said the product was instrumented. The reds were
#: measuring the harness, not the founder.
#:
#: Each entry is (topic keywords, answer). Keywords are substrings matched
#: against the lowercased question text, stemmed so one entry catches the
#: variants -- "pric" for price/pricing/priced, "custom" for
#: customer/customers. The answer with the most distinct hits wins.
#:
#: BOTH PERSONAS COVER THE SAME TOPICS IN THE SAME ORDER. That is what makes
#: the runs comparable: a question matches the same slot in either persona,
#: so the only thing differing between two runs is the quality of the answer
#: that lands, never which subject got discussed.
#:
#: The first six are the business dimensions. The last four exist because
#: Founder DNA asks about the founder, not the business -- 18 of the ~36
#: questions in a full journey -- and with only business answers in the bank
#: that whole phase fell through to the generic reply.

#: (defining terms, supporting terms) per topic. A defining term means the
#: question is about this topic -- "feedback", "competitor", "cofounder".
#: A supporting term only leans that way -- "money", "build", "week" -- and
#: on its own is coincidence.
_TOPICS = (
    # customers, validation, who actually pays
    (("customer", "spoken to", "talked to", "talking to someone",
      "interview", "personal network", "validat", "pays for this",
      "anyone else told", "problem is real", "actually uses it",
      # "how many people have actually paid you, or clearly committed to pay
      # you? Not interested -- committed." never uses the word "customer",
      # and fell back on the one question this topic exists to answer.
      "actually paid you", "committed to pay"),
     ("talk to", "audience", "demand")),
    # time, planning, priorities, focus
    (("plan", "priorit", "schedul", "deep work",
      "your time", "specific time", "every hour", "spend more time",
      "actual hours", "hours went into", "avoiding right now",
      "decided not to do", "left over",
      # "what did you actually do today that moves you toward the life you
      # picture in five years" is a planning question, not a purpose one --
      # it asks what today did, not why the venture matters. Without these
      # it went to purpose on "five years" and manufactured RC-1088 as a
      # rank-1 top finding off a category holding one answer.
      "actually do today", "moves you toward",
      # Early Traction asks about energy as conditions for good work:
      # "the last stretch of work that gave you real momentum".
      "real momentum", "conditions made it", "stretch of work"),
     ("week", "focus", "switching")),
    # market size, research, competitors
    (("market", "competitor", "how many businesses", "count or estimate",
      "would actually need this",
      # "who else solves this problem" never says "competitor"
      "who else solves", "else is solving", "who else is"),
     ("estimate", "size", "research")),
    # product, analytics, what got shipped
    (("product", "analytics", "you've built", "shipped", "actually used",
      "prototype"),
     ("tools", "build", "usage", "feature")),
    # pricing, money, financial boundaries
    #
    # "behind your price" and "your price" are here because "walk me through
    # the math behind your price" fell through to the generic answer and was
    # scored red: every pricing term in this topic said "pricing", and that
    # question says "price".
    (("pricing", "what we charge", "charge for", "financial", "revenue",
      "clean boundary", "money move", "behind your price", "your price",
      # and "how did you arrive at your current price?" is not "your price"
      # either. This is the third phrasing of the same question to need its
      # own entry, which is the cost of matching on substrings.
      #
      # "arrive at your" alone was the obvious way to write that and the
      # wrong one: it also takes "how did you arrive at your sales
      # projections" and "...your current or desired valuation", neither of
      # which the pricing answer addresses.
      "current price"),
     ("money", "cost", "price")),
    # team, roles, who decides
    (("team", "cofounder", "co-founder", "who owns", "the split",
      "decide together"),
     ("hire", "role")),
    # risk
    (("risk", "could fail", "downside", "worst case", "thought about risk",
      "seriously hurt", "listed out everything"),
     ("go wrong", "unsettle", "fail")),
    # decisions under uncertainty, stress
    (("decision", "decide fast", "big unknown", "uncertainty",
      "under pressure", "completely drained",
      # later-stage phrasings of the same two dimensions
      "completely overwhelmed", "push through", "shut down", "got to you",
      "wore you down"),
     ("decide", "unknown", "stress", "drained", "reach out")),
    # feedback, criticism, blind spots
    (("feedback", "criticis", "blind spot", "pointed out", "dismisses your",
      "told to you straight",
      # "what have you had to learn the hard way" is the same dimension asked
      # of someone who has now had time to learn it
      "learn the hard way", "get wrong first", "got wrong first"),
     ("harsh", "difficult")),
    # motivation, purpose, vision
    (("why does", "deserve", "thriving", "vision", "grabbed you",
      "origin story", "opening line", "advice right now",
      # later-stage origin, motivation, vision and values phrasings
      "worth actually building", "what tipped it", "last win",
      "one number", "really working", "tempted you to compromise",
      "you'd said mattered",
      # the later-stage origin question, which says none of the above
      "started this in the first place", "necessary rather than optional"),
     # "five years" is a date, not a subject. As a defining term it pulled a
     # Business Planning question about what you did TODAY into purpose.
     ("matters", "picture", "five years")),
    # --- added after a run where each of these fell through to the generic
    # --- answer and was scored as though the founder had dodged the question
    # what "doing it well" means
    (("being trusted", "being the best", "really well"),
     ("mean to you", "recognised")),
    # explaining the idea -- the pitch
    (("one breath", "explain this idea", "explain it to", "elevator"),
     ("stranger", "rehearsing")),
    # the founder's own encounter with the problem
    (("ran into this problem", "personally ran into", "had it yourself",
      "your own experience", "experienced it yourself"),
     ("yourself",)),
    # what it is being built WITH
    (("what tool", "no-code", "existing tool", "or template",
      "currently using to build", "any tools", "tools that could help"),
     ("spreadsheet", "from scratch")),
    # time WASTED, which is not the same question as how time is planned:
    # the planning answer describes protected Mondays and was correctly
    # marked down on "what eats the most time", because it never names a
    # time-waster. Two Founder Psychology answers, and RC-974 behind them.
    (("eats the most", "spent hours", "without actually moving",
      "need that much time", "didn't need",
      # the same question once there is a team and a queue to be pulled into
      "context-switch", "pulled you away", "lost real time"),
     ("waste", "looking back")),
)

#: THE OPERATING TOPICS -- everything a founder with customers, staff and
#: money gets asked and a pre-launch founder does not.
#:
#: Measured, not guessed: these are the subjects that fell through to the
#: generic answer in the Early Traction run (report #96). Nine of thirty
#: diagnosis answers were generic there and eight of those nine scored RED,
#: because a non-answer reads to the classifier as evasion. Founder Readiness
#: and Product & Execution both came back Critical Gap on the strength of
#: questions about delegation, single points of failure, and what is written
#: down -- none of which the Ideation topics have a slot for.
#:
#: Appended, never substituted. The first fifteen topics stay exactly as the
#: weak and strong runs see them, so those runs remain comparable with every
#: run that came before.
#:
#: TIE-BREAKING. `match_answer` keeps the first topic on an equal score, and
#: the fifteen above are all earlier, so an operating topic that merely ties
#: loses. Several deliberately carry more than one defining phrase for that
#: reason: "team" alone scores 2 for the team topic, so a question about role
#: clarity needs 3+ to land where it belongs. test_stage_4_question_routing
#: pins all thirty real questions against this.
_OPERATING_TOPICS = (
    # delegation -- handing work over, and whether anyone was taught how
    (("delegat", "been taught", "how you want something", "just guess",
      "hand off", "handing over", "taking over",
      # "hand off" as a phrase never appears in "when you hand something off",
      # which is the exact question this topic is for. Nor does any term here
      # appear in "how often do you catch yourself thinking it would just be
      # faster if I did this myself" -- the purest delegation question in the
      # bank, which scored zero against every topic.
      "hand something off", "explain the outcome you want",
      "faster if i did this myself", "just the task to complete",
      "handed off by now", "still do yourself"),
     ("teach", "show them", "someone else")),
    # founder dependency -- the bus factor
    (("got sick", "only you know", "genuinely wait", "second-in-command",
      "required you personally", "in your absence", "would simply stop",
      "stop happening", "nobody else could pick up", "without you explaining",
      "ran without you"),
     ("personally", "a week", "everything waits")),
    # what is written down -- process, SOPs, institutional memory
    #
    # "anything tracking" rather than "system for tracking": the latter also
    # appears in "is there any system for tracking who owns what", which
    # belongs to role clarity. This topic is earlier, so on a tie it would
    # have taken that question away from the slot that answers it.
    (("written down", "step-by-step procedure", "written step-by-step",
      "live in your head", "lives in your head", "only in someone's head",
      "someone's head", "documented", "anything written",
      "anything tracking", "due and when",
      # "the last recurring task you did for the third time -- did you do it
      # the same way, or figure it out fresh again" is this question asked
      # without any of the words above. The answer here, about step-by-steps
      # someone other than the author has followed, is the right one for it.
      "recurring task", "the third time", "figure it out fresh"),
     ("process", "procedure", "notes", "in writing")),
    # role clarity -- who owns what, on paper
    (("expected of each person", "who owns what", "role clarity",
      "live in conversations", "tracking who owns"),
     ("responsibilit", "ownership", "in writing", "each person")),
    # decision rights -- how a disagreement actually gets settled
    (("who owned a task", "clear way to resolve", "disagreed about who",
      "decision rights", "make a real decision"),
     ("resolve", "disagree", "settle")),
    # performance -- knowing whether the team is working, not just busy
    (("actually performing", "performing well", "just staying busy",
      "staying busy", "how do you know if your team"),
     ("performance", "review", "busy")),
    # hiring, and holding on to the wrong person
    (("kept someone on", "longer than you should", "replacing them",
      "hire", "hiring", "let someone go"),
     ("team member", "harder than")),
    # retention and churn -- who stays and who leaves
    (("churn", "sticks around", "stick around", "renew", "cancel",
      "stop paying", "retention"),
     ("leaves", "separates a customer")),
    # the buying journey -- how a customer actually decides
    (("buying journey", "how they decide", "decision to buy",
      "sales cycle", "how a customer finds"),
     ("journey", "buying", "scale of 1 to 5")),
    # pricing in practice -- consistency, not the rationale
    (("present pricing", "presenting pricing", "varies each time",
      "vary each time", "quote", "discount"),
     ("consistent", "each time")),
    # cash and profit -- the money rhythm
    (("cash position", "profitable", "just generating revenue",
      "runway", "burn", "margin", "check your cash"),
     ("regular schedule", "prompts you", "last month")),
    # evidence of traction -- what proves it works, to someone else
    (("real evidence", "evidence of market demand", "beyond your own belief",
      "personally convinced", "fundraising pitch", "prove the problem",
      "what evidence would you show"),
     ("evidence", "proof", "traction")),
    # marketing -- whether a campaign has a definition of success
    (("campaign", "launch a campaign", "success actually looks like",
      "figure that out after", "marketing"),
     ("define", "success", "channel")),
    # ICP drift -- who you built for versus who actually pays
    (("originally designed", "designed it for", "who your paying customers",
      "matches reality", "still matches", "same type of customer",
      "actually are, versus"),
     ("drift", "versus who", "understanding of your customer")),
    # what running this has done to the founder -- how they have changed, and
    # the thing they have not said out loud. Founder DNA's closing question at
    # this stage, and no earlier topic is about it: Ideation has no "before"
    # to compare against and nothing yet worth not saying.
    (("how you show up", "show up now", "before you started building",
      "haven't told anyone", "not told anyone", "about running this",
      # "who were you as a leader in year one, and who are you now"
      "as a leader in year one", "who are you now"),
     ("different", "versus before", "changed")),

    # --- added after the first weak_traction run, where eleven of thirty
    # --- diagnosis questions fell back. Five of those were near misses on
    # --- topics above and were fixed there. These six had no slot at all:
    # --- every one scored zero against every topic in the bank.

    # the problem itself drifting -- not the customer (that is ICP drift
    # below) and not the product
    #
    # Keyed on the DRIFT, not on "the problem you set out to solve" -- that
    # phrase also opens "what's a piece of customer feedback you've dismissed
    # because it didn't fit the problem you set out to solve", which is a
    # question about dismissing feedback and was already being answered.
    (("changed shape", "notice when it happened"),
     ("drifted", "since you started building")),
    # data protection, as a thing with a standard rather than a comfort level
    (("data privacy", "privacy and security", "personally identifiable",
      "comfort level with data"),
     ("security", "actually needed")),
    # the state of the pipeline, asked as a rating
    #
    # NOT a bare "sales pipeline": that also matches "what tools do you use to
    # track your sales pipeline and deals", which is a tooling question, and
    # took it away from the tooling answer that was handling it correctly.
    (("pipeline is right now", "healthy your sales", "sales pipeline data",
      "pipeline data"),
     ("pipeline", "rate from 1 to 5")),
    # sales collateral -- whether anything is reusable
    (("template for proposals", "reusable template",
      "every one get built", "proposals"),
     ("template", "reusable")),
    # oversight -- the founder as the only check on something legal
    (("reviewing contracts", "adequate oversight", "sufficient, without",
      "personally reviewing"),
     ("contracts", "oversight")),
    # publishing rhythm, as distinct from whether a campaign had a target
    (("publish content", "actually publish", "how often do you publish",
      "publishing"),
     ("content", "on average")),
)

#: WEAK. A founder who has not done the work: no market sizing, no pricing
#: rationale, no planning rhythm, no analytics, nothing written down.
_WEAK_TEXTS = (
    "About ten paying customers, mostly from my own network, and two churned "
    "last month without telling me why. I have not spoken to anyone outside "
    "the people I already knew.",
    "I spend most of the week firefighting support and very little on "
    "anything that compounds. I have not sat down to plan since the week I "
    "started.",
    "I have never worked out the real size of this market. I know the problem "
    "is real because I had it myself, and I have never gone looking for who "
    "else is solving it.",
    "The last thing I shipped took six weeks and almost nobody has used it. I "
    "built it because one loud customer asked, and I would only know someone "
    "used it if they told me.",
    "I do not really know why we charge what we charge. I copied a "
    "competitor's pricing page when we launched and never revisited it, and "
    "my own money and the business money are in the same account.",
    "There are two of us. Neither of us owns anything in writing, we just "
    "work out who does what each morning, and we have never agreed who "
    "decides when we disagree.",
    "I have worried about it plenty but never written anything down. If you "
    "asked me for the list I would have to make it up on the spot.",
    "I usually put the decision off and hope it resolves itself, and when it "
    "does not I pick whichever option is in front of me that day.",
    "Someone told me something useful about six weeks ago and I found a "
    "reason it did not apply. I have not gone back to it since.",
    "Honestly I have not put it into words. I know it matters to me but if "
    "you asked me to say why in one sentence I would struggle.",
    "Being the one people have heard of, I suppose. I have not thought past "
    "that -- what doing it well looks like on an ordinary Tuesday I could "
    "not tell you.",
    "I always ramble when someone asks. It comes out different every time "
    "and I usually take two minutes to get anywhere near the point.",
    "Not recently, no. It is more something I noticed other people "
    "complaining about than something I have run into myself.",
    "Everything from scratch, because I never looked at what already "
    "exists. It did not occur to me to check before I started building.",
    "Support, and fiddling with things nobody asked for. If I am honest "
    "that is most of the week, and I could not tell you what it bought me.",
)

#: STRONG. The same topics, in the same order, answered by a founder who HAS
#: done the work.
#:
#: DELIBERATELY STILL EARLY-STAGE. The temptation is to write a scaled
#: company -- crores of revenue, a team of thirty -- but these founders are
#: at Ideation, and the confidence engine carries a stage_coherence_factor
#: that reads answers against the founder's stage. Answers describing a
#: Series B would make the comparison measure stage mismatch rather than the
#: thing being tested. Strong here means rigorous, not big.
_STRONG_TEXTS = (
    "Forty-one conversations with people I had never met, found through two "
    "industry Slack groups and cold email rather than my own network. Nine "
    "offered to pay before I had anything to sell, and the notes are in one "
    "doc tagged by which of the three problems they led with.",
    "Mondays are two hours on the one question that decides the week, and I "
    "protect them -- the rest is execution against what that produced. Last "
    "Monday it was whether to build the integration or keep doing it by hand, "
    "and I chose by hand for another month because it is the cheaper way to "
    "learn what the integration should be.",
    "Bottom-up: roughly eleven thousand firms in this bracket in India, about "
    "four hundred reachable through the two channels I have actually tested. "
    "I wrote it down because the top-down number flattered me and I did not "
    "trust it, and I check the three nearest alternatives every month.",
    "I instrumented the three steps that matter before I shipped it, so I can "
    "see that eleven of nineteen people who start the flow finish it, and "
    "where the other eight stop. That drop-off is the next thing I fix, and I "
    "know it is next because I can see it rather than because someone "
    "complained.",
    "I tested three prices with real people rather than a survey -- asked for "
    "money and watched what happened. At the middle one, six of nine said yes "
    "without negotiating, which tells me it is too low rather than right. The "
    "business account is separate from mine and has been since week one.",
    "Two of us, and we wrote the split down in week one precisely because "
    "everyone told us not to bother: I own product and customer "
    "conversations, she owns the build, and we agreed in writing who decides "
    "when we disagree. It has already been used once.",
    "Five written down, reviewed monthly. The one that actually worries me is "
    "channel concentration -- both channels I have tested run through the "
    "same two communities, and I have no third.",
    "I write the decision down with what would have to be true for it to be "
    "wrong, then set a date to check. The integration call last month is on "
    "that list with a review date of the fourteenth.",
    "Someone told me six weeks ago that I was optimising a flow nobody had "
    "asked for. I stopped that week, went back to the interview notes, and "
    "she was right -- it was not in any of them.",
    "Because I watched people give up on something they needed for want of "
    "anyone willing to explain it, and I can say that in one sentence because "
    "I have had to say it to forty-one strangers.",
    "Trusted. Not first and not the biggest -- if ten of the forty-one I "
    "spoke to would recommend this to someone in their position without me "
    "asking, that is doing it well. First and biggest are not things I can "
    "control at this stage. That one I can.",
    "Firms this size lose a day a week to a process they all do the same "
    "bad way, and we do it for them in an hour. I have said that sentence "
    "forty-one times and cut something out of it every time somebody looked "
    "confused halfway through.",
    "Last March, in my old job -- I lost most of a week to it and rebuilt "
    "the same spreadsheet three times. That is where this started, and it "
    "is exactly why I went looking for whether anyone else had that week.",
    "A no-code form, a spreadsheet, and about two hundred lines of glue. I "
    "checked what already existed first: three tools do eighty per cent of "
    "it, so I am only building the part none of them do.",
    "Polishing copy nobody reads. I caught it three weeks ago when the "
    "analytics said the page it sits on gets nine visits a week, and it is "
    "capped at an hour on Fridays now.",
)

#: TRACTION. An operator eleven months in: sixty-two paying customers, four
#: people, money coming in every month. Same rigour as the strong set, moved
#: forward two stages -- and that is the whole point of it.
#:
#: WHY A THIRD PERSONA AT ALL. weak and strong differ in QUALITY at one stage;
#: this differs in STAGE at one quality. The strong set is deliberately
#: pre-launch ("nine offered to pay before I had anything to sell"), so at
#: Early Traction it had nothing to say to two thirds of Founder DNA and to
#: nine of thirty diagnosis questions. Those fell back, the fallback reads as
#: evasion, and report #96 came back with Founder Readiness and Product &
#: Execution at Critical Gap off eight reds that belonged to the harness.
#:
#: The answers stay AT Early Traction and do not overshoot. A founder
#: describing a Series B is measured against the confidence engine's
#: stage_coherence_factor and the result reports stage mismatch instead of
#: answer quality -- the same trap the strong set's note warns about, one
#: stage further along.
_TRACTION_TEXTS = (
    # --- the fifteen shared topics, in an operator's voice -----------------
    "Sixty-two paying, and I speak to six every month on a rota so it is not "
    "only the loudest ones I hear from. Eleven of the sixty-two came from "
    "people I already knew; the rest came through two channels I can name. "
    "The notes live in one doc tagged by what they were doing before us.",
    "Thursday mornings are two hours nothing gets into, and the week's work "
    "is set against whatever that produces. Last Thursday it was whether to "
    "take the enterprise pilot or finish onboarding automation -- we chose "
    "onboarding, because the pilot would have cost us the four smaller "
    "customers we already have.",
    "About eleven thousand firms in this bracket in India, four hundred "
    "reachable through the two channels we have actually worked. We lose to "
    "the same competitor in roughly three of every ten deals and I know why: "
    "they have the integration we have not built yet. I check them monthly.",
    "Instrumented before we shipped it, so I can see that thirty-one of "
    "sixty-two use it weekly and eight have not opened it in a month. The "
    "eight are the ones I call. The drop-off is at the import step and that "
    "is what we are fixing this quarter.",
    "Three tiers. The middle one started from what a firm this size already "
    "loses to the problem -- about a day a week of somebody's time -- and I "
    "priced at a fifth of that. Six of nine said yes without negotiating, so "
    "it is still too low, and the next cohort goes up in April.",
    "Four of us: two engineers, one on support, me on customers and pricing. "
    "Who decides what is written down and we settled it in week one, "
    "including who breaks a tie. It has been used twice and both times it "
    "stopped an argument becoming a fortnight.",
    "Five written down, reviewed monthly. The one that actually worries me is "
    "that both channels run through the same two communities, and I have no "
    "third -- which is also why I am not spending on paid acquisition yet.",
    "I write the decision down with what would have to be true for it to be "
    "wrong, then set a date to check. The enterprise pilot call is on that "
    "list with a review date of the fourteenth and the condition written next "
    "to it.",
    "Our support person told me six weeks ago that I answer tickets she is "
    "meant to own, and that it was making her slower rather than faster. She "
    "was right. I stopped, and the ones I was reaching for first are now the "
    "three types she escalates by rule.",
    "Because I watched firms this size pay penalties for something nobody had "
    "ever shown them how to track, and I can say that in one sentence because "
    "I have said it to sixty-two people who then paid for it.",
    "Trusted. Not the biggest and not the first -- if the sixty-two would "
    "recommend us to someone in their position without me asking, that is "
    "doing it well. Nineteen already have, and that is the number I watch.",
    "Firms this size lose a day a week to compliance filings they all do the "
    "same bad way, and we do it for them in an hour. I have said that "
    "sentence to sixty-two customers and cut something out of it every time "
    "somebody looked confused halfway through.",
    "In my old job, the last quarter before I left -- we paid a late fee on "
    "something nobody had been told was theirs to file, and I rebuilt the "
    "same tracking spreadsheet three times that year. That is where this "
    "started.",
    "A no-code form, a spreadsheet and about two hundred lines of glue for "
    "the first nine months, and we have replaced roughly half of that since. "
    "I checked what existed first: three tools do eighty per cent of it, and "
    "we only build the part none of them do.",
    "Answering support tickets that are not mine. I caught it when I looked "
    "at where last month went and saw eleven hours in a queue we hired "
    "someone to own. It is capped at the Friday escalations now.",

    # --- the operating topics ---------------------------------------------
    # delegation
    "Taught, not guessed -- and I got that wrong for the first half of this "
    "year. Now anything I hand over I do once alongside them, then they do "
    "the next one while I watch, and the third is theirs with the notes we "
    "wrote together. Onboarding went across that way in March and I have not "
    "touched one since.",
    # founder dependency
    "Two things: the pricing conversation on anything above the middle tier, "
    "and the quarterly filing logic nobody else has had to change yet. If I "
    "were out for a week the filings would still go, because the rules are "
    "written and our engineer has run them twice with me sitting out. The "
    "pricing calls would wait, and that is the one I am fixing next.",
    # written down
    "Written down, in one place the team can open. Onboarding, the escalation "
    "rules and the monthly close each have a step-by-step someone other than "
    "the author has followed end to end at least once -- that is the test, "
    "not whether the document exists. The filing logic is the exception and "
    "it is on this quarter's list.",
    # role clarity
    "In writing, one line each, and we reread it at the monthly. Support owns "
    "every ticket to resolution, our senior engineer owns what ships, I own "
    "pricing and anything a customer signs. The gap we found in February was "
    "that nobody owned data corrections, so they sat for days; that has a "
    "name against it now.",
    # decision rights
    "It is written down: whoever owns the area decides, and if it crosses two "
    "areas it comes to me the same day rather than sitting. We agreed that in "
    "week one and it has settled two disagreements -- one about refunding a "
    "customer, one about shipping with a known bug.",
    # performance
    "Three things per person we agreed at the start of the quarter, and we "
    "look at them monthly rather than at the end when it is too late to act. "
    "For support it is time to first reply and how many tickets come back a "
    "second time -- the second one matters more, because busy and effective "
    "look identical on the first.",
    # hiring / holding on too long
    "Yes, once, for about two months longer than I should have, because "
    "hiring again felt worse than the problem. It cost us two customers who "
    "left quietly. I now write down what would have to change and by when, "
    "and I say it out loud to them, which makes the date real.",
    # retention / churn
    "Four have left in eleven months and I know why for all four: two never "
    "got through the import, one had a person leave who was the only one "
    "using us, one outgrew what we do. The ones who stay have a second user "
    "inside the first month -- that is the single strongest signal we have "
    "and it now drives onboarding.",
    # buying journey
    "Four steps and I can name where they stall: somebody feels the pain at "
    "a filing deadline, asks in one of two communities, tries us on one "
    "filing, then has to get their accountant to agree. The accountant step "
    "is where deals die, so we now offer to talk to the accountant directly.",
    # pricing presentation
    "Same three tiers, same page, same order, every time -- I stopped "
    "improvising after I gave two customers different numbers for the same "
    "thing in one week and had to honour both. Discounts are annual-only and "
    "capped at ten per cent, and anything outside that comes to me.",
    # cash and profit
    "Every Monday, same fifteen minutes, whether or not anything prompts it. "
    "Last month was profitable but only just, and only because one "
    "annual payment landed in it -- on the monthly figures alone we were "
    "about even. I keep the two numbers separate for exactly that reason.",
    # evidence of traction
    "Sixty-two paying, nineteen unprompted referrals, and revenue that has "
    "grown every month for seven months without paid acquisition. The "
    "strongest piece is not the growth though -- it is that thirty-one use it "
    "weekly. Somebody could believe none of my opinions and still check all "
    "four of those.",
    # marketing
    "Written down before it starts, or we do not start it. The last one was "
    "a guide for one community with a target of twenty-five signups and "
    "eight trials; it got thirty-one and five, so it half worked and I know "
    "which half. The trial number is the one that decides whether we do it "
    "again.",
    # ICP drift
    "I checked in January and I was wrong. We designed for firms of twenty "
    "to fifty people and the ones who actually stay are ten to twenty, where "
    "there is no full-time finance person at all. We moved the messaging to "
    "match what pays rather than what I drew, and the next cohort converted "
    "better.",
    # how running this has changed the founder
    "I answer fewer things myself and I am slower to say yes, which took "
    "about eight months and two bad calls to learn. The part I have not "
    "really said out loud is that the month we became profitable I felt "
    "almost nothing, and I have been trying to work out since whether that "
    "means I picked the wrong number to care about.",
    # --- the six subjects that had no slot until the first weak_traction run
    "It has narrowed, and I noticed in January rather than at the time. We "
    "started on 'compliance is hard' and what people actually pay for is one "
    "filing they keep missing. I only caught it because the notes are tagged, "
    "and reading six months of them in one sitting made it obvious.",
    "We hold client financial data, so it is not about what I am comfortable "
    "with. We encrypt at rest, nobody outside the two of us has production "
    "access, and I had someone who does this properly review it in March. The "
    "gap they found was our backup restore, which we had never tested.",
    "Four, maybe. It is the weakest part of the business and I would not "
    "dress it up -- I can see the deals but I cannot predict them, because "
    "the accountant approval step has no timeline I control. Everything "
    "before that step I can call within a week.",
    "There is one, and it is three years of edits deep. Roughly eighty per "
    "cent is the same every time; the rest is the filing types they need. "
    "Before it existed each proposal took me an afternoon and two of them "
    "contradicted each other on scope.",
    "No -- I read them and I am not qualified to, which I know. Anything with "
    "an indemnity or a data clause goes to an actual solicitor now, and that "
    "rule came out of a renewal I signed last year with an auto-renew in it "
    "that I had read and not registered.",
    "Fortnightly, and I can say that because it is scheduled rather than "
    "because it is how it feels. It used to be whenever I had something to "
    "say, which meant nothing for five weeks and then three in a fortnight. "
    "The fortnightly version brings in about twice as many trials.",
)

#: THE CURRENT PROBLEM TOPICS -- the third phase, which until now was almost
#: entirely fallback.
#:
#: `current_problem_questions` holds twelve rows: four questions for each of
#: the three stage groups. Every founder answers the four for their stage, and
#: measured against the bank as it stood, exactly one of any four matched a
#: topic. The other three took the generic fallback, so in every e2e run ever
#: recorded, three quarters of this phase's evidence was a topic-neutral line
#: that says nothing about the founder.
#:
#: Two of the twelve "matches" were worse than the fallbacks. Question 9 --
#: "what is the single biggest problem in the company right now? Say it the
#: way you'd say it to a co-founder, not the way you'd say it to a board" --
#: scored 2 on the TEAM topic, on the word "co-founder" in the sentence
#: telling the founder how to phrase their answer. It came back with an answer
#: about who owns what. Question 12, which is about a decision that should
#: have been made a level down, matched "team" on "team lead" and answered
#: about team structure. A fallback is visibly a non-answer; a confident answer
#: to the wrong question is not, and it lands in the report as evidence.
#:
#: Appended after the operating topics, and the same tie-breaking applies:
#: `match_answer` keeps the FIRST topic on an equal score and these are last,
#: so each one carries enough defining phrases to win outright rather than
#: tie. Question 9 has to beat team's 2 and scores 6; question 12 the same.
#: EVERY PHRASE HERE IS A FULL PHRASE, and the first draft of this block shows
#: why. It used the bare terms "stall" and "matters most", which read as
#: obviously on-topic and are nothing of the kind in a bank of 3,340
#: questions: "when your standard follow-up stalls", "do you track why deals
#: stall at a specific stage", "has the business started stalling because your
#: attention is diverted into investor meetings" and "are multiple goals being
#: pursued with no clear ranking of which matters most" all matched, and all
#: four came back with an answer about an abandoned landing page or an
#: unstarted business. Six false matches, bought in exchange for fixing two.
#:
#: The same goes for the supporting terms. "this week", "one thing", "metric"
#: and "instead" each look harmless and each pairs with almost anything, and
#: two supporting terms is a match on its own.
_CURRENT_PROBLEM_TOPICS = (
    # the headline problem -- the opening question at all three stages
    #
    # "part that matters most" and not "matters most": the questions open
    # "Now the part that matters most." "one thing that matters most" is
    # separate because question 386 asks exactly that and means it.
    (("single biggest thing", "single biggest problem", "standing between you",
      "part that matters most", "one thing that matters most",
      "say it the way", "not the way you'd say it"),
     ("own words", "polish it")),
    # what would have to be true to start
    (("would need to be true", "to actually start", "need to be true this"),
     ()),
    # what has already been tried, and where it stalled
    #
    # No "stall" here in any form -- the two defining phrases below already
    # score 4 on the question this topic exists for, and every use of "stall"
    # wide enough to also catch it caught four sales-pipeline questions with it.
    (("already tried", "move this forward"),
     ("a call, a sketch",)),
    # the single thing whose failure stops everything
    #
    # Distinct from the operating founder-dependency topic, which is about
    # work stopping in the FOUNDER's absence. This is about a dependency in
    # the business: "if it broke tomorrow". No phrase is shared with it.
    (("broke tomorrow", "stop the business cold", "if it broke"),
     ("stop the business",)),
    # what is being avoided
    #
    # The planning topic already owns "avoiding right now" -- that question
    # asks what is being put off in a WEEK of work. This one asks what is
    # being avoided full stop, and the phrases do not overlap.
    (("avoiding this week", "know you need to deal with",
      "been avoiding this"),
     ("you know you need",)),
    # the number being avoided
    (("metric have you been", "quietly avoiding", "looking at this month"),
     ()),
    # the problem that keeps coming back after it was declared fixed
    (("keep resurfacing", "same problem keep", "already fixed it",
      "thought you'd already fixed"),
     ("resurfacing", "even after")),
    # decisions landing on the founder that belong a level down
    (("team lead should have made", "should have made instead",
      "land on you", "why did it land"),
     ("made a call",)),
)

#: THE FOUNDER TOPICS -- the psychological dimensions Founder DNA asks about
#: and no other phase does.
#:
#: Measured across the whole 67-question Founder DNA bank: Stage 0 matched
#: 16 of 23, Stage 0->1 matched 19 of 22, and Stage 1->10+ matched 12 of 22.
#: Nearly half of what a later-stage founder is asked about themselves was
#: being answered with a topic-neutral line, and Founder DNA is 18 of the
#: ~52 questions in a journey and the main input to Founder Readiness.
#:
#: The misses clustered in six dimensions -- core_motivation, energy_patterns,
#: purpose_mission, core_values, focus_attention and mindset_excellence. Four
#: other dimensions (origin, archetype, vision, stress_response) had single
#: misses that were phrasings of questions already covered, and those were
#: fixed by adding the phrase to the topic that already had the right answer,
#: rather than by adding a topic here.
#:
#: These go to ALL FOUR personas: every founder is asked about themselves,
#: whatever stage they are at.
_FOUNDER_TOPICS = (
    # what a good outcome felt like -- motivation, read off a real memory
    (("genuinely satisfied you", "genuinely moved you", "what about it landed",
      "last thing you built or finished", "last thing this business achieved"),
     ("landed", "satisfied")),
    # recognition against contribution, as a forced choice
    #
    # The two images ARE the question -- there is no abstract wording to key
    # on, which is why the phrases here are the pictures themselves.
    (("trophy on a pedestal", "unfinished bridge", "two cliffs",
      "people you will never meet"),
     ("recognised", "which one pulls you")),
    # where energy comes from and where it goes -- including the long stretch
    # of uninterrupted work, which is the same question asked positively
    (("energised rather than drained", "left you wiped out", "genuinely in flow",
      "recharges you", "desk lamp", "loud room",
      "sat with one problem", "without switching to something else"),
     ("energised", "flow", "recharge")),
    # why you are still here, what "done" would mean, what should outlast you
    #
    # NOT "does it end": that also ends "does anything structured happen
    # afterward, or does it end with the conversation", which is about
    # performance reviews.
    (("considered dropping this", "made you stay with it",
      "being 'done'", "even mean to you",
      "stepped away for a year", "still be true when you came back"),
     ("done", "stay with it")),
    # the thing done by hand on purpose
    #
    # Its own topic rather than part of the one above, because "why do you
    # keep going" and "why are you still doing this by hand" want different
    # answers, and the purpose answer does not address the second at all.
    (("isn't scalable", "not scalable", "doing anyway"),
     ("by hand", "and why")),
    # the line that does not get crossed, tested against money
    #
    # NOT a bare "crossed a line": "the last time someone on your team crossed
    # a line you care about" is a question about the team, and it was already
    # being answered by the team topic.
    (("walked away from something", "turned down money",
      "weren't willing to trade", "what was the line"),
     ("line", "walked away")),
    # perfectionism, as a cost rather than a virtue
    (("perfectionism", "were you polishing", "what it delayed"),
     ("polishing", "cost you real time")),
    # how much the problem actually costs the person who has it
    (("fixed the problem overnight", "change life for your user",
      "how much would that change"),
     ("overnight", "for your user")),
    # whether the founder's own experience of the problem generalises
    #
    # Distinct from the topic about first encountering the problem: that one
    # asks where this came from, this one asks whether one person's version
    # of it is everyone's. The bank has 27 "do you assume ..." questions and
    # they span every dimension there is -- vendor pricing, culture, urgency,
    # what a prospect will infer. They are NOT one subject and there is no
    # topic here for the shape of the question, because an answer that fits
    # all 27 would be a fallback wearing a topic's clothes. These two are one
    # subject: my experience versus everyone else's.
    (("you personally experience this", "your own daily experience",
      "representative of how most", "how urgent or common"),
     ("representative", "actually is")),
)

#: The founder-dimension answers, one per topic above, per persona. Same
#: discipline: quality is the only variable within a stage pair.
_WEAK_FOUNDER_TEXTS = (
    "I honestly can't think of one recently. Ages ago I rebuilt a bike over a "
    "winter and finishing it felt good, but nothing here has. I keep waiting "
    "for something to feel like that and it hasn't yet.",
    "The trophy, I think. I'd like people to know I did something. That's "
    "probably not the answer I'm meant to give but it's the true one.",
    "I can't remember the last day I finished energised. Most of them just "
    "end. I've never paid attention to what makes the difference, so I "
    "couldn't tell you what to do more of.",
    "I think about dropping it most weeks. What stops me is not having a "
    "better idea rather than believing in this one. I've never thought about "
    "what finishing would even look like.",
    "Most of it, I suppose. I do everything by hand because there's nobody "
    "else and I've never looked at what could be automated. It's not a "
    "decision, it's just how it is.",
    "Nothing's really come up. Nobody's offered me money to do anything I'd "
    "object to. I'd like to think I'd walk away but I've not been tested.",
    "Constantly. I've rewritten the same page four times and it's still not "
    "up. I couldn't tell you what I was improving on the last two goes.",
    "A lot, I'd assume. It's a real problem -- I've felt it myself. I've not "
    "asked anyone to put a size on it, so I couldn't tell you what it's "
    "actually worth to them.",
    "I suppose I do assume that, yes. It was bad enough for me that I "
    "assumed it's bad for everyone. I've never checked whether other people "
    "find it as annoying as I did.",
)

_STRONG_FOUNDER_TEXTS = (
    "The first interview where someone finished my sentence describing the "
    "problem. That's what landed -- not that they liked it, that they already "
    "had the words. I've chased that reaction as a signal ever since and "
    "nine of twelve gave it.",
    "The bridge. I'd rather this worked and nobody knew my name than the "
    "reverse, and I can tell that's true because the thing I reread when it's "
    "going badly is the interview notes, not anything about me.",
    "Tuesdays, alone, first four hours, phone in a drawer -- that's when "
    "anything real gets written. I worked it out by keeping a note for a "
    "fortnight of when I'd actually made progress, and it was the same slot "
    "every time. The days that wipe me out are the ones broken into pieces.",
    "Seriously, twice -- once after four interviews said the problem was real "
    "and unimportant. What kept me was the next three, who'd built their own "
    "spreadsheet for it. Done would mean someone other than me runs it and "
    "the thing still works.",
    "I write every onboarding email myself, one at a time. It does not scale "
    "and I am doing it deliberately until about thirty of them, because the "
    "replies are where I have learned what people actually expect -- two of "
    "the twelve interview findings came out of those replies rather than the "
    "interviews.",
    "I turned down a consulting retainer in November that would have paid for "
    "six months, because it was the same customers and it would have made me "
    "their supplier rather than a peer. The line is that I don't sell them "
    "the workaround I'm trying to replace.",
    "The pricing page, for about three weeks. I was polishing the wording "
    "because I didn't want to commit to a number, and it delayed the only "
    "test that would have told me whether the number was right.",
    "About a day a week of somebody's time, and I know that because nine of "
    "the twelve interviews put a number on it unprompted. For four of them "
    "it is also the thing that makes them dread the end of the month, which "
    "is the part that does not show up as hours.",
    "I assumed it and then tested it, because my version was the worst case "
    "-- I had it monthly and most people have it quarterly. Three of the "
    "twelve did not recognise it as a problem at all, and that is why the "
    "pitch now opens with the deadline rather than with the admin.",
)

_TRACTION_FOUNDER_TEXTS = (
    "The month our support person handled a week entirely without me and I "
    "only found out afterwards. What landed was that it kept working when I "
    "wasn't there -- more than any revenue number has.",
    "The bridge, and it took running this to know that. Early on I'd have "
    "said trophy. The thing I actually reread is the churn notes, which is "
    "not where you look if it is about you.",
    "Mornings before the team is on, twice a week, and I protect them because "
    "I measured it -- almost everything I've written that mattered came out "
    "of those. The weeks that wipe me out are the ones with four days of "
    "back-to-back calls and nothing finished.",
    "I nearly stopped eighteen months ago when we had nine customers and no "
    "growth. What kept me was one of the nine telling me what they'd go back "
    "to without us. Done would be it running profitably without me in it, "
    "and I'd want the filing logic to still be right a year after I left.",
    "I still do the first call with every customer above the middle tier. It "
    "does not scale and I know it, and I keep it because the pricing "
    "objections only show up there -- the last three tier changes all came "
    "out of those calls. It goes when someone else can hear the objection "
    "the same way.",
    "We turned down a reseller deal last year worth about a third of revenue, "
    "because they wanted us to white-label and stop talking to the end "
    "customer. The customer conversations are the only reason we know "
    "anything, so that was the line.",
    "The onboarding rewrite, about two months. I kept refining flows nobody "
    "had complained about while the import step -- which is where people "
    "actually drop -- sat untouched. That one cost us a quarter.",
    "A day a week back, and a penalty they stop paying -- about forty "
    "thousand a year for a firm of that size. The one that matters more is "
    "that the person who owns it stops being the one who gets blamed, which "
    "is what nineteen referrals are actually about.",
    "No, and checking is what moved the business. I built for my version, "
    "which was a monthly filing at a firm of forty. The customers who stay "
    "are ten-to-twenty-person firms with no finance lead, where it is "
    "quarterly and nobody owns it -- a different problem, and I would not "
    "have found it by consulting my own memory.",
)

_WEAK_TRACTION_FOUNDER_TEXTS = (
    "Nothing recently, no. Things get done and then the next thing starts. I "
    "suppose when we hit a hundred customers I felt something for an "
    "afternoon, and then it was back to the inbox.",
    "The trophy, probably. I'd like it to have been worth it and for people "
    "to know that. I've not really thought about it.",
    "I don't get days like that any more. It's all interruptions. I couldn't "
    "tell you what a good week looks like because I'm not sure I've had one "
    "this year, and I've never tried to work out why.",
    "I think about stopping fairly often, usually when something breaks at "
    "the weekend. I stay because there are people employed here now. I've no "
    "idea what done would look like -- I've never thought that far.",
    "Loads of it. I still do the invoices by hand every month and half the "
    "support. It's not on purpose, I've just never stopped to sort it out, "
    "and every month it's the same two days gone.",
    "Not really. We took a deal last year I wasn't comfortable with because "
    "we needed the revenue, and I've not thought much about where the line "
    "is since. It hasn't come up in a way I couldn't ignore.",
    "Yes, though I'd call it caring about it being right. I spent weeks on "
    "the new pricing page and it's still not live. I couldn't tell you what "
    "was wrong with the version from a month ago.",
    "It'd help them a lot, I think. Nobody's ever put a number on it and I've "
    "not asked. I know they keep paying, so it must be worth something.",
    "Probably, yes. I built it for the version I had and I've never gone "
    "back to check whether that's what our customers actually have. It "
    "hasn't occurred to me that it might be a different problem.",
)

assert len(_WEAK_FOUNDER_TEXTS) == len(_STRONG_FOUNDER_TEXTS) \
    == len(_TRACTION_FOUNDER_TEXTS) == len(_WEAK_TRACTION_FOUNDER_TEXTS) \
    == len(_FOUNDER_TOPICS)

_TRACTION_TOPICS = _TOPICS + _OPERATING_TOPICS

#: THE WEAK COUNTERPART AT EARLY TRACTION -- the other half of a comparison
#: that, until this existed, had only one side.
#:
#: `traction` proved COVERAGE at stage 4: report #96 was the first run to
#: assess six pillars of six. It proved nothing about DISCRIMINATION there.
#: weak and strong are a quality pair at Ideation and the engine separates
#: them cleanly -- health 20 against 92, eight root causes against two. At
#: Early Traction there was one persona, so a run could only ever come back
#: "strong", and a stage-4 engine that scored every founder well would have
#: looked exactly like the one we had.
#:
#: Same thirty subjects as `traction`, slot for slot, in the same order.
#: Quality is the only variable: no numbers anybody measured, nothing written
#: down, every system a memory, every problem noticed after it cost something.
#: This founder is not failing -- they have customers and staff and revenue,
#: which is the point. They are running a real business on recall and reaction.
_WEAK_TRACTION_TEXTS = (
    "Sixty-odd paying, I think -- I'd have to look. I hear from the same four "
    "or five who email a lot and I assume the rest are fine. Most came in "
    "through people I know, and I could not tell you which ones.",
    "I don't really plan the week. Whatever came in overnight sets it, and by "
    "Wednesday I've forgotten what I meant to do on Monday. The enterprise "
    "pilot has been sitting there for a month because I keep not deciding.",
    "It's a big market, that's about as far as I've got. There's a competitor "
    "everyone mentions -- I've never sat down and looked at what they do, I "
    "just hear the name when we lose one.",
    "We ship a fair bit. I couldn't tell you who uses what, we never put "
    "anything in to measure it. I know people drop off somewhere in setup "
    "because they email me about it, not because I can see it.",
    "Three tiers, and I picked the numbers because they felt about right when "
    "we started. Nobody's really pushed back, which I take as a good sign. I "
    "haven't changed them in a year and a half.",
    "There are four of us. Nothing is written down about who does what -- we "
    "just sort of know, and we work it out when it clashes. It has clashed a "
    "few times and it usually ends with me deciding.",
    "I haven't written any of that down. I know roughly what would hurt -- if "
    "the main channel dried up we'd be in trouble -- but I've never sat and "
    "listed it out, and I probably should.",
    "Quickly, usually, and then I go back and forth on it for a week "
    "afterwards. I don't write down why I decided something, so when it comes "
    "up again I'm arguing the same thing from scratch.",
    "Our support person said something a while back about me answering her "
    "tickets. I said I'd stop. I mostly haven't, because it's faster if I "
    "just do it, and I haven't asked her since whether it's still a problem.",
    "Because it's a real problem and people pay for it. I had a version of it "
    "myself. I don't have a sharper answer than that, which I notice when "
    "somebody asks me directly.",
    "Being the best at it, I suppose. Or the biggest. I haven't really "
    "thought about it in those terms -- I'd like people to rate us, but I "
    "don't know if they do because I've never asked.",
    "It takes me a couple of goes. I start with the compliance thing and then "
    "end up explaining the whole background, and I can usually see the point "
    "where the other person stops following.",
    "Sort of. I saw it happen at my old job rather than having it land on me "
    "directly. I've never been the person filing, which people do sometimes "
    "point out when I'm explaining it.",
    "A mix of things we built and a spreadsheet that's still holding up more "
    "than it should. I didn't really check what was out there first -- it was "
    "quicker to build it than to go looking.",
    "Support, mostly, and answering things at night. I only realised how much "
    "when someone asked me this -- I've never actually looked at where the "
    "week goes. It just feels full.",
    "I hand things over and then they come back wrong, so I end up taking "
    "them back. I don't really teach it -- I explain it once and hope. It's "
    "quicker to do it myself, which I know is the wrong answer.",
    "Most of it, honestly. If I were out for a week the filings wouldn't go, "
    "because the rules for the odd cases are only in my head. I've been "
    "meaning to write them down since roughly last summer.",
    "Not really. There's a doc from when we started that's out of date. "
    "Everything current lives in whoever did it last, which means when they're "
    "away we guess, and we've got it wrong twice that I know about.",
    "We've never written roles down. Everyone kind of does everything, which "
    "was fine at two people. There was a thing in February where nobody fixed "
    "some bad data for about a week because we all thought it wasn't ours.",
    "It comes to me. There's no rule, it just does, and if I'm busy it sits "
    "until I get to it. A refund argument sat for four days last month for "
    "that reason.",
    "They seem busy and things get done, so I assume it's fine. We don't have "
    "targets for anyone. I'd probably notice if somebody stopped entirely, "
    "and I'm not sure I'd notice anything short of that.",
    "Yes, and far too long -- the better part of a year. I kept thinking it "
    "would sort itself out and hiring again felt like more work than the "
    "problem. I never said anything to them directly, which I regret.",
    "People leave, some months more than others. I don't have the number. I "
    "usually find out when the payment stops rather than before, and I've "
    "never gone back and asked any of them why.",
    "They find us somehow and then some of them buy. There's an accountant "
    "involved somewhere near the end and that's often where it goes quiet, "
    "but I haven't mapped it out or counted where they drop.",
    "It depends who's asking. I've given different numbers to different "
    "people for the same thing, and once I had to honour both. I keep meaning "
    "to fix the page so I stop improvising.",
    "When something makes me look -- usually a payment going out. I know "
    "roughly where we are. Last month felt fine but I couldn't tell you "
    "whether that was the business or one big invoice landing.",
    "We've got customers and revenue's up, mostly. I'd show them that. I "
    "don't have the retention or usage numbers to hand, so it would be the "
    "growth line and me explaining why I believe in it.",
    "We put things out and see what happens. The last one got some signups -- "
    "I don't know how many turned into anything, because we didn't decide "
    "beforehand what would count as it having worked.",
    "We built it for bigger firms than the ones who actually stay, I think. "
    "I've noticed the pattern but I've never gone and checked it properly, "
    "and the website still says what it said at the start.",
    "I'm more tired and shorter with people than I was. I haven't really "
    "stopped to think about what's changed. The thing I don't say is that I'm "
    "not sure I'd do it again, and I've never said that to anyone.",
    # --- the same six subjects
    "Probably, yes. It doesn't feel like what I described at the start but I "
    "couldn't tell you when that changed or what it is now. Nobody sat down "
    "and decided it -- it just drifted, and the website still describes the "
    "original version.",
    "We're fine, I think. It's the same as I'd do with my own stuff and "
    "nobody's ever complained. I've not had anyone look at it and I don't "
    "really know what we'd be expected to have.",
    "Two out of five, if I'm honest. I don't have a pipeline as such -- there "
    "are some conversations going on and I couldn't tell you how many or "
    "where any of them are. They either happen or they don't.",
    "Every one gets written fresh. I've got old ones in my email I copy from "
    "when I remember, and they've drifted apart, so I've definitely told two "
    "people different things about what's included.",
    "I read them all myself. I'm not a lawyer and I know that's not really "
    "enough, but getting someone to look at every one costs money and it "
    "hasn't caused a problem yet that I'm aware of.",
    "Whenever I get to it, which is not often. There'll be a burst and then "
    "nothing for two months. I know that's not how it's supposed to work but "
    "it's always the thing that gets dropped when the week fills up.",
)

#: Current Problem, at Early Traction, weakly answered. Same eight subjects
#: as every other persona.
_WEAK_TRACTION_CP_TEXTS = (
    "Everything, a bit. Probably that it's all on me and there's no slack "
    "anywhere -- if I stopped for a fortnight I don't know what would "
    "happen. I couldn't name one thing above the others.",
    "More hours, or another me. I know that's not a real answer. Nothing "
    "specific is blocking it, I just never get to the things that aren't "
    "already on fire.",
    "We tried a campaign a few months ago and it didn't really go anywhere. I "
    "couldn't tell you why it stopped -- we just stopped doing it and moved "
    "on to whatever was next.",
    "Me, probably. Or the setup process, which one person built and nobody "
    "else understands. I've thought about it and then not done anything "
    "about it, because it's been fine so far.",
    "Writing down how the filing logic works. It's been on my list since the "
    "summer. Every week there's something more urgent and it's the thing "
    "that gets dropped.",
    "I don't really look at numbers, so there isn't one I'm avoiding "
    "specifically. I suppose if I checked how many people actually still use "
    "it I might not like the answer.",
    "Support. We fix whatever people are complaining about, it goes quiet, "
    "and then it's back in a different form a month later. We've been round "
    "that loop a few times now without ever asking why.",
    "A refund decision last week that our support person could have made. It "
    "came to me because there's no rule about it -- there's no rule about "
    "most things, so everything comes to me.",
)

assert len(_WEAK_TRACTION_TEXTS) == len(_TRACTION_TEXTS)
assert len(_WEAK_TRACTION_CP_TEXTS) == len(_CURRENT_PROBLEM_TOPICS)

#: The Current Problem answers, one per topic above, per persona. Same
#: discipline as everywhere else in this file: weak and strong differ in
#: QUALITY and cover identical subjects, so a run that separates them is
#: measuring the engine and not the topic list.
_WEAK_CP_TEXTS = (
    "Honestly? That I have not started. I think about it constantly and then "
    "the day goes and I have done nothing that counts. I could not tell you "
    "what the actual blocker is, which is probably the real answer.",
    "I would need to stop feeling like I am going to get it wrong. I know "
    "that is not a thing I can put in a calendar, but that is the truth of "
    "it -- nothing concrete is stopping me.",
    "I started a landing page about four months ago and never finished it. I "
    "did not stop for a reason I could name. I just opened it less and less "
    "and then stopped opening it.",
    "Me, I suppose. There is nothing else to break -- it is all in my head "
    "and a half-finished document. I have never thought about it in those "
    "terms because there is nothing running to stop.",
    "Emailing the three people who said they would try it. They said that "
    "weeks ago and I have not replied, and now it feels too late to, which "
    "makes it easier to keep not doing it.",
    "I do not have one I am avoiding because I do not track anything. There "
    "is no number anywhere. I know roughly what I have spent and I would "
    "rather not add it up.",
    "Deciding what this actually is. I settle it, feel fine for a week, then "
    "it is open again and I am back to the same argument with myself. I have "
    "had that argument probably five times now.",
    "Everything lands on me -- there is no one else. I would not know how to "
    "hand any of it over even if there were, because none of it is written "
    "down anywhere outside my own head.",
)

_STRONG_CP_TEXTS = (
    "Distribution. I have twelve interviews saying the problem is real and a "
    "prototype two people use weekly, and I still have no repeatable way to "
    "reach the next hundred. Everything so far came from my own network, so I "
    "have proved the problem and not the channel.",
    "One outbound channel tested end to end -- fifty contacts, a measured "
    "reply rate, one booked call. It is booked in for Thursday and Friday "
    "this week, and if the reply rate is under four percent I will treat the "
    "channel as dead and try the next one.",
    "I tried warm intros first: thirty-one asks, nine calls, four people who "
    "said they would pay. It stalled because it does not scale past people "
    "who already know me, and I let it run three weeks longer than the data "
    "justified because the calls were pleasant.",
    "The two weekly users. They are the entire evidence base, and if both "
    "churned I would have no signal at all -- which is why I speak to each of "
    "them fortnightly and log it, rather than assuming quiet means content.",
    "Writing the pricing page. I have the willingness-to-pay data from nine "
    "of the twelve interviews and I have been treating it as a design task "
    "when it is actually a commitment I do not want to make yet. It is on "
    "this week's list with a date against it.",
    "Interview-to-trial conversion. Twelve conversations, two people using "
    "it -- that is seventeen percent, and I have been telling myself the "
    "sample is too small rather than that the pitch is not landing.",
    "Scope. It comes back every time I talk to a new user with an adjacent "
    "problem. I wrote down the one job it does in March and I reread that "
    "line before I commit to anything now, which has cut it from weekly to "
    "about monthly.",
    "Right now, everything, and correctly -- there is one of me. What I do "
    "have is a written note of which decisions I would hand over first when "
    "there are two of us, and pricing is not one of them.",
)

_TRACTION_CP_TEXTS = (
    "Churn. We are at six percent monthly on a hundred and forty accounts, "
    "which quietly eats most of what sales brings in. Everything else -- "
    "hiring, the roadmap, the raise -- is downstream of that number, and I "
    "have known it for two quarters.",
    "A named owner for retention who is not me. I have the role written up "
    "and the budget signed off, and until someone holds it, it gets my "
    "attention only in the weeks nothing else is on fire.",
    "We ran a win-back campaign in June -- two hundred lapsed accounts, "
    "eleven came back, three of those churned again. It stalled because we "
    "were treating the symptom; nobody had asked the eleven why they left in "
    "the first place, so we had nothing to fix.",
    "The onboarding automation. One engineer built it, it touches billing and "
    "provisioning, and if it broke tomorrow every new account would stall at "
    "signup. It is the one system with no runbook, and that is on this "
    "quarter's list to fix.",
    "The conversation with the engineer who built that automation about "
    "documenting it. He is stretched and I do not want to add to it, so I "
    "have let it sit for six weeks -- which is exactly how a single point of "
    "failure stays one.",
    "Cohort retention past month three. We report monthly churn at the "
    "all-hands because it looks survivable. The cohort curve is the honest "
    "version and I look at it a good deal less often than I should.",
    "Support load. We fix the top complaint, it goes quiet for a month, and "
    "then a different flavour of the same confusion comes back. We have done "
    "that three times now, which tells me we keep patching the surface "
    "instead of the underlying model.",
    "A refund decision last week that the support lead is entirely capable of "
    "making. It reached me because the limit is written in my head and not in "
    "the policy, so people escalate rather than guess. That is my fault, not "
    "theirs, and it is a one-afternoon fix I keep deferring.",
)

assert len(_WEAK_CP_TEXTS) == len(_STRONG_CP_TEXTS) == len(_TRACTION_CP_TEXTS) \
    == len(_CURRENT_PROBLEM_TOPICS)

assert len(_WEAK_TEXTS) == len(_STRONG_TEXTS) == len(_TOPICS)
assert len(_TRACTION_TEXTS) == len(_TRACTION_TOPICS)

#: ALLY ITSELF, AT MVP — the product diagnosing its own founder.
#:
#: Written from what this repository actually contains and what building it
#: actually turned up, not from an idea of a founder. Ally has a working
#: product, a handful of testers, no paying customers, `PUBLIC_LAUNCH=false`
#: so every feature is free, and a small team. Strong in the places real
#: effort went (the engine, the rebuild procedure, the deploy pipeline) and
#: genuinely weak in the places nobody has got to yet (pricing, distribution,
#: anything written down about who owns what).
#:
#: The honest answers are the point. A persona that made Ally sound good would
#: measure nothing.
_ALLY_MVP_TEXTS = (
    # 0 customers / validation
    "None paying. About a dozen testers, all of them people we know or the "
    "team itself, and the eighteen accounts held at Pro in the launch "
    "migration are ours. So the product works and nobody has yet proved they "
    "would pay for it, which are different facts and I try not to blur them.",
    # 1 planning / priorities
    "Badly. The week is set by whatever broke, and this week that was a "
    "production deploy and a test suite nobody could read. I have not planned "
    "a week in advance since we started building.",
    # 2 market / competitors
    "Early-stage founders in India who cannot afford a real advisor. I have "
    "not sized it and I have not looked properly at who else does this -- "
    "there are coaching programmes and there are generic AI chat products, "
    "and I have never sat down and worked out which of them a founder picks "
    "instead of us.",
    # 3 product / analytics
    "The engine is instrumented in the sense that every diagnosis writes a "
    "report row and every model call is logged with its cost. What we do not "
    "have is product analytics on the human side -- where someone abandons "
    "the journey, how far into the thirty questions they get. I could tell "
    "you what the engine did and not what the founder felt.",
    # 4 pricing
    "Three plans exist in the catalog and nobody has ever paid one of them. "
    "The numbers came from what felt reasonable for an Indian founder, not "
    "from anyone telling me what the problem costs them. Free carries almost "
    "the whole product today on purpose, because the people using it are our "
    "own testers.",
    # 5 team
    "Small -- a few engineers and me. Nothing about who owns what is written "
    "down; we work it out in conversation, which held fine at three people "
    "and is starting not to. When two of us disagree it comes to me, and "
    "that is not a rule anyone agreed, it is just what happens.",
    # 6 risk
    "The one that actually worries me: the whole diagnosis depends on an LLM "
    "classifying answers, and until this week nobody had proved that worked "
    "in production. Not once. The report renders either way, which is exactly "
    "what makes it dangerous. I have not written the rest down.",
    # 7 decisions / stress
    "Fast, and then I revisit them at night. Under pressure I do the thing in "
    "front of me rather than the thing that matters -- last week that meant "
    "shipping a deploy fix while the question about whether scoring works at "
    "all sat untouched.",
    # 8 feedback / blind spots
    "The sharpest feedback I have had recently came from our own tooling "
    "rather than a person: a review of the codebase found that three "
    "documents described behaviour the code no longer had, and one of them "
    "was mine. I would rather have heard it from a teammate first, and nobody "
    "said it.",
    # 9 purpose / motivation
    "Because a founder at this stage cannot get an honest read on their own "
    "business, and the advice they can afford is generic. I watched people "
    "pay for programmes that told them what they already knew. That is worth "
    "a few years.",
    # 10 doing it well
    "Trusted. If a founder reads their report and says 'that is the thing I "
    "have been avoiding', we did it. Not the biggest, not the first -- I do "
    "not know how I would measure trusted yet, which is a gap.",
    # 11 the pitch
    "Ally asks a founder about themselves and their business, and gives them "
    "a diagnosis: what is actually wrong, the root causes underneath it, and "
    "the three things to do next. I still take two goes to say it, because I "
    "start explaining the six-pillar model instead of the outcome.",
    # 12 own encounter
    "I have been the founder who could not tell whether the problem was the "
    "product or the market, and paid for advice that answered neither. Second "
    "-hand more than first -- I have watched it closely more than I have "
    "lived every version of it, and people do point that out.",
    # 13 what it is built with
    "FastAPI and React, Postgres on RDS, Claude for the classification and "
    "OpenAI for embeddings, Gotenberg for the PDFs. We build the part nobody "
    "else does -- the model of what a founder's problems actually are -- and "
    "buy everything else.",
    # 14 time wasted
    "Firefighting infrastructure. I spent most of this week on a deploy "
    "pipeline, a migration graph and a test suite, none of which is the "
    "product. It needed doing and it was still not the thing that gets us a "
    "paying customer.",
    # 15 delegation
    "Poorly. I explain the task and not the outcome, and then I am surprised "
    "when it comes back as the thing I described rather than the thing I "
    "wanted. Nobody has been taught how I want anything done, because I have "
    "never written it down to teach from.",
    # 16 founder dependency
    "Most of it. If I were out for a week the product would keep serving, "
    "because it is deployed and the pipeline works -- but no decision would "
    "get made, and anything about the diagnosis model lives in my head and a "
    "few documents I wrote.",
    # 17 what is written down
    "More than there was. The rebuild procedure is written down and has been "
    "run twice, and the deploy is documented properly now. What is not "
    "written down is anything about how we work: no process for who reviews "
    "what, no runbook for anything a person does rather than a machine.",
    # 18 role clarity
    "Not in writing. Everyone does a bit of everything, which is honest for "
    "four people and is already costing us -- things fall between us and I "
    "find out when they have been sitting for days.",
    # 19 decision rights
    "It comes to me. There is no rule, and if I am deep in something it "
    "waits. That is fine at this size and it is the first thing I would fix "
    "if we hired two more people.",
    # 20 performance
    "I have no idea, honestly. There are no targets for anyone. Things get "
    "done and I assume that means it is working, and I would probably only "
    "notice a problem when something broke.",
    # 21 kept someone on
    "Not yet -- we have not been going long enough or hired widely enough for "
    "that to have come up.",
    # 22 churn
    "No churn because no paying customers. Testers do go quiet, and I do not "
    "chase them or ask why, which is probably the most useful signal "
    "available to me right now and I am not collecting it.",
    # 23 buying journey
    "There isn't one. Every person using Ally got here because somebody on "
    "the team told them about it. I could not describe the steps a stranger "
    "would go through, because no stranger ever has.",
    # 24 presenting pricing
    "It is on the plans page and I have never talked anyone through it. The "
    "first time I have to justify a number to a founder who is deciding will "
    "be the first real test of whether it is right.",
    # 25 cash
    "I look when something prompts me. We are spending on infrastructure and "
    "model calls against no revenue, so the number only moves one way and I "
    "know roughly where it is without a schedule for checking.",
    # 26 evidence of demand
    "Weak, and I would say so to an investor. What I have is a working "
    "product and testers who finish the journey. What I do not have is one "
    "person outside our network who wanted it enough to pay. Any honest "
    "version of the pitch has to lead with the model, not with traction.",
    # 27 campaign
    "We have not run one. Nothing has been launched, nothing has been "
    "marketed, and there is no definition of success waiting for when we do.",
    # 28 ICP drift
    "I do not know yet -- there are not enough real users to have drifted "
    "from. We designed for early-stage founders in India and the testers are "
    "mostly people like us, which is not the same thing and I am aware of it.",
    # 29 how the founder has changed
    "I am far more suspicious of things that look like they are working. This "
    "week a report rendered perfectly with zero model calls behind it, and "
    "that has changed how I read every green tick since. The thing I have not "
    "said out loud is that I am not sure the product is good yet -- only that "
    "it runs.",
    # 30 problem drift
    "It has narrowed and I noticed late. We started on 'founders need advice' "
    "and what the product actually does is tell a founder the one thing they "
    "are avoiding. The six-pillar model is how we get there, not what we "
    "sell, and I still describe it the wrong way round.",
    # 31 data privacy
    "We hold what founders say about their businesses at their most honest, "
    "which is about as sensitive as it gets. Row-level security is on, "
    "founder data is deliberately never in the repository, and backups were "
    "confirmed at seven days -- this week, because nobody had checked before.",
    # 32 pipeline
    "One out of five. There is no pipeline. There are conversations with "
    "people we know and no way to predict any of them, because none of them "
    "have been asked for money.",
    # 33 proposals
    "Nothing reusable, because we have never sent one.",
    # 34 contract oversight
    "I read them myself and I am not qualified to. It has not caused a "
    "problem yet, which is not the same as it being fine.",
    # 35 publishing
    "Almost never. There is a plan to write and it is the first thing "
    "dropped when a week fills up, which is every week.",
    # 36 the headline problem
    "That nobody has paid us. Everything else -- the engine, the pipeline, "
    "the tests -- is real work and none of it answers whether a founder "
    "values this enough to buy it. I have been able to make progress on the "
    "building, so I have kept building.",
    # 37 what would need to be true
    "One founder outside our network completing a diagnosis and telling me it "
    "was worth paying for. Nothing technical is stopping that this week. What "
    "stops it is that I have not asked anyone.",
    # 38 already tried
    "We put the product in front of the team and a few friendly founders and "
    "watched them use it. It stalled because I treated 'they finished the "
    "journey' as the result, and never asked the next question, which was "
    "whether they would pay.",
    # 39 single point of failure
    "The classifier. If the model call fails, every answer scores the same "
    "and the report comes out looking complete and saying nothing. That is "
    "the failure I would least likely notice, and it went unverified in "
    "production until this week.",
    # 40 avoiding
    "Asking a tester for money. I have had the conversation ready for weeks "
    "and I keep finding an infrastructure problem to solve instead, and "
    "there is always a real one available.",
    # 41 the avoided metric
    "How many testers finish the whole journey. I know how many started. I "
    "have not looked at how many reached the report, because I think I know "
    "the answer and I would rather not have it confirmed.",
    # 42 recurring problem
    "Things that look finished and are not. A test suite that was green "
    "because it never ran, a document describing a feature that had been "
    "removed, a report that renders with nothing behind it. Same shape every "
    "time: the surface says done and nobody checked underneath.",
    # 43 decisions landing on me
    "All of them, and this week that included deciding whether to merge a "
    "pull request nobody else had looked at. There is no reviewer other than "
    "me, so 'should this ship' is a question with one possible answer.",
    # 44 what landed
    "Watching the whole journey run end to end against a database rebuilt "
    "from nothing but the repository. Forty-six questions, a report at the "
    "end, all six pillars assessed. It was the first time the thing existed "
    "as a system rather than as parts I believed in.",
    # 45 trophy or bridge
    "The bridge, and I can tell that is true because the part I reread is the "
    "founder's report, not anything about us. Early on I would probably have "
    "said trophy.",
    # 46 energy
    "Early mornings before anything is on fire, and I do not protect them -- "
    "they just happen when they happen. The weeks that flatten me are the "
    "ones spent entirely on infrastructure, because at the end of them the "
    "product is exactly where it was.",
    # 47 why I stay / what done means
    "I have thought about stopping, mostly on the days when the honest answer "
    "to 'is this good' was 'I do not know'. What keeps me is that the problem "
    "is real whether or not we solve it. Done would be a founder we have "
    "never met paying for a diagnosis and acting on it.",
    # 48 the unscalable thing
    "I read the reports. Every one, personally, before anyone sees it. It "
    "does not scale and it is the only reason I know what the engine actually "
    "produces rather than what I hope it produces. It goes when I trust the "
    "scoring, and I do not yet.",
    # 49 the line
    "Nothing has tested it properly, which I notice when I am asked. The "
    "nearest thing: I will not ship a report that says something confident we "
    "cannot support, and this week that meant refusing to treat a run with "
    "zero model calls as a result.",
    # 50 perfectionism
    "The infrastructure, for most of a week. Migrations, test fixtures, a "
    "drift check -- all of it genuinely broken and none of it the thing that "
    "gets a customer. I was polishing what I knew how to fix.",
    # 51 what it is worth to the user
    "A founder at this stage burns months on the wrong problem, and the "
    "advice that would have caught it costs more than they have. That is what "
    "we are worth if we work. Nobody has put a number on it because nobody "
    "has been asked to.",
    # 52 does my experience generalise
    "I assume it more than I should. I built this for the founder I have "
    "been, and the testers are mostly people like me, so I have had very "
    "little chance to be wrong out loud. That is the assumption I would most "
    "like tested.",
)

#: THE SAME BUSINESS, RUN BY SOMEONE WHO HAS NOT DONE THE WORK.
#:
#: `ally_mvp`'s counterpart, and the pair is the discrimination test at stage
#: 3. Identical facts -- Ally, Prototype/MVP, a dozen testers, no paying
#: customers, a handful of people, everything free -- because if the two
#: personas described different businesses, a difference in the report would
#: not tell you which of the two caused it.
#:
#: What differs is entirely the founder: no measurement, no notes, no second
#: opinion, nothing written down, and above all no idea which of it matters.
#: `ally_mvp` names the thing it is avoiding; this one has not noticed there
#: is one.
_ALLY_WEAK_TEXTS = (
    # 0 customers
    "Some people are using it. The team and a few friends -- I'd have to "
    "check how many. Nobody's paying yet but that's not really the stage "
    "we're at.",
    # 1 planning
    "I don't plan as such. I open the laptop and deal with what's there. It "
    "mostly works out.",
    # 2 market
    "Every founder needs this, so it's huge. I haven't looked at competitors "
    "-- there's nothing quite like what we're doing.",
    # 3 product
    "We ship constantly. I don't have numbers on what gets used, but the "
    "product's in good shape and people seem happy with it.",
    # 4 pricing
    "There are three plans. The numbers felt right. Nobody's complained "
    "about them, so I think we're fine there.",
    # 5 team
    "There's a few of us and everyone knows what they're doing. We don't "
    "need process at this size -- we just talk.",
    # 6 risk
    "Nothing major. The tech is solid and we've got AWS behind it. I don't "
    "really think in terms of risks, I just fix things when they come up.",
    # 7 decisions
    "I decide quickly and move on. Overthinking kills startups. I don't write "
    "decisions down, I just remember them.",
    # 8 feedback
    "People are generally positive. Nobody's told me anything hard recently. "
    "I'd like to think I'm approachable enough that they would.",
    # 9 purpose
    "Because AI is going to change how founders get advice and we want to be "
    "there. It's a big opportunity and the timing is right.",
    # 10 doing it well
    "Being the first to really crack it. If we're the name people think of "
    "when they think founder diagnosis, that's the win.",
    # 11 the pitch
    "It's an AI platform for founders -- diagnosis, insights, a whole system "
    "around their business. It takes me a while to explain because there's a "
    "lot to it.",
    # 12 own encounter
    "I've been around founders for years and I've seen the problem. Not "
    "something I lived through myself exactly, but I know it's real.",
    # 13 tools
    "We built most of it ourselves. I didn't look much at what was out there "
    "-- it was faster to just build it the way I wanted.",
    # 14 time wasted
    "I'm busy the whole time, so not much is wasted. There's always more to "
    "do than hours. I've never actually looked at where the time goes.",
    # 15 delegation
    "I hand things over when I'm stretched. If it comes back wrong I redo it. "
    "Faster than explaining it twice.",
    # 16 founder dependency
    "It'd be fine. The system runs itself, it's all deployed. I'd pick up "
    "whatever piled up when I got back.",
    # 17 written down
    "It's mostly in my head and that's been fine. We're too small for "
    "documentation -- it'd be out of date by the time anyone read it.",
    # 18 role clarity
    "Everyone knows their bit. Writing it down would make it feel like a "
    "corporate job, and that's not what we are.",
    # 19 decision rights
    "It comes to me and that's how it should be at this stage. I'm the one "
    "with the full picture.",
    # 20 performance
    "They're working hard, I can see that. I'd know if someone wasn't pulling "
    "their weight.",
    # 21 kept someone on
    "No, hasn't come up.",
    # 22 churn
    "People drift off sometimes but they're not paying, so it's not churn "
    "really. They'll come back when it's more polished.",
    # 23 buying journey
    "They hear about it and they sign up. I haven't mapped it because there "
    "isn't much to map yet.",
    # 24 presenting pricing
    "It's on the page. I'd explain it if someone asked, though nobody has.",
    # 25 cash
    "I check now and then. We're spending on infrastructure and the AI calls, "
    "which is what you'd expect at this stage.",
    # 26 evidence
    "The product works end to end, which is more than most people have at "
    "this point. That's the evidence. Revenue follows the product.",
    # 27 campaign
    "Not yet -- we'll do marketing once it's ready. No point driving people "
    "to something that isn't finished.",
    # 28 ICP drift
    "It's early-stage founders and that hasn't changed. The testers are "
    "roughly that.",
    # 29 how the founder has changed
    "More confident, I'd say. I know the space better than I did. I can't "
    "think of anything I've got badly wrong.",
    # 30 problem drift
    "Same problem we started with. Founders need better advice, and that's "
    "what we're building.",
    # 31 data privacy
    "It's on AWS with all the standard stuff. I haven't had anyone look at "
    "it specifically but I'm not worried about it.",
    # 32 pipeline
    "There isn't one yet and that's fine -- we're not selling. I'd say a "
    "three because the interest is there.",
    # 33 proposals
    "Haven't needed one.",
    # 34 contracts
    "I read them. It's not complicated stuff.",
    # 35 publishing
    "We'll start once there's something to announce. No point before.",
    # 36 the headline problem
    "Getting it finished, really. There's a long list and I'm the bottleneck "
    "on most of it. Once the product's properly done the rest follows.",
    # 37 what would need to be true
    "More hours, or another engineer. It's a throughput problem more than "
    "anything.",
    # 38 already tried
    "We showed it to some founders and they liked it. That went fine -- "
    "there wasn't really anything to stall.",
    # 39 single point of failure
    "Nothing that worries me. It's deployed and it's been stable.",
    # 40 avoiding
    "Nothing I can think of. I work through the list.",
    # 41 avoided metric
    "I'm not avoiding any of them. I don't look at numbers much because at "
    "this stage they don't tell you anything.",
    # 42 recurring problem
    "Nothing recurring. Things come up and we deal with them.",
    # 43 decisions landing on me
    "All of them, but that's normal for a founder. It's my company.",
    # 44 what landed
    "Getting it live. Seeing the whole thing work felt good after all the "
    "months of building.",
    # 45 trophy or bridge
    "The trophy, I'd say. I'd like this to be the thing I'm known for.",
    # 46 energy
    "I'm energised most of the time, honestly. I don't really track it -- if "
    "I'm working on the product I'm fine.",
    # 47 why I stay / done
    "Never seriously thought about stopping. Done would be a big exit, or "
    "the platform everyone uses.",
    # 48 the unscalable thing
    "Not much -- it's all automated, that's the point of it. I suppose I'm "
    "doing everything, but that's just being early.",
    # 49 the line
    "I'd never do anything dodgy. Hasn't come up.",
    # 50 perfectionism
    "I wouldn't call it perfectionism, I'd call it standards. I'd rather it "
    "was right. It hasn't cost us anything I can point to.",
    # 51 what it is worth
    "A lot -- founders waste years on the wrong things. I haven't put a "
    "number on it but it's obviously valuable.",
    # 52 does my experience generalise
    "I think so. I understand this space well and the problem's the same for "
    "everyone at this stage.",
)

#: A question that matches no topic still gets an answer of the right
#: quality. Quality is the variable under test; subject is not, so the
#: fallback is deliberately topic-neutral -- it must not smuggle in evidence
#: (or the absence of it) about a dimension the question never raised.
FALLBACKS = {
    "weak": "Honestly, no -- I have not done that. I keep meaning to and then "
            "find something else to deal with instead.",
    "strong": "Yes, and I can point at where -- I write these down as I go "
              "and review them on a set day rather than when I happen to "
              "remember.",
    # Same shape as strong's, in the operator's voice. Still topic-neutral:
    # it must not smuggle in evidence about a dimension the question did not
    # raise, which is the whole reason the fallback is written this way.
    "traction": "Yes, and I can show you where -- we write these down as we "
                "go and go through them at the monthly rather than when "
                "somebody happens to remember.",
    # weak's shape in the operator's voice, and topic-neutral for the same
    # reason: it must not say anything about a dimension the question did not
    # raise, or a fallback becomes evidence.
    "weak_traction": "No, not really -- I keep meaning to and then something "
                     "comes in and it goes to the bottom of the list again.",
    # Topic-neutral like the rest: it must not smuggle in evidence about a
    # dimension the question never raised.
    "ally_mvp": "Partly, and not deliberately -- it is one of the things that "
                "has never had a proper pass, so whatever is true of it today "
                "is an accident rather than a decision.",
    "ally_weak": "Not really, no. It hasn't come up as a problem so I've not "
                 "spent time on it.",
}

#: Every persona also carries the Current Problem topics, appended last.
#:
#: Unlike the operating topics, these are NOT traction-only: all three stage
#: groups have a Current Problem phase, so a weak or strong founder meets
#: these questions too and was falling back on three of four of them. Adding
#: them to weak and strong does not break comparability with earlier runs the
#: way changing a topic would -- the first fifteen slots are untouched and
#: still match what they always matched. What changes is that the phase which
#: used to be measuring the fallback line now measures the persona.
ANSWER_BANK = {
    "weak": tuple(zip(_TOPICS + _CURRENT_PROBLEM_TOPICS + _FOUNDER_TOPICS,
                      _WEAK_TEXTS + _WEAK_CP_TEXTS + _WEAK_FOUNDER_TEXTS)),
    "strong": tuple(zip(_TOPICS + _CURRENT_PROBLEM_TOPICS + _FOUNDER_TOPICS,
                        _STRONG_TEXTS + _STRONG_CP_TEXTS
                        + _STRONG_FOUNDER_TEXTS)),
    # The only persona with the operating topics. weak and strong keep exactly
    # the fifteen they have always had, so every earlier run is still
    # comparable with every later one.
    "traction": tuple(zip(_TRACTION_TOPICS + _CURRENT_PROBLEM_TOPICS
                          + _FOUNDER_TOPICS,
                          _TRACTION_TEXTS + _TRACTION_CP_TEXTS
                          + _TRACTION_FOUNDER_TEXTS)),
    # The quality pair at Early Traction. Identical topics to `traction`, slot
    # for slot, so a run that separates the two is measuring the engine and
    # not which subjects came up.
    "weak_traction": tuple(zip(_TRACTION_TOPICS + _CURRENT_PROBLEM_TOPICS
                               + _FOUNDER_TOPICS,
                               _WEAK_TRACTION_TEXTS + _WEAK_TRACTION_CP_TEXTS
                               + _WEAK_TRACTION_FOUNDER_TEXTS)),
    # Ally's own founder at MVP. One flat tuple in topic order rather than the
    # three-part split the others use -- it was written against the topic list
    # as a whole, and splitting it would only invite the halves to drift.
    "ally_mvp": tuple(zip(_TRACTION_TOPICS + _CURRENT_PROBLEM_TOPICS
                          + _FOUNDER_TOPICS, _ALLY_MVP_TEXTS)),
    # The same business without the work behind it -- the stage-3 quality pair.
    "ally_weak": tuple(zip(_TRACTION_TOPICS + _CURRENT_PROBLEM_TOPICS
                           + _FOUNDER_TOPICS, _ALLY_WEAK_TEXTS)),
}

#: The texts alone, in topic order -- the index-based fallback when no
#: question text is available, and what anything importing these expects.
#:
#: These include the Current Problem texts, so that this list stays the same
#: length and the same order as the persona's entry in ANSWER_BANK. A caller
#: with no question text picks by `n % len(answers)`, and if these were the
#: bare topic texts while the bank had eight more, that index would address a
#: different set of answers than the one a question-bearing caller sees.
WEAK_ANSWERS = _WEAK_TEXTS + _WEAK_CP_TEXTS + _WEAK_FOUNDER_TEXTS
STRONG_ANSWERS = _STRONG_TEXTS + _STRONG_CP_TEXTS + _STRONG_FOUNDER_TEXTS
TRACTION_ANSWERS = (_TRACTION_TEXTS + _TRACTION_CP_TEXTS
                    + _TRACTION_FOUNDER_TEXTS)
WEAK_TRACTION_ANSWERS = (_WEAK_TRACTION_TEXTS + _WEAK_TRACTION_CP_TEXTS
                         + _WEAK_TRACTION_FOUNDER_TEXTS)

ALLY_MVP_ANSWERS = _ALLY_MVP_TEXTS
ALLY_WEAK_ANSWERS = _ALLY_WEAK_TEXTS

PERSONAS = {"weak": WEAK_ANSWERS, "strong": STRONG_ANSWERS,
            "traction": TRACTION_ANSWERS,
            "weak_traction": WEAK_TRACTION_ANSWERS,
            "ally_mvp": ALLY_MVP_ANSWERS,
            "ally_weak": ALLY_WEAK_ANSWERS}


#: A defining term is worth two, a supporting term one, and two points are
#: needed to match at all. So one defining term is enough, two supporting
#: terms are enough, and a single supporting term is not -- which is the
#: point: "the last time you..." opens a dozen questions that have nothing
#: to do with time management, and a wrong answer is worse than the generic
#: one. It gets scored as though the founder failed to address a subject
#: they were never asked about, which is exactly how RC-441 Weak Product
#: Analytics came to be detected against a founder whose answer described an
#: instrumented product.
_DEFINING_WEIGHT, _SUPPORTING_WEIGHT = 2, 1
_MATCH_THRESHOLD = 2


def _score(topic, text: str) -> tuple[int, int]:
    """(defining hits, total score) for one topic against one question.

    Terms match at a word boundary. That matters: plain substring matching
    scored "Which one recharges you?" against the pricing answer, because
    "charge" sits inside "recharges". Stems still work -- "plan" matches
    "planning" -- because only the start is anchored.

    Defining hits lead the comparison so that a question naming several
    topics goes to the one it is really asking about: "could fail in a way
    that costs you real time or money" scores two either way, but only risk
    scores it on a defining term.
    """
    defining, supporting = topic
    d = sum(1 for t in defining if re.search(r"\b" + re.escape(t), text))
    sup = sum(1 for t in supporting if re.search(r"\b" + re.escape(t), text))
    return d, d * _DEFINING_WEIGHT + sup * _SUPPORTING_WEIGHT


def match_answer(question_text: str, persona: str = "weak") -> tuple[str, bool]:
    """(answer, matched) for one question -- the answer whose topic scores
    highest, or the persona's fallback when nothing clears the threshold.

    `matched` is reported at the end of each phase, because a run where most
    questions fell back is measuring the fallback line, not the persona, and
    its bands should be read that way.
    """
    low = (question_text or "").lower()
    best, best_rank = None, (0, 0)
    for topic, answer in ANSWER_BANK[persona]:
        rank = _score(topic, low)
        if rank > best_rank:
            best, best_rank = answer, rank
    if best is None or best_rank[1] < _MATCH_THRESHOLD:
        return FALLBACKS[persona], False
    return best, True


#: What Siddharth -- or any founder -- says when a question revisits ground he
#: has already covered. Deliberately topic-neutral and carrying no new fact:
#: the point of a deflection is that it adds nothing, so a band earned on one
#: is a band the engine assigned to "I already told you", not to the founder.
_DEFLECTIONS = (
    "I think I covered that earlier.",
    "That's related to what I mentioned before -- I don't have anything to add "
    "beyond it.",
    "Same answer as before, really.",
    "I don't have another specific number for that.",
)


class AnswerLedger:
    """Serves each prepared answer AT MOST ONCE for the length of a run.

    The bank is keyed by topic, not by question, and a stage asks several
    questions per topic. Without this, the highest-scoring answer is served
    again every time its topic comes round: in run #24 one answer covered five
    questions, among them "what does it cost to acquire one paying customer",
    which it does not address. The engine then scored those repeats as evidence
    and built two of its three root causes on them.

    That is fine for what this harness was first built for -- proving the
    engine separates a capable founder from an incapable one, where only the
    aggregate matters. It is not fine for judging whether a diagnosis follows
    from its evidence, because the evidence is then something the persona never
    said. So: once an answer is spent, the next question on that topic gets a
    deflection, which is what a real founder gives when asked the same thing
    twice, and which carries no new claim for the engine to score.

    One ledger spans all three phases, because a founder does not get his
    answers back between them.
    """

    def __init__(self, persona: str):
        self.persona = persona
        self._spent: set[int] = set()
        self.matched = 0
        self.deflected = 0
        self.unknown = 0

    def answer(self, question_text: str) -> tuple[str, bool]:
        """(answer, matched) -- the same contract match_answer has, so the
        caller does not care which of the two it is talking to."""
        low = (question_text or "").lower()
        best_i, best_rank, spent_hit = None, (0, 0), False
        for i, (topic, _) in enumerate(ANSWER_BANK[self.persona]):
            rank = _score(topic, low)
            if rank[1] < _MATCH_THRESHOLD or rank <= best_rank:
                continue
            if i in self._spent:
                # Records that the topic WAS reached, so a second question on
                # it deflects rather than falling back -- "I covered that" and
                # "I have never tracked that" are different founder states and
                # must not be collapsed.
                spent_hit = True
                continue
            best_i, best_rank = i, rank
        if best_i is not None:
            self._spent.add(best_i)
            self.matched += 1
            return ANSWER_BANK[self.persona][best_i][1], True
        if spent_hit:
            self.deflected += 1
            return _DEFLECTIONS[self.deflected % len(_DEFLECTIONS)], False
        self.unknown += 1
        return FALLBACKS[self.persona], False

    def summary(self) -> str:
        return (f"  answers served          {self.matched} unique, "
                f"{self.deflected} deflected (topic already spent), "
                f"{self.unknown} not known to this founder\n"
                f"    reuses                  0  (consume-once: an answer is "
                f"never served twice)")


#: The three states a question-keyed run can be in, kept apart on purpose.
#: Collapsing them is how run #25 read as a Critical Gap founder: a deflection,
#: an honest "we don't track that" and a question that does not apply to the
#: business all reached the classifier as the same evasive non-answer.
ANSWERED = "ANSWERED"                              # the founder answered it
GENUINELY_UNKNOWN = "GENUINELY_UNKNOWN"            # he does not know
GENUINELY_NON_APPLICABLE = "GENUINELY_NON_APPLICABLE"  # it does not apply here
HARNESS_MISS = "HARNESS_MISS"                      # WE have no answer: a bug


#: The largest share of served answers that may be harness filler before a run
#: stops counting as evidence.
#:
#: NOT a measured constant -- a judgement, set here so it is arguable in one
#: place instead of implicit everywhere. The reasoning: FALLBACKS[persona] is a
#: string THIS SCRIPT invented, and AnswerLedger.summary already warns that the
#: engine scores it like any other answer. On a category holding a single
#: question one filler answer is enough to manufacture a top finding -- RC-1088
#: was rank 1 on exactly that. At one in five, a reader cannot tell a real
#: pattern from an artefact of how much we happened not to know.
#:
#: Deflections are NOT filler. "I covered that" is a real founder state the
#: ledger produces deliberately, and it carries no new claim for the engine to
#: score. Only `unknown` -- the persona has no answer at all -- counts here.
MAX_FILLER_SHARE = 0.20


def evidence_degraded_reason(*, calls_observable: bool, made: int,
                             failed: int) -> str | None:
    """Why this run cannot be read as evidence about the ADAPTIVE engine, or None.

    D1. This used to answer None for the single most important case. `degraded`
    was set only in the `elif failed:` branch, which is reachable only when
    `made > 0`, so a run where NOTHING reached a model -- a dead key, an
    exhausted account, or scoring simply off -- printed a warning and was then
    stamped `valid_for_diagnostic_evidence: true`. A real batch of five
    adversarial runs came back 36 calls, $0.0000, 30 advisor failures and was
    briefly read as engine behaviour. Zero calls is not a quiet run: with
    ADAPTIVE_QUESTIONS the advisor IS the classifier, so zero calls means every
    answer is unscored and every band is the neutral AMBER fallback.

    `calls_observable` false means llm_call_log could not be read. That is not
    a pass either: validity is a positive claim, and a run we could not watch
    does not support it.
    """
    if not calls_observable:
        return ("llm_call_log could not be read, so the number of provider "
                "calls this run made is unknown. Validity is a positive claim "
                "about the evidence and nothing here supports it.")
    if made == 0:
        return ("ZERO provider calls were made. With ADAPTIVE_QUESTIONS the "
                "submit-time advisor IS the classifier, so zero calls means no "
                "answer carried a score label and every band is the neutral "
                "AMBER fallback. This run measures the unscored path, NOT the "
                "adaptive engine.")
    if failed:
        return (f"{failed} of {made} provider calls FAILED. Every failed "
                f"classification takes the neutral AMBER fallback and every "
                f"failed advisor call takes the deterministic question pick, so "
                f"this run measures the fallback path, NOT the adaptive engine.")
    return None


def coverage_gap_reason(*, harness_misses: int | None, filler: int | None,
                        served: int | None,
                        max_filler_share: float = MAX_FILLER_SHARE) -> str | None:
    """Why the ANSWERS behind this run are not the founder's, or None.

    D2. Only the question-keyed path (`--answer-map`) ever reported this, via
    HARNESS_MISS. Persona mode -- the default, and the one every persona run
    uses -- had no gap at all: a question the persona has no answer for is
    filled with FALLBACKS[persona] and counted only as `_fell_back`, which
    nothing downstream read. A desi_bar run served 11 of 46 answers (24%) from
    that one invented string and reported clean.

    `served is None` means neither ledger was kept (--repeat-answers), so
    coverage was not measured. Same rule as D1: not measured is not a pass.
    """
    if harness_misses:
        return (f"{harness_misses} questions had no prepared answer. The "
                f"harness submitted a literal '[HARNESS_MISS: ...]' string for "
                f"each, which the engine then scored and used as evidence. "
                f"Build a full-coverage map with "
                f"scripts/qa/build_persona_answer_map.py.")
    if served is None:
        return ("answer coverage was not measured for this run (--repeat-answers "
                "keeps no ledger), so the share of harness filler in the "
                "evidence is unknown.")
    if served and filler:
        share = filler / served
        if share > max_filler_share:
            return (f"{filler} of {served} served answers ({share:.0%}) were "
                    f"generic harness filler, above the {max_filler_share:.0%} "
                    f"ceiling. The engine scores that string like any other "
                    f"answer, so findings built on it belong to this script, "
                    f"not to the founder.")
    return None


class QuestionKeyedLedger:
    """Answers looked up by question id. No topic matching anywhere.

    The topic-keyed bank cannot support a question-by-question audit: a stage
    asks several questions per topic, so either one answer is served repeatedly
    (run #24: one answer covered five questions, two root causes rested on it)
    or the repeats become deflections that the classifier scores as evasion
    (run #25: 17 of 30 answers non-substantive, five pillars Critical Gap).

    Here every served question has its own answer, written against that
    question. A question with no entry is a HARNESS_MISS -- our bug, reported
    and counted, never quietly filled from somewhere else.

    The map is {phase: {question_id: {"a": text, "status": ...}}}.
    """

    def __init__(self, path: str):
        with open(path) as fh:
            self.map = json.load(fh)
        self.served: dict[str, list] = {}
        self.misses: list[tuple[str, int, str]] = []
        self.counts = {ANSWERED: 0, GENUINELY_UNKNOWN: 0,
                       GENUINELY_NON_APPLICABLE: 0, HARNESS_MISS: 0}
        self.reuses = 0
        self._seen: set[tuple[str, str]] = set()

    def answer(self, phase: str, qid, question_text: str) -> tuple[str, bool]:
        key = str(qid)
        entry = (self.map.get(phase) or {}).get(key)
        if entry is None or not entry.get("a"):
            self.counts[HARNESS_MISS] += 1
            self.misses.append((phase, qid, question_text))
            # Deliberately NOT a persona fallback. A miss must look like a miss
            # in the transcript, not like something the founder said.
            return "[HARNESS_MISS: no answer prepared for this question]", False
        if (phase, key) in self._seen:
            self.reuses += 1
        self._seen.add((phase, key))
        status = entry.get("status", ANSWERED)
        self.counts[status] = self.counts.get(status, 0) + 1
        self.served.setdefault(phase, []).append(
            {"question_id": qid, "question": question_text,
             "answer": entry["a"], "status": status})
        return entry["a"], status == ANSWERED

    def clean(self) -> bool:
        return self.counts[HARNESS_MISS] == 0 and self.reuses == 0

    def summary(self) -> str:
        c = self.counts
        total = sum(c.values())
        return (
            f"  answer map              {total} questions served\n"
            f"    answered                {c[ANSWERED]}\n"
            f"    genuinely unknown       {c[GENUINELY_UNKNOWN]}   "
            f"(Siddharth does not know -- not a harness failure)\n"
            f"    genuinely N/A           {c[GENUINELY_NON_APPLICABLE]}   "
            f"(does not apply to this business -- not a harness failure)\n"
            f"    HARNESS MISS            {c[HARNESS_MISS]}   "
            f"<- must be 0 for a clean run\n"
            f"    answer reuse            {self.reuses}   <- must be 0")


def _tally(pairs) -> dict:
    out: dict = {}
    for _, label in pairs:
        out[label or "unscored"] = out.get(label or "unscored", 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def band_summary(rows, fallback_qids) -> list[str]:
    """The RESULT block's band lines, as strings.

    A function rather than inline printing because inline printing is how a
    NameError shipped: the split was added, `bands` was renamed to
    `answered`, the flat-amber check three lines below still said `bands`,
    and the whole RESULT block died after the bands and before the pillars,
    model calls and cost. Every test covered the matching and none covered
    the reporting, so nothing caught it until a paid run printed a
    traceback where its summary should have been.

    `rows` is (question_id, score_label); `fallback_qids` are the questions
    that got the generic answer.
    """
    answered = _tally(rows)
    lines = [f"  answer bands            {answered or 'none'}"]

    generic = _tally([r for r in rows if r[0] in fallback_qids])
    if generic:
        on_topic = _tally([r for r in rows if r[0] not in fallback_qids])
        lines.append(f"    of which on topic     {on_topic or 'none'}")
        lines.append(f"    of which generic      {generic}"
                     "   <- the script had no answer for these; read them"
                     " as harness noise, not as the founder")

    # SHARES, because the two personas do not answer the same number of
    # questions and raw counts across runs do not compare. The engine stops
    # when it has enough, so a strong run can finish at 12 answers where a
    # weak one needs 14: "10 green" and "8 green" say nothing until they are
    # 83% and 57%. See stop_reason() for why a run ended where it did.
    total = sum(answered.values())
    if total:
        shares = ", ".join(f"{k} {v * 100 // total}%" for k, v in answered.items())
        lines.append(f"    share of {total:<14} {shares}")

    # About SCORING being off, not about this script's answers: one band for
    # everything is the signature of answers reaching the pipeline unscored.
    if len(answered) == 1 and "amber" in answered:
        lines.append("    ^ every answer identical -- this is the unscored "
                     "fallback, not a real classification")
    return lines


#: routing_state thresholds, from the column comment on sessions.routing_state.
_ROUTING_MEANING = {
    "continue": "<60 = keep asking",
    "validate": "60-80 = confirm the hypothesis with the founder",
    "generate_report": ">80 = confident enough to report, stop asking",
    "distress_support": "distress path, questioning suspended",
}


def stop_reason(row) -> str:
    """One line saying why the diagnosis stopped where it did.

    Two personas answering different numbers of questions looks like a bug in
    this script and is not one: the engine ends the session as soon as
    `overall_confidence_score` clears the `routing_state` threshold, so a
    persona that answers clearly gets asked less. A strong run ended at 12
    answers on confidence 82 while the weak run took all 14. Without this
    line the next reader compares 12 against 14 and concludes the harness
    dropped two questions.

    `row` is (questions_answered_count, routing_state, overall_confidence_score,
    question_budget); None when no session was found. The budget may be None.
    """
    if row is None:
        return "  session                 not found"
    answered, state, confidence = row[0], row[1], row[2]
    budget = row[3] if len(row) > 3 else None
    meaning = _ROUTING_MEANING.get(state or "", "")
    conf = "?" if confidence is None else f"{float(confidence):.0f}"
    tail = f"   ({meaning})" if meaning else ""

    # The stored score is not always the score that set the state. A live run
    # printed "routing_state 'generate_report' at confidence 80 (>80 = ...)",
    # which reads as 80 being greater than 80. What happened: questioning
    # stopped at 82, and the report pipeline then recomputed confidence with
    # answer_consistency available (a factor there is no data for until the
    # answers are in) and wrote 80 back. The state is the one that ended the
    # session; the number is the one left behind afterwards.
    if state and confidence is not None and not _satisfies(state, float(confidence)):
        tail += ("\n                          ^ the state was set on a score "
                 "measured DURING questioning; this number is the report "
                 "pipeline's later recompute, so the two need not agree")

    # THE BUDGET CAN BE WHAT STOPPED IT, and then the routing_state is just
    # whatever the session happened to be in when the questions ran out. The
    # Early Traction run ended at its 30-question budget on confidence 78 in
    # state 'validate'; the report pipeline then recomputed to 83 and flipped
    # the state, so this line read "routing_state 'generate_report' at
    # confidence 83" and credited the stop to a threshold that questioning
    # never actually crossed.
    if budget is not None and answered >= budget:
        return (f"  stopped after           {answered} answers -- the stage's "
                f"{budget}-question budget ran out, not confidence\n"
                f"                          (session now reads routing_state "
                f"{state!r} at confidence {conf}; more questions were "
                "available and were not asked)")

    return (f"  stopped after           {answered} answers -- "
            f"routing_state {state!r} at confidence {conf}{tail}")


#: The band each routing_state is reached in, per the sessions.routing_state
#: column comment. Used only to notice when a stored score falls outside it.
_ROUTING_BANDS = {
    "continue": (0.0, 60.0),
    "validate": (60.0, 80.0),
    "generate_report": (80.0, 100.0),
}


def _satisfies(state: str, confidence: float) -> bool:
    """Is `confidence` inside the band that `state` is reached in?

    Unknown states (distress_support, anything added later) are never reported
    as inconsistent -- they are not reached by a threshold at all.
    """
    band = _ROUTING_BANDS.get(state)
    if band is None:
        return True
    low, high = band
    return low < confidence <= high if low else confidence <= high


def _answer_for(n: int, persona: str = "weak", question_text: str | None = None) -> str:
    """The answer to send. With question text, the topic match; without it,
    the old index cycle, which is what callers that have no question have."""
    if question_text:
        return match_answer(question_text, persona)[0]
    answers = PERSONAS[persona]
    return answers[n % len(answers)]


# ---------------------------------------------------------------------------


def _config_report(settings) -> tuple[list[str], bool]:
    lines = [
        f"  LLM_PROVIDER          {settings.LLM_PROVIDER or '(empty)'}",
        f"  ANTHROPIC_API_KEY     {'present' if settings.ANTHROPIC_API_KEY else 'MISSING'}",
        f"  OPENAI_API_KEY        {'present' if settings.OPENAI_API_KEY else 'missing'}",
        f"  ADAPTIVE_QUESTIONS    {settings.ADAPTIVE_QUESTIONS}",
        f"  ANSWER_CLASSIFIER     {settings.ANSWER_CLASSIFIER}",
        f"  scoring configured    {settings.diagnosis_scoring_configured}",
    ]
    return lines, bool(settings.diagnosis_scoring_configured)


def _llm_calls(db, sa) -> tuple[int, float, int]:
    """(calls, cost so far, failed calls).

    The failure count is the third value because a run where every provider call
    returned an error still LOOKS healthy: the advisor falls back to the
    deterministic pick, every answer takes the neutral AMBER fallback score, a
    report is still produced, and the only outward sign is a cost of $0.0000.
    Five such runs were mistaken for results before this was counted.
    """
    try:
        row = db.execute(sa.text(
            "select count(*), coalesce(sum(estimated_cost_usd), 0), "
            "count(*) filter (where status <> 'ok') from llm_call_log"
        )).one()
        return int(row[0]), float(row[1]), int(row[2])
    except Exception:                                            # noqa: BLE001
        db.rollback()
        return -1, 0.0, -1


#: Rows a test run of either mode can add, in the order they must be deleted
#: (children before parents). `founders` and `founder_consents` are NOT here
#: -- --stage mode deletes them separately for its own synthetic founders,
#: --founder-email mode never touches them at all.
_JOURNEY_TABLES = (
    ("answers", "founder_id"), ("founder_dna_answers", "founder_id"),
    ("current_problem_answers", "founder_id"), ("founder_reports", "founder_id"),
    ("detected_root_causes", "session_id"), ("sessions", "founder_id"),
)


#: Journey state that lives on the `founders` row itself rather than in a
#: child table. Deleting the answers without clearing these leaves a founder
#: marked complete with nothing behind it -- and the next run's
#: founder-dna/start and current-problem/start then serve no question at all,
#: because `current_state()` short-circuits on the timestamp. That is how a
#: journey check came back "0 question(s) answered" for two whole phases.
_JOURNEY_STAMPS = ("founder_dna_completed_at", "current_problem_completed_at")


def _clear_journey_stamps(db, sa, founder_ids: list) -> None:
    """Reset the phase-completion timestamps on `founders`.

    This is the one place cleanup touches the founders row, and it is
    deliberate: these two columns are journey state, not identity. Nothing
    about who the founder is, their consent, plan or profile is altered --
    only the record of having finished a phase, which is exactly what
    cleanup is removing everywhere else.
    """
    try:
        db.execute(sa.text(
            "update founders set "
            + ", ".join(f"{c} = null" for c in _JOURNEY_STAMPS)
            + " where founder_id = any(:f)"), {"f": founder_ids})
    except Exception:                                            # noqa: BLE001
        db.rollback()  # column may not exist on this schema; keep going


def _delete_journey_rows(db, sa, founder_ids: list) -> None:
    _clear_journey_stamps(db, sa, founder_ids)
    for table, col in _JOURNEY_TABLES:
        try:
            if col == "session_id":
                db.execute(sa.text(
                    f"delete from {table} where session_id in "
                    "(select session_id from sessions where founder_id = any(:f))"),
                    {"f": founder_ids})
            else:
                db.execute(sa.text(f"delete from {table} where {col} = any(:f)"),
                           {"f": founder_ids})
        except Exception:                                        # noqa: BLE001
            db.rollback()  # table may not exist on this schema; keep going


def cleanup(db, sa) -> int:
    """Removes every synthetic --stage founder (@ally-e2e.local) entirely."""
    founders = [r[0] for r in db.execute(sa.text(
        "select founder_id from founders where email like :p"),
        {"p": f"%@{TEST_DOMAIN}"}).all()]
    if not founders:
        print(f"  nothing to clean up at @{TEST_DOMAIN}")
        return 0
    _delete_journey_rows(db, sa, founders)
    try:
        db.execute(sa.text("delete from founder_consents where founder_id = any(:f)"),
                   {"f": founders})
    except Exception:                                            # noqa: BLE001
        db.rollback()
    db.execute(sa.text("delete from founders where founder_id = any(:f)"), {"f": founders})
    db.commit()
    print(f"  removed {len(founders)} test founder(s) and their data")
    return len(founders)


def cleanup_founder_journey(db, sa, *, fid: int | None = None, email: str | None = None,
                           label: str | None = None) -> int:
    """Removes journey rows for one EXISTING, real founder.

    Never removes the founder or their consent -- that account is real and
    outlives this script. It does write two columns ON the founders row:
    founder_dna_completed_at and current_problem_completed_at are reset to
    null, because they record having finished a phase whose answers this
    function is deleting. Leaving them set is what made a cleaned founder
    unable to re-run Founder DNA or Current Problem at all.
    """
    if fid is None:
        fid = db.execute(sa.text("select founder_id from founders where email = :e"),
                         {"e": email}).scalar()
        if fid is None:
            print(f"  no founder found with email {email}")
            return 0
    label = label or f"founder_id={fid}"
    _delete_journey_rows(db, sa, [fid])
    db.commit()
    print(f"  removed journey data for {label} "
          "(the founder and their consent were left alone)")
    return 1


#: Onboarding profiles, per persona. The default is a generic SaaS founder;
#: `ally_mvp` describes Ally itself.
#:
#: This is not decoration. The founder row is CONTEXT the classifier reads
#: alongside each answer, so a profile that says "Acme Compliance, compliance
#: SaaS" under answers about building a diagnosis engine is not merely an
#: incoherent transcript -- it is a contradiction the scoring is then asked to
#: explain. The persona and the profile have to be the same founder.
_ONBOARDING = {
    None: {
        "business_name": "Acme Compliance",
        "problem_statement":
            "Customers churn after the second month and I cannot tell why.",
        "building_summary": "Compliance SaaS for Indian SMBs.",
        "industry": "SaaS",
        "current_challenges": ["Sales", "Cash flow"],
        "goal_90_day": "Ten real customer interviews.",
        "vision_1_year": "Series A raised.",
    },
    "ally_mvp": {
        "business_name": "Ally",
        "problem_statement":
            "Founders at this stage cannot get an honest read on their own "
            "business, and the advice they can afford is generic.",
        "building_summary":
            "Ally -- an AI business diagnosis for early-stage founders: what "
            "is actually wrong, the root causes under it, and what to do next.",
        "industry": "SaaS",
        "current_challenges": ["Sales", "Cash flow"],
        "goal_90_day":
            "One founder outside our own network paying for a diagnosis.",
        "vision_1_year":
            "Founders we have never met completing a diagnosis and acting on "
            "it, without us in the room.",
        "product_description":
            "A guided journey -- Founder DNA, the current problem, then a "
            "staged diagnosis -- that produces a report scoring six pillars "
            "of a founder's business and names the root causes beneath them.",
    },
}

#: The weak counterpart runs the SAME business, so it gets the same profile.
#: Anything else would make the comparison a test of two companies.
_ONBOARDING["ally_weak"] = _ONBOARDING["ally_mvp"]


def _seed_founder(db, sa, stage_order: int, persona: str | None = None) -> tuple[int, str]:
    """A brand-new synthetic founder with a random user_id.

    Only works where founders.user_id carries no FK to auth.users -- see the
    module docstring. Raises IntegrityError with a clear message, rather than
    a bare traceback, when that FK exists and rejects the fabricated id.

    FILLS THE PATH 2 FIELDS TOO, whatever stage is asked for. It did not, and
    the effect was that `--stage 4` could not run a journey at all:

        FAIL /api/v1/founder-dna/start -> 409 ProfileIncompleteError
        Still needed: Monthly Revenue, What It Is, Business Reality

    `app/services/profile_progress.py` requires four extra fields of any
    founder past Ideation (PATH_2_REQUIRED), and this insert filled only the
    always-required set plus Path 1's `goal_90_day`. So the founder it built
    was Stage 0-shaped no matter what `--stage` said, and every gate past
    Stage 0 refused it -- which is the gate working correctly on a founder the
    test harness had built wrong.

    `current_revenue` follows the stage, because "under_1L" on a Growth
    founder is not a weak answer, it is a contradiction, and the diagnosis
    would then be asked to explain a founder who cannot exist. The bands and
    the reality signals are imported from `fill_missing_onboarding` rather
    than copied, so the founder this builds and the founder that script
    repairs are the same founder.
    """
    from scripts.fill_missing_onboarding import (
        BUSINESS_REALITY,
        FIELDS,
        REVENUE_BY_STAGE_ORDER,
    )

    email = f"e2e+{int(time.time())}@{TEST_DOMAIN}"
    revenue = REVENUE_BY_STAGE_ORDER.get(stage_order, FIELDS["current_revenue"])
    profile = {**_ONBOARDING[None], **_ONBOARDING.get(persona, {})}
    try:
        fid = db.execute(sa.text("""
            insert into founders (user_id, email, full_name, stage_id, profile_completed,
                                  experience_level, problem_statement, building_summary,
                                  business_name, industry, customer_segment,
                                  current_challenges, goal_90_day, vision_1_year,
                                  founder_reality_signals, invisible_gaps,
                                  current_revenue, product_description,
                                  business_reality_signals)
            values (gen_random_uuid(), :e, 'E2E Test Founder', :s, true,
                    'one_company', :problem, :building,
                    :bizname, :industry,
                    '["Business"]'::jsonb, cast(:challenges as jsonb),
                    :goal90, :vision1,
                    '{"clear_next_step": true}'::jsonb, '["pricing"]'::jsonb,
                    :rev, :prod, cast(:breality as jsonb))
            returning founder_id"""),
            {"e": email, "s": stage_order, "rev": revenue,
             "problem": profile["problem_statement"],
             "building": profile["building_summary"],
             "bizname": profile["business_name"],
             "industry": profile["industry"],
             "challenges": json.dumps(profile["current_challenges"]),
             "goal90": profile["goal_90_day"],
             "vision1": profile["vision_1_year"],
             "prod": profile.get("product_description",
                                 FIELDS["product_description"]),
             "breality": json.dumps(BUSINESS_REALITY)}).scalar_one()
    except Exception as exc:                                      # noqa: BLE001
        db.rollback()
        if "user_id" in str(exc) and ("fkey" in str(exc).lower() or "foreign key" in str(exc).lower()):
            raise SystemExit(
                "\n  This database enforces a real foreign key from "
                "founders.user_id to auth.users -- a random UUID cannot "
                "satisfy it, by design (see the module docstring).\n"
                "  Use --founder-email <email> instead, naming an account "
                "that already exists (ideally your own, signed up through "
                "the app normally)."
            ) from exc
        raise
    db.execute(sa.text("""
        insert into founder_consents (consent_id, founder_id, terms_version,
                                      privacy_version, agree_terms, agree_diagnosis)
        values (gen_random_uuid(), :f, 'v1', 'v1', true, true)"""), {"f": fid})
    db.commit()
    return fid, email


def _resolve_existing_founder(db, sa, *, email: str | None = None,
                              founder_id: int | None = None) -> tuple[int, str]:
    """An EXISTING founder's id, by email or by id -- exactly one of the two.

    Never inserts into founders or founder_consents -- see the module
    docstring for why. Returns (fid, label): label is the email when looked up
    by email, or `founder_id=N` when looked up by id, so id-mode never has to
    read or print an email it was not given.
    """
    assert (email is None) != (founder_id is None), "pass exactly one of email/founder_id"

    if email is not None:
        row = db.execute(sa.text(
            "select founder_id, stage_id, profile_completed from founders "
            "where email = :e"), {"e": email}).first()
        not_found = (
            f"\n  No founder exists with email {email!r} on this database.\n"
            "  --founder-email requires an account that already exists -- "
            "sign up through the app first, or use --stage on a database "
            "with no auth.users FK instead."
        )
        label = email
    else:
        row = db.execute(sa.text(
            "select founder_id, stage_id, profile_completed from founders "
            "where founder_id = :f"), {"f": founder_id}).first()
        not_found = (
            f"\n  No founder exists with founder_id={founder_id} on this database.\n"
            "  --founder-id requires an account that already exists -- "
            "sign up through the app first, or use --stage on a database "
            "with no auth.users FK instead."
        )
        label = f"founder_id={founder_id}"

    if row is None:
        raise SystemExit(not_found)
    fid, stage_id, profile_completed = row
    if not profile_completed:
        print(f"  warning: {label} has profile_completed=false; onboarding "
              "gates may reject the journey below.")
    has_consent = db.execute(sa.text(
        "select 1 from founder_consents where founder_id = :f limit 1"),
        {"f": fid}).first()
    if has_consent is None:
        raise SystemExit(
            f"\n  {label} has no consent record, and this script will not "
            "create one on a real account -- consent must come from the "
            "founder themselves, through the app.\n"
            "  Complete consent in the app for this account, then re-run."
        )
    return fid, label


def _walk(client, start_path, answer_path, id_field, label, out, persona="weak",
          ledger=None, qk_ledger=None, qk_phase=None):
    """Drive one question/answer phase to completion, recording every question."""
    r = client.post(start_path)
    if r.status_code not in (200, 201):
        print(f"  FAIL {start_path} -> {r.status_code} {r.text[:200]}")
        return False
    q = (r.json() or {}).get("question")
    # Only the questions this walk appends are its own: the counts below are
    # taken from this slice, never from `len(out)`.
    start_len = len(out)
    if q is None:
        # A null question means "this phase is already complete for this
        # founder" -- and that is a FAILURE here, not a pass. This check
        # exists to prove the phases run; a phase that served nothing proved
        # nothing. It used to slip through: `while q:` simply never entered,
        # and the walk printed "0 question(s) answered" and returned True
        # under a confident-looking summary.
        #
        # The usual cause is exactly the one this script can create: cleanup
        # removes the answer rows but the completion timestamp on `founders`
        # (founder_dna_completed_at / current_problem_completed_at) stays set,
        # leaving the founder marked complete with no answers behind it.
        print(f"  FAIL {label}: no question served -- this phase reports "
              "itself already complete for this founder.\n"
              "       Run --cleanup-founder-id <id> (which now clears the "
              "completion timestamps too) and try again.")
        return False
    reprompts = 0
    while q:
        out.append(q)
        if qk_ledger is not None:
            answer, matched = qk_ledger.answer(
                qk_phase, q.get(id_field), q.get("question_text", ""))
        elif ledger is not None:
            answer, matched = ledger.answer(q.get("question_text", ""))
        else:
            answer, matched = match_answer(q.get("question_text", ""), persona)
        # The transcript has to carry what was actually SAID, not just what
        # was asked. Without it a reviewer cannot tell a real answer from a
        # deflection, which is exactly the check run #24 needed and failed.
        q["_answer_text"] = answer
        # Recorded on the question itself so the summary can separate bands
        # earned by the persona from bands earned by the generic answer.
        q["_fell_back"] = not matched
        body = {id_field: q[id_field], "answer_text": answer}
        a = client.post(answer_path, json=body)
        if a.status_code not in (200, 201):
            print(f"  FAIL {answer_path} -> {a.status_code} {a.text[:200]}")
            return False
        data = a.json() or {}
        if data.get("accepted") is False:
            # Only the LLM path rejects an answer as off-question, so seeing one
            # is itself evidence the model ran.
            reprompts += 1
            out.pop()
            if reprompts > 3:
                print("  FAIL too many reprompts in a row")
                return False
            continue
        reprompts = 0
        if data.get("is_complete") or (data.get("progress") or {}).get("is_complete"):
            q = data.get("next_question")
            if not q:
                break
        q = data.get("next_question")
    answered = out[start_len:]
    if not answered:
        print(f"  FAIL {label}: 0 questions answered")
        return False
    # How many questions got an answer actually about them. A phase that
    # mostly fell back is measuring the fallback line, not the persona, and
    # its bands should be read that way.
    #
    # Counted from the surviving questions, not from a running total. A
    # running counter incremented at answer time double-counts a question
    # whose answer was rejected and re-asked: the reprompt branch pops the
    # question off `out` but could not un-increment the counter, so
    # `len(out) - matched_count` went NEGATIVE ("-2 fell back to the generic
    # answer") on any run with reprompts.
    matched_count = sum(1 for q in answered if not q.get("_fell_back"))
    fell_back = len(answered) - matched_count
    detail = f", {fell_back} fell back to the generic answer" if fell_back else ""
    print(f"  {label}: {len(answered)} question(s) answered "
          f"({matched_count} matched on topic{detail})")
    return True


def run(args) -> int:
    os.environ["DATABASE_URL"] = args.database_url
    os.environ.setdefault("SECRET_KEY", "e2e-journey-check-not-a-real-secret")

    import sqlalchemy as sa
    from fastapi.testclient import TestClient

    from app.api.deps import get_founder_record
    from app.core.config import settings
    from app.db.session import SessionLocal, get_db
    from app.main import app
    from app.models import Founder

    # Cleanup first, and before the scoring check. Tidying up after a run must
    # not require a working model config -- that would strand test rows on any
    # machine without a key, which is exactly where they get left behind.
    if args.cleanup:
        print("CLEANUP")
        with SessionLocal() as db:
            cleanup(db, sa)
        return 0
    if args.cleanup_founder_email or args.cleanup_founder_id:
        print("CLEANUP (single founder)")
        with SessionLocal() as db:
            if args.cleanup_founder_email:
                cleanup_founder_journey(db, sa, email=args.cleanup_founder_email)
            else:
                cleanup_founder_journey(db, sa, fid=args.cleanup_founder_id)
        return 0

    print("=" * 74)
    print("CONFIGURATION")
    print("=" * 74)
    lines, scoring_on = _config_report(settings)
    # Which answers produced this. A band means nothing without it.
    lines.append(f"  answer persona        {args.persona}")
    print("\n".join(lines))
    if not scoring_on and not args.allow_unscored:
        print("\n  ABORT: scoring is not configured, so every answer would be "
              "recorded as a flat amber and no report would be produced.\n"
              "  Set ADAPTIVE_QUESTIONS=true (with a working key), or pass "
              "--allow-unscored to run anyway.")
        return 2

    using_existing = bool(args.founder_email or args.founder_id)
    with SessionLocal() as db:
        calls_before, cost_before, fails_before = _llm_calls(db, sa)
        if using_existing:
            fid, label = _resolve_existing_founder(
                db, sa, email=args.founder_email, founder_id=args.founder_id)
            print(f"\n  existing founder {fid} ({label}) (unchanged: not created "
                  "by this script)")
        else:
            fid, label = _seed_founder(db, sa, args.stage, args.persona)
            print(f"\n  test founder {fid} <{label}> at stage_order {args.stage}")

    from fastapi import Depends
    from sqlalchemy.orm import Session as OrmSession

    def _founder(db: OrmSession = Depends(get_db)):
        return db.get(Founder, fid)

    app.dependency_overrides[get_founder_record] = _founder

    # The per-founder rate limits, switched off for this run only.
    #
    # `/diagnosis/answer` allows 20 answers in 60 seconds. A stage-4 journey
    # has a budget of 30 questions and stages 6 and 7 have 32, and this script
    # answers at machine speed -- so the run died at question 21 with a 429,
    # having proved nothing about the diagnosis engine and everything about
    # the rate limiter, which is not what it is for.
    #
    # A real founder types answers and will not come close; this is a
    # consequence of a test harness being faster than a person, not a defect
    # in the limit. The router exposes these as module-level dependency
    # objects specifically so they can be overridden by identity, which is
    # why this works -- see the comment above them in
    # app/api/v1/diagnosis/router.py.
    from app.api.v1.diagnosis.router import answer_rate_limit, start_rate_limit

    app.dependency_overrides[start_rate_limit] = lambda: None
    app.dependency_overrides[answer_rate_limit] = lambda: None

    client = TestClient(app)

    dna, problem, diagnosis = [], [], []
    print("\n" + "=" * 74)
    print("JOURNEY")
    print("=" * 74)
    # One ledger for the whole journey -- a founder does not get his answers
    # back between phases. --repeat-answers restores the old behaviour, which
    # is what the earlier discrimination baselines were measured with.
    qk = QuestionKeyedLedger(args.answer_map) if args.answer_map else None
    ledger = None if (args.repeat_answers or qk) else AnswerLedger(args.persona)
    ok = (
        _walk(client, "/api/v1/founder-dna/start", "/api/v1/founder-dna/answer",
              "founder_dna_question_id", "Founder DNA", dna, args.persona,
              ledger, qk, "dna")
        and _walk(client, "/api/v1/current-problem/start",
                  "/api/v1/current-problem/answer",
                  "current_problem_question_id", "Current Problem", problem,
                  args.persona, ledger, qk, "cp")
        and _walk(client, "/api/v1/diagnosis/start", "/api/v1/diagnosis/answer",
                  "question_id", "Diagnosis", diagnosis, args.persona, ledger,
                  qk, "diag")
    )
    if qk is not None and not qk.clean():
        print("\n" + "=" * 74)
        print("CONTAMINATED RUN -- the answer map did not cover this path")
        print("=" * 74)
        print(qk.summary())
        for phase, qid, text in qk.misses:
            print(f"  MISS  {phase}/{qid}: {text[:100]}")
        import json as _j
        _j.dump(qk.misses, open("/tmp/qk_misses.json", "w"), indent=1)
        print("\n  misses written to /tmp/qk_misses.json -- add answers and re-run.")
    if not ok:
        return 1

    # --- report -----------------------------------------------------------
    report = None
    with SessionLocal() as db:
        founder = db.get(Founder, fid)
        sid = db.execute(sa.text(
            "select session_id from sessions where founder_id=:f "
            "order by session_id desc limit 1"), {"f": fid}).scalar()
        try:
            from app.api.v1.reasoning.trigger import build_reasoning_service, run_sync
            run_sync(build_reasoning_service(db).analyze_session(founder, sid))
            db.commit()
        except Exception as exc:                                 # noqa: BLE001
            print(f"\n  reasoning pipeline raised: {type(exc).__name__}: {exc}")
            db.rollback()
        report = db.execute(sa.text(
            "select report_id, business_dna from founder_reports "
            "where founder_id=:f order by report_id desc limit 1"), {"f": fid}).first()
        calls_after, cost_after, fails_after = _llm_calls(db, sa)

    # --- what happened ----------------------------------------------------
    print("\n" + "=" * 74)
    print("QUESTIONS SERVED")
    print("=" * 74)
    print("\n-- Founder DNA --")
    for i, q in enumerate(dna, 1):
        close = "  [WOW CLOSE]" if q.get("is_closing") else ""
        print(f"  {i:2d}. ({q.get('dimension_code')}/{q.get('format')}){close}")
        print(f"      {q.get('question_text','')}")
    print("\n-- Current Problem --")
    for i, q in enumerate(problem, 1):
        print(f"  {i:2d}. {q.get('question_text','')}")
    print("\n-- Diagnosis --")
    for i, q in enumerate(diagnosis, 1):
        generic = "  <- generic answer" if q.get("_fell_back") else ""
        print(f"  {i:2d}. [{q.get('category')}] {q.get('question_text','')}{generic}")

    print("\n" + "=" * 74)
    print("RESULT")
    print("=" * 74)
    # Bands split by whether the answer was the persona's or the generic
    # fallback. This matters more than it looks: a fallback does not read as
    # neutral to the classifier, it reads as evasion, so it scores red
    # whichever persona sent it. On a category holding a single question that
    # is enough to manufacture a top finding -- RC-1088 was rank 1 on exactly
    # that. Reporting the split stops the next reader crediting the founder
    # with a gap that belongs to this script.
    fallback_qids = {q.get("question_id") for q in diagnosis if q.get("_fell_back")}
    with SessionLocal() as db:
        rows = db.execute(sa.text(
            "select question_id, score_label from answers where founder_id=:f"),
            {"f": fid}).all()

    print(f"  answer persona          {args.persona}")
    if qk is not None:
        print(qk.summary())
    elif ledger is not None:
        print(ledger.summary())
    for line in band_summary(rows, fallback_qids):
        print(line)
    with SessionLocal() as db:
        print(stop_reason(db.execute(sa.text(
            "select s.questions_answered_count, s.routing_state, "
            "       s.overall_confidence_score, st.question_budget "
            "  from sessions s "
            "  join founders f on f.founder_id = s.founder_id "
            "  left join founder_stages st on st.stage_id = f.stage_id "
            " where s.founder_id = :f "
            " order by s.session_id desc limit 1"), {"f": fid}).first()))

    if report:
        bd = report[1] or {}
        print(f"  report                  #{report[0]} generated")
        print(f"  overall band            {bd.get('band')}")
        print(f"  pillars assessed        {bd.get('pillars_assessed')}"
              f" of {bd.get('pillars_total')}"
              f"  ({bd.get('assessed_weight_pct')}% of the model)")
        for p in (bd.get("pillars") or []):
            cov = p.get("dimensions_in_scope") or []
            tot = p.get("dimensions_total") or 0
            qual = f"  ({', '.join(cov)} only)" if cov and tot and len(cov) < tot else ""
            print(f"    {p.get('pillar_name')}{qual}: {p.get('band') or 'not assessed'}")
    else:
        print("  report                  NONE GENERATED")

    calls_observable = calls_before >= 0
    made = (calls_after - calls_before) if calls_observable else 0
    failed = (fails_after - fails_before) if calls_observable else 0
    if calls_observable:
        print(f"  model calls this run    {made}"
              f"   (cost ${cost_after - cost_before:.4f}, {failed} failed)")
    else:
        print("  model calls this run    (llm_call_log unavailable)")
    degraded = evidence_degraded_reason(calls_observable=calls_observable,
                                        made=made, failed=failed)
    if degraded:
        print(f"    ^ {degraded}")

    # Filler is `unknown` only: a deflection is a real founder state the ledger
    # produces on purpose (see AnswerLedger), not something this script made up.
    if qk is not None:
        harness_misses = qk.counts[HARNESS_MISS]
        filler = served = None
    elif ledger is not None:
        harness_misses = 0
        filler = ledger.unknown
        served = ledger.matched + ledger.deflected + ledger.unknown
    else:
        harness_misses, filler, served = 0, None, None
    coverage_gap = coverage_gap_reason(harness_misses=harness_misses,
                                       filler=filler, served=served,
                                       max_filler_share=args.max_filler_share)
    if coverage_gap:
        print(f"\n  COVERAGE GAP            {coverage_gap}")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump({"generated_at": datetime.now(timezone.utc).isoformat(),
                       "stage_order": args.stage, "founder_id": fid,
                       # Stamped so a run that fell back to the deterministic
                       # path or answered from HARNESS_MISS can never be read
                       # later as evidence about the adaptive engine.
                       "valid_for_diagnostic_evidence": not (degraded or coverage_gap),
                       "degraded_reason": degraded,
                       "coverage_gap": coverage_gap,
                       # The inputs to the two verdicts above, so a reader can
                       # re-derive them instead of trusting the booleans.
                       "evidence_inputs": {
                           "calls_observable": calls_observable,
                           "model_calls": made, "failed_calls": failed,
                           "harness_misses": harness_misses,
                           "filler_answers": filler, "served_answers": served,
                           "max_filler_share": args.max_filler_share},
                       "founder_dna": dna, "current_problem": problem,
                       "diagnosis": diagnosis,
                       "report": (report[1] if report else None)}, fh, indent=1)
        print(f"\n  written to {args.json_out}")

    if args.founder_email:
        print(f"\n  clean up with: --database-url ... --cleanup-founder-email {label}")
    elif args.founder_id:
        print(f"\n  clean up with: --database-url ... --cleanup-founder-id {fid}")
    else:
        print(f"\n  clean up with: --database-url ... --cleanup")

    if args.strict_evidence and (degraded or coverage_gap):
        print("\n  STRICT EVIDENCE MODE: this run is NOT usable as evidence about "
              "the adaptive engine. Exiting non-zero so a batch stops here rather "
              "than writing another file that looks like a result.")
        return 3
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--database-url", required=True,
                   help="SQLAlchemy URL. Deliberately NOT read from DATABASE_URL -- "
                        "this script writes, so the target has to be named.")
    p.add_argument("--stage", type=int, default=1, choices=range(1, 9),
                   help="founder_stages.stage_order for a NEW synthetic founder "
                        "(default 1, Ideation). Ignored with --founder-email. "
                        "Only works on a database with no auth.users FK on "
                        "founders.user_id -- see the module docstring.")
    p.add_argument("--founder-email", metavar="EMAIL",
                   help="use an EXISTING founder by email instead of creating one "
                        "-- required against a real Supabase project. That "
                        "account must already exist, with profile and consent "
                        "completed through the app; this script never creates "
                        "either on your behalf.")
    p.add_argument("--founder-id", type=int, metavar="N",
                   help="same as --founder-email, but by founder_id -- avoids "
                        "naming an email on the command line at all")
    p.add_argument("--confirm-writes", action="store_true",
                   help="required: acknowledges that this writes a diagnosis "
                        "journey and a report into the named database")
    p.add_argument("--cleanup", action="store_true",
                   help=f"delete every @{TEST_DOMAIN} founder and their data, then exit")
    p.add_argument("--cleanup-founder-email", metavar="EMAIL",
                   help="delete the journey data (sessions/answers/report) for "
                        "one existing founder by email, then exit -- leaves the "
                        "founder and their consent untouched")
    p.add_argument("--cleanup-founder-id", type=int, metavar="N",
                   help="same as --cleanup-founder-email, but by founder_id")
    p.add_argument("--allow-unscored", action="store_true",
                   help="run even with scoring off (useful only to test the fallback)")
    p.add_argument("--persona", choices=sorted(PERSONAS), default="weak",
                   help="which answer set to reply with. 'weak' (default) is a "
                        "founder who has not done the work; 'strong' is the same "
                        "six dimensions done properly, still at the same stage. "
                        "Run both against the same founder and compare the bands: "
                        "if they come out the same, the scorer is not reading the "
                        "answers, whatever the band says. 'traction' is strong's "
                        "rigour two stages on -- customers, staff and money -- "
                        "and is the one to use above Prototype/MVP, where strong "
                        "has nothing on-topic to say about delegation, cash or "
                        "what is written down. 'weak_traction' is traction's "
                        "counterpart -- the same thirty-eight subjects answered "
                        "by someone running a real business on memory and "
                        "reaction. traction alone proved the engine COVERS "
                        "stage 4; the pair is what proves it DISCRIMINATES "
                        "there, the way weak/strong does at Ideation.")
    p.add_argument("--strict-evidence", action="store_true",
                   help="Exit 3 if the run cannot support a claim about the "
                        "adaptive engine: any provider call failed (so answers "
                        "took the neutral AMBER fallback and questions the "
                        "deterministic pick), or any served question had no "
                        "prepared answer (so a literal HARNESS_MISS string was "
                        "submitted and scored). Both conditions otherwise "
                        "produce a run that looks entirely normal -- a report is "
                        "generated either way -- which is how five fallback runs "
                        "were once mistaken for adversarial results. Use this "
                        "for anything whose output will be quoted.")
    p.add_argument("--answer-map", metavar="FILE",
                   help="JSON {phase: {question_id: {a, status}}}. Answers are "
                        "looked up by question id and nothing is matched by "
                        "topic, which is what a question-by-question audit "
                        "needs. A question with no entry is reported as a "
                        "HARNESS MISS rather than filled from elsewhere.")
    p.add_argument("--repeat-answers", action="store_true",
                   help="serve the best-matching answer every time its topic "
                        "comes round, instead of once. The old behaviour: it "
                        "is what the discrimination baselines were measured "
                        "with, and it inflates evidence when several questions "
                        "share a topic.")
    p.add_argument("--max-filler-share", type=float, default=MAX_FILLER_SHARE,
                   metavar="F",
                   help=f"largest share of served answers that may be generic "
                        f"harness filler before the run is reported as a "
                        f"COVERAGE GAP and stamped invalid "
                        f"(default {MAX_FILLER_SHARE}). Deflections do not "
                        f"count as filler.")
    p.add_argument("--json-out", metavar="FILE", help="write the full transcript as JSON")
    args = p.parse_args(argv)

    exit_actions = [args.cleanup, bool(args.cleanup_founder_email),
                    bool(args.cleanup_founder_id)]
    if sum(exit_actions) > 1:
        p.error("--cleanup / --cleanup-founder-email / --cleanup-founder-id "
                "are mutually exclusive")
    if not args.confirm_writes and not any(exit_actions):
        p.error("--confirm-writes is required (or one of the --cleanup* flags)")

    if args.founder_email and args.founder_id:
        p.error("--founder-email and --founder-id are mutually exclusive")
    if args.stage != 1 and (args.founder_email or args.founder_id):
        p.error("--stage is ignored with --founder-email/--founder-id -- drop one of them")
    return run(args)


# ---------------------------------------------------------------------------
# `desi_bar` -- a real user case, not a test fixture.
#
# A founder at Ideation with a healthy protein bar and mithai-style sweet made
# from desi ingredients, who wants the idea validated. Written to be an HONEST
# founder rather than a strong or weak one: some real work done (kitchen
# batches, friends and family fed, a rough costing), with the gaps a first-time
# D2C food founder actually has -- no strangers interviewed, no FSSAI or
# shelf-life work, price set by looking at a competitor's MRP.
#
# Appended at module scope so the tuples above stay as they were written. The
# argparse `choices` read PERSONAS inside main(), so a persona registered here
# is on the command line like any other.
# ---------------------------------------------------------------------------
_DESI_BAR_TEXTS = (
    # -- _TOPICS, in order ------------------------------------------------
    # 0 customers spoken to / validation
    "Honestly, mostly people who already like me. I've fed samples to about "
    "twenty-five people -- family, my society WhatsApp group, four colleagues "
    "from my old job. Everyone said it was tasty. Two of them asked if they "
    "could buy a box, and I gave it free instead, which I now think was a "
    "mistake. Outside my own circle I have spoken to nobody. No shopkeeper, "
    "no gym owner, no stranger. I know that number should worry me.",
    # 1 planning / time / priorities
    "I work on it after 9pm and on Sundays, because I still have my job. I "
    "don't plan the week -- I do whatever feels most urgent that evening, "
    "which is usually recipe tweaking because it's the part I enjoy. Last "
    "week I spent maybe eleven hours on it and nine of those were in the "
    "kitchen. The boring things -- costing, licence, finding a co-packer -- "
    "keep sliding to next week.",
    # 2 market / competitors
    "The healthy snack shelf in India is crowded at the top -- Yoga Bar, "
    "Max Protein, The Whole Truth. I've picked up their packs and read the "
    "labels. But my read is that they're all Western-format bars with Indian "
    "marketing. Nobody is properly doing a mithai format -- a besan or ragi "
    "laddoo with real protein in it and no refined sugar. That's the gap I "
    "think I'm in. I haven't sized it. I don't know how many people actually "
    "buy healthy mithai versus just saying they would.",
    # 3 product / prototype
    "I have eleven recipe versions in a notebook and three I'm happy with -- "
    "a ragi-peanut bar, a besan-jaggery laddoo, and a makhana-date one. All "
    "made in my own kitchen, hand-rolled, no machine. They last maybe five "
    "days before they go soft. I have not done any shelf-life testing, no lab "
    "report, no nutrition panel that I'd be willing to print on a pack. So I "
    "have a good recipe, not a product.",
    # 4 pricing / revenue / money
    "I put it at Rs 60 a bar because The Whole Truth is around Rs 70 and I "
    "wanted to be a bit cheaper. That's the whole logic, and saying it out "
    "loud it sounds thin. My ingredient cost per bar is roughly Rs 22 when I "
    "buy almonds and dates retail, but that ignores my time, gas, packaging, "
    "wastage and whatever a courier costs. I've never actually built the "
    "sheet. I suspect at Rs 60 with delivery I lose money on every order.",
    # 5 team / co-founder
    "It's me alone. My wife helps with packing on weekends and my mother is "
    "the one who taught me the besan recipe, but neither is a co-founder. I "
    "know I'll need someone for operations because I'm not an ops person, "
    "but I haven't started looking and I haven't thought about what equity "
    "would be fair. Right now every single thing routes through me.",
    # 6 risk
    "Not in a written way, no. If I sit and think about it now: FSSAI "
    "licence, which I don't have. Somebody falling ill from something I made "
    "in a home kitchen. Jaggery and almond prices swinging. And the real one "
    "-- that people say healthy and then buy the thing with sugar in it "
    "anyway. That last one would end the business and I have done nothing to "
    "check it.",
    # 7 decision under uncertainty / pressure
    "I gather too much. I'll read for three weeks before making a call that "
    "could have been tested in two days with fifty rupees of ingredients. "
    "When I'm drained I stop deciding altogether and go back to the kitchen, "
    "because the kitchen always gives me an answer and the business questions "
    "don't.",
    # 8 feedback / criticism / blind spot
    "My brother-in-law runs a small restaurant and he told me flatly that I "
    "am building a recipe, not a business, and that I'm in love with the "
    "product. It stung because he's right. My first reaction was to defend "
    "the recipe, which rather proved his point. I want it straight, but I "
    "notice I only ask people I expect to be kind.",
    # 9 why / vision / origin
    "My father is diabetic. Every Diwali he sits there while everyone else "
    "eats mithai, and he either goes without or eats it anyway and feels "
    "guilty. That's the thing I want to fix -- a sweet that belongs on the "
    "same plate at a festival, made from ragi, jaggery, makhana, ghee, things "
    "my grandmother already used, with protein that actually counts. In five "
    "years I'd want a diabetic uncle at a wedding to be handed one of these "
    "and not have to explain himself.",
    # 10 being first / best / trusted
    "Trusted. In food it's the only one that matters. If someone reads my "
    "label and believes it without checking, I've won. Being first to market "
    "with a ragi protein laddoo means nothing if the second person is more "
    "honest about what's in it.",
    # 11 explain the idea in one breath
    "Indian sweets and protein bars made only from desi ingredients -- ragi, "
    "jaggery, makhana, ghee, dates -- with no refined sugar and no protein "
    "isolate, so people who've been told to stop eating mithai can eat mithai.",
    # 12 personally ran into the problem
    "Last Diwali, at my own house. My father picked up a kaju katli, looked "
    "at it, and put it back down. Nobody said anything. That silence is the "
    "whole reason I'm doing this. I've watched it happen at every festival "
    "for about six years.",
    # 13 tools / how they build
    "A notebook and a kitchen weighing scale, honestly. I keep costs in a "
    "WhatsApp note to myself, which is as bad as it sounds. I haven't set up "
    "a spreadsheet, an Instagram page, or a way to take an order. If somebody "
    "wanted to pay me today I'd have to send them a UPI QR from my phone.",
    # 14 time that eats the most without moving anything
    "Recipe iteration. I can lose a whole Sunday adjusting the jaggery-to-"
    "ragi ratio by five grams, and at the end of it I've learned almost "
    "nothing I could sell on. The version I had in March was probably good "
    "enough to put in front of a shop, and it's September.",

    # -- _CURRENT_PROBLEM_TOPICS ------------------------------------------
    # 0 single biggest thing standing between you and starting
    "I'm scared to charge money. That's it, really. The moment I take Rs 500 "
    "from a stranger it stops being a nice thing I do on Sundays and becomes "
    "something I can fail at publicly, in front of people who know me. So I "
    "keep improving the recipe, because improving the recipe feels like "
    "progress and never puts me in front of that moment.",
    # 1 what would need to be true this week
    "One person I'm not related to would have to pay me for a box and eat it "
    "and tell me the truth about it. That's all. I don't need a licence or a "
    "co-packer or a brand name for that to happen this week.",
    # 2 what already tried, why it stalled
    "I made a batch for my society's Ganesh Chaturthi event and handed it "
    "out free. People ate them and were nice about it. I got zero real "
    "information because free food is always nice. I also half-made an "
    "Instagram page, posted twice, then stopped because I didn't have a "
    "logo I liked. That's the pattern -- I stall on the cosmetic step.",
    # 3 what would stop it cold if it broke
    "Me. If I'm ill for two weeks there is no product, because it's my hands "
    "in my kitchen. There's no recipe written down properly that somebody "
    "else could follow, no supplier on record, nothing. It's all in my head "
    "and my notebook.",
    # 4 what you're avoiding this week
    "The FSSAI registration. I've had the page open on my laptop for about "
    "two months. I think I'm avoiding it because filling it in makes it "
    "official, and then people will ask me how it's going.",
    # 5 metric you've been quietly avoiding
    "Cost per unit, fully loaded. I know roughly what the ingredients cost "
    "and I've deliberately not added up gas, packaging, my hours and "
    "wastage, because I'm fairly sure the number tells me Rs 60 doesn't work "
    "and then I'd have to change either the price or the recipe.",
    # 6 problem that keeps resurfacing
    "Shelf life. Every couple of months I decide it's fine because people eat "
    "them within two days anyway, and then I remember that a shop won't touch "
    "something that softens in five days. I keep deciding it's solved and it "
    "keeps coming back because I've never actually tested it.",
    # 7 decision that landed on you
    "Everything lands on me -- there's nobody else. But the one that "
    "shouldn't have taken a month was choosing the packaging. That's a "
    "reversible, fifty-rupee decision and I treated it like it was permanent.",

    # -- _FOUNDER_TOPICS ---------------------------------------------------
    # 0 last thing that genuinely satisfied you
    "The first batch where the besan laddoo held together without any binder "
    "I wasn't happy with. Four months of it crumbling, and then it just "
    "worked. What landed was that it was mine -- not a recipe I'd copied, "
    "something I'd actually arrived at.",
    # 1 trophy vs bridge
    "The bridge. Easily. I don't need anyone to know it was me. I'd genuinely "
    "be happy if someone's father ate one at a wedding and never once thought "
    "about who made it.",
    # 2 what recharges / flow
    "The quiet kitchen, early, before anyone's up. That's where I lose three "
    "hours without noticing. A loud room drains me -- I did a food expo in "
    "Pune in June and I was finished by noon, and I didn't speak to a single "
    "stall owner properly.",
    # 3 considered dropping it / what 'done' means
    "In April, after I costed it roughly and realised the margin might not be "
    "there. I stayed with it because Diwali came around again and I watched "
    "the same thing happen with my father. 'Done' for me would be a shop I "
    "have no relationship with reordering without me asking.",
    # 4 not scalable but doing anyway
    "Hand-rolling every single laddoo and writing a note in the box. It "
    "cannot scale and I know it. I'm doing it because it's the part that "
    "feels like mine, and I'll probably hold onto it longer than I should.",
    # 5 walked away / the line
    "A distributor at the expo offered to help if I'd use palm oil and a "
    "cheaper protein powder to bring cost down. I said no on the spot. The "
    "line is that I won't sell my father something I wouldn't let him eat -- "
    "if I break that, there's no reason for this thing to exist.",
    # 6 perfectionism / polishing
    "The logo. Two months, maybe forty versions, and it delayed the Instagram "
    "page and therefore delayed anyone outside my circle ever hearing about "
    "this. Same with the eleven recipe versions. I polish the thing I control "
    "so I don't have to do the thing I can't.",
    # 7 if fixed overnight, how much would it change life for the user
    "For most people, honestly, not much -- it's a nicer snack. But for the "
    "diabetic uncle at the wedding it changes the evening. He stops being the "
    "person who can't. I think the mistake I keep making is pricing and "
    "pitching this at the first group when the second group is the one who "
    "actually needs it.",
    # 8 is your own experience representative
    "Probably not, and I've been assuming it is. My father is diabetic, so "
    "festivals are loaded for me in a way they aren't for most people. I've "
    "built the whole idea on my own household's experience and I've never "
    "checked whether a stranger feels any of it. That's the gap.",
)

_DESI_BAR_ONBOARDING = {
    "business_name": "Desi Protein Co.",
    "problem_statement":
        "People who have been told to cut sugar -- diabetics, and anyone "
        "watching what they eat -- are excluded from Indian festival and "
        "everyday sweets, and the healthy options on the shelf are Western "
        "protein bars that do not belong on a mithai plate.",
    "building_summary":
        "Protein bars and mithai-format sweets made only from desi "
        "ingredients -- ragi, jaggery, makhana, ghee, dates -- with no "
        "refined sugar and no protein isolate.",
    "industry": "Food & Beverage (D2C)",
    "current_challenges": ["Sales", "Operations"],
    "goal_90_day":
        "One person outside my own network paying for a box, and a fully "
        "loaded cost sheet I trust.",
    "vision_1_year":
        "Shops I have no personal relationship with reordering on their own, "
        "and a sweet a diabetic guest can be handed at a wedding without "
        "having to explain himself.",
    "product_description":
        "A range of hand-made Indian sweets and bars -- ragi-peanut, "
        "besan-jaggery, makhana-date -- built to sit on the same plate as "
        "traditional mithai while being something a diabetic can eat.",
}

DESI_BAR_ANSWERS = _DESI_BAR_TEXTS
ANSWER_BANK["desi_bar"] = tuple(zip(
    _TOPICS + _CURRENT_PROBLEM_TOPICS + _FOUNDER_TOPICS, _DESI_BAR_TEXTS))
# Topic-neutral, like the rest: it must not say anything about a dimension
# the question never raised, or the fallback itself becomes evidence.
FALLBACKS["desi_bar"] = ("No, I have not got to that one yet -- it keeps "
                         "sliding to next week behind whatever is in front "
                         "of me that evening.")
PERSONAS["desi_bar"] = DESI_BAR_ANSWERS
_ONBOARDING["desi_bar"] = _DESI_BAR_ONBOARDING


# ---------------------------------------------------------------------------
# `arya_parlour` -- a second real user case, at Early Traction.
#
# Arya runs a beauty parlour with two franchise units and wants to franchise
# across India. Roughly Rs 1-1.5 lakh a month today; she wants Rs 10 lakh.
#
# Written the way she would actually talk -- warm, specific, occasionally
# contradicting herself -- rather than in the clipped register of the older
# personas. The interesting thing about this case is the distance between the
# ambition and the operating reality: two units she can barely keep
# consistent, no written process, and a founder still doing bridal makeup
# herself on Saturdays.
# ---------------------------------------------------------------------------
_ARYA_TEXTS = (
    # ---- _TOPICS (15) ---------------------------------------------------
    # 0 customers spoken to / validation
    "Every single day, but I should be honest about what kind of talking. I "
    "chat with the women in my chair for two hours at a time, so I know my "
    "Pune customers better than anyone. But franchise buyers? That is a "
    "totally different customer and I have properly spoken to maybe four. "
    "Both my current franchisees came to me -- one is my cousin's friend, the "
    "other was a client for three years. I have never once gone out and found "
    "someone who did not already know me.",
    # 1 planning / time / priorities
    "I plan the salon week properly -- bookings, staff shifts, stock, all of "
    "it is tight. The expansion I do not plan at all. It happens on Sunday "
    "night if I have energy left, which honestly is maybe two Sundays a "
    "month. Last week I did about sixty-two hours and I would say four of "
    "them were on the franchise idea. The rest was me behind the chair or "
    "sorting out something at the Kothrud branch.",
    # 2 market / competitors
    "Locally I know exactly who I am up against -- there are two salons in "
    "the same lane and I know their rate cards by heart. Nationally I have no "
    "idea. Lakme Salon, Naturals, Green Trends, Jawed Habib -- these are the "
    "names, and Naturals has something like seven hundred outlets. What I "
    "have not done is sat down and worked out what makes someone pick my "
    "franchise over Naturals when Naturals has the brand and the ad budget. I "
    "keep saying personal touch, but that is not really an answer, is it.",
    # 3 product / what you have built
    "Two franchise units, both in Pune, both running about eighteen months. "
    "Plus my own original parlour in Karve Nagar which is nine years old now. "
    "What I have actually built is a good salon and a reputation. What I have "
    "not built is a franchise system -- no manual, no training programme, no "
    "brand guidelines. When the second franchisee opened I basically stood in "
    "her salon for three weeks and showed her. That is not something I can do "
    "forty times.",
    # 4 pricing / revenue / money
    "The salon does about one to one and a half lakh a month, and that is "
    "mostly my own outlet -- bridal season pushes it up, monsoon it drops. "
    "From the two franchises I take a small royalty, around eight thousand "
    "each, and I will be honest, one of them has paid late four months "
    "running and I have not pushed because she is family, more or less. So "
    "the franchise side is not really revenue yet. I want to get to ten lakh "
    "a month and when I say that number out loud I have not actually worked "
    "out what has to be true for it. I think I have been assuming more "
    "franchises equals more money without doing the sum.",
    # 5 team / co-founder
    "No co-founder. I have four girls at my own outlet -- two beauticians, "
    "one who does hair, one at the desk. Been with me three to six years, "
    "very loyal, I trust them with clients completely. But nobody there is "
    "going to help me build a franchise business, and I have not hired anyone "
    "for that because I do not know what that person even looks like. My "
    "husband handles some of the accounts in the evening.",
    # 6 risk
    "Not written down anywhere, no. In my head -- a franchisee doing bad work "
    "and someone posting about it, that frightens me the most. One bad Google "
    "review with my name on it in a city I have never visited. Also money, "
    "because if I take a franchise fee and the girl fails in eight months, "
    "that is her savings. That would sit very badly with me.",
    # 7 decision under uncertainty
    "I decide fast, sometimes too fast. I signed the second franchise in "
    "about ten days because she was keen and I was flattered. Looking back I "
    "did not check whether she could actually run a business or just wanted "
    "to. When I am exhausted I say yes to things I should sit on.",
    # 8 feedback / criticism / blind spot
    "My senior beautician, Sunita, told me something in March that I did not "
    "want to hear. She said I talk about going all-India but I still do the "
    "bridal bookings myself every Saturday, so when would I even have the "
    "time. My first reaction was to explain why bridal is different and "
    "high-margin, and then afterwards I thought, no, she is right and I was "
    "just defending it. I do take feedback, but from my own people. I do not "
    "go looking for it from outside.",
    # 9 why / vision / origin
    "I started in one room in my house because my marriage was not in a good "
    "place and I needed my own money. Nine years later I employ four women, "
    "and two more run their own places. That is the thing that actually moves "
    "me -- not the salon, the fact that women who had nothing of their own "
    "now have something. Five years from now I want fifty women running their "
    "own outlet under my name and not needing to ask anyone for money.",
    # 10 first / best / trusted
    "Trusted, without question. In this line a woman is letting you touch her "
    "face before her own wedding. If she does not trust you, nothing else "
    "matters. I would rather be the one people recommend quietly than the one "
    "with the biggest hoarding.",
    # 11 explain it in one breath
    "A beauty parlour franchise for small-town and neighbourhood India, run "
    "by women who want their own business, where the training and the "
    "standards actually come with it instead of just the board outside.",
    # 12 personally ran into the problem
    "I lived it. When I started nobody trained me properly -- I did a "
    "six-month course that taught me almost nothing useful and then I learned "
    "on real customers, which is a terrible way to learn. I burnt a client's "
    "hair in my second month. I still remember her face. That is the gap I am "
    "trying to fix for the next woman.",
    # 13 tools
    "WhatsApp for everything, which is the honest answer. Bookings in a "
    "diary, a paper one. I tried a salon software last year for two months, "
    "could not get the staff to use it, gave up. The franchise accounts are "
    "in a notebook my husband keeps. So if you asked me today how much profit "
    "the Kothrud branch made in July, I could not tell you without sitting "
    "down for an hour.",
    # 14 time that eats the most
    "Doing treatments myself. I am good at it and clients ask for me by name, "
    "so I keep doing it, and it takes thirty-plus hours of my week. Every one "
    "of those hours is an hour not spent building the thing I say I want. I "
    "know this. I have known it for about two years.",

    # ---- _OPERATING_TOPICS (21) -----------------------------------------
    # 0 delegation
    "Badly. I will tell one of the girls to handle a client and then hover, "
    "or I take over halfway because it is faster. With the franchisees it is "
    "worse -- they call me and I just solve it on the phone instead of making "
    "them work it out. I think I have trained everyone to depend on me.",
    # 1 if you got sick / in your absence
    "I had dengue two years ago and was out for eleven days. Revenue that "
    "month dropped by nearly forty percent and two bridal bookings went to "
    "the salon down the road. Sunita held the place together but she could "
    "not do the bridal or the accounts or the ordering. So honestly, if I "
    "disappeared the business would survive maybe three weeks.",
    # 2 written down / SOPs
    "Nothing is written down. Not one page. All of it is in my head or in my "
    "hands. When I trained the second franchisee I stood there and showed "
    "her, and when she forgets something she rings me. I know that is the "
    "single biggest thing stopping me from opening a third, and yet I have "
    "not written a word, and I cannot fully explain why.",
    # 3 who owns what / role clarity
    "In my own salon everyone knows their job, it runs smoothly. Between me "
    "and the franchisees it is completely unclear. Who pays for the "
    "advertisement? Who decides if she can add a new service? We have never "
    "written it down, so every time something comes up we argue about it "
    "fresh and I usually give in.",
    # 4 decision rights / disagreements
    "There is no proper way. Last month the Kothrud franchisee wanted to run "
    "a 40% discount for Shravan. I said no, it damages the brand, she said it "
    "is her salon and her rent. She ran it. I did not stop her because I have "
    "no agreement that says I can. That was a bad week.",
    # 5 how do you know the team is performing
    "I can see it in my own salon -- I am standing there. For the franchises "
    "I genuinely do not know. I see the royalty amount, which tells me a "
    "little, and I hear things. I have never once looked at their actual "
    "numbers, their repeat customer rate, anything. I would not even know "
    "what to ask for.",
    # 6 hiring / kept someone too long
    "Yes. A girl at my outlet, about two years back -- lovely person, clients "
    "did not warm to her, and I kept her nearly a year longer than I should "
    "because letting her go felt cruel. It cost me. I am soft that way and it "
    "is going to be a real problem when there are thirty outlets.",
    # 7 churn / retention
    "At my own place retention is excellent -- I have clients from year one, "
    "some of them come every ten days. I would guess seventy percent of my "
    "revenue is regulars. For the franchises I have no idea whether their "
    "customers come back. Nobody is tracking it. That is probably the number "
    "that would tell me most and I do not have it.",
    # 8 buying journey
    "For the salon, simple -- a friend tells them, or they walk past, or they "
    "see us on Instagram. For a franchise I really could not describe it. "
    "Both the ones I have came through relationship. If a woman in Nagpur "
    "wanted to buy my franchise tomorrow, there is no place she could even "
    "find out about it. No website, no enquiry form, nothing.",
    # 9 pricing / quotes / discounts
    "My salon rate card is fixed and printed, that is fine. The franchise "
    "fee I have made up twice -- I charged the first one two lakh and the "
    "second one one and a half, and the only reason was that the second "
    "negotiated and I felt awkward. If someone asked me today what it costs "
    "I would probably say a number based on how the conversation was going, "
    "which is not a business.",
    # 10 cash / profit / margin
    "I know what comes in. I could not tell you my actual profit. Rent, four "
    "salaries, products, electricity -- it all comes out of the same account "
    "and my household expenses come out of it too, which I know is wrong. I "
    "check the balance on my phone and if it looks alright I carry on. I have "
    "never made a proper P&L, not in nine years.",
    # 11 evidence of demand beyond your own belief
    "Honestly? Mostly belief. What I could show is that two women took the "
    "franchise and both are still running after eighteen months, and that my "
    "own place has survived nine years including Covid. What I could not show "
    "is anyone outside my circle wanting it -- no waiting list, no enquiries, "
    "nothing on paper. If an investor asked me to prove demand for the "
    "franchise I would struggle.",
    # 12 marketing / campaigns
    "Instagram, and only when I remember. I post a before-after when a bridal "
    "looks nice, so maybe six or seven times a month, no plan behind it. I "
    "have never run a campaign with a goal attached. I would not know what "
    "success looked like other than getting some likes.",
    # 13 who you designed it for vs who buys
    "I thought my franchisee would be a young girl straight out of beauty "
    "school wanting her own place. Both the actual ones are married women in "
    "their thirties with some savings and family support who want something "
    "of their own. That is a different person with different worries and I "
    "have not changed anything about how I talk about it. I only really "
    "noticed this while answering you now.",
    # 14 who are you now as a leader
    "In year one I was a beautician who owned a chair. Now I am supposed to "
    "be someone other women depend on for their income, and I do not think I "
    "have grown into that. I still feel like the girl doing facials in her "
    "spare room. Nobody knows I feel that way.",
    # 15 changed shape / when
    "It changed when the first franchise opened, and I did not notice for "
    "about six months. Before that every problem was mine to solve with my "
    "own hands. After that, other people's money and other people's "
    "reputations were riding on decisions I was making casually.",
    # 16 data / privacy
    "I have client phone numbers and their appointment history in a diary, "
    "and photographs of women's faces before their weddings on my phone, "
    "which I sometimes post. I ask them, usually verbally. Nothing is written "
    "or signed. I had not really thought of it as a risk until this question.",
    # 17 sales pipeline
    "There is no pipeline. If you asked me how many people are currently "
    "interested in taking a franchise, the answer is one, a lady from Nashik "
    "who called in July, and I have not rung her back. That is the entire "
    "pipeline of my all-India expansion.",
    # 18 templates / proposals
    "Nothing reusable. Both times I explained the franchise over tea and then "
    "we made a simple agreement with a lawyer my husband knows. Different "
    "terms both times. If a third person came I would start from scratch "
    "again.",
    # 19 contracts / oversight
    "My husband's lawyer friend looked at both agreements, briefly. I read "
    "them but I would not say I understood every clause. There is nothing in "
    "there about quality standards or what happens if she stops paying, which "
    "I only realised when the payments started coming late.",
    # 20 publishing content
    "Six or seven Instagram posts a month, no schedule, whenever a client "
    "looks especially good. Nothing written, no blog, nothing about the "
    "franchise at all. Somebody told me I should be making reels and I have "
    "been meaning to for a year.",

    # ---- _CURRENT_PROBLEM_TOPICS (8) ------------------------------------
    # 0 single biggest thing
    "I am the business. That is it. Everything runs through my hands and my "
    "phone, and I keep saying I want fifty outlets while I am personally "
    "doing someone's bridal makeup on a Saturday. I cannot be in Nagpur and "
    "at that chair at the same time, and I have not let go of the chair.",
    # 1 what would need to be true this week
    "I would have to let Sunita do a full bridal on her own, start to finish, "
    "without me in the room. That is genuinely it. If I could do that one "
    "thing this week it would tell me more than any plan.",
    # 2 already tried / why it stalled
    "I started writing a training manual in January. I got four pages in -- "
    "hygiene and how to greet a client -- and then bridal season hit and I "
    "never went back. I also made a list of ten cities to target and did "
    "nothing with it. Both times it was not that I gave up, it is that a "
    "client walked in and the client always wins.",
    # 3 what would stop it cold
    "Me. If I could not work, the whole thing stops in about three weeks. "
    "After that, honestly, my Karve Nagar landlord -- I am on a verbal "
    "understanding there, nine years, no written lease. If he asked me to "
    "leave I would have nothing to stand on.",
    # 4 avoiding this week
    "Ringing the Kothrud franchisee about the late royalty. Four months now. "
    "Every week I decide I will call her and every week I do not, because she "
    "is practically family and I hate the conversation. Meanwhile I am "
    "teaching her that it does not matter.",
    # 5 metric quietly avoiding
    "My actual profit. And close behind it, what I earn per hour when I am "
    "behind the chair versus what those hours would be worth building the "
    "franchise. I have avoided both for about two years because I think I "
    "know roughly what they say.",
    # 6 problem that keeps resurfacing
    "Quality at the franchise outlets. Every few months I hear something -- a "
    "client complained, they used a cheaper product, the place was not clean. "
    "I go, I have a talk, it improves for a month, then it slides back. I "
    "keep treating it as a people problem when actually there is no standard "
    "written anywhere for them to fall short of.",
    # 7 decision that landed on you
    "The Shravan discount one. That should have been settled by an agreement "
    "signed eighteen months ago, not by the two of us arguing on the phone at "
    "eleven at night. Almost everything lands on me like that because I never "
    "set up anything to decide it in advance.",

    # ---- _FOUNDER_TOPICS (9) --------------------------------------------
    # 0 last thing that satisfied you
    "The second franchisee's opening day. She cried, her husband was "
    "photographing everything, her mother was there. I built that. Not the "
    "salon -- that moment for her. Nothing in my own salon has felt like "
    "that in years.",
    # 1 trophy vs bridge
    "The bridge, easily. I do not need my name on it. I want a woman in some "
    "town I will never visit to be earning her own money because of something "
    "I set up. That is the whole point of it for me.",
    # 2 what recharges / flow
    "Strangely, doing a really good bridal. Four hours, one face, total "
    "silence in my head. That is my flow and it is also my trap, because it "
    "is the thing I should be doing least. What drains me is the phone -- "
    "franchisee calls, supplier calls, that leaves me finished.",
    # 3 considered dropping it / what 'done' means
    "Last November. Payments late, a complaint from Kothrud, and I thought, "
    "why am I doing this, my own salon is fine and profitable and simple. "
    "What stopped me was the opening day memory, honestly. 'Done' for me "
    "would be a franchise opening in a city where I do not go, run properly, "
    "without me on a single phone call.",
    # 4 not scalable but doing anyway
    "Personally training every franchisee, standing in their salon for three "
    "weeks. And doing the bridals. Both are completely unscalable and both "
    "are the parts I love, so I keep finding reasons why they are "
    "necessary. They are not necessary. They are comfortable.",
    # 5 walked away / the line
    "A man approached me last year about putting my name on a chain of salons "
    "he would run, good money upfront. I said no because he talked about the "
    "staff like they were furniture. I will not put my name on a place where "
    "the girls are treated badly. That is the line and I would hold it even "
    "if it cost me the expansion.",
    # 6 perfectionism
    "The logo and the interiors. I spent nearly five months and a lot of "
    "money getting the second franchise's interiors exactly like mine -- same "
    "shade of paint, same mirrors. Five months. In that time I could have "
    "written the manual that actually matters, and the customer would not "
    "have noticed a different shade of paint.",
    # 7 if fixed overnight, what changes for the user
    "For the franchisee it changes everything -- she would have a real system "
    "instead of my phone number. Right now what she has bought is access to "
    "me, and I am one person with a full appointment book. For the end "
    "customer, honestly, not much changes; she already gets a decent facial. "
    "The person I am actually failing is the franchisee.",
    # 8 is your own experience representative
    "Probably not, and I have been assuming it is. I built everything around "
    "what I needed nine years ago -- a woman with no money, no training, "
    "starting from her house. My actual franchisees have savings, a husband "
    "backing them, and a completely different fear, which is losing what they "
    "already have. I have been designing for who I was, not for who they are.",
)

_ARYA_ONBOARDING = {
    "business_name": "Arya Beauty Studio",
    "problem_statement":
        "Women who want to run their own beauty parlour get no real training "
        "or system -- the big franchise chains sell a board and a rate card, "
        "and independent salons learn on real customers and make expensive "
        "mistakes.",
    "building_summary":
        "A beauty parlour franchise for neighbourhood and small-town India, "
        "run by women, where the training and the standards come with the "
        "brand rather than just the signage.",
    "industry": "Beauty & Wellness",
    "current_challenges": ["Operations", "Team"],
    "goal_90_day":
        "A written training manual and one franchise signed by someone I did "
        "not already know.",
    "vision_1_year":
        "Ten outlets running to the same standard, and a month where I do not "
        "personally do a single bridal.",
    "product_description":
        "A franchised beauty parlour -- hair, skin, bridal -- sold to women "
        "who want their own business, with training, standards and supply "
        "included.",
}

ARYA_ANSWERS = _ARYA_TEXTS
ANSWER_BANK["arya_parlour"] = tuple(zip(
    _TRACTION_TOPICS + _CURRENT_PROBLEM_TOPICS + _FOUNDER_TOPICS, _ARYA_TEXTS))
# Topic-neutral, in her voice: it must not smuggle in evidence about a
# dimension the question never raised.
FALLBACKS["arya_parlour"] = ("No, I have not done that one, and I cannot even "
                             "give you a good reason -- it just never reaches "
                             "the top of the list.")
PERSONAS["arya_parlour"] = ARYA_ANSWERS
_ONBOARDING["arya_parlour"] = _ARYA_ONBOARDING


# ---------------------------------------------------------------------------
# `vikram_logistics` -- a blind QA case at Growth / Scaling.
#
# Regional logistics, Rs 15 crore, 85 people, four cities, twelve B2B accounts,
# department heads in place, expanding to ten cities in eighteen months.
#
# Written for a BLIND test: the founder does not know what is wrong with him and
# does not say it. The evidence is present and the conclusion is not -- he says
# he delegates and then describes reversing decisions in the same breath, calls
# the margin slide a market problem, and treats the queue outside his office as
# proof he is needed. An engine that only reads what he claims will call this a
# healthy scaling business.
# ---------------------------------------------------------------------------
_VIKRAM_TEXTS = (
    # ---- _TOPICS (15) ---------------------------------------------------
    # 0 customers spoken to / validation
    "Constantly. Twelve major accounts and I know all twelve promoters "
    "personally -- I still do the quarterly review calls myself for the top "
    "six. That relationship is genuinely why we win. When a client has a "
    "problem at 11pm they call me, not the account manager, and it gets "
    "sorted. I think that is our advantage, not a problem.",
    # 1 planning / time / priorities
    "Long days, and I would not call it planned. I am in by seven and the "
    "first two hours are the only clean ones. After that it is whatever is in "
    "front of me -- approvals mostly. If I look at last week honestly, the "
    "expansion work happened in aeroplanes and on Sunday. The urgent stuff "
    "eats the important stuff, which I know is a cliche, but it is true.",
    # 2 market / competitors
    "We know the regional players well. The nationals -- Delhivery, Safexpress "
    "-- are above us on price because of scale, and the small local guys "
    "undercut us on short hauls. We sit in the middle on service. Where I "
    "would say I am less sure is what happens to that position in ten cities "
    "instead of four. In our four we have relationships. In Indore or Nagpur "
    "we would be a name nobody knows.",
    # 3 product / what you have built
    "Fifteen crore, eighty-five people, four cities, twelve major B2B "
    "accounts. Three years ago we were a third of that. The operation itself "
    "is solid -- our on-time numbers are good, the fleet is maintained, the "
    "warehouse discipline is there. I am proud of it. I built it from two "
    "trucks and a rented shed.",
    # 4 pricing / revenue / money
    "Rate cards per client, negotiated annually, with exceptions when a client "
    "pushes. The exceptions come to me. Margins have been slipping the last "
    "three or four quarters -- diesel, driver wages, and clients squeezing at "
    "renewal. My read is it is market pressure. Though if I am honest I could "
    "not tell you which of the twelve accounts is actually profitable at the "
    "line level right now.",
    # 5 team / co-founder
    "No co-founder, it is my company. But I have department heads now -- "
    "operations, fleet, sales, accounts, HR. Good people, most have been with "
    "me four years plus. On paper the structure is there. They run their "
    "functions and bring me what needs deciding.",
    # 6 risk
    "Yes, in my head, always. Client concentration worries me -- our top three "
    "are a big chunk. Diesel. A serious accident. What I have not done is put "
    "any of that on paper or in front of the team. I tend to carry it myself "
    "rather than worry everybody.",
    # 7 decision under uncertainty
    "Fast. That is how we got here. I would rather make eight decisions "
    "quickly and be wrong on two than sit on all eight for a month. In this "
    "business speed genuinely wins -- if a client asks for something Friday "
    "and you answer Monday, you have lost them. I have very little patience "
    "for long deliberation.",
    # 8 feedback / criticism / blind spot
    "I ask for it. Not sure how much I get. My ops head is direct with me, "
    "the others less so. Somebody said something a few months ago about "
    "things waiting on me -- I took the point, we added a rule that anything "
    "under fifty thousand does not need my sign-off. I do still look at most "
    "of them, but that is me being thorough, not blocking anything.",
    # 9 why / vision / origin
    "I drove one of the two trucks myself for the first eight months. My "
    "father had a transport business that went under when I was nineteen and "
    "I watched what that did to him. So this is partly that -- building the "
    "thing he could not hold on to. In five years I want to be the regional "
    "player the nationals have to price against, across ten or twelve cities.",
    # 10 first / best / trusted
    "Trusted. In logistics the client is handing you their goods and their "
    "promise to their own customer. You get that wrong twice and no rate card "
    "saves you. We win on being the ones who pick up the phone.",
    # 11 explain it in one breath
    "Regional B2B logistics -- warehousing and line-haul across four cities "
    "for manufacturers and distributors who need reliability more than they "
    "need the lowest rate.",
    # 12 personally ran into the problem
    "My father's business. Watching goods sit because nobody would answer a "
    "phone, and clients leaving one by one. That is why I answer the phone.",
    # 13 tools
    "We have a TMS for dispatch, Tally for accounts, and everything else is "
    "Excel and WhatsApp. Each department head has their own sheet. There is "
    "no single place I can open and see the business -- if I want the real "
    "picture I ask four people and put it together myself. It takes about a "
    "day and by then it has moved.",
    # 14 time that eats the most
    "Approvals and exceptions. A client wants a rate deviation, a branch wants "
    "to hire a supervisor, somebody wants to waive a detention charge. Each "
    "one is five minutes. There are forty of them a day. That is most of my "
    "week and none of it is the ten-city plan.",

    # ---- _OPERATING_TOPICS (21) -----------------------------------------
    # 0 delegation
    "I delegate a lot more than people think. The heads run their departments. "
    "What I do is stay close -- I want to know what is being decided, and if I "
    "see it going wrong I will step in, because it is faster than letting it "
    "play out and fixing it later. That is not the same as not delegating.",
    # 1 if you got sick / in your absence
    "Two weeks would be hard. Not impossible -- the trucks would run, the "
    "warehouse would run. But every exception and every approval would stack "
    "up waiting for me. I went to Singapore for nine days in March and came "
    "back to about sixty things in the queue. Some of them had gone cold.",
    # 2 written down / SOPs
    "Operations are documented -- loading, handover, damage claims, all of "
    "that is in the manual and audited. What is not written down is how "
    "decisions get made. Who can approve what, up to what value, without "
    "asking. That lives with me and people have learned it by watching.",
    # 3 who owns what / role clarity
    "Clear at the function level -- ops is ops, fleet is fleet. Where it gets "
    "murky is anything crossing two functions, or anything new. The expansion "
    "is the obvious one. I have a plan with city targets and dates, but if you "
    "asked me who owns Indore, the honest answer is me, for now.",
    # 4 decision rights / disagreements
    "It comes to me. That is the resolution mechanism. If sales and ops "
    "disagree about whether to take a load at a certain rate, they both call "
    "me and I decide in two minutes. It works. I suppose it means they do not "
    "resolve much between themselves.",
    # 5 how do you know the team is performing
    "I can feel it. I am in the operation every day, I see who is on top of "
    "their patch. On paper -- ops has their numbers, sales has theirs, but "
    "they are different sheets in different formats and I have never put them "
    "side by side. There is no single dashboard, no. It is on the list.",
    # 6 hiring / kept someone too long
    "Yes. A branch manager in Nashik, kept him about a year longer than I "
    "should have because he had been with me since early days. Every senior "
    "hire comes through me -- I meet every one of them before an offer goes "
    "out, even at supervisor level, because culture is everything in this "
    "business.",
    # 7 churn / retention
    "Very low, which is the thing I am proudest of. We have not lost a major "
    "account in three years. One reduced volume when their own business "
    "shrank. That is the relationship doing its work.",
    # 8 buying journey
    "Referral, mostly, or I know somebody. A manufacturer's logistics head "
    "asks around, my name comes up, we meet, I quote. The sales team generates "
    "leads but the big ones close with me in the room. Always have.",
    # 9 pricing / quotes / discounts
    "Annual rate card per client, and then exceptions all year. Fuel "
    "surcharge, seasonal, a client who has had a bad quarter and asks for "
    "relief. I approve those, case by case, on judgement. I would not say "
    "there is a written rule for when we say yes.",
    # 10 cash / profit / margin
    "Cash is fine, we are profitable, we fund growth from operations. But the "
    "margin is drifting down and I have not got to the bottom of it. Accounts "
    "gives me a monthly P&L at company level. Per-client, per-lane "
    "profitability -- we do not produce that. I have been meaning to ask for "
    "it for about a year.",
    # 11 evidence of demand beyond your own belief
    "Three years of growth and twelve accounts that renew. For the ten-city "
    "plan specifically -- less. Two existing clients have said they would "
    "give us volume if we were in those cities, which is what started the "
    "idea. I have not gone beyond that and tested it properly.",
    # 12 marketing / campaigns
    "Almost none. A website, some presence at industry events. In B2B "
    "logistics at our size it is relationships and referrals. That has worked "
    "for four cities. Whether it works for a city where nobody knows me is a "
    "fair question.",
    # 13 who you designed it for vs who buys
    "Still the same -- mid-size manufacturers and distributors who care about "
    "reliability. That has not shifted. If anything we have moved slightly "
    "upmarket as clients grew with us.",
    # 14 who are you now as a leader
    "I do not think I have changed as much as the company has. I still "
    "operate the way I did with twenty people -- close to everything, hands "
    "on, quick. At eighty-five people that is more hours but it is the same "
    "job as far as I am concerned. People tell me I should be more strategic. "
    "I am not entirely sure what that would look like day to day.",
    # 15 changed shape / when
    "Somewhere around the third city, maybe two years ago. Before that I could "
    "genuinely hold the whole thing in my head. Now I cannot, and I have not "
    "really changed anything about how I work to account for that. I just work "
    "longer.",
    # 16 data / privacy
    "We hold client shipment data and some commercial terms. It is on our TMS "
    "and in spreadsheets. Access is informal -- the heads have what they need. "
    "Not something we have formally reviewed.",
    # 17 sales pipeline
    "Sales keeps a sheet. I could not tell you today what is in it without "
    "asking. For the ten-city expansion there is no pipeline -- there is a "
    "plan with dates on it, which is not the same thing.",
    # 18 templates / proposals
    "Rate proposals are semi-standard, the ops annexure is reused. The "
    "commercial terms I write or rewrite myself for anything significant, "
    "because those are the ones that matter.",
    # 19 contracts / oversight
    "I read every contract above a certain size personally. We have a "
    "retained lawyer for the drafting. I would not sign something I had not "
    "read -- that is one I am not willing to hand over.",
    # 20 publishing content
    "Nothing. No blog, no LinkedIn presence to speak of. Not how this "
    "industry buys, in my view.",

    # ---- _CURRENT_PROBLEM_TOPICS (8) ------------------------------------
    # 0 single biggest thing
    "Speed. We are not moving fast enough on the expansion. The plan is "
    "eighteen months for ten cities and we are six months in with one new "
    "city half-opened. Every week that slips, somebody else takes that "
    "ground. I need the organisation to move at the pace I am moving at.",
    # 1 what would need to be true this week
    "Somebody other than me would have to take Indore end to end -- site, "
    "hiring, the first client -- and actually run with it. I keep meaning to "
    "hand it to my ops head but he is already stretched and frankly I am "
    "faster at it.",
    # 2 already tried / why it stalled
    "We set up a weekly expansion review about four months ago. It ran three "
    "times and then died, because two of those weeks I was travelling and "
    "without me in the room it did not really happen. I also put the fifty-"
    "thousand approval rule in. Both were the right idea. Neither stuck.",
    # 3 what would stop it cold
    "Losing one of the top three accounts. Or me being out for a month. I "
    "would like to say the second one is not true but I have just told you "
    "what nine days looked like.",
    # 4 avoiding this week
    "The margin question. I know I need to sit down with accounts and take it "
    "apart client by client, and I keep pushing it because it is a full day "
    "and there is always something on fire. Also a conversation with my sales "
    "head about his numbers that I have been putting off for a month.",
    # 5 metric quietly avoiding
    "Per-client profitability. I have a feeling two or three of the twelve are "
    "barely making money after the exceptions I have approved over the year, "
    "and I have not wanted to find out which ones, because then I have to go "
    "and have that conversation with people I have known for a decade.",
    # 6 problem that keeps resurfacing
    "Decisions waiting. It comes up every few months -- somebody raises it, we "
    "put a rule in, it improves for a while, then it is back. I keep treating "
    "it as a bandwidth problem and hiring another person or adding another "
    "rule, and it keeps coming back.",
    # 7 decision that landed on you
    "Last week a branch wanted to hire a second dispatch supervisor. That came "
    "to me. Salary was well within what the branch manager should be able to "
    "decide. It sat in my queue four days and he was chasing me about it. I do "
    "not know why that one needed me, honestly, but everything does.",

    # ---- _FOUNDER_TOPICS (9) --------------------------------------------
    # 0 last thing that satisfied you
    "Winning the Aurangabad account in February against a national player. "
    "They chose us on service history. Eight years ago that client would not "
    "have taken my call. That landed.",
    # 1 trophy vs bridge
    "Honestly? The trophy. I built this and I would like that to be visible. "
    "My father's business went down and everyone in that town knew. I would "
    "like them to know about this one too. I am aware that is ego.",
    # 2 what recharges / flow
    "Being in the operation. A difficult dispatch day where I am on the floor "
    "solving things -- that is where I feel useful and the hours disappear. "
    "What drains me is the queue. Forty small approvals in a day and I go home "
    "having achieved nothing I can point at.",
    # 3 considered dropping it / what 'done' means
    "Never dropping it. There was a stretch after Covid where I wondered if we "
    "would survive, but that is different. 'Done' would be ten cities running "
    "properly without me in every decision. Saying it out loud, that is quite "
    "far from where we are.",
    # 4 not scalable but doing anyway
    "Meeting every senior hire. Reading every significant contract. Taking the "
    "quarterly calls with the top six clients myself. None of that scales to "
    "ten cities and I know it. I do it because those are the things that "
    "actually determine whether this works, and I am better at them.",
    # 5 walked away / the line
    "A client in 2019 wanted us to move goods with paperwork that was not "
    "right. Good volume. I said no and we lost them. Never regretted it. That "
    "is the line -- I will not do something I would have to hide.",
    # 6 perfectionism
    "Not perfectionism exactly. But I will redo somebody's work if it is not "
    "how I would have done it, and I have been told that is demoralising. A "
    "rate proposal came to me last month, it was fine, I rewrote it anyway "
    "because I would have positioned it differently. Took me two hours.",
    # 7 if fixed overnight, what changes for the user
    "For the client, not much immediately -- service is already good. Over a "
    "year it would matter a lot, because we would be in the cities they are "
    "asking us to be in. The people it would change most are my own managers. "
    "I am not sure they would all enjoy it, actually.",
    # 8 is your own experience representative
    "Probably more than I should assume. I have been in this business twenty "
    "years and I do think I can read a situation faster than most of my team. "
    "That is experience, not arrogance. But I take the point that I am "
    "deciding a lot of things on my own instinct and not checking it.",
)

_VIKRAM_ONBOARDING = {
    "business_name": "Vikram Logistics",
    "problem_statement":
        "Mid-size manufacturers and distributors need a regional logistics "
        "partner who is reliable and reachable -- the nationals are cheaper "
        "but impersonal, and the small operators are unreliable.",
    "building_summary":
        "Regional B2B logistics -- warehousing and line-haul across four "
        "cities, expanding to ten in eighteen months.",
    "industry": "Logistics",
    "current_challenges": ["Operations", "Team"],
    "goal_90_day":
        "Two new cities open and taking volume, and a per-client "
        "profitability view I trust.",
    "vision_1_year":
        "Ten cities running to the same standard, and an organisation that "
        "does not wait for me to decide.",
    "product_description":
        "B2B line-haul and warehousing for manufacturers and distributors "
        "across four cities, sold on reliability rather than lowest rate.",
}

VIKRAM_ANSWERS = _VIKRAM_TEXTS
ANSWER_BANK["vikram_logistics"] = tuple(zip(
    _TRACTION_TOPICS + _CURRENT_PROBLEM_TOPICS + _FOUNDER_TOPICS, _VIKRAM_TEXTS))
# Topic-neutral, in his register: it must not smuggle in evidence about a
# dimension the question never raised.
FALLBACKS["vikram_logistics"] = ("No, not formally. It is one of those things "
                                 "I have carried in my head rather than sat "
                                 "down and done properly.")

# Topics the 53 shared slots do not reach, that this case turns on. Added to
# Vikram's bank only: a fallback on "how many managers can decide without
# escalating" would have measured the persona's hole rather than the engine.
_VIKRAM_EXTRA = (
    ((("could make a real call", "without escalating", "without escalation",
       "decide without escalating", "how many managers"),
      ("escalat", "managers do you")),
     "Without escalating? Two, maybe three of the five, and even they check "
     "with me on anything unusual. The others bring me the decision. I have "
     "told them repeatedly they do not need to. It has not changed much, and "
     "I have stopped pushing it because the queue moves faster if I just "
     "answer."),
    ((("real day off", "without checking in", "day off without"),
      ("day off", "checking in")),
     "Properly, without looking at the phone? I could not tell you. Sundays I "
     "am not in the office but I am answering things. The nine days in "
     "Singapore in March was the longest and I worked through most of it."),
    ((("licenses, permits", "licences, permits", "permits, or certifications",
       "compliance fine"),
      ("licens", "permit", "certification", "compliance")),
     "Yes, all in place -- carrier permits, GST, the warehouse certifications, "
     "and we are audited. Fleet compliance is one thing I do not take chances "
     "with. My fleet head owns it and that one genuinely runs without me."),
    ((("coach and develop", "develop your managers", "developed the skills"),
      ("coach", "develop")),
     "Not really, no. I promote people who are good operators and then expect "
     "them to figure out the management part the way I did. I have never been "
     "taught it either. Looking at it now, I have five heads and I could not "
     "tell you when I last sat with one of them about their own development "
     "rather than about a problem."),
    ((("how many different opportunities", "actively pursuing"),
      ("opportunities", "directions")),
     "One, really -- the ten-city expansion. There is a cold-chain idea a "
     "client keeps raising and I have not said no to it, but it is not being "
     "worked on. So one and a half."),
    ((("instinct on compliance", "own instinct on compliance"),
      ("instinct", "compliance")),
     "On compliance, no -- that is documented and audited, I do not freelance "
     "there. On commercial calls, yes, I trust my instinct heavily. Twenty "
     "years in this business and I am usually right, which is probably why I "
     "keep making them myself."),
)
ANSWER_BANK["vikram_logistics"] = (
    ANSWER_BANK["vikram_logistics"] + _VIKRAM_EXTRA)

PERSONAS["vikram_logistics"] = VIKRAM_ANSWERS
_ONBOARDING["vikram_logistics"] = _VIKRAM_ONBOARDING


# ---------------------------------------------------------------------------
# `siddharth_saas` -- a blind QA case at Early Traction, B2B SaaS.
#
# ComplyFlow: HR compliance software for Indian SMEs. Three years, 42 paying
# companies, about Rs 4.2 lakh MRR, five engineers, and a founder who closes
# most of the deals himself.
#
# The case tests whether the engine separates the four actors a B2B SaaS
# business actually has -- the HR manager who uses it, the founder or CFO who
# approves it, the company that pays, and the person whose pain it solves. The
# founder never names the distinction. He describes it repeatedly without
# noticing it, and reaches for a product explanation every time a commercial
# fact appears.
# ---------------------------------------------------------------------------
_SIDDHARTH_TEXTS = (
    # ---- _TOPICS (15) ---------------------------------------------------
    # 0 customers spoken to / validation
    "A lot, but mostly during sales rather than as research. I am on nearly "
    "every first call -- probably seventy percent of new customers close with "
    "me in the room. What I notice is the HR manager is usually the one who "
    "finds us and gets excited, and then the founder or the CFO is the one who "
    "actually has to sign. Those are two quite different conversations and I "
    "run both.",
    # 1 planning / time / priorities
    "Split badly. Sales calls eat the mornings and I do product in the "
    "evenings, which is when I am least sharp. I would guess half my week is "
    "sales, a third product decisions, the rest admin. The product half is the "
    "part I am actually good at.",
    # 2 market / competitors
    "There are the big HRMS suites -- greytHR, Keka, Zoho People -- which do "
    "everything and do compliance badly as a module. And there are consultants "
    "doing it manually. Our compliance depth is genuinely better than any of "
    "them, I have gone through their products feature by feature. That is not "
    "me being biased, it is a real gap. What I find harder to explain is why "
    "that does not convert faster.",
    # 3 product / what you have built
    "Three years in. Statutory reminders, employee document vault, PF and ESI "
    "workflow, state-wise compliance calendar, audit trail. Forty-two paying "
    "companies, about four point two lakh MRR. Five of us on product and "
    "engineering. The product is solid -- that I am confident about.",
    # 4 pricing / revenue / money
    "Per-employee per-month, with slabs. Honestly it varies more than it "
    "should -- early customers are on old rates, and if someone pushes I "
    "usually find a way. I could not give you an average revenue per customer "
    "off the top of my head without opening the sheet. I know the total.",
    # 5 team / co-founder
    "No co-founder. Five people on product and engineering, all technical. "
    "Nobody owns sales except me. I hired a junior person for outreach last "
    "year and it did not work out -- he could not answer the compliance "
    "questions that come up on the second call, so everything came back to me "
    "anyway.",
    # 6 risk
    "Concentration is not really the risk -- forty-two customers, no one is "
    "huge. What worries me is that growth is tied to my calendar. If I stop "
    "selling, new revenue stops. I have not written any of this down.",
    # 7 decision under uncertainty
    "I gather data where data exists. Where it does not, I go on judgement, "
    "and I am usually reasoning from the product side -- what would make this "
    "better, what would remove friction. That is my instinct for most "
    "problems.",
    # 8 feedback / criticism / blind spot
    "I take product feedback very well, genuinely. Sales feedback I find "
    "harder. When a prospect says it is too expensive or they do not see the "
    "value, my first reaction is that they have not understood what it does, "
    "and I go back and explain it again. Someone told me I argue with "
    "prospects. I would say I clarify.",
    # 9 why / vision / origin
    "I was a backend engineer and my sister runs HR at a two-hundred-person "
    "manufacturing company. I watched her miss a PF deadline and get "
    "personally hauled up for it -- the anxiety of that stayed with me. She "
    "was tracking statutory dates in a diary. In three years I want compliance "
    "to be something an Indian SME does not have to think about.",
    # 10 first / best / trusted
    "Trusted. Compliance is not a category where you want to be the exciting "
    "new thing. If we get a filing date wrong, somebody gets a notice with "
    "their name on it.",
    # 11 explain it in one breath
    "HR compliance software for Indian SMEs -- statutory reminders, employee "
    "documentation and HR workflows, so nobody misses a PF or ESI deadline.",
    # 12 personally ran into the problem
    "Through my sister, not directly. I have never been an HR manager. I have "
    "sat next to one for years and watched what the job actually does to "
    "someone.",
    # 13 tools
    "For the product, proper tooling. For the business, embarrassing -- the "
    "pipeline is a Google Sheet, a lot of WhatsApp, and frankly my own memory. "
    "I know which deals are live because I am on all of them. We put in a CRM "
    "last year and I stopped updating it after about six weeks.",
    # 14 time that eats the most
    "Repeating the same product explanation on sales calls. I have given "
    "essentially the same forty-minute walkthrough a few hundred times. I keep "
    "thinking I should record it, and then the next call is slightly different "
    "and I do it live again.",

    # ---- _OPERATING_TOPICS (21) -----------------------------------------
    # 0 delegation
    "Product I delegate reasonably -- the engineers own their areas. Sales I "
    "have not delegated at all, and I am not sure it is delegable yet. The "
    "second call always turns into a compliance discussion and I am the only "
    "one who can hold that.",
    # 1 if you got sick / in your absence
    "The product would ship, the team is fine. New sales would stop entirely. "
    "Existing customers would be served. So the business would survive and "
    "would not grow.",
    # 2 written down / SOPs
    "Engineering has proper process -- code review, deploys, on-call. Sales "
    "has nothing written. No playbook, no call script, no objection handling "
    "document. It is all in my head, which is fine while I am the one doing "
    "it.",
    # 3 who owns what / role clarity
    "Clear on the engineering side. On the commercial side I own everything "
    "-- lead generation, demos, pricing, closing, and then onboarding and "
    "account management afterwards. There is nobody to be unclear with.",
    # 4 decision rights / disagreements
    "Product disagreements we argue out on merit and usually I decide. It "
    "works because we are small and everyone is technical. Nothing really gets "
    "stuck.",
    # 5 how do you know the team is performing
    "Engineering I can see -- velocity, bugs, what ships. There is no "
    "equivalent measure on the commercial side because there is nobody else "
    "doing it.",
    # 6 hiring / kept someone too long
    "The outreach hire, about eight months. I knew by month three it was not "
    "working and I told myself it was a ramp problem. In hindsight I had given "
    "him nothing to work with -- no script, no list, no definition of who to "
    "call.",
    # 7 churn / retention
    "We lose some. I could not give you a number -- we do not calculate it "
    "properly, it is more that I notice when somebody does not renew. My sense "
    "is it is the ones who never really got going after onboarding. Some "
    "customers are in the product every day and some I look at the logs and "
    "there is almost nothing after the first month.",
    # 8 buying journey
    "Usually the HR manager searches for something or hears about us, comes "
    "in, likes it. Then it has to go up -- to the founder in a smaller "
    "company, or the CFO in a bigger one. That is where it slows down. Forty "
    "to fifty days from first call to signature, and most of that is waiting "
    "for the approval conversation to happen.",
    # 9 pricing / quotes / discounts
    "Per-employee slabs, but I deviate. If a deal is close and they push on "
    "price I will do something. Different customers are on quite different "
    "effective rates for the same thing and I have never gone back and "
    "cleaned that up.",
    # 10 cash / profit / margin
    "We are roughly break-even, funded by revenue and some of my savings. "
    "Gross margin is good, it is software. What I do not have is any view of "
    "what it costs to acquire a customer, because the main cost is my time and "
    "I have never priced that.",
    # 11 evidence of demand beyond your own belief
    "Forty-two companies paying every month for up to three years. That is "
    "real. What I could not show you is why those forty-two and not others, or "
    "which of them we should be trying to find more of.",
    # 12 marketing / campaigns
    "Some content on compliance deadlines, a bit of LinkedIn, mostly written "
    "by me when I have time. No paid spend to speak of. Most of it comes "
    "through referral and search.",
    # 13 who you designed it for vs who buys
    "We have companies from about twenty employees up to five hundred. I "
    "genuinely think there is value across the whole range -- compliance is "
    "compliance. If you asked me which size is our best customer I would have "
    "to think about it, and I am not sure I would have a good answer.",
    # 14 who are you now as a leader
    "Still mostly an engineer who sells because he has to. I am comfortable "
    "talking about the product to anyone. Standing in front of a CFO talking "
    "about ROI, I am less comfortable, and I suspect it shows.",
    # 15 changed shape / when
    "It changed when we crossed about twenty-five customers. Before that I "
    "knew every account personally and what they used. Now I do not, and I "
    "have not replaced that knowledge with anything measured.",
    # 16 data / privacy
    "This one we take seriously -- we hold employee PII, salary data, "
    "statutory records. Encrypted at rest, access controls, audit logs, we did "
    "a security review last year because a larger prospect asked. It is one of "
    "the few business processes that is properly documented.",
    # 17 sales pipeline
    "In a sheet, and in my head. I could tell you roughly what is live because "
    "I am on all of it, but I could not give you a conversion rate by stage "
    "or tell you where deals die. I know it takes forty to fifty days.",
    # 18 templates / proposals
    "A proposal template exists. The demo is not templated -- I do it live "
    "and adapt as I go, which people tell me is a strength and is also why "
    "nobody else can do it.",
    # 19 contracts / oversight
    "Standard subscription agreement drafted by a lawyer, I sign them. Larger "
    "customers occasionally send their own paper and I read those properly. "
    "Not a bottleneck.",
    # 20 publishing content
    "Irregularly -- maybe two or three compliance explainers a month when "
    "things are calm, nothing for weeks when they are not. It does bring "
    "inbound when I keep it up, which I do not.",

    # ---- _CURRENT_PROBLEM_TOPICS (8) ------------------------------------
    # 0 single biggest thing
    "Growth is stuck to me. Seventy percent of what closes, closes because I "
    "was on the call. I want to be at one crore ARR in the next year or so and "
    "I cannot personally sell my way there -- the maths does not work, there "
    "are not enough hours. But every time I try to hand sales over it comes "
    "back to me.",
    # 1 what would need to be true this week
    "Somebody other than me would have to run a full cycle -- first call to "
    "signature -- on a real deal, and win it. That would tell me whether this "
    "is teachable or whether it genuinely needs me.",
    # 2 already tried / why it stalled
    "I hired the outreach person, which failed. I wrote about half a sales "
    "playbook in January and never finished it. I also built a self-serve "
    "signup flow thinking it would let smaller companies buy without a call -- "
    "we got signups and almost none of them converted to paid. That one I have "
    "not properly worked out.",
    # 3 what would stop it cold
    "Me. Specifically me on sales calls. The product would keep running "
    "without me for a long time; new revenue would stop the same week.",
    # 4 avoiding this week
    "Going through the accounts that barely use the product. I have a rough "
    "sense of who they are and I have been avoiding actually pulling the "
    "usage data and calling them, partly because I think the answer might be "
    "that they never needed it and I sold it to them anyway.",
    # 5 metric quietly avoiding
    "Real churn, calculated properly. And activation -- what percentage of "
    "customers are actually using the thing sixty days in. I have a feeling "
    "both numbers are worse than the story I tell myself, and the MRR going up "
    "has let me not look.",
    # 6 problem that keeps resurfacing
    "Deals stalling at the approval stage. The HR manager is sold, then it "
    "goes to the founder or the CFO and sits. I keep treating it as a "
    "messaging problem and rewriting the deck, and it keeps happening.",
    # 7 decision that landed on you
    "Which features go in the next release. That is genuinely mine to decide, "
    "I think -- but I notice I am deciding it from what the last three "
    "prospects asked for on calls, which is not really a system.",

    # ---- _FOUNDER_TOPICS (9) --------------------------------------------
    # 0 last thing that satisfied you
    "We shipped state-wise compliance rules for all twenty-eight states in "
    "March. Nobody else in this category has that depth. Two customers "
    "specifically mentioned it. That felt like the thing I am actually here "
    "to do.",
    # 1 trophy vs bridge
    "The bridge. If ComplyFlow disappeared and somebody else made HR "
    "compliance boring and safe for Indian SMEs, I would be genuinely fine "
    "with that. I want the problem solved more than I want to be the one who "
    "solved it.",
    # 2 what recharges / flow
    "Building. A hard technical problem and a closed door and I lose the whole "
    "day happily. What drains me is back-to-back sales calls -- four in a day "
    "and I am finished, even though objectively it is just talking.",
    # 3 considered dropping it / what 'done' means
    "Around year two, when we were at maybe twelve customers and I could not "
    "see how it scaled. What kept me in was a customer telling me we had "
    "caught something that would have been a real penalty for them. 'Done' "
    "would be the company growing without me on every call.",
    # 4 not scalable but doing anyway
    "Doing every demo myself. Answering compliance questions personally, "
    "including for customers who are already paying. Writing the content. None "
    "of it scales and I do it because I am better at it than anyone I have "
    "managed to hand it to.",
    # 5 walked away / the line
    "A consultancy wanted to white-label us and resell under their brand. Good "
    "money, would have doubled revenue that year. I said no because they "
    "wanted to control what we told customers about statutory changes, and I "
    "will not have somebody else deciding what a customer is told about a "
    "deadline that could get them fined.",
    # 6 perfectionism
    "Yes, on product. I held the multi-state release back about seven weeks "
    "for edge cases that affected a small number of customers. Meanwhile "
    "nothing happened on the sales side because I was heads-down on that. I "
    "would probably do it again, which may be the problem.",
    # 7 if fixed overnight, what changes for the user
    "For the HR manager, enormous -- she stops lying awake about a date she "
    "might have missed. For the business owner it is quieter: he avoids a "
    "penalty he was not thinking about. That difference might be why the HR "
    "person is excited and the person signing is lukewarm.",
    # 8 is your own experience representative
    "Probably not. I am technical and I find the product obvious, and I have "
    "assumed the value is self-evident in the same way. When a prospect does "
    "not see it my instinct is that I explained it badly, not that they are "
    "genuinely different from me. I have never been an HR manager or a CFO.",
)

_SIDDHARTH_EXTRA = (
    # Aimed at the ONE question in the bank that asks the B2B actor split --
    # "Who actually pays for this, and who actually uses it day to day -- are
    # they the same person?" -- which otherwise ties with the generic customer
    # topic and loses on first-topic-wins. The answer covers both halves
    # because the question asks both.
    ((("who actually pays", "actually uses it day to day",
       "are they the same person", "who actually uses", "daily users"),
      ("users", "who uses", "pays for this")),
     "No, and that is the whole shape of it. The HR manager uses it, every "
     "day -- her and maybe one executive under her, and that is true whether "
     "the company has thirty people or four hundred. The founder or the CFO "
     "is the one who actually signs and pays, and they typically never log in "
     "again after the first month. So the person with the pain and the person "
     "with the budget are two different people."),
    ((("who approves", "who signs off", "economic buyer", "who pays",
       "approving the purchase"),
      ("approve", "sign off", "budget holder")),
     "Founder in a twenty-to-hundred person company, CFO or finance head "
     "above that. They are not the ones who feel the problem day to day -- "
     "they feel it once, when there is a notice. So I am selling relief to "
     "one person and insurance to another, in the same call."),
    ((("why do customers churn", "why they leave", "reason customers leave",
       "why do they cancel"),
      ("churn", "cancel", "leave")),
     "My honest answer is they never really started using it. Whether that is "
     "an onboarding problem, or whether they were the wrong companies to sell "
     "to, I do not know. I have assumed it was onboarding and built more "
     "onboarding."),
    ((("could someone else close", "another salesperson", "somebody else sell",
       "hire a salesperson"),
      ("salesperson", "close the same deal")),
     "I want to say yes but the evidence says no -- I tried it once and it "
     "came back to me. The sticking point is the second call, where it turns "
     "into specific compliance questions about their state and their headcount "
     "and their filings."),
    ((("self-serve", "free trial", "sign up without", "product-led"),
      ("self-serve", "trial", "signup")),
     "We built one. Signups came, conversion to paid was almost nothing, and "
     "I never diagnosed why. I assumed the smaller companies were not serious. "
     "I have not actually gone and asked any of them."),
    ((("expansion revenue", "upsell", "existing customers spend more",
       "grow accounts"),
      ("upsell", "expansion")),
     "Barely. Revenue grows when a customer's headcount grows, because we are "
     "per-employee, and that happens on its own. We have never deliberately "
     "sold anything additional to an existing customer."),
)

_SIDDHARTH_ONBOARDING = {
    "business_name": "ComplyFlow",
    "problem_statement":
        "Indian SMEs miss statutory HR deadlines -- PF, ESI, state filings -- "
        "because compliance is tracked in diaries and spreadsheets by one "
        "overloaded HR manager, and the penalty lands on a named person.",
    "building_summary":
        "B2B SaaS for HR compliance at Indian SMEs: statutory reminders, "
        "employee documentation, and HR workflows.",
    "industry": "SaaS",
    "current_challenges": ["Sales", "Operations"],
    "goal_90_day":
        "One full sales cycle closed by somebody who is not me, and a real "
        "churn and activation number I trust.",
    "vision_1_year":
        "One crore ARR, with most of it closing without me on the call.",
    "product_description":
        "HR compliance software for Indian SMEs -- statutory reminders, an "
        "employee document vault, PF and ESI workflows and a state-wise "
        "compliance calendar, sold per employee per month.",
}

SIDDHARTH_ANSWERS = _SIDDHARTH_TEXTS
ANSWER_BANK["siddharth_saas"] = tuple(zip(
    _TRACTION_TOPICS + _CURRENT_PROBLEM_TOPICS + _FOUNDER_TOPICS,
    _SIDDHARTH_TEXTS)) + _SIDDHARTH_EXTRA
FALLBACKS["siddharth_saas"] = ("Honestly, I do not know -- we do not track "
                               "that. I would have to go and look.")
PERSONAS["siddharth_saas"] = SIDDHARTH_ANSWERS
_ONBOARDING["siddharth_saas"] = _SIDDHARTH_ONBOARDING


if __name__ == "__main__":
    sys.exit(main())

