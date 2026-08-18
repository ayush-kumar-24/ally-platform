from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import settings

# Static, response-shape-independent headers. No CSP here: this API returns
# JSON only, never HTML it renders itself, so there is no inline-script/style
# surface for a content-security-policy to restrict -- the frontend (a
# separate app) owns its own CSP. Adding one here would just be dead weight
# that has to be kept in sync with nothing.
_BASE_HEADERS = {
    # Browsers already treat JSON responses as non-executable, but this closes
    # the MIME-sniffing gap outright rather than relying on that behaviour.
    "X-Content-Type-Options": "nosniff",
    # This API is never meant to be framed; blocks clickjacking attempts that
    # embed an authenticated fetch/response inside a hidden iframe.
    "X-Frame-Options": "DENY",
    # Don't leak the full request URL (which can carry query params) to
    # whatever a redirect or an embedded resource points at.
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # Opts out of the FLoC-successor topics/attribution APIs; this API has no
    # use for them and shouldn't be silently enrolled.
    "Permissions-Policy": "browsing-topics=()",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds standard defensive headers to every response.

    HSTS is added only in production: it tells the browser to refuse plain
    HTTP for a full year, which is exactly wrong advice to give out over a
    local http://localhost dev server.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for name, value in _BASE_HEADERS.items():
            response.headers.setdefault(name, value)
        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response
