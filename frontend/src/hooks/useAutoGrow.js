import { useLayoutEffect, useRef } from 'react';

/**
 * Grows a textarea to fit what has been typed into it, and shrinks it back
 * when the field is cleared.
 *
 * A composer that stays one line tall while the answer runs to four asks the
 * founder to write into a slot: the sentence they are still forming scrolls
 * out of sight above the caret. Ally asks open questions, so the long answer
 * is the useful one and the field should not argue with it.
 *
 * The ceiling deliberately lives in CSS, not here — `.ci-row textarea` sets
 * `max-height`, which clamps whatever height this writes and turns the
 * scrollbar on past it. One place to change how tall a composer may get.
 *
 * Pass the current value: every composer here is controlled, so re-running on
 * the value covers typing, a cleared field after send, a restored draft, and
 * text arriving from voice transcription without any of them having to ask.
 *
 * @param {string} value the textarea's current value
 * @returns {import('react').RefObject<HTMLTextAreaElement>} ref for the textarea
 */
export default function useAutoGrow(value) {
  const ref = useRef(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    /* Measured from a collapsed field, otherwise scrollHeight only ever
       reports the height it already has and the box can never shrink. */
    el.style.height = 'auto';
    /* While voice input is recording, CSS hides the textarea and it measures
       zero. Leaving the height alone until it is shown again is right; the
       next keystroke or transcription re-runs this. */
    if (el.scrollHeight) el.style.height = el.scrollHeight + 'px';
  }, [value]);

  return ref;
}
