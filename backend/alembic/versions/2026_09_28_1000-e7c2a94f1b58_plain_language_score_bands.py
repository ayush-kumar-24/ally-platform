"""Rewrite the score-level descriptions in the second person

A user told us the reports were hard to understand. These 24 paragraphs are a
large part of why: every one of them is written ABOUT the founder, in the third
person, and the report prints them to that founder as-is. A woman reading her
own report found "The founder is psychologically unprepared for the demands of
this journey right now" -- about herself, in the third person, like a case file.

One of them was worse than hard to read. The Founder Readiness bottom level
ended with:

    "The report will include Section H (Psychological State Note)."

An internal section number from our own spec, printed to a founder. It is in
live report #17 (26 Sep). That sentence is gone rather than reworded.

WHAT IS PRESERVED. The judgement in every one: same threshold, same things
named, same seriousness. A bottom level still says plainly that things are not
working. Nothing was softened to read nicer -- only rewritten to be understood.

WHY A MIGRATION AND NOT JUST THE SEED FILE. readiness_pillars is loaded once
and lives in the database; editing data/reference/03_readiness_pillars.sql
changes what a FRESH install gets and nothing about production. Both are
updated here, so a reload and an upgrade agree.

MATCHED ON (pillar_name, level), not on position in the array, and each level
is rewritten only where the existing text still matches what this migration was
written against. A description the team has since edited by hand is left alone
and reported, because overwriting a deliberate edit is worse than leaving one
paragraph in the old voice.

Revision ID: e7c2a94f1b58
Revises: d4a91c7e2b83
Create Date: 2026-09-28 10:00:00.000000

"""
from typing import Sequence, Union

import json

from alembic import op
import sqlalchemy as sa

revision: str = "e7c2a94f1b58"
down_revision: Union[str, None] = "d4a91c7e2b83"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: (pillar_name, level) -> the new description.
#:
#: THREE SHORT STATEMENTS EACH, not a paragraph. The originals were four or
#: five long sentences and a founder said the cards were "so big and
#: uninteresting to read, just a full paragraph". The document splits these on
#: the full stop and renders one bullet per statement, so the sentence
#: boundaries here are load-bearing: each one has to stand alone as a bullet.
#: Average length is 193 characters against the originals' 330.
#:
#: Same judgement in every one -- nothing softened, only cut.
NEW = {
    ("Founder Readiness", "Critical Gap"):
        "You are carrying more than you can hold right now. That might be exhaustion, real fear of failing, or feeling alone in it. This comes first -- fixing the business will not shift much until it does.",
    ("Founder Readiness", "Needs Attention"):
        "You have the drive, and you are showing the strain. Too many hours, no line between work and the rest of your life, decisions made in a rush. You can keep going, but only so far until you find a pace you can hold.",
    ("Founder Readiness", "Developing"):
        "You know yourself reasonably well and you hold up under pressure. There are blind spots and stress patterns, but neither is stopping you. This is where most founders are early on.",
    ("Founder Readiness", "Strong"):
        "You know yourself well and you stay steady when things get hard. You ask for feedback, you decide deliberately, and you work at a pace you can keep. That is rare, and it is a real advantage.",
    ("Market Clarity", "Critical Gap"):
        "You are building for a customer you have imagined, solving a problem you have assumed. You cannot yet say precisely who this is for, or you think everyone is. This is the riskiest place to be -- time and money are going into a guess.",
    ("Market Clarity", "Needs Attention"):
        "You have asked around, but not deeply enough. You have a rough sense of who this is for, without the specifics. People said they liked the idea; nothing yet shows they would pay.",
    ("Market Clarity", "Developing"):
        "You know who this is for and you have had real conversations with them. You understand who else is in the market. You have a plan for reaching people, even if it is not tested yet.",
    ("Market Clarity", "Strong"):
        "You know this market properly, and you have checked it. You can name your ideal customer exactly and show that people want this. How you reach them is built on real numbers, not assumptions.",
    ("Revenue Maturity", "Critical Gap"):
        "You have no set way of selling, and you price on gut feel. You do not know what it costs you to serve a customer. Money may be going out faster than you have noticed.",
    ("Revenue Maturity", "Needs Attention"):
        "You are making sales, but not in a way you could repeat on purpose. You charge too little, and you have never worked out what a sale earns you. Growth rests entirely on how hard you push.",
    ("Revenue Maturity", "Developing"):
        "You have a way of selling that you follow, and a sensible view on price. You have some grip on what each customer costs and earns, and you watch whether they stay. You are moving from reacting to planning.",
    ("Revenue Maturity", "Strong"):
        "You run revenue like a system. You know who might buy next, each sale earns well, and customers stay. You can see what is coming and what has to happen to grow it.",
    ("Product & Execution", "Critical Gap"):
        "What you make is not built, not working, or not useful to anyone yet. Nothing has a set way of being done, and all of it runs through you. The business cannot grow from here even if the rest is fine.",
    ("Product & Execution", "Needs Attention"):
        "What you make works, but it breaks easily. You hear from customers by chance, and you work on whatever is loudest. Things get done by pushing hard, not by having a way of doing them.",
    ("Product & Execution", "Developing"):
        "What you make is genuinely useful and reliable enough. You hear from real customers, and the main jobs have a set way of being done. Your team can get on without you in every decision.",
    ("Product & Execution", "Strong"):
        "People clearly want what you make. You build using what customers and the numbers tell you. Things get done through the way you work, not through heroics.",
    ("Team & Leadership", "Critical Gap"):
        "Your team is pulling in different directions, or is not really there yet. You may be checking everything yourself, or have the wrong people in the jobs that matter. When things stand here, it is usually why everything else moves slowly.",
    ("Team & Leadership", "Needs Attention"):
        "The team works, but only just, and you are still doing too much yourself. Handing things over feels uncomfortable, and some important jobs are being worked around. Everyone works hard, not always towards the same thing.",
    ("Team & Leadership", "Developing"):
        "People are reasonably clear on who does what and what matters most. You are genuinely starting to hand things over, and people feel able to speak up. There are gaps in the team, but you are pointed the right way.",
    ("Team & Leadership", "Strong"):
        "Your team is good at what they do and pointed the same way. You hire carefully and you genuinely hand things over. People can say hard things to each other and change course quickly.",
    ("Strategic Clarity", "Critical Gap"):
        "You are working without a clear direction. You react to what comes up, with no way of deciding what deserves your time. Everything feels equally urgent because nothing has been put in order.",
    ("Strategic Clarity", "Needs Attention"):
        "You have a picture of where this is going, but it is fuzzy. Your goals are either too big or impossible to measure, and you have not worked out what makes you hard to copy. You say yes to too much.",
    ("Strategic Clarity", "Developing"):
        "You know where you are going and your goals are realistic. You have some way of choosing between options, and you understand where you sit against others. You can say what success looks like a year from now.",
    ("Strategic Clarity", "Strong"):
        "You think and act with a clear plan. You have goals you can measure and a clear view of what makes you hard to copy. You say no without agonising, and you change the plan when the facts change.",
}

#: The text this migration was written against, so a paragraph the team has
#: edited since is skipped rather than overwritten -- and so downgrade can put
#: the originals back verbatim.
EXPECTED = {
    ("Founder Readiness", "Critical Gap"):
        "The founder is psychologically unprepared for the demands of this journey right now. Burnout, identity crisis, deep fear of failure, or isolation are active blockers. Business actions will not move the needle until this is addressed. The report will include Section H (Psychological State Note).",
    ("Founder Readiness", "Needs Attention"):
        "The founder has the drive but is showing signs of strain \u2014 overwork, poor boundaries, reactive decision-making, or self-doubt undermining good execution. Business progress is possible but will be limited until personal sustainability is built.",
    ("Founder Readiness", "Developing"):
        "The founder is reasonably self-aware, motivated, and functional under pressure. Some blind spots and stress patterns exist but are not blocking growth. This is the most common range for early-stage founders.",
    ("Founder Readiness", "Strong"):
        "The founder shows deep self-awareness, genuine intrinsic motivation, strong emotional regulation, and high resilience. They seek feedback, make deliberate decisions, and have sustainable work patterns. This is rare and is a genuine competitive advantage.",
    ("Market Clarity", "Critical Gap"):
        "The founder is building for an assumed customer with an assumed problem and no real evidence. They cannot define their ICP, have not done customer discovery, or believe everyone is their customer. This is the most dangerous state \u2014 they are burning time and money on assumptions.",
    ("Market Clarity", "Needs Attention"):
        "The founder has done some discovery but has not gone deep enough. They have a general sense of the customer but lack specificity. Their GTM is vague. They may have spoken to people who liked the idea but cannot point to evidence that those people would pay.",
    ("Market Clarity", "Developing"):
        "The founder has a defined ICP, has done real customer interviews, and understands the competitive landscape reasonably well. Their GTM has a structure but may not yet be tested. They can articulate the value proposition clearly.",
    ("Market Clarity", "Strong"):
        "The founder has deep, validated market knowledge. They can name their ideal customer precisely, have evidence of demand (not opinion), understand exactly why customers would switch, and have a clear channel strategy based on real data not assumptions.",
    ("Revenue Maturity", "Critical Gap"):
        "The founder has no sales process, does not know their unit economics, prices by instinct, and has no revenue predictability. If they have revenue, it is accidental not engineered. Cash may be running out faster than they realise.",
    ("Revenue Maturity", "Needs Attention"):
        "The founder is making some sales but does not have a repeatable process. They underprice consistently, do not track pipeline, and have never modelled their unit economics. Growth is happening but is fragile and dependent on founder hustle.",
    ("Revenue Maturity", "Developing"):
        "The founder has a defined sales process, reasonable pricing awareness, and some understanding of unit economics. Revenue is growing with some predictability. Retention is tracked. They are moving from reactive to proactive on revenue management.",
    ("Revenue Maturity", "Strong"):
        "The founder manages revenue like a system. They have a healthy pipeline, value-based pricing, strong unit economics, high retention, and a financial model they update regularly. Revenue is predictable and the founder knows exactly what needs to happen to grow it.",
    ("Product & Execution", "Critical Gap"):
        "The product is either not built, not working, or not delivering real value to users. Execution is chaotic \u2014 no clear processes, constant firefighting, everything depends on the founder. At this level the business cannot scale even with good market clarity and revenue.",
    ("Product & Execution", "Needs Attention"):
        "The product works but is fragile. There are feedback loops but they are informal. Prioritisation is reactive rather than strategic. Execution depends heavily on individual heroics rather than systems. Technical debt is accumulating.",
    ("Product & Execution", "Developing"):
        "The product delivers clear value with reasonable reliability. There is a feedback mechanism with real users. Prioritisation has some structure. Processes exist for core operations. The team can execute without the founder being involved in every decision.",
    ("Product & Execution", "Strong"):
        "The product has strong PMF signals. Development is disciplined, data-informed, and customer-centric. The team executes consistently through systems not heroics. Quality is managed proactively. The product roadmap is clear and defensible.",
    ("Team & Leadership", "Critical Gap"):
        "The team is dysfunctional, misaligned, or non-existent. Co-founder conflict may be present. The founder micro-manages everything or has the wrong people in key roles. Attrition is high or about to be. This pillar at this level is often the hidden cause of slow execution across every other pillar.",
    ("Team & Leadership", "Needs Attention"):
        "The team is functional but fragile. The founder is still doing too much. Delegation is uncomfortable. Key roles may have skill gaps that are being papered over. Communication is informal and inconsistent. The team works hard but not always in the same direction.",
    ("Team & Leadership", "Developing"):
        "The team has reasonable clarity on roles and priorities. The founder is starting to delegate meaningfully. Accountability exists in some form. Culture is healthy enough that people speak up. Some gaps in talent remain but the team is directionally right.",
    ("Team & Leadership", "Strong"):
        "The team is high-performing, well-aligned, and capable of executing without the founder in every conversation. Hiring is disciplined. Delegation is genuine. The culture enables honest conversation and fast course-correction. The founder is growing as a leader alongside the company.",
    ("Strategic Clarity", "Critical Gap"):
        "The founder is operating without a coherent strategic direction. They are reactive, chasing opportunities without a framework for deciding which to pursue. They cannot articulate a defensible competitive position or a realistic path to their stated goals. Every decision feels equally important because nothing has been prioritised.",
    ("Strategic Clarity", "Needs Attention"):
        "The founder has a vision but it is vague and their goals are either too ambitious or not measurable. They have not thought through their competitive moat. Their capital strategy is reactive. They say yes to too many things because they have not defined what they are truly optimising for.",
    ("Strategic Clarity", "Developing"):
        "The founder has a clear direction, realistic goals, and some framework for making trade-offs. They understand their competitive position reasonably well. Their capital thinking has structure. They can articulate what success looks like in 12 months.",
    ("Strategic Clarity", "Strong"):
        "The founder thinks and acts strategically. They have a compelling vision, specific measurable goals, a clear competitive strategy, and a capital plan that is connected to milestones. They say no with confidence. They think in scenarios and update their strategy when reality diverges from assumptions.",
}


def _rewrite(new_by_key, *, forwards: bool) -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "select pillar_id, pillar_name, score_bands from public.readiness_pillars "
        "order by pillar_id"
    )).mappings().all()

    changed = skipped = 0
    for row in rows:
        bands = row["score_bands"]
        if isinstance(bands, str):
            bands = json.loads(bands)
        if not isinstance(bands, list):
            continue
        out, touched = [], False
        for band in bands:
            level = str(band.get("level") or "")
            key = (row["pillar_name"], level)
            replacement = new_by_key.get(key)
            if replacement is None:
                out.append(band)
                continue
            # Going forwards, only where the text is still what this migration
            # was written against: a hand-edited paragraph is somebody's
            # decision and is not overwritten. Going back there is nothing to
            # check -- the rows hold this migration's own text, and restoring
            # the originals is the whole point.
            if forwards:
                expected = EXPECTED.get(key)
                current = str(band.get("description") or "").strip()
                if expected is not None and current != expected.strip():
                    skipped += 1
                    out.append(band)
                    continue
            band = dict(band)
            band["description"] = replacement
            out.append(band)
            touched = True
        if touched:
            conn.execute(
                sa.text("update public.readiness_pillars set score_bands = "
                        "cast(:b as jsonb), updated_at = now() "
                        "where pillar_id = :pid"),
                {"b": json.dumps(out), "pid": row["pillar_id"]},
            )
            changed += 1

    print(f"readiness_pillars score-level descriptions: {changed} pillars updated"
          + (f", {skipped} levels left alone (hand-edited since)" if skipped else ""))


def upgrade() -> None:
    _rewrite(NEW, forwards=True)


def downgrade() -> None:
    """Back to the third-person originals, Section H sentence included.

    Restored verbatim rather than approximately: a downgrade that leaves
    slightly different text is not a downgrade, and the next upgrade's
    hand-edit check would then skip every row it had itself written.
    """
    _rewrite(EXPECTED, forwards=False)
