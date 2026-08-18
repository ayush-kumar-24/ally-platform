/**
 * services/voice.js — browser audio recording + server-side transcription.
 *
 * Recording is MediaRecorder/getUserMedia (browser-native); transcription is a
 * real backend call to POST /voice/transcribe (OpenAI Whisper server-side) — no
 * browser speech API involved, so accuracy/support is consistent across browsers.
 *
 * Plan gating goes through the same entitlement catalog as every other gated
 * feature (services/plans.js FEATURES.VOICE_CHAT / VOICE_DIAGNOSIS, mirroring
 * app/plans/catalog.py) — this endpoint doesn't invent its own "free plan"
 * rule, it asks the same catalog PlanGate/chat_gate do. The backend's
 * FeatureNotInPlanError (403) is the actual authority; the UI-level pre-check
 * lives in the caller (AllyChat.jsx, via can(plan, FEATURES.VOICE_CHAT)) so a
 * free founder never even sees the recording UI activate for chat.
 */

import { post } from './api';

export class VoiceUpgradeRequiredError extends Error {
  constructor(message) {
    super(message || 'This voice feature requires a different plan.');
    this.name = 'VoiceUpgradeRequiredError';
  }
}

/** Records from the mic until `stop()` is called; resolves the recorded Blob.
 *
 * Also exposes `getLevel()` -- current mic amplitude, 0..1 -- so callers can
 * render a live "we can hear you" meter. It reads the real stream through a
 * Web Audio AnalyserNode rather than animating on a timer, so the bars reflect
 * what the mic is actually picking up: silence reads flat, which is the whole
 * point. A founder who is muted, or too far from the mic, sees it immediately
 * instead of discovering it in a bad transcript afterwards.
 */
export function startRecording() {
  return navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
    const mimeType = MediaRecorder.isTypeSupported('audio/webm')
      ? 'audio/webm'
      : ''; // let the browser pick a supported default
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    const chunks = [];
    recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };

    /* Metering is strictly best-effort: if AudioContext is unavailable or
       blocked, the recording itself must still work, so every failure here
       degrades to a flat level rather than breaking the mic. */
    let audioCtx = null;
    let analyser = null;
    let timeData = null;
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (Ctx) {
        audioCtx = new Ctx();
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 1024;
        analyser.smoothingTimeConstant = 0.75;
        audioCtx.createMediaStreamSource(stream).connect(analyser);
        timeData = new Uint8Array(analyser.fftSize);
      }
    } catch { /* metering unavailable -- recording continues without it */ }

    const teardown = () => {
      stream.getTracks().forEach((t) => t.stop());
      analyser = null;
      timeData = null;
      // close() is async and rejects if already closed; nothing to do either way.
      try { audioCtx?.close?.().catch?.(() => {}); } catch { /* already closed */ }
      audioCtx = null;
    };

    const stopped = new Promise((resolve) => {
      recorder.onstop = () => {
        teardown();
        resolve(new Blob(chunks, { type: recorder.mimeType || 'audio/webm' }));
      };
    });

    recorder.start();
    return {
      stop: () => { recorder.stop(); return stopped; },
      cancel: () => {
        recorder.onstop = null;
        recorder.stop();
        teardown();
      },
      /* RMS of the time-domain signal, not peak -- peak jumps to full on any
         transient and reads as a permanently solid bar. */
      getLevel: () => {
        if (!analyser || !timeData) return 0;
        analyser.getByteTimeDomainData(timeData);
        let sumSquares = 0;
        for (let i = 0; i < timeData.length; i++) {
          const v = (timeData[i] - 128) / 128; // centre at 0, normalise to -1..1
          sumSquares += v * v;
        }
        return Math.sqrt(sumSquares / timeData.length);
      },
    };
  });
}

/**
 * Upload a recorded blob for transcription.
 * @param {Blob} blob
 * @param {'diagnosis'|'chat'} context
 * @returns {Promise<string>} transcribed text
 */
export async function transcribeAudio(blob, context) {
  const form = new FormData();
  form.append('context', context);
  const ext = blob.type.includes('webm') ? 'webm' : blob.type.includes('mp4') ? 'mp4' : 'wav';
  form.append('file', blob, `recording.${ext}`);

  try {
    const data = await post('/voice/transcribe', form, {
      headers: { 'Content-Type': undefined }, // let axios set the multipart boundary
    });
    return data.text;
  } catch (err) {
    if (err.status === 403 && err.data?.error === 'FeatureNotInPlanError') {
      throw new VoiceUpgradeRequiredError(err.detail);
    }
    throw err;
  }
}
