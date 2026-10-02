/**
 * Users list — instant search, filters, sortable columns, pagination.
 *
 * Two details that matter:
 *  - The search box is debounced (see useDebounce) so typing fires one request for
 *    the settled term, not one per keystroke that can land out of order.
 *  - Every response carries a request sequence number; a slower earlier request
 *    that arrives after a newer one is discarded. Without that, a stale response
 *    can overwrite fresh results and the table shows the wrong rows.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { listUsers, USER_STATUSES } from '../../services/admin';
import { useDebounce } from '../../hooks/useDebounce';
import { EmptyState, ErrorState, Loading, Pagination } from './AdminUI';

const COLUMNS = [
  { key: 'founder_id', label: 'ID', sortable: false },
  { key: 'full_name', label: 'Name', sortable: true },
  { key: 'email', label: 'Email', sortable: true },
  { key: 'phone', label: 'Phone', sortable: false },
  { key: 'business_name', label: 'Business', sortable: false },
  { key: 'status', label: 'Status', sortable: true },
  { key: 'plan_type', label: 'Plan', sortable: false },
  { key: 'credits_balance', label: 'Credits', sortable: true, numeric: true },
  { key: 'consent_status', label: 'Terms', sortable: false },
  /* Separate from Terms. A founder can accept the Terms and refuse cookies, or
     accept the Terms and never see the banner at all -- one column could not
     say which, and this list is where an admin comes to find exactly that. */
  { key: 'cookie_status', label: 'Cookies', sortable: false },
  { key: 'last_active_at', label: 'Last active', sortable: true },
  { key: 'created_at', label: 'Registered', sortable: true },
];

const PAGE_SIZE = 25;

/* Activity windows -- the same three the dashboard cards count
   (app/admin/insights.py), so clicking "Live now: 3" lists those 3 people.
   "Today" is UTC midnight because that is where the server's card starts its
   day; local midnight would list a different set than the card counted. */
const LIVE_WINDOW_MS = 5 * 60 * 1000;
const ACTIVITY = {
  live: { label: 'Live now (last 5 min)', since: () => new Date(Date.now() - LIVE_WINDOW_MS) },
  today: {
    label: 'Active today',
    since: () => {
      const n = new Date();
      return new Date(Date.UTC(n.getUTCFullYear(), n.getUTCMonth(), n.getUTCDate()));
    },
  },
  '7d': { label: 'Active last 7 days', since: () => new Date(Date.now() - 7 * 24 * 3600 * 1000) },
};
const LIVE_REFRESH_MS = 30 * 1000;

function isLive(iso) {
  return Boolean(iso) && Date.now() - new Date(iso).getTime() <= LIVE_WINDOW_MS;
}

/** "just now", "4 min ago", "3 h ago", or a date past a day. */
function ago(iso) {
  if (!iso) return 'never';
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min ago`;
  if (mins < 24 * 60) return `${Math.floor(mins / 60)} h ago`;
  return fmt(iso);
}

function fmt(iso) {
  return iso ? new Date(iso).toLocaleDateString('en-IN',
    { day: 'numeric', month: 'short', year: 'numeric' }) : '—';
}

export default function AdminUsers() {
  // ?active=live|today|7d -- set by the dashboard's activity cards.
  const [params, setParams] = useSearchParams();
  const initialActivity = ACTIVITY[params.get('active')] ? params.get('active') : '';
  const [activity, setActivity] = useState(initialActivity);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [diagnosis, setDiagnosis] = useState('');
  const [consent, setConsent] = useState('');
  // Who is active is the question an activity view answers, so it opens
  // sorted most-recently-active first.
  const [sortBy, setSortBy] = useState(initialActivity ? 'last_active_at' : 'created_at');
  const [descending, setDescending] = useState(true);
  const [page, setPage] = useState(1);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const debouncedSearch = useDebounce(search, 300);
  const seq = useRef(0);

  const load = useCallback(() => {
    const mine = ++seq.current;
    setLoading(true);
    setError(null);
    listUsers({
      search: debouncedSearch || undefined,
      status: status || undefined,
      diagnosis_completed: diagnosis === '' ? undefined : diagnosis === 'yes',
      consent_status: consent || undefined,
      // Recomputed on every load, so a refresh of "Live now" really is now.
      active_since: activity ? ACTIVITY[activity].since().toISOString() : undefined,
      sort_by: sortBy,
      descending,
      page,
      page_size: PAGE_SIZE,
    })
      .then((res) => { if (mine === seq.current) setData(res); })
      .catch((err) => { if (mine === seq.current) setError(err); })
      .finally(() => { if (mine === seq.current) setLoading(false); });
  }, [debouncedSearch, status, diagnosis, consent, activity, sortBy, descending, page]);

  useEffect(load, [load]);

  // "Live now" goes stale in minutes, so that view refreshes itself.
  useEffect(() => {
    if (activity !== 'live') return undefined;
    const t = setInterval(load, LIVE_REFRESH_MS);
    return () => clearInterval(t);
  }, [activity, load]);

  const changeActivity = (value) => {
    setActivity(value);
    if (value) setSortBy('last_active_at');
    setDescending(true);
    const next = new URLSearchParams(params);
    if (value) next.set('active', value); else next.delete('active');
    setParams(next, { replace: true });
  };

  // Any filter change invalidates the current page number — staying on page 4 of a
  // result set that now has one page would show an empty table.
  useEffect(() => { setPage(1); }, [debouncedSearch, status, diagnosis, consent, activity]);

  const toggleSort = (key) => {
    if (sortBy === key) setDescending(d => !d);
    else { setSortBy(key); setDescending(true); }
  };

  const items = data?.items ?? [];
  const hasFilters = Boolean(debouncedSearch || status || diagnosis || consent || activity);

  return (
    <>
      <h1 className="adm-h1">{activity ? ACTIVITY[activity].label : 'Users'}</h1>
      <p className="adm-sub">
        {activity === 'live'
          ? 'Founders who used the app in the last 5 minutes. Refreshes every 30 seconds.'
          : 'Search by name, email, phone, business name or founder ID.'}
      </p>

      <div className="adm-panel">
        <div className="adm-filters">
          <input
            className="adm-input adm-search"
            type="search"
            placeholder="Search users…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            aria-label="Search users"
          />
          <select className="adm-select" value={activity}
                  onChange={e => changeActivity(e.target.value)} aria-label="Filter by activity">
            <option value="">Any activity</option>
            {Object.entries(ACTIVITY).map(([k, a]) => <option key={k} value={k}>{a.label}</option>)}
          </select>
          <select className="adm-select" value={status} onChange={e => setStatus(e.target.value)}
                  aria-label="Filter by status">
            <option value="">All statuses</option>
            {USER_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <select className="adm-select" value={diagnosis} onChange={e => setDiagnosis(e.target.value)}
                  aria-label="Filter by diagnosis">
            <option value="">Any diagnosis</option>
            <option value="yes">Diagnosis completed</option>
            <option value="no">Not completed</option>
          </select>
          <select className="adm-select" value={consent} onChange={e => setConsent(e.target.value)}
                  aria-label="Filter by consent">
            <option value="">Any consent</option>
            <option value="granted">Consent granted</option>
            <option value="stale">Consent stale</option>
            <option value="missing">Consent missing</option>
          </select>
        </div>

        {error ? (
          <ErrorState error={error} onRetry={load} />
        ) : loading && !data ? (
          <Loading label="Loading users…" />
        ) : items.length === 0 ? (
          <EmptyState
            title={activity === 'live' ? 'Nobody is live right now'
              : hasFilters ? 'No users match those filters' : 'No users yet'}
            hint={hasFilters ? 'Try clearing the search or filters.' : undefined}
          />
        ) : (
          <>
            <div className="adm-table-wrap" aria-busy={loading}>
              <table className="adm-table">
                <thead>
                  <tr>
                    {COLUMNS.map(c => (
                      <th
                        key={c.key}
                        scope="col"
                        className={`${c.sortable ? '' : 'adm-nosort'} ${c.numeric ? 'adm-num' : ''}`}
                        aria-sort={sortBy === c.key ? (descending ? 'descending' : 'ascending') : 'none'}
                      >
                        {/* Sorting was an onClick on the <th> itself — not
                            focusable and not keyboard-operable. The button is
                            the control; the th keeps aria-sort. */}
                        {c.sortable ? (
                          <button type="button" className="adm-sort-btn" onClick={() => toggleSort(c.key)}>
                            {c.label}{sortBy === c.key ? (descending ? ' ↓' : ' ↑') : ''}
                          </button>
                        ) : (
                          <>{c.label}</>
                        )}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {items.map(u => (
                    <tr key={u.founder_id}>
                      <td className="adm-mono">{u.founder_id}</td>
                      <td><Link to={`/admin/users/${u.founder_id}`}>{u.full_name || '—'}</Link></td>
                      <td>{u.email}</td>
                      <td className="adm-mono">{u.phone || '—'}</td>
                      <td>{u.business_name || '—'}</td>
                      <td><span className={`adm-pill ${u.status}`}>{u.status}</span></td>
                      <td>{u.plan_type || '—'}</td>
                      <td className="adm-num">{u.credits_balance}</td>
                      <td><span className={`adm-pill ${u.consent_status}`}>{u.consent_status}</span></td>
                      <td>
                        <span className={`adm-pill ${u.cookie_status}`}>
                          {/* "never answered" reads as a state; "never_answered" reads as a bug. */}
                          {(u.cookie_status || 'never_answered').replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td title={u.last_active_at ? new Date(u.last_active_at).toLocaleString('en-IN') : undefined}>
                        {isLive(u.last_active_at)
                          ? <span className="adm-pill active">● live</span>
                          : <span className="adm-muted">{ago(u.last_active_at)}</span>}
                      </td>
                      <td className="adm-muted">{fmt(u.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={data.page} pages={data.pages} total={data.total}
                        onChange={setPage} busy={loading} />
          </>
        )}
      </div>
    </>
  );
}
