import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { get, post, ApiError } from '../services/api';
import { useVoiceInput } from '../hooks/useVoiceInput';

const DIM_CHIPS = ['All', 'Revenue', 'Strategy', 'Team', 'Operations', 'Finance', 'Market'];

function nowLabel() {
  return 'Just now';
}

export default function DiagnosisChat() {
  const navigate = useNavigate();
  const { showToast } = useApp();
  const [activeDim, setActiveDim] = useState('All');
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [question, setQuestion] = useState(null); // current QuestionRead, or null when complete
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [complete, setComplete] = useState(false);
  const [kgVisible, setKgVisible] = useState(true);
  const kgRef = useRef(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    if (kgRef.current) setTimeout(() => kgRef.current?.classList.add('draw'), 800);
  }, [messages]);

  // Resume an in-progress session, or start a new one, on first load.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        let session, currentQuestion;
        try {
          const current = await get('/diagnosis/current');
          session = current.session;
          currentQuestion = current.question;
        } catch (err) {
          if (err instanceof ApiError && err.status === 404) {
            const started = await post('/diagnosis/start', {});
            session = started.session;
            currentQuestion = started.question;
          } else {
            throw err;
          }
        }
        if (cancelled) return;
        if (session?.current_category) setActiveDim(session.current_category);
        if (currentQuestion) {
          setQuestion(currentQuestion);
          setMessages([{ role: 'ally', text: currentQuestion.question_text, time: nowLabel() }]);
        } else {
          setComplete(true);
          setMessages([{
            role: 'ally',
            text: "You've completed your diagnosis. Your report is ready — head over to your dashboard to see the full breakdown.",
            time: nowLabel(),
          }]);
        }
      } catch (err) {
        showToast(err instanceof ApiError ? err.detail : 'Could not load your diagnosis session — please refresh.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submitAnswer = async (text) => {
    const answer = text.trim();
    if (!answer || !question || submitting) return;
    setMessages(prev => [...prev, { role: 'me', text: answer, time: nowLabel() }]);
    setInput('');
    setSubmitting(true);
    try {
      const result = await post('/diagnosis/answer', {
        question_id: question.question_id,
        answer_text: answer,
      });
      if (result.session?.current_category) setActiveDim(result.session.current_category);
      if (result.is_complete || !result.next_question) {
        setComplete(true);
        setQuestion(null);
        setMessages(prev => [...prev, {
          role: 'ally',
          text: "That completes your diagnosis. Your report is ready — head over to your dashboard to see the full breakdown.",
          time: nowLabel(),
        }]);
      } else {
        setQuestion(result.next_question);
        setMessages(prev => [...prev, {
          role: 'ally', text: result.next_question.question_text, time: nowLabel(),
        }]);
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'ally',
        text: err instanceof ApiError && err.status === 422
          ? "That answer didn't come through — could you rephrase it?"
          : "Something went wrong submitting that answer. Please try again.",
        time: nowLabel(),
      }]);
    } finally {
      setSubmitting(false);
    }
  };

  // Voice is free on every plan in diagnosis (only chat is plan-gated) -- no
  // canUseVoiceInChat check here, matching the product decision.
  const voice = useVoiceInput({
    context: 'diagnosis',
    onTranscribed: (text) => setInput(prev => (prev ? `${prev} ${text}` : text)),
    onError: () => showToast('Could not access the microphone — check your browser permissions.'),
  });

  return (
    <div className="chat" style={{ height: 'calc(100vh - 64px)' }}>
      <div className="chat-main">
        {/* Dimension chips */}
        <div className="chat-dims">
          {DIM_CHIPS.map(d => (
            <button key={d} className={`dim-chip${activeDim === d ? ' on' : ''}`} onClick={() => setActiveDim(d)}>
              <span className="p" />
              {d}
            </button>
          ))}
        </div>

        {/* Messages */}
        <div className="chat-scroll" ref={scrollRef}>
          {loading ? (
            <div className="msg ally">
              <div className="m-av ally">🤝</div>
              <div><div className="bubble">Loading your diagnosis…</div></div>
            </div>
          ) : (
            messages.map((m, i) => (
              <div key={i} className={`msg ${m.role}`}>
                <div className={`m-av ${m.role}`}>{m.role === 'ally' ? '🤝' : 'RV'}</div>
                <div>
                  <div className="bubble">{m.text}</div>
                  <div className="m-meta">{m.time}</div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Input */}
        <div className="chat-input">
          <div className="ci-row">
            <textarea
              rows={1}
              placeholder={complete ? 'Your diagnosis is complete.' : "Answer Ally's question…"}
              value={input}
              disabled={complete || loading || submitting}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitAnswer(input); }
              }}
            />
            <button
              className={`ci-btn${voice.status === 'recording' ? ' recording' : ''}`}
              title="Voice input"
              aria-pressed={voice.status === 'recording'}
              disabled={complete || loading || voice.status === 'transcribing'}
              onClick={voice.toggle}
            >
              <svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0014 0M12 18v3"/></svg>
            </button>
            <button
              className="ci-btn send"
              title="Send"
              disabled={complete || loading || submitting}
              onClick={() => submitAnswer(input)}
            >
              <svg viewBox="0 0 24 24"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
            </button>
          </div>
          <div className="ci-hint">Structured diagnosis · Voice input free on every plan here</div>
        </div>
      </div>

      {/* Knowledge Graph Panel (illustrative -- not yet driven by live session data) */}
      {kgVisible && (
        <div className="kg-panel">
          <h3>Live knowledge graph</h3>
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
              <text className="kg-lbl" x="52" y="43">Flat growth</text>
              <text className="kg-lbl" x="52" y="123">Rising spend</text>
              <text className="kg-lbl" x="52" y="183">Week-2 silence</text>
              <text className="kg-lbl hot" x="96" y="118">Mechanism</text>
              <text className="kg-lbl hot" x="176" y="172">Root cause</text>
            </svg>
          </div>
          <div className="kg-legend">
            <div className="kg-leg"><span className="d" style={{ background: 'rgba(255,255,255,.3)' }} /> Symptoms you described</div>
            <div className="kg-leg"><span className="d" style={{ background: '#34d399' }} /> Mechanism Ally inferred</div>
            <div className="kg-leg"><span className="d" style={{ background: '#A8D94A' }} /> Root cause</div>
          </div>
        </div>
      )}
    </div>
  );
}
