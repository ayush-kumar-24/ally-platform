/**
 * System page — feature flags, broadcasts and bulk credit operations.
 *
 * All three are Super-Admin-only server-side. Controls are hidden for other roles
 * as a convenience; the backend rejects the request either way.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import {
  bulkCredits,
  can,
  createBroadcast,
  CREDIT_OPS,
  deactivateBroadcast,
  listBroadcasts,
  listFlags,
  setFlag,
  USER_STATUSES,
} from '../../services/admin';
import { ConfirmDialog, EmptyState, ErrorState, Flash, Loading, useFlash } from './AdminUI';

function fmt(iso) {
  return iso ? new Date(iso).toLocaleString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  }) : '—';
}

export default function AdminSystem() {
  const { me } = useOutletContext();
  const mayManage = can(me, 'system_settings');
  const mayCredits = can(me, 'transfer_credits');

  const [flags, setFlags] = useState([]);
  const [casts, setCasts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [flash, setFlash] = useFlash();
  const [busy, setBusy] = useState(false);
  const [dialog, setDialog] = useState(null);
  const inFlight = useRef(false);

  // New flag
  const [flagKey, setFlagKey] = useState('');
  const [flagDesc, setFlagDesc] = useState('');
  // New broadcast
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [severity, setSeverity] = useState('info');
  const [audience, setAudience] = useState('all');
  const [audiencePlan, setAudiencePlan] = useState('');
  // Bulk credits
  const [op, setOp] = useState('add');
  const [amount, setAmount] = useState('');
  const [reason, setReason] = useState('');
  const [cohortPlan, setCohortPlan] = useState('');
  const [cohortStatus, setCohortStatus] = useState('');
  const [preview, setPreview] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([listFlags(), listBroadcasts()])
      .then(([f, b]) => { setFlags(f.flags ?? []); setCasts(b.items ?? []); })
      .catch(setError)
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  const run = async (fn, message) => {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    try {
      const res = await fn();
      setFlash({ message: typeof message === 'function' ? message(res) : message });
      setDialog(null);
      load();
    } catch (err) {
      setFlash({ error: true, message: err.detail || err.message || 'Action failed.' });
      setDialog(null);
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  };

  const cohortPayload = (dryRun) => ({
    operation: op,
    amount: Number(amount),
    reason,
    subscription: cohortPlan || undefined,
    status: cohortStatus || undefined,
    dry_run: dryRun,
  });

  const runPreview = async () => {
    if (!amount || !reason.trim()) {
      setFlash({ error: true, message: 'Amount and reason are both required.' });
      return;
    }
    try {
      setBusy(true);
      setPreview(await bulkCredits(cohortPayload(true)));
    } catch (err) {
      setFlash({ error: true, message: err.detail || 'Preview failed.' });
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <Loading label="Loading system settings…" />;
  if (error) return <ErrorState error={error} onRetry={load} />;

  return (
    <>
      <h1 className="adm-h1">System</h1>
      <p className="adm-sub">Feature flags, broadcasts and bulk credit operations.</p>
      <Flash flash={flash} />

      {/* ── Feature flags ── */}
      <div className="adm-panel">
        <h2>Feature flags</h2>
        {mayManage && (
          <form className="adm-filters" onSubmit={(e) => {
            e.preventDefault();
            if (!flagKey.trim()) return;
            run(() => setFlag(flagKey.trim(), false, flagDesc), `Flag "${flagKey}" created (off).`)
              .then(() => { setFlagKey(''); setFlagDesc(''); });
          }}>
            <input className="adm-input" placeholder="new_flag_key" value={flagKey}
                   onChange={e => setFlagKey(e.target.value)} aria-label="Flag key" />
            <input className="adm-input adm-search" placeholder="Description" value={flagDesc}
                   onChange={e => setFlagDesc(e.target.value)} aria-label="Flag description" />
            <button className="adm-btn adm-btn--primary" type="submit" disabled={busy}>
              Create flag
            </button>
          </form>
        )}
        {flags.length === 0 ? (
          <EmptyState title="No feature flags" hint="Create one to gate a feature." />
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead>
                <tr>
                  <th scope="col" className="adm-nosort">Key</th>
                  <th scope="col" className="adm-nosort">Description</th>
                  <th scope="col" className="adm-nosort">State</th>
                  <th scope="col" className="adm-nosort">Updated</th>
                  {mayManage && <th scope="col" className="adm-nosort"><span className="sr-only">Actions</span></th>}
                </tr>
              </thead>
              <tbody>
                {flags.map(f => (
                  <tr key={f.key}>
                    <td className="adm-mono">{f.key}</td>
                    <td>{f.description || <span className="adm-muted">—</span>}</td>
                    <td>
                      <span className={`adm-pill ${f.enabled ? 'active' : 'inactive'}`}>
                        {f.enabled ? 'on' : 'off'}
                      </span>
                    </td>
                    <td className="adm-muted">{fmt(f.updated_at)}</td>
                    {mayManage && (
                      <td>
                        <button className="adm-btn adm-btn--sm" type="button" disabled={busy}
                                onClick={() => run(
                                  () => setFlag(f.key, !f.enabled, f.description || ''),
                                  `${f.key} turned ${f.enabled ? 'off' : 'on'}.`)}>
                          Turn {f.enabled ? 'off' : 'on'}
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Broadcasts ── */}
      <div className="adm-panel">
        <h2>Broadcasts</h2>
        {mayManage && (
          <form onSubmit={(e) => {
            e.preventDefault();
            setDialog({
              title: 'Publish this broadcast?',
              body: <>It becomes visible to <strong>{audience === 'plan' ? `${audiencePlan} users` : `${audience} users`}</strong> immediately.</>,
              confirmLabel: 'Publish',
              run: () => run(() => createBroadcast({
                title, body, severity, audience,
                audience_plan: audience === 'plan' ? audiencePlan : undefined,
              }), 'Broadcast published.').then(() => { setTitle(''); setBody(''); }),
            });
          }}>
            <div className="adm-filters">
              <input className="adm-input adm-search" placeholder="Title" value={title}
                     onChange={e => setTitle(e.target.value)} aria-label="Broadcast title" />
              <select className="adm-select" value={severity}
                      onChange={e => setSeverity(e.target.value)} aria-label="Severity">
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="critical">Critical</option>
              </select>
              <select className="adm-select" value={audience}
                      onChange={e => setAudience(e.target.value)} aria-label="Audience">
                <option value="all">All users</option>
                <option value="plan">By plan</option>
                <option value="active">Active users</option>
                <option value="suspended">Suspended users</option>
              </select>
              {audience === 'plan' && (
                <input className="adm-input" placeholder="Plan (e.g. pro)" value={audiencePlan}
                       onChange={e => setAudiencePlan(e.target.value)} aria-label="Plan" />
              )}
            </div>
            <div className="adm-filters">
              <textarea className="adm-input adm-search" rows={2} placeholder="Message body"
                        value={body} onChange={e => setBody(e.target.value)}
                        aria-label="Broadcast body" />
              <button className="adm-btn adm-btn--primary" type="submit"
                      disabled={busy || !title.trim() || !body.trim()}>
                Publish
              </button>
            </div>
          </form>
        )}
        {casts.length === 0 ? (
          <EmptyState title="No broadcasts" hint="Published messages appear here." />
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead>
                <tr>
                  <th scope="col" className="adm-nosort">Title</th>
                  <th scope="col" className="adm-nosort">Severity</th>
                  <th scope="col" className="adm-nosort">Audience</th>
                  <th scope="col" className="adm-nosort">State</th>
                  <th scope="col" className="adm-nosort">Created</th>
                  {mayManage && <th scope="col" className="adm-nosort"><span className="sr-only">Actions</span></th>}
                </tr>
              </thead>
              <tbody>
                {casts.map(b => (
                  <tr key={b.broadcast_id}>
                    <td>{b.title}</td>
                    <td>{b.severity}</td>
                    <td>{b.audience === 'plan' ? `plan: ${b.audience_plan}` : b.audience}</td>
                    <td>
                      <span className={`adm-pill ${b.active ? 'active' : 'inactive'}`}>
                        {b.active ? 'active' : 'inactive'}
                      </span>
                    </td>
                    <td className="adm-muted">{fmt(b.created_at)}</td>
                    {mayManage && (
                      <td>
                        {b.active && (
                          <button className="adm-btn adm-btn--sm" type="button" disabled={busy}
                                  onClick={() => run(() => deactivateBroadcast(b.broadcast_id),
                                                     'Broadcast deactivated.')}>
                            Deactivate
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Bulk credits ── */}
      {mayCredits && (
        <div className="adm-panel">
          <h2>Bulk credit operation</h2>
          <p className="adm-muted">
            Applies to every user matching the cohort. Preview first — the run itself
            cannot be undone.
          </p>
          <div className="adm-filters">
            <select className="adm-select" value={op} onChange={e => setOp(e.target.value)}
                    aria-label="Operation">
              {CREDIT_OPS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            <input className="adm-input" type="number" min="0" placeholder="Amount"
                   value={amount} onChange={e => { setAmount(e.target.value); setPreview(null); }}
                   aria-label="Amount" style={{ width: 120 }} />
            <select className="adm-select" value={cohortPlan}
                    onChange={e => { setCohortPlan(e.target.value); setPreview(null); }}
                    aria-label="Cohort plan">
              <option value="">Any plan</option>
              <option value="free">free</option>
              <option value="pro">pro</option>
              <option value="elite">elite</option>
            </select>
            <select className="adm-select" value={cohortStatus}
                    onChange={e => { setCohortStatus(e.target.value); setPreview(null); }}
                    aria-label="Cohort status">
              <option value="">Any status</option>
              {USER_STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <input className="adm-input adm-search" placeholder="Reason (required)"
                   value={reason} onChange={e => setReason(e.target.value)} aria-label="Reason" />
            <button className="adm-btn" type="button" onClick={runPreview} disabled={busy}>
              Preview
            </button>
          </div>

          {preview && (
            <div className="adm-flash">
              Matches <strong>{preview.matched}</strong> user{preview.matched === 1 ? '' : 's'}.
              {preview.matched > 0 && (
                <button className="adm-btn adm-btn--danger adm-btn--sm"
                        style={{ marginLeft: 12 }} type="button" disabled={busy}
                        onClick={() => setDialog({
                          title: `Apply to ${preview.matched} users?`,
                          danger: true,
                          confirmLabel: `Apply to ${preview.matched}`,
                          body: <>
                            <strong>{op.toUpperCase()} {amount}</strong> credits for{' '}
                            {preview.matched} users.<br />Reason: {reason}
                            <br /><br />Every change is written to the credit ledger and cannot be undone.
                          </>,
                          run: () => run(() => bulkCredits(cohortPayload(false)),
                            (res) => `Applied to ${res.succeeded}; ${res.failure_count} failed.`)
                            .then(() => setPreview(null)),
                        })}>
                  Apply
                </button>
              )}
            </div>
          )}
        </div>
      )}

      <ConfirmDialog
        open={Boolean(dialog)}
        title={dialog?.title}
        body={dialog?.body}
        danger={dialog?.danger}
        confirmLabel={dialog?.confirmLabel}
        busy={busy}
        onConfirm={() => dialog?.run?.()}
        onCancel={() => setDialog(null)}
      />
    </>
  );
}
