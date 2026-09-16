import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * A Founder DNA dimension: a few short bullets at rest, the founder's own
 * answers in full behind "Read more".
 *
 * THE BULLETS ARE A SUMMARY, NOT THE PARAGRAPH CHOPPED UP. Bulleting the answers
 * themselves was the first attempt and it changed nothing -- a 300-word answer
 * with a dot in front of it is still a 300-word answer. The preview is written
 * by the backend (reasoning/engines/founder_dna_summary.py) once per report and
 * cached on it, so the card is not paying for a model call every time someone
 * opens the page.
 *
 * WHAT "READ MORE" OPENS IS THE REAL THING. One paragraph per answer, verbatim,
 * with nothing summarised, trimmed or reordered. That is what makes a lossy
 * preview of somebody's own words acceptable: the words are one click away, and
 * the click is obvious.
 *
 * WITH NO SUMMARY it falls back to the answers themselves, each clamped to a
 * couple of lines -- which is what every report generated before the previews
 * shipped will do until someone opens it, and what any dimension the model
 * could not summarise does permanently. A plainer card, not a broken one.
 *
 * The fallback's toggle is driven by MEASUREMENT, not a character count: a guess
 * is wrong at both ends, offering "Read more" under text that already fits on a
 * wide screen and withholding it from text that overflows on a narrow one.
 * scrollHeight vs clientHeight asks the browser what actually happened, at the
 * width it actually happened at.
 */
export default function ClampedList({ items, summary, lines = 2 }) {
  const ref = useRef(null);
  const [expanded, setExpanded] = useState(false);
  const [overflows, setOverflows] = useState(false);

  const hasSummary = Array.isArray(summary) && summary.length > 0;

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
    // Only the fallback measures: a summary is short by construction and its
    // toggle is always offered, because there is always more behind it.
    if (hasSummary) return undefined;
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
  }, [measure, items, hasSummary]);

  if (!items || items.length === 0) return null;

  /* SUMMARISED: bullets at rest, the answers in full when opened. */
  if (hasSummary) {
    return (
      <>
        {expanded ? (
          <div className="fd-answers">
            {items.map((text, i) => (
              // eslint-disable-next-line react/no-array-index-key -- answers are plain strings with no id, and two identical ones are possible
              <p key={i} className="fd-card-desc">{text}</p>
            ))}
          </div>
        ) : (
          <ul className="fd-bullets">
            {summary.map((text, i) => (
              // eslint-disable-next-line react/no-array-index-key -- same
              <li key={i}><span className="fd-bullet-text">{text}</span></li>
            ))}
          </ul>
        )}
        <button
          type="button"
          className="fd-more"
          aria-expanded={expanded}
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? 'Show less' : 'Read more'}
        </button>
      </>
    );
  }

  /* NO SUMMARY: the answers themselves, one bullet each, clamped. */
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
