"""Frontend error monitoring.

No third-party APM (Sentry/LogRocket/etc.) is wired up -- that needs an
account and DSN nobody has provisioned. This is a self-hosted stand-in: the
frontend posts sanitized crash reports here, and they land in the backend's
own structured JSON logger, which is infrastructure the team already has and
watches, rather than vanishing into whichever browser tab happened to hit the
error.

Deliberately narrow: only structural fields (message, stack, url, user
agent) are accepted, never arbitrary request/response bodies or form state --
that is what would actually carry a founder's private answers or a bearer
token. The frontend's own reporter (frontend/src/services/errorReporting.js)
redacts anything JWT/Bearer-shaped before this ever leaves the browser; this
module's field-length limits are the second layer, not the only one.
"""
