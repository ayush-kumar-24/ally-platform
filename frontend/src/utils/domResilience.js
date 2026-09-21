/**
 * utils/domResilience.js — survive other software editing our DOM.
 *
 * THE BUG THIS FIXES, reported four times and never actually fixed until now.
 *
 * Founders kept hitting a full-page error card — "This page needs a refresh" —
 * on page after page, at random. Underneath it is always the same crash:
 *
 *     NotFoundError: Failed to execute 'removeChild' on 'Node':
 *     The node to be removed is not a child of this node.
 *
 * React keeps its own record of the DOM it built. When it unmounts something
 * it calls parent.removeChild(child) against that record. If another piece of
 * software moved or deleted that node in the meantime, the node is no longer
 * a child of that parent, the DOM throws, and the throw happens inside React's
 * commit phase — which React cannot recover from, so the whole tree unmounts
 * and the nearest error boundary paints its fallback over the page.
 *
 * "Another piece of software" is not hypothetical and not rare:
 *
 *   - Chrome's built-in page translation. It replaces each text node with a
 *     <font> wrapper. Every text node React later wants to remove is then a
 *     node React has never seen, inside a parent it does not know about.
 *   - The browser's own AI side panels (the report that prompted this fix
 *     came from a Chrome window with Gemini integrated), and reader modes.
 *   - Extensions that rewrite text in place — password managers, Grammarly,
 *     ad and cookie blockers, accessibility and dark-mode tools.
 *
 * India is a multilingual market and Chrome offers to translate an English
 * page by default, so "just don't translate the page" is not a fix we get to
 * ask for, and <meta name="google" content="notranslate"> would take the
 * translation away from the founders who need it most.
 *
 * WHAT WE DID BEFORE, AND WHY IT WAS NOT ENOUGH. The last attempt at this
 * detected the crash in ErrorBoundary and wrote a kinder message explaining
 * that an extension or a translation had probably caused it. That was a
 * better apology for the same broken page. The founder still lost the screen
 * they were on. This stops the crash instead.
 *
 * THE FIX. Make the three mutation methods React commits through tolerant of
 * a DOM that has already moved on. Each one only deviates from the standard
 * behaviour in the exact case that would otherwise throw:
 *
 *   removeChild   the child is already detached, or now lives somewhere else
 *                 -> the caller's goal ("this must not be in me") is already
 *                    true, so return the child and let React carry on.
 *   insertBefore  the reference node is no longer ours -> append instead of
 *                 throwing. The position is a guess; having the node on the
 *                 page in the wrong order beats losing the page.
 *   replaceChild  same as removeChild, then insert the replacement.
 *
 * Anything else — a genuine bug in our own code — is passed straight through
 * to the real method and still throws, so this does not quietly swallow our
 * mistakes. Every deviation is reported (throttled) under
 * source: 'dom_sync_patched', so the frequency stays visible in the backend
 * error log instead of becoming invisible the moment it stops hurting.
 *
 * Installed from main.jsx BEFORE the first render: a patch applied after
 * React has already committed a tree would miss the unmounts in between.
 */

import { reportError } from '../services/errorReporting';

/* Each kind is worth knowing about once. A translated page can generate
   hundreds of these in a second while React reconciles a list, and a flood of
   identical reports would drown the log this exists to keep honest. */
const reported = new Set();

function reportOnce(method, detail) {
  if (reported.has(method)) return;
  reported.add(method);
  try {
    reportError(
      new Error(`DOM out of sync on ${method}: ${detail}. Recovered without unmounting.`),
      { source: 'dom_sync_patched' },
    );
  } catch {
    /* Telemetry must never be the thing that breaks the page it is describing. */
  }
}

let installed = false;

export function installDomResilience() {
  // Guarded because React's StrictMode double-invokes module side effects in
  // development, and patching a patched prototype builds a chain that calls
  // the original twice.
  if (installed) return;
  if (typeof Node !== 'function' || !Node.prototype) return;
  installed = true;

  const realRemoveChild = Node.prototype.removeChild;
  const realInsertBefore = Node.prototype.insertBefore;
  const realReplaceChild = Node.prototype.replaceChild;

  Node.prototype.removeChild = function removeChild(child) {
    if (child && child.parentNode !== this) {
      reportOnce('removeChild', 'node already detached or reparented');
      return child;
    }
    return realRemoveChild.apply(this, arguments);
  };

  Node.prototype.insertBefore = function insertBefore(newNode, referenceNode) {
    // A null reference means "append", which is already what we fall back to,
    // so only a reference that has genuinely wandered off needs handling.
    if (referenceNode && referenceNode.parentNode !== this) {
      reportOnce('insertBefore', 'reference node no longer in this parent');
      return this.appendChild(newNode);
    }
    return realInsertBefore.apply(this, arguments);
  };

  Node.prototype.replaceChild = function replaceChild(newNode, oldChild) {
    if (oldChild && oldChild.parentNode !== this) {
      reportOnce('replaceChild', 'node being replaced is no longer in this parent');
      return this.appendChild(newNode);
    }
    return realReplaceChild.apply(this, arguments);
  };
}

/* Exported for the test: restores the untouched methods so one test's patch
   cannot leak into the next. Not used by the app. */
export function __uninstallDomResilience(originals) {
  Node.prototype.removeChild = originals.removeChild;
  Node.prototype.insertBefore = originals.insertBefore;
  Node.prototype.replaceChild = originals.replaceChild;
  installed = false;
  reported.clear();
}
