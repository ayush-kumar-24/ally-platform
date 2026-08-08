import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { normalise, resumeOrStart, submitAnswer } from '../services/diagnosis';
import { useVoiceInput } from '../hooks/useVoiceInput';
import FeedbackPrompt from '../components/FeedbackPrompt';
import { FEEDBACK } from '../services/feedback';

/* There was a filter bar here: All / Revenue / Strategy / Team / Operations /
   Finance / Market. It filtered nothing -- the click handler set state nothing
   ever read -- and none of those seven are real: the question bank uses
   seventeen categories ("Sales Execution", "Founder Psychology", "Target
   Customer & ICP" and so on), and the server decides what to ask next anyway.
   A founder cannot choose their own diagnosis path, so offering a chooser was
   a lie twice over. What's shown now is the category actually being asked. */

const clock = () => new Date().toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });

export default function DiagnosisChat() {
  const navigate = useNavigate();
  const { user, showToast } = useApp();
  const [answered, setAnswered] = useState(0);
  const [category, setCategory] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [question, setQuestion] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [kgVisible] = useState(true);
  const kgRef = useRef(null);
  const scrollRef = useRef(null);

  /* The draw timer had no cleanup and this effect runs on every message, so a
     new orphaned timeout was created for each one and any pending timers kept
     touching the DOM after unmount. */
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    if (!kgRef.current) return undefined;
    const t = setTimeout(() => kgRef.current?.classList.add('draw'), 800);
    return () => clearTimeout(t);
  }, [messages]);

  // Resume if a session is in progress, otherwise start one. The server owns the
  // progress, which is what makes closing the tab mid-diagnosis safe.
  useEffect(() => {
    let cancelled = false;
    resumeOrStart()
      .then((session) => {
        if (cancelled) return;
        setSessionId(session.sessionId);
        setQuestion(session.question);
        // Real counters, straight off the session the server already returns.
        setAnswered(session.answered ?? 0);
        setCategory(session.question?.category ?? null);
        if (session.question?.text) {
          setMessages([{ role: 'ally', text: session.question.text, time: clock() }]);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setMessages([{ role: 'ally', time: clock(),
            text: "I couldn't start your diagnosis just now. Please refresh to try again." }]);
        }
      });
    return () => { cancelled = true; };
  }, []);

  const answer = async (text) => {
    if (!text.trim() || busy || done) return;
    setMessages(prev => [...prev, { role: 'me', text, time: clock() }]);
    setInput('');
    setBusy(true);
    try {
      const res = await submitAnswer({ questionId: question?.id, answer: text });
      const state = normalise(res, true);
      const next = state.question;
      // The server's count is authoritative; only fall back to counting
      // locally if it didn't send one.
      if (typeof state.answered === 'number') setAnswered(state.answered);
      else setAnswered(a => a + 1);
      setCategory(next?.category ?? null);
      // Trust the explicit is_complete flag over "no next question": a transient
      // gap must not be mistaken for the end of the diagnosis.
      if (next?.text && !state.complete) {
        setQuestion(next);
        setMessages(prev => [...prev, { role: 'ally', time: clock(), text: next.text }]);
      } else {
        setDone(true);
        setMessages(prev => [...prev, {
          role: 'ally', time: clock(),
          text: 'That completes your diagnosis. I am building your report now.',
        }]);
        // The hand-off to the report interstitial now waits on the feedback
        // prompt below: the moment the diagnosis ends is the only point the
        // founder has just experienced it, and navigating 1.2s later would tear
        // the dialog off the screen. FeedbackPrompt resolves immediately when
        // there is nothing to ask, so this never strands anyone.
      }
    } catch {
      setMessages(prev => [...prev, {
        role: 'ally', time: clock(),
        text: "That didn't save. Your answer wasn't lost — try sending it again.",
      }]);
    } finally {
      setBusy(false);
    }
  };

  // Voice is free on every plan in diagnosis (only chat is plan-gated) -- no
  // canUseVoiceInChat check here, matching the product decision.
  const voice = useVoiceInput({
    context: 'diagnosis',
    onTranscribed: (text) => setInput(prev => (prev ? `${prev} ${text}` : text)),
    onError: () => showToast('Could not access the microphone — check your browser permissions.'),
  });

  const initials = (user?.initials || user?.name || '?').charAt(0).toUpperCase();

  /* The graph's "symptoms" are the founder's own answers, newest last -- the
     panel claims to connect what you say to the underlying cause, so it has to
     be built from what you actually said. It used to be three fixed labels
     ("Flat growth", "Rising spend", "Week-2 silence") rendered identically for
     everyone, before a single question had been answered. */
  const symptoms = messages
    .filter(m => m.role === 'me' && m.text.trim())
    .slice(-3)
    .map(m => (m.text.length > 22 ? `${m.text.slice(0, 21).trimEnd()}…` : m.text));

  return (
    <div className="chat" style={{ height: 'calc(100vh - 64px)' }}>
      <div className="chat-main">
        {/* Which area the diagnosis is in, plus real progress. The count comes
            from the session the server returns; there is no total to show
            against it because the engine picks questions adaptively, so saying
            "12 of N" would be inventing the N. */}
        <div className="chat-dims">
          {category && (
            <span className="dim-chip on">
              <span className="p" />
              {category}
            </span>
          )}
          <span className="dg-progress" aria-live="polite">
            {answered > 0 ? `${answered} answered` : 'Just started'}
            {' · your answers are saved as you go'}
          </span>
        </div>

        {/* Messages */}
        {/* AllyChat's transcript is a labelled live region; this one -- the
            product's core 20-minute journey -- announced nothing at all, so no
            question Ally asked ever reached a screen reader. */}
        <div className="chat-scroll" ref={scrollRef} role="log" aria-live="polite" aria-label="Your diagnosis with Ally">
          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              {/* Was the literal string 'RV' -- the mock founder's initials,
                  shown to every founder next to their own answers. */}
              <div className={`m-av ${m.role}`} aria-hidden="true">
                {m.role === 'ally' ? '🤝' : initials}
              </div>
              <div>
                <div className="bubble">{m.text}</div>
                <div className="m-meta">{m.time}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Was three buttons with no onClick at all, captioned with a fictional
            founder's business ("the SME churn pattern"). These answer the
            question actually on screen, and they send. */}
        {!done && question && (
          <div className="suggs">
            {['I’m not sure', 'Can you rephrase that?', 'Skip this one'].map(t => (
              <button
                key={t}
                className="sugg"
                type="button"
                disabled={busy}
                onClick={() => answer(t)}
              >
                {t}
              </button>
            ))}
          </div>
        )}

        {/* Input */}
        <div className="chat-input">
          <div className="ci-row">
            <label className="sr-only" htmlFor="dg-answer">Your answer to Ally</label>
            <textarea
              id="dg-answer"
              rows={1}
              placeholder={done ? 'Your diagnosis is complete.' : "Answer Ally's question or ask anything..."}
              value={input}
              onChange={e => setInput(e.target.value)}
              disabled={busy || done}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); answer(input); }
              }}
            />
            <button
              className={`ci-btn${voice.status === 'recording' ? ' recording' : ''}`}
              type="button"
              title="Voice input"
              aria-label="Voice input"
              aria-pressed={voice.status === 'recording'}
              disabled={busy || done || voice.status === 'transcribing'}
              onClick={voice.toggle}
            >
              <svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0014 0M12 18v3"/></svg>
            </button>
            <button className="ci-btn send" title="Send" aria-label="Send answer" type="button"
                    disabled={busy || done || !input.trim()}
                    onClick={() => answer(input)}>
              <svg viewBox="0 0 24 24"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
            </button>
          </div>
          <div className="ci-hint">
            {done ? 'Diagnosis complete — building your report…'
                  : busy ? 'Saving your answer…'
                  : 'Structured diagnosis · Voice input free on every plan here'}
          </div>
        </div>
      </div>

      {/* Knowledge Graph Panel */}
      {kgVisible && (
        <div className="kg-panel">
          <h2>Live knowledge graph</h2>
          <p className="kp-sub">How Ally is connecting what you say to the underlying cause.</p>
          <div className="kg" ref={kgRef}>
            <svg viewBox="0 0 260 210" preserveAspectRatio="xMidYMid meet">
              <path className="edge" d="M40,40 C110,40 90,95 130,95" />
              <path className="edge" d="M40,120 C110,120 100,100 130,95" />
              <path className="edge" d="M40,180 C110,180 110,110 130,100" />
              <path className="edge hot" d="M130,95 C190,95 190,150 220,150" />
              <circle className="kn" cx="40" cy="40" r="7" fill="rgba(255,255,255,.25)" />
              <circle className="kn" cx="40" cy="120" r="7" fill="rgba(255,255,255,.25)" />
              <circle className="kn" cx="40" cy="180" r="7" fill="rgba(255,255,255,.25)" />
              <circle className="kg-ring" cx="220" cy="150" r="11" />
              <circle className="kn pulse-m" cx="130" cy="97" r="8" fill="#34d399" />
              <circle className="kn pulse-r" cx="220" cy="150" r="10" fill="#A8D94A" />
              <circle className="kg-sig s1" r="3" />
              <circle className="kg-sig s2" r="3" />
              <circle className="kg-sig s3" r="3" />
              <circle className="kg-sig hot" r="3.4" />
              {/* The founder's own answers, newest last. */}
              {[43, 123, 183].map((y, i) => (
                <text key={y} className="kg-lbl" x="52" y={y}>
                  {symptoms[i] || '—'}
                </text>
              ))}
              {/* The mechanism and root cause are produced by the reasoning
                  layer once the diagnosis finishes -- there is nothing truthful
                  to name here while questions are still being answered. */}
              <text className="kg-lbl hot" x="96" y="118">{done ? 'Mechanism' : 'Listening…'}</text>
              <text className="kg-lbl hot" x="176" y="172">{done ? 'Root cause' : 'In your report'}</text>
            </svg>
          </div>
          <div className="kg-legend">
            <div className="kg-leg"><span className="d" style={{ background: 'rgba(255,255,255,.3)' }} /> Symptoms you described</div>
            <div className="kg-leg"><span className="d" style={{ background: '#34d399' }} /> Mechanism Ally inferred</div>
            <div className="kg-leg"><span className="d" style={{ background: '#A8D94A' }} /> Root cause</div>
          </div>
          {symptoms.length === 0 && (
            <p className="kp-sub" style={{ marginTop: 10 }}>
              Nothing plotted yet — this fills in from your answers as you go.
            </p>
          )}
        </div>
      )}

      {/* Asked once, the moment the diagnosis ends. Holds the hand-off to the
          report interstitial so the dialog is not navigated out from under
          them, and resolves straight through if they have already answered. */}
      <FeedbackPrompt
        type={FEEDBACK.DIAGNOSIS}
        when={done}
        sessionId={sessionId}
        title="How was that diagnosis?"
        subtitle="You just answered a lot of questions. Were they the right ones?"
        onResolved={() => navigate('/app/thinking')}
      />
    </div>
  );
}
