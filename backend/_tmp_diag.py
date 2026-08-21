import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from fastapi.testclient import TestClient
from app.main import app
from app.core.auth import AuthUser, get_current_founder
UID = "7a70613d-6fb9-58a0-8642-a85fdaa135f4"
app.dependency_overrides[get_current_founder] = lambda: AuthUser(id=UID, email="priya@northstar.in", provider="dev")
c = TestClient(app); B = "/api/v1"

KEYED = {
 307:"Being trusted. Not first, not the best -- I want a lab owner to recommend us without me asking.",
 215:"Small labs spend more time explaining results than producing them, so we do the explaining automatically.",
 113:"Zero paying customers. One lab -- my aunt's -- and that isn't a real customer, it's family.",
 122:"No team. Solo. Ops background, not healthcare, not engineering. No cofounder. First startup.",
 404:"No. I've never written a risk list. I worry constantly at 2am but worrying isn't listing.",
 377:"My aunt's lab, and the translation model I don't own. One is family, one is a vendor I can't control.",
 332:"Zero. Nobody outside my own network. Eleven labs on a list, not one contacted.",
 393:"A Google doc from when I quit, dates already missed, not opened since week two.",
 306:"A friend said 'this is a feature, not a company'. It stayed with me for a weekend and honestly it's still here.",
 1471:"Yes, and I've treated that as a virtue when it's mostly an excuse not to look for a cofounder.",
 376:"No. Never once. The moment those five things are on one page you can do the arithmetic and I've avoided that.",
 339:"A person explaining it. My aunt, for twenty minutes, unpaid. There's no software competitor.",
 405:"That my aunt's lab isn't a normal lab, and I built everything around it as if it were.",
 171:"No. I saw one unusually conscientious lab and generalised from a sample of one.",
 1469:"Honestly no. Zero founder circles since moving to Kochi. I've never put myself anywhere I'd find one.",
 379:"Parts fast, the whole thing no. The pen stops where the economics should be.",
 6:"Call five labs and ask for 3000 rupees. It costs nothing. I've known that for six weeks and haven't done it.",
 2108:"I'd have said yes a month ago and meant it. Now I think it was cover. Both were losing to something easier.",
 106:"2. It works for one user, on the version of the problem I assumed rather than verified.",
 351:"Per report, per branch, charge the patient, or bundle through software vendors. Tested none.",
 177:"Gut, entirely. No controls at all. One personal account, no bookkeeping, no accountant.",
 2:"The lab owner pays, the patient benefits, and I've never verified the owner feels the pain.",
 392:"Not since the week I quit -- about two months. Daily work, no altitude.",
 210:"Three weeks ago. I decided the output wasn't good enough to show a stranger, and spent two days on phrasing.",
 352:"I didn't choose it. I defaulted to it. 3000 came out of my mouth once and my aunt said 'maybe less'.",
 340:"Yes -- my aunt, fifty times. She's genuinely good. I've never used another lab's software.",
 1693:"No boundary at all. One account, mine. API bills on my personal card.",
 99:"Around what I want to build. I've been polishing Malayalam output instead of calling labs.",
}
FB = ("Honestly, no -- I haven't done that. I keep meaning to and then find something in the "
      "product to fix instead. It scares me a bit to find out the answer.")

r = c.post(f"{B}/diagnosis/start"); assert r.status_code in (200,201), r.text
q = r.json().get("question"); n = 0
print("session started")
while q and n < 45:
    qid = q["question_id"]
    print(f"[{n+1:2}] id={qid:<5} {'OK' if qid in KEYED else 'FB'} {q['question_text'][:64]}", flush=True)
    resp = c.post(f"{B}/diagnosis/answer", json={"question_id": qid, "answer_text": KEYED.get(qid, FB)})
    if resp.status_code != 200:
        print("!! HTTP", resp.status_code, resp.text[:200]); break
    body = resp.json(); n += 1
    if body.get("is_complete"):
        print(f"\n*** COMPLETE after {n} answers ***", flush=True); break
    q = body.get("next_question")
