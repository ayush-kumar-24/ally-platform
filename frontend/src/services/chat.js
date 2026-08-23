/**
 * services/chat.js — Ally Chat.
 *
 * Conversations are server-owned, so a founder's history survives a reload and
 * follows them across devices. Nothing here keeps its own copy of the transcript;
 * the server list is the truth.
 */

import { get, post, del, prune } from './api';

export function listConversations(includeArchived = false) {
  return get('/chat/conversations', { params: { include_archived: includeArchived } });
}

export function createConversation(title) {
  return post('/chat/conversations', prune({ title: title || undefined }));
}

export function getConversation(conversationId) {
  return get(`/chat/conversations/${conversationId}`);
}

/**
 * The actual transcript. getConversation() above returns only the header
 * (title, counts, timestamps) -- the messages themselves live here, on their
 * own endpoint. Previously there was nowhere to get them from at all, so
 * reopening a past conversation always rendered empty regardless of how many
 * messages it really had.
 */
export function getConversationMessages(conversationId) {
  return get(`/chat/conversations/${conversationId}/messages`);
}

export function archiveConversation(conversationId) {
  return del(`/chat/conversations/${conversationId}`);
}

export function restoreConversation(conversationId) {
  return post(`/chat/conversations/${conversationId}/restore`, {});
}

/**
 * Send a message and get Ally's reply.
 *
 * The plan gate runs server-side ahead of this, so a 403/402/429 here is a real
 * limit being enforced, not a transport error — surface it with explainLimit().
 */
export function sendMessage({ message, conversationId, sessionId, language, requestId }) {
  // Nulls are pruned: `language` and `response_category` are plain strings with
  // server defaults, so an explicit null is a validation error.
  return post('/chat/message', prune({
    message,
    conversation_id: conversationId,
    session_id: sessionId,
    language,
    request_id: requestId,
  }));
}

/* --- attachments ---------------------------------------------------------
   Upload lives in the page (it needs FormData + the multipart Content-Type
   dance); these two are the reads/removes the chip row needs so a founder
   can see what is actually attached and take one back off. */

/** Active attachments on a conversation. Archived ones are excluded, which
 *  matches what the chat's context builder actually feeds the LLM. */
export function listAttachments(conversationId) {
  return get(`/chat/conversations/${conversationId}/attachments`);
}

/** Tie an uploaded file to the message it was sent with. Uploads happen
 *  before the message exists, so this can only run after the send returns --
 *  it is what lets a reload put the chip back in its own bubble instead of
 *  back in the composer. */
export function linkAttachmentToMessage(attachmentId, messageId) {
  return post(`/chat/attachments/${attachmentId}/link`, { message_id: messageId });
}

/** Archive (not purge): the row and its bytes stay, but the attachment drops
 *  out of the conversation and out of the LLM's context -- reversible, and
 *  the audit trail survives. */
export function removeAttachment(attachmentId) {
  return del(`/chat/attachments/${attachmentId}`);
}

export function getSuggestions(conversationId) {
  return get(`/chat/conversations/${conversationId}/suggestions`);
}

/**
 * `feedback` must be one of the server's three values -- 'accepted', 'dismissed'
 * or 'ignored' -- not a free-form string. This previously sent `feedback_type`
 * (wrong key) with values like 'helpful' (not in the server's enum), so every
 * call would have 422'd the moment a UI wired up a feedback button.
 */
export function sendSuggestionFeedback(suggestionId, feedback, note) {
  return post(`/chat/suggestions/${suggestionId}/feedback`, { feedback, note });
}

/**
 * A timestamp as a person reads it.
 *
 * `created_at` went straight to the screen, so opening an older conversation
 * printed "2026-08-01T14:22:31.118Z" under every bubble while messages sent in
 * the same session said "Just now".
 */
export function messageTime(iso) {
  if (!iso) return '';
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return '';

  const minutes = Math.floor((Date.now() - then.getTime()) / 60000);
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;

  const midnight = new Date();
  midnight.setHours(0, 0, 0, 0);
  const clock = then.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  if (then >= midnight) return clock;

  const yesterday = new Date(midnight);
  yesterday.setDate(yesterday.getDate() - 1);
  if (then >= yesterday) return `Yesterday, ${clock}`;

  return then.toLocaleDateString(undefined, { day: 'numeric', month: 'short' }) + `, ${clock}`;
}

/* The server speaks OpenAI's vocabulary ('user' / 'assistant'); the UI speaks
 * its own ('me' / 'ally'), which is what the stylesheet is written against.
 *
 * Both halves have to be translated. This used to map only 'assistant' and let
 * everything else through untouched, so a stored 'user' message rendered as
 * `.msg.user` -- a class the CSS has never defined. The bare `.bubble` rule
 * carries no background and no colour, so the founder's own words came out as
 * near-invisible text on the dark ground, left-aligned, with no green bubble.
 * Live-confirmed against the database, which holds exactly 'user' and
 * 'assistant'.
 *
 * It hid well because sending is optimistic: a message you have just typed is
 * pushed with role 'me' and looks right. Only on REOPENING the conversation,
 * when the transcript is rebuilt from the server, did half of it vanish.
 */
const UI_ROLE = { assistant: 'ally', ally: 'ally', user: 'me', me: 'me' };

/** Normalise a server message into what the UI renders. */
export function toUiMessage(m) {
  return {
    id: m.message_id ?? m.id,
    // Unknown roles fall back to 'ally' rather than passing through: an
    // unstyled role renders invisibly, and silently dropping a message from a
    // transcript is far worse than showing it in the wrong bubble.
    role: UI_ROLE[m.role] ?? 'ally',
    text: m.content ?? m.text ?? '',
    time: messageTime(m.created_at),
  };
}
