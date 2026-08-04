import { useState } from 'react';

const LABELS = ['Poor', 'Fair', 'Good', 'Great', 'Excellent'];

/**
 * A 1-5 star rating.
 *
 * Implemented as a radiogroup rather than five buttons, so arrow keys move
 * between stars the way a keyboard user expects, and each option announces
 * what it means ("3 of 5, Good") instead of just "star".
 */
export default function StarRating({ value, onChange, disabled = false }) {
  const [hover, setHover] = useState(0);
  const shown = hover || value || 0;

  const move = (delta) => {
    const next = Math.min(5, Math.max(1, (value || 0) + delta));
    onChange(next);
  };

  return (
    <div
      className="stars"
      role="radiogroup"
      aria-label="Rating out of five"
      onMouseLeave={() => setHover(0)}
      onKeyDown={(e) => {
        if (disabled) return;
        if (e.key === 'ArrowRight' || e.key === 'ArrowUp') { e.preventDefault(); move(1); }
        if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') { e.preventDefault(); move(-1); }
      }}
    >
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          className={`star${n <= shown ? ' on' : ''}`}
          role="radio"
          aria-checked={value === n}
          aria-label={`${n} of 5 — ${LABELS[n - 1]}`}
          // Only the selected star (or the first, when nothing is chosen) is in
          // the tab order; arrow keys handle the rest. Five tab stops for one
          // question is a lot of keystrokes.
          tabIndex={value === n || (!value && n === 1) ? 0 : -1}
          disabled={disabled}
          onMouseEnter={() => setHover(n)}
          onClick={() => onChange(n)}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
          </svg>
        </button>
      ))}
      <span className="stars-label" aria-hidden="true">{shown ? LABELS[shown - 1] : ''}</span>
    </div>
  );
}
