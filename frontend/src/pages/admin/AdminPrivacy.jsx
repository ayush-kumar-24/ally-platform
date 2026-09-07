/**
 * The Privacy Center review queue — requests that need a person.
 *
 * WHY THIS PAGE EXISTS. The backend has had `GET /admin/privacy-requests` and
 * `PATCH /admin/privacy-requests/{id}` for a while, with RBAC and an audit
 * trail, and NOTHING in the UI called either of them. Every data-correction
 * request a founder submitted went into a table nobody could see without
 * opening a database client. The rows were real; the queue was invisible.
 *
 * THE ONE THAT CANNOT WAIT is `email_change`. A founder who mistyped their
 * address at signup is signed in as an inbox they do not own: every login code,
 * confirmation and report link goes somewhere else, and they cannot email us
 * from the address on their account because that address is the mistake. This
 * row is their only route back, so it is sorted to the top and marked.
 *
 * AND IT IS THE ONE TO BE CAREFUL WITH. Pointing an account at a new inbox
 * means whoever controls that inbox can take the account over with a password
 * reset. So the flow here deliberately does NOT offer a one-click "apply" — it
 * offers "working on it" and "done", and the warning says verify first. The
 * actual change happens in the auth provider, by a human who has checked.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import { can, listPrivacyRequests, resolvePrivacyRequest } from '../../services/admin';
import { ConfirmDialog, EmptyState, ErrorState, Flash, Loading, useFlash } from './AdminUI';

const VIEW_CAPABILITY = 'view_users';
const MANAGE_CAPABILITY = 'manage_privacy_requests';

/** Founder-facing wording, so the team and the founder describe it the same way. */
const TYPE_LABELS = {
  correct_data: 'Data correction',
  email_change: 'Email change',
  grievance: 'Privacy complaint',
  view_data: 'View data summary',
  download_data: 'Download data',
  portability: 'Data portability export',
  restrict_processing: 'Restrict processing',
  withdraw_consent: 'Withdraw consent',
  delete_account: 'Account deletion',
  cancel_deletion: 'Deletion cancelled',
};

function whenLabel(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString('en-IN', {
    day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit', hour12: true,
  });
}

/**
 * How long it has been sitting. The commitment to founders is 30 days, so this
 * counts toward that rather than showing a raw age nobody can act on.
 */
/** Hours since it arrived -- the unit a 48-hour promise is actually measured in. */
function ackClock(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const hours = Math.floor((new Date() - d) / 3600000);
  if (hours < 1) return { label: 'just now', tone: 'ok' };
  if (hours < 48) return { label: `${hours}h ago — ack due in ${48 - hours}h`, tone: hours > 36 ? 'soon' : 'ok' };
  return { label: `${hours}h ago — 48h ack MISSED`, tone: 'past' };
}

function waiting(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const days = Math.floor((new Date() - d) / 86400000);
  if (days <= 0) return { label: 'Today', tone: 'ok' };
  if (days === 1) return { label: '1 day', tone: 'ok' };
  if (days < 21) return { label: `${days} days`, tone: days > 7 ? 'soon' : 'ok' };
  return { label: `${days} days — past due soon`, tone: 'past' };
}

export default function AdminPrivacy() {
  const { me } = useOutletContext();
  const canView = can(me, VIEW_CAPABILITY);
  const canManage = can(me, MANAGE_CAPABILITY);

  const [rows, setRows] = useState([]);
  const [onlyPending, setOnlyPending] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [flash, setFlash] = useFlash();
  const [busyId, setBusyId] = useState(null);
  // { req, mode: 'in_progress' | 'completed' | 'rejected' }
  const [dialog, setDialog] = useState(null);
  const [note, setNote] = useState('');

  const load = useCallback(() => {
    if (!canView) { setLoading(false); return; }
    setLoading(true);
    setError(null);
    listPrivacyRequests({ status: onlyPending ? 'pending' : null })
      .then((r) => setRows(Array.isArray(r?.items) ? r.items : []))
      .catch(setError)
      .finally(() => setLoading(false));
  }, [canView, onlyPending]);

  useEffect(load, [load]);

  // Email changes first, then oldest — the two things that decide what to pick
  // up next. The API returns them in its own order; sorting here rather than
  // asking for a new query parameter keeps this page's opinion in this page.
  const ordered = useMemo(() => {
    /* Grievances first: they carry a 48-hour acknowledgement promise under the
       DPDP Act, far shorter than the 30 days everything else here gets. Then
       email changes, whose founders cannot be reached at all. Then oldest. */
    const rank = (r) => (r.request_type === 'grievance' ? 0
      : r.request_type === 'email_change' ? 1 : 2);
    return [...rows].sort((a, b) =>
      rank(a) - rank(b) ||
      new Date(a.requested_at) - new Date(b.requested_at));
  }, [rows]);

  const act = async () => {
    if (!dialog) return;
    const { req, mode } = dialog;
    const text = note.trim();
    if (mode === 'rejected' && !text) {
      setFlash({ tone: 'bad', text: 'A rejection needs a reason — the founder is owed one.' });
      return;
    }
    setBusyId(req.request_id);
    try {
      await resolvePrivacyRequest(req.request_id, {
        status: mode,
        ...(mode === 'rejected' ? { rejectionReason: text } : { processingNotes: text || undefined }),
      });
      setFlash({
        tone: 'ok',
        text: mode === 'completed' ? 'Marked done.'
          : mode === 'rejected' ? 'Rejected, with the reason on the record.'
          : 'Marked as being worked on.',
      });
      setDialog(null);
      setNote('');
      load();
    } catch (err) {
      setFlash({ tone: 'bad', text: err?.detail || err?.message || 'That did not go through. Try again.' });
    } finally {
      setBusyId(null);
    }
  };

  if (!canView) {
    return (
      <section>
        <h1 className="adm-h1">Privacy requests</h1>
        <EmptyState
          title="You do not have access to this"
          hint="Viewing the privacy queue needs the users permission. Ask a super admin to add it."
        />
      </section>
    );
  }

  return (
    <section>
      <h1 className="adm-h1">Privacy requests</h1>
      <p className="adm-sub">
        Data-rights requests that need a person. We tell founders these are handled
        within 30 days. Email changes are listed first — those founders usually
        cannot receive anything we send, so they cannot chase us.
      </p>

      <Flash flash={flash} />

      <div className="adm-panel">
        <div className="adm-filters">
          <label className="adm-check">
            <input
              type="checkbox"
              checked={onlyPending}
              onChange={(e) => setOnlyPending(e.target.checked)}
            />
            Waiting on us only
          </label>
          <button className="adm-btn" type="button" onClick={load} disabled={loading}>
            Refresh
          </button>
        </div>

        {loading && <Loading label="Loading privacy requests…" />}
        {error && !loading && <ErrorState error={error} onRetry={load} />}

        {!loading && !error && ordered.length === 0 && (
          <EmptyState
            title={onlyPending ? 'Nothing waiting' : 'No privacy requests yet'}
            hint={onlyPending
              ? 'Every request has been actioned. Untick the box above to see the ones already handled.'
              : 'When a founder asks for a correction or an email change it will appear here.'}
          />
        )}

        {!loading && !error && ordered.length > 0 && (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead>
                <tr>
                  <th>Request</th>
                  <th>Founder</th>
                  <th>What they asked for</th>
                  <th>Waiting</th>
                  <th>Status</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {ordered.map((r) => {
                  const isEmail = r.request_type === 'email_change';
                  const age = waiting(r.requested_at);
                  const pending = r.status === 'pending' || r.status === 'in_progress';
                  return (
                    <tr key={r.request_id}>
                      <td>
                        <div>{TYPE_LABELS[r.request_type] || r.request_type}</div>
                        {isGrievance && <span className="adm-tag">Complaint · 48h</span>}
                        {isEmail && <span className="adm-tag">Locked out</span>}
                        <div className="adm-dim">{whenLabel(r.requested_at)}</div>
                      </td>
                      <td>
                        {/* Links through, because deciding an email change means
                            looking at the account first — you cannot verify who
                            is asking from a row in a queue. */}
                        <Link to={`/admin/users/${r.founder_id}`}>
                          Founder {r.founder_id}
                        </Link>
                      </td>
                      <td className="adm-wrap">
                        {r.request_details
                          ? <span className={isEmail ? 'adm-mono' : undefined}>{r.request_details}</span>
                          : <span className="adm-dim">Nothing said</span>}
                        {isEmail && (
                          <div className="adm-dim adm-warn" style={{ marginTop: 6 }}>
                            Verify who is asking before changing this. Whoever controls
                            the new inbox can then take the account over with a password
                            reset.
                          </div>
                        )}
                      </td>
                      <td>
                        {age && (
                          <span className={age.tone === 'ok' ? 'adm-dim' : 'adm-warn'}>
                            {age.label}
                          </span>
                        )}
                      </td>
                      <td>{r.status}</td>
                      <td className="adm-actions">
                        {pending && canManage ? (
                          <>
                            {r.status === 'pending' && (
                              <button
                                className="adm-btn"
                                type="button"
                                disabled={busyId === r.request_id}
                                onClick={() => { setNote(''); setDialog({ req: r, mode: 'in_progress' }); }}
                              >
                                On it
                              </button>
                            )}
                            <button
                              className="adm-btn adm-btn--primary"
                              type="button"
                              disabled={busyId === r.request_id}
                              onClick={() => { setNote(''); setDialog({ req: r, mode: 'completed' }); }}
                            >
                              Done
                            </button>
                            <button
                              className="adm-btn"
                              type="button"
                              disabled={busyId === r.request_id}
                              onClick={() => { setNote(''); setDialog({ req: r, mode: 'rejected' }); }}
                            >
                              Reject
                            </button>
                          </>
                        ) : (
                          <span className="adm-dim">
                            {r.processed_by ? `by ${r.processed_by}` : '—'}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {!canManage && ordered.length > 0 && (
          <p className="adm-dim" style={{ marginTop: 12 }}>
            You can see this queue but not action it — that needs the privacy-requests
            permission.
          </p>
        )}
      </div>

      <ConfirmDialog
          open={Boolean(dialog)}
          title={
            dialog?.mode === 'completed' ? 'Mark this done?'
              : dialog?.mode === 'rejected' ? 'Reject this request?'
              : 'Mark as being worked on?'
          }
          body={
            <>
              <p>
                {dialog?.mode === 'completed' && dialog?.req?.request_type === 'email_change'
                  ? 'Only mark this done once the address has actually been changed in the auth provider AND you have verified who asked. This does not change anything by itself.'
                  : dialog?.mode === 'completed'
                  ? 'This records that the request has been actioned.'
                  : dialog?.mode === 'rejected'
                  ? 'The reason is kept on the record and is what the founder is told.'
                  : 'This tells the rest of the team you have picked it up.'}
              </p>
              <label htmlFor="adm-privacy-note" className="adm-check" style={{ display: 'block', marginBottom: 6 }}>
                {dialog?.mode === 'rejected' ? 'Reason (required)' : 'Notes (optional)'}
              </label>
              <textarea
                id="adm-privacy-note"
                className="adm-textarea"
                rows={3}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder={dialog?.mode === 'rejected'
                  ? 'Why this cannot be done'
                  : 'What you did, for whoever reads this later'}
              />
            </>
          }
          confirmLabel={
            dialog?.mode === 'completed' ? 'Mark done'
              : dialog?.mode === 'rejected' ? 'Reject'
              : 'Mark in progress'
          }
          busy={busyId !== null}
          onConfirm={act}
          onCancel={() => { setDialog(null); setNote(''); }}
      />
    </section>
  );
}
