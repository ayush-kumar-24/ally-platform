/**
 * Registrations waiting on the team — the screen where access is granted.
 *
 * Sign-ups are switched off at the Supabase project level, so approving here
 * is not a formality: it is the only thing in the product that creates a login.
 * Approving mints the founder's identity and emails them "you're in", which is
 * why it goes through a confirmation step rather than being a quiet toggle.
 *
 * Oldest first, unlike the Calls screen. A call request is about an upcoming
 * date, so the soonest one matters most; this is a backlog, so the person who
 * has waited longest should be the one you answer.
 *
 * Two facts are kept apart on purpose. `status: approved` means somebody said
 * yes; `can_sign_in` means the identity actually exists behind it. They come
 * apart when the approval landed but the Supabase call did not, and a founder
 * in that state has been told they are in and cannot log in — so the row says
 * so loudly instead of showing a green tick.
 */

import { useCallback, useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import {
  approveRegistration,
  can,
  listWaitlist,
  rejectRegistration,
} from '../../services/admin';
import { ConfirmDialog, EmptyState, ErrorState, Flash, Loading, useFlash } from './AdminUI';

const CAPABILITY = 'manage_waitlist';

const FILTERS = [
  { key: 'pending', label: 'Waiting on us' },
  { key: 'approved', label: 'Approved' },
  { key: 'rejected', label: 'Rejected' },
  { key: 'all', label: 'Everyone' },
];

/** "9 Sep, 2:04 pm" — how long someone has been waiting, readably. */
function whenLabel(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString('en-IN', {
    day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit', hour12: true,
  });
}

/** How long they have been in the queue. The reason to answer today. */
function waitingFor(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const days = Math.floor((Date.now() - d) / 86400000);
  if (days <= 0) return 'Today';
  if (days === 1) return 'Waiting 1 day';
  return `Waiting ${days} days`;
}

export default function AdminWaitlist() {
  const { me } = useOutletContext();
  // Everyone who can see the panel's user list can read this queue, so Support
  // can answer "did my registration arrive?". Only manage_waitlist can answer it.
  const canDecide = can(me, CAPABILITY);

  const [rows, setRows] = useState([]);
  const [counts, setCounts] = useState({});
  const [cap, setCap] = useState(null);
  const [filter, setFilter] = useState('pending');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [flash, setFlash] = useFlash();
  const [busyId, setBusyId] = useState(null);
  // { row, mode: 'approve' | 'reject' }
  const [dialog, setDialog] = useState(null);
  const [reason, setReason] = useState('');

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    listWaitlist({ status: filter })
      .then((r) => {
        setRows(Array.isArray(r?.registrations) ? r.registrations : []);
        setCounts(r?.counts || {});
        setCap(r?.cap || null);
      })
      .catch(setError)
      .finally(() => setLoading(false));
  }, [filter]);

  useEffect(load, [load]);

  const act = async () => {
    if (!dialog) return;
    const { row, mode } = dialog;
    setBusyId(row.registration_id);
    try {
      if (mode === 'approve') {
        const updated = await approveRegistration(row.registration_id);
        // Flash reads { message, error } -- see AdminUI. The email case is
        // flagged as an error not because the grant failed (it did not) but
        // because it is the one outcome that still needs a human to act.
        setFlash(
          updated?.approval_email_sent_at
            ? { message: `${row.full_name} is in, and has been emailed.` }
            : {
                error: true,
                message: `${row.full_name} is in, but the email did not send. Tell them directly.`,
              },
        );
      } else {
        await rejectRegistration(row.registration_id, reason.trim());
        setFlash({ message: 'Rejected. Nobody is emailed; the reason is on the record.' });
      }
      setDialog(null);
      setReason('');
      load();
    } catch (err) {
      setFlash({ error: true, message: err?.detail || err?.message || 'That did not go through. Try again.' });
    } finally {
      setBusyId(null);
    }
  };

  const full = cap?.is_full;

  return (
    <section>
      <h1 className="adm-h1">Waitlist</h1>
      <p className="adm-sub">
        People who registered on the landing page. Nobody can sign in until
        somebody here approves them — approving creates their login and emails
        them that they are in.
      </p>

      <Flash flash={flash} />

      {/* The 300-place budget, above the queue rather than inside it: it is a
          fact about the phase, not about any one row. */}
      {cap && (
        <div className="adm-panel">
          <strong>{cap.approved} of {cap.cap}</strong> places taken
          {!full && <> · {cap.remaining} left</>}
          {full && (
            <span className="adm-warn">
              {' '}· The list is full. Only a super admin can approve past this.
            </span>
          )}
          {cap.can_grant_access === false && (
            <div className="adm-warn" style={{ marginTop: 6 }}>
              Access cannot be granted right now: the identity provider is not
              configured (SUPABASE_SERVICE_ROLE_KEY is unset), so approving
              would fail. Nothing here will let anyone in until that is set.
            </div>
          )}
        </div>
      )}

      <div className="adm-panel">
        <div className="adm-filters">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              className={`adm-btn${filter === f.key ? ' adm-btn--primary' : ''}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
              {counts[f.key] !== undefined && <> ({counts[f.key]})</>}
            </button>
          ))}
          <button className="adm-btn" type="button" onClick={load} disabled={loading}>
            Refresh
          </button>
        </div>

        {loading && <Loading label="Loading registrations…" />}
        {error && !loading && <ErrorState error={error} onRetry={load} />}

        {!loading && !error && rows.length === 0 && (
          <EmptyState
            title={filter === 'pending' ? 'Nothing waiting' : 'Nothing here'}
            hint={filter === 'pending'
              ? 'Every registration has been answered. Use the tabs above to see the ones you already handled.'
              : 'When someone registers on the landing page they will appear here.'}
          />
        )}

        {!loading && !error && rows.length > 0 && (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead>
                <tr>
                  <th>Who</th>
                  <th>Registered</th>
                  <th>What they said</th>
                  <th>Status</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const pending = r.status === 'pending';
                  return (
                    <tr key={r.registration_id}>
                      <td>
                        <div>{r.full_name}</div>
                        <div className="adm-mono adm-dim">{r.email}</div>
                        {r.company && <div className="adm-dim">{r.company}{r.role_title ? ` · ${r.role_title}` : ''}</div>}
                      </td>
                      <td>
                        <div>{whenLabel(r.created_at)}</div>
                        {pending && <div className="adm-dim">{waitingFor(r.created_at)}</div>}
                        {r.source && <span className="adm-tag">{r.source}</span>}
                      </td>
                      {/* Their own words, in full rather than truncated: it is
                          the whole basis for deciding yes or no. */}
                      <td className="adm-wrap">
                        {r.note || <span className="adm-dim">Nothing said</span>}
                        {r.stage && <div className="adm-dim">Stage: {r.stage}</div>}
                      </td>
                      <td>
                        {r.status === 'approved' && !r.can_sign_in ? (
                          <span className="adm-warn">Approved · no login created</span>
                        ) : (
                          r.status
                        )}
                        {r.status === 'approved' && r.can_sign_in && !r.approval_email_sent_at && (
                          <div className="adm-warn">Email not sent</div>
                        )}
                        {r.decided_by_email && (
                          <div className="adm-dim adm-mono">{r.decided_by_email}</div>
                        )}
                        {r.decision_reason && (
                          <div className="adm-dim">{r.decision_reason}</div>
                        )}
                      </td>
                      <td className="adm-actions">
                        {pending && canDecide ? (
                          <>
                            <button
                              className="adm-btn adm-btn--primary"
                              type="button"
                              disabled={busyId === r.registration_id || cap?.can_grant_access === false}
                              onClick={() => setDialog({ row: r, mode: 'approve' })}
                            >
                              Approve
                            </button>
                            <button
                              className="adm-btn"
                              type="button"
                              disabled={busyId === r.registration_id}
                              onClick={() => { setReason(''); setDialog({ row: r, mode: 'reject' }); }}
                            >
                              Reject
                            </button>
                          </>
                        ) : (
                          <span className="adm-dim">{pending ? 'View only' : 'Answered'}</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={Boolean(dialog) && dialog.mode === 'approve'}
        title="Let them in?"
        body={dialog
          ? `${dialog.row.full_name} (${dialog.row.email}) will get a login and an email telling them they are on the founder's list. This cannot be undone from here.`
          : ''}
        confirmLabel="Approve and email"
        busy={busyId !== null}
        onConfirm={act}
        onCancel={() => setDialog(null)}
      />

      <ConfirmDialog
        open={Boolean(dialog) && dialog.mode === 'reject'}
        title="Reject this registration?"
        body={
          <>
            <p>
              {dialog?.row?.full_name || 'This person'} will not be emailed —
              say why, so whoever looks at this later knows what was decided.
            </p>
            <textarea
              className="adm-textarea"
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Not a founder — agency enquiry"
              aria-label="Reason for rejecting"
            />
          </>
        }
        confirmLabel="Reject"
        danger
        busy={busyId !== null}
        /* Required by the API too. Blocking here means the team finds out
           before the request fails, not after. */
        disabled={reason.trim().length === 0}
        onConfirm={act}
        onCancel={() => { setDialog(null); setReason(''); }}
      />
    </section>
  );
}
