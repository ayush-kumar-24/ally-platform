import { useEffect, useRef } from 'react';

const BAR_COUNT = 28;
/* One new sample per ~55ms rather than per frame: at a full 60fps the history
   scrolls past far too fast to read as "this is my voice". */
const SAMPLE_MS = 55;

/**
 * Live mic meter shown while recording -- a scrolling history of real
 * amplitude, newest on the right.
 *
 * `getLevel` is polled on requestAnimationFrame and written straight to the
 * bars' inline heights. Deliberately NOT React state: amplitude changes every
 * frame, and routing that through state would re-render the entire chat
 * ~60x/sec for the whole time someone is talking.
 */
export default function VoiceBars({ getLevel, label = 'Listening…' }) {
  const barsRef = useRef([]);

  useEffect(() => {
    const history = new Array(BAR_COUNT).fill(0);
    let rafId = null;
    let last = 0;

    const tick = (now) => {
      rafId = requestAnimationFrame(tick);
      if (now - last < SAMPLE_MS) return;
      last = now;

      history.shift();
      history.push(getLevel());

      for (let i = 0; i < BAR_COUNT; i++) {
        const el = barsRef.current[i];
        if (!el) continue;
        /* Speech RMS sits well below 1.0, so it needs scaling up to fill the
           meter at normal talking volume. The 12% floor keeps a visible
           baseline -- a meter that flattens to nothing in the pauses between
           words reads as "it stopped working", which is the opposite of the
           reassurance this is here to give. */
        el.style.height = `${Math.min(100, 12 + history[i] * 260)}%`;
      }
    };

    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [getLevel]);

  return (
    <div className="voice-meter" role="status" aria-live="polite">
      <span className="vm-dot" aria-hidden="true" />
      <span className="vm-label">{label}</span>
      <div className="vm-bars" aria-hidden="true">
        {Array.from({ length: BAR_COUNT }, (_, i) => (
          <span key={i} ref={(el) => { barsRef.current[i] = el; }} />
        ))}
      </div>
    </div>
  );
}
