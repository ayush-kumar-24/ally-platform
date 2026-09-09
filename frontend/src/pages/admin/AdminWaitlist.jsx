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
  openWaitlistSlots,
  previewWaitlistSlots,
  rejectRegistration,
} from '../../services/admin';
import { ConfirmDialog, EmptyState, ErrorState, Flash, Loading, useFlash } from './AdminUI';

const CAPABILITY = 'manage_waitlist';
// Opening slots is a decision about how big the phase is, not about one
// person, so it sits a tier above clearing the queue. See rbac.py.
const OPEN_SLOTS_CAPABILITY = 'open_waitlist_slots';

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
  const canOpenSlots = can(me, OPEN_SLOTS_CAPABILITY);

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
  // How many places to open. A string, not a number: a controlled number input
  // that coerces as you type fights the person clearing it to type "25".
  const [slots, setSlots] = useState('');
  // The server's answer to "who would this let in" -- named people, held until
  // somebody confirms. Null means nothing is pending.
  const [preview, setPreview] = useState(null);
  const [previewing, setPreviewing] = useState(false);
  const [opening, setOpening] = useState(false);

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

  const slotCount = Number.parseInt(slots, 10);
  const slotsValid = Number.isInteger(slotCount) && slotCount >= 1 && slotCount <= 500;

  const askWhoGetsIn = async () => {
    if (!slotsValid) return;
    setPreviewing(true);
    try {
      setPreview(await previewWaitlistSlots(slotCount));
    } catch (err) {
      setFlash({ error: true, message: err?.detail || err?.message || 'Could not read the queue.' });
    } finally {
      setPreviewing(false);
    }
  };

  const confirmOpen = async () => {
    if (!preview) return;
    setOpening(true);
    try {
      const result = await openWaitlistSlots(preview.slots);
      const inCount = result?.approved?.length || 0;
      const failed = result?.failures?.length || 0;
      const direct = result?.direct_signup_opened || 0;
      // Said once, here, because this is the moment it happened -- the
      // running total afterwards lives in the cap box above, not repeated
      // in every flash.
      const directNote = direct > 0
        ? ` ${direct} more direct sign-in ${direct === 1 ? 'place is' : 'places are'} open too.`
        : '';
      // A partial result is flagged as an error not because the grant failed
      // for the others -- it did not -- but because the people who missed out
      // are the ones still needing a human.
      setFlash(
        failed
          ? {
              error: true,
              message: `${inCount} let in. ${failed} could not be: ${result.failures
                .map((f) => `${f.full_name} (${f.reason})`)
                .join('; ')}. They are still at the front of the queue.${directNote}`,
            }
          : inCount === 0
            ? { message: `Nobody was waiting to let in.${directNote}` }
            : {
                message: `${inCount} ${inCount === 1 ? 'founder is' : 'founders are'} in, and have been emailed.${directNote}`,
              },
      );
      setPreview(null);
      setSlots('');
      load();
    } catch (err) {
      setFlash({ error: true, message: err?.detail || err?.message || 'Nothing was opened. Try again.' });
    } finally {
      setOpening(false);
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

      {/* The place budget, above the queue rather than inside it: it is a
          fact about the phase, not about any one row. */}
      {cap && (
        <div className="adm-panel">
          <strong>{cap.approved} of {cap.cap}</strong> places taken
          {!full && <> · {cap.remaining} left</>}
          {full && (
            <span className="adm-warn">
              {' '}· The list is full. Open more places below, or a super admin
              can approve past it one at a time.
            </span>
          )}
          {/* Where the number came from. "325" on its own reads as a constant;
              "300 to start, 25 opened here" reads as a decision someone made. */}
          {cap.slots_opened > 0 && (
            <div className="adm-dim" style={{ marginTop: 4 }}>
              {cap.base_cap} to start · {cap.slots_opened} opened from this screen
            </div>
          )}

          {/* Direct sign-in is the other door: whatever a batch does not spend
              on the queue becomes places a stranger can fill by logging in,
              no approval needed. This is the one fact the landing page's own
              "Register" vs "Log in" button reads, so the number here is
              exactly what a founder sees decide their button right now. */}
          {cap.direct_signup_capacity > 0 ? (
            <div className="adm-panel" style={{ marginTop: 10, padding: 10 }}>
              <strong>{cap.direct_signup_capacity}</strong> direct sign-in{' '}
              {cap.direct_signup_capacity === 1 ? 'place is' : 'places are'} open
              right now — anyone can log in and get an account on the spot, no
              approval needed. The landing page shows "Log in" instead of
              "Register" while this is above zero, and it drops back to
              "Register" the moment it hits zero.
            </div>
          ) : (
            <div className="adm-dim" style={{ marginTop: 10 }}>
              Direct sign-in is closed — new visitors register and land in the
              queue below. Opening places above will fill the queue first,
              oldest first, then hand anything left over to direct sign-in.
            </div>
          )}

          {cap.can_grant_access === false && (
            <div className="adm-warn" style={{ marginTop: 6 }}>
              Access cannot be granted right now: the identity provider is not
              configured (SUPABASE_SERVICE_ROLE_KEY is unset), so approving
              would fail. Nothing here will let anyone in until that is set.
            </div>
          )}

          {canOpenSlots && (
            <div style={{ marginTop: 12, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <label htmlFor="waitlist-slots">Open</label>
              <input
                id="waitlist-slots"
                className="adm-input"
                type="number"
                min="1"
                max="500"
                style={{ width: 90 }}
                value={slots}
                onChange={(e) => setSlots(e.target.value)}
                placeholder="25"
              />
              <span>more places</span>
              <button
                className="adm-btn adm-btn--primary"
                type="button"
                disabled={!slotsValid || previewing || cap.can_grant_access === false}
                onClick={askWhoGetsIn}
              >
                {previewing ? 'Checking…' : 'See who gets in'}
              </button>
              <span className="adm-dim">
                The people who have waited longest are let in first, in the same
                order as the queue below. You see exactly who before anything
                happens.
              </span>
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

      {/* Named people, not a number. The confirmation for "open 25 slots" has
          to answer "which 25?", because the act creates 25 logins and sends 25
          emails and none of it can be taken back from here. */}
      <ConfirmDialog
        open={Boolean(preview)}
        title={preview ? `Let in ${preview.would_approve.length} ${preview.would_approve.length === 1 ? 'person' : 'people'}?` : ''}
        body={preview ? (
          <>
            <p>
              These are the {preview.would_approve.length} who have waited
              longest. Each one gets a login and an email saying they are on the
              founder&apos;s list. This cannot be undone from here.
            </p>
            {preview.would_approve.length === 0 ? (
              <p className="adm-warn">
                Nobody is waiting, so this would let nobody in from the queue
                — instead it opens {preview.slots} direct sign-in{' '}
                {preview.slots === 1 ? 'place' : 'places'}: anyone can log in
                and get an account on the spot until they run out.
              </p>
            ) : (
              <ol style={{ maxHeight: 220, overflowY: 'auto', margin: '8px 0', paddingLeft: 20 }}>
                {preview.would_approve.map((r) => (
                  <li key={r.registration_id} style={{ marginBottom: 4 }}>
                    {r.full_name}
                    <span className="adm-mono adm-dim"> · {r.email}</span>
                  </li>
                ))}
              </ol>
            )}
            {preview.unused_slots > 0 && preview.would_approve.length > 0 && (
              <p className="adm-dim">
                The queue is shorter than that — the other{' '}
                {preview.unused_slots} of {preview.slots} places become
                direct sign-in capacity instead: anyone can log in and get an
                account on the spot until they run out.
              </p>
            )}
          </>
        ) : ''}
        confirmLabel={preview && preview.would_approve.length > 0
          ? `Let ${preview.would_approve.length} in and email them`
          : 'Open the places'}
        busy={opening}
        onConfirm={confirmOpen}
        onCancel={() => setPreview(null)}
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
