# -*- coding: utf-8 -*-
"""Ayush's answers. Authored as a founder interview, not to steer a result.

GRADE is my own note on how the answer should read to a classifier -- it is
recorded so the report can say whether the engine agreed. It is NOT sent to
the engine.

Founder reality held constant everywhere:
  working AI SaaS, outbound outreach started, early interest, NO revenue,
  no predictable acquisition, small team (3 incl. Ayush), founder does
  product + outreach + demos + ops, processes informal, no free tier,
  a handful of pilot accounts from demos.
"""

NA = "N/A"

# question_id -> (answer, my_grade)
DIAGNOSIS = {
 5038: ("We don't have open signup, it's demo then we create the account. Nine pilot accounts so far. Four came back and used it more than once, the rest logged in once and that was it. So roughly 4 out of 9, which sounds fine until you remember nine is a tiny number.", "average"),
 5057: ("No. Every demo is me. I've tried to write down what I say but it's still in my head, so right now if I'm not on the call there is no call.", "weak"),
 5039: ("I set them up myself. I create the workspace, load their context, and walk them through the first diagnosis on a call. It works but it's completely manual and it takes me about two hours a customer.", "average"),
 5053: ("Honestly I looked at what similar tools charge and picked a number that felt defensible. It isn't based on value delivered or on anything a customer told me. Nobody has paid it yet so it hasn't been tested at all.", "weak"),
 5044: (NA, "n/a"),
 5042: ("A bit, yes. I catch myself telling people we have nine accounts when what I actually have is nine conversations that went well. Zero of them pay. I know the difference, I just don't always say it out loud.", "average"),
 5041: ("Setup is me, about two hours. Where people drop is after that first session -- they get the report, say it's useful, and then nothing happens. That gap is the real problem and I haven't fixed it.", "weak"),
 5046: (NA, "n/a"),
 5051: ("Occasional, and that's a real worry. Right now it's a thing you'd run when something feels wrong, maybe once a quarter. I want it to be part of how they run the week but it isn't yet.", "average"),
 5043: ("Zero. No free tier, and nobody has paid. Pre-revenue.", "weak"),
 5054: ("No. Never tested it, never changed it. There's been nothing to test it against.", "weak"),
 5045: (NA, "n/a"),
 5055: ("I've sketched three tiers on paper but nothing is live and nobody is on any of them. So in practice, no.", "weak"),
 72: ("Two follow ups, then I usually go quiet because it feels pushy. There's no sequence and no reminder -- it's whatever I remember to do that morning. I know that's the weakest part of my outreach.", "weak"),
 226: ("Zero paid, zero committed. Several people said 'come back when you have X' and two said they'd pilot it if it were free. Interested is not committed and I'm trying not to lie to myself about that.", "weak"),
 2275: ("One of the two has, on the engineering side -- I sat with him and we wrote down how a release should go. The other one is guessing, and that's on me.", "average"),
 167: ("Probably yes, and it worries me. We're selling to businesses and enterprises are going to ask about data handling. I've read a bit but I haven't checked what's actually required. That's an assumption I'm running on.", "weak"),
 55: ("Maybe a 3. I know roughly how they find us and what makes them curious. What I genuinely don't know is who signs off and what has to be true before they'll spend money -- that part I'm guessing at.", "average"),
 2756: ("No formal training, everyone's learning on the job. There are three of us so it hasn't hurt yet, but I'm aware that's not a plan.", "average"),
 281: ("Founders usually know something's wrong but not what to fix first. Ally runs a structured diagnosis, finds the root cause underneath the symptom, and gives them the three things to do about it. I've said that sentence enough times now that it lands.", "strong"),
 343: ("Same as I said before -- I benchmarked competitors and picked a number. Not from customer conversations, not from value. It's a placeholder I've started treating as a decision.", "weak"),
 2276: ("They'd be guessing on most things. Engineering probably survives a week. Anything involving a customer stops, because all of that runs through me.", "weak"),
 356: ("Neither. No revenue at all, so not profitable and not generating revenue. We're spending my own money.", "weak"),
 441: ("Mostly in my head. There's a doc I made three months ago that's already out of date, and a Notion board that's half right. If you asked my team what the plan is you'd get two different answers.", "weak"),
 489: ("Irregularly. Two posts one week, then nothing for three. There's no calendar and no owner, it happens when I have a gap, which mostly means it doesn't.", "weak"),
 2757: ("Not in writing. We all roughly know, but nothing is written down. With three people you can get away with it -- I don't think you can at six.", "weak"),
 2277: ("Both, depending on how rushed I am. When I have time I explain the outcome and it goes well. When I'm behind I just hand over the task, and that's usually when it comes back wrong.", "average"),
 525: ("I do it myself in a spreadsheet. No accounting software, no accountant yet. There's very little to account for right now, but I know that's a bad habit to start.", "weak"),
 408: ("Data security and compliance for enterprise buyers. I know it will block a deal eventually and I haven't done anything because there's no deal close enough yet to force it. That's the honest reason -- it isn't urgent so it stays undone.", "average"),
 421: ("About six weeks ago, and it did change things. I started thinking it was for any business, and the prospect calls pushed me towards founders and small operators who don't have an analyst. I update that view as I go, it's one of the few things I do keep checking.", "strong"),
}

CURRENT_PROBLEM = {
 5: ("We can't turn interest into money. People take the demo, say it's genuinely useful, and then nothing happens. I've got a product that works and no repeatable way to get anyone to pay for it.", "n/a"),
 6: ("Me. If I stopped for two weeks every conversation with a customer would stop with me. There's no second person who can run a demo or set up an account.", "n/a"),
 7: ("My engineer wanted to ship the integrations first, I wanted to fix the onboarding. We went with mine because I pushed, not because I made a better case. He was probably half right and I haven't gone back to it.", "n/a"),
 8: ("Pricing. I know the number I picked is made up and I need to go and ask five people what they'd actually pay, and I keep finding other work instead.", "n/a"),
}

FOUNDER_DNA = {
 117: "A friend running a logistics business showed me his numbers and asked what was wrong. I could see three things but not which one mattered first -- and neither could he, and he'd been living in it for two years. That's when it stopped being an idea.",
 118: "I finish things now. Before I'd get to the interesting part of a problem and move on. I'm also worse company -- I'm half in a conversation and half thinking about the product.",
 119: "The onboarding flow. It's manual and ugly and I shipped it because a prospect had a call booked and I wanted something real in front of them. It's still manual four months later.",
 120: "A prospect finished the diagnosis and said 'nobody has ever asked me that question'. That one landed because it wasn't about the product working, it was about the thing actually being useful.",
 121: "About three weeks ago. I shut down -- told myself I was thinking, spent two days reading things that didn't matter and shipped nothing. I don't reach out, that's a pattern I'm aware of and haven't fixed.",
 122: "It's changed. It started as 'founders deserve better advice than a generic blog post'. Now it's narrower -- most founders can see the symptom and not the cause, and that gap is expensive. The narrower version is truer.",
 123: "Number of businesses that run a second diagnosis without me asking them to. Everything else I can talk myself into.",
 124: "An enterprise prospect wanted us to white-label it and take our name off. It was the closest thing to money we'd seen. I said no, and I'm still not completely sure that was the right call.",
 125: "Two weeks in July when I stopped taking calls and just built. No meetings, one problem, shipped the whole diagnosis engine rewrite. What made it work was that nobody needed anything from me.",
 126: "Figuring it out as I go, mostly. I set a direction for the quarter and then react for twelve weeks. I'd like to say it's deliberate but it's closer to drift with good intentions.",
 127: "Last month, when two prospects went quiet the same week. I kept working but I wasn't really working -- refreshing email, redoing slides. I didn't tell anyone, which made it longer than it needed to be.",
 128: "That building more doesn't fix a selling problem. I spent six weeks adding features because it was easier than making calls, and at the end of it I had a better product and the same zero customers.",
 129: "Straight. Tell me the thing, I'll ask questions after. Step by step feels like being managed.",
 130: "Yesterday. I was writing the follow-up sequence I keep saying I'll write, a prospect messaged, and I spent the afternoon on that instead. The sequence still doesn't exist.",
 161: "Pushing to move, usually. With three people and no revenue I think slow is the bigger risk. But I notice I use that as a reason not to think carefully, which isn't the same thing.",
 132: "I personally run every demo and set up every account by hand, two hours each. It doesn't scale at all. I'm doing it because it's the only way I learn what actually confuses people, and I'm not ready to give that up yet.",
 133: "The report layout. I spent nine days on typography and spacing for a report that eleven people had seen. It delayed the follow-up work by about two weeks and none of those eleven mentioned the layout.",
 131: "That I'm not sure I'm the right person to sell this. I can build it and I can explain it, but the part where you ask someone for money -- I avoid it, and I haven't said that to anyone.",
}

# ---------------------------------------------------------------------------
# ADDED after the first keyed run. The adaptive selector picks questions the
# original thirty were not written against: twenty of thirty-six served
# questions fell through to the GENERIC placeholder, the classifier read those
# non-answers as Red, and Founder Readiness and Revenue Maturity scored a flat
# zero on answers Ayush never gave.
#
# These are the ids that were missed, answered in the same voice and held to
# the same founder reality: working AI SaaS, outbound started, early interest,
# NO revenue, no free tier, nine pilot accounts from demos, team of three,
# founder does product + outreach + demos + ops, processes informal.
#
# Nothing above this line was edited. Grades are my own note, never sent to the
# engine.
# ---------------------------------------------------------------------------
DIAGNOSIS.update({
 5047: ("There is no free tier, so there is nobody to ask. The nine pilot accounts were set up by me after a demo, and I have asked four of them what it would take to start paying. Two said they need a couple of things built first, two went quiet.", "average"),
 5040: ("They have to give us enough context about their business for the diagnosis to be worth anything -- that is the honest blocker. If they skip it the report reads generic and they never come back. I do it with them on the call now, which works and does not scale.", "average"),
 5052: ("Not really. They see the report and it is genuinely useful, but I have never put the value in money terms -- what the wrong decision costs them, what finding it earlier is worth. That gap is probably why nobody has paid yet.", "weak"),
 1917: ("I think they understand the diagnosis part and not the rest. Four of nine came back and used it again, which tells me something landed, but I have never asked the five who did not why. I should have.", "weak"),
 2282: ("The demo. I have never handed one over because I do not trust that anyone else can read what a founder is actually worried about in the first five minutes. That may be true or it may be me not having written down how I do it.", "weak"),
 1714: ("No. No accountant, no company secretary, nobody. I file what I have to and I am fairly sure there are obligations I do not know about. It is on the list and has been for months.", "weak"),
 61: ("Nine pilot accounts, all from outbound I sent personally. No inbound, no referrals, no repeatable source. Every single one traces back to a message I wrote myself, which is the problem.", "average"),
 2758: ("It lives in conversation and in my head. Three of us talk every day so it works at this size, and it is already starting not to -- things I assumed someone owned turn out to be nobody's.", "weak"),
 282: ("Honestly, thin. I can show that nine founders took a demo and four came back. Everything else I say about the market is my own conviction, not evidence. I catch myself stating it as though it were proven.", "average"),
 2285: ("No. If I had to hand off the outreach or the demos tomorrow there is nothing written down -- no script, no objection list, no account notes worth the name. It would be starting over.", "weak"),
 2877: ("Two or three days, usually, because I write each one from scratch. It is too slow and I know a faster follow-up would probably have converted at least one of the conversations that went quiet.", "weak"),
 2910: ("Because it is the one I know. Outbound email is what I have always done, so that is what we do. I have not tested anything else, so I cannot tell you whether it is the right channel or just the familiar one.", "weak"),
 2761: ("We have not made a hire. The three of us came together around the idea, so there has been no hiring process and no defined role to fill. Any hiring is on the other side of having revenue.", "n/a"),
 2286: ("Reading a founder on a demo call and turning that into the right first diagnosis. Nobody else here could pick that up without me explaining it live, and I have not written any of it down.", "weak"),
 2937: ("Pretty much, yes. I look at what is in the account and whether it is going down. There is no model, no forecast, no accounting software -- a spreadsheet and my own sense of it.", "weak"),
 2347: ("N/A -- we have no customers, so I cannot describe a best one from experience. The prospects who engage most are small software businesses where the founder is still close to the operation. That is a pattern from conversations, not from anyone who has paid.", "n/a"),
})

# ---------------------------------------------------------------------------
# Batch 4 added 18 SaaS questions at Stage 0→1, and twelve of them land in the
# industry opening block -- so without answers the harness substitutes filler
# for most of the run and the generic-answer guard (correctly) fails it.
#
# Written to the same founder reality held constant at the top of this file:
# working AI SaaS, outbound started, early interest, NO revenue, team of three,
# founder does product + outreach + demos + ops, nine pilot accounts.
# Not tuned to produce a finding. A pre-revenue solo-selling founder answers
# the revenue and delegation questions badly because that is the truth of the
# situation, not because I wanted a particular root cause to rank.
#
# Spread of the 18: weak 8, average 7, strong 2, n/a 1.
#
# NOTE ON THE IDS. This bank is keyed by question_id, which is assigned by the
# sequence and therefore differs between databases. The question_code in each
# comment is stable, so these can be re-derived anywhere with:
#   select question_id, question_code from questions where question_code like 'S01-SAS-3%';
# Keying the bank by code instead of id would remove the problem entirely; that
# is a harness change, not an answers change, so it is not made here.
# ---------------------------------------------------------------------------
DIAGNOSIS.update({
 # S01-SAS-301-1
 6384: ("Eleven calls last month. Seven were demos off outbound, four were intros someone passed me. Two asked for pricing afterwards and neither came back. So eleven calls, zero closes, and I can name every one of them -- which tells you how small the number is.", "average"),
 # S01-SAS-301-2
 6385: ("Sometimes. The ones who say it outright I remember -- 'not now', 'we'd need it to talk to our data'. But I don't write them down anywhere, so I'm going on the ones that stuck in my head rather than the actual pattern. I suspect the real reason is the same every time and I couldn't prove it.", "weak"),
 # S01-SAS-302-1
 6390: ("Maybe nine or ten hours, because every demo and every setup is me. That part I'm genuinely not short of. What I'm short of is talking to people who aren't already interested.", "average"),
 # S01-SAS-302-2
 6391: ("Deployments and the smaller bug fixes. One of the engineers could do both -- he's done deploys with me sitting there. I keep doing it because it takes me fifteen minutes and explaining it takes an hour, which I know is exactly the wrong reason.", "average"),
 # S01-SAS-303-1
 6396: ("Engineering keeps going, they've got work queued. But nothing ships, because I'm the one who decides what goes in a release, and nothing customer-facing happens at all. I was away four days in August and the honest answer is the company paused.", "weak"),
 # S01-SAS-303-2
 6397: ("One of the two engineers can, and has. The steps aren't written down though -- he learned it by watching me, so if he's out too then it's just me again.", "average"),
 # S01-SAS-304-1
 6402: ("Nobody has left because nobody is paying. But five of the nine pilots went quiet and no, I didn't see any of them coming. Each one I only noticed weeks later when I went looking. If those had been paying customers I'd have lost them the same way.", "weak"),
 # S01-SAS-304-2
 6403: ("There's no definition. I do about two hours with them -- workspace, load their context, run the first diagnosis -- and then I decide in my head that they're set up. Nothing is written, nothing is checked, and it's different every time depending on how the call went.", "weak"),
 # S01-SAS-305-1
 6408: (NA, "n/a"),
 # S01-SAS-305-2
 6409: ("They get an answer on the call, because I'm the one on the call and I'm the one who sets the price. That's the one upside of everything running through me. It won't hold the moment anyone else is selling.", "average"),
 # S01-SAS-306-1
 6414: ("No. Both of them came through people I know and I hired them off conversations and a look at previous work. No test, nothing the same across both. It's worked out so far, which I think is luck rather than judgement.", "weak"),
 # S01-SAS-306-2
 6415: ("Sales. Neither of them sells and neither do I, properly -- I demo, which isn't the same thing. We also have nobody who has run a product against enterprise buyers, and that's who we say we're for. Those two gaps are the same gap really.", "strong"),
 # S01-SAS-307-1
 6420: ("Two came from pilot accounts -- one wanted their own data in it, one wanted a shareable report. The third I decided myself. So mostly whoever asked most recently, which isn't a process.", "average"),
 # S01-SAS-307-2
 6421: ("That's the uncomfortable one. Two solo founders, a small dev agency, and one team inside a large company. They want completely different things and I've been building for all three because each one was a real person asking. Written down like that it's obviously a problem.", "weak"),
 # S01-SAS-308-1
 6426: ("One. An agency wanted us to white-label the report with their branding and I said no, because it would have made us their tool rather than a product. I was fairly sure at the time and I'm still comfortable with it.", "average"),
 # S01-SAS-308-2
 6427: ("Whoever asked last, mostly, plus whatever I think will help the next demo. There's a list but it isn't in any order, so in practice the most recent conversation wins. I don't have a rule I could write down.", "weak"),
 # S01-SAS-309-1
 6432: ("Manual onboarding. I told myself after the third pilot that I'd write the setup down before the next one, and then I did the next six by hand exactly the same way. Same mistake, six more times, and each time I had the reason ready.", "strong"),
 # S01-SAS-309-2
 6433: ("Nowhere. It's in my head and some of it is in WhatsApp. If I stopped tomorrow nobody could tell you why any of those five pilots went quiet.", "weak"),
})
