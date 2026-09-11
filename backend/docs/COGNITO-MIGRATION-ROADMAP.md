# Moving Ally's authentication to AWS Cognito

A roadmap, not an implementation. Read top to bottom — it takes about ten
minutes and tells you what we already have, what actually has to change, and in
what order.

---

## 1. The short version

Ally's login is **Supabase Auth** today. The plan is to replace it with **AWS
Cognito**. The backend was written for this swap: `app/core/auth/base.py` says
so out loud —

> "Swapping Supabase for Cognito later means adding one subclass and changing
> `AUTH_PROVIDER` — no route or service code changes."

That is true of **token verification**. It is not the whole job. The work that
remains is everything Supabase does for us *besides* signing a JWT: creating
users when an admin approves a waitlist entry, mailing one-time codes, storing
passwords, and telling us when an identity is deleted.

**Rough size: 3–4 weeks, one backend + one frontend engineer**, most of it in
phases 3 and 5 below.

---

## 2. What we have today

```
Frontend (Vite/React)                 Backend (FastAPI)
─────────────────────                 ─────────────────
supabase-js  ──(1) sign in──►  Supabase Auth
     │                              │
     │  (2) Supabase JWT            │
     ▼                              │
POST /api/v1/auth/session ──(3) verify JWT (JWKS / ES256)
     │
     ▼  (4) Ally's OWN access + refresh tokens
every later request
```

Two token worlds, deliberately kept apart:

| | Who issues it | Lives how long | Used where |
|---|---|---|---|
| **IdP token** | Supabase (later: Cognito) | minutes | once, at `POST /auth/session` |
| **Session token** | Ally's backend, HS256 with `SECRET_KEY` | 30 min access / 30 day refresh | every API request |

**This is the single most important fact in this document.** Only step 3 knows
which identity provider we use. Routes, services, RLS, and the refresh cookie
do not. That is why this migration is bounded.

### Pieces that already exist and stay

- `app/core/auth/base.py` — `AuthProvider` ABC, `AuthUser`, `AuthError`
- `app/core/auth/factory.py` — picks a provider from `AUTH_PROVIDER`
- `app/core/auth/tokens.py` — our access/refresh tokens (untouched)
- `app/core/auth/session_store.py` — refresh revocation / logout (untouched)
- `app/api/v1/auth/routes.py` — `/session`, `/refresh`, `/resume`, `/logout` (untouched)
- **RLS** — policies read `app.current_founder_uuid`, which *we* set in
  `set_founder_rls_context()`. It does **not** use Supabase's `auth.uid()`.
  Nothing about RLS changes.

---

## 3. What we must know before starting

Five things decide the shape of the project. Answer them first.

### 3.1 Passwords cannot be exported from Supabase

Supabase will not hand over password hashes. There are two ways to deal with
this, and the choice drives everything:

| Option | How it works | Cost |
|---|---|---|
| **A. Forced reset** (recommended) | Bulk-create every founder in Cognito, everyone signs in once with an emailed code and sets a new password | One email to all users; simple, finished in a day |
| **B. Lazy migration** | Run both providers; a Cognito `USER_MIGRATION` Lambda trigger validates against Supabase on first login and silently rehashes | No user disruption; dual-run for months, more code, more to get wrong |

Ally's user base is small and gated by a waitlist, and the app already mails
6-digit codes as a normal flow. **Option A is the right call.**

### 3.2 The founder id will not change — make sure of it

`founders.user_id` is a UUID that today holds the Supabase `auth.users` id, and
it is the `sub` of every token. Cognito mints its **own** `sub` UUID.

Nothing will line up unless we **carry the id across**. Cognito lets you set a
custom attribute at user creation, so on migration each Cognito user gets
`custom:founder_uuid` = the existing Supabase UUID, and the Cognito provider
reads `custom:founder_uuid` (falling back to `sub` for brand-new users) as
`AuthUser.id`.

Get this wrong and every founder logs in successfully to an empty account.

### 3.3 The FK to `auth.users` is already gone

Historical: `founders.user_id` used to be a real FK to Supabase's `auth.users`
with `ON DELETE CASCADE`. It was dropped when the database moved off Supabase's
own Postgres (see `app/models/__init__.py` and `app/api/v1/webhooks/supabase.py`).
So **no schema change is needed** — `user_id` is now a plain UUID column.

### 3.4 Three things depend on Supabase beyond token verification

These are the real work. Each needs a Cognito equivalent:

| Today | File | Cognito equivalent |
|---|---|---|
| Admin creates a user on waitlist approval (service-role key) | `app/services/supabase_admin.py` → `create_auth_user()` | `AdminCreateUser` via boto3 |
| Emailed 6-digit OTP + "set your password" | `frontend/src/services/auth.js` | `ForgotPassword` / `AdminCreateUser` invite code, or a custom-auth Lambda |
| Auth webhook on identity deletion → schedules erasure | `app/api/v1/webhooks/supabase.py` | Cognito has **no** delete webhook. Replace with an EventBridge rule on the CloudTrail `AdminDeleteUser` event, or make admin deletion go through our own API |

3.4's third row is the one people forget. Don't.

### 3.5 Cognito's OTP flow is not Supabase's

Supabase has one clean call: `signInWithOtp` → `verifyOtp`. Cognito's nearest
equivalents are clumsier — the invite flow (`AdminCreateUser` mails a temporary
password, user must change it on first sign-in) or `ForgotPassword` (mails a
code, user sets a new password). Both are usable; neither is identical.

**Decide early:** are we keeping a passwordless-feeling first login, or are we
switching to "invite email with a temporary password"? The frontend login page
looks different in each case. Recommended: use `ForgotPassword`-style codes so
the current two-step UI ("enter code, choose password") survives unchanged.

---

## 4. Requirements

### AWS

- A **Cognito User Pool** (one per environment: dev, staging, prod)
  - Sign-in alias: **email**. Self-registration **disabled** (Ally is waitlist-gated —
    this mirrors the current Supabase setting exactly)
  - MFA: optional now, `ON` for admin accounts later
  - Password policy: 12+ chars, agreed with the team
  - Custom attribute: `custom:founder_uuid` (string, mutable=false)
  - Token expiry: access/ID token 5 min — ours are what carry the session
  - Email: **SES**, from Ally's verified domain (the Cognito default sender is
    capped at 50 mails/day and is not production-usable)
- An **app client**: public, no client secret (the SPA cannot keep one), auth
  flows `ALLOW_USER_SRP_AUTH` + `ALLOW_REFRESH_TOKEN_AUTH`
- An **IAM role/user** for the backend with *only* `cognito-idp:AdminCreateUser`,
  `AdminGetUser`, `AdminDeleteUser`, `AdminUpdateUserAttributes` — scoped to the
  one pool ARN. Same containment discipline as `supabase_admin.py` has now.

### Config (`app/core/config.py`)

```bash
AUTH_PROVIDER=cognito
COGNITO_REGION=ap-south-1
COGNITO_USER_POOL_ID=ap-south-1_xxxxxxxxx
COGNITO_APP_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
# JWKS is derived, not configured:
# https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json
```

Frontend: `VITE_COGNITO_REGION`, `VITE_COGNITO_USER_POOL_ID`,
`VITE_COGNITO_APP_CLIENT_ID`.

### Non-negotiables (these hold today; they must still hold after)

1. **The backend never sees, stores, or transports a password.** True with
   Supabase; must stay true with Cognito.
2. **The refresh token stays in an HttpOnly cookie**, never in `localStorage`.
3. **A misconfigured deployment refuses to serve** rather than quietly
   authenticating everyone — the factory raises `RuntimeError`, it does not
   fall back to `dev`.
4. **Tokens are verified by signature and claims only** — never by calling
   Cognito on each request.
5. `AUTH_PROVIDER=dev` stays blocked in production.

---

## 5. Verification: what the Cognito provider must check

`CognitoAuthProvider.verify_token()` is ~80 lines and mirrors
`supabase_provider.py` almost exactly (fetch JWKS, match `kid`, bounded
refresh, decode). Differences worth writing down:

| Check | Supabase | Cognito |
|---|---|---|
| Algorithm | ES256 (+ legacy HS256) | **RS256 only** — reject everything else, especially `none` |
| `iss` | not pinned | **must equal** `https://cognito-idp.{region}.amazonaws.com/{pool_id}` |
| `aud` | `authenticated` | the **app client id** |
| `token_use` | n/a | **must be `"id"`** — an access token is not an identity |
| Subject | `sub` | `custom:founder_uuid`, falling back to `sub` |
| Required claims | `aud`, `exp`, `sub` | same, plus `iss` and `token_use` |

Use the **ID token**, not the access token: only the ID token carries `email`
and our custom attribute.

---

## 6. The roadmap

### Phase 0 — Decide (2 days)
Sign off on §3.1 (forced reset), §3.2 (carry the UUID), §3.5 (which OTP flow).
Create the dev user pool. **Nothing is coded until these three are settled.**

### Phase 1 — The provider (3 days)
- `app/core/auth/cognito_provider.py`, subclassing `AuthProvider`
- Register `cognito` in `factory.py`; add the settings above
- Tests: valid token, wrong `iss`, wrong `aud`, `token_use=access`, expired,
  `alg=none`, unknown `kid`, JWKS-fetch failure keeps serving cached keys
- **Exit:** a hand-made Cognito token authenticates against a local backend.
  Nothing else in the app has changed.

### Phase 2 — The frontend (4 days)
- Swap `supabase-js` for `amazon-cognito-identity-js` (or AWS Amplify Auth)
  inside `services/supabaseClient.js` → rename to `services/idpClient.js`
- `services/auth.js` keeps **the same exported functions** — `sendEmailOtp`,
  `verifyOtpAndSetPassword`, `signInWithPassword`, `logout`. Only their bodies
  change. `Login.jsx` should need no edits.
- **Exit:** the full login flow works end to end against the dev pool.

### Phase 3 — Admin + lifecycle (4 days)
The part that is genuinely new:
- `app/services/cognito_admin.py` — the mirror of `supabase_admin.py`. Keep the
  same narrow scope: one file, one credential, `create_auth_user()` and nothing
  generic.
- Point `app/services/waitlist.py` at it
- Replace the deletion webhook (§3.4): the simplest safe path is to route admin
  deletion through our own API, which deletes in Cognito *and* calls
  `PrivacyService.request_account_deletion()` — one path, no webhook to miss
- **Exit:** approve a waitlist entry → the founder receives a real email and can
  sign in. Delete them → erasure is scheduled.

### Phase 4 — Data migration (2 days)
- Script: read every `founders.user_id` + email → `AdminCreateUser` in the prod
  pool with `custom:founder_uuid` set and `MessageAction=SUPPRESS` (no mail yet)
- **Dry-run first**, on a copy. Verify every founder has exactly one Cognito
  user and the UUIDs match. This is reconciliation, not hope.
- **Exit:** counts match, spot-checks pass, nobody has been emailed.

### Phase 5 — Cutover (1 day + a watched week)
1. Announce: "you'll set a new password on your next sign-in"
2. Deploy backend with `AUTH_PROVIDER=cognito`, frontend with the new client
3. Existing sessions **keep working** — they run on our own tokens, which
   Cognito has nothing to do with. Only *new logins* hit Cognito. This is the
   quiet advantage of the two-token design.
4. Watch 401 rates, `/auth/session` failures, and password-reset completions
5. Keep Supabase Auth alive and untouched for **30 days**

### Phase 6 — Decommission (1 day)
Remove `supabase_provider.py`, `supabase_admin.py`, the webhook route, the
`SUPABASE_*` auth settings, and `@supabase/supabase-js`. Delete the Supabase
service-role key. **Only after 30 quiet days.**

---

## 7. Rollback

Through the end of phase 5, rollback is: set `AUTH_PROVIDER=supabase`, redeploy
the previous frontend build. Supabase users were never deleted, so it is a
config change, not a restore.

The point of no return is **phase 6**, not the cutover. Do not rush it.

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| Founder ids don't carry across → everyone lands in an empty account | §3.2; phase 4 reconciliation is the gate |
| Cognito emails land in spam at cutover | SES on a verified domain with DKIM, warmed before phase 5 |
| Deletion webhook has no replacement → GDPR/DPDP erasure silently stops | Phase 3 replaces it in the same PR that switches the provider |
| Someone leaves `AUTH_PROVIDER=dev` in a deployed env | Already guarded — the factory refuses it in production. Keep that test. |
| Cognito's OTP flow forces a login-page redesign | Settled in phase 0, before any code |

---

## 9. Files this touches

```
backend/app/core/auth/cognito_provider.py     NEW
backend/app/core/auth/factory.py              + one branch
backend/app/core/config.py                    + COGNITO_* settings
backend/app/services/cognito_admin.py         NEW (mirrors supabase_admin.py)
backend/app/services/waitlist.py              swap the create_auth_user import
backend/app/api/v1/webhooks/supabase.py       REPLACED (see phase 3)
backend/scripts/migrate_users_to_cognito.py   NEW, one-shot
frontend/src/services/idpClient.js            REPLACES supabaseClient.js
frontend/src/services/auth.js                 same exports, new bodies
frontend/package.json                         -@supabase/supabase-js +cognito sdk
```

**Untouched, and that is the measure of whether we did this right:**
`tokens.py`, `session_store.py`, `dependencies.py`, `auth/routes.py`, every
route, every service, and all RLS.
