/**
 * Launch control — the go-live ceremony, from the panel.
 *
 * Four buttons, in the order the day runs:
 *   Arm       close the platform ahead of the event
 *   Start     run the shared countdown everybody is watching
 *   Abort     stop it, doors still shut — the reason the countdown exists
 *   Launch    open to everyone. Irreversible.
 *
 * WHAT THIS SCREEN DOES NOT DECIDE
 * `can_launch` comes from the server on every poll; this page renders it and
 * never computes it. If it ran its own timer, the button would unlock on the
 * browser's clock while the backend still refused the press — the panel would
 * be showing the room a button that does not work. Same reason the countdown
 * itself is server state: see backend app/launch/service.py.
 *
 * Launch is the only action in the panel with no undo, so it goes through the
 * confirmation dialog and says so in as many words. Everything here is Super
 * Admin only, enforced server-side; the rest of the team can watch the state
 * without being able to press anything.
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
    line: 'The platform is open to everyone. A launch happens once — this '
      + 'cannot be replayed or undone.',
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
  const [confirming, setConfirming] = useState(false);
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

  return (
    <section>
      <h1 className="adm-h1">Launch</h1>
      <p className="adm-sub">
        The one-time moment Ally opens to everyone. Arm the gate, run the
        countdown in front of the room, then launch.
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

        {launched && state.launched_at && (
          <div className="adm-dim" style={{ marginTop: 10 }}>
            Launched {whenLabel(state.launched_at)}
            {state.launched_by ? ` · by admin #${state.launched_by}` : ''}
          </div>
        )}

        {!allowed && (
          <div className="adm-dim" style={{ marginTop: 12 }}>
            You can watch the launch from here. Pressing anything needs Super
            Admin.
          </div>
        )}

        {allowed && !launched && (
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
              onClick={() => setConfirming(true)}
            >
              {state.can_launch ? 'Launch Ally' : 'Launch (waiting for zero)'}
            </button>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={confirming}
        title="Open Ally to everyone?"
        body={
          <>
            This opens the platform to every visitor, immediately. It happens
            once and <strong>cannot be undone</strong> — there is no un-launch.
          </>
        }
        confirmLabel="Launch now"
        busy={busy}
        onCancel={() => setConfirming(false)}
        onConfirm={async () => {
          await run(launchNow, 'Ally is live.');
          setConfirming(false);
        }}
      />
    </section>
  );
}
