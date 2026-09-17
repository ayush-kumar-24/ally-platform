import { useEffect, useState } from 'react';
import { QUOTES } from '../data/quotes';
import { getTodayQuotes } from '../services/quotes';
import { dayIndex, timeSlot } from '../utils/helpers';

/**
 * Per-surface offsets into the fallback list. Distinct values, and both smaller
 * than the shortest list in data/quotes.js, so `(day + offset) % length` can
 * never land on the same line for two surfaces on the same day.
 */
const SURFACE_OFFSET = { compass: 0, plan: 2 };

/**
 * The line at the top of the Compass and Plan Your Day, chosen for this founder.
 *
 * WHAT CHANGED AND WHY. This used to pick from a bundled list by day-of-year,
 * time of day and which page it was on -- three inputs, none of them the
 * founder. Every founder on the platform read the same sentence at the same
 * moment, which is exactly the opposite of what a line is for: a founder should
 * read it and think "that is where I am right now", and they cannot if it was
 * written for everyone at once.
 *
 * Now the backend chooses two lines for each founder overnight from their stage
 * and what their profile says they are dealing with, and this reads them. The
 * pick is fixed until midnight IST, so a refresh does not reshuffle it and the
 * two pages never show the same line.
 *
 * THE BUNDLED LIST IS STILL HERE, as the fallback. It covers the request
 * failing, the founder being brand new, the backend not being deployed yet, and
 * the feature being switched off -- all of which should look like a normal card
 * rather than an empty panel or a spinner. Which is why the fallback renders
 * FIRST and is replaced if and when the fetch lands: a card that is right
 * immediately and better a moment later beats one that is blank for 200ms.
 *
 * NO ATTRIBUTION, on either path. Every line is written for this product and
 * credited to nobody -- the point is recognition, not authority.
 *
 * The clock still drives the fallback, and is polled rather than scheduled to
 * the boundary: a laptop that sleeps through 6pm wakes with a stale timeout, and
 * a founder with the tab open all afternoon would keep reading the morning line
 * into the night. A minute of lag beats a timer that can silently stop being
 * true.
 */
export default function QuoteCard({ size = 'sm', surface = 'plan', className = '' }) {
  const [slot, setSlot] = useState(() => timeSlot());
  const [day, setDay] = useState(() => dayIndex());
  const [chosen, setChosen] = useState(null);

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

  useEffect(() => {
    let live = true;
    getTodayQuotes().then((bySurface) => {
      // Guarded against the unmount: this is decoration, and a setState on a
      // card the founder has already navigated away from is a warning in the
      // console for no benefit.
      if (live && bySurface[surface]) setChosen(bySurface[surface]);
    });
    return () => { live = false; };
  }, [surface]);

  const list = QUOTES[slot] || QUOTES.morning;
  const offset = SURFACE_OFFSET[surface] ?? 0;
  const text = chosen ?? list[(day + offset) % list.length]?.text;
  if (!text) return null;

  return (
    <figure className={`qc qc-${size}${className ? ` ${className}` : ''}`}>
      <blockquote className="qc-text">{text}</blockquote>
    </figure>
  );
}
