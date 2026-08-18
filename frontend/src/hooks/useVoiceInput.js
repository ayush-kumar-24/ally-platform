import { useCallback, useEffect, useRef, useState } from 'react';
import { startRecording, transcribeAudio, VoiceUpgradeRequiredError } from '../services/voice';

/**
 * One mic button's state machine: idle -> recording -> transcribing -> idle.
 *
 * `context` is 'diagnosis' or 'chat' (passed straight through to the backend,
 * which is the actual authority on the free-plan chat gate). `onUpgradeRequired`
 * fires when the backend rejects a chat request from a free-plan founder —
 * callers show their own popup/toast from there; this hook does not decide UI.
 */
export function useVoiceInput({ context, onTranscribed, onUpgradeRequired, onError }) {
  const [status, setStatus] = useState('idle'); // idle | recording | transcribing
  const sessionRef = useRef(null);
  const alive = useRef(true);

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
      if (alive.current) onTranscribed?.(text);
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

  /* Read on demand (rAF, by the meter component) rather than pushed through
     React state -- amplitude changes every frame, and putting that in state
     would re-render the whole chat ~60x/sec while someone is talking. */
  const getLevel = useCallback(() => sessionRef.current?.getLevel?.() ?? 0, []);

  return { status, toggle, start, stop, cancel, getLevel };
}
