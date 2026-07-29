/* API client for the Ally backend.
 *
 * One place owns the base URL, auth header, and error shape, so screens call
 * typed helpers (api.reports.get(id)) instead of raw fetch. Auth is pluggable:
 * today it sends the dev-provider bearer (the founder's user_id UUID); swapping
 * to a real Supabase JWT is a one-line change in `getAuthToken()`.
 */

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
const DEV_TOKEN =
  import.meta.env.VITE_DEV_FOUNDER_TOKEN || '00000000-0000-0000-0000-000000000001';

/** Resolve the bearer token. Later: return the Supabase session JWT instead. */
export function getAuthToken() {
  // A token stashed by a future login flow takes precedence over the dev token.
  try {
    const stored = localStorage.getItem('ally_token');
    if (stored) return stored;
  } catch {
    /* localStorage unavailable (SSR / privacy mode) — fall through to dev token */
  }
  return DEV_TOKEN;
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

async function request(path, { method = 'GET', body, headers, signal, raw = false } = {}) {
  const token = getAuthToken();
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
