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
      "anyone else told", "problem is real", "actually uses it"),
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
      "actually do today", "moves you toward"),
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
    (("pricing", "what we charge", "charge for", "financial", "revenue",
      "clean boundary", "money move"),
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
      "under pressure", "completely drained"),
     ("decide", "unknown", "stress", "drained")),
    # feedback, criticism, blind spots
    (("feedback", "criticis", "blind spot", "pointed out", "dismisses your",
      "told to you straight"),
     ("harsh", "difficult")),
    # motivation, purpose, vision
    (("why does", "deserve", "thriving", "vision", "grabbed you",
      "origin story", "opening line", "advice right now"),
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
      "need that much time", "didn't need"),
     ("waste", "looking back")),
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

assert len(_WEAK_TEXTS) == len(_STRONG_TEXTS) == len(_TOPICS)

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
}

ANSWER_BANK = {
    "weak": tuple(zip(_TOPICS, _WEAK_TEXTS)),
    "strong": tuple(zip(_TOPICS, _STRONG_TEXTS)),
}

#: The texts alone, in topic order -- the index-based fallback when no
#: question text is available, and what anything importing these expects.
WEAK_ANSWERS = _WEAK_TEXTS
STRONG_ANSWERS = _STRONG_TEXTS

PERSONAS = {"weak": WEAK_ANSWERS, "strong": STRONG_ANSWERS}


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

    `row` is (questions_answered_count, routing_state, overall_confidence_score);
    None when no session was found.
    """
    if row is None:
        return "  session                 not found"
    answered, state, confidence = row[0], row[1], row[2]
    meaning = _ROUTING_MEANING.get(state or "", "")
    conf = "?" if confidence is None else f"{float(confidence):.0f}"
    tail = f"   ({meaning})" if meaning else ""
    return (f"  stopped after           {answered} answers -- "
            f"routing_state {state!r} at confidence {conf}{tail}")


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


def _llm_calls(db, sa) -> tuple[int, float]:
    """(calls, cost so far). Zero rows after a run means the model never ran."""
    try:
        row = db.execute(sa.text(
            "select count(*), coalesce(sum(estimated_cost_usd), 0) from llm_call_log"
        )).one()
        return int(row[0]), float(row[1])
    except Exception:                                            # noqa: BLE001
        db.rollback()
        return -1, 0.0


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


def _seed_founder(db, sa, stage_order: int) -> tuple[int, str]:
    """A brand-new synthetic founder with a random user_id.

    Only works where founders.user_id carries no FK to auth.users -- see the
    module docstring. Raises IntegrityError with a clear message, rather than
    a bare traceback, when that FK exists and rejects the fabricated id.
    """
    email = f"e2e+{int(time.time())}@{TEST_DOMAIN}"
    try:
        fid = db.execute(sa.text("""
            insert into founders (user_id, email, full_name, stage_id, profile_completed,
                                  experience_level, problem_statement, building_summary,
                                  business_name, industry, customer_segment,
                                  current_challenges, goal_90_day, vision_1_year,
                                  founder_reality_signals, invisible_gaps)
            values (gen_random_uuid(), :e, 'E2E Test Founder', :s, true,
                    'one_company',
                    'Customers churn after the second month and I cannot tell why.',
                    'Compliance SaaS for Indian SMBs.',
                    'Acme Compliance', 'SaaS',
                    '["Business"]'::jsonb, '["Sales","Cash flow"]'::jsonb,
                    'Ten real customer interviews.', 'Series A raised.',
                    '{"clear_next_step": true}'::jsonb, '["pricing"]'::jsonb)
            returning founder_id"""), {"e": email, "s": stage_order}).scalar_one()
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


def _walk(client, start_path, answer_path, id_field, label, out, persona="weak"):
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
        answer, matched = match_answer(q.get("question_text", ""), persona)
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
        calls_before, cost_before = _llm_calls(db, sa)
        if using_existing:
            fid, label = _resolve_existing_founder(
                db, sa, email=args.founder_email, founder_id=args.founder_id)
            print(f"\n  existing founder {fid} ({label}) (unchanged: not created "
                  "by this script)")
        else:
            fid, label = _seed_founder(db, sa, args.stage)
            print(f"\n  test founder {fid} <{label}> at stage_order {args.stage}")

    from fastapi import Depends
    from sqlalchemy.orm import Session as OrmSession

    def _founder(db: OrmSession = Depends(get_db)):
        return db.get(Founder, fid)

    app.dependency_overrides[get_founder_record] = _founder
    client = TestClient(app)

    dna, problem, diagnosis = [], [], []
    print("\n" + "=" * 74)
    print("JOURNEY")
    print("=" * 74)
    ok = (
        _walk(client, "/api/v1/founder-dna/start", "/api/v1/founder-dna/answer",
              "founder_dna_question_id", "Founder DNA", dna, args.persona)
        and _walk(client, "/api/v1/current-problem/start",
                  "/api/v1/current-problem/answer",
                  "current_problem_question_id", "Current Problem", problem,
                  args.persona)
        and _walk(client, "/api/v1/diagnosis/start", "/api/v1/diagnosis/answer",
                  "question_id", "Diagnosis", diagnosis, args.persona)
    )
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
        calls_after, cost_after = _llm_calls(db, sa)

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
    for line in band_summary(rows, fallback_qids):
        print(line)
    with SessionLocal() as db:
        print(stop_reason(db.execute(sa.text(
            "select questions_answered_count, routing_state, "
            "overall_confidence_score from sessions where founder_id=:f "
            "order by session_id desc limit 1"), {"f": fid}).first()))

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

    if calls_before >= 0:
        made = calls_after - calls_before
        print(f"  model calls this run    {made}"
              f"   (cost ${cost_after - cost_before:.4f})")
        if made == 0:
            print("    ^ ZERO. Nothing reached a model. Either scoring is off, or "
                  "the provider failed and the failover chain fell through to "
                  "MockLLMProvider -- check the logs for an auth error.")
    else:
        print("  model calls this run    (llm_call_log unavailable)")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump({"generated_at": datetime.now(timezone.utc).isoformat(),
                       "stage_order": args.stage, "founder_id": fid,
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
                        "answers, whatever the band says.")
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


if __name__ == "__main__":
    sys.exit(main())
