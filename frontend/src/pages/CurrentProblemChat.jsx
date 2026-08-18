import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import {
  getCurrentProblem,
  normalise,
  resumeOrStartCurrentProblem,
  submitCurrentProblemAnswer,
} from '../services/currentProblem';
import { useVoiceInput } from '../hooks/useVoiceInput';

/* The bridge between Founder DNA and the business diagnosis: the founder
   says, in their own words, what they think is wrong — then answers three
   stage-specific probes.

   Mirrors FounderDnaChat's shape (same transcript, same saved-as-you-go
   promise, same voice input) so the journey reads as one conversation. The
   differences are deliberate:

     * no intro brief. FounderDnaChat already explained the whole journey,
       and re-explaining it to someone fifteen answers deep reads as Ally
       having forgotten the conversation.
     * progress is a real "2 of 4". This phase has a fixed length, so unlike
       Founder DNA an honest count exists and withholding it would be
       needlessly vague.
     * the opening question is announced. It is the one answer the report
       quotes back verbatim, and a founder who dashes it off in five words
       has weakened their own report without knowing it. */

const clock = (d) => (d ? new Date(d) : new Date()).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });

const DONE_LINE = "That's what I needed. Now let's trace it back to what's actually causing it.";

export default function CurrentProblemChat() {
  const navigate = useNavigate();
  const { user, showToast } = useApp();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [question, setQuestion] = useState(null);
  const [progress, setProgress] = useState({ answered: 0, total: 0 });
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [failed, setFailed] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, busy]);

  useEffect(() => {
    let cancelled = false;
    resumeOrStartCurrentProblem()
      .then((state) => {
        if (cancelled) return;
        setProgress({ answered: state.answered, total: state.total });
        if (state.complete) {
          // Already finished on arrival -- pass straight through, same
          // reasoning as FounderDnaChat's: this route is on the path every
          // "Start Diagnosis" button takes, so a founder who has done the
          // phase must never see a completion screen for it again.
          navigate('/app/diagnosis', { replace: true });
          return;
        }
        setQuestion(state.question);
        const opening = state.answered > 0
          ? []
          : [{ role: 'ally', time: clock(),
              text: "Good — I've got a clear read on you. Now the business itself." }];
        // Rebuild what was already said, so a reload doesn't render one lone
        // question in an empty transcript. Real answered_at timestamps, not
        // "now", so the history stays honest.
        const past = state.history.flatMap(h => [
          { role: 'ally', time: clock(h.answeredAt), text: h.questionText, symptom: h.isSymptom },
          { role: 'me', time: clock(h.answeredAt), text: h.answerText },
        ]);
        setMessages([
          ...opening,
          ...past,
          ...(state.question?.text
            ? [{ role: 'ally', time: clock(), text: state.question.text, symptom: state.question.isSymptom }]
            : []),
        ]);
      })
      .catch((err) => {
        if (cancelled) return;
        setFailed(true);
        // A 409 here means the Founder DNA phase isn't finished -- a routing
        // problem, not a server fault, and "please refresh" would loop them
        // forever on a page that cannot work yet.
        const needsDna = err?.response?.status === 409;
        setMessages([{ role: 'ally', time: clock(),
          text: needsDna
            ? "Let's finish getting to know you first — I'll take you back."
            : "I couldn't start this just now. Please refresh to try again." }]);
        if (needsDna) setTimeout(() => navigate('/app/founder-dna-journey', { replace: true }), 1800);
      });
    return () => { cancelled = true; };
    // `navigate` is stable across renders in react-router v6, so listing it
    // cannot re-run this effect and re-start the phase.
  }, [navigate]);

  const answer = async (text) => {
    if (!text.trim() || busy || done) return;
    setMessages(prev => [...prev, { role: 'me', text, time: clock() }]);
    setInput('');
    setBusy(true);
    try {
      const state = normalise(await submitCurrentProblemAnswer({
        questionId: question?.id, answer: text,
      }));
      setProgress(p => ({ answered: state.answered, total: state.total || p.total }));
      if (state.question?.text && !state.complete) {
        setQuestion(state.question);
        setMessages(prev => [...prev, {
          role: 'ally', time: clock(), text: state.question.text,
          symptom: state.question.isSymptom,
        }]);
      } else {
        setDone(true);
        setQuestion(null);
        setMessages(prev => [...prev, { role: 'ally', time: clock(), text: DONE_LINE }]);
      }
    } catch {
      // Same reconciliation as FounderDnaChat/DiagnosisChat: a client-side
      // failure does not prove the server failed, and telling a founder to
      // resend an answer that already landed earns them a 409 on the retry.
      try {
        const current = normalise(await getCurrentProblem());
        if (current.complete) {
          setDone(true);
          setQuestion(null);
          setMessages(prev => [...prev, { role: 'ally', time: clock(), text: DONE_LINE }]);
          return;
        }
        if (current.question?.id && current.question.id !== question?.id) {
          setQuestion(current.question);
          setProgress({ answered: current.answered, total: current.total });
          setMessages(prev => [...prev, {
            role: 'ally', time: clock(), text: current.question.text,
            symptom: current.question.isSymptom,
          }]);
          return;
        }
      } catch {
        // Reconciliation itself failed -- fall through to the honest message.
      }
      setMessages(prev => [...prev, {
        role: 'ally', time: clock(),
        text: "That didn't save. Your answer wasn't lost — try sending it again.",
      }]);
    } finally {
      setBusy(false);
    }
  };

  const voice = useVoiceInput({
    context: 'current_problem',
    onTranscribed: (text) => setInput(prev => (prev ? `${prev} ${text}` : text)),
    onError: () => showToast('Could not access the microphone — check your browser permissions.'),
  });

  const initials = (user?.initials || user?.name || '?').charAt(0).toUpperCase();

  if (done) {
    return (
      <div
        style={{
          height: '100%', display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', textAlign: 'center',
          gap: '16px', padding: '32px', maxWidth: '520px', margin: '0 auto',
        }}
        role="status"
      >
        <div style={{ fontSize: '40px' }} aria-hidden="true">🎯</div>
        <h2 style={{ margin: 0 }}>Got it — that's the problem as you see it</h2>
        <p style={{ color: 'var(--muted-2)', margin: 0 }}>
          Ally will now work through the business itself and trace this back to
          what's actually causing it. Your report will show both — what you said,
          and what the answers point to.
        </p>
        <div style={{ display: 'flex', gap: '10px', marginTop: '8px', flexWrap: 'wrap', justifyContent: 'center' }}>
          <button type="button" className="btn-primary" onClick={() => navigate('/app/diagnosis')}>
            Continue to diagnosis
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="chat" style={{ height: '100%' }}>
      <div className="chat-main">
        <div className="chat-dims">
          <span className="dim-chip on">
            <span className="p" />
            Current problem
          </span>
          {/* A real count, unlike Founder DNA's adaptive length -- this phase
              is exactly four questions, so any vagueness here would be
              invented rather than honest. */}
          <span className="dg-progress" aria-live="polite">
            {progress.total
              ? `${Math.min(progress.answered + 1, progress.total)} of ${progress.total}`
              : 'Getting started'}
            {' · your answers are saved as you go'}
          </span>
        </div>

        <div
          className="chat-scroll"
          ref={scrollRef}
          role="log"
          aria-live="polite"
          aria-label="Describing your current problem to Ally"
        >
          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              <div className={`m-av ${m.role}`} aria-hidden="true">
                {m.role === 'ally' ? '🤝' : initials}
              </div>
              <div>
                {/* The one answer quoted verbatim in the report. Saying so
                    before they answer is what gets a real sentence instead of
                    four words -- and the report is only as good as this. */}
                {m.symptom && (
                  <div className="dg-progress" style={{ marginBottom: 6 }}>
                    Take this one slowly — I'll quote it back to you in your report.
                  </div>
                )}
                <div className="bubble">{m.text}</div>
                <div className="m-meta">{m.time}</div>
              </div>
            </div>
          ))}
          {busy && (
            <div className="typing" aria-live="polite" aria-label="Ally is thinking">
              <div className="m-av ally" aria-hidden="true">🤝</div>
              <div className="bubble"><div className="td"><span /><span /><span /></div></div>
            </div>
          )}
        </div>

        <div className="chat-input">
          <div className="ci-row">
            <label className="sr-only" htmlFor="cp-answer">Your answer to Ally</label>
            <textarea
              id="cp-answer"
              rows={1}
              placeholder={
                failed ? 'Refresh to try again.'
                  : question?.isSymptom
                    ? "In your own words — don't polish it."
                    : 'The specific example is the useful one.'
              }
              value={input}
              onChange={e => setInput(e.target.value)}
              disabled={busy || failed}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); answer(input); }
              }}
            />
            <button
              className={`ci-btn${voice.status === 'recording' ? ' recording' : ''}`}
              type="button" title="Voice input" aria-label="Voice input"
              aria-pressed={voice.status === 'recording'}
              disabled={busy || failed || voice.status === 'transcribing'}
              onClick={voice.toggle}
            >
              <svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0014 0M12 18v3"/></svg>
            </button>
            <button className="ci-btn send" title="Send" aria-label="Send answer" type="button"
                    disabled={busy || failed || !input.trim()}
                    onClick={() => answer(input)}>
              <svg viewBox="0 0 24 24"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
            </button>
          </div>
          <div className="ci-hint">
            {busy ? 'Saving your answer…'
                  : 'Current problem · then Ally examines the business'}
          </div>
        </div>
      </div>
    </div>
  );
}
