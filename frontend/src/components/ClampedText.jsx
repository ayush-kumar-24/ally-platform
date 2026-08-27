import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Body text clamped to a few lines, with a toggle that appears ONLY when there
 * is genuinely more to see.
 *
 * Founder DNA cards carry the founder's own answers verbatim, and those answers
 * are wildly uneven: one dimension holds two words ("Told straight"), the next
 * holds three hundred. Rendered raw, the long ones bury the page and the short
 * ones look broken beside them. Clamping evens the grid out without throwing a
 * single word away -- the whole answer is one click from view, and nothing is
 * summarised or truncated in storage.
 *
 * The toggle is driven by MEASUREMENT, not by a character count. A guess at
 * "long enough to need a Read more" is wrong at both ends: it puts the control
 * under text that already fits at a wide viewport, and hides it from text that
 * overflows at a narrow one. scrollHeight vs clientHeight asks the browser what
 * actually happened, at the width it actually happened at.
 */
export default function ClampedText({
  text,
  lines = 4,
  className = '',
  // The clamp itself is not card-specific -- the report hero has exactly the
  // same problem (it quotes the founder's own answers) and wants exactly the
  // same control. `baseClass` keeps each surface's own typography while
  // sharing the measurement, so a hero does not grow a second copy of this.
  baseClass = 'fd-card-desc',
}) {
  const ref = useRef(null);
  const [expanded, setExpanded] = useState(false);
  const [overflows, setOverflows] = useState(false);

  const measure = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    // Measured while clamped: expanded, scrollHeight equals clientHeight and
    // the control would delete itself the moment it was used.
    if (expanded) return;
    setOverflows(el.scrollHeight > el.clientHeight + 1);
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
  }, [measure, text]);

  if (!text) return null;

  return (
    <>
      <p
        ref={ref}
        className={`${baseClass}${expanded ? ' is-open' : ' is-clamped'}${className ? ` ${className}` : ''}`}
        style={expanded ? undefined : { WebkitLineClamp: lines }}
      >
        {text}
      </p>
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
