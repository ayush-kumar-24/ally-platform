import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { searchFaqs } from '../data/faqs';
import { ApiError, getAccessToken } from '../services/api';
import { FEEDBACK, submitFeedback } from '../services/feedback';
import { askSupport } from '../services/support';
import { IconClose, IconMessageSquare, IconSend } from '../utils/icons';

/**
 * The help assistant that floats over every platform page.
 *
 * Help used to live only at /app/help, which meant a founder stuck on the
 * report or mid-diagnosis had to leave the thing they were stuck on to ask
 * about it -- and losing your place is exactly the moment you give up and
 * email instead. This puts the same answers one click away, in the shape
 * people expect to ask a question in: a conversation.
 *
 * It asks POST /support/ask, which matches the question against 277 published
 * help answers by meaning and composes a reply from the ones it picked and
 * nothing else. It cannot invent: when nothing fits, it says so and hands over
 * to a person rather than reaching for a plausible answer about billing or data
 * deletion.
 *
 * STILL NOT METERED, and that reason has not changed: Ally chat charges the
 * founder's daily token allowance, and spending it on "how do I upgrade" would
 * charge them for a question the product should answer for free. /support/ask
 * runs unmetered and is rate-limited per founder instead.
 *
 * data/faqs.js REMAINS, as the fallback. The content lives in a table loaded by
 * a SQL script rather than a migration, so a healthy deployment can be running
 * without it -- and the model can be down, and the request can time out. In any
 * of those cases `answerFor` answers from the local list, which is shorter and
 * keyword-matched but always there. A help widget showing an error is worse
 * than one quietly answering from sixteen entries.
 *
 * Hidden on /app/help itself, where it would sit on top of the same content.
 */

const PANEL_ID = 'help-assistant-panel';

const GREETING =
  "Hi — I'm Ally's help assistant. Ask me about your account, plans, the diagnosis or your data, and I'll find the answer.";

/* The four things people actually open help for, as one-tap starters. */
const STARTERS = [
  'How do I start a diagnosis?',
  'How do plans work?',
  'I forgot my password',
  'Can I delete my data?',
];

let seq = 0;
const nextId = () => `m${++seq}`;

/**
 * What the assistant replies to `text`.
 *
 * Returns the answer plus up to two other questions that also matched, offered
 * as follow-up chips -- a founder who types "report" means one of three things,
 * and guessing silently is worse than showing the choice.
 */
function answerFor(text) {
  const hits = searchFaqs(text);
  if (!hits.length) return { miss: true };
  return { faq: hits[0], related: hits.slice(1, 3) };
}

export default function HelpWidget() {
  const { showToast } = useApp();
  const navigate = useNavigate();
  const location = useLocation();

  const [open, setOpen] = useState(false);
  const [full, setFull] = useState(false);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState('');
  const [thinking, setThinking] = useState(false);

  const [composing, setComposing] = useState(false);
  const [supportMsg, setSupportMsg] = useState('');
  const [sending, setSending] = useState(false);

  const rootRef = useRef(null);
  const buttonRef = useRef(null);
  const inputRef = useRef(null);
  const composeRef = useRef(null);
  const feedRef = useRef(null);
  const replyTimer = useRef(null);

  const suggestions = useMemo(
    () => STARTERS.filter((s) => searchFaqs(s).length > 0),
    [],
  );

  /* Ask, and answer. Shared by the input and every chip.
   *
   * Asks the backend first: it matches against all 277 published help answers
   * by MEANING, using the same content the Help page reads, and composes a
   * reply from the answers it picked and nothing else. That is the difference
   * that matters here -- the local list below is a keyword match over 16
   * entries, so "I can't get in" finds nothing while the backend routes it
   * straight to the password answer.
   *
   * FALLS BACK TO THE LOCAL LIST, always. The content lives in a table loaded
   * by a SQL script rather than a migration, so a healthy deployment can be
   * running without it; the model can be unreachable; the request can time
   * out. None of that should leave a founder looking at an error inside the
   * help widget, of all places. `answerFor` stays exactly as it was and takes
   * over whenever the call does not come back usable.
   *
   * Not metered. Ally chat charges a founder's daily token allowance; charging
   * someone to ask how to cancel would be indefensible, so /support/ask is
   * unmetered and rate-limited per founder instead. */
  const ask = useCallback(async (raw) => {
    const text = raw.trim();
    if (!text) return;
    setDraft('');
    setMessages((prev) => [...prev, { id: nextId(), from: 'you', text }]);
    setThinking(true);
    clearTimeout(replyTimer.current);

    const localReply = () => {
      const result = answerFor(text);
      return result.miss
        ? { id: nextId(), from: 'bot', miss: true, text: "I don't have an answer for that one in the help guide. Send it to our team and we'll reply by email — or ask Ally, if it's about your business rather than the product." }
        : { id: nextId(), from: 'bot', text: result.faq.a, related: result.related.map((f) => f.q) };
    };

    let reply = null;
    try {
      const res = await askSupport(text);
      if (res?.answer) {
        reply = {
          id: nextId(),
          from: 'bot',
          text: res.answer,
          // `escalate` is the backend saying it would rather hand over than
          // guess. Rendered the same as a local miss, so the "message our
          // team" affordance appears in exactly the cases it should.
          miss: Boolean(res.escalate),
          links: res.links || [],
        };
      }
    } catch {
      /* offline, 5xx, timeout -- the local list answers instead */
    }

    setThinking(false);
    setMessages((prev) => [...prev, reply || localReply()]);
  }, []);

  // Close on Escape and on a click outside. Escape leaves full screen first,
  // so it never throws away the conversation in one keystroke.
  useEffect(() => {
    if (!open) return undefined;

    const onKeyDown = (e) => {
      if (e.key !== 'Escape') return;
      e.stopPropagation();
      if (full) { setFull(false); return; }
      setOpen(false);
      buttonRef.current?.focus();
    };
    const onPointerDown = (e) => {
      if (full) return; // full screen has its own backdrop
      if (!rootRef.current?.contains(e.target)) setOpen(false);
    };

    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('mousedown', onPointerDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.removeEventListener('mousedown', onPointerDown);
    };
  }, [open, full]);

  // Focus the right field a frame after the panel is laid out: focusing a node
  // that has not been laid out yet scrolls the page to the top on Safari.
  useEffect(() => {
    if (!open) return undefined;
    const id = requestAnimationFrame(() => {
      (composing ? composeRef : inputRef).current?.focus();
    });
    return () => cancelAnimationFrame(id);
  }, [open, composing, full]);

  // Keep the newest message in view.
  useEffect(() => {
    const feed = feedRef.current;
    if (feed) feed.scrollTop = feed.scrollHeight;
  }, [messages, thinking, open, full]);

  // Navigating away closes it; without this the panel stayed open over the
  // page it had just sent the founder to.
  useEffect(() => { setOpen(false); }, [location.pathname]);

  // A pending reply must not land after the panel is gone.
  useEffect(() => () => clearTimeout(replyTimer.current), []);

  // Full screen covers the page, so the page behind it must not scroll.
  useEffect(() => {
    if (!open || !full) return undefined;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = previous; };
  }, [open, full]);

  const openPanel = () => {
    setMessages([{ id: nextId(), from: 'bot', text: GREETING }]);
    setDraft('');
    setComposing(false);
    setSupportMsg('');
    setOpen(true);
  };

  const closePanel = () => {
    setOpen(false);
    setFull(false);
    setComposing(false);
    clearTimeout(replyTimer.current);
    setThinking(false);
  };

  const go = (path) => { closePanel(); navigate(path); };

  const sendSupport = async () => {
    const trimmed = supportMsg.trim();
    if (!trimmed || sending) return;
    setSending(true);
    try {
      // Same pipeline and the same tag as the Help page's own form, so both
      // land in one queue the team already watches.
      await submitFeedback({ type: FEEDBACK.GENERAL, comment: `[Support request] ${trimmed}` });
      showToast('Sent — our team will get back to you by email.');
      closePanel();
    } catch (err) {
      showToast(err instanceof ApiError ? err.detail : "Couldn't send that just now — your message is still here.");
    } finally {
      setSending(false);
    }
  };

  /* SIGNED-IN ONLY, enforced here rather than by where this happens to be
     mounted.

     Today the only mount is PlatformLayout, which is already behind
     RequireAuth, so this changes nothing. It is here so that stays true: if
     anyone ever drops <HelpWidget /> onto a public page -- a landing page, a
     pricing page, a marketing embed -- it renders nothing instead of quietly
     appearing to a visitor with no account.

     That is a product rule (2026-09-06: the assistant is not available before
     sign-in), and a rule that depends on nobody making a mistake in a different
     file is not enforced. It is also the honest technical position: /support/ask
     needs a founder session and is rate-limited per founder, so with no session
     this could not answer anything anyway -- it would just be a button that
     fails.

     Reads the token directly rather than through context, so it holds even if
     this is mounted outside AppProvider. */
  if (!getAccessToken()) return null;

  if (location.pathname === '/app/help') return null;

  const panel = (
    <div className={`hw-panel${full ? ' is-full' : ''}`} id={PANEL_ID} role="dialog" aria-label="Help assistant">
      <div className="hw-head">
        <div className="hw-head-id">
          <span className="hw-avatar" aria-hidden="true"><RobotIcon /></span>
          <div>
            <div className="hw-title">{composing ? 'Message support' : 'Help assistant'}</div>
            {/* The assistant subtitle used to read "Answers from Ally's help
                guide · N topics". Removed: a topic count is a fact about our
                content library, not about whether we can answer the question
                somebody is holding -- and it was actively misleading, because
                it counted whichever source happened to be answering. A founder
                who saw "16 topics" and then got "I don't have an answer" read
                the number as the reason, which it never was.

                `composing` keeps its subtitle: "we reply by email" tells
                someone about to type a message what happens next, which is
                worth the line. */}
            {composing && <div className="hw-sub">We reply by email</div>}
          </div>
        </div>
        <div className="hw-head-actions">
          <button
            className="hw-icon-btn"
            type="button"
            onClick={() => setFull((f) => !f)}
            aria-pressed={full}
            aria-label={full ? 'Exit full screen' : 'Open full screen'}
            title={full ? 'Exit full screen' : 'Full screen'}
          >
            {full ? <IconCollapse /> : <IconExpand />}
          </button>
          <button className="hw-icon-btn" type="button" onClick={closePanel} aria-label="Close help">
            <IconClose />
          </button>
        </div>
      </div>

      {composing ? (
        <div className="hw-compose">
          <p className="hw-note">
            Tell us what is happening and we will reply by email, usually within one working day.
          </p>
          <textarea
            ref={composeRef}
            className="hw-textarea"
            rows={full ? 10 : 5}
            placeholder="What went wrong, and what were you trying to do?"
            value={supportMsg}
            onChange={(e) => setSupportMsg(e.target.value)}
            disabled={sending}
          />
          <div className="hw-compose-actions">
            <button className="hw-link" type="button" onClick={() => setComposing(false)} disabled={sending}>
              Back to chat
            </button>
            <button className="hw-send-btn" type="button" onClick={sendSupport} disabled={sending || !supportMsg.trim()}>
              <IconSend />
              {sending ? 'Sending…' : 'Send'}
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="hw-feed" ref={feedRef}>
            {messages.map((m) => (
              <div key={m.id} className={`hw-msg is-${m.from}`}>
                {m.from === 'bot' && <span className="hw-msg-avatar" aria-hidden="true"><RobotIcon /></span>}
                <div className="hw-bubble">
                  <p>{m.text}</p>
                  {m.miss && (
                    <div className="hw-bubble-actions">
                      <button type="button" onClick={() => setComposing(true)}>Message support</button>
                      <button type="button" onClick={() => go('/app/ally-chat')}>Ask Ally</button>
                    </div>
                  )}
                  {m.related?.length > 0 && (
                    <div className="hw-related">
                      <span className="hw-related-lbl">Related</span>
                      {m.related.map((q) => (
                        <button key={q} className="hw-chip" type="button" onClick={() => ask(q)}>{q}</button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {thinking && (
              <div className="hw-msg is-bot">
                <span className="hw-msg-avatar" aria-hidden="true"><RobotIcon /></span>
                <div className="hw-bubble hw-typing" aria-label="Looking that up">
                  <i /><i /><i />
                </div>
              </div>
            )}

            {messages.length <= 1 && !thinking && (
              <div className="hw-starters">
                {suggestions.map((s) => (
                  <button key={s} className="hw-chip" type="button" onClick={() => ask(s)}>{s}</button>
                ))}
              </div>
            )}
          </div>

          <form
            className="hw-ask"
            onSubmit={(e) => { e.preventDefault(); ask(draft); }}
          >
            <input
              ref={inputRef}
              type="text"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask about your account, plans, data…"
              aria-label="Ask the help assistant"
            />
            <button type="submit" aria-label="Send" disabled={!draft.trim()}><IconSend /></button>
          </form>

          <div className="hw-foot">
            <button className="hw-link" type="button" onClick={() => setComposing(true)}>
              <IconMessageSquare aria-hidden="true" /> Message support
            </button>
            <button className="hw-link" type="button" onClick={() => go('/app/help')}>Full help page</button>
          </div>
        </>
      )}
    </div>
  );

  return (
    <>
      {open && full && <div className="hw-backdrop" onClick={closePanel} aria-hidden="true" />}
      <div className={`hw${full ? ' is-full' : ''}`} ref={rootRef}>
        {open && panel}
        {!(open && full) && (
          <button
            ref={buttonRef}
            className={`hw-fab${open ? ' is-open' : ''}`}
            type="button"
            onClick={() => (open ? closePanel() : openPanel())}
            aria-expanded={open}
            aria-controls={open ? PANEL_ID : undefined}
            aria-label={open ? 'Close help assistant' : 'Help assistant'}
          >
            {open ? <IconClose /> : <RobotIcon />}
            {!open && <span className="hw-fab-pulse" aria-hidden="true" />}
          </button>
        )}
      </div>
    </>
  );
}

/* ── Icons local to this component ──────────────────────────────────────────
   The robot is the assistant's identity: it is the button, the avatar on every
   reply, and the mark in the header. Drawn here rather than in utils/icons.jsx
   because nothing else in the product uses it. */

function RobotIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"
         strokeLinecap="round" strokeLinejoin="round" width="1em" height="1em" aria-hidden="true" {...props}>
      {/* antenna */}
      <path d="M12 2.5v2.4" />
      <circle cx="12" cy="1.9" r="1.05" fill="currentColor" stroke="none" />
      {/* head */}
      <rect x="4" y="5" width="16" height="12.5" rx="4.5" />
      {/* visor */}
      <rect x="6.9" y="8.2" width="10.2" height="5.4" rx="2.4" opacity=".45" />
      {/* eyes */}
      <circle cx="9.6" cy="10.9" r="1.15" fill="currentColor" stroke="none" />
      <circle cx="14.4" cy="10.9" r="1.15" fill="currentColor" stroke="none" />
      {/* side receivers */}
      <path d="M4 9.6H2.4M20 9.6h1.6" />
      {/* shoulders */}
      <path d="M7.5 17.5v1.2a2.5 2.5 0 0 0 2.5 2.5h4a2.5 2.5 0 0 0 2.5-2.5v-1.2" />
    </svg>
  );
}

function IconExpand(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
         strokeLinecap="round" strokeLinejoin="round" width="1em" height="1em" {...props}>
      <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
    </svg>
  );
}

function IconCollapse(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
         strokeLinecap="round" strokeLinejoin="round" width="1em" height="1em" {...props}>
      <path d="M4 14h6v6M20 10h-6V4M14 10l7-7M3 21l7-7" />
    </svg>
  );
}
