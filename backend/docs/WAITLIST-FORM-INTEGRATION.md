# Wiring the waitlist form on join.goxlally.ai

The endpoint is live. Nothing posts to it yet, so the admin queue is empty --
correct, not broken. This is what the form on the waitlist site has to send.

The site is a separate codebase, which is why this note exists here rather than
the change being made: this repository owns the contract, the other one owns the
form.

---

## The endpoint

```
POST https://api.goxlally.ai/api/v1/waitlist
Content-Type: application/json
```

No token. It is the one route in the API anybody on the internet may write to,
by design -- the whole point is that someone with no account can ask for one.
See the module docstring in `app/api/v1/waitlist/public.py` for the abuse
reasoning (per-IP limit, honeypot, length caps, deliberately no CAPTCHA).

## The body

`email` and `full_name` are required. Everything else is optional and may be
omitted or sent as `null`.

| Field        | Max | Notes |
|--------------|-----|-------|
| `email`      | 255 | Shape-checked here, validated properly by Supabase at approval |
| `full_name`  | 200 | Required, min 1 |
| `company`    | 200 | |
| `role_title` | 120 | |
| `stage`      |  60 | Free text -- whatever the form's stage picker offers |
| `note`       | 2000 | "Tell us about what you're building" |
| `source`     |  60 | Where they came from, for the team's own reading |
| `website`    | 200 | **Honeypot. Never shown to a human.** |

**The schema is `extra="forbid"`.** A field the site adds without a matching
change here comes back 422 rather than being silently dropped for months. That
is deliberate, and it means adding an input to the form is a two-repository
change.

## The honeypot

Render `website` as a real input that a person cannot see or tab into, and leave
it empty:

```html
<div aria-hidden="true" style="position:absolute;left:-9999px" >
  <label>Website<input type="text" name="website" tabindex="-1" autocomplete="off"></label>
</div>
```

Do not name it `honeypot` in the DOM -- that defeats it. A submission that fills
it is accepted with the same 202 and dropped: a bot told it failed just tries
again with a different shape.

## The responses

**202 -- always, for every genuine submission.** New row, duplicate address, or
somebody already approved: identical status, identical body. The form cannot
tell them apart and must not try to. An endpoint that distinguished them would
tell an anonymous caller whether a given address is on the founder list.

```json
{ "detail": "Thanks -- your registration is in. We review the founder's list by hand, and you'll get an email as soon as your place is confirmed." }
```

Show `detail` as-is if you want the API's wording, or the site's own equivalent.
Either way the message must not promise access, only that the request was
received -- approval is a human decision and may be a no.

**422** -- a malformed address, a field over its cap, or an unknown field. This
is a bug in the form, not something a founder should be shown raw. Validate
length and address shape client-side so it stays unreachable.

**429** -- the per-IP limit: 5 submissions per 5 minutes. Reachable by a person
mashing the button. Ask them to try again in a few minutes; do not retry
automatically.

## Before it will work at all: CORS

The browser calls this cross-origin, so `CORS_ORIGINS` on the ECS task
definition must contain the waitlist site's exact origin
(`https://join.goxlally.ai`, plus any preview domain the form is tested from).
It is an operator-set variable on the task definition, not a repo default --
`app/core/cors.py` reads it and `allow_credentials=True`, so a wildcard is not
an option.

A missing origin fails in the browser only: the request never reaches the API,
nothing is logged here, and the form appears to hang. Check this first if the
queue stays empty after wiring.

## A drop-in

Vanilla, no dependencies, matching the contract above.

```js
async function joinWaitlist(form) {
  const value = (name) => (form.elements[name]?.value || "").trim() || null;

  const response = await fetch("https://api.goxlally.ai/api/v1/waitlist", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: value("email"),
      full_name: value("full_name"),
      company: value("company"),
      role_title: value("role_title"),
      stage: value("stage"),
      note: value("note"),
      source: "join.goxlally.ai",
      website: form.elements["website"]?.value || null,  // honeypot
    }),
  });

  if (response.status === 202) return { ok: true };
  if (response.status === 429) {
    return { ok: false, message: "That's a few tries in a row -- give it a couple of minutes." };
  }
  // 422 is a form bug; anything else is us being down. Same thing to a founder.
  return { ok: false, message: "Something went wrong on our side. Please try again shortly." };
}
```

Note `credentials` is left at its default (`omit`). There is no session to send
and no cookie to receive -- the founder has no account yet.

## What happens next, so the form's copy can be honest

A `pending` row lands in the queue. An admin approves it in the panel, which
creates the Supabase identity and emails them that they are on the founder's
list. Nothing about posting this form creates a login, and there is a cap on how
many places exist -- so "you're in" is not a promise the form gets to make.
