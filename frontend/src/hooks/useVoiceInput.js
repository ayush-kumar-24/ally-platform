import { useCallback, useEffect, useRef, useState } from 'react';
import { startRecording, transcribeAudio, VoiceUpgradeRequiredError } from '../services/voice';

/**
 * One mic button's state machine: idle -> recording -> transcribing -> idle.
 *
 * `context` is 'diagnosis' or 'chat' (passed straight through to the backend,
 * which is the actual authority on the free-plan chat gate). `onUpgradeRequired`
 * fires when the backend rejects a chat request from a free-plan founder —
 * callers show their own popup/toast from there; this hook does not decide UI.
 *
 * `inputRef` is the composer's textarea. Optional, and only keyboard control
 * needs it: with it, Enter ends a recording and Escape throws it away, and the
 * founder lands back in the field — caret at the end — when the transcript
 * arrives, so a second Enter sends. Dictating never has to leave the keyboard.
 * The mic button still starts and stops everything on its own, which is what
 * a phone actually uses: a soft keyboard is not on screen while someone is
 * talking into their phone, so the keys here are an accelerator and never the
 * only way out of a recording.
 */
export function useVoiceInput({ context, onTranscribed, onUpgradeRequired, onError, inputRef }) {
  const [status, setStatus] = useState('idle'); // idle | recording | transcribing
  const sessionRef = useRef(null);
  const alive = useRef(true);
  /* Set only when a transcript actually landed, so an upgrade prompt or a
     microphone error does not yank focus into an empty field. */
  const refocusOnIdle = useRef(false);

  /* startRecording() holds a live getUserMedia stream, and only cancel() stops
     its tracks. Nothing called cancel() on unmount, so navigating away from
     AllyChat / DiagnosisChat / ProfileBuild mid-recording left the microphone
     open — with the browser's recording indicator lit — until the tab closed.
     The alive flag additionally stops the async continuations below from
     setting state on an unmounted component. */
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      sessionRef.current?.cancel();
      sessionRef.current = null;
    };
  }, []);

  const start = useCallback(async () => {
    if (status !== 'idle') return;
    try {
      const session = await startRecording();
      if (!alive.current) { session.cancel(); return; }
      sessionRef.current = session;
      setStatus('recording');
    } catch (err) {
      if (alive.current) onError?.(err);
    }
  }, [status, onError]);

  const stop = useCallback(async () => {
    const session = sessionRef.current;
    if (!session) return;
    sessionRef.current = null;
    setStatus('transcribing');
    try {
      const blob = await session.stop();
      const text = await transcribeAudio(blob, context);
      if (alive.current) {
        refocusOnIdle.current = true;
        onTranscribed?.(text);
      }
    } catch (err) {
      if (!alive.current) return;
      if (err instanceof VoiceUpgradeRequiredError) {
        onUpgradeRequired?.();
      } else {
        onError?.(err);
      }
    } finally {
      if (alive.current) setStatus('idle');
    }
  }, [context, onTranscribed, onUpgradeRequired, onError]);

  const cancel = useCallback(() => {
    sessionRef.current?.cancel();
    sessionRef.current = null;
    setStatus('idle');
  }, []);

  const toggle = useCallback(() => {
    if (status === 'recording') stop();
    else if (status === 'idle') start();
  }, [status, start, stop]);

  /* Enter ends the recording; Escape discards it.

     On the WINDOW, not on the text field, and that is not a stylistic choice:
     while status !== 'idle' the composer swaps the textarea out for the live
     meter (.voice-meter takes its slot -- see platform.css), so the field is
     display:none for the whole recording. A hidden element cannot hold focus
     or receive keydown, which means the composer's own onKeyDown -- the one
     that normally sends on Enter -- is unreachable from the moment recording
     starts. Without this listener there is no key that can stop a recording.

     Capture phase so this resolves before any page-level Enter handler, and
     nothing runs while transcribing: the request is still in flight, the
     field is empty, and an Enter that slipped through would either send
     nothing or race the transcript that is about to be written into it. */
  useEffect(() => {
    if (status === 'idle') return undefined;

    const onKeyDown = (e) => {
      if (e.key !== 'Enter' && e.key !== 'Escape') return;
      // An IME candidate window is mid-composition; that Enter is picking a
      // word, not ending a recording.
      if (e.isComposing || e.keyCode === 229) return;
      /* Some other field is still on screen and focused -- AllyChat's
         rename-this-conversation input is the live case. Its Enter belongs to
         it, not to us. Our own textarea is excluded because it is hidden right
         now and cannot be the one being typed into. */
      const el = document.activeElement;
      if (
        el
        && el !== inputRef?.current
        && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)
      ) return;

      e.preventDefault();
      e.stopPropagation();
      if (status === 'transcribing') return;   // swallowed on purpose, see above
      if (e.key === 'Enter') stop();
      else cancel();
    };

    window.addEventListener('keydown', onKeyDown, true);
    return () => window.removeEventListener('keydown', onKeyDown, true);
  }, [status, stop, cancel, inputRef]);

  /* Put the founder back in the text field once a transcript lands, caret at
     the end. Starting a recording moves focus to the mic button they clicked,
     and the field was hidden besides, so without this the transcript is on
     screen with nothing focused and the Enter meant to send it goes nowhere.
     Caret at the end rather than selecting, so the obvious next keystroke
     appends to what they said instead of replacing it.

     In an effect, not inline after onTranscribed: the field is still
     display:none until React re-renders on 'idle', and focus() on a hidden
     element is a silent no-op. */
  useEffect(() => {
    if (status !== 'idle' || !refocusOnIdle.current) return;
    refocusOnIdle.current = false;
    const el = inputRef?.current;
    if (!el) return;
    el.focus();
    const end = el.value.length;
    el.setSelectionRange?.(end, end);
  }, [status, inputRef]);

  /* Read on demand (rAF, by the meter component) rather than pushed through
     React state -- amplitude changes every frame, and putting that in state
     would re-render the whole chat ~60x/sec while someone is talking. */
  const getLevel = useCallback(() => sessionRef.current?.getLevel?.() ?? 0, []);

  return { status, toggle, start, stop, cancel, getLevel };
}
