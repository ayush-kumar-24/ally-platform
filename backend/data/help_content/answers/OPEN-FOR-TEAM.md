# Questions left unanswered — for the team

A running list. Every question here has been deliberately left empty rather than
answered badly. Each one needs a decision, a piece of the product, or access I do
not have.

Updated as each group is worked through. Last updated: **4 September 2026**
(groups 1, 3-8, 16, 22, 23 done).

---

## 1. Needs a product decision

| # | Question | Why it is open |
|---|---|---|
| 4 | I picked the wrong stage. Can I change it? | Stage is not a cosmetic field. It decides which pillars are in scope and whether a business health score is published at all. So the real question is what happens to a report already generated against the old stage — reissue it, mark it stale, or refuse the change after a diagnosis. Needs deciding before anything is written. |
| 64 | My report looks thin — is that all of it? | Waiting on the open decision: do we defend shorter reports or fix them? An answer written now would either excuse a real product problem or admit one we have not agreed to admit. |
| 100 | Can I ask Ally about legal, tax or investment decisions? | No boundary exists anywhere — checked the prompt library, the knowledge base and the grounding prompts. Nothing states what Ally may or may not advise on. Needs writing from scratch, and is a legal position as much as a product one. |
| 200 | I run two businesses. Can I have both on one account? | Waiting on the team account decision. |
| 201 | Can I give my cofounder access? | Same decision. Worth noting the diagnosis is built around one founder's DNA, so this is not only a billing question. |
| 258 | What is "private mode", and what happens if I leave it off? | The toggle says it keeps business data "anonymised in aggregate insights", which tells a founder their data feeds aggregate insights unless they opt out. Either that is true and we say what it means, or the label is wrong. The most trust-sensitive item found so far. |
| 259 | What are these "aggregate insights" my business is going into? | Same as 258. |
| 278 | Is Ally actually DPDP and GDPR compliant, or just saying so? | A legal position, not an observation. Also collides with the decision never to name the AI model: data residency is settled and answerable, the processor is not. |

## 2. Needs a throwaway account

These change real account state on a production database. Not run.

| # | Question | What it needs |
|---|---|---|
| 273 | What is the difference between restricting processing and withdrawing consent? | Withdraw consent on a disposable account and compare against restriction, which is already tested and fully reversible. |
| 274 | If I withdraw consent, do I lose my report? | The founder asks this with their finger over the button. It has to be demonstrated, not repeated from the product's own wording. |

## 3. Cannot be tested locally — needs the deployed site

The local build has no Supabase, so sign-in shows "Continue (local development)"
instead of the real flow. Session behaviour differs under the dev auth provider.

| # | Question |
|---|---|
| 197 | I can't log in. I've forgotten my password. |
| 198 | Can I use the same account on my phone and my laptop? |
| 199 | I share a laptop. How do I sign out everywhere? |

*(Question 12, "can I sign in with Google", was answered by reading the live
sign-in page while signed out — no account needed. The three above need an actual
session on the deployed site.)*

## 4. Answered, but the answer is wrong until the product changes

| # | Question | The conflict |
|---|---|---|
| 5 | Is this going to try to sell me something? | Written to the agreed pricing — no free plan, ₹199 entry. The app still ships a Free tier: the test account shows "Ally Free" at ₹0, and the plan catalog defines free/starter/pro at ₹0/₹450/₹999 with no ₹199 tier. **Do not publish this answer until the catalog is updated.** Everything in groups 13, 14 and 15 depends on the same change. |

## 5. Still to test, not blocked

Not open questions — just work not yet done. Listed so they are not mistaken for
finished.

| # | Question |
|---|---|
| 195 | How do I change my profile photo? |
| 196 | Can I change the email on my account? |
| 203 | Which browsers does this work on? |
| 266 | Can I make the text bigger? |
| 267 | Does this work with a screen reader, or by keyboard only? |
| 271 | I want a fact corrected. Will that change my report? |
| 276 | I scheduled deletion by mistake. Can I stop it? |
