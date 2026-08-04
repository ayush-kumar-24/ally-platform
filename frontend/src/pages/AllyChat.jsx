import { useState, useRef, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import {
  createConversation,
  getConversation,
  listConversations,
  sendMessage,
  toUiMessage,
} from '../services/chat';
import { post, ApiError } from '../services/api';
import { useVoiceInput } from '../hooks/useVoiceInput';
import { usePlan as usePlanGateEntitlements } from '../components/PlanGate';
import { explainLimit, getMyPlan, can, FEATURES } from '../services/plans';

const PROMPT_CARDS = [
  { t: 'Help me increase revenue', s: 'Find the highest-leverage growth lever' },
  { t: 'Review my pricing', s: 'Pressure-test packaging & price points' },
  { t: 'Improve my sales strategy', s: 'Tighten the funnel and close rate' },
  { t: 'Validate my startup idea', s: 'Stress-test demand and assumptions' },
  { t: 'Help me hire my first employee', s: 'Scope the role and where to look' },
  { t: 'Create a GTM strategy', s: 'A go-to-market plan for launch' },
];

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
}

export default function AllyChat() {
  const { user, showToast } = useApp();
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
  const scrollRef = useRef(null);
  const taRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, typing]);

  // Conversations are server-owned, so history survives a reload.
  useEffect(() => {
    listConversations()
      .then(res => setConversations(res.conversations ?? []))
      .catch(() => setConversations([]));
    // Real allowance, so the counter reflects the founder's actual plan rather
    // than an invented cap.
    getMyPlan().then(setPlan).catch(() => setPlan(null));
  }, []);

  const openConversation = async (id) => {
    setHistOpen(false);
    setActiveConv(id);
    setLoadingThread(true);
    setThreadError(false);
    setSendError(null);
    try {
      const conv = await getConversation(id);
      setMessages((conv.messages ?? []).map(toUiMessage));
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

  const send = async (text) => {
    if (!text.trim() || sending) return;
    setLimitNotice(null);
    setSendError(null);
    setMessages(prev => [...prev, { role: 'me', text, time: 'Just now' }]);
    setInput('');
    sizeTa();
    setTyping(true);
    setSending(true);

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

      const res = await sendMessage({ message: text, conversationId: convId });

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
      } else {
        setMessages(prev => [...prev, {
          role: 'ally', text: reply, time: 'Just now',
          confidence: res.confidence != null ? Math.round(res.confidence * 100) : undefined,
        }]);
      }
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
      if (limit) {
        setLimitNotice(limit);
      } else {
        setSendError(
          err instanceof ApiError && err.isNetwork
            ? "Couldn't reach the server — check your connection and send again."
            : "Couldn't send that just now. Your message is still here — try again.",
        );
      }
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
      await post('/chat/attachments', form, { headers: { 'Content-Type': undefined } });
      showToast(`Attached "${file.name}" — mention it in your message and I'll take it into account.`);
    } catch (err) {
      showToast(err instanceof ApiError ? err.detail : 'Could not attach that file — please try again.');
    } finally {
      setUploading(false);
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
    onTranscribed: (text) => {
      setInput(prev => (prev ? `${prev} ${text}` : text));
      sizeTa();
    },
    onUpgradeRequired: () => showToast(upgradeMessage),
    onError: () => showToast('Could not access the microphone — check your browser permissions.'),
  });

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
            <button key={conv.conversation_id} className={`ac-item${activeConv === conv.conversation_id ? ' on' : ''}`}
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
            </button>
          ))}
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
              <div className="ac-av">✦</div>
              <h2>{greeting()}, <em>{firstName}</em>. How can I help?</h2>
              <p className="ac-lede">Ask me anything — marketing, sales, hiring, fundraising, pricing, growth or strategy. I'm your always-on thinking partner, no assessment required.</p>
              <div className="ac-cards">
                {PROMPT_CARDS.map((c, i) => (
                  /* Was a div with onClick: not focusable, not keyboard
                     operable, and announced as nothing to a screen reader. */
                  <button key={i} type="button" className="ac-pcard" onClick={() => send(c.t)}>
                    <div className="pc-t">{c.t}</div>
                    <div className="pc-s">{c.s}</div>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((m, i) => (
                <div key={i} className={`msg ${m.role}`}>
                  {/* The fallback was 'RV' -- the mock founder's initials -- so
                      a founder whose name hadn't loaded was shown someone
                      else's monogram. */}
                  <div className={`m-av ${m.role}`} aria-hidden="true">
                    {m.role === 'ally' ? '✦' : (user?.initials || firstName || '?').charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <div className="bubble">{m.text}</div>
                    {m.confidence && (
                      <ConfBar pct={m.confidence} />
                    )}
                    <div className="m-meta">{m.time}</div>
                  </div>
                </div>
              ))}
              {typing && (
                <div className="typing">
                  <div className="m-av ally">✦</div>
                  <div className="bubble">
                    <div className="td">
                      <span /><span /><span />
                    </div>
                  </div>
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
          <div className="ci-row">
            <input
              ref={fileInputRef}
              type="file"
              style={{ display: 'none' }}
              onChange={handleFileSelected}
            />
            <button
              className="ci-btn"
              type="button"
              title="Attach a file or image"
              aria-label="Attach a file or image"
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
              className={`ci-btn${voice.status === 'recording' ? ' recording' : ''}`}
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
