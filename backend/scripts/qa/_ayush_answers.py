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
