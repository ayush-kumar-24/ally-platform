/**
 * LaunchGate — the holding screen in front of the platform before go-live.
 *
 * Wraps the routes a founder uses. While the gate is closed, this is the only
 * thing they see; the moment it opens, the app underneath renders as normal.
 *
 * THE CLOCK IS THE SERVER'S
 * Every poll brings back `seconds_remaining` computed on the backend, and that
 * is what is displayed. Between polls the number is interpolated locally so it
 * ticks smoothly, but each poll snaps it back to the server's answer. The
 * alternative — counting down from `countdown_ends_at` against the browser's
 * own clock — drifts by however much the laptops in one room disagree, which
 * is exactly enough for a countdown people are reading aloud not to match.
 *
 * IT FAILS OPEN, LIKE THE BACKEND
 * If the status request fails, the platform renders. The backend gate fails
 * open for the same reason (see app/launch/service.py): a network blip or a
 * cold backend must not put a holding screen in front of a live platform full
 * of founders mid-diagnosis. The cost is that an outage during the ceremony
 * opens the doors early — loud, visible and recoverable, unlike a silent
 * lockout.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { getLaunchStatus, LAUNCH_STATES } from '../services/launch';
import '../styles/launch.css';

/* Poll cadences. Fast while the room is watching a number change, lazy while
   the gate is simply shut -- a holding screen that could sit there for a day
   should not make a request every second for all of it. */
const POLL_COUNTING_MS = 1000;
const POLL_IDLE_MS = 5000;
/* Local interpolation between polls. 100ms is smooth to the eye and cheap. */
const TICK_MS = 100;

/* Routes that must never be gated:
   /admin  — the launch button itself lives there. Gating it would make the
             ceremony unstartable, which is the one failure this feature
             cannot recover from on its own.
   /terms, /privacy — legal pages are public obligations, not product. */
const UNGATED = ['/admin', '/terms', '/privacy'];

function isUngated(pathname) {
  return UNGATED.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

export default function LaunchGate({ children }) {
  const { pathname } = useLocation();
  /* null = the first request has not answered yet. Distinct from "open": the
     app is held back for that one round-trip so the platform does not flash
     into view a moment before the gate closes over it. */
  const [status, setStatus] = useState(null);
  const [remaining, setRemaining] = useState(null);
  /* The wall-clock moment the last server reading was taken, so the local tick
     measures elapsed time rather than counting its own intervals -- a
     backgrounded tab throttles timers to once a minute, and a counter that
     trusted its own ticks would come back reading eight when it should read
     zero. */
  const readAtRef = useRef(0);

  const poll = useCallback(async () => {
    try {
      const next = await getLaunchStatus();
      readAtRef.current = Date.now();
      setStatus(next);
      setRemaining(next.seconds_remaining);
    } catch {
      /* Fail open — see the module docstring. */
      setStatus((prev) => prev ?? { is_open: true, state: LAUNCH_STATES.OPEN });
    }
  }, []);

  useEffect(() => { poll(); }, [poll]);

  const state = status?.state;
  const counting = state === LAUNCH_STATES.COUNTING;
  const open = status?.is_open !== false;

  useEffect(() => {
    /* Once the platform is open it stays open -- the backend has no un-launch
       -- so polling stops for good rather than running for the life of the
       session. */
    if (open) return undefined;
    const id = setInterval(poll, counting ? POLL_COUNTING_MS : POLL_IDLE_MS);
    return () => clearInterval(id);
  }, [open, counting, poll]);

  /* Re-armed by every poll (`status` is a new object each time), so the
     interpolation always subtracts from the freshest server reading rather
     than from its own previous output -- errors cannot accumulate. */
  useEffect(() => {
    if (!counting) return undefined;
    const from = status.seconds_remaining ?? 0;
    const id = setInterval(() => {
      setRemaining(Math.max(0, from - (Date.now() - readAtRef.current) / 1000));
    }, TICK_MS);
    return () => clearInterval(id);
  }, [counting, status]);

  /* useLocation, not window.location: the exemption has to be re-evaluated on
     client-side navigation too, and a bare window read is a value React never
     re-renders for. */
  if (isUngated(pathname)) return children;
  /* One round-trip on a dark ground, matching App.jsx's RouteFallback: a
     spinner for something this short is more distracting than the blank. */
  if (status === null) {
    return <div style={{ minHeight: '100dvh', background: 'var(--forest-night, #06140d)' }} />;
  }
  if (open) return children;

  return <HoldingScreen status={status} remaining={remaining} counting={counting} />;
}

function HoldingScreen({ status, remaining, counting }) {
  const seconds = Math.ceil(remaining ?? 0);
  const total = status.countdown_seconds || 10;
  /* Elapsed, not remaining: the bar fills towards the launch rather than
     draining away from it. */
  const progress = counting ? Math.min(100, ((total - (remaining ?? 0)) / total) * 100) : 0;
  const atZero = counting && seconds <= 0;

  return (
    <div className="lg" role="status" aria-live="polite">
      <main id="main-content" tabIndex={-1} className="lg-inner">
        <p className="lg-kicker">GoXL Ally</p>

        {!counting && (
          <>
            <h1>We&rsquo;re opening the doors shortly</h1>
            <p>
              <span className="lg-dot" aria-hidden="true" />
              Ally is moments away from going live. Keep this page open — it
              will let you in the second we launch.
            </p>
          </>
        )}

        {counting && !atZero && (
          <>
            <h1>Going live in</h1>
            {/* The key restarts the pulse on every new number, so each second
                animates in rather than a loop running past the count. */}
            <div className="lg-count lg-count-tick" key={seconds}>{seconds}</div>
            <div className="lg-ring">
              <div className="lg-ring-fill" style={{ width: `${progress}%` }} />
            </div>
          </>
        )}

        {atZero && (
          <>
            <h1>Any moment now</h1>
            <div className="lg-count">0</div>
            <p>
              <span className="lg-dot" aria-hidden="true" />
              The countdown is done. Ally opens the instant the team presses
              launch.
            </p>
          </>
        )}
      </main>
    </div>
  );
}
