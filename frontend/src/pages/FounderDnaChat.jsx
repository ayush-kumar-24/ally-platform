import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import {
  TOTAL_DIMENSIONS,
  dimensionLabel,
  getCurrentFounderDna,
  normalise,
  resumeOrStartFounderDna,
  submitFounderDnaAnswer,
} from '../services/founderDna';
import { useVoiceInput } from '../hooks/useVoiceInput';

/* The identity half of the journey, asked before the business diagnosis.
   Deliberately mirrors DiagnosisChat's shape -- same transcript, same
   saved-as-you-go promise, same voice input -- so it reads as one continuous
   conversation with Ally rather than two different products. The differences
   are the ones that carry meaning:

     * a forced-choice question renders as buttons, not a textarea. The
       backend sends `format` and `options`; typing "Bracing with the team"
       by hand would be a worse answer to a question that is a pick-one.
     * progress counts DIMENSIONS understood, not questions answered. The
       count of questions is an implementation detail a founder has no
       reason to care about; "9 of 14 understood" is the thing that is
       actually happening.
     * the closing question is announced. The doc calls for a deliberately
       larger final question, and landing it without a beat of separation
       wastes it. */

const clock = (d) => (d ? new Date(d) : new Date()).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });

export default function FounderDnaChat() {
  const navigate = useNavigate();
  const { user, showToast } = useApp();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [question, setQuestion] = useState(null);
  const [resolved, setResolved] = useState([]);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [failed, setFailed] = useState(false);
  // Shown before the first question, and ONLY to a founder who hasn't
  // started -- someone resuming has already read it, and re-explaining the
  // process to a person nine answers deep reads as Ally having forgotten
  // the conversation. Set from the server's answered count on load, so it
  // survives a refresh mid-phase.
  const [showBrief, setShowBrief] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, busy]);

  useEffect(() => {
    let cancelled = false;
    resumeOrStartFounderDna()
      .then((state) => {
        if (cancelled) return;
        setResolved(state.resolved);
        if (state.complete) {
          // Already finished on arrival -- pass straight through to the
          // diagnosis rather than showing a completion screen for something
          // they did days ago. `replace` so Back doesn't bounce them here
          // again. This is what lets the dashboard's single "Start
          // Diagnosis" button always point at this route: a founder who has
          // done the phase never notices it exists, and one who hasn't gets
          // it before the 409 can happen.
          navigate('/app/diagnosis', { replace: true });
          return;
        }
        setQuestion(state.question);
        setShowBrief(state.answered === 0);
        const opening = state.answered > 0
          ? []
          : [{ role: 'ally', time: clock(),
              text: "Right — let's start with you. There are no wrong answers here, and a specific story tells me far more than a polished one." }];
        // Rebuild what was already said. Without this a reload showed one
        // lone question in an empty transcript -- every earlier answer was
        // safe on the server but invisible, which reads as the conversation
        // having been thrown away. Each turn keeps its real answered_at
        // rather than "now", so the timestamps stay honest.
        const past = state.history.flatMap(h => [
          { role: 'ally', time: clock(h.answeredAt), text: h.questionText },
          { role: 'me', time: clock(h.answeredAt), text: h.answerText },
        ]);
        setMessages([
          ...opening,
          ...past,
          ...(state.question?.text
            ? [{ role: 'ally', time: clock(), text: state.question.text, closing: state.question.isClosing }]
            : []),
        ]);
      })
      .catch(() => {
        if (cancelled) return;
        setFailed(true);
        setMessages([{ role: 'ally', time: clock(),
          text: "I couldn't start this just now. Please refresh to try again." }]);
      });
    return () => { cancelled = true; };
    // `navigate` is referenced for the already-complete pass-through above.
    // It is stable across renders in react-router v6, so listing it cannot
    // re-run this effect and re-start the phase.
  }, [navigate]);

  const answer = async (text) => {
    if (!text.trim() || busy || done) return;
    setMessages(prev => [...prev, { role: 'me', text, time: clock() }]);
    setInput('');
    setBusy(true);
    try {
      const state = normalise(await submitFounderDnaAnswer({
        questionId: question?.id, answer: text,
      }));
      setResolved(state.resolved);
      if (state.question?.text && !state.complete) {
        setQuestion(state.question);
        setMessages(prev => [...prev, {
          role: 'ally', time: clock(), text: state.question.text,
          closing: state.question.isClosing,
        }]);
      } else {
        setDone(true);
        setQuestion(null);
        setMessages(prev => [...prev, {
          role: 'ally', time: clock(),
          text: "That's your Founder DNA mapped. Now let's look at the business itself.",
        }]);
      }
    } catch {
      // Same reconciliation as DiagnosisChat, for the same measured reason:
      // a client timeout here does not mean the server failed. The
      // dimension-resolution call can push this past the client's patience
      // while the answer saves fine, and telling a founder to resend an
      // answer that already landed gets them a 409 on the retry.
      try {
        const current = normalise(await getCurrentFounderDna());
        if (current.complete) {
          setDone(true);
          setQuestion(null);
          setMessages(prev => [...prev, {
            role: 'ally', time: clock(),
            text: "That's your Founder DNA mapped. Now let's look at the business itself.",
          }]);
          return;
        }
        if (current.question?.id && current.question.id !== question?.id) {
          setQuestion(current.question);
          setResolved(current.resolved);
          setMessages(prev => [...prev, {
            role: 'ally', time: clock(), text: current.question.text,
            closing: current.question.isClosing,
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
    context: 'founder_dna',
    onTranscribed: (text) => setInput(prev => (prev ? `${prev} ${text}` : text)),
    onError: () => showToast('Could not access the microphone — check your browser permissions.'),
  });

  const initials = (user?.initials || user?.name || '?').charAt(0).toUpperCase();
  const isChoice = question?.format === 'forced_choice' && Array.isArray(question.options);

  /* What's about to happen, before it happens. This is a ~40-minute
     commitment across two phases and a founder should be able to decide
     whether now is the moment -- previously the only warning was a single
     chat bubble that scrolls away, which is easy to start half-attentively
     and abandon at question nine. Reuses the guided flow's phase-card
     pattern (Expectation.jsx) so "here is the shape of this" looks the same
     wherever Ally says it.

     Note the times are honest about the WHOLE journey, not just this phase:
     Founder DNA is ~15 min, the business diagnosis after it is ~20. */
  if (showBrief && !failed) {
    return (
      <div className="fd-container">
        {/* Same dark hero + white-cards-on-cream language as the Founder DNA
            result page (styles/founder-dna.css). An earlier cut of this
            screen reused the guided flow's `.j-*` classes, which are written
            for that flow's dark stage -- on this light shell `.j-sub` is
            `#a7c0b4` on cream, so the intro paragraph came out unreadable
            and the phase cards lost their hierarchy entirely. */}
        <div className="fd-hero">
          <div className="fd-hero-content">
            <div className="fd-hero-kicker">Founder diagnosis</div>
            <h1 className="fd-hero-title">
              Here's how this <em>works</em>
            </h1>
            <p className="fd-hero-desc">
              Two conversations and a report. Ally asks one question at a time,
              adapts to what you say, and stops as soon as it has what it needs
              — so the length depends on your answers.
            </p>
          </div>
        </div>

        <div className="fd-section-head">
          <h2 className="fd-section-title">What happens</h2>
        </div>

        <div className="fd-grid" style={{ gridTemplateColumns: '1fr' }}>
          {[
            {
              step: 'First · ~15 min',
              title: 'Ally gets to know you',
              desc: 'Around fifteen questions about how you decide, what drives you, where your energy goes, and how you handle pressure. Not a personality quiz — real situations from how you actually run this.',
            },
            {
              step: 'Then · ~20 min',
              title: 'Ally examines the business',
              desc: "A structured diagnosis across revenue, market, product, team and operations — tracing symptoms back to what's actually causing them.",
            },
            {
              step: 'Finally',
              title: 'You get your report',
              desc: 'Your Founder DNA, your business health, the root cause Ally found, and the specific next steps that follow from it.',
            },
          ].map(({ step, title, desc }) => (
            <div className="fd-card" key={title}>
              <div className="fd-card-top">
                <div className="fd-card-info">
                  <div className="fd-card-title-wrap">
                    <h4 className="fd-card-title">{title}</h4>
                  </div>
                  <div className="fd-card-subtitle">{step}</div>
                </div>
              </div>
              <p className="fd-card-desc">{desc}</p>
            </div>
          ))}
        </div>

        <div className="fd-card" style={{ marginTop: 18 }}>
          <p className="fd-card-desc" style={{ margin: 0 }}>
            <strong style={{ color: 'var(--ink, #16241c)' }}>Two things worth knowing.</strong>{' '}
            Every answer saves as you go, so you can close this and pick it up
            exactly where you left off. And honest beats impressive every time —
            Ally is reading for patterns, not judging the answers.
          </p>
        </div>

        {/* Sticky, not inline: on a narrow viewport the cards push the CTA
            past the fold (measured at y=1089 in a 741px window), leaving the
            founder scrolling to find how to begin. Same intent as the guided
            flow's fixed bar, but sticky inside the scroll container so it
            cannot sit over the app's own chrome. */}
        <div
          style={{
            position: 'sticky', bottom: 0, display: 'flex', gap: 12,
            alignItems: 'center', flexWrap: 'wrap',
            padding: '18px 0 10px', marginTop: 10,
            background: 'linear-gradient(to bottom, transparent, var(--bg, #f7f5ef) 22%)',
          }}
        >
          <button type="button" className="btn btn-em" onClick={() => setShowBrief(false)}>
            I'm ready — let's start
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => navigate('/app')}>
            Not right now
          </button>
        </div>
      </div>
    );
  }

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
        <div style={{ fontSize: '40px' }} aria-hidden="true">🧬</div>
        <h2 style={{ margin: 0 }}>Your Founder DNA is mapped</h2>
        <p style={{ color: 'var(--muted-2)', margin: 0 }}>
          {resolved.length} of {TOTAL_DIMENSIONS} dimensions understood. Next, Ally
          looks at the business itself and traces what's actually holding it back.
        </p>
        <div style={{ display: 'flex', gap: '10px', marginTop: '8px', flexWrap: 'wrap', justifyContent: 'center' }}>
          <button type="button" className="btn-primary" onClick={() => navigate('/app/diagnosis')}>
            Continue to diagnosis
          </button>
          <button type="button" className="sugg" onClick={() => navigate('/app/founder-dna')}>
            See my Founder DNA
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="chat" style={{ height: '100%' }}>
      <div className="chat-main">
        {/* Dimensions understood, not questions answered -- the question count
            is an implementation detail; the dimensions are the actual thing
            being built. No "x of N questions" for the same reason
            DiagnosisChat avoids it: the length is adaptive, so any N would
            be invented. */}
        <div className="chat-dims">
          {question?.dimension && (
            <span className="dim-chip on">
              <span className="p" />
              {dimensionLabel(question.dimension)}
            </span>
          )}
          <span className="dg-progress" aria-live="polite">
            {`${resolved.length} of ${TOTAL_DIMENSIONS} dimensions understood`}
            {' · your answers are saved as you go'}
          </span>
        </div>

        <div
          className="chat-scroll"
          ref={scrollRef}
          role="log"
          aria-live="polite"
          aria-label="Mapping your Founder DNA with Ally"
        >
          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              <div className={`m-av ${m.role}`} aria-hidden="true">
                {m.role === 'ally' ? '🤝' : initials}
              </div>
              <div>
                {/* The doc asks for the journey to end on one deliberately
                    bigger question. Dropping it in unannounced reads as just
                    another question and wastes the moment it was written for. */}
                {m.closing && (
                  <div className="dg-progress" style={{ marginBottom: 6 }}>
                    One last one — and this is the one worth sitting with.
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

        {/* A pick-one question gets buttons. Typing the option text by hand
            would be a worse answer and a worse experience. */}
        {isChoice && !busy && (
          <div className="suggs" role="group" aria-label="Choose one">
            {question.options.map(opt => (
              <button key={opt} className="sugg" type="button" disabled={busy}
                      onClick={() => answer(opt)}>
                {opt}
              </button>
            ))}
          </div>
        )}

        <div className="chat-input">
          <div className="ci-row">
            <label className="sr-only" htmlFor="fdna-answer">Your answer to Ally</label>
            <textarea
              id="fdna-answer"
              rows={1}
              placeholder={
                failed ? 'Refresh to try again.'
                  : isChoice ? 'Pick one above — or type if none of them fit.'
                  : 'Take your time — the specific answer is the useful one.'
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
                  : 'Founder DNA · this comes before the business diagnosis'}
          </div>
        </div>
      </div>
    </div>
  );
}
