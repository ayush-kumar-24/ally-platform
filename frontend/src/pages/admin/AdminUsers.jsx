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
import { Link } from 'react-router-dom';
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
  { key: 'consent_status', label: 'Consent', sortable: false },
  { key: 'created_at', label: 'Registered', sortable: true },
];

const PAGE_SIZE = 25;

function fmt(iso) {
  return iso ? new Date(iso).toLocaleDateString('en-IN',
    { day: 'numeric', month: 'short', year: 'numeric' }) : '—';
}

export default function AdminUsers() {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [diagnosis, setDiagnosis] = useState('');
  const [consent, setConsent] = useState('');
  const [sortBy, setSortBy] = useState('created_at');
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
      sort_by: sortBy,
      descending,
      page,
      page_size: PAGE_SIZE,
    })
      .then((res) => { if (mine === seq.current) setData(res); })
      .catch((err) => { if (mine === seq.current) setError(err); })
      .finally(() => { if (mine === seq.current) setLoading(false); });
  }, [debouncedSearch, status, diagnosis, consent, sortBy, descending, page]);

  useEffect(load, [load]);

  // Any filter change invalidates the current page number — staying on page 4 of a
  // result set that now has one page would show an empty table.
  useEffect(() => { setPage(1); }, [debouncedSearch, status, diagnosis, consent]);

  const toggleSort = (key) => {
    if (sortBy === key) setDescending(d => !d);
    else { setSortBy(key); setDescending(true); }
  };

  const items = data?.items ?? [];
  const hasFilters = Boolean(debouncedSearch || status || diagnosis || consent);

  return (
    <>
      <h1 className="adm-h1">Users</h1>
      <p className="adm-sub">Search by name, email, phone, business name or founder ID.</p>

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
            title={hasFilters ? 'No users match those filters' : 'No users yet'}
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
