import { useCallback, useRef, useState } from 'react';
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

  const start = useCallback(async () => {
    if (status !== 'idle') return;
    try {
      sessionRef.current = await startRecording();
      setStatus('recording');
    } catch (err) {
      onError?.(err);
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
      onTranscribed?.(text);
    } catch (err) {
      if (err instanceof VoiceUpgradeRequiredError) {
        onUpgradeRequired?.();
      } else {
        onError?.(err);
      }
    } finally {
      setStatus('idle');
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

  return { status, toggle, start, stop, cancel };
}
