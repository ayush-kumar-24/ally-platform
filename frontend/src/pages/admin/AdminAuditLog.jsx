/**
 * Audit log — the immutable record of every admin action.
 *
 * Read-only by design: there is no edit or delete control here because the backend
 * offers none. An audit trail you can amend is not an audit trail.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { getAuditLog } from '../../services/admin';
import { useDebounce } from '../../hooks/useDebounce';
import { EmptyState, ErrorState, Loading } from './AdminUI';

const PAGE_SIZE = 50;

function fmt(iso) {
  return iso ? new Date(iso).toLocaleString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  }) : '—';
}

/** Old/new values are stored as JSON strings; show them compactly. */
function Value({ raw }) {
  if (!raw) return <span className="adm-muted">—</span>;
  let text = raw;
  try {
    const parsed = JSON.parse(raw);
    text = Object.entries(parsed).map(([k, v]) => `${k}: ${v}`).join(', ');
  } catch { /* not JSON — show as-is */ }
  return <span className="adm-mono">{text}</span>;
}

export default function AdminAuditLog() {
  const [targetUser, setTargetUser] = useState('');
  const [action, setAction] = useState('');
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const debouncedTarget = useDebounce(targetUser, 300);
  const debouncedAction = useDebounce(action, 300);
  const seq = useRef(0);

  const load = useCallback(() => {
    const mine = ++seq.current;
    setLoading(true);
    setError(null);
    getAuditLog({
      limit: PAGE_SIZE,
      offset,
      target_user_id: debouncedTarget || undefined,
      action: debouncedAction || undefined,
    })
      .then(res => { if (mine === seq.current) setData(res); })
      .catch(err => { if (mine === seq.current) setError(err); })
      .finally(() => { if (mine === seq.current) setLoading(false); });
  }, [offset, debouncedTarget, debouncedAction]);

  useEffect(load, [load]);
  useEffect(() => { setOffset(0); }, [debouncedTarget, debouncedAction]);

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <>
      <h1 className="adm-h1">Audit log</h1>
      <p className="adm-sub">Every admin action, immutable. Newest first.</p>

      <div className="adm-panel">
        <div className="adm-filters">
          <input className="adm-input" type="number" min="1" placeholder="Filter by founder ID"
                 value={targetUser} onChange={e => setTargetUser(e.target.value)}
                 aria-label="Filter by target user" style={{ width: 200 }} />
          <input className="adm-input adm-search" type="search"
                 placeholder="Filter by action (e.g. credits.add)"
                 value={action} onChange={e => setAction(e.target.value)}
                 aria-label="Filter by action" />
        </div>

        {error ? (
          <ErrorState error={error} onRetry={load} />
        ) : loading && !data ? (
          <Loading label="Loading audit log…" />
        ) : items.length === 0 ? (
          <EmptyState title="No audit entries"
                      hint={targetUser || action ? 'Try clearing the filters.' : 'Admin actions will appear here.'} />
        ) : (
          <>
            <div className="adm-table-wrap" aria-busy={loading}>
              <table className="adm-table">
                <thead>
                  <tr>
                    <th scope="col" className="adm-nosort">When</th>
                    <th scope="col" className="adm-nosort">Admin</th>
                    <th scope="col" className="adm-nosort">Role</th>
                    <th scope="col" className="adm-nosort">Action</th>
                    <th scope="col" className="adm-nosort">Target</th>
                    <th scope="col" className="adm-nosort">Old</th>
                    <th scope="col" className="adm-nosort">New</th>
                    <th scope="col" className="adm-nosort">IP</th>
                    <th scope="col" className="adm-nosort">Result</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map(e => (
                    <tr key={e.event_id}>
                      <td className="adm-muted">{fmt(e.timestamp)}</td>
                      <td>{e.admin_email || `#${e.admin_id}`}</td>
                      <td className="adm-muted">{(e.admin_role || '').replace('_', ' ')}</td>
                      <td className="adm-mono">{e.action}</td>
                      <td>
                        {e.target_user_id
                          ? <Link to={`/admin/users/${e.target_user_id}`}>#{e.target_user_id}</Link>
                          : <span className="adm-muted">—</span>}
                      </td>
                      <td><Value raw={e.old_value} /></td>
                      <td><Value raw={e.new_value} /></td>
                      <td className="adm-mono">{e.ip_address || '—'}</td>
                      <td>
                        <span className={`adm-pill ${e.result === 'success' ? 'active' : 'banned'}`}>
                          {e.result}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="adm-pagination">
              <span className="adm-muted">Page {page} of {pages} · {total} events</span>
              <div className="adm-pagination-btns">
                <button className="adm-btn" type="button" disabled={loading || offset === 0}
                        onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Previous</button>
                <button className="adm-btn" type="button"
                        disabled={loading || offset + PAGE_SIZE >= total}
                        onClick={() => setOffset(offset + PAGE_SIZE)}>Next</button>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}
