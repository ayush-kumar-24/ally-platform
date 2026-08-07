/**
 * Admin dashboard — metric cards from /admin/metrics plus the newest users.
 *
 * A card whose `available` is false renders "—" with a tooltip, never 0. Showing
 * ₹0 revenue when the payments table simply isn't readable would get acted on as
 * if it were real; "—" gets investigated instead.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import { getMetrics, listUsers } from '../../services/admin';
import { ErrorState, Loading } from './AdminUI';

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

export default function AdminDashboard() {
  const { me } = useOutletContext();
  const [metrics, setMetrics] = useState([]);
  const [recent, setRecent] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      getMetrics(),
      listUsers({ page_size: 5, sort_by: 'created_at', descending: true }),
    ])
      .then(([m, users]) => {
        setMetrics(m.metrics ?? []);
        setRecent(users.items ?? []);
      })
      .catch(setError)
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  if (loading) return <Loading label="Loading dashboard…" />;
  if (error) return <ErrorState error={error} onRetry={load} />;

  const unavailable = metrics.filter(m => !m.available);

  return (
    <>
      <h1 className="adm-h1">Dashboard</h1>
      <p className="adm-sub">
        Signed in as {me.email} — role <strong>{me.role.replace('_', ' ')}</strong>.
      </p>

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
            measured — the underlying tables are missing or unpopulated in this
            environment. These show “—” rather than zero so they aren’t mistaken for real values.
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
