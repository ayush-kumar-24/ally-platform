import { useEffect, useState } from 'react';
import { QUOTES } from '../data/quotes';
import { dayIndex, timeSlot } from '../utils/helpers';

/**
 * Per-surface offsets into the slot's list. Distinct values, and both smaller
 * than the shortest list in data/quotes.js, so `(day + offset) % length` can
 * never land on the same line for two surfaces on the same day.
 */
const SURFACE_OFFSET = { compass: 0, plan: 2 };

/**
 * A quote chosen for the time of day, which changes on its own as the day moves.
 *
 * The pick is derived, not stored: the slot decides WHICH list, and the day of
 * the year plus the surface's own offset decides which line within it. So it
 * changes four times a day and does not repeat tomorrow, with nothing written
 * to storage and nothing fetched.
 *
 * The two surfaces are deliberately never showing the same line at the same
 * moment. This first shipped the other way round -- one quote everywhere, on
 * the reasoning that two pages disagreeing would read as a bug -- and that
 * call was overruled: a founder moving from the Compass to Plan Your Day
 * should get a second thought, not the same one twice. SURFACE_OFFSET above is
 * what guarantees it, so those values must stay distinct.
 *
 * The clock is polled rather than scheduled to the exact boundary because a
 * laptop that sleeps through 6pm wakes with a stale timeout, and a founder with
 * the tab open all afternoon would keep reading the morning quote into the
 * night. A minute of lag at the boundary is not worth a timer that can silently
 * stop being true.
 */
export default function QuoteCard({ size = 'sm', surface = 'plan', className = '' }) {
  const [slot, setSlot] = useState(() => timeSlot());
  const [day, setDay] = useState(() => dayIndex());

  useEffect(() => {
    const tick = () => {
      setSlot(timeSlot());
      setDay(dayIndex());
    };
    const id = setInterval(tick, 60_000);
    // Also on return to the tab: a backgrounded tab's interval is throttled
    // hard by the browser, so coming back after hours would otherwise show
    // yesterday evening's quote until the next tick landed.
    document.addEventListener('visibilitychange', tick);
    return () => {
      clearInterval(id);
      document.removeEventListener('visibilitychange', tick);
    };
  }, []);

  const list = QUOTES[slot] || QUOTES.morning;
  const offset = SURFACE_OFFSET[surface] ?? 0;
  const quote = list[(day + offset) % list.length];
  if (!quote) return null;

  return (
    <figure className={`qc qc-${size}${className ? ` ${className}` : ''}`}>
      <blockquote className="qc-text">{quote.text}</blockquote>
      {quote.by && <figcaption className="qc-by">{quote.by}</figcaption>}
    </figure>
  );
}
