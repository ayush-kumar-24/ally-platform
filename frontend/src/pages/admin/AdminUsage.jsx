/**
 * Usage dashboard — tokens, cost and the unbilled backlog.
 *
 * Cost is labelled "estimated" everywhere because it is tokens × a blended rate,
 * not a provider invoice. Presenting it as a real figure would invite someone to
 * reconcile it against a bill it was never going to match.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getUsage, reconcileUsage } from '../../services/admin';
import { can } from '../../services/plans';
import { useOutletContext } from 'react-router-dom';
import { ConfirmDialog, EmptyState, ErrorState, Flash, Loading, useFlash } from './AdminUI';

const n = (v) => (typeof v === 'number' ? v.toLocaleString('en-IN') : v ?? '—');
const usd = (v) => (typeof v === 'number' ? `$${v.toFixed(4)}` : '—');

export default function AdminUsage() {
  const { me } = useOutletContext();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [flash, setFlash] = useFlash();
  const [dialog, setDialog] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    getUsage()
      .then(setData)
      .catch(setError)
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  const runReconcile = async () => {
    setBusy(true);
    try {
      const res = await reconcileUsage();
      setFlash({ message: `Reconciled ${res.result.resolved}; ${res.result.failed} still pending.` });
      setDialog(false);
      load();
    } catch (err) {
      setFlash({ error: true, message: err.detail || 'Reconciliation failed.' });
      setDialog(false);
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <Loading label="Loading usage…" />;
  if (error) return <ErrorState error={error} onRetry={load} />;

  const s = data?.summary ?? {};
  const daily = data?.daily ?? [];
  const top = data?.top_consumers ?? [];
  const peak = Math.max(1, ...daily.map(d => d.tokens));
  const mayReconcile = can({ features: me?.capabilities }, 'transfer_credits');

  const CARDS = [
    { label: 'Tokens today', value: n(s.tokens_today) },
    { label: 'Tokens this month', value: n(s.tokens_month) },
    { label: 'Requests this month', value: n(s.requests_month) },
    { label: 'Avg tokens / request', value: n(s.avg_tokens_per_request) },
    { label: 'Estimated cost today', value: usd(s.estimated_cost_today_usd) },
    { label: 'Estimated cost this month', value: usd(s.estimated_cost_month_usd) },
  ];

  return (
    <>
      <h1 className="adm-h1">Usage</h1>
      <p className="adm-sub">
        Token consumption and estimated cost. Cost is an estimate at{' '}
        ${s.cost_basis_per_1k_usd ?? '—'} per 1,000 tokens — not a provider invoice.
      </p>
      <Flash flash={flash} />

      <div className="adm-grid">
        {CARDS.map(c => (
          <div className="adm-panel" key={c.label}>
            <h2>{c.label}</h2>
            <div className="adm-stat">{c.value}</div>
          </div>
        ))}
      </div>

      {/* Unbilled backlog — the thing that used to vanish silently */}
      <div className="adm-panel">
        <h2>Unbilled usage</h2>
        {s.unbilled_tokens ? (
          <>
            <p className="adm-muted" style={{ marginTop: 0 }}>
              <strong style={{ color: 'var(--adm-danger)' }}>
                {n(s.unbilled_tokens)} tokens ({n(s.unbilled_credits)} credits)
              </strong>{' '}
              were delivered but not charged, because metering failed after the reply
              had already been produced. Replaying charges them against the ledger.
            </p>
            {mayReconcile && (
              <button className="adm-btn adm-btn--primary" type="button"
                      disabled={busy} onClick={() => setDialog(true)}>
                Reconcile now
              </button>
            )}
          </>
        ) : (
          <p className="adm-muted" style={{ margin: 0 }}>
            Nothing unbilled. Every delivered response has been charged.
          </p>
        )}
      </div>

      {/* Daily series */}
      <div className="adm-panel">
        <h2>Daily tokens</h2>
        {daily.length === 0 ? (
          <EmptyState title="No usage recorded yet"
                      hint="Token usage appears here once founders start chatting." />
        ) : (
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 120,
                        overflowX: 'auto', paddingTop: 8 }}>
            {daily.map(d => (
              <div key={d.date} title={`${d.date}: ${n(d.tokens)} tokens · ${usd(d.estimated_cost_usd)}`}
                   style={{
                     flex: '1 0 14px', minWidth: 14,
                     height: `${Math.round((d.tokens / peak) * 100)}%`,
                     minHeight: d.tokens ? 2 : 0,
                     background: 'var(--adm-accent)', borderRadius: '3px 3px 0 0',
                   }} />
            ))}
          </div>
        )}
      </div>

      {/* Top consumers */}
      <div className="adm-panel">
        <h2>Top consumers this month</h2>
        {top.length === 0 ? (
          <EmptyState title="No consumption yet" />
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead>
                <tr>
                  <th className="adm-nosort">Founder</th>
                  <th className="adm-nosort">Email</th>
                  <th className="adm-nosort">Plan</th>
                  <th className="adm-nosort adm-num">Tokens</th>
                  <th className="adm-nosort adm-num">Est. cost</th>
                </tr>
              </thead>
              <tbody>
                {top.map(u => (
                  <tr key={u.founder_id}>
                    <td><Link to={`/admin/users/${u.founder_id}`}>{u.full_name || `#${u.founder_id}`}</Link></td>
                    <td>{u.email}</td>
                    <td>{u.plan_type || '—'}</td>
                    <td className="adm-num">{n(u.tokens)}</td>
                    <td className="adm-num">{usd(u.estimated_cost_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={dialog}
        title="Reconcile unbilled usage?"
        body={<>This charges {n(s.unbilled_credits)} credits across the affected
          founders. Each charge is a real ledger entry and cannot be undone.</>}
        confirmLabel="Reconcile"
        busy={busy}
        onConfirm={runReconcile}
        onCancel={() => setDialog(false)}
      />
    </>
  );
}
