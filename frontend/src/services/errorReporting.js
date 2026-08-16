/**
 * services/errorReporting.js — lightweight, self-hosted frontend error
 * monitoring.
 *
 * No third-party APM (Sentry/LogRocket/etc.) is wired up here -- that needs
 * an account and DSN nobody has provisioned. This sends sanitized crash
 * reports to the backend's own structured logger instead (POST
 * /frontend-errors), which is infrastructure the team already has and
 * watches, rather than errors vanishing into whichever browser tab hit them.
 * If a real APM gets set up later, this is the redaction-safe shape to feed
 * it instead of (or alongside) the backend log.
 *
 * Two independent things are called "error monitoring" here and both matter:
 *   - ErrorBoundary (components/ErrorBoundary.jsx) catches React RENDER
 *     errors and calls reportError() from componentDidCatch.
 *   - main.jsx's window 'error' / 'unhandledrejection' listeners catch
 *     everything React's error boundaries structurally cannot -- errors
 *     thrown in event handlers, timers, and async code/rejected promises.
 * Missing either one leaves a real class of production errors invisible.
 */

import { getAccessToken } from './api';

const ENDPOINT = '/frontend-errors';
const MAX_LEN = 2000;

// A JWT is three base64url segments joined by '.', starting with the
// standard '{"' header ('eyJ...'). Matches access tokens, refresh tokens and
// Supabase's own tokens uniformly, without needing to know which one leaked.
const JWT_PATTERN = /eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}/g;
const BEARER_PATTERN = /Bearer\s+\S+/gi;

/**
 * Truncates and scrubs a string before it ever leaves the browser. This is
 * the FIRST of two redaction layers -- the backend route's field-length caps
 * are the second, not the only one. An error message or stack can
 * accidentally embed something it shouldn't (a thrown Error built from raw
 * user input, a token visible in a caught request's URL); this is defense
 * against that, not a claim that error text is normally sensitive.
 */
function sanitize(value) {
  if (!value) return null;
  const s = String(value)
    .replace(JWT_PATTERN, '[redacted-jwt]')
    .replace(BEARER_PATTERN, 'Bearer [redacted]');
  return s.length > MAX_LEN ? `${s.slice(0, MAX_LEN)}…[truncated]` : s;
}

// Crude client-side loop guard: a render error that fires on every re-render
// (an error boundary resetting into the same broken state, say) must not
// turn into a report on every single one of those renders.
let lastSentAt = 0;
const MIN_INTERVAL_MS = 2000;

/**
 * Report an uncaught error. Never throws, never blocks the UI it's reporting
 * from, never retries -- a failed error report is telemetry, not something
 * worth fighting for or surfacing to the founder.
 *
 * @param {unknown} error - an Error, or anything a catch/rejection handed us
 * @param {{source?: string, componentStack?: string|null}} [context]
 */
export function reportError(error, { source = 'unknown', componentStack = null } = {}) {
  const now = Date.now();
  if (now - lastSentAt < MIN_INTERVAL_MS) return;
  lastSentAt = now;

  const message = error && typeof error === 'object' && 'message' in error
    ? error.message
    : String(error ?? 'Unknown error');

  const payload = {
    message: sanitize(message) || 'Unknown error',
    stack: sanitize(error?.stack),
    component_stack: sanitize(componentStack),
    url: window.location?.href ?? '',
    user_agent: navigator?.userAgent ?? null,
    source,
    event_id: crypto.randomUUID(),
  };

  const base = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '/api/v1';
  const token = getAccessToken();

  try {
    // Bare fetch, not the app's axios instance -- must not recurse through
    // its interceptors (a failed report must never trigger a session refresh
    // or, worse, report itself) and must not wait on the app's normal 20s
    // request timeout for something that is fundamentally best-effort.
    fetch(`${base}${ENDPOINT}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(payload),
      keepalive: true, // survives a navigation/unload the error itself triggers
    }).catch(() => {}); // best-effort: nothing to do if this itself fails
  } catch {
    // JSON.stringify or fetch construction itself failed -- give up quietly.
  }
}
