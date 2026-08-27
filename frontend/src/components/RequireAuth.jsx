import { useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { getAccessToken, resumeSession } from '../services/api';

/**
 * Guards the main platform: no access token, no render.
 *
 * Without this, landing on e.g. /app/diagnosis with no session sent every
 * request with no Authorization header. In dev mode the backend's no-token
 * fallback silently authenticates that as a placeholder founder that doesn't
 * exist in the database, so every call 404s and the page shows a generic
 * "couldn't reach the server" -- which reads as a network glitch, not "you
 * aren't signed in." This catches the missing-session case before any of
 * that happens and sends the founder to login instead.
 *
 * "No access token" is not automatically "no session", though -- a founder
 * can lose the access token (it's short-lived, or something cleared
 * localStorage) while still holding a perfectly valid 30-day refresh
 * session in the HttpOnly cookie the backend can't help but see on every
 * request. Live-confirmed this used to bounce straight to login and force a
 * full Google/LinkedIn re-auth in exactly that case, even though
 * POST /auth/resume exists on the backend specifically to avoid it ("a
 * returning user who still holds a valid refresh token is brought back in
 * without bouncing through the provider" -- its own docstring). So: only
 * skip straight to "authed" when a token is already in hand; otherwise try
 * resume once before concluding there's really nothing to restore.
 */
/**
 * Local-only escape hatch for reviewing UI without a backend or an account.
 *
 * Two locks, both of which must be open, and neither of which can be opened in
 * production:
 *
 *  - `import.meta.env.DEV` is a literal `false` in any built bundle, so Vite
 *    deletes this branch entirely at build time. It cannot be flipped by an
 *    env var on a server, because by then it is not a variable any more.
 *  - the opt-in still has to be passed explicitly, so a normal `npm run dev`
 *    is unaffected and nobody bypasses auth by accident while working.
 *
 * It only skips the ROUTE GUARD. No token is minted and nothing is faked, so
 * every API call still goes out unauthenticated and pages that need real data
 * will show their own empty or error states. That is the point: it is for
 * looking at layout, naming and navigation, not for using the product.
 */
const DEV_BYPASS = import.meta.env.DEV && import.meta.env.VITE_DEV_BYPASS_AUTH === '1';

export default function RequireAuth({ children }) {
  const location = useLocation();
  const [status, setStatus] = useState(() =>
    (DEV_BYPASS || getAccessToken() ? 'authed' : 'checking'));

  useEffect(() => {
    if (DEV_BYPASS || status !== 'checking') return undefined;
    let cancelled = false;
    resumeSession().then((founder) => {
      if (!cancelled) setStatus(founder ? 'authed' : 'unauthed');
    });
    return () => { cancelled = true; };
  }, [status]);

  // Same shell background as RouteFallback (App.jsx) -- a blank frame, not a
  // spinner, for the same reason: this resolves in one round-trip, almost
  // always well under a second, and a spinner that appears and immediately
  // disappears reads as more broken than nothing at all.
  if (status === 'checking') {
    return <div style={{ minHeight: '100dvh', background: 'var(--color-forest-night, #06140d)' }} />;
  }

  if (status === 'unauthed') {
    return <Navigate to="/guided/login" replace state={{ from: location.pathname }} />;
  }

  return children;
}
