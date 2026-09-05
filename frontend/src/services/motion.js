/**
 * Reduced motion, from two sources that both have to be honoured.
 *
 * The app already respected the DEVICE setting (`prefers-reduced-motion`) in the
 * splash screen, the product tour, the landing page and a couple of scroll
 * animations. What it never respected was its own switch: Profile > Preferences
 * > Reduced motion saved `reduced_motion` to the server, read it back to draw
 * the toggle, and then nothing anywhere consumed it. The switch was decorative.
 *
 * That is a bad thing for any setting and a worse one for an accessibility
 * setting, because the person who turns it on is the person least able to shrug
 * off it not working -- and they have no way to tell it did nothing.
 *
 * So: the founder's choice is stamped on <html> as `data-reduced-motion`, the
 * stylesheet flattens animation and transition durations under that attribute,
 * and `prefersReducedMotion()` below is the single check every script uses. On
 * means on, whichever of the two switches is set; a founder who has asked their
 * operating system for calm does not have to ask us separately.
 */

const ATTR = 'data-reduced-motion';

/** The device's own setting. Guarded: matchMedia is absent in some embeds. */
export function deviceWantsReducedMotion() {
  try {
    return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
  } catch {
    return false;
  }
}

/**
 * Should motion be reduced right now? True when EITHER the device asks for it
 * or the founder has turned it on in Ally. Use this instead of calling
 * matchMedia directly, or the in-app switch goes back to meaning nothing.
 */
export function prefersReducedMotion() {
  if (deviceWantsReducedMotion()) return true;
  try {
    return document.documentElement.getAttribute(ATTR) === 'true';
  } catch {
    return false;
  }
}

/**
 * Apply the founder's saved choice. Called once when settings load and again
 * whenever the switch is flipped, so the change is visible immediately rather
 * than after a reload.
 */
export function applyReducedMotion(on) {
  try {
    if (on) document.documentElement.setAttribute(ATTR, 'true');
    else document.documentElement.removeAttribute(ATTR);
  } catch { /* nothing to do -- the device setting still applies via CSS */ }
}
