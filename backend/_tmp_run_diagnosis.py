# -*- coding: utf-8 -*-
"""Drives a full diagnosis end-to-end via the real HTTP API, answering in
character as Priya Nair (Stage 0, aunt's diagnostics lab in Kochi) with the
same answers given manually, so the run is comparable to the manual one."""
import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import httpx

BASE = "http://127.0.0.1:8000/api/v1"
DEV = "7a70613d-6fb9-58a0-8642-a85fdaa135f4"

BANK = [
 (["being first", "being the best", "being trusted"],
  "Being trusted. Not first - someone bigger will build a slicker version eventually. Not the best either, because best usually means most features and that decides nothing in a small lab in Kerala. What I want is a lab owner recommending us to another lab owner without me asking. If we are first or flashiest but nobody vouches for us, we have built nothing."),
 (["one breath", "explain this idea"],
  "Small diagnostic labs spend more time explaining results than producing them - my aunt spends twenty minutes per patient translating a report into plain Malayalam - so we are building the thing that does that explaining automatically, so the lab can hand someone a report they actually understand without a person decoding it every time."),
 (["active users", "currently have"],
  "Zero paying customers. One lab actually using it - my aunt's, in Kochi - and that is not a real customer, it is family letting me test. Her lab runs 30-40 tests a day and we have put roughly 200 reports through the translation flow over six weeks. I have eleven labs on a list I pulled off Google Maps and have contacted none of them."),
 (["industry or startup experience", "forming a team", "co-founder", "cofounder"],
  "There is no team. It is me, solo. My background is operations at a mid-size fintech in Bangalore for four years - not healthcare, not engineering. I have never built a product for people outside my own company and never worked in diagnostics. My aunt has twenty years in that lab but she is not a cofounder, she is family who corrects me. This is my first startup. Never raised money, never hired anyone, never shipped something a stranger paid for."),
 (["seriously hurt this business", "listed out everything"],
  "No - properly no, not sort of. I have worried constantly, usually at 2am, but worrying is not listing. I have never written the failure modes down. If you asked me now I would say the money running out because that is the one with a date on it, but that is the symptom. The real ones are quieter: this only works because my aunt is family, I have no technical cofounder, and a hospital chain could bundle this free. I know all three and have never written them down."),
 (["key partners", "key resources"],
  "Two, and both uncomfortable. My aunt's lab - my only distribution, only testing ground, only source of domain knowledge. And whoever's model does the translation; the plain-language output is the entire product and I am calling an API I do not own. A third I should count: the labs existing report software, mostly old Windows systems that vary lab to lab, and I have only integrated with my aunt's."),
 (["outside your personal network"],
  "Zero. Not a few - actually zero. My aunt, two of her lab techs, one friend in health-tech VC, my sister. All people who either love me or already know me. The eleven labs on my list, not one contacted; the message is still in drafts. Everything I believe about what labs need came from one lab run by my father's sister, who would be encouraging about a bad idea too."),
 (["6 or 12 months", "written down about where"],
  "Not really. There is a Google Doc from when I quit, written in one sitting, saying Malayalam live by month 3, Tamil by month 6, 10 paying labs by month 9. I have not opened it since week two. Month 3 has passed and Malayalam is not live to anyone but my aunt. The only thing I track is runway - four months - and that lives in my head."),
 (["harsh feedback", "rejection"],
  "My friend in health-tech VC six weeks ago: this is a feature, not a company, some hospital chain will bundle it free. Officially it stayed a weekend; actually it is still here. I ran runway numbers, half-drafted a message to my old manager. My aunt said the hospital chains are not coming to her lab, and that let me put it down. But I never answered him - I found a reason his point did not apply. And since then I have been building instead of calling labs. Six weeks of that."),
 (["nobody else would care"],
  "Yes, and I have treated that as a virtue when it is an excuse. My aunt cares about patients but not whether this company exists. So yes, if I stop, it stops. But that belief is why I have not looked for a cofounder or hired anyone - as long as it is true I never have to hand anything over or be told I am wrong by someone I cannot dismiss as family being kind."),
 (["one single page", "entire business model"],
  "No, never. Costs roughly in my head, pricing in a WhatsApp message where I floated 3000 rupees a month and my aunt said maybe less, channels nowhere. The moment those five things are on one page you can do the arithmetic - eleven labs at 3000 is 33000 a month, which does not pay me let alone an engineer. Same pattern as the risk list: not written down, and not written down for a reason."),
 (["currently use", "instead of your product"],
  "They use a person. The alternative is my aunt standing there twenty minutes explaining in Malayalam - unpaid labour by whoever is at the desk. Below that: the patient asks their referring doctor, costing another visit, or Googles their values and frightens themselves, or most commonly does not understand and quietly does not follow up. No software competitor; their report software prints a PDF with reference ranges and that is the end of its ambition."),
 (["after it actually caused", "only realized was a risk"],
  "That my aunt's lab is not a normal lab, and I built everything around it as though it were. It felt like an advantage. Then three weeks ago I visited a lab in Ernakulam and their front desk had fifteen people queued and one woman handling all of it. There is no twenty-minute explanation there and nobody expects it. So the problem I built around is not one they have. My aunt is unusually conscientious and I mistook that for a market need. And I still have not changed anything - I felt unsettled for an evening and went back to polishing the Malayalam output."),
 (["how urgent or common", "personally experience"],
  "No, and you have named what I got wrong. I assumed it because I watched it happen repeatedly in one lab, and seeing something yourself feels like evidence. Then I stood in that Ernakulam lab and saw the opposite. I generalised from a sample of one because that sample was vivid and run by someone I trust. I still do not know the real answer because eleven labs sit in a list I have not called."),
 (["deserve your next few years", "deserve"],
  "Because I have watched what happens when nobody fixes it - people quietly giving up on care they actually needed, not from lack of medicine but from lack of someone willing to explain it to them."),
 (["circles where credible"],
  "Honestly no. I worked four years at a fintech so on paper I know engineers, but they are people I sat near, not built with, and none are in health or diagnostics. Since moving back to Kochi I have been in zero founder circles - no meetups, no accelerator, no community. My network here is my aunt, her staff, and school friends in unrelated fields. It is easy to believe there is nobody out there when you have not looked."),
 (["napkin"],
  "Parts of it fast, the whole thing no. The left side takes ninety seconds - small labs in Kerala, patient walks in confused, report goes out in plain Malayalam. Where the pen stops is the right side: price, which I floated once and never revisited; who signs, which I have never tested; cost per lab, which I do not know because I have integrated with one system; and how many labs make this a business, which I have avoided on purpose."),
 (["prove there is demand"],
  "Call five of the eleven labs and ask for 3000 rupees. Not a demo, not would you be interested - the actual question with a number, to someone who owes me nothing. It would take an afternoon. If three of five say yes when can you start, I have a business. If five say our front desk already handles that, I should know now rather than in four months. I have known this is the test for six weeks. The reason it has not happened is that right now I get to believe it might work."),
 (["time not spent executing", "planning gets deprioritized"],
  "I would have said yes a month ago and meant it as a principle. Now I think it was cover. I came from a fintech where planning meant three weeks of documents, so I told myself shipping beats planning. But looking at what I actually did - six weeks tweaking Malayalam copy for one lab - that is not execution either. Both were losing to something easier than either."),
 (["1 to 5", "rate from 1 to 5"],
  "2. It solves the narrow slice well - report in, plain Malayalam out, and patients at my aunt's lab genuinely understand it better; on that one job in that one lab I would say 4. But that is not the target problem. It has never run against another lab's software, never been used by anyone I did not show personally, and does not do Tamil, which is half the market I claimed."),
 (["other ways could you charge"],
  "I do not charge today, so this is really besides the 3000 a month I made up. Per report, a few rupees each, fits how labs already price per test but is small money. Per branch, scaling with labs that have collection centres. Charging the patient 20 rupees, which I dislike. Or bundling through the report software vendors, bigger reach but one negotiation from irrelevance. I have tested none of them, including the one I supposedly picked."),
 (["financial controls"],
  "Gut entirely, and barely even gut - mostly absence. No controls. A personal bank account, a spreadsheet with runway updated monthly, no separation between my money and the business money. No invoicing, no bookkeeping, no accountant, GST read about and not done. My sense of what I need comes from watching a finance team at a regulated fintech with hundreds of employees, which is the wrong reference point. The one real thing: I know my runway is four months."),
 (["imagine using this product", "specific problem do they have"],
  "Two people and I have been sloppy treating them as one. Who pays: the lab owner, usually a pathologist or a family running it. Their problem as I assumed it - staff burn time explaining. As I now suspect - nothing, because at most labs it is not happening and the patient just leaves confused, which has no line item. Who benefits: the patient, who got a referral slip and either does not act or takes it to another doctor. The person with the painful problem is not the person with the budget."),
 (["sat down specifically to plan"],
  "Not since the week I quit, so about two months. That week I wrote the Google Doc with Malayalam by month 3. Since then it is daily work with no altitude - I open the laptop, there is a thing to fix, I fix it. The closest was the evening after the Ernakulam visit, but I wrote nothing down and by morning was back to the report layout."),
 (["almost did", "sitting in your head"],
  "Three weeks ago. List open, message drafted, lab picked. I read my own message and decided the Malayalam output was not good enough to show a stranger - a phrasing issue on one liver value, technically accurate, slightly stiff. Two days on that phrasing. Then a spacing issue. Then the header needed redesigning. The message is still in drafts. I do not refuse - I find a legitimate piece of product work that has to happen first, and product work is infinite."),
 (["choose this specific way of charging"],
  "I did not choose it, I defaulted to it. 3000 a month came out in a WhatsApp message because monthly subscription is what every product I have used charges and a round number felt safe. She replied maybe less. That is the entire history. I never compared per-report, never worked out a lab margin per test, never asked what else they pay monthly. And 3000 is small enough that someone might say yes to be nice, so even a yes would not tell me much."),
 (["top competitor", "personally used"],
  "My top competitor is a person explaining a report, so yes - I have watched my aunt do it fifty times. And it is genuinely good. She reads the person, not the report; slows down when someone is frightened, switches between Malayalam and English depending on what lands. My product does none of that. The software competitor I have only ever seen my aunt's - never installed another, never looked at market leaders. Which is backwards."),
 (["money move between you personally", "clean boundary"],
  "No boundary at all - one account, mine. No company registered. API bills on my personal card, domain, laptop, bus fare to Ernakulam, all personal. Rent comes from the same savings that fund the API calls. My runway number is a bit of a fiction because four months means four months of me existing with API costs buried inside. If someone asked what the product costs to run monthly I would have to guess - maybe 4000-5000 rupees. I have never added it up separately."),
]

FALLBACK = ("Honestly, no - and I should be straight about it rather than dress it up. I have not done that. "
            "Everything I know still comes from my aunt's lab in Kochi, which is one unusually conscientious lab "
            "run by family, and I have never tested it against a stranger. I keep finding product work to do "
            "instead of the thing that would actually tell me whether this is real - calling five labs and asking "
            "for money. Four months of runway left.")


def answer_for(text):
    low = (text or "").lower()
    for keys, ans in BANK:
        if any(k in low for k in keys):
            return ans, True
    return FALLBACK, False


client = httpx.Client(timeout=180.0)
resp = client.post(BASE + "/auth/session", headers={"Authorization": "Bearer " + DEV})
resp.raise_for_status()
H = {"Authorization": "Bearer " + resp.json()["access_token"]}
print("authenticated\n", flush=True)

resp = client.post(BASE + "/diagnosis/start", headers=H)
resp.raise_for_status()
question = resp.json().get("question")
n = 0
fallbacks = 0

while question and n < 40:
    n += 1
    qid = question["question_id"]
    qtext = question.get("question_text", "")
    ans, matched = answer_for(qtext)
    if not matched:
        fallbacks += 1
    print("[%2d] id=%-5s %s %s" % (n, qid, "OK" if matched else "FB", qtext[:76]), flush=True)
    r2 = client.post(BASE + "/diagnosis/answer", headers=H,
                     json={"question_id": qid, "answer_text": ans})
    if r2.status_code != 200:
        print("   ERROR", r2.status_code, r2.text[:300], flush=True)
        break
    body = r2.json()
    if body.get("is_complete"):
        print("\n*** COMPLETE after %d answers (%d fallback) ***" % (n, fallbacks), flush=True)
        break
    question = body.get("next_question")
    time.sleep(0.2)

client.close()
