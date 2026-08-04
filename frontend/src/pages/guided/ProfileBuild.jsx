import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { saveOnboardingProfile } from '../../services/profile';
import { useVoiceInput } from '../../hooks/useVoiceInput';
import {
  QUESTIONS,
  QUESTION_COUNT,
  SECTIONS,
  STAGE_GROUPS,
  ADAPTIVE_BY_STAGE,
  ADAPTIVE_FALLBACK,
} from '../../data/onboardingQuestions';
import { createReplyPicker } from '../../data/onboardingReplies';

/* Onboarding is deliberately offline: every question, option and reply is
   defined in src/data/onboarding*.js. Nothing here calls an LLM. The only
   network call is the one at the end that persists the answers. */

const reduce = typeof window !== 'undefined' && window.matchMedia
  ? window.matchMedia('(prefers-reduced-motion: reduce)').matches : false;

const sleep = (ms) => new Promise((r) => setTimeout(r, reduce ? Math.min(ms, 50) : ms));

/** Option lists are either plain strings or {label, value} pairs. */
const optLabel = (o) => (typeof o === 'string' ? o : o.label);
const optValue = (o) => (typeof o === 'string' ? o : o.value);

/** What the founder sees in the DNA panel and in their own chat bubble. */
const displayOf = (value) => (Array.isArray(value) ? value.join(', ') : String(value ?? ''));

export default function ProfileBuild() {
  const navigate = useNavigate();
  const { user, setUser, showToast } = useApp();
  const first = user?.name ? user.name.split(' ')[0] : 'there';
  const initial = (user?.initials || first).charAt(0).toUpperCase();

  const [messages, setMessages] = useState([]);
  const [typing, setTyping] = useState(false);
  const [activeQ, setActiveQ] = useState(-1);      // question awaiting an answer
  const [input, setInput] = useState('');
  const [fields, setFields] = useState({});
  const [sectionsOpen, setSectionsOpen] = useState({});
  const [emptyGone, setEmptyGone] = useState(false);
  const [complete, setComplete] = useState(false);
  const [showBar, setShowBar] = useState(false);
  const [introReady, setIntroReady] = useState(false);
  const [undTarget, setUndTarget] = useState(0);
  const [undDisplay, setUndDisplay] = useState(0);
  const [undNote, setUndNote] = useState('Listening…');
  const [undUp, setUndUp] = useState(false);

  /* Per-control working state, reset whenever a new question is presented. */
  const [stageGroup, setStageGroup] = useState(null);
  const [picked, setPicked] = useState([]);
  const [otherText, setOtherText] = useState('');
  const [search, setSearch] = useState('');

  const scrollRef = useRef(null);
  const taRef = useRef(null);
  const searchRef = useRef(null);
  const qiRef = useRef(0);
  const awaitingRef = useRef(false);
  const profileRef = useRef({});
  const started = useRef(false);
  const noteTimer = useRef(null);
  const replyRef = useRef(createReplyPicker());

  const scrollToBottom = () => {
    const s = scrollRef.current;
    if (s) s.scrollTop = s.scrollHeight;
  };
  useEffect(scrollToBottom, [messages, typing, activeQ]);

  /* Focus the answer control as each question appears. Someone answering
     thirteen questions in a row should never have to click into the box first.
     This lives here rather than in present() because the control only mounts
     once activeQ has been set. */
  useEffect(() => {
    if (activeQ < 0) return;
    const { type } = QUESTIONS[activeQ];
    if (type === 'short' || type === 'long') taRef.current?.focus();
    else if (type === 'dropdown') searchRef.current?.focus();
  }, [activeQ]);

  useEffect(() => {
    // Don't animate a number nobody can see. requestAnimationFrame does not run
    // in a hidden tab, so without this the bar (plain state) would move while
    // the percentage beside it stayed frozen at a stale value for any founder
    // who switches away mid-answer.
    if (reduce || document.hidden) { setUndDisplay(undTarget); return undefined; }
    let raf;
    const from = undDisplay;
    const t0 = performance.now();
    const tick = (now) => {
      const k = Math.min(1, (now - t0) / 900);
      setUndDisplay(Math.round(from + (undTarget - from) * (1 - Math.pow(1 - k, 3))));
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [undTarget]);

  const addAlly = useCallback((text) => setMessages((m) => [...m, { who: 'ally', text }]), []);
  const addMe = useCallback((text) => setMessages((m) => [...m, { who: 'me', text }]), []);

  const bumpUnd = useCallback((target, note) => {
    setUndTarget(target);
    if (note) {
      setUndNote(note);
      setUndUp(true);
      if (noteTimer.current) clearTimeout(noteTimer.current);
      noteTimer.current = setTimeout(() => { setUndUp(false); setUndNote('Listening…'); }, 1700);
    }
  }, []);

  /* The last question's text depends on the stage picked in the first. */
  const questionText = useCallback((q) => {
    if (!q.adaptive) return q.q;
    return ADAPTIVE_BY_STAGE[profileRef.current.stage] || ADAPTIVE_FALLBACK;
  }, []);

  const confirmField = useCallback((key, text, animate) => {
    const q = QUESTIONS.find((x) => x.key === key);
    setEmptyGone(true);
    setSectionsOpen((o) => ({ ...o, [q.section]: true }));
    if (animate && !reduce) {
      setFields((f) => ({ ...f, [key]: { status: 'building', text } }));
      setTimeout(() => {
        setFields((f) => ({ ...f, [key]: { status: 'on', text, justin: true } }));
        setTimeout(() => setFields((f) => ({ ...f, [key]: { ...f[key], justin: false } })), 800);
      }, 560);
    } else {
      setFields((f) => ({ ...f, [key]: { status: 'on', text } }));
    }
  }, []);

  const present = useCallback((i) => {
    setStageGroup(null);
    setPicked([]);
    setOtherText('');
    setSearch('');
    setInput('');
    awaitingRef.current = true;
    setActiveQ(i);
  }, []);

  const finish = useCallback(() => {
    setActiveQ(-1);
    awaitingRef.current = false;

    // Persist what the founder just spent ten minutes telling us. Fire-and-report
    // rather than blocking the closing message: the answers are already captured,
    // and making someone wait on a network round trip to hear "that's everything
    // I need" would be the wrong trade.
    saveOnboardingProfile(profileRef.current)
      .then((result) => {
        if (!result.ok) {
          addAlly("I've got your answers, though a few didn't save just now. " +
                  'You can review them any time in your profile.');
        }
      })
      .catch(() => {
        addAlly("I've got your answers here, but I couldn't save them to your " +
                "profile just now. They'll be there when the connection recovers.");
      });
    bumpUnd(100, 'Founder DNA complete');
    setComplete(true);
    setUser((prev) => ({
      ...prev,
      stage: profileRef.current.stage || prev.stage,
      problem: profileRef.current.problem || prev.problem,
      company: profileRef.current.building || prev.company,
      founderProfile: {
        ...(prev?.founderProfile || {}),
        ...profileRef.current,
      },
    }));
    addAlly(`That's everything I need, ${first}. I've got a clear read on you now — give me a moment to form a first impression.`);
    setShowBar(true);
  }, [addAlly, bumpUnd, first, setUser]);

  const askQ = useCallback(async (i) => {
    if (i >= QUESTION_COUNT) { finish(); return; }
    const q = QUESTIONS[i];
    setTyping(true);
    await sleep(820);
    setTyping(false);
    addAlly(questionText(q));
    if (q.prompt) addAlly(q.prompt);
    present(i);
  }, [addAlly, present, finish, questionText]);

  /**
   * Commit an answer.
   * `value`   what gets stored (string, or array for multi-selects)
   * `extra`   fields the question collects alongside its main answer
   * `display` what the founder sees, when that differs from what we store
   */
  const answer = useCallback(async (value, extra, display) => {
    if (!awaitingRef.current) return;
    const empty = Array.isArray(value) ? value.length === 0 : !String(value ?? '').trim();
    if (empty) return;

    awaitingRef.current = false;
    setActiveQ(-1);
    const i = qiRef.current;
    const q = QUESTIONS[i];
    const stored = Array.isArray(value) ? value : String(value).trim();
    // Single-selects store the database value ('first_time', 'excited') and must
    // never show it -- the founder reads their own words back, not our enum.
    const shown = display || displayOf(stored);
    // Multi-selects read better replied against the raw array (the reply joins
    // them with "and"); everything else replies against what was actually shown.
    const replyInput = Array.isArray(stored) ? stored : shown;

    addMe(shown);
    setInput('');
    if (taRef.current) taRef.current.style.height = 'auto';
    profileRef.current = { ...profileRef.current, [q.key]: stored, ...(extra || {}) };
    confirmField(q.key, shown, true);
    const nextQi = i + 1;
    qiRef.current = nextQi;

    await sleep(600);
    const answered = QUESTIONS.filter((x) => profileRef.current[x.key] !== undefined).length;
    bumpUnd(Math.round((answered / QUESTION_COUNT) * 100), 'Ally learned something new');

    setTyping(true);
    await sleep(900);
    setTyping(false);
    if (nextQi < QUESTION_COUNT) {
      addAlly(replyRef.current(q.key, replyInput, { first }));
      await sleep(640);
      askQ(nextQi);
    } else {
      addAlly(replyRef.current(q.key, replyInput, { first }));
      await sleep(640);
      finish();
    }
  }, [addMe, confirmField, bumpUnd, addAlly, askQ, finish, first]);

  /* The founder's name arrives from GET /profile *after* mount -- AppContext
     hydrates identity asynchronously. Greeting someone as "there" while their
     real name is about to appear in the panel beside it reads as a bug, and the
     opening line is pushed into `messages` once, so it never self-corrects.
     Hold the intro until the name lands, bounded so a founder with no name on
     file (or an offline profile fetch) is never stuck on an empty screen. */
  useEffect(() => {
    if (user?.name) { setIntroReady(true); return undefined; }
    const t = setTimeout(() => setIntroReady(true), 2500);
    return () => clearTimeout(t);
  }, [user?.name]);

  useEffect(() => {
    if (!introReady || started.current) return;
    started.current = true;
    (async () => {
      addAlly(`Welcome to GoXL AI, ${first}.`);
      await sleep(700);
      addAlly('Every entrepreneur has a unique story, a different challenge, and a bold vision for the future. In just a few minutes, help me understand yours.');
      await sleep(900);
      askQ(0);
    })();
  }, [introReady]);

  const q = activeQ >= 0 ? QUESTIONS[activeQ] : null;
  const isText = q && (q.type === 'short' || q.type === 'long');

  // Enter sends on every free-text question, long ones included -- gating this
  // on type === 'short' meant Enter silently did nothing on the five long-text
  // questions, which is most of them. Shift+Enter still starts a new line.
  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      answer(taRef.current.value);
    }
  };
  const onInput = (e) => {
    setInput(e.target.value);
    const ta = e.target;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
  };

  // Profile-build is pre-chat onboarding, not the paid chat surface -- voice
  // here is ungated, same product decision as the diagnosis mic (context:
  // 'diagnosis' matches the backend's VOICE_DIAGNOSIS feature, free on every
  // plan).
  const voice = useVoiceInput({
    context: 'diagnosis',
    onTranscribed: (text) => {
      setInput((prev) => (prev ? `${prev} ${text}` : text));
      if (taRef.current) {
        taRef.current.focus();
        taRef.current.style.height = 'auto';
        taRef.current.style.height = Math.min(taRef.current.scrollHeight, 120) + 'px';
      }
    },
    onError: () => showToast('Could not access the microphone — check your browser permissions.'),
  });

  /* --- control handlers ---------------------------------------------------- */

  const toggle = (value) => {
    setPicked((cur) => {
      if (cur.includes(value)) return cur.filter((v) => v !== value);
      if (q?.max && cur.length >= q.max) return cur;   // cap enforced here
      return [...cur, value];
    });
  };

  const submitPicked = () => {
    if (picked.length === 0) return;
    const other = otherText.trim();
    if (q.type === 'chips') {
      // "Other" stays in the list as the marker that there is more; the free
      // text it reveals goes to its own column rather than being appended as a
      // pseudo-chip, so the same words are never stored in two places.
      answer(picked, other ? { audienceOther: other } : undefined);
      return;
    }
    answer(picked);
  };

  const filteredOptions = useMemo(() => {
    if (!q || q.type !== 'dropdown') return [];
    const term = search.trim().toLowerCase();
    if (!term) return q.options;
    return q.options.filter((o) => optLabel(o).toLowerCase().includes(term));
  }, [q, search]);

  const sectionCount = (key) =>
    QUESTIONS.filter((x) => x.section === key && fields[x.key]?.status === 'on').length;

  const needsOther = q?.type === 'chips' && picked.includes('Other');
  const atMax = q?.max ? picked.length >= q.max : false;

  /* --- the input region, one control per question type --------------------- */
  function renderControl() {
    if (!q) return null;

    if (q.type === 'stage') {
      const group = STAGE_GROUPS.find((g) => g.key === stageGroup);
      if (!group) {
        return (
          <div className="ob-cards">
            {STAGE_GROUPS.map((g) => (
              <button
                key={g.key}
                type="button"
                className="ob-card"
                onClick={() => {
                  // Stage 0 has exactly one stage -- asking again would be noise.
                  if (g.stages.length === 1) {
                    answer(g.stages[0].name, { stage_group: g.group });
                  } else {
                    setStageGroup(g.key);
                  }
                }}
              >
                <span className="ob-card-t">{g.label}</span>
                <span className="ob-card-s">{g.hint}</span>
              </button>
            ))}
          </div>
        );
      }
      return (
        <div className="ob-cards">
          <button type="button" className="ob-back" onClick={() => setStageGroup(null)}>
            ← {group.label}
          </button>
          {group.stages.map((s) => (
            <button
              key={s.name}
              type="button"
              className="ob-card"
              onClick={() => answer(s.name, { stage_group: group.group })}
            >
              <span className="ob-card-t">{s.name}</span>
              <span className="ob-card-s">{s.blurb}</span>
            </button>
          ))}
        </div>
      );
    }

    if (q.type === 'single') {
      return (
        <div className="suggs">
          {q.options.map((o) => (
            <button
              key={optValue(o)}
              type="button"
              className="sugg"
              onClick={() => answer(optValue(o), undefined, optLabel(o))}
            >
              {optLabel(o)}
            </button>
          ))}
        </div>
      );
    }

    if (q.type === 'dropdown') {
      return (
        <div className="ob-drop">
          <label className="sr-only" htmlFor="obSearch">{q.q}</label>
          <input
            id="obSearch"
            ref={searchRef}
            className="ob-search"
            type="text"
            value={search}
            placeholder={q.placeholder}
            onChange={(e) => setSearch(e.target.value)}
            autoComplete="off"
          />
          <div className="ob-drop-list" role="listbox">
            {filteredOptions.length === 0 && (
              <p className="ob-drop-empty">No match — pick “Other”.</p>
            )}
            {filteredOptions.map((o) => (
              <button
                key={optValue(o)}
                type="button"
                role="option"
                aria-selected="false"
                className="ob-drop-opt"
                onClick={() => answer(optValue(o))}
              >
                {optLabel(o)}
              </button>
            ))}
          </div>
        </div>
      );
    }

    if (q.type === 'chips' || q.type === 'multi') {
      return (
        <div className="ob-multi">
          <div className="ob-chips">
            {q.options.map((o) => {
              const v = optValue(o);
              const on = picked.includes(v);
              return (
                <button
                  key={v}
                  type="button"
                  className={`sugg${on ? ' on' : ''}`}
                  aria-pressed={on}
                  disabled={!on && atMax}
                  onClick={() => toggle(v)}
                >
                  {optLabel(o)}
                </button>
              );
            })}
          </div>

          {needsOther && (
            <input
              className="ob-other"
              type="text"
              value={otherText}
              placeholder={q.otherPlaceholder || 'Tell me more…'}
              onChange={(e) => setOtherText(e.target.value)}
            />
          )}

          <div className="ob-multi-foot">
            <span className="ob-count">
              {q.max ? `${picked.length} of ${q.max} chosen` : `${picked.length} chosen`}
            </span>
            <button
              type="button"
              className="btn btn-em ob-continue"
              disabled={picked.length === 0}
              onClick={submitPicked}
            >
              Continue
            </button>
          </div>
        </div>
      );
    }

    /* short / long free text */
    return (
      <div className="chat-input">
        <div className="ci-row">
          <label className="sr-only" htmlFor="profText">Your answer to Ally</label>
          <textarea
            id="profText"
            ref={taRef}
            rows={q.type === 'long' ? 2 : 1}
            placeholder={q.placeholder || 'Type your answer…'}
            value={input}
            onChange={onInput}
            onKeyDown={onKeyDown}
          />
          <button
            className={`ci-btn${voice.status === 'recording' ? ' recording' : ''}`}
            type="button"
            aria-label="Voice input"
            aria-pressed={voice.status === 'recording'}
            disabled={voice.status === 'transcribing'}
            onClick={voice.toggle}
          >
            <svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>
          </button>
          <button className="ci-btn send" type="button" aria-label="Send" onClick={() => answer(input)}>
            <svg viewBox="0 0 24 24"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4z" /></svg>
          </button>
        </div>
        {q.examples && (
          <p className="ci-hint">For example: {q.examples.join(' · ')}</p>
        )}
        {!q.examples && (
          <p className="ci-hint">
            Ally is building your founder profile as you talk · Enter to send
            {q.type === 'long' ? ' · Shift+Enter for a new line' : ''}
          </p>
        )}
      </div>
    );
  }

  return (
    <section className="view chat-view active" id="v-profile">
      <div className="chat">
        <div className="chat-main">
          <div className="chat-scroll" ref={scrollRef} aria-live="polite">
            {messages.map((m, i) => (
              <div key={i} className={`msg ${m.who === 'me' ? 'me' : 'ally'}`}>
                <span className={`m-av ${m.who === 'me' ? 'me' : 'ally'}`}>{m.who === 'me' ? initial : 'A'}</span>
                <div><div className="bubble">{m.text}</div></div>
              </div>
            ))}
            {typing && (
              <div className="typing">
                <span className="m-av ally">A</span>
                <div className="bubble"><span className="td"><span /><span /><span /></span></div>
              </div>
            )}
          </div>

          {renderControl()}
          {!isText && q && (
            <p className="ci-hint ob-standalone-hint">Ally is building your founder profile as you talk</p>
          )}
        </div>

        <aside className="kg-panel prof-panel" aria-label="Your Founder DNA">
          <h3>Building Your Founder DNA</h3>
          <p className="kp-sub">Every answer helps Ally understand how you think, build, and lead.</p>
          <div className="understanding">
            <div className="und-row"><span className="und-l">Understanding</span><span className="und-pct">{undDisplay}%</span></div>
            <div className="und-bar"><i style={{ width: `${undTarget}%` }} /></div>
            <div className={`und-note${undUp ? ' up' : ''}`}>{undNote}</div>
          </div>

          <div className="prof-fields">
            <div className={`pf-empty${emptyGone ? ' gone' : ''}`}>
              <span className="pf-empty-ic"><span className="lv" /></span>
              <span className="pf-empty-t">I’m listening…</span>
              <span className="pf-empty-s">Your Founder DNA appears here as you answer.</span>
            </div>

            {SECTIONS.map((sec) => {
              const qs = QUESTIONS.filter((x) => x.section === sec.key);
              return (
                <div key={sec.key} className={`pfg${sectionsOpen[sec.key] ? ' open' : ''}`}>
                  <div className="pfg-head">
                    <span className="pfg-t">{sec.label}</span>
                    <span className="pfg-c">{sectionCount(sec.key)} / {qs.length}</span>
                  </div>
                  <div className="pfg-rows">
                    {qs.map((item) => {
                      const f = fields[item.key];
                      const status = f?.status;
                      const cls = 'pf' + (status === 'on' ? ' on' : '') + (status === 'building' ? ' building' : '') + (f?.justin ? ' justin' : '');
                      const val = status === 'on' ? f.text : status === 'building' ? 'Building…' : 'Waiting…';
                      const tag = status === 'on' ? 'Learned' : status === 'building' ? 'Building' : '';
                      return (
                        <div key={item.key} className={cls}>
                          <div className="pf-l">
                            <span className="pf-ck"><svg viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5" /></svg></span>
                            {item.label}
                            <span className="pf-tag">{tag}</span>
                          </div>
                          <div className="pf-v">{val}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}

            <div className={`pf-complete${complete ? ' on' : ''}`}>
              <span className="pf-complete-ck"><svg viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5" /></svg></span>
              <span className="pf-complete-t">Founder Profile Complete</span>
              <span className="pf-complete-s">Everything Ally learned here will guide every future conversation.</span>
            </div>
          </div>
        </aside>
      </div>

      {showBar && (
        <div className="j-bar on" style={{ position: 'fixed', bottom: 0, left: 0, width: '100%', zIndex: 100 }}>
          <span className="jb-note">Your Founder DNA is ready.</span>
          <div className="spacer" />
          <button className="btn btn-em cta-pulse" type="button" onClick={() => navigate('/guided/tour')}>
            Continue <svg viewBox="0 0 24 24" className="w-4 h-4 inline-block ml-1" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
          </button>
        </div>
      )}
    </section>
  );
}
