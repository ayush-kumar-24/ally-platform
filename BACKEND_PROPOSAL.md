# Backend proposal for this session's frontend features

Everything below is a **proposal only** — nothing has been implemented. Five features
built this session live entirely in browser `localStorage` right now (per-device, lost
on cache-clear, invisible to any admin/analytics view). This proposes moving them to
real backend persistence, matching the existing layered pattern in this codebase
(`app/<domain>/{models,repository,db_repository,service}.py` + `app/api/v1/<domain>/
{router,schemas,responses,dependencies}.py`, e.g. `app/consents/*`).

**Not proposing changes** to Recommendations (already reads the real report endpoint)
or the Dashboard/AllyChat UI tweaks (no data involved).

---

## Priority order

| # | Feature | Why this order |
|---|---|---|
| 1 | **Goals** | Simplest schema, most obviously wanted cross-device |
| 2 | **Achievements** | Same shape as Goals; the unlock-gate logic should move server-side too |
| 3 | **Vision** | Slightly richer shape (6 fixed territories + a summary) |
| 4 | **Frameworks usage/notes** | Lowest urgency — losing "last used" on cache-clear is low-stakes |

---

## 1. Goals

**Table** `goals`
```
id            bigint PK
founder_id    bigint FK -> founders.id, not null, indexed
title         text, not null
subtitle      text, nullable
created_at    timestamptz, default now()
updated_at    timestamptz, default now()
```

**Endpoints** (`app/api/v1/goals/router.py`, prefix `/goals`)
- `GET /goals` — list the founder's goals, newest first
- `POST /goals` — create `{title, subtitle}`
- `PATCH /goals/{id}` — update
- `DELETE /goals/{id}` — remove

**Frontend change**: `services/goals.js` swaps its `localStorage` calls for `get/post/patch/del` from `services/api.js` — same shape as `services/vision.js` would become, no UI changes needed.

---

## 2. Achievements

**Table** `achievements`
```
id            bigint PK
founder_id    bigint FK -> founders.id, not null, indexed
title         text, not null
description   text, nullable
category      text, nullable   -- Business / Leadership / Team / Impact / Personal
occurred_on   text, nullable   -- kept free-text ("Aug 2026"), matches current UI
created_at    timestamptz, default now()
```

**Endpoints** (`app/api/v1/achievements/router.py`, prefix `/achievements`)
- `GET /achievements` — list
- `POST /achievements` — create
- `PATCH /achievements/{id}` / `DELETE /achievements/{id}`

**The unlock gate** (`>= 15 total messages with Ally`) currently recomputes client-side
from `listConversations()`. Proposing it move server-side too:
- `GET /achievements/engagement` → `{message_count, unlocked}` — one authoritative
  number instead of the frontend re-summing every conversation's `message_count` on
  every page load, and a natural place to raise the threshold later without a
  frontend redeploy.

---

## 3. Vision

**Table** `vision_territories`
```
id            bigint PK
founder_id    bigint FK -> founders.id, not null
territory     text, not null   -- 'life' | 'business' | 'impact' | 'financial' | 'ideal_day' | 'legacy'
statement     text, not null
tag1          text, nullable
tag2          text, nullable
updated_at    timestamptz
UNIQUE (founder_id, territory)
```

**Table** `vision_summary` (one row per founder, or fold into `founders` directly —
simpler given it's exactly 3 fields)
```
founder_id    bigint PK/FK -> founders.id
target        text, nullable
current       text, nullable
unit          text, nullable
updated_at    timestamptz
```

**Endpoints** (`app/api/v1/vision/router.py`, prefix `/vision`)
- `GET /vision` — `{territories: {...}, summary: {...}}`, same shape the frontend already expects
- `PUT /vision/territories/{key}` — upsert one territory
- `PUT /vision/summary` — upsert the summary fields

---

## 4. Frameworks usage + notes

**Table** `framework_usage`
```
founder_id     bigint FK -> founders.id
framework_id   text, not null   -- matches data/frameworks.js ids, e.g. 'first-principles'
last_used_at   timestamptz, not null
note           text, nullable
PRIMARY KEY (founder_id, framework_id)
```

**Endpoints** (`app/api/v1/frameworks/router.py`, prefix `/frameworks`)
- `GET /frameworks/usage` — `{[framework_id]: {last_used_at, note}}`
- `POST /frameworks/{id}/use` — record opening it (idempotent-ish: just bumps the timestamp)
- `PUT /frameworks/{id}/note` — save/clear the note

The framework **content** itself (`data/frameworks.js` — titles, descriptions, steps,
diagrams) stays static on the frontend. Moving that server-side would only be worth it
if you want to edit framework copy without a redeploy; not proposing that now.

---

## What this needs from you before I touch anything

1. **Confirm you want this at all** — the localStorage version works today; this is
   purely "survive a cache-clear / show up on another device / be visible to admin
   tooling." If that's not a priority yet, skip it.
2. **Which of the 4 to do, and in what order** — I'd suggest starting with just Goals
   to prove the pattern, rather than all four at once.
3. **Database target** — per our earlier conversation, your local `backend/.env`
   `DATABASE_URL` points at the same Supabase project production uses. I'd want a
   migration tested against a separate project/branch first, not run directly against
   prod. (You rotated that database password after we discussed this — confirm the
   new one before I'd touch it either way.)
4. Each table needs an Alembic migration (`backend/alembic/versions/`, following the
   existing `YYYY_MM_DD_HHMM-<hash>_<description>.py` naming already in the repo) plus
   RLS policies matching the pattern the rest of the schema uses for founder-scoped
   rows.

Say which of the four (if any) to start with and I'll write the migration + router +
frontend swap for just that one, reviewed before moving to the next.
