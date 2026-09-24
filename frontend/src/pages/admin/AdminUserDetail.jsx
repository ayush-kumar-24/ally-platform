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
  regenerateReport,
  resetConversations,
  resetDiagnosis,
  resetOnboarding,
  setPlan,
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

/* Both names, deliberately. The tier id is what the database holds and what an
   admin will see in logs and in the users list; the plan name is what the
   founder was sold. Two of the four differ -- basic is "Starter", starter is
   "Plus" -- and an admin picking from names alone would grant the wrong one.
   Mirrors app/plans/catalog.py; the API validates against it regardless. */
const PLAN_TIERS = [
  { value: 'free', label: 'Free (free)' },
  { value: 'basic', label: 'Starter — ₹199 (basic)' },
  { value: 'starter', label: 'Plus — ₹499 (starter)' },
  { value: 'pro', label: 'Pro — ₹999 (pro)' },
];

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

  // Plan form
  const [planTier, setPlanTier] = useState('');
  const [planReason, setPlanReason] = useState('');

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

  const submitPlan = (e) => {
    e.preventDefault();
    if (!planTier || !planReason.trim()) {
      setFlash({ error: true, message: 'Plan and reason are both required.' });
      return;
    }
    const label = PLAN_TIERS.find(t => t.value === planTier)?.label ?? planTier;
    setDialog({
      title: 'Change this founder\u2019s plan?',
      // Named rather than implied: this grants or removes paid access without a
      // payment, so the admin should see exactly which plan before confirming.
      body: `They will be moved to ${label} immediately. No payment is taken and no
             subscription record is written; the change is recorded in the audit log.`,
      confirmLabel: 'Change plan',
      run: () => run(() => setPlan(id, planTier, planReason.trim()),
                     () => `Plan changed to ${label}.`)
        .then(() => { setPlanTier(''); setPlanReason(''); }),
    });
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
  const canPlan = can(me, 'modify_subscription');
  const canResetDiag = can(me, 'reset_diagnosis');
  const canResetChat = can(me, 'reset_conversations');
  const canResetOnboarding = can(me, 'reset_onboarding');
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
          <h2>Terms &amp; Privacy</h2>
          {detail.consent ? <KV data={detail.consent} />
            : <p className="adm-muted">Never accepted.</p>}
        </div>
        {/* Its own panel, not folded into the one above. The cookie banner is a
            separate consent under a separate basis, and until now the admin
            could not see it at all -- a founder who rejected analytics looked
            identical to one who had never been shown the banner. Those are the
            two answers this panel now tells apart. */}
        <div className="adm-panel">
          <h2>Cookies</h2>
          {detail.cookie_consent ? <KV data={detail.cookie_consent} />
            : <p className="adm-muted">Banner never answered.</p>}
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

      {/* ── Plan ──
          Its own panel rather than a button in Actions: it needs a plan, a
          reason and the current value in view, which is a form, not a verb. */}
      <div className="adm-panel">
        <h2>Plan</h2>
        <p className="adm-muted" style={{ marginTop: 0 }}>
          Currently <strong>{detail.profile?.plan_type || 'free'}</strong>. Use this when a
          payment captured but the plan did not land — the payment itself is not altered.
        </p>
        {canPlan ? (
          <form className="adm-filters" onSubmit={submitPlan}>
            <select className="adm-select" value={planTier}
                    onChange={e => setPlanTier(e.target.value)} aria-label="Plan">
              <option value="">Choose a plan…</option>
              {PLAN_TIERS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
            <input className="adm-input adm-search" type="text" placeholder="Reason (required)"
                   value={planReason} onChange={e => setPlanReason(e.target.value)}
                   aria-label="Reason for the plan change" />
            <button className="adm-btn adm-btn--primary" type="submit" disabled={busy}>
              Change plan
            </button>
          </form>
        ) : (
          <p className="adm-muted">Your role cannot change plans.</p>
        )}
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
          {canResetOnboarding && (
            <button className="adm-btn" type="button" disabled={busy} onClick={() => setDialog({
              title: 'Reset onboarding?',
              body: 'Clears every answer the founder gave during onboarding, so Ally asks '
                + 'them again from the first question. Their diagnosis, report and chat '
                + 'history are kept. It cannot be undone.',
              danger: true, confirmLabel: 'Reset onboarding',
              run: () => run(() => resetOnboarding(id), r => `Onboarding reset (${r.rows_affected} row(s)).`),
            })}>Reset onboarding</button>
          )}
          {/* Body rewritten to say what this now does. It used to clear two
              columns that the lifetime cap does not read, so it promised a
              fresh diagnosis and did not deliver one -- see reset_diagnosis in
              admin/users_db_repository.py. */}
          {canResetDiag && (
            <button className="adm-btn" type="button" disabled={busy} onClick={() => setDialog({
              title: 'Reset diagnosis?',
              body: 'Deletes the founder\'s diagnosis sessions, answers, Founder DNA, '
                + 'Current Problem answers, report and any share links to it, so they can '
                + 'run a new diagnosis from scratch. Their onboarding answers and chat '
                + 'history are kept. It cannot be undone.',
              danger: true, confirmLabel: 'Reset diagnosis',
              run: () => run(() => resetDiagnosis(id), r => `Diagnosis reset (${r.rows_affected} row(s)).`),
            })}>Reset diagnosis</button>
          )}
          {/* Same capability the endpoint enforces (panel_service.regenerate_report
              requires RESET_DIAGNOSIS). The endpoint has existed all along with
              nothing calling it, which left a founder's report frozen for good:
              the narrative is cached on narrative_snapshot and never rebuilt on
              read, so a prompt or generator change could not reach a report that
              already existed. */}
          {canResetDiag && (
            <button className="adm-btn" type="button" disabled={busy} onClick={() => setDialog({
              title: 'Regenerate this report?',
              body: 'Re-runs the diagnosis reasoning on the founder\'s latest completed '
                + 'session and replaces their report. Use it after a change to how '
                + 'reports are written. This takes a few minutes — keep this tab open.',
              confirmLabel: 'Regenerate report',
              run: () => run(
                async () => {
                  const res = await regenerateReport(id, 'Regenerated from admin panel');
                  // 200 does not mean it worked -- the pipeline reports failure in
                  // the body, so without this an admin is told a failed run is done.
                  const r = res?.result ?? {};
                  if (r.status !== 'regenerated' && r.status !== 'no_change') {
                    throw new Error(r.error || r.reason || 'Report regeneration failed.');
                  }
                  return res;
                },
                (res) => (res.result.status === 'regenerated'
                  ? `Report regenerated (report #${res.result.report_id}).`
                  : 'Already up to date — nothing regenerated.'),
              ),
            })}>Regenerate report</button>
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
