import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';

/* How far off the bottom the founder may be and still count as "reading the
   newest message". A few pixels of slack cost nothing and cover sub-pixel
   rounding and a half-finished trackpad flick; a whole message's worth would
   mean hijacking someone who has deliberately scrolled up. */
const NEAR_BOTTOM_PX = 120;

/**
 * Keeps a chat transcript pinned to its newest message.
 *
 * Every chat surface here used to carry its own one-line version of this:
 * `scrollTop = scrollHeight` in an effect on [messages]. That fires once, at
 * the instant the message is committed, and is then blind to everything that
 * happens next — an avatar image decoding, a web font swapping in, the answer
 * composer mounting under the question, a bubble's entry animation settling,
 * markdown laying out. Any of those add height after the jump, and the newest
 * message drifts back below the fold with nothing left to notice. That is what
 * a founder sees as "the chat doesn't scroll".
 *
 * So this follows the content instead of sampling it once: a ResizeObserver on
 * each child re-pins on any late growth, and a MutationObserver catches
 * messages arriving and text changing inside them (and re-aims the
 * ResizeObserver at the new children).
 *
 * It follows only while the founder is already at the bottom. Someone who has
 * scrolled up to re-read an earlier answer is doing that on purpose, and
 * yanking them back down every time Ally types is worse than not scrolling at
 * all. Scrolling back to the bottom re-arms it.
 *
 * @param {import('react').DependencyList} [deps] state that adds messages —
 *   the observers cover the rest; this just keeps the common case in the same
 *   frame as the render, so nothing renders below the fold even briefly.
 * @param {object} [options]
 * @param {import('react').MutableRefObject<number|null>} [options.holdRef] set
 *   to the container's scrollHeight immediately before prepending older
 *   messages. The founder is then held where they were reading rather than
 *   thrown to the bottom — the exact opposite of what "load older" was clicked
 *   for. Cleared once honoured.
 * @returns {Function & {current: HTMLElement|null}} ref for the scroll
 *   container; also readable as `.current`, like a plain ref.
 */
export default function useAutoScroll(deps = [], { holdRef = null } = {}) {
  const [el, setEl] = useState(null);
  // Whether new content should be followed. Starts true: a transcript opens on
  // its newest message.
  const stuck = useRef(true);

  /* A callback ref rather than a plain object one. Several of these
     transcripts mount well after their page does — the help widget's feed
     only exists while the panel is open, and a phase chat swaps its
     transcript out for a completion screen and back — and an attach-once
     effect would look for the container before it exists and never look
     again. Carries `.current` too, so callers that read the live element
     (AllyChat measures it before prepending) are unaffected. */
  const ref = useCallback((node) => {
    ref.current = node;
    // A freshly mounted transcript opens at its newest message, whatever the
    // founder had scrolled to in the last one.
    if (node) stuck.current = true;
    setEl(node);
  }, []);

  const held = () => holdRef && holdRef.current != null;

  useEffect(() => {
    if (!el) return undefined;

    /* Only ever reads the founder's own scrolling. Scroll events are
       dispatched asynchronously, so this cannot be relied on to record what
       the hook itself just did — an observer firing in the meantime would
       read a stale answer. The two places that scroll deliberately say so
       themselves, synchronously. */
    const onScroll = () => {
      stuck.current = el.scrollHeight - el.scrollTop - el.clientHeight <= NEAR_BOTTOM_PX;
    };
    el.addEventListener('scroll', onScroll, { passive: true });

    const follow = () => {
      if (!stuck.current || held()) return;
      el.scrollTop = el.scrollHeight;
    };

    const ro = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(follow);
    /* Observing the container alone would report nothing useful: it is a
       fixed-height flex child, so it is the children that grow. */
    const watchChildren = () => {
      if (!ro) return;
      ro.disconnect();
      for (const child of el.children) ro.observe(child);
    };
    watchChildren();

    const mo = typeof MutationObserver === 'undefined' ? null : new MutationObserver((records) => {
      if (records.some((r) => r.type === 'childList' && r.target === el)) watchChildren();
      follow();
    });
    if (mo) mo.observe(el, { childList: true, subtree: true, characterData: true });

    follow();

    return () => {
      el.removeEventListener('scroll', onScroll);
      if (ro) ro.disconnect();
      if (mo) mo.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [el]);

  /* Before paint, so a new message never spends a frame below the fold. The
     observers above would catch it a tick later; this keeps it invisible. */
  useLayoutEffect(() => {
    if (!el) return;
    if (held()) {
      /* Everything added went in above the founder, so the line they were
         reading moved down by exactly the height that was added. Recording
         that they are no longer at the bottom has to happen right here: the
         scroll event saying so arrives too late to stop an observer from
         undoing the hold. */
      el.scrollTop = el.scrollHeight - holdRef.current;
      holdRef.current = null;
      stuck.current = false;
      return;
    }
    if (stuck.current) el.scrollTop = el.scrollHeight;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [el, ...deps]);

  return ref;
}
