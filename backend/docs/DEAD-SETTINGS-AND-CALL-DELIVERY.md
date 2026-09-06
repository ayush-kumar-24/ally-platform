# Two things found while writing the help answers

**Status as of 2026-09-05 — most of this is now done.** What remains needs
access we do not have from here (an AWS console, a Google Workspace account, a
scheduler). Table first, detail below.

| # | Thing | Status |
|---|---|---|
| 1 | Join link never reached the founder | **Fixed** — shown on the calls page |
| 2 | "Paid plans include a call each month" | **Fixed** — no plan ever included one |
| 3 | Reminder job had no caller | **Fixed** — `POST /internal/jobs/send-call-reminders` |
| 4 | `login_notifications` did nothing | **Built** — new-device sign-in emails |
| 5 | `session_timeout_minutes` did nothing | **Removed** from the whole surface |
| 6 | `meeting_reminders` duplicated a real switch | **Removed** |
| 7 | "Notifications" switch did nothing | **Hidden** until it controls something |
| 8 | `private_mode` described a data use we do not have | **Removed** |
| 9 | Host calendar is a personal Gmail | **Yours** — needs a Workspace account |
| 10 | `EMAIL_HOST` unset, so nothing sends | **Yours** — one env var |
| 11 | Nothing runs the scheduler | **Yours** — point cron at the job above |
| 12 | The four reminder settings did nothing | **Removed 2026-09-05** — team decision |

Everything marked *Yours* is infrastructure. Nothing in the repo can do it.

---

# Part 1 — How a discovery call actually reaches a founder

**Short version: it now does, via the app.** Until 2026-09-05 a founder could
book and pay, an admin could confirm, and there was no path at all by which the
joining link reached them. The app now shows it. Email is still not sending, and
the calendar is still a personal Gmail — both below.

## What we use

**Not Calendly.** A docstring in `app/api/v1/discovery/routes.py` says "booking
runs through Calendly in production" — that is stale and was never true. Nothing
in the codebase talks to Calendly.

What we actually have is our own booking flow on top of **Google Calendar**:

1. We generate a candidate grid of slots (10:00, 11:00, 14:00, 15:00, 16:00,
   weekdays only, opening one business day out).
2. If Google Calendar is configured, we filter that grid against the host
   calendar's free/busy so we never offer a time the host is booked.
3. The founder picks one. This creates a **pending request** — no payment gate,
   no calendar event, nothing consumed.
4. An admin confirms it from `/admin/calls`. **Only then** is the calendar event
   created and the founder told.

Step 4 is deliberate: the previous flow made a Google Meet before writing the
row, so a failed insert left a real meeting on the calendar that nobody would
attend.

## The host calendar is a personal Gmail, and that breaks two things

`GOOGLE_CALENDAR_ID` is `14aarush9@gmail.com` — a personal account, not
Workspace. Two features need Workspace, so both are off:

| Setting | State | Consequence |
|---|---|---|
| `GOOGLE_CALENDAR_CREATE_MEET` | off | We cannot auto-generate a per-call Meet link. Personal Gmail rejects it outright ("Invalid conference type value"). |
| `GOOGLE_CALENDAR_INVITE_ATTENDEES` | off | We cannot add the founder as an attendee, so **Google never emails them an invite**. |

Because auto-Meet is off, every discovery call uses one permanent room:

```
GOXL_MEETING_URL = https://meet.google.com/bxx-nczh-rki
```

**The same link for every call, for every founder, forever.** Anyone who has ever
been sent it can rejoin any future call. Two founders booked back to back can
overlap in the room.

## And the app doesn't tell them either

With Google invites off, the app is supposed to deliver the link itself. It
cannot:

* **Email is off.** `EMAIL_HOST` is not set, so `send_email()` runs in stub
  mode — it logs the message and returns `False`. The booking confirmation is
  written and never sent.
* ~~**The app doesn't show it.**~~ **FIXED 2026-09-05.** `meeting_link` was in
  the API response the whole time and simply never rendered. The calls list now
  shows a **Join call** button on a confirmed booking, and tells a founder with a
  pending one that the link follows confirmation. Cancelled calls never offer a
  way in. This is the one delivery path that cannot silently fail, because it
  depends on neither mail nor Workspace.
* ~~**Reminders never fire.**~~ **HALF FIXED 2026-09-05.** `send_due_reminders()`
  now has a caller: `POST /internal/jobs/send-call-reminders`, same shared-secret
  auth as the other sweeps. **Point your scheduler at it every 15 minutes.** It
  is idempotent, and its response reports `email_configured` so a scheduler log
  shows plainly when the real blocker is still `EMAIL_HOST`.

So: booked, paid, confirmed — and, until today, silent. The app now speaks. Mail
still does not.

## What needs deciding

1. **Move the host calendar to a Google Workspace account.** This is the root
   fix. It turns on per-call Meet links and lets Google send the invite itself —
   which also gives the founder a calendar entry and Google's own reminders, for
   free, and removes our dependence on our own SMTP for the critical path.
2. **Set `EMAIL_HOST`** so the confirmation actually sends. Needed regardless.
3. ~~Show the link in the app.~~ **Done.**
4. **Schedule the reminder job** — `POST /internal/jobs/send-call-reminders`,
   every 15 minutes, with the `X-Internal-Secret` header. Harmless before email
   works; useless until it does.

Item 3 has landed, so a paid call can now reach the person who paid for it. Items
1 and 2 are what make it reach them *without them having to come and look*.

**One more thing worth deciding.** Every call currently shares the permanent room
link, so anyone ever sent it can rejoin any future call, and two founders booked
back to back can walk into each other. Moving to Workspace (item 1) fixes this as
a side effect, because each booking then gets its own Meet link.

---

# Part 2 — Seven settings that do nothing

Each of these validates, persists and reads back through a working API. **None
is read by any code anywhere.** Grep confirms zero consumers outside the settings
module itself.

| # | Setting | Verdict | Status |
|---|---|---|---|
| 1 | `session_timeout_minutes` | Drop it | **Removed 2026-09-05** |
| 2 | `login_notifications` | Build it | **Built 2026-09-05** |
| 3 | `reminder_time` | Build after email | **Removed 2026-09-05** |
| 4 | `daily_reminders` | Build with #3 | **Removed 2026-09-05** |
| 5 | `task_reminders` | Build with #3 | **Removed 2026-09-05** |
| 6 | `goal_reminders` | Build with #3 | **Removed 2026-09-05** |
| 7 | `meeting_reminders` | Merge into the call switch | **Removed 2026-09-05** |
| — | `in_app_all` ("Notifications") | Hide until real | **Hidden 2026-09-05** |

**All eight are now dealt with.** Items 3–6 were removed on 2026-09-05 by team
decision — *"if it does not work, just remove it; if we need it, we will build
it."* The section they lived in went with them, and so did
`PATCH /settings/reminders`, which had nothing left to write.

The daily digest they were the shape of is still a sensible feature. It just no
longer has four dormant settings sitting in the schema pretending it exists. If
it gets built, the settings come back with it.

*(`private_mode` was the eighth. Removed 2026-09-05 — it described a data use we
do not have.)*

## Taken one at a time

### 1. `session_timeout_minutes` — dropped

A founder setting this to 5 minutes gets exactly the same 30-day session as
everyone else. Sessions are governed by a 30-minute access token and a 30-day
rotating refresh cookie, and nothing consults this number.

**Recommendation: delete it.** A security setting that silently does nothing is
worse than not offering one — it is a false assurance, and the sort of thing that
looks very bad in a security questionnaire. There is no real founder demand for
configurable session length, and implementing it properly means per-founder token
lifetimes, which is a lot of machinery for a setting nobody asks for.

If you would rather keep a security control here, "sign out everywhere" is the
one founders actually want (question 199) and it is far simpler: revoke that
founder's refresh tokens.

### 2. `login_notifications` — built

Right now we send no sign-in email at all. That is why help answer 253 tells
founders that an email claiming "someone signed in" is **not from us** and is
probably phishing.

That answer is correct today, and it is fragile: the day anyone switches this on,
that answer becomes dangerous advice.

**Done, and new-device only.** An email on every sign-in is noise people learn to
delete unread, so the one that matters gets deleted too.

`app/services/login_notifications.py`. The device is a deliberately coarse
fingerprint — browser/OS family plus the /24 of the IP — because a stricter one
would email a founder every browser update and every time their phone changed
cell, and be ignored within a month. History lives in `audit_logs`, which already
had the right columns, so there was no migration; it also means sign-ins show up
in a founder's data export, where they would expect them.

A founder's *first* device is learned silently — emailing someone seconds after
they sign up is alarming and tells them nothing.

The email deliberately **contains no link**. A security email that asks you to
click something teaches founders to click links in security emails, which is
exactly how the phishing it is meant to catch works. That also keeps "our emails
never ask you to click" true, which is a test a founder can actually apply.

Help answer 253 has been rewritten. It used to say we never send sign-in emails
and that any such email was phishing — true until today, and dangerous the moment
this shipped.

### 3–6. `reminder_time`, `daily_reminders`, `task_reminders`, `goal_reminders`

These are the reminder model, and they are worth building **but only after there
is something to send them with**. They are downstream of Part 1: we have no
working outbound email, and no scheduler running.

The sequence matters:

1. Get `EMAIL_HOST` set and the scheduler running (Part 1, items 2 and 4).
2. Then a daily digest at `reminder_time` — *"three things you said you'd do
   today"* — with `task_reminders` / `goal_reminders` choosing what goes in it.
3. Then surface all of it on the Profile page.

**Recommendation: build, in that order.** This is the answer to help question 137,
where Ally has to admit it cannot chase you — *"it does not email you, and it
cannot notice on a Thursday that you have not opened it since Monday."* That is
the single biggest hole in the product's ability to create a habit, and these four
settings are already modelled, validated and stored, waiting for it.

`reminder_time` defaulting to 09:00 and being founder-local is already right.

### 7. `meeting_reminders` — removed

This duplicates the email switch on the Profile page, which already gates the 24h
and 1h discovery-call reminders. Two flags for one thing.

**Done.** Deleted; the switch on the Profile page is now the only one.

### `in_app_all` — hidden

The "Notifications" switch on the Profile page. It saves, and there are no in-app
notifications for it to control, so flipping it changes nothing.

**Done.** Hidden, not deleted: the flag, the API and the stored value are all
still correct, so restoring it when in-app notifications exist is a one-line
change. A visible switch that does nothing teaches founders that our settings are
decorative, which is expensive on a page whose whole job is letting them change
something.

---

## What is left, and it is all yours

1. **Set `EMAIL_HOST`.** One env var. Nothing outbound sends without it — not the
   call confirmation, not the reminders, not the new-device notice that is now
   built and waiting. This is the single highest-value thing on the list.
2. **Move the discovery-call calendar to a Workspace account.** Gets per-call
   Meet links (so founders stop sharing one permanent room) and Google's own
   invites and reminders, for free.
3. **Point a scheduler at `POST /internal/jobs/send-call-reminders`**, every 15
   minutes, with the `X-Internal-Secret` header.
4. **Decide on the daily digest** (settings 3–6). It is the answer to Ally not
   being able to chase anyone, which is the biggest hole in its ability to build
   a habit — but it is a feature, so it is your call, not a bug fix.
