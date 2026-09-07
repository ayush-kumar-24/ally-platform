/**
 * Admin dashboard — metric cards from /admin/metrics plus the newest users.
 *
 * A card whose `available` is false renders "—" with a tooltip, never 0. Showing
 * ₹0 revenue when the payments table simply isn't readable would get acted on as
 * if it were real; "—" gets investigated instead.
 *
 * The numbers refresh themselves. A dashboard you have to press F5 on is a
 * screenshot, and a screenshot of "Live now" is worthless — the whole point of
 * that card is the last five minutes. Refreshes are quiet: the cards keep their
 * current values while the next poll is in flight, so the page never blanks, and
 * a poll that fails leaves the last good numbers on screen with a warning rather
 * than replacing them with an error page. Polling stops while the tab is hidden
 * and catches up the moment it comes back, so a tab left open overnight isn't
 * hitting the API every 30 seconds for nobody.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import { getMetrics, listUsers } from '../../services/admin';
import { ErrorState, Loading } from './AdminUI';

const REFRESH_MS = 30_000;

function formatValue(m) {
  if (!m.available || m.value === null) return '—';
  const n = typeof m.value === 'number' ? m.value : Number(m.value);
  if (Number.isNaN(n)) return String(m.value);
  const pretty = n.toLocaleString('en-IN');
  if (m.unit === '₹') return `₹${pretty}`;
  if (m.unit === '$') return `$${pretty}`;
  if (m.unit === 'ms') return `${pretty} ms`;
  return pretty;
}

function clockTime(date) {
  return date.toLocaleTimeString('en-IN', {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

export default function AdminDashboard() {
  const { me } = useOutletContext();
  const [metrics, setMetrics] = useState([]);
  const [recent, setRecent] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  // A failed *refresh* is not a failed page: the numbers on screen are still
  // the numbers, they're just older than they should be.
  const [staleReason, setStaleReason] = useState(null);
  const inFlight = useRef(false);

  const load = useCallback((opts = {}) => {
    const { silent = false } = opts;
    // Overlapping polls would let an older response land after a newer one and
    // walk the dashboard backwards.
    if (inFlight.current) return Promise.resolve();
    inFlight.current = true;
    if (silent) setRefreshing(true);
    else { setLoading(true); setError(null); }

    return Promise.all([
      getMetrics(),
      listUsers({ page_size: 5, sort_by: 'created_at', descending: true }),
    ])
      .then(([m, users]) => {
        setMetrics(m.metrics ?? []);
        setRecent(users.items ?? []);
        setUpdatedAt(new Date());
        setStaleReason(null);
        setError(null);
      })
      .catch(err => {
        if (silent) setStaleReason(err?.detail || err?.message || 'Refresh failed.');
        else setError(err);
      })
      .finally(() => {
        inFlight.current = false;
        setRefreshing(false);
        setLoading(false);
      });
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    let timer = null;
    const stop = () => { if (timer) { clearInterval(timer); timer = null; } };
    const start = () => { stop(); timer = setInterval(() => load({ silent: true }), REFRESH_MS); };

    const onVisibility = () => {
      if (document.hidden) {
        stop();
      } else {
        // Whatever is on screen is at least one hidden interval stale.
        load({ silent: true });
        start();
      }
    };

    if (!document.hidden) start();
    document.addEventListener('visibilitychange', onVisibility);
    return () => { stop(); document.removeEventListener('visibilitychange', onVisibility); };
  }, [load]);

  if (loading) return <Loading label="Loading dashboard…" />;
  if (error) return <ErrorState error={error} onRetry={() => load()} />;

  const unavailable = metrics.filter(m => !m.available);

  return (
    <>
      <h1 className="adm-h1">Dashboard</h1>
      <p className="adm-sub">
        Signed in as {me.email} — role <strong>{me.role.replace('_', ' ')}</strong>.
      </p>

      <p className="adm-sub" aria-live="polite">
        {updatedAt ? `Updated ${clockTime(updatedAt)}` : 'Updating…'}
        {refreshing && ' · refreshing…'}
        {' · auto-refreshes every 30s · '}
        <button className="adm-btn adm-btn--sm" type="button"
                onClick={() => load({ silent: true })} disabled={refreshing}>
          Refresh now
        </button>
      </p>

      {staleReason && (
        <div className="adm-flash" role="status">
          Showing the last good numbers — the most recent refresh failed ({staleReason}).
        </div>
      )}

      <div className="adm-grid">
        {metrics.map(m => (
          <div className="adm-panel" key={m.key}>
            <h2>{m.label}</h2>
            <div className={`adm-stat ${m.available ? '' : 'adm-muted'}`}
                 title={m.available ? undefined : (m.unavailable_reason || 'Not measurable')}>
              {formatValue(m)}
            </div>
            {!m.available && (
              <p className="adm-muted" style={{ fontSize: 12 }}>
                {m.unavailable_reason || 'Not measurable in this environment'}
              </p>
            )}
          </div>
        ))}
      </div>

      {unavailable.length > 0 && (
        <div className="adm-panel">
          <p className="adm-muted" style={{ margin: 0 }}>
            {unavailable.length} metric{unavailable.length === 1 ? '' : 's'} could not be
            measured — each card says why. These show “—” rather than zero so a
            number nobody could actually measure isn’t mistaken for a real one.
          </p>
        </div>
      )}

      <div className="adm-panel">
        <h2>Newest users</h2>
        {recent.length === 0 ? (
          <p className="adm-muted">No users yet.</p>
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead>
                <tr>
                  <th scope="col" className="adm-nosort">ID</th>
                  <th scope="col" className="adm-nosort">Name</th>
                  <th scope="col" className="adm-nosort">Email</th>
                  <th scope="col" className="adm-nosort">Status</th>
                  <th className="adm-nosort adm-num">Credits</th>
                </tr>
              </thead>
              <tbody>
                {recent.map(u => (
                  <tr key={u.founder_id}>
                    <td className="adm-mono">{u.founder_id}</td>
                    <td><Link to={`/admin/users/${u.founder_id}`}>{u.full_name || '—'}</Link></td>
                    <td>{u.email}</td>
                    <td><span className={`adm-pill ${u.status}`}>{u.status}</span></td>
                    <td className="adm-num">{u.credits_balance}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
