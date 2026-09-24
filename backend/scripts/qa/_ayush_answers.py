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

 # --- added after the first keyed run -------------------------------------
 # The bank above was written against the questions the DETERMINISTIC selector
 # serves. With the advisor on, selection changes and the industry opening
 # block pulls from the 1,800-question industry bank, so 16 of 30 questions had
 # no answer here and got the placeholder -- which the classifier read as
 # avoidance and scored red, 16 times. These cover the rest of the SaaS
 # Stage 0->1 bank and every universal question that run actually served.
 #
 # Same rule as everything above: answered as Ayush really is, not to produce
 # a finding. Several are unflattering and two are close to N/A without being
 # N/A -- nobody has cancelled because nobody pays, which is a real answer and
 # a worse one than "does not apply".

 5040: ("They have to connect at least one real data source and answer the profile questions honestly. That's maybe twenty minutes of work before anything useful comes back, and I think that is the single biggest reason pilots go quiet -- the value is real but it is not immediate.", "average"),
 5047: ("No. There is no free tier to upgrade from, and with the pilots I have never once said 'this is what it costs, do you want it'. I keep telling myself the product isn't ready for that conversation, which is probably an excuse.", "weak"),
 5048: ("Nobody has cancelled because nobody is paying. Of the nine pilot accounts, five went quiet after the first session. That is functionally the same thing and I should treat it that way.", "average"),
 5049: ("No warning at all. They just stop logging in and I find out when I happen to check. There's no usage alert, no check-in, nothing -- I notice weeks later.", "weak"),
 5050: ("Not properly. I know roughly why in my head for two of them; nothing is written down. So five pilots went quiet and I cannot tell you the pattern, which is exactly the thing I would tell a customer off for.", "weak"),
 5052: ("Not really. There's no pricing page and no written breakdown of what you get. It's whatever I say on the call, which means it changes slightly every time and nobody has anything to look at afterwards.", "weak"),
 5056: ("Never, because I have never closed a deal. Two prospects asked for a free pilot and I said yes to one, which is a hundred percent discount if you want to be honest about it.", "weak"),

 1917: ("Some are. The ones who stayed got real value out of the diagnosis and said so. But I think most of them never got far enough in to see it -- they saw the setup, not the payoff. So the value is there and the path to it is too long.", "average"),
 2282: ("The customer calls. I have told myself it's because I learn the most from them, and that is partly true, but it is also that I do not trust anyone else to handle a prospect yet. Nobody has ever had the chance to prove me wrong.", "weak"),
 2285: ("Almost nothing. There's a half-written doc for the engineering side and that's it. If I had to hand over the customer side tomorrow the person would be starting from zero with a set of Slack messages.", "weak"),
 2286: ("The diagnosis logic itself -- why a question is asked in a particular order and what it is really testing. That lives entirely in my head. If someone had to change it without me they would break it and not know.", "weak"),
 2347: ("An operations lead at a services business, forty to eighty people, who already suspects the problem is internal and not the market. That's from the pilots, not from my pitch deck -- the ones who came back were all that shape. I could not have told you that three months ago.", "strong"),
 61: ("Nine, all from outbound I did myself -- cold emails and two intros. Four came back and used it more than once. None of them pay, and I would call them interested rather than committed.", "average"),
 282: ("Honestly, not much. Nine pilots, four repeat users, a lot of people saying it is useful. That is a signal, not evidence. The claim I make in a pitch -- that this changes how they run the business -- has nothing behind it yet and I know it.", "strong"),
 1714: ("No. No accountant, no CS, no lawyer. I know that is a gap and I have been telling myself it can wait until there is revenue, which is the same logic I would challenge in a founder if they said it to me.", "weak"),
 2758: ("It lives in conversation and memory. Three people, so it has not broken yet. There is a Notion board that is half right and nobody updates it.", "weak"),
 2761: ("Because I needed someone. There was no defined role -- I was drowning on the build and brought in an engineer I already knew. It worked out, but it was a reaction, not a decision.", "average"),
 2877: ("There is no proposal. After a good call I send a follow-up email and nothing formal follows it, because I do not have a price I am confident enough to put in writing. That gap is where the interest dies.", "weak"),
 2910: ("Habit, mostly. I do outbound email and LinkedIn because that is what I know, not because I worked out where these buyers actually are. I have never tested a second channel properly.", "weak"),
 2937: ("Yes, basically. I look at the balance and my own runway and that is it. No burn rate, no cost per pilot, nothing forward-looking. There is very little to model right now, but that is how the habit starts.", "weak"),
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
