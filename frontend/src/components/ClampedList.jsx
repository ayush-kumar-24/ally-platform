import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * A fact's separate answers as separate bullets, each clamped to a couple of
 * lines, with one toggle that opens all of them.
 *
 * WHY BULLETS AND NOT A PARAGRAPH. A Founder DNA dimension is not one answer.
 * It is up to three of the founder's own answers to that dimension (see
 * reasoning/engines/founder_dna_extras.py, which caps each at three), and the
 * card used to join them with ", " -- so two unrelated narrative answers read
 * as one run-on sentence and the boundary the founder actually wrote was gone.
 * One bullet per answer puts that boundary back. It is a rendering change and
 * nothing else: no answer is summarised, rewritten or dropped.
 *
 * WHY EACH BULLET IS CLAMPED RATHER THAN THE LIST. Clamping the list would hide
 * whole answers -- the founder would see two of their three and have no way to
 * tell the third was there. Clamping each bullet instead shows every answer at
 * rest, at two lines apiece, so the card is scannable and the shape of what is
 * there is honest.
 *
 * THE TOGGLE IS DRIVEN BY MEASUREMENT, like ClampedText's: a character-count
 * guess is wrong at both ends -- it offers "Read more" under text that already
 * fits on a wide screen, and withholds it from text that overflows on a narrow
 * one. scrollHeight vs clientHeight asks the browser what actually happened, at
 * the width it actually happened at.
 */
export default function ClampedList({ items, lines = 2 }) {
  const ref = useRef(null);
  const [expanded, setExpanded] = useState(false);
  const [overflows, setOverflows] = useState(false);

  const measure = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    // Measured while clamped: expanded, scrollHeight equals clientHeight and
    // the control would delete itself the moment it was used.
    if (expanded) return;
    const spans = el.querySelectorAll('.fd-bullet-text');
    setOverflows(Array.from(spans).some((s) => s.scrollHeight > s.clientHeight + 1));
  }, [expanded]);

  useEffect(() => {
    measure();
    if (typeof ResizeObserver === 'undefined') {
      // Older browsers: re-check on window resize. Coarser, but the alternative
      // is a control that is right at first paint and wrong ever after.
      window.addEventListener('resize', measure);
      return () => window.removeEventListener('resize', measure);
    }
    const ro = new ResizeObserver(measure);
    if (ref.current) ro.observe(ref.current);
    return () => ro.disconnect();
  }, [measure, items]);

  if (!items || items.length === 0) return null;

  return (
    <>
      <ul className={`fd-bullets${expanded ? ' is-open' : ' is-clamped'}`} ref={ref}>
        {items.map((text, i) => (
          // The clamp lives on an inner span, not on the <li>. -webkit-box is
          // the only cross-browser way to clamp by LINES, and setting it on the
          // list item replaces display:list-item -- which deletes the bullet
          // the clamp was added to sit beside.
          // eslint-disable-next-line react/no-array-index-key -- answers are plain strings with no id, and two identical ones are possible
          <li key={i}>
            <span
              className="fd-bullet-text"
              style={expanded ? undefined : { WebkitLineClamp: lines }}
            >
              {text}
            </span>
          </li>
        ))}
      </ul>
      {overflows && (
        <button
          type="button"
          className="fd-more"
          aria-expanded={expanded}
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? 'Show less' : 'Read more'}
        </button>
      )}
    </>
  );
}
