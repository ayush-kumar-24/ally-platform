/**
 * Discovery-call requests waiting on the team.
 *
 * A founder picks a slot from the team's real availability and that creates a
 * REQUEST — nothing is booked, nothing is charged, and no calendar event exists
 * yet. This screen is the other half: somebody here says yes or no.
 *
 * Confirming is the moment the meeting is created and the founder emailed, so
 * the button is deliberately not a quiet toggle — it has a confirmation step,
 * because pressing it sends a real person a real invitation.
 *
 * Ordered by priority then soonest slot, which is the order they actually need
 * answering in: a request for Tuesday matters more than one for next month,
 * whoever asked first.
 */

import { useCallback, useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { can, confirmCallRequest, declineCallRequest, listCallRequests } from '../../services/admin';
import { ConfirmDialog, EmptyState, ErrorState, Flash, Loading, useFlash } from './AdminUI';

const CAPABILITY = 'manage_discovery_calls';

/** "Tue 9 Sep, 2:00 pm" — the team reads a diary, not a timestamp. */
function whenLabel(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString('en-IN', {
    weekday: 'short', day: 'numeric', month: 'short',
    hour: 'numeric', minute: '2-digit', hour12: true,
  });
}

/** How soon it is. A request for tomorrow needs answering today. */
function urgency(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const days = Math.ceil((d - new Date()) / 86400000);
  if (days < 0) return { label: 'Slot has passed', tone: 'past' };
  if (days === 0) return { label: 'Today', tone: 'soon' };
  if (days === 1) return { label: 'Tomorrow', tone: 'soon' };
  return { label: `In ${days} days`, tone: 'ok' };
}

export default function AdminCalls() {
  const { me } = useOutletContext();
  const allowed = can(me, CAPABILITY);

  const [rows, setRows] = useState([]);
  const [onlyPending, setOnlyPending] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [flash, setFlash] = useFlash();
  const [busyId, setBusyId] = useState(null);
  // { call, mode: 'confirm' | 'decline' }
  const [dialog, setDialog] = useState(null);
  const [reason, setReason] = useState('');

  const load = useCallback(() => {
    if (!allowed) { setLoading(false); return; }
    setLoading(true);
    setError(null);
    listCallRequests({ onlyPending })
      .then((r) => setRows(Array.isArray(r) ? r : []))
      .catch(setError)
      .finally(() => setLoading(false));
  }, [allowed, onlyPending]);

  useEffect(load, [load]);

  const act = async () => {
    if (!dialog) return;
    const { call, mode } = dialog;
    setBusyId(call.call_id);
    try {
      if (mode === 'confirm') {
        await confirmCallRequest(call.call_id);
        setFlash({ tone: 'ok', text: `Confirmed. ${call.founder_name || 'The founder'} has been emailed the joining link.` });
      } else {
        await declineCallRequest(call.call_id, reason.trim());
        setFlash({ tone: 'ok', text: 'Request declined. The reason is on the record for when you follow up.' });
      }
      setDialog(null);
      setReason('');
      load();
    } catch (err) {
      setFlash({ tone: 'bad', text: err?.detail || err?.message || 'That did not go through. Try again.' });
    } finally {
      setBusyId(null);
    }
  };

  if (!allowed) {
    return (
      <section>
        <h1 className="adm-h1">Discovery calls</h1>
        <EmptyState
          title="You do not have access to this"
          hint="Handling call requests needs the discovery-calls permission. Ask a super admin to add it."
        />
      </section>
    );
  }

  return (
    <section>
      <h1 className="adm-h1">Discovery calls</h1>
      <p className="adm-sub">
        Founders request a slot from your real availability. Nothing is booked and
        nobody is charged until you confirm — confirming creates the meeting and
        emails them the link.
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

        {loading && <Loading label="Loading call requests…" />}
        {error && !loading && <ErrorState error={error} onRetry={load} />}

        {!loading && !error && rows.length === 0 && (
          <EmptyState
            title={onlyPending ? 'Nothing waiting' : 'No call requests yet'}
            hint={onlyPending
              ? 'Every request has been answered. Untick the box above to see the ones you already handled.'
              : 'When a founder asks for a slot it will appear here.'}
          />
        )}

        {!loading && !error && rows.length > 0 && (
          <div className="adm-table-wrap">
            <table className="adm-table">
              <thead>
                <tr>
                  <th>Founder</th>
                  <th>Requested slot</th>
                  <th>What they want to cover</th>
                  <th>Status</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {rows.map((c) => {
                  const soon = urgency(c.scheduled_at);
                  const pending = c.status === 'pending';
                  return (
                    <tr key={c.call_id}>
                      <td>
                        <div>{c.founder_name || `Founder ${c.founder_id}`}</div>
                        <div className="adm-mono adm-dim">{c.founder_email || '—'}</div>
                        {c.is_priority && <span className="adm-tag">Priority</span>}
                      </td>
                      <td>
                        <div>{whenLabel(c.scheduled_at)}</div>
                        {soon && (
                          <div className={`adm-dim${soon.tone === 'soon' ? ' adm-warn' : ''}`}>
                            {soon.label} · {c.duration_minutes} min
                          </div>
                        )}
                      </td>
                      {/* The founder's own words about why they want the call.
                          Shown in full rather than truncated: it is the whole
                          reason somebody is deciding yes or no. */}
                      <td className="adm-wrap">{c.notes_pre_call || <span className="adm-dim">Nothing said</span>}</td>
                      <td>{c.status}</td>
                      <td className="adm-actions">
                        {pending ? (
                          <>
                            <button
                              className="adm-btn adm-btn--primary"
                              type="button"
                              disabled={busyId === c.call_id}
                              onClick={() => setDialog({ call: c, mode: 'confirm' })}
                            >
                              Confirm
                            </button>
                            <button
                              className="adm-btn"
                              type="button"
                              disabled={busyId === c.call_id}
                              onClick={() => { setReason(''); setDialog({ call: c, mode: 'decline' }); }}
                            >
                              Decline
                            </button>
                          </>
                        ) : (
                          <span className="adm-dim">Answered</span>
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
        open={Boolean(dialog) && dialog.mode === 'confirm'}
        title="Confirm this call?"
        body={dialog
          ? `A meeting will be created for ${whenLabel(dialog.call.scheduled_at)} and ${dialog.call.founder_name || 'the founder'} will be emailed the joining link.`
          : ''}
        confirmLabel="Confirm the call"
        busy={busyId !== null}
        onConfirm={act}
        onCancel={() => setDialog(null)}
      />

      <ConfirmDialog
        open={Boolean(dialog) && dialog.mode === 'decline'}
        title="Decline this request?"
        body={
          <>
            <p>
              {dialog?.call?.founder_name || 'This founder'} asked for{' '}
              {dialog ? whenLabel(dialog.call.scheduled_at) : ''}. Say why, so
              whoever follows up knows what was decided.
            </p>
            <textarea
              className="adm-textarea"
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="No availability that week — offered Thursday instead"
              aria-label="Reason for declining"
            />
          </>
        }
        confirmLabel="Decline"
        danger
        busy={busyId !== null}
        /* A reason is required by the API too. Blocking here as well means the
           team finds out before the request fails, not after. Separate from
           `busy`, or the button claims to be working while it is only waiting
           for somebody to type. */
        disabled={reason.trim().length === 0}
        onConfirm={act}
        onCancel={() => { setDialog(null); setReason(''); }}
      />
    </section>
  );
}
