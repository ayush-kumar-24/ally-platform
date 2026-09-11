import { useCallback, useEffect, useRef, useState } from 'react';

/* navigator.clipboard is the whole story on https, which production is. The
   fallback is for the cases where it silently is not there: an http origin
   (a LAN preview of the dev server on a phone), an iframe without the
   clipboard-write permission, and older iOS Safari. Returning false rather
   than throwing lets the button say so instead of looking like it worked. */
async function writeClipboard(text) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* Denied or unavailable -- fall through to the old way rather than give up. */
  }
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    // Off-screen but still selectable. position:fixed keeps focusing it from
    // scrolling the transcript out from under the founder.
    ta.style.cssText = 'position:fixed;top:0;left:-9999px;opacity:0';
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

const COPIED_MS = 1600;

/**
 * The small row of controls under one message: copy it, and — where the caller
 * passes `onEdit` — edit it.
 *
 * Shared by every chat surface (AllyChat, DiagnosisChat, FounderDnaChat,
 * CurrentProblemChat, ProfileBuild), which all render the same
 * `.msg > div > .bubble` shape, so the row sits in the same place in all of
 * them and behaves identically.
 *
 * `onEdit` is deliberately opt-in per surface rather than "show it on every
 * message from the founder". Editing only means something where re-sending
 * means something: in open conversation. An answer inside the diagnosis has
 * already been scored server-side and the session has moved to the next
 * question, so there is nothing an edit here could revise — see the note in
 * DiagnosisChat.
 */
export default function MessageActions({ text, onEdit, what = 'message' }) {
  const [state, setState] = useState(null); // null | 'copied' | 'failed'
  const timer = useRef(null);

  useEffect(() => () => clearTimeout(timer.current), []);

  const copy = useCallback(async () => {
    const ok = await writeClipboard(text);
    setState(ok ? 'copied' : 'failed');
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setState(null), COPIED_MS);
  }, [text]);

  return (
    <div className="msg-actions">
      <button
        type="button"
        className={`msg-act${state ? ` is-${state}` : ''}`}
        onClick={copy}
        /* The label carries the outcome as well as the action, so a screen
           reader hears that the copy happened -- the tick alone is silent. */
        aria-label={
          state === 'copied' ? `${what} copied`
            : state === 'failed' ? `Could not copy ${what}`
              : `Copy ${what}`
        }
        title={state === 'failed' ? 'Could not copy' : state === 'copied' ? 'Copied' : 'Copy'}
      >
        {state === 'copied' ? (
          <svg viewBox="0 0 24 24" aria-hidden="true"><polyline points="20 6 9 17 4 12" /></svg>
        ) : (
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <rect x="9" y="9" width="12" height="12" rx="2" />
            <path d="M5 15V5a2 2 0 012-2h10" />
          </svg>
        )}
        <span className="msg-act-text">
          {state === 'copied' ? 'Copied' : state === 'failed' ? "Couldn't copy" : 'Copy'}
        </span>
      </button>

      {onEdit && (
        <button
          type="button"
          className="msg-act"
          onClick={onEdit}
          aria-label={`Edit ${what} and send it again`}
          title="Edit and send again"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 20h9" />
            <path d="M16.5 3.5a2.12 2.12 0 013 3L7 19l-4 1 1-4z" />
          </svg>
          <span className="msg-act-text">Edit</span>
        </button>
      )}

      {/* Announced once per outcome. The buttons' own labels change too, but a
          founder who has already moved focus away would otherwise never learn
          that a copy failed. */}
      <span className="sr-only" role="status" aria-live="polite">
        {state === 'copied' ? 'Copied to clipboard' : state === 'failed' ? 'Could not copy' : ''}
      </span>
    </div>
  );
}
