import { useState, useRef, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import {
  CONVERSATION_PAGE,
  MESSAGE_PAGE,
  createConversation,
  deleteConversation,
  getConversationMessages,
  getSuggestions,
  linkAttachmentToMessage,
  listAttachments,
  listConversations,
  markConversationRead,
  removeAttachment,
  renameConversation,
  restoreAttachment,
  sendMessage,
  sendSuggestionFeedback,
  streamMessage,
  toUiMessage,
} from '../services/chat';
import { post, ApiError } from '../services/api';
// Shared so the whole app switches greeting at the same hour. This page used to
// define its own with a 17:00 afternoon cutoff while everywhere else used 18:00,
// so between 5 and 6pm the dashboard said "Good afternoon" and this said
// "Good evening" -- the exact bug greetingNow's docstring was written to end.
import { greetingNow } from '../utils/helpers';
import { useVoiceInput } from '../hooks/useVoiceInput';
import VoiceBars from '../components/VoiceBars';
import Markdown from '../components/Markdown';
import { usePlan as usePlanGateEntitlements } from '../components/PlanGate';
import { explainLimit, getMyPlan, can, FEATURES } from '../services/plans';

/**
 * Whether a send goes over /chat/stream instead of /chat/message.
 *
 * OFF, and this is a measurement rather than a preference. /chat/stream is a
 * complete, correct SSE endpoint, but the layer beneath it is not incremental:
 * StreamingGenerator calls the ordinary blocking `chat_service.send_message`,
 * waits for the entire answer, and only then cuts it into sentence-sized
 * pieces (see its own module docstring). Measured against the real backend, a
 * 445-character reply produced its FIRST token at 14.44s of a 14.44s total --
 * every chunk lands at the end, together. Time to first token is therefore
 * identical to the blocking endpoint, and switching would buy a second code
 * path in the send flow for no gain the founder could perceive.
 *
 * What has to change before this is worth turning on: the OpenAI provider
 * (app/services/llm/providers/openai.py) has no streaming mode at all, so real
 * streaming means `stream=True` there, an incremental path through the LLM
 * adapter and ChatExecutionService, and a StreamingGenerator that forwards
 * provider deltas instead of chunking a finished string. When that lands, this
 * flips to true and nothing else here changes -- streamReply below is written
 * against the event contract the endpoint already emits and is exercised by
 * the backend's own SSE tests.
 */
const USE_STREAMING = false;

/**
 * What clicking a suggestion does, keyed by the server's suggestion_type.
 *
 * This map is also the filter: a suggestion whose type is absent here is not
 * rendered. That is deliberate and it is not a blacklist -- a suggestion the
 * founder cannot act on is not a suggestion, it is a sentence. The backend's
 * `continue_conversation` rule fires on every single turn to say "keep going,
 * ask your next question whenever you're ready", which is exactly that: it has
 * no action because there is nothing to do with it, so it never appears.
 *
 *   go      navigate somewhere
 *   ask     send this as the next message
 *   prefill put text in the composer for the founder to edit before sending
 */
const SUGGESTION_ACTIONS = {
  // The one suggestion that names a real gap. Points at the journey entry
  // point rather than /app/diagnosis, which is phase three of three.
  missing_information: { label: 'Start your diagnosis', go: '/app/founder-dna-journey' },
  goal_reminder: {
    label: 'Talk this through',
    ask: (s) => `From my diagnosis: ${s.body.replace(/^From your diagnosis:\s*/i, '')}\n\nHow should I approach this?`,
  },
  summarization: {
    label: 'Summarise it',
    ask: () => 'Summarise this conversation so far — the key points and anything I decided.',
  },
  attachment_review: {
    label: 'Ask about the files',
    ask: () => 'Take the files I attached into account — what stands out?',
  },
  link_discussion: {
    label: 'Discuss the links',
    ask: () => 'Walk me through the links I shared.',
  },
  follow_up: {
    label: 'Go deeper',
    // body is "Want to go deeper on <topic>?", where the topic is the top root
    // cause from the founder's own diagnosis.
    ask: (s) => {
      const topic = /go deeper on (.+?)\?*$/i.exec(s.body || '')?.[1];
      return topic ? `Go deeper on ${topic}.` : 'Go deeper on that.';
    },
  },
  // This one fires because Ally could not answer, so the thing worth doing is
  // editing the question that failed -- not sending anything new. `refillLast`
  // puts the founder's own last message back in the composer; the handler
  // resolves it, because only the page knows the transcript.
  clarification: { label: 'Edit my question', refillLast: true },
};

export default function AllyChat() {
  const { user, showToast } = useApp();
  const location = useLocation();
  const navigate = useNavigate();
  const [histOpen, setHistOpen] = useState(false);
  const [activeConv, setActiveConv] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [typing, setTyping] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [limitNotice, setLimitNotice] = useState(null);
  const [sending, setSending] = useState(false);
  // A failed send is not something Ally said, so it does not belong in the
  // transcript as an Ally bubble -- it is a status about the app.
  const [sendError, setSendError] = useState(null);
  const [loadingThread, setLoadingThread] = useState(false);
  const [threadError, setThreadError] = useState(false);
  const [plan, setPlan] = useState(null);
  const [uploading, setUploading] = useState(false);
  /* What is attached to THIS conversation right now. A transient toast was
     the only signal before, so once it faded a founder had no way to tell
     whether their file was actually attached -- or, after a reload, that it
     still was. Server-sourced on open so it survives a refresh. */
  const [attachments, setAttachments] = useState([]);
  /* Files already delivered, keyed by the message they went out with, so
     they render inside that bubble instead of sitting in the composer
     forever. Rebuilt from the server on open (AttachmentResponse carries
     message_id), so it survives a reload. */
  const [sentAttachments, setSentAttachments] = useState({});
  /* Paging state for the transcript. `olderOffset` is where the loaded window
     starts in the whole conversation; null means there is nothing above it. */
  const [olderOffset, setOlderOffset] = useState(null);
  const [loadingOlder, setLoadingOlder] = useState(false);
  /* Paging state for the history panel, same idea one level up. */
  const [convTotal, setConvTotal] = useState(0);
  const [loadingMoreConvs, setLoadingMoreConvs] = useState(false);
  /* Actionable suggestions for the open conversation, generated server-side
     right after the last turn. */
  const [suggestions, setSuggestions] = useState([]);
  /* Which history row has its menu open, and which is mid-rename. */
  const [menuFor, setMenuFor] = useState(null);
  const [renamingId, setRenamingId] = useState(null);
  const [renameDraft, setRenameDraft] = useState('');
  const scrollRef = useRef(null);
  const taRef = useRef(null);
  const fileInputRef = useRef(null);
  // { text, requestId } of the last send() that failed, or null. Live-
  // confirmed a send can succeed fully server-side (message saved, Ally
  // replied) while the client's own timeout fires first and tells the
  // founder to resend -- if they do, this lets the retry reuse the SAME
  // request_id instead of minting a new one, so the backend's idempotent-
  // replay path (ChatExecutionService.send_message) recognises it as the
  // same turn rather than running the LLM call a second time. Only reused
  // when the resent text is unchanged; an edited retry is a new message.
  const lastFailedRef = useRef(null);

  /* Set just before older messages are prepended. Without it, growing the
     transcript upwards trips the scroll-to-bottom below and throws the founder
     back to the newest message -- the precise opposite of what "load older"
     was clicked for. Holds the scrollHeight from before the prepend, so the
     view can be pinned to the same message afterwards. */
  const pinScrollRef = useRef(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    if (pinScrollRef.current !== null) {
      // Keep the founder looking at the same line: everything added went in
      // above them, so their position moved down by exactly that much.
      el.scrollTop = el.scrollHeight - pinScrollRef.current;
      pinScrollRef.current = null;
      return;
    }
    el.scrollTop = el.scrollHeight;
  }, [messages, typing]);

  // A page like Your Vision can hand off here with a message drafted from
  // the founder's own words (see VisionPage's talkAboutTerritory). It only
  // ever lands in the composer for them to review or edit -- never sent on
  // their behalf. Consumed once via `replace`, so refreshing this page (or
  // coming back to it later) doesn't keep re-dropping the same text in.
  useEffect(() => {
    const prefill = location.state?.prefill;
    if (!prefill) return;
    setInput(prefill);
    navigate(location.pathname, { replace: true, state: {} });
    // Give the textarea a beat to mount/receive the value before resizing
    // and focusing it -- sizeTa() reads scrollHeight off the live element.
    requestAnimationFrame(() => {
      sizeTa();
      taRef.current?.focus();
    });
  }, [location.state, location.pathname, navigate]);

  // Conversations are server-owned, so history survives a reload.
  useEffect(() => {
    listConversations()
      .then(res => {
        setConversations(res.conversations ?? []);
        setConvTotal(res.total ?? (res.conversations ?? []).length);
      })
      .catch(() => { setConversations([]); setConvTotal(0); });
    // Real allowance, so the counter reflects the founder's actual plan rather
    // than an invented cap.
    getMyPlan().then(setPlan).catch(() => setPlan(null));
  }, []);

  const openConversation = async (id) => {
    setHistOpen(false);
    setMenuFor(null);
    setActiveConv(id);
    setLoadingThread(true);
    setThreadError(false);
    setSendError(null);
    setSuggestions([]);
    setOlderOffset(null);
    try {
      const conv = await getConversationMessages(id);
      setMessages((conv.messages ?? []).map(toUiMessage));
      // Only meaningful when there is something above this page.
      setOlderOffset(conv.has_more ? (conv.offset ?? 0) : null);

      // Opening it is what makes it read. Best-effort and unawaited: a failed
      // read-marker must not stop the transcript from rendering.
      markConversationRead(id)
        .then(() => setConversations(prev => prev.map(
          c => (c.conversation_id === id ? { ...c, unread_count: 0 } : c))))
        .catch(() => {});
      refreshSuggestions(id);
      // Best-effort: a thread still opens fine if this read fails, it just
      // shows no chips rather than blocking the transcript on them.
      listAttachments(id)
        .then((res) => {
          const all = res.attachments ?? [];
          // Unlinked = uploaded but never sent (the founder attached, then
          // navigated away), so it belongs back in the composer. Linked =
          // already delivered, and belongs to its message.
          setAttachments(all.filter(a => !a.message_id));
          setSentAttachments(all.reduce((acc, a) => {
            if (a.message_id) (acc[a.message_id] ||= []).push(a);
            return acc;
          }, {}));
        })
        .catch(() => { setAttachments([]); setSentAttachments({}); });
    } catch {
      /* This used to just setMessages([]), which rendered the "New
         conversation" hero -- so a thread that failed to load was
         indistinguishable from one that had never been started, and the
         founder's history looked like it had silently vanished. */
      setMessages([]);
      setThreadError(true);
    } finally {
      setLoadingThread(false);
    }
  };

  const sizeTa = () => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
  };

  /* Suggestions are generated server-side as part of the last chat turn, so
     this only reads what is already there -- it never asks for new ones.
     Filtered to the types that have an action (see SUGGESTION_ACTIONS) and
     capped, because a wall of chips under every answer is its own noise. */
  const refreshSuggestions = (conversationId) => {
    if (!conversationId) return;
    getSuggestions(conversationId)
      .then(res => setSuggestions(
        (res.suggestions ?? [])
          .filter(s => s.status === 'active' && SUGGESTION_ACTIONS[s.suggestion_type])
          .slice(0, 3)))
      .catch(() => setSuggestions([]));
  };

  const handleSuggestion = (s) => {
    const action = SUGGESTION_ACTIONS[s.suggestion_type];
    if (!action) return;
    // Acting on it IS the accept signal -- the founder should not have to rate
    // a suggestion as well as follow it.
    sendSuggestionFeedback(s.suggestion_id, 'accepted').catch(() => {});
    setSuggestions(prev => prev.filter(x => x.suggestion_id !== s.suggestion_id));

    if (action.go) { navigate(action.go); return; }
    if (action.refillLast) {
      const lastMine = [...messages].reverse().find(m => m.role === 'me');
      setInput(lastMine?.text ?? '');
      requestAnimationFrame(() => { sizeTa(); taRef.current?.focus(); });
      return;
    }
    if (action.ask) send(action.ask(s));
  };

  const dismissSuggestion = (s) => {
    setSuggestions(prev => prev.filter(x => x.suggestion_id !== s.suggestion_id));
    sendSuggestionFeedback(s.suggestion_id, 'dismissed').catch(() => {});
  };

  /* Walk backwards through a long transcript. The open call loads the newest
     page; this loads the page above whatever is currently loaded. */
  const loadOlder = async () => {
    if (olderOffset === null || loadingOlder || !activeConv) return;
    setLoadingOlder(true);
    const nextOffset = Math.max(0, olderOffset - MESSAGE_PAGE);
    try {
      const page = await getConversationMessages(activeConv, {
        limit: olderOffset - nextOffset, offset: nextOffset,
      });
      // Pin the view before the prepend so it does not jump -- see pinScrollRef.
      pinScrollRef.current = scrollRef.current?.scrollHeight ?? null;
      setMessages(prev => [...(page.messages ?? []).map(toUiMessage), ...prev]);
      setOlderOffset(nextOffset > 0 ? nextOffset : null);
    } catch {
      showToast("Couldn't load the earlier messages — please try again.");
    } finally {
      setLoadingOlder(false);
    }
  };

  const loadMoreConversations = async () => {
    if (loadingMoreConvs) return;
    setLoadingMoreConvs(true);
    try {
      const res = await listConversations(false, {
        limit: CONVERSATION_PAGE, offset: conversations.length,
      });
      // Merge by id rather than concatenating: a conversation whose activity
      // moved it onto an earlier page between the two requests would otherwise
      // appear twice, with duplicate React keys.
      setConversations(prev => {
        const seen = new Set(prev.map(c => c.conversation_id));
        return [...prev, ...(res.conversations ?? []).filter(c => !seen.has(c.conversation_id))];
      });
      setConvTotal(res.total ?? convTotal);
    } catch {
      showToast("Couldn't load more conversations — please try again.");
    } finally {
      setLoadingMoreConvs(false);
    }
  };

  const beginRename = (conv) => {
    setMenuFor(null);
    setRenamingId(conv.conversation_id);
    setRenameDraft(conv.title || '');
  };

  const commitRename = async (conversationId) => {
    const title = renameDraft.trim();
    setRenamingId(null);
    const previous = conversations.find(c => c.conversation_id === conversationId)?.title;
    if (!title || title === previous) return;      // nothing to do, and "" is a 422
    setConversations(prev => prev.map(
      c => (c.conversation_id === conversationId ? { ...c, title } : c)));
    try {
      await renameConversation(conversationId, title);
    } catch (err) {
      setConversations(prev => prev.map(
        c => (c.conversation_id === conversationId ? { ...c, title: previous } : c)));
      showToast(err instanceof ApiError ? err.detail : "Couldn't rename that conversation.");
    }
  };

  const handleDelete = async (conv) => {
    setMenuFor(null);
    // Deliberately a confirm: this is the one destructive action in the chat,
    // it takes a thread out of the founder's history for good, and there is no
    // undo anywhere in this UI to fall back on.
    if (!window.confirm(`Delete "${conv.title || 'this conversation'}"? This can't be undone.`)) return;
    const id = conv.conversation_id;
    const snapshot = conversations;
    setConversations(prev => prev.filter(c => c.conversation_id !== id));
    setConvTotal(t => Math.max(0, t - 1));
    if (activeConv === id) startNew();
    try {
      await deleteConversation(id);
    } catch (err) {
      setConversations(snapshot);
      setConvTotal(t => t + 1);
      showToast(err instanceof ApiError ? err.detail : "Couldn't delete that conversation.");
    }
  };

  /**
   * Send over SSE, rendering Ally's answer into the transcript as it is written.
   *
   * Returns the same shape the blocking send does ({ ok, answer, error, ... })
   * so the caller's success/failure handling is identical either way -- with
   * one extra flag, `streamed`, telling it the bubble is already on screen and
   * must not be appended a second time.
   *
   * On failure it takes its own placeholder bubble back out before returning,
   * so a stream that dies never leaves an empty bubble sitting in the
   * transcript looking like Ally said nothing.
   */
  const streamReply = async ({ text, convId, requestId }) => {
    let received = '';
    let placed = false;

    const placeBubble = () => {
      placed = true;
      setTyping(false);          // the answer is arriving; the dots have done their job
      setMessages(prev => [...prev, { role: 'ally', text: '', time: 'Just now', streaming: true }]);
    };
    const dropBubble = () => {
      if (!placed) return;
      setMessages(prev => (prev[prev.length - 1]?.streaming ? prev.slice(0, -1) : prev));
      placed = false;
    };

    let summary = null;
    try {
      await streamMessage({ message: text, conversationId: convId, requestId }, {
        onToken: (chunk) => {
          if (!chunk) return;
          if (!placed) placeBubble();
          received += chunk;
          setMessages(prev => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.streaming) next[next.length - 1] = { ...last, text: received };
            return next;
          });
        },
        onDone: (s) => { summary = s; },
        onError: (message) => { summary = { ok: false, error: message || 'stream_error' }; },
      });
    } catch (err) {
      dropBubble();
      /* Fall back to the blocking endpoint when the stream never produced a
         token and the failure was not the plan gate refusing (which would
         refuse identically) or the network being down (which would fail
         identically). That covers the realistic breakage -- a proxy or a
         deployment where SSE does not survive the hop -- without turning one
         rejected send into two.

         The SAME request_id is reused, so if the stream actually did complete
         server-side before the connection broke, the backend recognises the
         replay and returns that turn instead of running the model twice. */
      const isLimit = !!explainLimit(err);
      const isNetwork = err instanceof ApiError && err.isNetwork;
      if (received || isLimit || isNetwork) throw err;
      return sendMessage({ message: text, conversationId: convId, requestId });
    }

    const answer = received.trim();
    if (!answer || summary?.ok === false) {
      dropBubble();
      return { ok: false, answer: '', error: summary?.error ?? '' };
    }
    // Clear the streaming flag so a later token from a subsequent send cannot
    // land in this bubble.
    setMessages(prev => {
      const next = [...prev];
      const last = next[next.length - 1];
      if (last?.streaming) next[next.length - 1] = { ...last, streaming: false };
      return next;
    });
    return { ok: true, answer, streamed: true, conversation_id: summary?.conversation_id };
  };

  const send = async (text) => {
    if (!text.trim() || sending) return;
    setLimitNotice(null);
    setSendError(null);
    // Last turn's suggestions are about last turn. Clearing them here rather
    // than when the new ones arrive means they never sit under a newer answer
    // pretending to be about it.
    setSuggestions([]);
    setMessages(prev => [...prev, { role: 'me', text, time: 'Just now' }]);
    setInput('');
    sizeTa();
    setTyping(true);
    setSending(true);

    // Reuse the failed attempt's own request_id when resending the SAME text
    // unchanged -- see lastFailedRef above. Anything else (first send, or the
    // founder edited the text before resending) is a genuinely new message.
    const failed = lastFailedRef.current;
    const requestId = failed && failed.text === text ? failed.requestId : crypto.randomUUID();
    // Snapshot before awaiting: these are the files this send is delivering.
    const pending = attachments;

    try {
      // Create the conversation lazily, on the first message, so an abandoned
      // "New chat" click never leaves an empty thread in the founder's history.
      let convId = activeConv;
      if (!convId) {
        const created = await createConversation(text.slice(0, 60));
        convId = created.conversation_id;
        setActiveConv(convId);
        setConversations(prev => [created, ...prev]);
      }

      /* Streamed unless this send is delivering files.
         The stream's closing `summary` event carries conversation_id and
         assistant_message_id but no user_message_id, and linking an attachment
         needs exactly that -- so a send with attachments takes the blocking
         path, where the id comes back in the response. Adding the field to the
         stream would mean changing the frozen streaming layer for the rarer
         case; this keeps the common one fast and the rarer one correct. */
      const res = (USE_STREAMING && !pending.length)
        ? await streamReply({ text, convId, requestId })
        : await sendMessage({ message: text, conversationId: convId, requestId });
      lastFailedRef.current = null;

      /* Hand the pending files to the message that just went out, so they
         stop sitting in the composer looking un-sent. Linking is persisted
         (message_id on the row) purely so a reload can put them back in the
         right bubble -- it does not change what the LLM sees, which stays
         conversation-wide as before. Best-effort: if the link call fails the
         chip still moves locally, because the file genuinely was sent. */
      const mid = res.user_message_id;
      if (mid) {
        // The optimistic bubble was pushed before the server had assigned an
        // id; adopt the real one so anything keyed by message id lands on it.
        setMessages(prev => {
          const next = [...prev];
          for (let i = next.length - 1; i >= 0; i--) {
            if (next[i].role === 'me' && !next[i].id) { next[i] = { ...next[i], id: mid }; break; }
          }
          return next;
        });
      }
      if (pending.length) {
        setAttachments([]);
        if (mid) {
          setSentAttachments(prev => ({ ...prev, [mid]: pending }));
          Promise.all(pending.map(a =>
            linkAttachmentToMessage(a.attachment_id, mid).catch(() => {})));
        }
      }

      // The API answers with `ok: false` and an empty `answer` when it cannot
      // ground a reply -- most often because this founder has no diagnosis yet, so
      // there is no root-cause context to reason from. Rendering the empty string
      // would leave a blank bubble and look broken; say what actually happened.
      const reply = (res.answer ?? '').trim();
      if (res.ok === false || !reply) {
        const needsDiagnosis = String(res.error || '').includes('executive_summary')
          || String(res.error || '').includes('top_root_causes');
        setMessages(prev => [...prev, {
          role: 'ally', time: 'Just now',
          text: needsDiagnosis
            ? "I can't answer properly yet — I ground every reply in your diagnosis, and you haven't completed one. Run the Founder Diagnosis and I'll have real context to work from."
            : "I couldn't put together a grounded answer just then. Try rephrasing, or ask me something else.",
        }]);
      } else if (!res.streamed) {
        // A streamed reply is already in the transcript -- it was rendered
        // token by token as it arrived. Appending here would show it twice.
        setMessages(prev => [...prev, {
          role: 'ally', text: reply, time: 'Just now',
          confidence: res.confidence != null ? Math.round(res.confidence * 100) : undefined,
        }]);
      }

      /* Suggestions are produced as part of the turn that just finished, so
         this is the moment they exist. Unawaited: they are an extra, and the
         founder already has their answer. */
      refreshSuggestions(convId);
    } catch (err) {
      /* The message never reached the server, so it must not stay in the
         transcript looking sent. Take it back out and put the text back in the
         box -- the copy already promised "your message wasn't lost", while the
         code had cleared it and left them to retype it. */
      setMessages(prev => {
        const last = prev[prev.length - 1];
        return last?.role === 'me' && last.text === text ? prev.slice(0, -1) : prev;
      });
      setInput(text);

      // 403/402/429 are the plan gate doing its job -- show what it means and
      // what to do about it, rather than a generic failure.
      const limit = explainLimit(err);
      const isNetwork = err instanceof ApiError && err.isNetwork;
      if (limit) {
        setLimitNotice(limit);
      } else {
        setSendError(
          isNetwork
            ? "Couldn't reach the server — check your connection and send again."
            : "Couldn't send that just now. Your message is still here — try again.",
        );
      }
      // Only a network/timeout failure means the server never told us the
      // outcome -- it may have completed the turn anyway (live-confirmed:
      // slow-but-successful sends can outlast the client timeout). A plan-
      // gate rejection or another real error response means it definitely
      // did NOT complete, so a resend there is unambiguously a fresh attempt.
      lastFailedRef.current = isNetwork ? { text, requestId } : null;
    } finally {
      setTyping(false);
      setSending(false);
    }
  };

  // A conversation is created lazily by the first send() call. Attachments need
  // an existing conversation_id up front, so this creates one on demand if there
  // isn't one yet (e.g. attaching a file before typing anything).
  const ensureConversation = async () => {
    if (activeConv) return activeConv;
    const created = await createConversation();
    setActiveConv(created.conversation_id);
    setConversations(prev => [created, ...prev]);
    return created.conversation_id;
  };

  const handleAttachClick = () => fileInputRef.current?.click();

  const handleFileSelected = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = ''; // allow re-selecting the same file later
    if (!file) return;
    setUploading(true);
    try {
      const conversationId = await ensureConversation();
      const form = new FormData();
      form.append('conversation_id', conversationId);
      form.append('file', file);
      const created = await post('/chat/attachments', form,
                                 { headers: { 'Content-Type': undefined } });
      setAttachments(prev => [...prev, created]);
      showToast(`Attached "${file.name}" — mention it in your message and I'll take it into account.`);
    } catch (err) {
      showToast(err instanceof ApiError ? err.detail : 'Could not attach that file — please try again.');
    } finally {
      setUploading(false);
    }
  };

  const handleRemoveAttachment = async (att) => {
    // Optimistic: the chip disappears on click, and comes back if the
    // request fails, so removing never feels laggy but never lies either.
    setAttachments(prev => prev.filter(a => a.attachment_id !== att.attachment_id));
    try {
      await removeAttachment(att.attachment_id);
    } catch (err) {
      setAttachments(prev => [...prev, att]);
      /* Putting the chip back on screen is not the whole rollback. If the
         archive actually landed and only its response was lost -- a timeout, a
         dropped connection -- the file would be visible to the founder and
         invisible to Ally, which is the worst of both. Un-archiving makes the
         two agree. Best-effort by nature: if it fails, the chip is still the
         optimistic one and a reload will show the truth. */
      restoreAttachment(att.attachment_id).catch(() => {});
      showToast(err instanceof ApiError ? err.detail : 'Could not remove that file — please try again.');
    }
  };

  // PlanGate's usePlan() gives a lightweight `{plan, loading}` read used only for
  // the voice-input gate; `plan` (above) is the fuller /plans/me object the usage
  // bar needs. Two different shapes for two different jobs, both real API-backed.
  const { plan: entitlementPlan } = usePlanGateEntitlements();
  const canUseVoice = !entitlementPlan || can(entitlementPlan, FEATURES.VOICE_CHAT);
  const upgradeMessage = 'Voice chat is a paid-plan feature. Voice input is available for free during your diagnosis.';

  const voice = useVoiceInput({
    context: 'chat',
    onTranscribed: (text) => setInput(prev => (prev ? `${prev} ${text}` : text)),
    onUpgradeRequired: () => showToast(upgradeMessage),
    onError: () => showToast('Could not access the microphone — check your browser permissions.'),
  });

  /* Re-measure once React has actually rendered the new value AND the field
     is back on screen. sizeTa() reads scrollHeight, so calling it inline
     right after setInput() measured the PREVIOUS content -- and while
     voice.status !== 'idle' the textarea is display:none (the meter has its
     slot), where scrollHeight reads 0, collapsing the box and clipping the
     transcript that had just been dictated into it. */
  useEffect(() => {
    if (voice.status === 'idle') sizeTa();
  }, [input, voice.status]);

  const handleMicClick = () => {
    if (!canUseVoice) {
      showToast(upgradeMessage);
      return;
    }
    voice.toggle();
  };

  const dailyLimit = plan?.daily_token_limit ?? 0;
  const dailyLeft = plan?.daily_tokens_remaining ?? 0;
  const usedPct = dailyLimit ? Math.min(100, Math.round(((dailyLimit - dailyLeft) / dailyLimit) * 100)) : 0;
  const near = dailyLimit > 0 && dailyLeft <= dailyLimit * 0.15;
  const isEmpty = messages.length === 0;
  const firstName = (user?.name || '').split(' ')[0] || 'there';

  const startNew = () => {
    setActiveConv(null);
    setMessages([]);
    // Attachments belong to a conversation, so they must not carry over into
    // a new one -- leaving them would show files that this thread cannot use.
    setAttachments([]);
    setSentAttachments({});
    setSuggestions([]);
    setOlderOffset(null);
    setMenuFor(null);
    setHistOpen(false);
  };

  return (
    <div className={`ac${histOpen ? ' open' : ''}`} style={{ minHeight: 'calc(100vh - 64px)' }}>

      {/* ── History slide-over ── */}
      <div className="ac-hist">
        <div className="ac-hist-top">
          <div className="h">History</div>
          <button className="ac-hist-x" type="button" aria-label="Close conversation history" onClick={() => setHistOpen(false)}>
            <svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <button className="ac-new" onClick={startNew}>
          <svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          New conversation
        </button>
        <div className="ac-hist-lbl">Recent conversations</div>
        <div className="ac-list">
          {/* Zero conversations rendered a blank panel under the heading, which
              reads as a loading failure rather than a new account. */}
          {conversations.length === 0 && (
            <p className="ac-status">No conversations yet. Ask Ally something and it'll appear here.</p>
          )}
          {conversations.map(conv => (
            // Was `conv.id`, a field that doesn't exist on this shape (only
            // `conversation_id` does) -- so the key was always undefined (React's
            // "unique key" warning) and this highlight never lit up, ever, since
            // `activeConv === undefined` is only true before any conversation opens.
            <div key={conv.conversation_id} className="ac-row">
              {renamingId === conv.conversation_id ? (
                /* Rename in place. Enter commits, Escape abandons, and losing
                   focus commits too -- clicking away from a field you have just
                   typed into should not throw the typing away. */
                <input
                  className="ac-rename"
                  autoFocus
                  value={renameDraft}
                  maxLength={200}
                  aria-label="Conversation title"
                  onChange={(e) => setRenameDraft(e.target.value)}
                  onBlur={() => commitRename(conv.conversation_id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') { e.preventDefault(); commitRename(conv.conversation_id); }
                    if (e.key === 'Escape') { e.preventDefault(); setRenamingId(null); }
                  }}
                />
              ) : (
                <>
                  <button className={`ac-item${activeConv === conv.conversation_id ? ' on' : ''}`}
                    onClick={() => openConversation(conv.conversation_id)}>
                    <div className="ai-ic">
                      <svg viewBox="0 0 24 24"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
                    </div>
                    <div className="ai-body">
                      {/* createConversation() with no title leaves this null, which
                          rendered a blank row you could click but not identify. */}
                      <div className="ai-t">{conv.title || 'Untitled conversation'}</div>
                      <div className="ai-w">{conv.message_count ?? 0} msgs</div>
                    </div>
                    {/* A dot, not the number. The count is one per assistant
                        message and nothing cleared it until this release, so
                        existing rows carry inflated totals -- "you have not seen
                        this" is true where "you have 47 unread" is not. */}
                    {conv.unread_count > 0 && activeConv !== conv.conversation_id && (
                      <span className="ac-unread" aria-label="Unread reply" />
                    )}
                  </button>
                  <button
                    className="ac-more"
                    type="button"
                    aria-label={`Options for ${conv.title || 'this conversation'}`}
                    aria-expanded={menuFor === conv.conversation_id}
                    onClick={() => setMenuFor(m => (m === conv.conversation_id ? null : conv.conversation_id))}
                  >
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <circle cx="12" cy="5" r="1.6" /><circle cx="12" cy="12" r="1.6" /><circle cx="12" cy="19" r="1.6" />
                    </svg>
                  </button>
                  {menuFor === conv.conversation_id && (
                    <div className="ac-rowmenu" role="menu">
                      <button type="button" role="menuitem" onClick={() => beginRename(conv)}>Rename</button>
                      <button type="button" role="menuitem" className="danger" onClick={() => handleDelete(conv)}>Delete</button>
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
          {/* Only offered when there is genuinely something more to load --
              `total` is how many exist, not how many came back. */}
          {conversations.length < convTotal && (
            <button className="ac-loadmore" type="button" onClick={loadMoreConversations} disabled={loadingMoreConvs}>
              {loadingMoreConvs ? 'Loading…' : `Load older conversations (${convTotal - conversations.length} more)`}
            </button>
          )}
        </div>
      </div>

      {/* ── Scrim ── */}
      <div className="ac-scrim" onClick={() => setHistOpen(false)} />

      {/* ── Main area ── */}
      <div className="ac-main">
        {/* Bar */}
        <div className="ac-bar">
          <button className="ac-menu" type="button" aria-label="Conversation history" aria-expanded={histOpen} onClick={() => setHistOpen(o => !o)} title="Conversations">
            <svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/></svg>
          </button>
          <div className="ac-ttl">
            <div className="t">{isEmpty ? 'New conversation' : (conversations.find(c => c.conversation_id === activeConv)?.title || 'Conversation')}</div>
            <div className="s">General consultation · always on</div>
          </div>
          <button className="ac-barnew" type="button" aria-label="Start a new conversation" onClick={startNew}>
            <svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            New
          </button>
        </div>

        {/* Scroll area */}
        <div className="ac-scroll" ref={scrollRef} role="log" aria-live="polite" aria-label="Conversation with Ally">
          {limitNotice && (
            <div className="ac-limit-notice" role="alert" style={{
              margin: '12px 16px', padding: '12px 14px', borderRadius: 10,
              background: '#fffbeb', border: '1px solid #fde68a', color: '#92400e',
              fontSize: 13, lineHeight: 1.55,
            }}>
              <strong>{limitNotice.title}.</strong> {limitNotice.message}{' '}
              {limitNotice.kind !== 'wait' && (
                <a href="/app/billing" style={{ color: '#92400e', fontWeight: 700 }}>
                  See plans
                </a>
              )}
            </div>
          )}

          {loadingThread ? (
            <p className="ac-status" role="status">Loading this conversation…</p>
          ) : threadError ? (
            <div className="ac-status" role="alert">
              <p>That conversation didn't load. It's still there — this was a connection problem.</p>
              <button className="btn btn-ghost" type="button" onClick={() => openConversation(activeConv)}>
                Try again
              </button>
            </div>
          ) : isEmpty ? (
            <div className="ac-empty">
              <div className="ac-av"><img src="/ally-logo-mark.png" alt="" /></div>
              <h2>{greetingNow()}, <em>{firstName}</em>. How can I help?</h2>
              <p className="ac-lede">Ask me anything — marketing, sales, hiring, fundraising, pricing, growth or strategy. I'm your always-on thinking partner, no assessment required.</p>
            </div>
          ) : (
            <>
              {/* A conversation opens on its newest page; this walks upwards.
                  Only rendered when there is actually something above. */}
              {olderOffset !== null && (
                <button className="ac-loadmore" type="button" onClick={loadOlder} disabled={loadingOlder}>
                  {loadingOlder ? 'Loading earlier messages…' : 'Load earlier messages'}
                </button>
              )}
              {messages.map((m, i) => (
                <div key={i} className={`msg ${m.role}`}>
                  {/* The fallback was 'RV' -- the mock founder's initials -- so
                      a founder whose name hadn't loaded was shown someone
                      else's monogram. */}
                  <div className={`m-av ${m.role}`} aria-hidden="true">
                    {m.role === 'ally'
                      ? <img src="/ally-logo-mark.png" alt="" />
                      : (user?.initials || firstName || '?').charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <div className="bubble">
                      {m.role === 'ally' ? <Markdown>{m.text}</Markdown> : m.text}
                    </div>
                    {/* Files delivered with this turn -- read-only here (the
                        message is already sent), so no remove control. */}
                    {(sentAttachments[m.id] || []).length > 0 && (
                      <div className="msg-attachments">
                        {sentAttachments[m.id].map((a) => (
                          <span className="ac-chip is-sent" key={a.attachment_id}>
                            <svg viewBox="0 0 24 24" aria-hidden="true">
                              <path d="M21.4 11.05 12.25 20.2a5.5 5.5 0 01-7.78-7.78l9.19-9.19a3.5 3.5 0 114.95 4.95l-9.2 9.19a1.5 1.5 0 01-2.12-2.12l8.49-8.49" />
                            </svg>
                            <span className="ac-chip-name" title={a.filename}>{a.filename}</span>
                          </span>
                        ))}
                      </div>
                    )}
                    {m.confidence && (
                      <ConfBar pct={m.confidence} />
                    )}
                    <div className="m-meta">{m.time}</div>
                  </div>
                </div>
              ))}
              {typing && (
                <div className="typing">
                  <div className="m-av ally"><img src="/ally-logo-mark.png" alt="" /></div>
                  <div className="bubble">
                    <div className="td">
                      <span /><span /><span />
                    </div>
                  </div>
                </div>
              )}
              {/* What to do next, generated as part of the turn that just
                  finished. Only ones with an action reach here -- see
                  SUGGESTION_ACTIONS -- and never while Ally is still writing,
                  which would be suggesting a next step before the current one
                  has landed. */}
              {!typing && !sending && suggestions.length > 0 && (
                <div className="ac-suggestions" aria-label="Suggested next steps">
                  {suggestions.map(s => (
                    <span className="ac-sugg" key={s.suggestion_id}>
                      <button type="button" className="ac-sugg-go" onClick={() => handleSuggestion(s)}>
                        {SUGGESTION_ACTIONS[s.suggestion_type].label}
                        <em>{s.title}</em>
                      </button>
                      <button
                        type="button"
                        className="ac-sugg-x"
                        aria-label={`Dismiss "${s.title}"`}
                        onClick={() => dismissSuggestion(s)}
                      >
                        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12" /></svg>
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        {/* Input */}
        <div className="ac-input">
          {sendError && (
            <p className="ac-senderror" role="alert">{sendError}</p>
          )}
          {/* When /plans/me fails, plan is null and the meter used to render an
              empty bar labelled "Usage" -- identical to a healthy account with
              nothing spent. Say we don't know instead. */}
          <div style={{ maxWidth: 800, margin: '0 auto 8px', textAlign: 'center' }}>
            <span className={`ac-remain${near ? ' near' : ''}`}>
              <span>
                {plan
                  ? `${dailyLeft.toLocaleString('en-IN')} of ${dailyLimit.toLocaleString('en-IN')} tokens left today`
                  : 'Usage unavailable'}
              </span>
              {plan && <span className="arm-bar"><i style={{ width: `${usedPct}%` }} /></span>}
            </span>
          </div>
          {/* Persistent proof of what is attached. The upload toast is
              transient, so once it faded there was no way to tell a file had
              attached at all -- or, after a reload, that it still was. */}
          {attachments.length > 0 && (
            <div className="ac-attachments" aria-label="Attached files">
              {attachments.map((a) => (
                <span className="ac-chip" key={a.attachment_id}>
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M21.4 11.05 12.25 20.2a5.5 5.5 0 01-7.78-7.78l9.19-9.19a3.5 3.5 0 114.95 4.95l-9.2 9.19a1.5 1.5 0 01-2.12-2.12l8.49-8.49" />
                  </svg>
                  <span className="ac-chip-name" title={a.filename}>{a.filename}</span>
                  <button
                    type="button"
                    className="ac-chip-x"
                    aria-label={`Remove ${a.filename}`}
                    onClick={() => handleRemoveAttachment(a)}
                  >
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M18 6 6 18M6 6l12 12" />
                    </svg>
                  </button>
                </span>
              ))}
            </div>
          )}
          <div className={`ci-row${voice.status !== 'idle' ? ' voice-live' : ''}`}>
            {voice.status !== 'idle' && (
              <VoiceBars
                getLevel={voice.getLevel}
                label={voice.status === 'transcribing' ? 'Transcribing…' : 'Listening…'}
              />
            )}
            {/* Documents only. Images upload happily and Ally cannot read a
                word of them -- LLMMessage.content is a plain string, so there
                is no way to send a picture to the model at all. Offering them
                in the picker produced the worst version of that: a successful
                upload, a file chip in the thread, and then an assistant that
                could not see it. Restore image types in the same change that
                makes the transport multimodal. */}
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.txt,.md,.csv,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown,text/csv"
              aria-label="Attach a document"
              tabIndex={-1}
              style={{ display: 'none' }}
              onChange={handleFileSelected}
            />
            <button
              className="ci-btn"
              type="button"
              title="Attach a document (PDF, Word, text, Markdown or CSV)"
              aria-label="Attach a document"
              disabled={uploading || sending}
              onClick={handleAttachClick}
            >
              <svg viewBox="0 0 24 24"><path d="M21.4 11.05 12.25 20.2a5.5 5.5 0 01-7.78-7.78l9.19-9.19a3.5 3.5 0 114.95 4.95l-9.2 9.19a1.5 1.5 0 01-2.12-2.12l8.49-8.49"/></svg>
            </button>
            <label className="sr-only" htmlFor="ac-input">Message Ally</label>
            <textarea
              id="ac-input"
              ref={taRef}
              rows={1}
              placeholder={sending ? 'Sending…' : 'Ask Ally anything about your business…'}
              value={input}
              disabled={sending}
              onChange={e => { setInput(e.target.value); sizeTa(); }}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input); } }}
            />
            <button
              className={`ci-btn mic${voice.status === 'recording' ? ' recording' : ''}`}
              type="button"
              title={canUseVoice ? 'Voice input' : 'Voice input (paid plan)'}
              aria-label={canUseVoice ? 'Voice input' : 'Voice input (paid plan)'}
              aria-pressed={voice.status === 'recording'}
              disabled={voice.status === 'transcribing' || sending}
              onClick={handleMicClick}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0014 0M12 18v3"/></svg>
            </button>
            {/* Was never disabled: send() silently returned while `sending`, so
                clicking again did nothing with nothing to show for it. */}
            <button
              className="ci-btn send"
              type="button"
              onClick={() => send(input)}
              title="Send"
              aria-label="Send message"
              disabled={sending || !input.trim()}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
            </button>
          </div>
          <p className="ci-hint">Ally is your always-on strategic partner for advice, brainstorming and daily founder questions · Enter to send</p>
        </div>
      </div>
    </div>
  );
}

function ConfBar({ pct }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) setTimeout(() => { if (ref.current) ref.current.style.width = `${pct}%`; }, 200);
  }, [pct]);
  return (
    <div className="conf">
      <div className="l">Confidence</div>
      <div className="bar"><i ref={ref} /></div>
      <div className="pct">{pct}%</div>
    </div>
  );
}
