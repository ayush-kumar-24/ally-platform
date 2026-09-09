/**
 * Launch control — the go-live ceremony, from the panel.
 *
 * Five buttons, in the order the day runs:
 *   Arm       close the platform ahead of the event
 *   Start     run the shared countdown everybody is watching
 *   Abort     stop it, doors still shut — the reason the countdown exists
 *   Launch    open to everyone. Spends one of a small allowance.
 *   Reset     close it again for another rehearsal, while any remain
 *
 * WHAT THIS SCREEN DOES NOT DECIDE
 * `can_launch` comes from the server on every poll; this page renders it and
 * never computes it. If it ran its own timer, the button would unlock on the
 * browser's clock while the backend still refused the press — the panel would
 * be showing the room a button that does not work. Same reason the countdown
 * itself is server state: see backend app/launch/service.py.
 *
 * Both irreversible-ish actions go through the confirmation dialog: launch,
 * because it opens the product to the public, and reset, because it CLOSES a
 * platform that is live right now — the more dangerous of the two if pressed
 * by accident, and the one whose danger is easiest to underestimate.
 *
 * `launches_remaining` and `can_reset` are read from the server, never
 * computed here. The panel must not be able to offer a rehearsal the backend
 * would refuse, or hide one it would allow. Everything is Super Admin only,
 * enforced server-side; the rest of the team can watch without pressing.
 */

import { useCallback, useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { can } from '../../services/admin';
import {
  abortCountdown,
  armLaunch,
  getLaunchState,
  launchNow,
  LAUNCH_STATES,
  resetLaunch,
  startCountdown,
} from '../../services/launch';
import { ConfirmDialog, ErrorState, Flash, Loading, useFlash } from './AdminUI';
import '../../styles/launch.css';

const CAPABILITY = 'system_settings';

/* Fast enough that the number on this screen matches the one on the wall,
   slow enough not to poll every second at three in the afternoon two weeks
   before the launch. */
const POLL_COUNTING_MS = 500;
const POLL_IDLE_MS = 5000;

const COPY = {
  [LAUNCH_STATES.OPEN]: {
    label: 'Open',
    line: 'No gate. The platform is serving everyone as normal — this is how it '
      + 'ships until somebody arms the launch.',
  },
  [LAUNCH_STATES.ARMED]: {
    label: 'Armed',
    line: 'The doors are shut. Everyone but the admin panel sees the holding '
      + 'screen. Nothing is counting yet.',
  },
  [LAUNCH_STATES.COUNTING]: {
    label: 'Counting',
    line: 'The countdown is running on every open browser at once. Abort stops '
      + 'it; the launch button unlocks when it reaches zero.',
  },
  [LAUNCH_STATES.LAUNCHED]: {
    label: 'Launched',
    line: 'The platform is open to everyone right now.',
  },
};

function whenLabel(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d.toLocaleString();
}

export default function AdminLaunch() {
  const { me } = useOutletContext() ?? {};
  const allowed = can(me, CAPABILITY);

  const [state, setState] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  /* null | 'launch' | 'reset' — one dialog, two questions. */
  const [confirming, setConfirming] = useState(null);
  const [seconds, setSeconds] = useState(10);
  const [flash, setFlash] = useFlash();

  const load = useCallback(async () => {
    try {
      setState(await getLaunchState());
      setError(null);
    } catch (e) {
      setError(e);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const counting = state?.state === LAUNCH_STATES.COUNTING;
  const launched = state?.state === LAUNCH_STATES.LAUNCHED;

  useEffect(() => {
    if (launched) return undefined;          // terminal — nothing left to watch
    const id = setInterval(load, counting ? POLL_COUNTING_MS : POLL_IDLE_MS);
    return () => clearInterval(id);
  }, [counting, launched, load]);

  /* Every button funnels through here so one in-flight request cannot be
     double-fired, and so a refused press (409 from the server — launching
     early, aborting nothing) is shown rather than swallowed. */
  const run = async (action, message) => {
    setBusy(true);
    try {
      setState(await action());
      setFlash({ message });
    } catch (e) {
      setFlash({ message: e?.detail || e?.message || 'That did not work.', error: true });
      load();
    } finally {
      setBusy(false);
    }
  };

  if (error) return <ErrorState error={error} onRetry={load} />;
  if (!state) return <Loading label="Reading launch state…" />;

  const copy = COPY[state.state] ?? { label: state.state, line: '' };
  const remaining = state.seconds_remaining;

  /* Whether the API actually told us about the allowance.
     Deploys are not atomic: this page ships from S3 in seconds while the API
     rolls out over ~15 minutes, so a build that knows about launch counters
     WILL run against an API that does not. Reading those absent fields as
     numbers made `launches_remaining > 0` false and `can_reset` false, and
     the page then said "none left, the platform is open for good" and "this
     one is final" -- both untrue, on the one screen whose entire job is to
     tell the truth about whether the platform is open.
     Absent is not zero. When the fields are missing we say nothing about the
     allowance rather than inventing the most alarming reading of it. */
  const allowanceKnown = Number.isFinite(state.max_launches) && state.max_launches > 0;

  return (
    <section>
      <h1 className="adm-h1">Launch</h1>
      <p className="adm-sub">
        The moment Ally opens to everyone. Arm the gate, run the countdown in
        front of the room, then launch — rehearsals included, up to the
        allowance.
      </p>

      <Flash flash={flash} />

      <div className="adm-panel">
        <span className={`lc-state lc-state-${state.state}`}>{copy.label}</span>
        <p className="adm-sub" style={{ marginTop: 10 }}>{copy.line}</p>

        {counting && (
          <div className="lc-clock" aria-live="off">
            {Math.ceil(remaining ?? 0)}s
          </div>
        )}

        {state.launched_at && (
          <div className="adm-dim" style={{ marginTop: 10 }}>
            {launched ? 'Launched' : 'Last launched'} {whenLabel(state.launched_at)}
            {state.launched_by ? ` · by admin #${state.launched_by}` : ''}
          </div>
        )}

        {/* The budget, stated plainly wherever the team is standing. "2 of 3
            used" is the number somebody needs before deciding whether this
            run-through is a rehearsal or the real thing. */}
        {allowanceKnown && (
          <div className="adm-dim" style={{ marginTop: 6 }}>
            {state.launch_count} of {state.max_launches} launches used
            {state.launches_remaining > 0
              ? ` · ${state.launches_remaining} left`
              : ' · none left, the platform is open for good'}
          </div>
        )}

        {!allowanceKnown && (
          <div className="adm-dim" style={{ marginTop: 6 }}>
            The API has not reported the launch allowance yet — it is probably
            mid-deploy. Reload in a minute; nothing here is safe to press until
            this line goes away.
          </div>
        )}

        {!allowed && (
          <div className="adm-dim" style={{ marginTop: 12 }}>
            You can watch the launch from here. Pressing anything needs Super
            Admin.
          </div>
        )}

        {allowed && launched && allowanceKnown && state.can_reset && (
          <div className="lc-actions">
            <button
              className="adm-btn"
              type="button"
              disabled={busy}
              onClick={() => setConfirming('reset')}
            >
              Close again for another rehearsal
            </button>
          </div>
        )}

        {allowed && launched && allowanceKnown && !state.can_reset && (
          <div className="adm-dim" style={{ marginTop: 12 }}>
            The launch allowance is spent, so this one is final — the platform
            cannot be closed from here.
          </div>
        )}

        {allowed && !launched && allowanceKnown && (
          <div className="lc-actions">
            {!counting && (
              <>
                <label className="adm-dim" htmlFor="lc-seconds">
                  Countdown
                  <input
                    id="lc-seconds"
                    className="adm-input"
                    type="number"
                    min={3}
                    max={300}
                    value={seconds}
                    onChange={(e) => setSeconds(Number(e.target.value))}
                    style={{ width: 80, marginLeft: 8 }}
                  />
                  {' '}seconds
                </label>
                <button
                  className="adm-btn"
                  type="button"
                  disabled={busy}
                  onClick={() => run(() => armLaunch(seconds),
                    'Gate armed — visitors now see the holding screen.')}
                >
                  {state.state === LAUNCH_STATES.ARMED ? 'Re-arm' : 'Arm the gate'}
                </button>
                <button
                  className="adm-btn adm-btn--primary"
                  type="button"
                  disabled={busy}
                  onClick={() => run(() => startCountdown(seconds), 'Countdown started.')}
                >
                  Start countdown
                </button>
              </>
            )}

            {counting && (
              <button
                className="adm-btn"
                type="button"
                disabled={busy}
                onClick={() => run(abortCountdown, 'Countdown aborted. Doors still shut.')}
              >
                Abort
              </button>
            )}

            <button
              className="adm-btn lc-danger"
              type="button"
              /* Disabled straight off the server's own answer, so this button
                 and the endpoint behind it can never disagree. */
              disabled={busy || !state.can_launch}
              onClick={() => setConfirming('launch')}
            >
              {state.can_launch ? 'Launch Ally' : 'Launch (waiting for zero)'}
            </button>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={confirming === 'launch'}
        title="Open Ally to everyone?"
        body={
          <>
            This opens the platform to every visitor, immediately.
            {state.launches_remaining > 1 ? (
              <>
                {' '}It spends one of your {state.launches_remaining} remaining
                launches, leaving {state.launches_remaining - 1}.
              </>
            ) : (
              <>
                {' '}This is your <strong>last launch</strong> — afterwards the
                platform cannot be closed again from here.
              </>
            )}
          </>
        }
        confirmLabel="Launch now"
        busy={busy}
        onCancel={() => setConfirming(null)}
        onConfirm={async () => {
          await run(launchNow, 'Ally is live.');
          setConfirming(null);
        }}
      />

      {/* Marked danger, unlike launch. Launching opens a platform nobody is
          using yet; this SHUTS one that is live, and anybody already inside
          meets the holding screen on their next page. That is the presser's
          decision to make, but not one to make by accident. */}
      <ConfirmDialog
        open={confirming === 'reset'}
        title="Close Ally again?"
        danger
        body={
          <>
            Every visitor goes back to the holding screen immediately, including
            anyone using the platform right now. The launch you already spent is
            not refunded — you will have{' '}
            <strong>{Math.max(0, state.launches_remaining)} launch
            {state.launches_remaining === 1 ? '' : 'es'}</strong> left afterwards.
          </>
        }
        confirmLabel="Close the platform"
        busy={busy}
        onCancel={() => setConfirming(null)}
        onConfirm={async () => {
          await run(resetLaunch, 'Platform closed. The gate is armed again.');
          setConfirming(null);
        }}
      />
    </section>
  );
}
