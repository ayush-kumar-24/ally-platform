import { useEffect, useState } from 'react';

/**
 * The actual current time, ticking.
 *
 * Deliberately NOT folded into the date chip beside it: that chip shows the
 * day being PLANNED, which is often not today -- a founder setting up
 * tomorrow morning sees "Thursday, August 28" there while it is still
 * Wednesday. A clock inside that chip would read as the time on that date,
 * which is a thing that does not exist.
 *
 * Each tick is scheduled to the next second boundary rather than on a flat
 * 1000ms interval. setInterval drifts by however long the callback and render
 * take, and a clock that drifts eventually skips a visible second -- the one
 * defect a clock cannot have. It also re-reads the wall clock on every tick
 * instead of adding a second to its own state, so a machine that sleeps or
 * has its time corrected comes back right rather than accumulating the gap.
 */
export default function LiveClock({ className = '' }) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    let timer;
    const tick = () => {
      const d = new Date();
      setNow(d);
      timer = setTimeout(tick, 1000 - (d.getTime() % 1000));
    };
    timer = setTimeout(tick, 1000 - (Date.now() % 1000));

    // A backgrounded tab has its timers throttled to once a minute or worse,
    // so returning to it would show a clock stuck minutes in the past until
    // the next throttled tick landed.
    const resync = () => {
      if (document.visibilityState !== 'visible') return;
      clearTimeout(timer);
      tick();
    };
    document.addEventListener('visibilitychange', resync);
    return () => {
      clearTimeout(timer);
      document.removeEventListener('visibilitychange', resync);
    };
  }, []);

  return (
    <div className={`plan-clock${className ? ` ${className}` : ''}`}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </svg>
      {/* aria-live is off on purpose: announcing a new time every second would
          make the page unusable with a screen reader. The <time> element still
          exposes the value to anything that asks for it. */}
      <time dateTime={now.toISOString()}>
        {now.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', second: '2-digit' })}
      </time>
    </div>
  );
}
