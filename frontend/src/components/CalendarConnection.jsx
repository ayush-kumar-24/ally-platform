import { useCallback, useEffect, useState } from 'react';
import {
  disconnectCalendar, getCalendarStatus, startCalendarConnect,
} from '../services/calendar';

/**
 * Connect / disconnect a Google Calendar, and say plainly what that does.
 *
 * Renders nothing at all when the deployment cannot offer calendar sync (no
 * OAuth client, no encryption key). A Connect button that can only 503 is worse
 * than no button: it reads as a broken feature rather than an absent one.
 */
export default function CalendarConnection({ onChange, showToast }) {
  const [state, setState] = useState({ loading: true, status: null });
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const load = useCallback(() => {
    getCalendarStatus()
      .then((status) => {
        setState({ loading: false, status });
        onChange?.(status);
      })
      // A failure here must not take the page down: Plan Your Day works fine
      // without ever knowing whether a calendar is attached.
      .catch(() => setState({ loading: false, status: null }));
  }, [onChange]);

  useEffect(load, [load]);

  /* The OAuth callback sends the browser back to /app/plan?calendar=…, which is
     the only channel a redirect has for reporting what happened. Read it, tell
     the founder, then strip it from the URL so a refresh doesn't replay a
     three-day-old "Connected!". */
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const outcome = params.get('calendar');
    if (!outcome) return;

    const detail = params.get('detail');
    if (outcome === 'connected') showToast?.('Google Calendar connected.');
    else if (outcome === 'cancelled') showToast?.('Calendar connection cancelled.');
    else showToast?.(detail || "Couldn't connect your calendar. Please try again.", 6000);

    window.history.replaceState({}, '', window.location.pathname);
    if (outcome === 'connected') load();
  }, [load, showToast]);

  const connect = async () => {
    setBusy(true);
    try {
      await startCalendarConnect();   // navigates away; nothing runs after this
    } catch (err) {
      setBusy(false);
      showToast?.(err?.message || "Couldn't start the connection. Please try again.", 6000);
    }
  };

  const confirmDisconnect = async () => {
    setBusy(true);
    try {
      const result = await disconnectCalendar();
      showToast?.(result?.message || 'Calendar disconnected.', 6000);
      setConfirming(false);
      load();
    } catch {
      showToast?.("Couldn't disconnect. Please try again.", 6000);
    } finally {
      setBusy(false);
    }
  };

  if (state.loading || !state.status || !state.status.available) return null;

  const { connected, account_email: email, needs_reconnect: needsReconnect } = state.status;

  return (
    <div className="cal-conn">
      <div className="cal-conn-row">
        <div className="cal-conn-text">
          <div className="cal-conn-title">
            {connected ? 'Google Calendar connected' : 'Google Calendar'}
          </div>
          <div className="cal-conn-sub">
            {connected
              ? (email
                // Worth naming: it need not be the address they use for Ally,
                // and "which account did I connect?" is otherwise unanswerable.
                ? `Tasks with a date appear on ${email}.`
                : 'Tasks with a date appear on your calendar.')
              : needsReconnect
                ? 'Access was removed in Google. Reconnect to resume syncing.'
                : 'Connect it and dated tasks become calendar events, with a reminder.'}
          </div>
        </div>

        {connected ? (
          <button type="button" className="cal-conn-btn cal-conn-ghost"
                  onClick={() => setConfirming(true)} disabled={busy}>
            Disconnect
          </button>
        ) : (
          <button type="button" className="cal-conn-btn" onClick={connect} disabled={busy}>
            {busy ? 'Opening Google…' : needsReconnect ? 'Reconnect' : 'Connect'}
          </button>
        )}
      </div>

      {confirming && (
        <div className="cal-conn-confirm" role="alertdialog" aria-label="Disconnect calendar">
          <p>
            Ally will stop adding tasks to your calendar.{' '}
            {/* Said up front, not discovered afterwards. Leaving them is the
                safer default — deleting someone's calendar entries in bulk
                cannot be undone — but it must not be a surprise. */}
            <strong>Events already added will stay on your calendar</strong>, and you
            can remove them there.
          </p>
          <div className="cal-conn-confirm-actions">
            <button type="button" className="cal-conn-btn cal-conn-danger"
                    onClick={confirmDisconnect} disabled={busy}>
              {busy ? 'Disconnecting…' : 'Disconnect'}
            </button>
            <button type="button" className="cal-conn-btn cal-conn-ghost"
                    onClick={() => setConfirming(false)} disabled={busy}>
              Keep connected
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
