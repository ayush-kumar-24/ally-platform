/* API client for the Ally backend.
 *
 * One place owns the base URL, the auth flow, and the error shape, so screens
 * call typed helpers (api.reports.get(id)) instead of raw fetch.
 *
 * Auth is a TWO-token exchange (matches the backend and the future Supabase
 * flow): an IDENTITY token is POSTed once to /auth/session and traded for a
 * backend SESSION access token, which is the bearer on every protected route.
 * In dev the identity token is the founder's user_id UUID; later it becomes the
 * Supabase JWT and only `IDENTITY_TOKEN` changes.
 */

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const IDENTITY_TOKEN =
  import.meta.env.VITE_DEV_FOUNDER_TOKEN || '00000000-0000-0000-0000-000000000001';

const ACCESS_KEY = 'ally_access_token';
const REFRESH_KEY = 'ally_refresh_token';
let accessTokenCache = null;

function readStored(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function writeStored(key, val) {
  try {
    if (val == null) localStorage.removeItem(key);
    else localStorage.setItem(key, val);
  } catch {
    /* localStorage unavailable — session lives in memory only */
  }
}

/** Error carrying the HTTP status so callers can branch on 401/403/404. */
export class ApiError extends Error {
  constructor(message, { status, body } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

/** Exchange the identity token for backend session tokens (dev: UUID; later: Supabase JWT). */
export async function startSession(identityToken = IDENTITY_TOKEN) {
  const res = await fetch(`${BASE_URL}/auth/session`, {
    method: 'POST',
    headers: identityToken ? { Authorization: `Bearer ${identityToken}` } : {},
  });
  if (!res.ok) {
    throw new ApiError(`Auth session failed (${res.status})`, { status: res.status });
  }
  const data = await res.json();
  accessTokenCache = data.access_token;
  writeStored(ACCESS_KEY, data.access_token);
  writeStored(REFRESH_KEY, data.refresh_token);
  return data.access_token;
}

async function ensureAccessToken() {
  if (accessTokenCache) return accessTokenCache;
  const stored = readStored(ACCESS_KEY);
  if (stored) {
    accessTokenCache = stored;
    return stored;
  }
  return startSession();
}

function clearSession() {
  accessTokenCache = null;
  writeStored(ACCESS_KEY, null);
}

async function request(path, { method = 'GET', body, headers, signal, raw = false } = {}, _retried = false) {
  const token = await ensureAccessToken();
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    signal,
    headers: {
      Accept: raw ? '*/*' : 'application/json',
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  // Access token expired/rejected -> re-exchange the identity token once and retry.
  if (res.status === 401 && !_retried) {
    clearSession();
    await startSession();
    return request(path, { method, body, headers, signal, raw }, true);
  }

  if (!res.ok) {
    let detail;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text().catch(() => '');
    }
    const message =
      (detail && (detail.detail || detail.message)) || `Request failed (${res.status})`;
    throw new ApiError(message, { status: res.status, body: detail });
  }

  if (raw) return res; // caller handles blob/stream (e.g. PDF export)
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  request,
  startSession,
  reports: {
    get: (id, opts) => request(`/reports/${id}`, opts),
    founderDna: (id, opts) => request(`/reports/${id}/founder-dna`, opts),
    businessDna: (id, opts) => request(`/reports/${id}/business-dna`, opts),
    insights: (id, opts) => request(`/reports/${id}/insights`, opts),
    recommendations: (id, opts) => request(`/reports/${id}/recommendations`, opts),
    createShare: (id) => request(`/reports/${id}/share`, { method: 'POST' }),
    shared: (token) => request(`/reports/shared/${token}`),
    /** PDF export — returns a Blob (Authorization is applied). */
    exportPdf: (id) =>
      request(`/reports/${id}/export`, { method: 'POST', raw: true }).then((r) => r.blob()),
  },
};

export default api;
