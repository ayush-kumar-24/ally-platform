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

/** Records from the mic until `stop()` is called; resolves the recorded Blob. */
export function startRecording() {
  return navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
    const mimeType = MediaRecorder.isTypeSupported('audio/webm')
      ? 'audio/webm'
      : ''; // let the browser pick a supported default
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    const chunks = [];
    recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };

    const stopped = new Promise((resolve) => {
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        resolve(new Blob(chunks, { type: recorder.mimeType || 'audio/webm' }));
      };
    });

    recorder.start();
    return {
      stop: () => { recorder.stop(); return stopped; },
      cancel: () => {
        recorder.onstop = null;
        recorder.stop();
        stream.getTracks().forEach((t) => t.stop());
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
