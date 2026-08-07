/**
 * User detail — profile, business, subscription, consent, activity, plus the credit
 * ledger and the admin actions.
 *
 * Controls the caller lacks the capability for are hidden, which is convenience
 * only: the backend rejects the request regardless of what is rendered here.
 * Every destructive action goes through a confirmation dialog and every request is
 * guarded against double-submission by a synchronous ref.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useOutletContext, useParams } from 'react-router-dom';
import {
  adjustCredits,
  can,
  changeStatus,
  CREDIT_OPS,
  deleteUser,
  getCredits,
  getTimeline,
  getUser,
  resetConversations,
  resetDiagnosis,
} from '../../services/admin';
import {
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Flash,
  Loading,
  useFlash,
} from './AdminUI';

function fmt(iso) {
  return iso ? new Date(iso).toLocaleString('en-IN', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  }) : '—';
}

function KV({ data, keys }) {
  const entries = (keys ?? Object.keys(data ?? {})).filter(k => data?.[k] !== undefined);
  if (entries.length === 0) return <p className="adm-muted">No data.</p>;
  return (
    <dl className="adm-kv">
      {entries.map(k => (
        <div key={k} style={{ display: 'contents' }}>
          <dt>{k.replace(/_/g, ' ')}</dt>
          <dd>{data[k] === null || data[k] === '' ? '—' : String(data[k])}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function AdminUserDetail() {
  const { id } = useParams();
  const { me } = useOutletContext();

  const [detail, setDetail] = useState(null);
  const [ledger, setLedger] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [flash, setFlash] = useFlash();

  const [dialog, setDialog] = useState(null);   // { title, body, danger, run }
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);

  // Credit form
  const [op, setOp] = useState('add');
  const [amount, setAmount] = useState('');
  const [reason, setReason] = useState('');

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    // The ledger and timeline are supplementary — if either is unavailable the
    // profile must still render, so their failures are caught individually.
    Promise.all([
      getUser(id),
      getCredits(id).catch(() => null),
      getTimeline(id).catch(() => null),
    ])
      .then(([d, l, t]) => { setDetail(d); setLedger(l); setTimeline(t?.events ?? []); })
      .catch(setError)
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(load, [load]);

  const run = async (fn, successMessage) => {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    try {
      const res = await fn();
      setFlash({ message: successMessage(res) });
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

  const submitCredits = (e) => {
    e.preventDefault();
    if (!amount || !reason.trim()) {
      setFlash({ error: true, message: 'Amount and reason are both required.' });
      return;
    }
    const label = CREDIT_OPS.find(o => o.value === op)?.label ?? op;
    setDialog({
      title: 'Apply credit change?',
      danger: op === 'remove' || op === 'set',
      confirmLabel: 'Apply',
      body: (
        <>
          <strong>{label} {amount}</strong> for founder #{id}.<br />
          Reason: {reason}
          <br /><br />
          This is recorded permanently in the credit ledger and the audit log.
        </>
      ),
      run: () => run(
        () => adjustCredits(id, { operation: op, amount, reason }),
        (res) => `${label} applied. Balance is now ${res.balance}.`,
      ),
    });
  };

  if (loading) return <Loading label="Loading user…" />;
  if (error) return <ErrorState error={error} onRetry={load} />;
  if (!detail) return <EmptyState title="User not found" />;

  const canCredits = can(me, 'transfer_credits');
  const canSuspend = can(me, 'suspend_user');
  const canDelete = can(me, 'delete_user');
  const canResetDiag = can(me, 'reset_diagnosis');
  const canResetChat = can(me, 'reset_conversations');
  const balance = ledger?.balance ?? detail.credits?.balance ?? 0;

  return (
    <>
      <p className="adm-sub"><Link to="/admin/users">← Back to users</Link></p>
      <h1 className="adm-h1">
        {detail.profile?.full_name || `Founder #${id}`}{' '}
        <span className={`adm-pill ${detail.profile?.status ?? 'active'}`}>
          {detail.profile?.status ?? 'active'}
        </span>
      </h1>
      <p className="adm-sub">{detail.profile?.email} · founder ID {detail.founder_id}</p>

      <Flash flash={flash} />

      <div className="adm-grid">
        <div className="adm-panel">
          <h2>Profile</h2>
          <KV data={detail.profile} />
        </div>
        <div className="adm-panel">
          <h2>Business</h2>
          <KV data={detail.business} />
        </div>
        <div className="adm-panel">
          <h2>Subscription</h2>
          {detail.subscription ? <KV data={detail.subscription} />
            : <p className="adm-muted">No subscription record.</p>}
        </div>
        <div className="adm-panel">
          <h2>Consent</h2>
          {detail.consent ? <KV data={detail.consent} />
            : <p className="adm-muted">No consent recorded.</p>}
        </div>
        <div className="adm-panel">
          <h2>Activity</h2>
          <dl className="adm-kv">
            <dt>Chats</dt><dd>{detail.chat_count}</dd>
            <dt>Reports</dt><dd>{detail.reports?.length ?? 0}</dd>
            <dt>Diagnosis sessions</dt><dd>{detail.diagnosis_history?.length ?? 0}</dd>
            <dt>Logins recorded</dt><dd>{detail.login_history?.length ?? 0}</dd>
            <dt>Privacy requests</dt><dd>{detail.privacy_requests?.length ?? 0}</dd>
          </dl>
        </div>
        <div className="adm-panel">
          <h2>Credits</h2>
          <div className="adm-stat">{balance}</div>
          <p className="adm-muted">Current balance</p>
        </div>
      </div>

      {/* ── Credit ledger ── */}
      <div className="adm-panel">
        <h2>Credit ledger</h2>
        {canCredits ? (
          <form className="adm-filters" onSubmit={submitCredits}>
            <select className="adm-select" value={op} onChange={e => setOp(e.target.value)}
                    aria-label="Credit operation">
              {CREDIT_OPS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            <input className="adm-input" type="number" min="0" placeholder="Amount"
                   value={amount} onChange={e => setAmount(e.target.value)}
                   aria-label="Amount" style={{ width: 120 }} />
            <input className="adm-input adm-search" type="text" placeholder="Reason (required)"
                   value={reason} onChange={e => setReason(e.target.value)} aria-label="Reason" />
            <button className="adm-btn adm-btn--primary" type="submit" disabled={busy}>
              Apply
            </button>
          </form>
        ) : (
          <p className="adm-muted">Your role cannot modify credits.</p>
        )}

        {!ledger || ledger.items.length === 0 ? (
          <EmptyState title="No credit transactions" hint="Adjustments will appear here." />
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead>
                <tr>
                  <th scope="col" className="adm-nosort">When</th>
                  <th scope="col" className="adm-nosort">Type</th>
                  <th className="adm-nosort adm-num">Amount</th>
                  <th className="adm-nosort adm-num">Before</th>
                  <th className="adm-nosort adm-num">After</th>
                  <th scope="col" className="adm-nosort">Reason</th>
                  <th scope="col" className="adm-nosort">Admin</th>
                </tr>
              </thead>
              <tbody>
                {ledger.items.map(t => (
                  <tr key={t.id}>
                    <td className="adm-muted">{fmt(t.created_at)}</td>
                    <td>{t.type}</td>
                    <td className={`adm-num ${t.amount >= 0 ? 'adm-pos' : 'adm-neg'}`}>
                      {t.amount >= 0 ? `+${t.amount}` : t.amount}
                    </td>
                    <td className="adm-num">{t.balance_before}</td>
                    <td className="adm-num">{t.balance_after}</td>
                    <td>{t.reason}</td>
                    <td className="adm-mono">#{t.admin_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Timeline ── */}
      <div className="adm-panel">
        <h2>Timeline</h2>
        {timeline.length === 0 ? (
          <EmptyState title="No timeline events"
                      hint="Account, diagnosis, report, credit and admin events appear here." />
        ) : (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead>
                <tr>
                  <th scope="col" className="adm-nosort">When</th>
                  <th scope="col" className="adm-nosort">Kind</th>
                  <th scope="col" className="adm-nosort">Event</th>
                  <th scope="col" className="adm-nosort">Detail</th>
                </tr>
              </thead>
              <tbody>
                {timeline.map((e, i) => (
                  <tr key={`${e.at}-${i}`}>
                    <td className="adm-muted">{fmt(e.at)}</td>
                    <td><span className="adm-pill inactive">{e.kind}</span></td>
                    <td>{e.title}</td>
                    <td className="adm-muted">{e.detail || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Actions ── */}
      <div className="adm-panel">
        <h2>Actions</h2>
        <div className="adm-actions">
          {canResetDiag && (
            <button className="adm-btn" type="button" disabled={busy} onClick={() => setDialog({
              title: 'Reset diagnosis?',
              body: 'This clears the founder\'s diagnosis progress so they can start again. It cannot be undone.',
              danger: true, confirmLabel: 'Reset diagnosis',
              run: () => run(() => resetDiagnosis(id), r => `Diagnosis reset (${r.rows_affected} row(s)).`),
            })}>Reset diagnosis</button>
          )}
          {canResetChat && (
            <button className="adm-btn" type="button" disabled={busy} onClick={() => setDialog({
              title: 'Delete chat history?',
              body: 'Every conversation for this founder is permanently deleted. It cannot be undone.',
              danger: true, confirmLabel: 'Delete conversations',
              run: () => run(() => resetConversations(id), r => `Conversations deleted (${r.rows_affected} row(s)).`),
            })}>Reset conversations</button>
          )}
          {canSuspend && (
            <>
              <button className="adm-btn" type="button" disabled={busy} onClick={() => setDialog({
                title: 'Suspend this user?',
                body: 'They will lose access until reactivated. This is reversible.',
                confirmLabel: 'Suspend',
                run: () => run(() => changeStatus(id, 'suspended', 'Suspended from admin panel'),
                               () => 'User suspended.'),
              })}>Suspend</button>
              <button className="adm-btn" type="button" disabled={busy} onClick={() => setDialog({
                title: 'Reactivate this user?',
                body: 'Access is restored immediately.',
                confirmLabel: 'Activate',
                run: () => run(() => changeStatus(id, 'active', 'Reactivated from admin panel'),
                               () => 'User reactivated.'),
              })}>Activate</button>
            </>
          )}
          {canDelete && (
            <button className="adm-btn adm-btn--danger" type="button" disabled={busy}
                    onClick={() => setDialog({
                      title: 'Delete this user?',
                      body: 'The account is banned and loses all access. Data is retained for compliance — permanent erasure runs through the Privacy Center.',
                      danger: true, confirmLabel: 'Delete user',
                      run: () => run(() => deleteUser(id, 'Deleted from admin panel'),
                                     () => 'User deleted (banned).'),
                    })}>Delete user</button>
          )}
          {!canResetDiag && !canResetChat && !canSuspend && !canDelete && (
            <p className="adm-muted">Your role has no actions available for this user.</p>
          )}
        </div>
      </div>

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
