# Share links and PUBLIC_APP_URL — three settings, two live bugs

Both bugs come from **one wrong environment variable**. Fixing it needs no code
deploy — the code change below is already in, and this is the configuration that
goes with it.

---

## The three settings

| Setting | Production value | What breaks without it |
|---|---|---|
| `PUBLIC_APP_URL` | `https://app.goxlally.ai` | Calendar OAuth returns a founder to a 404 |
| `SHARE_LINK_BASE_URL` | `https://app.goxlally.ai` | Share links are long but still work |
| `PUBLIC_API_URL` | `https://api.goxlally.ai` | Only matters if the two above are unset |

---

## Bug 1 — share links pointed at the marketing site

`PUBLIC_APP_URL` is set to `https://goxlally.ai`, which is the **marketing
site**. Share links were built as `<PUBLIC_APP_URL>/r/<token>`, so every founder
who pressed Share got:

```
https://goxlally.ai/r/<token>
  → 308 redirect to www.goxlally.ai/r/<token>
  → 404, the marketing site's "This page took a wrong turn"
```

**The `/r/` path was never the problem.** It is a rewrite declared in
`frontend/vercel.json`, it is live, and it works. Verified against production:

```
GET https://app.goxlally.ai/r/definitelynotarealtoken
→ {"error":"HTTPException","message":"This shared report is not available."}
```

That is this API answering *through* the rewrite. Right path, wrong host.

**Fixed in code:** `share_url_for` no longer reads `PUBLIC_APP_URL` at all. It
uses `SHARE_LINK_BASE_URL` when set, and otherwise the direct API URL, which
resolves with no rewrite anywhere.

---

## Bug 2 — the calendar OAuth return lands on a 404

The same wrong value, a completely unrelated feature. After a founder connects
their calendar, the API redirects them to `<PUBLIC_APP_URL>/app/plan`:

```
goxlally.ai/app/plan?calendar=connected      → 404
app.goxlally.ai/app/plan?calendar=connected  → 200
```

The connection is **saved before the redirect**, so this looks like it works —
the calendar really is connected — and then dumps the founder on a 404 at the
final step. That is why calendar sync was reported as working while feeling
broken.

**This one is not fixed in code, because the code is right.** It needs the
environment variable corrected.

---

## What to set

```
PUBLIC_APP_URL=https://app.goxlally.ai
SHARE_LINK_BASE_URL=https://app.goxlally.ai
PUBLIC_API_URL=https://api.goxlally.ai
```

`PUBLIC_APP_URL` is the one that matters most: it is currently wrong and is
breaking the calendar return today.

`SHARE_LINK_BASE_URL` is **opt-in on purpose**. Leaving it empty gives share
links like:

```
https://api.goxlally.ai/api/v1/reports/shared/<token>/view
```

which is uglier and resolves with no rewrite at all. Set it only to an origin
where the `/r/` rewrite genuinely exists — app.goxlally.ai does. The failure mode
is silent: an origin without the rewrite produces links that look perfect and
404, and nothing in the codebase can tell the difference. That silence is exactly
how this went unnoticed.

---

## Verifying after the change

```bash
# 1. Create a share from the app, copy the link. It should read:
#    https://app.goxlally.ai/r/<token>

# 2. Open it in a private window — no session — and expect the report to render.

# 3. Connect a calendar from Plan Your Day. The redirect at the end should land
#    on the plan page, not a 404.
```

Verified locally end to end before shipping: create → 201 with the pretty URL,
visitor with no auth → 200 with the real HTML report and `noindex` intact,
revoke → 204, visitor after revoke → 404.

---

## Existing share links

`share_url` is written onto the row when the share is created, so rows made
before this fix still carry the broken marketing-site URL. Links already sent to
someone cannot be repaired — those are in an inbox. This makes the app show a
working URL for shares that already exist:

```sql
UPDATE report_shares
   SET share_url = 'https://app.goxlally.ai/r/' || share_token
 WHERE share_url LIKE '%goxlally.ai/r/%'
   AND share_url NOT LIKE '%app.goxlally.ai%';
```

**Note:** production reported `total_shares: 0` on 2026-09-06, so there may be
nothing to update. If that count is still zero after a founder creates a share,
that is a separate problem worth chasing — it would mean share creation is
failing silently.

---

## Do not "clean up" frontend/vercel.json

It looks like leftover config from a migration that never happened. It is live
and load-bearing: `app.goxlally.ai` is served by **Vercel**, and that file
carries the `/api/*` proxy the entire app depends on, this `/r/:token` rewrite,
and the SPA fallback. Deleting it takes the app down.

```
app.goxlally.ai   Server: Vercel      X-Vercel-Cache: HIT
api.goxlally.ai   server: uvicorn     Via: CloudFront
goxlally.ai       Server: Vercel
```
