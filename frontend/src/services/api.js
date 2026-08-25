/**
 * services/api.js — the single production API layer for the frontend.
 *
 * All backend traffic goes through here. Pages/components import { get, post,
 * put, patch, del } (or domain services built on them) and NEVER call
 * axios/fetch directly.
 *
 * Features
 *  - Base URL from VITE_API_BASE_URL (falls back to "/api/v1", which the Vite
 *    dev proxy forwards to the FastAPI backend on :8000 — see vite.config.js)
 *  - 20s request timeout, JSON headers
 *  - Authorization: Bearer <access_token> from localStorage on every request
 *  - Automatic refresh: on 401, calls POST /auth/refresh — the refresh token
 *    itself is never seen here, it rides as the HttpOnly ally_refresh_token
 *    cookie the backend set on login (see api/v1/auth/routes.py), which is
 *    why every request below sets withCredentials: true. Stores the new
 *    access token and retries the original request. Concurrent 401s share
 *    ONE refresh flight so a burst of requests can't burn the single-use
 *    (rotating) refresh token.
 *  - Centralized error handling: every failure is normalized to ApiError
 *    { status, detail, data } — callers never touch axios error internals.
 */

import axios from 'axios';

const BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_API_URL || // legacy name, still honored
  '/api/v1';
const TIMEOUT_MS = 20_000;

// ── Token storage ────────────────────────────────────────────────────────────
//
// The refresh token is NOT stored here, or anywhere in JS-reachable storage
// at all -- it used to live in localStorage alongside the access token,
// which is readable by any script on the page (XSS, a compromised
// dependency, a malicious extension). It now lives only in the HttpOnly
// ally_refresh_token cookie the backend sets; this file never reads or
// writes it, it just makes sure every auth-relevant request carries cookies
// (withCredentials below) so the browser attaches it automatically.
//
// The access token stays in localStorage: short-lived (minutes, not the
// refresh token's 30 days), and every request already needs it read
// synchronously for the Authorization header, which a cookie can't do for a
// value JS needs to put in a header rather than have the browser attach.

const ACCESS_KEY = 'ally.access_token';

export const getAccessToken = () => localStorage.getItem(ACCESS_KEY);

/** Store the access token (e.g. from /auth/session, /auth/resume, /auth/refresh).
 *  The refresh token in the same response body is always null -- see
 *  TokenPair's docstring on the backend -- so there is nothing to store for it. */
export function setTokens({ access_token }) {
  if (access_token) localStorage.setItem(ACCESS_KEY, access_token);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
}

/** Optional app-level hook: called once when a session can't be recovered
 *  (refresh failed / revoked). Wire it to a redirect-to-login in App setup. */
let authFailureHandler = null;
export function onAuthFailure(handler) {
  authFailureHandler = handler;
}

// ── Error normalization ──────────────────────────────────────────────────────

export class ApiError extends Error {
  /**
   * @param {number|null} status  HTTP status, or null for network/timeout
   * @param {string}      detail  Human-readable message (FastAPI `detail` when available)
   * @param {any}         data    Raw response body, if any
   */
  constructor(status, detail, data = null) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    this.data = data;
    // The machine-readable error class name our own backend's AppError handler
    // always sends (see middleware/error_handler.py: {"error": cls.__name__, ...}).
    // Lets a caller branch on the exact error type instead of guessing from status
    // + message text, which is what explainLimit() needs to tell "daily limit,
    // resets tomorrow" apart from "lifetime allowance already used, never resets".
    this.code = data?.error ?? null;
  }

  get isNetwork() { return this.status === null; }
  get isAuth()    { return this.status === 401 || this.status === 403; }
}

function normalizeError(err) {
  if (err.response) {
    const { status, data } = err.response;
    // Live-confirmed gap: every error this backend raises -- AppError subclasses,
    // FastAPI's own HTTPException, and its 422 validation handler -- serialises as
    // {"error": "<ClassName>", "message": "..."}. There is no "detail" key
    // anywhere in this backend's responses. Reading data?.detail here always came
    // back undefined, so every custom message (plan limits, auth failures,
    // diagnosis rules) silently fell through to axios's generic
    // "Request failed with status code 422" -- which is exactly what showed up
    // raw on the production sign-up screen. `message` is checked first because
    // it is what this backend actually sends; `detail` is kept after it only in
    // case a future/third-party endpoint ever uses the FastAPI-default shape.
    const detail =
      (typeof data?.message === 'string' && data.message) ||
      (typeof data?.detail === 'string' && data.detail) ||
      (Array.isArray(data?.detail) && data.detail[0]?.msg) || // FastAPI 422 shape
      err.message ||
      `Request failed with status ${status}`;
    return new ApiError(status, detail, data);
  }
  if (err.code === 'ECONNABORTED') {
    return new ApiError(null, 'Request timed out — please try again.');
  }
  return new ApiError(null, 'Network error — is the server reachable?');
}

// ── Axios instance ───────────────────────────────────────────────────────────

const api = axios.create({
  baseURL: BASE_URL,
  timeout: TIMEOUT_MS,
  headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
  // Required for the browser to send/receive the HttpOnly ally_refresh_token
  // cookie at all -- without this, /auth/refresh, /resume and /logout would
  // never see it even though the backend sets and reads it correctly.
  withCredentials: true,
});

// Attach Bearer token
api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ── 401 → single-flight refresh → retry ──────────────────────────────────────

let refreshFlight = null; // Promise<string new access token> while a refresh is in progress

async function refreshTokens() {
  // No client-side way to pre-check "is there a session" anymore -- the
  // refresh token lives only in the HttpOnly cookie, which JS cannot read
  // (that's the point). The backend is the one that finds out whether it's
  // there and valid; a missing/expired/revoked cookie surfaces as this call
  // itself failing below, same as any other rejected refresh.
  try {
    // Bare axios (not `api`): must not recurse through these interceptors.
    // withCredentials still required here for the same reason as the `api`
    // instance -- this is the call that actually reads/sets the cookie.
    const { data } = await axios.post(
      `${BASE_URL}/auth/refresh`,
      {},
      { timeout: TIMEOUT_MS, headers: { 'Content-Type': 'application/json' }, withCredentials: true },
    );
    setTokens(data);
    return data.access_token;
  } catch (err) {
    clearTokens();
    authFailureHandler?.();
    throw normalizeError(err);
  }
}

/**
 * Restore a session purely from the HttpOnly refresh cookie -- for the
 * moment the app mounts with no access token in localStorage (a fresh tab,
 * or one that lost it) but the cookie may still be valid. Distinct from
 * refreshTokens() above: that one fires reactively off a 401 mid-session and
 * cascades into onAuthFailure when it fails; this one is a plain yes/no
 * probe a caller (RequireAuth) makes ITS OWN decision from -- "no valid
 * cookie" is an entirely normal, silent outcome here (most first visits),
 * not a failure worth notifying anyone about.
 *
 * Bare axios, not `api`: must not recurse through the interceptor below,
 * same reason as refreshTokens().
 *
 * Returns the founder object on success, or null on any failure (no cookie,
 * expired, revoked, network error) -- never throws, so a caller can always
 * just check truthiness rather than wrap this in try/catch.
 */
// Single-flight, same reason as refreshFlight below and the same bug shape:
// the refresh token is single-use/rotating (routes.py: "the old refresh
// token is revoked as part of this call"), so two concurrent resume calls
// race on the SAME cookie value -- the first rotates it, the second is
// then presenting an already-revoked token and gets a 401. Live-confirmed
// this actually happens, not just a theoretical race: React 18 StrictMode
// double-invokes effects in dev, so RequireAuth's mount fired resumeSession()
// twice a few ms apart, and the app landed on the login page despite a
// perfectly valid session existing seconds earlier. The same shape would hit
// production too with two tabs mounting around the same moment. Sharing one
// in-flight promise across every concurrent caller closes it the same way
// refreshFlight already does for the 401-triggered path.
let resumeFlight = null;

export function resumeSession() {
  resumeFlight ??= (async () => {
    try {
      const { data } = await axios.post(
        `${BASE_URL}/auth/resume`,
        {},
        { timeout: TIMEOUT_MS, headers: { 'Content-Type': 'application/json' }, withCredentials: true },
      );
      setTokens(data);
      return data.founder;
    } catch {
      return null;
    }
  })().finally(() => { resumeFlight = null; });
  return resumeFlight;
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;

    // One retry per request; never for the refresh call itself.
    if (status === 401 && original && !original._retried && !original.url?.includes('/auth/refresh')) {
      original._retried = true;
      refreshFlight ??= refreshTokens().finally(() => { refreshFlight = null; });
      const newAccess = await refreshFlight; // throws ApiError if refresh failed
      original.headers.Authorization = `Bearer ${newAccess}`;
      return api(original);
    }

    throw normalizeError(error);
  },
);

// ── Reusable methods ─────────────────────────────────────────────────────────
// All return `response.data` directly and throw ApiError on failure.

/* In-flight GET coalescing.
 *
 * One dashboard load issued /dashboard/overview twice and /profile three
 * times, because the shell (PlatformLayout) and the page (Dashboard, Report,
 * Billing...) each fetch what they need independently -- which is the right
 * way to write them; they should not have to know about each other. React's
 * StrictMode double-invokes effects in development on top of that, doubling
 * the whole set again.
 *
 * So: if an identical GET is ALREADY in flight, hand back the same promise
 * instead of opening a second request. Deliberately not a cache -- nothing is
 * retained past settlement, so a later refetch (after a save, say) still hits
 * the network and nobody can read a stale value. It only collapses requests
 * that overlap in time, which is exactly the duplicate class above.
 *
 * Skipped when a per-call `config` is present: that can carry an AbortSignal,
 * an Authorization override or one-off headers, and sharing a response across
 * two callers with different configs would be wrong.
 */
const inFlightGets = new Map();

export const get = (url, config) => {
  if (config) return api.get(url, config).then(r => r.data);

  const existing = inFlightGets.get(url);
  if (existing) return existing;

  const request = api
    .get(url)
    .then(r => r.data)
    .finally(() => inFlightGets.delete(url));

  inFlightGets.set(url, request);
  return request;
};
export const post  = (url, body, config) => api.post(url, body, config).then(r => r.data);
export const put   = (url, body, config) => api.put(url, body, config).then(r => r.data);
export const patch = (url, body, config) => api.patch(url, body, config).then(r => r.data);
export const del   = (url, config)       => api.delete(url, config).then(r => r.data);

// ── Server-Sent Events ───────────────────────────────────────────────────────
//
// axios cannot do this: it buffers the whole response before resolving, which
// is the opposite of what a stream is for. So this is the one place in the app
// that touches fetch directly -- and it lives HERE, next to everything else,
// rather than in a page, so the rules the rest of the app relies on (bearer
// token, single-flight 401 refresh, ApiError normalization) still apply.
//
// EventSource, the browser's built-in SSE client, is not an option either: it
// is GET-only and cannot set an Authorization header. A chat send is a POST
// carrying a message body, and every endpoint here needs the bearer.

/** One `event:`/`data:` frame off the wire. */
function parseSseFrame(raw) {
  let event = 'message';
  const dataLines = [];
  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim();
    // Not trimStart on the whole value: SSE strips exactly one leading space
    // after the colon, and content tokens can legitimately begin with spaces.
    // Trimming them all would silently glue words together mid-sentence.
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''));
  }
  if (!dataLines.length) return null;
  try {
    return { event, data: JSON.parse(dataLines.join('\n')) };
  } catch {
    return { event, data: null };
  }
}

/**
 * POST a body and consume the Server-Sent Events response.
 *
 * @param {string}   url       path relative to BASE_URL, e.g. '/chat/stream'
 * @param {object}   body      JSON request body
 * @param {object}   opts
 * @param {function} opts.onEvent  called as (eventName, data) per frame
 * @param {AbortSignal} opts.signal
 * @returns {Promise<void>} resolves when the stream ends, rejects with ApiError
 */
export async function stream(url, body, { onEvent, signal } = {}) {
  const run = async (token) => fetch(`${BASE_URL}${url}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
    credentials: 'include',
    signal,
  });

  let response;
  try {
    response = await run(getAccessToken());
    // Same single-flight refresh the axios interceptor uses, and deliberately
    // the SAME promise: a stream starting at the moment a normal request 401s
    // must not burn a second rotating refresh token.
    if (response.status === 401) {
      refreshFlight ??= refreshTokens().finally(() => { refreshFlight = null; });
      response = await run(await refreshFlight);
    }
  } catch (err) {
    if (err?.name === 'AbortError') return;         // caller cancelled; not a failure
    if (err instanceof ApiError) throw err;          // refresh already normalized it
    throw new ApiError(null, 'Network error — is the server reachable?');
  }

  if (!response.ok) {
    // Error responses are still JSON, not SSE -- the plan gate and rate limiter
    // reject before a single frame is written. Read them the same way the axios
    // path does so explainLimit() can recognise a 403/402/429 here too.
    let data = null;
    try { data = await response.json(); } catch { /* non-JSON error body */ }
    const detail =
      (typeof data?.message === 'string' && data.message) ||
      (typeof data?.detail === 'string' && data.detail) ||
      `Request failed with status ${response.status}`;
    throw new ApiError(response.status, detail, data);
  }
  if (!response.body) throw new ApiError(null, 'Streaming is not supported here.');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      // stream: true so a multi-byte character split across two network chunks
      // is held back rather than decoded into a replacement character.
      buffer += decoder.decode(value, { stream: true });
      // Frames are separated by a blank line. Anything after the last separator
      // is a partial frame and stays in the buffer for the next read.
      let sep;
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const frame = parseSseFrame(buffer.slice(0, sep));
        buffer = buffer.slice(sep + 2);
        if (frame) onEvent?.(frame.event, frame.data);
      }
    }
  } catch (err) {
    if (err?.name === 'AbortError') return;
    throw new ApiError(null, 'The connection dropped mid-reply — please try again.');
  } finally {
    reader.releaseLock?.();
  }
}

/**
 * Drop undefined/null keys from a request body.
 *
 * Several API schemas type optional fields as plain `str` with a default rather
 * than `str | None`, so sending an explicit null is a 422 while omitting the key
 * is fine. Callers should not have to remember which fields are which.
 */
export function prune(obj) {
  return Object.fromEntries(
    Object.entries(obj ?? {}).filter(([, v]) => v !== undefined && v !== null));
}

export default api;
