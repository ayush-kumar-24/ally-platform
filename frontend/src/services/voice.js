/**
 * services/voice.js — browser audio recording + server-side transcription.
 *
 * Recording is MediaRecorder/getUserMedia (browser-native); transcription is a
 * real backend call to POST /voice/transcribe (OpenAI Whisper server-side) — no
 * browser speech API involved, so accuracy/support is consistent across browsers.
 *
 * Plan gating (free plan: diagnosis only, not chat) is enforced by the backend
 * (403 VoiceUpgradeRequiredError) as the source of truth; `canUseVoiceInChat`
 * here is only a UI-level pre-check so a free founder never even sees the
 * recording UI activate for chat — it must stay consistent with, not replace,
 * the backend check.
 */

import { post } from './api';

export const FREE_PLAN = 'free';

/** Mirrors the backend gate (voice/router.py): free plan = diagnosis only. */
export function canUseVoiceInChat(user) {
  return Boolean(user) && user.plan_type !== FREE_PLAN;
}

export class VoiceUpgradeRequiredError extends Error {
  constructor() {
    super('Voice input in chat requires a paid plan.');
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
    if (err.status === 403 && err.data?.error === 'VoiceUpgradeRequiredError') {
      throw new VoiceUpgradeRequiredError();
    }
    throw err;
  }
}
