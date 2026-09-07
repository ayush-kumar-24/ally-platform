# Turning on email and discovery calls

Everything is built. This is the config to add and the order to add it in.

**One command tells you where you stand at any point:**

```bash
python -m app.jobs.verify_notifications
```

It connects to the real SMTP server and the real Calendar API, so it proves
credentials work rather than that they are present. Exit 0 means a booked call
reaches the founder. Run it after every step below.

---

## Why a check exists at all

Every part of this degrades quietly, which is right at runtime and useless when
you are trying to find out whether it works:

* `send_email()` returns `False` and logs when `EMAIL_HOST` is unset — nothing raises
* the calendar falls back to the shared Meet room — bookings still succeed
* the reminder job reports zero counts — a scheduler sees a green run

**An entirely unconfigured deployment looks healthy.** That is how reminders went
months without a caller and nobody noticed.

---

## Step 1 — Email (Resend)

Use Resend, not a Google Workspace mailbox, even once you own Workspace. A
mailbox is throttled for automated mail, has no bounce handling or delivery
visibility, and ties your email to the same account as your calendar — one
suspension takes out both.

```
EMAIL_HOST=smtp.resend.com
EMAIL_PORT=587
EMAIL_USER=resend
EMAIL_PASSWORD=<Resend API key>      ← Secrets Manager, never plain env
EMAIL_FROM=GoXL Ally <ally@goxl.in>
EMAIL_USE_TLS=true
```

Two things that will otherwise waste an afternoon:

* `EMAIL_USER` is the literal word **`resend`**, not an address.
* The domain in `EMAIL_FROM` **must be verified in Resend**, or every send is
  rejected. `goxl.in` already is if login codes go through it.

Then:

```bash
python -m app.jobs.verify_notifications --send-to you@example.com
```

`--send-to` sends exactly one email, to the address you name. It never emails a
founder.

---

## Step 2 — Calendar (Google Workspace)

```
GOOGLE_CALENDAR_ID=<the Workspace calendar>
GOOGLE_CALENDAR_DELEGATED_USER=<the Workspace user, e.g. calls@goxl.in>
GOOGLE_CALENDAR_CREATE_MEET=true
GOOGLE_CALENDAR_INVITE_ATTENDEES=true
DISCOVERY_TIMEZONE=Asia/Kolkata
```

Service-account JSON goes in Secrets Manager, not plaintext.

**`GOOGLE_CALENDAR_DELEGATED_USER` is the one that matters.** A bare service
account has its own empty calendar. It can write to a calendar shared with it —
which is why it looks like it works — but it **cannot** create a Meet conference
or invite attendees. Both need it to act *as* a Workspace user.

That needs a Workspace admin to authorise the service account's client ID:

> Admin console → Security → API controls → Domain-wide delegation
> Scope: `https://www.googleapis.com/auth/calendar`

**Setting `CREATE_MEET=true` without the delegated user will fail.** The verifier
catches that combination and fails loudly rather than letting you find out when a
founder gets a call with no link.

### What changes when this lands

| | Before | After |
|---|---|---|
| Meet link | One shared room for every call, forever | A private room per call |
| Calendar invite | None | Google emails the founder directly |
| Founder's calendar | Nothing | The call appears, with Google's own reminders |

The shared room is worth fixing on its own: anyone ever sent that link can rejoin
any future call, and back-to-back bookings can walk into each other.

---

## Step 3 — Reminders

```bash
python -m app.jobs.discovery_reminders
```

Point EventBridge Scheduler at it **every 15 minutes**. Idempotent — each call
carries a sent-once flag, so running it often is harmless and running it rarely
means a founder gets the 1-hour reminder late or not at all.

**Alarm on non-zero exit:**

| Exit | Meaning |
|---|---|
| 0 | Ran fine, including "nothing was due" |
| 1 | Job failed — database unreachable, unexpected error |
| 2 | `EMAIL_HOST` not configured — nothing could have been sent |

2 is deliberately not 0. Without it a scheduler would report a perfect green run
every 15 minutes while no founder ever received a reminder.

---

## Step 4 — Prove it end to end

1. Book a discovery call as a founder.
2. Confirm it from `/admin/calls`.
3. The confirmation email should arrive within a minute. It is **transactional**
   and always sends regardless of the founder's notification preference, which
   makes it the cleanest proof.

**If nothing arrives, in this order:**

1. **Resend dashboard → Logs.** Not there → the app never called out. There and
   bounced → Resend says why.
2. **CloudWatch** for `Email (stub, not sent)` — that line means `EMAIL_HOST` is
   still empty in the running container.
3. Spam.

---

## What the founder gets at each stage

| Configured | The founder gets |
|---|---|
| Nothing | The joining link on the Discovery call page only |
| Email | Confirmation email + reminders (once the scheduler runs) |
| Email + Workspace | The above, plus a Google calendar invite and their own Meet room |

The in-app link works at every stage. That is deliberate — it is the one delivery
path that depends on neither mail nor Google.

---

## Fixed while building this

* **Event timezone was never sent to Google.** `start`/`end` carried a bare
  `dateTime` with no `timeZone`, so a naive timestamp would book at the calendar's
  default zone — a founder told one hour, nobody on the call at that hour. Now
  sent explicitly from `DISCOVERY_TIMEZONE`.
* **`htmlLink` could be handed out as a joining link.** It was the last fallback
  when no Meet link existed, and it is not a meeting — it opens the event in
  Google Calendar, which for anyone outside the organisation is a permission
  error. A founder clicking "Join call" and landing on "you need access" reads as
  a broken product. Removed, with a loud log if a call is ever created with no
  link, and a warning if a per-call room was requested but not granted.
