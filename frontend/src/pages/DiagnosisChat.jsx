import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { getCurrentSession, normalise, resumeOrStart, submitAnswer } from '../services/diagnosis';
import { explainLimit, getMyPlan } from '../services/plans';
import { useVoiceInput } from '../hooks/useVoiceInput';
import VoiceBars from '../components/VoiceBars';
import useAutoGrow from '../hooks/useAutoGrow';
import Markdown from '../components/Markdown';
import FeedbackPrompt from '../components/FeedbackPrompt';
import LiveKnowledgeGraph from '../components/LiveKnowledgeGraph';
import { FEEDBACK } from '../services/feedback';

/* There was a filter bar here: All / Revenue / Strategy / Team / Operations /
   Finance / Market. It filtered nothing -- the click handler set state nothing
   ever read -- and none of those seven are real: the question bank uses
   seventeen categories ("Sales Execution", "Founder Psychology", "Target
   Customer & ICP" and so on), and the server decides what to ask next anyway.
   A founder cannot choose their own diagnosis path, so offering a chooser was
   a lie twice over. What's shown now is the category actually being asked. */

const clock = (d) => (d ? new Date(d) : new Date()).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });

export default function DiagnosisChat() {
  const navigate = useNavigate();
  const { user, showToast } = useApp();
  const [answered, setAnswered] = useState(0);
  const [category, setCategory] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const taRef = useAutoGrow(input);
  const [question, setQuestion] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  // Set only when the founder has already completed their one free diagnosis
  // (DiagnosisAlreadyCompletedError). This blocks the diagnosis screen
  // entirely -- there is no partial state to resume into, so nothing below it
  // renders at all. See the resumeOrStart().catch below.
  const [blocked, setBlocked] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, busy]);

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
        // Live-reproduced: resuming showed only the single current question
        // -- every prior answer was safely saved server-side but never sent
        // back to render, so the transcript looked wiped on every reload.
        // Rebuilds the full history as alternating ally/founder bubbles,
        // oldest first, using each turn's real answered_at rather than "now".
        const past = session.history.flatMap((h) => [
          { role: 'ally', time: clock(h.answeredAt), text: h.questionText },
          { role: 'me', time: clock(h.answeredAt), text: h.answerText },
        ]);
        // A plain page load really can end a diagnosis: _attach_question
        // (diagnosis/service.py) completes the session when the bank is
        // exhausted or the scorer already flipped routing_state to
        // generate_report, so GET /current answers is_complete with no
        // question. Only `question.text` was branched on below, so that
        // reply fell through every branch and left the founder on a blank
        // transcript with a live input box, on a diagnosis already over and
        // a report already being built. Same hand-off as the answer path.
        if (session.complete) {
          setDone(true);
          setMessages([...past, { role: 'ally', time: clock(),
            text: 'That completes your diagnosis. I am building your report now.' }]);
          return;
        }
        if (session.question?.text) {
          // A greeting precedes the first question on a genuine fresh start
          // only -- resuming reloads the same in-progress session (page
          // refresh, closed tab), and re-greeting there would read as Ally
          // forgetting the conversation was already underway.
          const opening = session.resumed
            ? []
            : [{ role: 'ally', time: clock(),
                // No question count. The engine picks adaptively and stops when
                // it has enough, so any number here is a promise the diagnosis
                // does not make -- and one a founder would hold it to.
                text: "Hi, I'm Ally. Let's get started — answer honestly and we'll get to your report as fast as your answers let us." }];
          setMessages([...opening, ...past, { role: 'ally', text: session.question.text, time: clock() }]);
        }
      })
      .catch(async (error) => {
        if (cancelled) return;
        const limit = explainLimit(error);
        if (limit?.kind === 'completed') {
          // Not a transient failure -- the founder's one free diagnosis is
          // already spent, and starting is never going to succeed here. The
          // chat UI never mounts for this founder; it stays blocked at the
          // message below until they upgrade or go read their report.
          setBlocked(limit.message);
          return;
        }
        // Live-reported: a founder who HAD finished their diagnosis was still
        // told to "refresh to try again", forever. DiagnosisAlreadyCompletedError
        // is only one of the ways POST /start refuses someone who is already
        // done -- the route also runs consent, profile and rate-limit gates
        // ahead of the handler, and any of those answers with a different code
        // (403/429/5xx) that lands here instead. Refreshing cannot clear any of
        // them, so the message above was both wrong and a dead end.
        //
        // The founder's usage is the thing that actually settles it, so ask for
        // it rather than inferring the answer from which error came back. Same
        // count and limit the start gate enforces (plans/router.py
        // _diagnosis_usage exists so the two can never disagree).
        try {
          const usage = (await getMyPlan())?.diagnosis_usage;
          if (cancelled) return;
          if (usage && usage.limit != null && usage.used >= usage.limit) {
            setBlocked('Your diagnosis is complete — your report is ready to read.');
            return;
          }
        } catch {
          // Could not confirm either way; say the honest transient thing below
          // rather than guessing at a completion that may not have happened.
        }
        if (cancelled) return;
        setMessages([{ role: 'ally', time: clock(),
          text: "I couldn't start your diagnosis just now. Please refresh to try again." }]);
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
      // The answer did not address the question -- nothing was kept and the same
      // question stands. Handled before anything below, because the server sends
      // that same question back as `question`, which would otherwise render as
      // Ally asking it twice in a row with no explanation. Mirrors
      // FounderDnaChat, which gates the identity phase the same way.
      if (!state.accepted) {
        setMessages(prev => [...prev, {
          role: 'ally', time: clock(),
          text: state.reprompt || "That didn't quite answer the question — try again.",
        }]);
        return;
      }
      const next = state.question;
      // The server's count is authoritative; only fall back to counting
      // locally if it didn't send one.
      if (typeof state.answered === 'number') setAnswered(state.answered);
      else setAnswered(a => a + 1);
      setCategory(next?.category ?? null);
      // Trust the explicit is_complete flag over "no next question": a transient
      // gap must not be mistaken for the end of the diagnosis.
      //
      // Branch on `complete` FIRST. The previous shape — `if (next?.text &&
      // !state.complete) ... else done` — fell into the completion branch on
      // any falsy question regardless of the flag, which is the opposite of
      // what the comment above describes. A response carrying no question and
      // is_complete:false (an abandoned session, a serialisation gap) told the
      // founder their diagnosis was over and sent them to /app/thinking, where
      // no report would ever arrive.
      if (state.complete) {
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
      } else if (next?.text) {
        setQuestion(next);
        setMessages(prev => [...prev, { role: 'ally', time: clock(), text: next.text }]);
      } else {
        // Not complete, but no question came back. The answer was accepted, so
        // the founder has not lost anything — keep them on the question they
        // are already sitting on rather than declaring the diagnosis over.
        setMessages(prev => [...prev, {
          role: 'ally', time: clock(),
          text: "Got that. I lost my place for a second — give me the next one "
            + 'again by refreshing, and nothing you have answered will be lost.',
        }]);
      }
    } catch {
      // Live-reproduced: a client-side timeout on this call does not mean the
      // server failed -- the answer-scoring pipeline routinely runs 12-15s and
      // has hit 23s, and the server goes on to save successfully after the
      // client has already given up and shown a "failed" message. Blindly
      // saying "try again" is actively wrong there: resubmitting the same
      // question_id after the server already advanced past it gets rejected
      // with 409 QuestionMismatchError, which read as a second, worse failure
      // for an answer that was never actually lost. Check server truth first.
      try {
        const raw = await getCurrentSession();
        const current = raw ? normalise(raw, true) : null;
        if (current?.question?.id && current.question.id !== question?.id) {
          // The server did move on -- the answer saved. Silently reconcile
          // instead of alarming the founder over nothing.
          setQuestion(current.question);
          if (typeof current.answered === 'number') setAnswered(current.answered);
          setCategory(current.question.category ?? null);
          setMessages(prev => [...prev, {
            role: 'ally', time: clock(), text: current.question.text,
          }]);
          return;
        }
        if (raw === null) {
          // No active session at all -- it genuinely completed while we were
          // waiting on this request (the last answer crossed the confidence
          // threshold or the 30-question cap).
          setDone(true);
          setMessages(prev => [...prev, {
            role: 'ally', time: clock(),
            text: 'That completes your diagnosis. I am building your report now.',
          }]);
          return;
        }
      } catch {
        // The reconciliation check itself failed -- fall through to the
        // honest "didn't save" message below, since we genuinely don't know.
      }
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

  if (blocked) {
    return (
      <div
        style={{
          height: 'calc(100vh - 64px)', display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', textAlign: 'center',
          gap: '16px', padding: '32px', maxWidth: '480px', margin: '0 auto',
        }}
        role="status"
      >
        <div style={{ fontSize: '40px' }} aria-hidden="true">✅</div>
        <h2 style={{ margin: 0 }}>Diagnosis already completed</h2>
        <p style={{ color: 'var(--muted-2)', margin: 0 }}>{blocked}</p>
        <button
          type="button"
          className="btn-primary"
          onClick={() => navigate('/app/report')}
          style={{ marginTop: '8px' }}
        >
          View your report
        </button>
      </div>
    );
  }

  /* height:100%, not a guessed calc(100vh-64px) -- #main-content
     (PlatformLayout.jsx) is itself flex:1/overflowY:auto, so any mismatch
     between a guessed absolute height here and its real available space
     makes #main-content become the active scroll container instead of
     .chat-scroll below, leaving the actual message history unscrollable.
     Matches the same fix already applied to AllyChat's .ac wrapper. */
  return (
    <div className="chat" style={{ height: '100%' }}>
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
                <div className="bubble">
                  {/* Ally's side only: a founder's own answer is shown
                      verbatim, since a stray asterisk in their words is
                      punctuation, not formatting. */}
                  {m.role === 'ally' ? <Markdown>{m.text}</Markdown> : m.text}
                </div>
                <div className="m-meta">{m.time}</div>
              </div>
            </div>
          ))}
          {/* Nothing showed while the answer was being interpreted and the next
              question chosen -- a real gap, since that round-trip runs an LLM
              classification plus a confidence recompute and routinely takes
              12-15s. Reuses AllyChat's own `.typing` dots for the same visual
              language across both chat surfaces, rather than a new animation. */}
          {busy && (
            <div className="typing" aria-live="polite" aria-label="Ally is thinking">
              <div className="m-av ally" aria-hidden="true">🤝</div>
              <div className="bubble">
                <div className="td">
                  <span /><span /><span />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Was three buttons with no onClick at all, captioned with a fictional
            founder's business ("the SME churn pattern"). These answer the
            question actually on screen, and they send.

            "Can you rephrase that?" and "Skip this one" are gone. There is no
            rephrase or skip endpoint — every chip posts to /diagnosis/answer —
            so both sent a NON-ANSWER into the scored evidence set. The
            responsiveness gate catches the first tap and re-asks, but it
            discards at most once per question by design, so a second tap left
            the non-answer KEPT and scored (almost certainly Red), permanently
            skewing that category's risk, its pillar band and, on a
            distress-tagged question, the distress trigger itself. The UI was
            offering a button for the exact failure the gate was built to stop.

            "I'm not sure" stays: it is a real answer, and the gate explicitly
            treats it as one — it judges topic, not quality. */}
        {!done && question && (
          <div className="suggs">
            {['I’m not sure'].map(t => (
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
          <div className={`ci-row${voice.status !== 'idle' ? ' voice-live' : ''}`}>
            {voice.status !== 'idle' && (
              <VoiceBars
                getLevel={voice.getLevel}
                label={voice.status === 'transcribing' ? 'Transcribing…' : 'Listening…'}
              />
            )}
            <label className="sr-only" htmlFor="dg-answer">Your answer to Ally</label>
            <textarea
              id="dg-answer"
              ref={taRef}
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
              className={`ci-btn mic${voice.status === 'recording' ? ' recording' : ''}`}
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

      <LiveKnowledgeGraph phase="diagnosis" messages={messages} resolved={done} />

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
