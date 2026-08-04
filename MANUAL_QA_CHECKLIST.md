# Ally — Manual QA Checklist

Release-candidate pass. Every item below was verified programmatically; this sheet is for
confirming it by hand, and for catching what automation cannot judge (copy, feel, layout).

---

## 0. Setup

```bash
python "C:/Users/ayush/OneDrive/Desktop/Claude Code/Ally-Platform/ally-platform/backend/scripts/run_dev.py" --port 8001
```

```bash
cd "C:/Users/ayush/OneDrive/Desktop/Claude Code/Ally-Platform/ally-platform/frontend" && npm run dev
```

Backend `http://127.0.0.1:8001` · Frontend `http://localhost:5173`

**Test accounts** (dev auth: present the founder's `user_id` as the bearer token to `POST /api/v1/auth/session`):

| Email | Plan | Panel role | founder_id |
|---|---|---|---|
| priya@northstar.in | starter | super_admin | 3704 |
| rahul@fernway.co | pro | admin | 3705 |
| aisha@tildehq.com | free | support | 3706 |

**Watch continuously:** DevTools Console (expect **zero** errors) · Network (expect no 5xx; 401→200 retry pairs are the token refresh working; bare 404s on `/diagnosis/current`, `/intelligence/reports/latest` are legitimate "nothing yet").

---

## 1. Landing → Login → Profile

| Check | API | Expect | DB | Failure modes |
|---|---|---|---|---|
| Landing renders, no console errors | — | Hero, pipeline rail, pricing | — | Font flash; rail overflow <1024px |
| Google login | `POST /auth/session` | 200 `{access_token, refresh_token, founder, provisioned:true}` | `founders` row created on first login | `provisioned:false` ⇒ no founder row ⇒ everything downstream 404s |
| Session survives reload | `POST /auth/resume` | 200, new token pair | old refresh jti revoked | Rotation means a refresh token works **once** |
| Profile loads real data | `GET /profile` | Your name/email — **never** "Ayush Sharma" or "Rahul Varma" | — | *Regression #6/#7 — check carefully* |
| Edit → Save | `PATCH /profile` | 200; toast "Profile saved ✓" | `founders.full_name`, `linkedin_url` | *Was a no-op (#8). Reload and confirm it stuck.* |
| Phone / Location / Email | — | **Read-only by design** — no endpoint persists them | — | If editable again, #C regressed |

---

## 2. Consent

| Check | API | Expect | DB |
|---|---|---|---|
| Accept terms + diagnosis | `POST /consents` | 200/201 | new `founder_consents` row (append-only) |
| Double-submit | `POST /consents` ×2 | second is rejected/deduped | no duplicate row |
| History | `GET /consents` | full ledger, newest first | — |

---

## 3. Diagnosis → Report

⚠️ **The diagnosis asks all 330 questions** (Product Decision A). Budget accordingly.

| Check | API | Expect | Failure modes |
|---|---|---|---|
| Start | `POST /diagnosis/start` | 200 + first question | — |
| Answer | `POST /diagnosis/answer` | `{next_question, is_complete}` | Sends `answer_text`, no `session_id` |
| Resume mid-way | `GET /diagnosis/current` | same question after reload | Session is server-side |
| Completion | — | `is_complete:true` | Only after the bank is exhausted |
| Report | `GET /intelligence/reports/latest` | 200 | 404 = none yet (valid) |
| Founder / Business DNA | `GET /reports/{id}/founder-dna` | facts render as "Community Builder · Connection" | No `[object Object]`; no `narrator: template` |
| Next steps | `GET /reports/{id}/recommendations` | server recommendations | Falls back to static list if empty |

**Empty states** (before any diagnosis) — confirm all four read correctly:
`/app/founder-dna` "Your Founder DNA isn't ready yet" · `/app/business-dna` "Your Business DNA…" ·
`/app/report` "Your report…" · `/app/next-steps` "Your next steps…"
*Regression check: none should say "Report DNA" or "Next steps DNA".*

---

## 4. Dashboard

| Check | API | Expect |
|---|---|---|
| Greeting | `GET /profile` | Time-appropriate + **your real first name** |
| Health cards | `GET /dashboard/business-health` | `available:false` ⇒ honest empty state, not a fabricated score |
| Plan badge (top bar + sidebar) | `GET /profile` | "Ally Starter" / "Ally Pro" — **not** "Ally Free" (#10) |
| Pro user | — | Upsell button reads "Manage plan" |

---

## 5. Plan Your Day *(Starter+; heavily repaired — test hardest)*

| Check | API | Expect | DB |
|---|---|---|---|
| Free user | — | PlanGate upsell | — |
| Page load | `GET /planning/plans` → `GET /planning/plans/{id}` | "Loading your plan…" then list | auto-creates a plan on first visit |
| Type + "Plan my day" | `POST /planning/goals/{gid}/tasks` **201** | task appears with title/priority/goal | `planning_tasks` row |
| **Watch for** | — | URL must **never** contain `/plans/undefined/` | *(#3)* |
| Tick checkbox | `PATCH /planning/tasks/{id}` | instantly moves to Completed; ring updates | `status='done'`, `completed_at` stamped |
| Un-tick completed row | `PATCH …` | returns to active | `status='todo'` |
| Keyboard: Tab to a completed row, press Enter | same | toggles | *(#18)* |
| Double-click submit | — | button disables, shows "Adding…" | exactly one row |
| Reload | — | everything persists | server is the only copy |

---

## 6. Ally Chat

| Check | API | Expect |
|---|---|---|
| New conversation | `POST /chat/conversations` | 201 |
| Send message | `POST /chat/message` | **Today: `ok:false`** → honest message "I can't answer properly yet — I ground every reply in your diagnosis…" |
| **Must never appear** | — | raw text `prompt: ('diagnosis_answer_grounded.standard', …)` |
| Free-tier voice | — | blocked (paid only) |
| Archive | `DELETE /chat/conversations/{id}` | disappears from list |

---

## 7. Discovery Call

| Check | API | Expect |
|---|---|---|
| Quote before clicking | `GET /plans/me/call-quote` | Free `{is_free:false, price_inr:300, free_remaining:0}` · Pro `{is_free:true, free_remaining:2}` |
| Book within allowance | `POST /discovery/book` | 201; `free_remaining` decrements |
| Book beyond allowance | `POST /discovery/book` | **402**, button reflects ₹300 |
| Slots | `GET /discovery/slots?days=7` | 200 |

---

## 8. Credits, Plans, Billing

| Check | API | Expect |
|---|---|---|
| Balance | `GET /plans/me` | Free 120/4000 · Starter 180/6000 · Pro 240/8000 |
| Pricing cards | `GET /plans` | tier count from API; no phantom 4th column |
| Responsive | — | cards reflow at 375px, no crush |
| Ledger | `GET /credits/me/transactions` | append-only, newest first |

---

## 9. Settings & Privacy

| Check | API | Expect | ⚠️ |
|---|---|---|---|
| Preferences | `GET/PATCH /settings/preferences` | persists | |
| Export | `GET /privacy/export` | JSON downloads | safe |
| Restrict processing | `POST /privacy/restrict` | reversible pause | sets `processing_restricted_at` |
| Withdraw consent | `POST /privacy/withdraw` | account stays, processing stops | **destructive — use a throwaway** |
| Delete account | `DELETE /privacy/account` | 30-day scheduled erasure | **destructive — use a throwaway** |

---

## 10. Notifications

| Check | API | Expect |
|---|---|---|
| Bell (empty) | `GET /notifications` | "You're all caught up" — **not** 3 mock items (#11) |
| Clear all | `POST /notifications/read-all` | clears **and stays cleared after reload** |

---

## 11. Admin *(priya = super_admin)*

| Page | API | Expect |
|---|---|---|
| `/admin` | `GET /admin/metrics` | "Signed in as … role super admin"; cards render |
| `/admin/users` | `GET /admin/users` | search by name/email/phone/business/ID; pagination; sort |
| Founder detail | `GET /admin/users/{id}` | profile, credits, timeline |
| Credits | `POST /admin/users/{id}/credits` | balance moves; ledger row appended |
| `/admin/usage` | `GET /admin/usage` | tokens + estimated cost |
| `/admin/system` | `GET /admin/flags`, `/admin/broadcasts` | flag create/toggle; broadcast publish |
| `/admin/audit` | `GET /admin/audit-log` | every write above appears, immutable, newest first |

### RBAC — verified, re-confirm by hand

| Action | super_admin | admin | support |
|---|---|---|---|
| View users | ✅ 200 | ✅ 200 | ✅ 200 |
| Adjust credits | ✅ | ❌ 403 | ❌ 403 |
| Bulk credits | ✅ | ❌ 403 | ❌ 403 |
| Feature flags | ✅ | ❌ 403 | ❌ 403 |
| Broadcasts | ✅ | ❌ 403 | ❌ 403 |

Capability counts: **super_admin 13 · admin 6 · support 3**.

---

## 12. Cross-cutting

- **Mobile 375px** — verified 0px overflow on `/app`, `/app/plan`, `/app/profile`, `/app/billing`, `/app/ally-chat`, `/app/discovery-call`, `/app/report`, `/admin`, `/admin/users`, `/admin/system`. Re-check sidebar drawer ≤1024px and the plan FAB.
- **Error boundary** — force a failure (stop the backend, reload). Expect a recovery card. ⚠️ *Known:* the boundary is shared across `/app` and does not reset on navigation, so one crash affects sibling routes until reload.
- **Offline / backend down** — pages should degrade to empty or error states, never a white screen.
- **Logout** — `POST /auth/logout` revokes the refresh token; protected routes then 401.

---

## 13. Regression watchlist (the bugs fixed this pass)

1. Plan Your Day checkbox / "Plan my day" / "Add task" all work — no `setActiveGoals is not defined`
2. No request to `/planning/plans/undefined/goals`
3. No "Ayush Sharma", "Rahul Varma", "BrightLoom", or "Nexus Robotics" anywhere
4. Plan badge matches the real plan
5. Profile Save persists across reload
6. Bell shows real notifications
7. Console clean on Plan Your Day (no `<defs>` / `<linearGradient>` errors)
8. Empty states don't say "Report DNA" / "Next steps DNA"
9. Greeting matches time of day
