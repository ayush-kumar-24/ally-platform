# Questions left unanswered — for the team

A running list. Every question here has been deliberately left empty rather than
answered badly. Each one needs a decision, a piece of the product, or access I do
not have.

Updated as each group is worked through. Last updated: **5 September 2026**.

**Start with the register directly below** — it is everything that needs you or
your team, gathered in one place. The numbered sections after it are the working
record of what was found and fixed, in the order it happened.


---

# ON YOU — the consolidated action register

Everything below needs **you or your team**, not the repo. Nothing here can be
fixed by writing code, so none of it is done and none of it will be until
somebody decides or configures something.

Ordered by what it costs you if it is left alone.

## A. Blocking a paid feature, right now

| # | What | Why it is yours | Cost of leaving it |
|---|---|---|---|
| A1 | **`EMAIL_HOST` is not set** | One environment variable on the server. | Nothing outbound sends. Not the discovery-call confirmation, not the call reminders, not the new-device sign-in notice that is built and waiting. Everything in section B is blocked behind this too. |
| A2 | **The discovery-call calendar is a personal Gmail** (`14aarush9@gmail.com`) | Needs a Google Workspace account. | No per-call Meet links and no Google invite emails. **Every call currently shares one permanent room** (`meet.google.com/bxx-nczh-rki`), so anyone ever sent it can rejoin any future call, and two founders booked back to back can walk into each other. |
| A3 | **Nothing runs the reminder scheduler** | Point your existing cron / EventBridge / pg_cron at `POST /internal/jobs/send-call-reminders`, every 15 minutes, with the `X-Internal-Secret` header. | 24h and 1h call reminders never fire. The endpoint now exists; nothing calls it. |
| A4 | **Checkout: the backend is built and correct, the frontend is a mock that collects card details** | Another teammate owns it. `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` are also unset. | See **E1** below — this is the most serious single item in this file. |
| A5 | **The merge migration is not applied to production RDS** | Needs the AWS teammate to run `alembic upgrade head`. | Discovery calls 500 on production (`column "is_priority" does not exist`). |
| A6 | **Testers are still on `plan_type = 'free'`** | SQL you have to run, listing the accounts explicitly. | The moment `PUBLIC_LAUNCH=true` is flipped, every current tester loses the product along with everyone else. See `docs/PUBLIC-LAUNCH-CHECKLIST.md`. |

## B. Product decisions — a support answer stays unwritten until you choose

| # | Question | The decision |
|---|---|---|
| B1 | 4 — I picked the wrong stage. Can I change it? | Stage decides which pillars are in scope and whether a health score is published. What happens to a report already built against the old stage: reissue, mark stale, or refuse the change after a diagnosis? |
| B2 | 64 — My report looks thin. Is that all of it? | Do we defend shorter reports or fix them? |
| B3 | 100 — Can I ask Ally about legal, tax or investment decisions? | **Correction: a boundary DOES exist — in the Terms, clause 2.** It says the Platform "does not constitute professional legal, financial, or management consulting advice" and the founder "remains solely responsible for all business decisions". I said earlier that no boundary existed anywhere; that was wrong, and I had not read the Terms. What is still true is that **nothing enforces it** — the prompt library, the knowledge base and the grounding prompts say nothing about it, so Ally will answer a tax question as readily as a pricing one. The gap is now between the document and the behaviour, which is the more awkward of the two to be caught in. |
| B4 | 152–155, 169 — Free's shape at launch | Settled in principle (nothing free at launch) but the catalog still ships a Free tier carrying almost everything. |
| B5 | 153 — Why does Free get more chat per day than Starter? | Free's daily ceiling is above the ₹450 plan's, and the ₹199 plan has no chat at all. No wording fixes this; the ladder does. |
| B6 | 200, 201 — two businesses / cofounder access | Team-account decision. Note the diagnosis is built around one founder's DNA, so it is not only a billing question. |
| B7 | 278 — DPDP/GDPR compliance | A legal position, not an observation. Two things would have to be resolved first: the Right to Nominate is published and not built (**E4**), and **E2**. *(209 is now answered — the Privacy Policy already discloses third-party LLM processing without naming the vendor.)* |
| B8 | 189 — refund policy | No refund policy exists in writing anywhere. Will be asked in week one. |
| B9 | 183, 185, 194 — GST invoicing, foreign payment, introductory pricing | All three are yours, all three are asked at checkout. |
| B10 | **Is ₹199 monthly or one-time?** | The catalog says per month; the pricing proposal said one-time. Both readings are live in the repo, and the billing page cannot avoid answering it. |
| B11 | **The daily digest** — `reminder_time`, `daily_reminders`, `task_reminders`, `goal_reminders` | Four settings that persist and do nothing. Building them is the answer to Ally being unable to chase anyone, which is the biggest hole in its ability to build a habit. A feature, not a defect — so your call. Blocked behind A1 and A3 anyway. |
| B12 | **A sample report** (question 244) | Nothing links to one, so nothing is broken — but it is a fair ask from someone about to pay, and today the answer is no. |
| B13 | **A status page** | Every answer in group 18 ends with "write to us". One outage becomes a hundred separate support conversations. |
| B14 | **An "about us"** (question 232) | Our Story explains *why* Ally was built but names nobody. If a founder asks what qualifies the people behind it, we have nothing beyond the framework and the corpus. |

## C. Marketing pages — say something the product does not do

These are on the live site, read before anyone reaches the support bot. All are
small text edits, but **none of them is in this repo**.

| # | Where | What it says | What is true |
|---|---|---|---|
| C1 | Landing page, above the sign-up form | "Your data is encrypted, private and **accessible only to you**." | Support and above can read a founder's conversations and report. Suggested replacement, true and nearly as strong: *"encrypted, private and never sold or shared with other founders."* |
| C2 | Landing page | "As the business changes, Ally **reruns the diagnosis** instead of starting the founder over." | One diagnosis per account. Re-running at a stage change is intended and not built. Stated in the present tense, on the page someone reads before paying. |
| C3 | Sample dashboard (`/ally-dashboard.html`) | "Ally Plus — Unlock deeper diagnosis, **unlimited chat** and **Founder MRI**." | There is no Founder MRI feature. And "unlimited chat" is the reverse of true — Plus is capped at 3,500 tokens a day, which against measured usage is two or three messages. **This is the upgrade pitch, on the page, above the sign-up form.** |
| C4 | Sample dashboard | "FOUNDER CLARITY: **Forming**" | Not one of our bands. The real four are Critical Gap, Needs Attention, Developing, Strong. |
| C5 | Our Story (`/about.html`) | Prints `join.goxlally.ai — early access is open` as plain text | That subdomain is retired. The button beside it is correct, so nobody is 404'd by clicking — but it reads as the address to type. |

## D. Verification only you can do

| # | What | Why |
|
## E. Found in the Terms and the Privacy Policy — read these first

Both documents are published and live. Everything here is a conflict between
what they say and either what the product does or what our help answers say. A
founder who reads both catches us; a regulator reading both catches us harder.

| # | What | Why it matters |
|---|---|---|
| **E1** | **The billing page collects card numbers and fakes a successful payment.** `Billing.jsx` renders its own form — card number, expiry, CVV — validates them, waits 2.2 seconds and shows **"Payment Successful!"**. Nothing is charged and nothing is granted. | Two separate problems. A founder can be told they have paid and receive nothing. And we are collecting raw card data in our own form, which is precisely what Razorpay's checkout widget exists to prevent — a PCI question the day it goes live. **The backend is not the problem: it is built and correct** (`POST /payments/checkout` creates a *pending* payment; only the signed webhook grants a plan; it fails closed without keys rather than faking success). The frontend simply never calls it. |
| **E2** | **The Terms and the Privacy Policy both say we improve our AI models from founder data. Help answer 206 says we never do.** Terms clause 4: *"Anonymised, aggregated insights may be used internally to improve our AI models."* Privacy Policy section 6: *"Anonymised, aggregated diagnostic data … may be retained indefinitely to improve our AI models."* Answer 206 says *"not used to train any AI model — not ours, and not anyone else's."* | Both cannot stand. This is also where the "aggregate insights" wording on the removed Private Mode switch came from — so that label was not a stray, it was pointing at a **real reserved right**. Today nothing in the product actually does it (no founder data is embedded, no aggregation pipeline exists), so the documents reserve something we do not use. Either amend them or soften the answer. **A legal call. Answer 206 is unchanged pending it.** |
| **E3** | **The Privacy Policy asserts AES-256 encryption at rest.** Section 8, stated as fact. | Help answer 246 deliberately did *not* claim it, because nothing in the repo proves it and production RDS has never been checked from here. A support answer being cautious is fine; a published privacy policy asserting an unverified security control is not. Confirm it (**D2**) or soften the policy. |
| **E4** | **The Right to Nominate is published and not built.** Privacy Policy section 7(f) offers founders the right to nominate someone to exercise their rights on death or incapacity. | There is no feature and no written manual process. It is a DPDP right we have committed to in writing. |
| **E5** | **Nothing covers GoXL being sold or shutting down.** No clause in the Terms or the Privacy Policy. | Question 285, left unanswered because there is nothing honest to say. The two things founders actually ask: would my data transfer to a buyer, and would I get a chance to take my report out first. |
| **E6** | **Terms clause 6 is narrower than the product behaves.** It licenses the Platform for *"personal or internal business purposes only"*, non-transferable. | Meanwhile the product ships a Share button that mints a public link, and help answer 82 actively encourages sending the report to an investor or a board — not an internal purpose. The product is almost certainly right and the clause is the thing to widen, but as written they disagree. |

**A resolved one, for completeness:** question 209 ("does what I type go to an
outside AI company?") was in section B as blocked. It is not — **Privacy Policy
section 5(b) already discloses it**: *"anonymised diagnostic data may be
processed by third-party LLM providers under strict data handling agreements."*
That is the disclosure without naming the vendor, which is exactly the position
we wanted. The answer can now be written.

---|---|---|
| D1 | **Confirm the production RDS region** | Answer 208 tells founders their data is stored in India. The load balancer and the Supabase project are both `ap-south-1`, but production RDS has never been checked from here, and a residency claim is one of the few things worth being certain about. |
| D2 | **Confirm encryption at rest** on RDS and the S3 buckets | Answer 246 deliberately claims only what was verified — HTTPS in transit and encrypted calendar tokens. If both come back clean the answer gets one stronger sentence. Commands are in `docs/PRODUCTION-RDS-CHECKS.md`, Check 6. |

---

*Everything NOT in this register was fixed in the repo. Sections 6 onward below
record what was found and what was done about it, in the order it was found.*

---

## 1. Needs a product decision

| # | Question | Why it is open |
|---|---|---|
| 4 | I picked the wrong stage. Can I change it? | Stage is not a cosmetic field. It decides which pillars are in scope and whether a business health score is published at all. So the real question is what happens to a report already generated against the old stage — reissue it, mark it stale, or refuse the change after a diagnosis. Needs deciding before anything is written. |
| 64 | My report looks thin — is that all of it? | Waiting on the open decision: do we defend shorter reports or fix them? An answer written now would either excuse a real product problem or admit one we have not agreed to admit. |
| 100 | Can I ask Ally about legal, tax or investment decisions? | No boundary exists anywhere — checked the prompt library, the knowledge base and the grounding prompts. Nothing states what Ally may or may not advise on. Needs writing from scratch, and is a legal position as much as a product one. |
| 152 | If Free already gives me the diagnosis and the report, why would I pay? | Free's shape at launch. Today it is a testing-phase tier that gives away almost everything, and the catalog says in as many words that it is to be resized. |
| 153 | Why does Free get more chat per day than Starter? | Still true. Free carries a higher daily chat ceiling than the Rs 450 plan, and the Rs 199 plan has no chat at all. No wording fixes this — the ladder does. |
| 154 | How long does Free last? | Same decision as 152. |
| 155 | What happens at the end of my free month? | Same decision as 152. |
| 169 | I'm on Free — do I get credits again next month? | Free's shape at launch, same as 152-155. Today Free grants credits once and never renews; at launch Free carries nothing. |
| 200 | I run two businesses. Can I have both on one account? | Waiting on the team account decision. |
| 201 | Can I give my cofounder access? | Same decision. Worth noting the diagnosis is built around one founder's DNA, so this is not only a billing question. |
| ~~258~~ | ~~What is "private mode"?~~ | **CLOSED 2026-09-05.** The switch was removed. Nothing read it, and there are no aggregate insights, so the label described a data use we do not have. Both answers are now written. Nothing to decide — unless you ever want to BUILD aggregate insights, in which case the opt-out belongs in the privacy policy before it goes back on the page. |
| ~~259~~ | ~~What are these "aggregate insights"?~~ | **CLOSED 2026-09-05.** Same. |
| 209 | Does what I type go to an outside AI company? | Collides with never naming the model. Residency is settled; the processor is not. DPDP/GDPR transparency generally expects a sub-processor to be identifiable. Belongs in the privacy policy before a support answer. |
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

## 3b. A discrepancy worth settling

**Rs 199 billing cycle.** The plan catalog labels the Rs 199 tier "per month"; the
pricing proposal recommended it as a one-time purchase, on the grounds that a
second month of "one diagnosis and its report" delivers nothing new and generates
a refund request. Both readings are live in the repo. Answers 145, 150 and 151
deliberately avoid stating a cycle until this is settled.

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

## 6. Product defects found while walking group 18

Not blocked answers — things the answers had to work around. Each was found by
running the product, not by reading it.

| Where | What | Why it matters |
|---|---|---|
| **Plan ladder** | Plus (Rs 450) allows 3,500 tokens a day. A measured average message costs 1,305 tokens, so that is **two or three messages a day**. Pro's 8,000 is about six, and a real founder-day has already exceeded it (8,189 recorded). | Question 224 is literally "it says I've hit a limit and I've only just started". On Plus that will be true, on the first sitting, for someone who has just paid. No wording fixes it — the ceiling does. |
| **Profile photo** | The avatar picker accepts PNG, JPEG and WEBP only. iPhones save photos as HEIC by default, so on an iPhone the founder's own photos are **greyed out in the file chooser** — no error, nothing to read. | This was hit in our own testing (question 219). Either accept HEIC and convert server-side, or put one line of help text next to the button. |
| **Everywhere** | There is no status page. | Every answer in group 18 ends with "write to us". One outage becomes a hundred separate support conversations. Not urgent before launch, but it is the fallback for all twelve of these questions. |

*Question 195 ("How do I change my profile photo?") is no longer untested — the
upload path was walked on 2026-09-05 and works. The HEIC gap above is the only
thing wrong with it.*

## 7. The landing page says two things the product does not do

Found while walking group 19, which had to be written from goxlally.ai because
the positioning lives there and nowhere else. These are not help-content
problems. They are things a founder will have already read before they ever
reach the support bot.

*(The `join.goxlally.ai` 404 raised earlier is NOT a defect — that subdomain was
deliberately retired when the landing page was merged onto the main domain.)*

| On the page | What is actually true | Why it matters |
|---|---|---|
| "Your data is encrypted, private and **accessible only to you**." | Support and above hold VIEW_CHATS and VIEW_REPORTS. A small number of people at GoXL can read a founder's conversations and report. | Group 17 already bans this exact phrase from support answers for this reason, and answers 204 and 210 say plainly that staff can read. A founder who reads the promise and then reads the answer catches us in a contradiction. **"Your data is encrypted, private and never sold or shared with other founders"** is true and says almost as much. |
| "As the business changes, Ally **reruns the diagnosis** instead of starting the founder over." | One diagnosis per account, on every tier. Re-running at a stage change is intended and not built. | Stated in the present tense, on the page someone reads before paying. Answer 85 handles it as "not yet, never no", but that is repair after the fact. Either build it or move the sentence to the future tense. |

## 8. Missing, and it blocks a good answer

**No public "about us".** Question 232 asks who built Ally and what qualifies
them to diagnose a business. The strongest true answer is the framework and the
corpus — 100+ dimensions, 10,000+ case studies, 25,000+ problems mapped to root
causes — and that is what is written. But nothing anywhere names the team or
their track record, so a founder who pushes past that answer gets nothing. A
short page the bot can point at would close it.

## 9. The sample dashboard on the homepage sells two things that do not exist

The landing page embeds a static demo at `/ally-dashboard.html` — "Ally —
Founder Platform (Sample)", a made-up founder called Priya Sharma. It is the
"see it from inside" section, so it is looked at closely by exactly the people
deciding whether to pay.

| In the demo | What is actually true |
|---|---|
| Sidebar: **"Ally Plus — Unlock deeper diagnosis, unlimited chat and Founder MRI."** | There is no **Founder MRI** feature anywhere in the product. And **"unlimited chat" is the opposite of true**: Plus is capped at 3,500 tokens a day, which against measured real usage is two or three messages. This is the upgrade pitch, on the page, above the sign-up form. |
| **"FOUNDER CLARITY: Forming"** | "Forming" is not one of our bands. The real four are Critical Gap, Needs Attention, Developing and Strong. A founder who sees it on the site and never in the product will think something is missing from their account. |

Both are one-line fixes on a static page.

*Also minor: Our Story (`/about.html`) prints `join.goxlally.ai — early access is
open` as plain text under its call to action. The button beside it correctly
points at `/#early-access`, so nobody is 404'd by clicking — but it reads as the
address to type, and that domain is retired.*

## 10. Two tabs can sign a founder out — proven, not suspected

Found while walking group 21. This is the most likely real cause of "it keeps
signing me out", which has been reported and never explained.

The refresh token is **single-use and rotating** — the backend revokes the old
one on every refresh. The frontend's guard against concurrent refreshes
(`refreshFlight` in `services/api.js`) is a **module-level variable, so it is per
tab, not per browser**. Two tabs whose 30-minute access tokens expire together
both call `/auth/refresh` with the same cookie.

Reproduced with curl against the running backend:

```
POST /auth/refresh  (first)   → 200, new token pair
POST /auth/refresh  (second, same cookie) → 401 "Refresh token has been revoked"
```

In the browser that 401 runs `clearTokens()` and the auth-failure handler, so
the founder is bounced to sign-in — and `localStorage` is cleared under the other
tab as well.

**Not fixed here.** It is auth-critical and wanted your decision first. Two ways:

* a cross-tab lock — `BroadcastChannel` or a `localStorage` mutex — so only one
  tab ever refreshes and the others wait for its result; or
* a short server-side grace window where a just-rotated refresh token is still
  accepted for a few seconds.

Answers 254 and 256 currently tell founders we know about it and are fixing it.
That is honest today. It should not stay true for long.

## 11. Seven settings that do nothing

Every one of these validates, persists and reads back through a working API.
**None of them is read by any code, anywhere.**

| Setting | Default | Reachable in the UI? |
|---|---|---|
| `session_timeout_minutes` | 60 (adjustable 5–1440) | No |
| `login_notifications` | true | No |
| `daily_reminders` | true | No |
| `reminder_time` | 09:00 | No |
| `task_reminders` | true | No |
| `meeting_reminders` | true | No |
| `goal_reminders` | true | No |
| `in_app_all` ("Notifications" switch) | true | **Yes — on the Profile page** |
| `private_mode` ("Private mode" switch) | true | **Yes — on the Profile page** |

The last two are the ones that matter, because a founder can see and flip them.

`session_timeout_minutes` deserves its own line: a founder setting it to 5
minutes gets exactly the same 30-day session as everyone else. A security
setting that silently does nothing is worse than not offering one.

Also: **nothing schedules the discovery-call reminder job**. `send_due_reminders`
exists and is never called, so the 24h and 1h reminders never fire.

## 12. "Private mode" — REMOVED 2026-09-05

The switch read *"Keep business data anonymised in aggregate insights"* — which
told a founder their business data goes into aggregate insights by default and
that this switch anonymises it. Neither was true: nothing read the flag, and
there are no aggregate insights anywhere in the product.

**Removed rather than reworded**, from both the Profile page and the settings
schema. A privacy control that does nothing is worse than no control, and
describing a data use we do not have is worse again. Stored rows keep the old key
harmlessly (`extra="allow"`), so there was no migration.

Questions 258 and 259 are now answered: there is no private mode, and there are
no aggregate insights.

*If aggregate insights are ever built, the opt-out goes in the privacy policy
BEFORE it goes back on that page.*

## 13. Fixed while walking groups 21 and 22

* **A marketing opt-out was switching off paid call reminders.** The switch read
  "Renewal reminder / Get notified about new features and offers" and was wired
  to `email_reminders` — whose only consumer gates the 24h and 1h reminders for a
  discovery call. A founder declining marketing was silently turning off the
  reminders for a call they had paid ₹199 for. Relabelled to **"Call reminders by
  email / Reminders before a discovery call you have booked"**. If marketing
  email is ever sent, it needs its own flag, not this one.
* **The four Profile switches were invisible to a screen reader.** Bare buttons
  with no text and no `aria-label`, so a screen reader announced "button" four
  times with no name and no on/off state. Added `role="switch"`, `aria-checked`
  and `aria-label` to all four. Verified live: the page now reports **zero**
  unnamed controls.

## 14. Two honest "no"s worth knowing

* **No dark mode.** Zero `prefers-color-scheme` colour rules are loaded and the
  root carries no `data-theme`. Answer 268 says so plainly and points at the
  Feedback page.
* **Text-only scaling barely works.** Of 107 sampled elements, 7 responded to a
  change in root font size — the styling is px throughout. Full page zoom works
  fine and reflows without overflow, so answer 266 recommends that and admits the
  gap rather than dodging it.

## 15. The full write-up: dead settings and discovery-call delivery

Both now have their own document: **`backend/docs/DEAD-SETTINGS-AND-CALL-DELIVERY.md`**.

**Part 1 — a paid discovery call currently cannot reach the founder who paid.**
Not Calendly; our own booking on top of Google Calendar. The host calendar is a
personal Gmail, so per-call Meet links and Google's own invite emails are both
off. `EMAIL_HOST` is unset so our confirmation email never sends. The app's own
"Your calls" list shows date and status only — no join link. And nothing
schedules the reminder job. Booked, paid, confirmed, silent. Also: every call
shares one permanent room link, so anyone ever sent it can rejoin any future
call.

**Part 2 — seven settings that persist and do nothing.** Verdicts in the doc:
drop `session_timeout_minutes`; **build `login_notifications`** (cheapest real
security win, and it retires a help answer that is only safe while it stays
true); build the four reminder settings *after* email and a scheduler exist,
because they are the answer to Ally not being able to chase anyone; merge
`meeting_reminders` into the existing call switch; hide the visible
"Notifications" switch until it controls something.

## 16. Fixed 2026-09-05: two tabs no longer sign a founder out

`services/api.js` now takes a **cross-tab lock in localStorage** before calling
`/auth/refresh` or `/auth/resume`. One tab refreshes; the others wait for the new
access token and use it. A stale lock is taken over after 10 seconds so a dead
tab cannot wedge anyone, and if `localStorage` is unavailable the code degrades
to exactly the old per-tab behaviour rather than breaking.

There is also a last defence: if a refresh fails, the code checks whether another
tab has since written a *newer* access token, and if so keeps the session instead
of signing the founder out.

`resumeSession` takes the same lock — the two were racing each other, not just
themselves.

**Verified live with two real browser tabs** reloading simultaneously with no
access token. tab-2 took the lock and called `/auth/resume` (200); tab-1 waited,
picked up the shared token and called `/auth/me` (200) instead of racing. Zero
401s, neither tab signed out, lock released cleanly. Before the fix the same test
produced `401 "Refresh token has been revoked"`.

## 17. Fixed 2026-09-05 (second pass) — everything actionable from the repo

| What | Where |
|---|---|
| **A paid discovery call had no way to reach the founder.** The join link was in the API response and never rendered; with the calendar on personal Gmail and `EMAIL_HOST` unset, there was no other route either. The calls list now shows a **Join call** button on a confirmed booking, and tells a founder with a pending one that the link follows confirmation. Cancelled calls never offer a way in. Statuses read as sentences instead of raw enum values. | `pages/DiscoveryCall.jsx` |
| **"Paid plans include a call each month"** — no plan ever has. `free_calls_per_month` is 0 on every tier. Now reads "Calls are ₹199 each, on any paid plan, and you can book as many as you need." | `pages/DiscoveryCall.jsx` |
| **The call-reminder job had no caller.** `send_due_reminders` has existed since discovery calls shipped and nothing ever ran it. Now `POST /internal/jobs/send-call-reminders`, same shared-secret auth as the other sweeps. **Point a scheduler at it every 15 minutes.** | `webhooks/internal_jobs.py` |
| **`login_notifications` built** — new-device sign-in emails. Coarse device fingerprint (browser/OS family + IP /24), history in `audit_logs` so no migration, first device learned silently, and the email deliberately carries **no link** so "our emails never ask you to click" stays a usable phishing test. | `services/login_notifications.py` |
| **`session_timeout_minutes` removed** from the API, the domain model, the service and the validators. It was a false assurance: a founder choosing 5 minutes got the same 30-day session as everyone else. | settings module |
| **`meeting_reminders` removed** — it duplicated the Profile page's own call-reminder switch, and only one of the two was reachable. | settings module |
| **The "Notifications" switch is hidden** until there is something for it to control. The flag and API remain, so restoring it is one line. | `pages/FounderProfile.jsx` |

DB columns for the two removed settings are **kept on purpose** — dropping them
needs a migration against a production database already behind on its own, and an
unread column costs nothing. Tidy them up whenever.

Help answers 143, 253, 254, 256, 257, 261, 262 and 263 were rewritten to match.
Answer 253 in particular had said we never send sign-in emails and that any such
email was phishing — true until today, and dangerous the moment this shipped.

### Still open, and all of it is infrastructure

1. **Set `EMAIL_HOST`.** One env var, and the highest-value item left. Nothing
   outbound sends without it — not the call confirmation, not the reminders, not
   the new-device notice that is now built and waiting.
2. **Move the discovery-call calendar to Google Workspace.** Personal Gmail
   cannot make per-call Meet links or invite attendees. Today every call shares
   one permanent room, so anyone ever sent it can rejoin any future call, and two
   founders booked back to back can walk into each other.
3. **Run the scheduler** against `POST /internal/jobs/send-call-reminders`.
4. **Decide on the daily digest** — `reminder_time`, `daily_reminders`,
   `task_reminders`, `goal_reminders` are still dead. They are a feature, not a
   defect, and blocked behind items 1 and 3 anyway.

Full detail: `backend/docs/DEAD-SETTINGS-AND-CALL-DELIVERY.md`.

---

# EVERYTHING THAT NEEDS YOU OR THE TEAM — one list

Added 2026-09-05. Sections 1–17 above are the running log. This is the same
material sorted by **who has to act**, so nothing that needs a decision is buried
in a log entry. Nothing below can be fixed from the repo.

## A. Decide before launch — the three that can bite

### A1. Our own Terms contradict a support answer about AI training

Three clauses we have already published:

* **Terms §4** — "Anonymised, aggregated insights may be used internally to
  improve our AI models."
* **Privacy Policy §3(c)** — lists improving our AI models with anonymised,
  aggregated insights as a *legitimate interest*.
* **Privacy Policy §6** — such data "may be retained **indefinitely** to improve
  our AI models."

Help answer 206 said, flatly: *"not used to train any AI model — not ours, and
not anyone else's."*

Both were live. A founder who reads the Terms and then asks the bot catches us
out, on the one topic where being caught out is fatal.

**Answer 206 has been rewritten** to draw the line the documents draw: your own
writing is never trained on and never indexed (both verified in code), while
anonymised aggregate data is something the Terms permit and nothing currently
does.

**The decision is yours:** do we actually intend to do this?

* **If no** — strike the clause from the Terms and Privacy Policy, and answer 206
  goes back to a clean "No", which is a much stronger thing to be able to say.
* **If yes** — it needs to be explained to founders in plain words *before* it
  starts, with a real opt-out. Which leads to A2.

### A2. "Private mode" is gone, and with it the only opt-out we ever offered

The switch read *"Keep business data anonymised in aggregate insights"* and was
removed on 2026-09-05 because nothing read it. **Correction to what was written
at the time:** that wording was not invented — it traces directly to the Terms
clause in A1. So the position now is:

* the Terms reserve the right to use anonymised aggregate data,
* nothing implements it, and
* founders no longer have even a nominal control over it.

Nothing about anyone's data changed. But if aggregate insights are ever built,
there is now no opt-out at all. **Do not re-add a switch that does nothing** —
settle A1 first, and if the answer is "yes we will do this", build the control
with the feature.

### A3. The Privacy Policy already promises AES-256 at rest, unverified

**Privacy Policy §8** claims TLS 1.3 in transit and **AES-256 encryption at
rest**, plus "regular security audits and vulnerability assessments".

Help answer 246 deliberately does *not* claim encryption at rest, because it
could not be verified from here. The policy claims it publicly, to every founder
who reads it.

**Check 6 in `docs/PRODUCTION-RDS-CHECKS.md`** is therefore no longer a
nice-to-have — it is confirming something already promised in writing. Same trip
should confirm the RDS **region**, which answer 208's "your data is in India"
rests on.

Also worth someone honestly answering: have the "regular security audits"
actually happened?

## B. Infrastructure — one env var, one account, one cron

| # | What | Why it matters | Effort |
|---|---|---|---|
| B1 | **Set `EMAIL_HOST`** | Nothing outbound sends. Not the discovery-call confirmation, not the reminders, not the new-device sign-in notice that is built and waiting. | One env var |
| B2 | **Move the discovery-call calendar to Google Workspace** | Personal Gmail cannot make per-call Meet links or invite attendees. Today **every call shares one permanent room** (`meet.google.com/bxx-nczh-rki`) — anyone ever sent it can rejoin any future call, and two founders booked back to back can walk into each other. | An account |
| B3 | **Point a scheduler at `POST /internal/jobs/send-call-reminders`** every 15 min, with the `X-Internal-Secret` header | The endpoint is built and tested. Without a caller the 24h/1h call reminders never fire. | A cron entry |
| B4 | **Apply the merge migration on production RDS** | Two alembic heads meant the plan-ladder branch never ran; `is_priority` is missing and discovery calls 500 on production. | One `alembic upgrade` |
| B5 | **Move testers off `plan_type='free'`** before `PUBLIC_LAUNCH=true` | The moment Free empties, every current tester loses the product with everyone else. SQL is in `docs/PUBLIC-LAUNCH-CHECKLIST.md`. | One UPDATE |

## C. Marketing pages — claims that do not match the product

Not in this repo, so somebody has to edit the site.

| Where | What it says | What is true |
|---|---|---|
| Sample dashboard on the homepage | "Ally Plus — Unlock deeper diagnosis, **unlimited chat** and **Founder MRI**" | There is no Founder MRI feature. Plus is capped at 3,500 tokens/day ≈ **two or three messages**. This is the upgrade pitch, above the sign-up form. |
| Same demo | "FOUNDER CLARITY: **Forming**" | Not one of our bands. The four are Critical Gap, Needs Attention, Developing, Strong. |
| Landing page, above the sign-up form | "Your data is encrypted, private and **accessible only to you**" | Support and above can read a founder's conversations and report. Suggested: *"encrypted, private and never sold or shared with other founders."* |
| Landing page | "As the business changes, Ally **reruns the diagnosis**" — present tense | One diagnosis per account. Re-running at a stage change is intended and not built. |
| Our Story (`/about.html`) | Prints `join.goxlally.ai` as plain text under the CTA | That subdomain is retired. The button beside it is correct, so nobody is 404'd by clicking — but it reads as the address to type. |

## D. Product decisions — no right answer without you

| # | Question | Why it is stuck |
|---|---|---|
| D1 | **Is ₹199 monthly or one-time?** | The catalog says per month; the pricing proposal said one-time. Both are live in the repo. The billing page cannot avoid answering it. Blocks answers 145, 150, 151. |
| D2 | **Refund policy** | Nothing exists in writing anywhere. Will be asked in week one. Blocks answer 189. |
| D3 | **GST invoicing, foreign payment, annual billing** | Blocks answers 182–185, 194. |
| D4 | **Team / multi-business accounts** | Blocks answers 157, 200, 201, and shapes 297. |
| D5 | **What happens to founder data if GoXL is acquired or shuts down** | The Terms have **no assignment, merger or successor clause at all**. Blocks answer 285; conspicuous to exactly the founder who reads terms before paying. |
| D6 | **Is a report usable in an investor deck?** | Terms §6 licenses the Platform for "personal or internal business purposes only" — arguably excluding an investor deck, which is the single most likely use of a report someone paid for. Answers 281 and 282 are written to that line; it deserves an explicit sentence in the Terms. |
| D7 | **GDPR** | Claimed nowhere. Fine while every founder is in India; a problem the first time an EU founder signs up. Answer 278 says so plainly. |
| D8 | **What may Ally advise on?** | No boundary exists in the prompt library, knowledge base or grounding prompts. Legal/tax/investment advice is deliberately **left off** answer 237's "what Ally does not do" list, because claiming a guardrail we have not built is worse than the gap. Blocks answer 100. |
| D9 | **A sample report before sign-up** | None exists. A fair ask from someone about to pay. Blocks answer 244. |
| D10 | **A referral programme** | Nothing exists. Asked by founders who like the product enough to tell someone — the cheapest acquisition there is. Blocks answer 295. |
| D11 | **The daily digest** (`reminder_time`, `daily_reminders`, `task_reminders`, `goal_reminders`) | Four settings that still do nothing. It is the answer to Ally being unable to chase anyone, which is the biggest hole in its ability to build a habit. A feature, not a bug — your call. Blocked behind B1 and B3 anyway. |
| D12 | **Upload a plan or deck instead of answering the diagnosis** | Asked by the founder with the least patience and the most to give us. Ally can already *read* a deck in chat; using it to pre-fill or shorten the diagnosis is close to machinery that already exists. Highest-value item in group 25. |

## E. Things a founder cannot reach

* **Group 21 is unreadable by the people who need it.** Every question in it is
  asked by someone locked out, and Help & Support lives *inside* the app. At
  minimum, "my code hasn't arrived", "the code expired" and "I signed up with the
  wrong email" need to be reachable from the sign-in screen itself.
* **No status page.** Every answer in group 18 ends with "write to us". One
  outage becomes a hundred separate support conversations.
* **Ally does not know it is Ally.** Asked about billing it suggested checking
  "their pricing page". The boundary is deliberate (answer 99), but the redirect
  wording is not.

## F. Still unanswered, and why

20 of 285 written answers have no text. Every one is deliberate:

| Where | Count | Blocked on |
|---|---|---|
| Group 13 — plans (152–155, 157–159) | 7 | **D1** (₹199 cycle), **D3**, **D4**, and checkout not existing |
| Group 16 — account and access (195–201, 203) | 8 | **Nothing.** This is simply the last group not yet walked — and most of it is now answerable from work done today. See below. |
| Group 14 — 169 (does Free renew?) | 1 | **D1** and the plan ladder |
| Group 24 — 285 (acquisition / shutdown) | 1 | **D5** |
| Group 8 — 100 (legal, tax, investment advice) | 1 | **D8** |
| Group 4 — 64 (is my report thin?) | 1 | Needs a product view on report length |
| Group 1 — 4 (I picked the wrong stage) | 1 | Left empty at your instruction, pending the stage-change decision |

**Group 16 is close to free.** Today's walks already answered most of it without
meaning to: the avatar upload path (195) was walked for question 219, the fact
that a founder cannot change their own email (196) came out of question 252,
password reset (197) out of 249, and multiple devices and sessions (198) out of
255 and 256. Only 199 ("sign out everywhere"), 200/201 (**D4**) and 203
(browsers) need anything new — and 199 is the security control worth having
instead of the session timeout that was just removed.

---

# DECISIONS TAKEN 2026-09-05 — ten items closed

The team went through the consolidated list. Recorded here so nothing gets
re-litigated, and so the reasoning survives the meeting.

| # | Decision | What changed in the product |
|---|---|---|
| **A1** | **The Terms are the position.** Anonymised, aggregated data may be used to improve Ally's models, as Terms §4 and Privacy Policy §3(c) and §6 already say. | Answers **206, 258, 259 and 283** rewritten to draw the line the Terms draw: *your own writing is never trained on and never indexed; anonymous combined patterns may be used.* The first half is verified in code. |
| **A2** | **Remove private mode.** "If it was doing nothing, then it is better to remove it." | Gone from the Profile page and the settings schema. |
| **D1 (calls)** | **₹199 per discovery call, every time.** Not monthly, not one-time. Every plan can book as many as they want; each is ₹199 for 30 minutes. | Answers **144, 145 and 146** rewritten from "the price is confirmed when the team accepts" to the actual number. |
| **D9** | **No sample report, ever.** A made-up one would set an expectation a real report might not match. | Answer **244** now says so plainly instead of "not yet". |
| **D11** | **Remove the four dead reminder settings.** "If it does not work, just remove it. If we need it, we will build it." | `reminder_time`, `daily_reminders`, `task_reminders`, `goal_reminders` removed from the API, the domain model, the service and the validators — and `PATCH /settings/reminders` with them. Answers **257, 260, 261** rewritten from "not yet" to a plain no. |
| **D12** | **Every diagnosis question must be answered by the founder.** An uploaded deck will not pre-fill or shorten it — *"our system needs to know you from you."* | Answer **290** now gives that reason rather than calling it a gap. |
| **E1** | **The support bot goes on the landing page, and every page.** Reachable without an account — no founder identity is needed to answer a question about signing in. | Closes the locked-out-founder problem. **Not built yet**, so no answer claims it. |
| **E3** | Already fixed. | The chat prompt names Profile and Help & Support instead of "their pricing page". Applied to the grounded and general chat prompts. |
| **B4** | Owner: **the AWS teammate.** | — |
| **B5** | Owner: **us, immediately before launch.** | — |

## What the decisions did NOT settle

**Two different things cost ₹199.** The discovery-call price is now settled. But
the **entry plan tier is also ₹199**, billed per month in the catalog, giving the
diagnosis and report and nothing else. A founder who has heard "₹199" will not
know which one they are buying.

That question is still open and is tracked as **D1b**: is the ₹199 *plan* monthly
or a one-off, and is it worth renaming or repricing one of them so the two stop
colliding? It blocks answers 152–155, 157–159 and 169.

## Still open

**B1, B2, B3** (email host, Workspace calendar, the reminder scheduler) — to
discuss with whoever owns that work.
**A3** (the unverified AES-256 claim), **C1–C5** (marketing copy), **D2–D8**,
**D10** and **E2** — all still need a decision.

Eighteen items, in the artifact.

## D1b settled — both 199s

**The Starter plan is Rs 199 per month**, renewed monthly. It gives the diagnosis
and the Clarity Report.

**A discovery call is Rs 300 for 30 minutes**, every time one is booked, on any
plan, with no included allowance anywhere. There is no cap on how many.

*Updated later the same day:* the call was Rs 199, the same number as the monthly
plan. It is now Rs 300. That removes a real support problem as well as changing
the price -- a founder who had heard "Rs 199" had no way to tell whether they
were buying a month of Ally or a single call.

`CALL_PRICE_INR` is the only place the number lives, and every screen, quote and
answer reads from it, so the change was one line plus the copy. Answers 5, 144,
145, 146 and 245 were rewritten. Answer 5 also had a second error corrected: it
said the Rs 199 was paid "once, not every month".

This unblocked five answers -- 152, 153, 154, 155 and 169. All five describe the
product once Free is empty, so they carry
`status = 'answered_pending_product_change'` and stay out of the bot until
`PUBLIC_LAUNCH` is on. The one line of SQL that releases them (along with answer
5) is in `docs/PUBLIC-LAUNCH-CHECKLIST.md`.

Still open in group 13: **157** (team plans, D4), **158** (student or early-stage
discount -- no discount mechanism exists in the catalog at all, so this is a
build as well as a decision) and **159** (annual billing, D3).
