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
 *  - Automatic refresh: on 401, trades the refresh token at POST /auth/refresh
 *    (rotating — each refresh token works exactly once), stores the new pair,
 *    and retries the original request. Concurrent 401s share ONE refresh
 *    flight so a burst of requests can't burn the single-use token.
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

const ACCESS_KEY = 'ally.access_token';
const REFRESH_KEY = 'ally.refresh_token';

export const getAccessToken = () => localStorage.getItem(ACCESS_KEY);
export const getRefreshToken = () => localStorage.getItem(REFRESH_KEY);

/** Store a token pair (e.g. from /auth/session, /auth/resume, /auth/refresh). */
export function setTokens({ access_token, refresh_token }) {
  if (access_token) localStorage.setItem(ACCESS_KEY, access_token);
  if (refresh_token) localStorage.setItem(REFRESH_KEY, refresh_token);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
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
  }

  get isNetwork() { return this.status === null; }
  get isAuth()    { return this.status === 401 || this.status === 403; }
}

function normalizeError(err) {
  if (err.response) {
    const { status, data } = err.response;
    const detail =
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
  const refresh_token = getRefreshToken();
  if (!refresh_token) {
    // No wired onAuthFailure handler meant this path used to fail silently on
    // whatever page the founder happened to be on -- e.g. a diagnosis page
    // reporting "couldn't reach the server" when the real problem was simply
    // "you are not signed in."
    authFailureHandler?.();
    throw new ApiError(401, 'No session — please sign in.');
  }
  try {
    // Bare axios (not `api`): must not recurse through these interceptors.
    const { data } = await axios.post(
      `${BASE_URL}/auth/refresh`,
      { refresh_token },
      { timeout: TIMEOUT_MS, headers: { 'Content-Type': 'application/json' } },
    );
    setTokens(data);
    return data.access_token;
  } catch (err) {
    clearTokens();
    authFailureHandler?.();
    throw normalizeError(err);
  }
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

export const get   = (url, config)       => api.get(url, config).then(r => r.data);
export const post  = (url, body, config) => api.post(url, body, config).then(r => r.data);
export const put   = (url, body, config) => api.put(url, body, config).then(r => r.data);
export const patch = (url, body, config) => api.patch(url, body, config).then(r => r.data);
export const del   = (url, config)       => api.delete(url, config).then(r => r.data);

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
