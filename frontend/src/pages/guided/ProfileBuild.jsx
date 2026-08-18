import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import { getProfile, saveOnboardingProfile, toGuidedAnswers } from '../../services/profile';
import { readable } from '../../utils/profileDisplay';
import { useVoiceInput } from '../../hooks/useVoiceInput';
import VoiceBars from '../../components/VoiceBars';
import {
  QUESTIONS as ALL_QUESTIONS,
  effectiveQuestions,
  SECTIONS,
  STAGE_GROUPS,
  STAGE_BY_NAME,
} from '../../data/onboardingQuestions';
import { createReplyPicker } from '../../data/onboardingReplies';

/* Onboarding is deliberately offline: every question, option and reply is
   defined in src/data/onboarding*.js. Nothing here calls an LLM. Two network
   calls happen along the way -- see "resume support" below. */

const reduce = typeof window !== 'undefined' && window.matchMedia
  ? window.matchMedia('(prefers-reduced-motion: reduce)').matches : false;

const sleep = (ms) => new Promise((r) => setTimeout(r, reduce ? Math.min(ms, 50) : ms));

/* --- resume support ---------------------------------------------------------
   Each answer is PATCHed to its owning /profile/* section as soon as it's
   given (see `answer()`), not batched up for the one call `finish()` used to
   make alone. That's what makes resume cross-device: the backend, not this
   browser, is the source of truth for how far a founder got, so picking the
   wizard back up on a different device sees the same progress a moment later.
   `finish()` still sends the full batch at the end too -- cheap and
   idempotent, and a backstop for any single in-flight PATCH that didn't land.

   On mount, the founder's actual saved answers are fetched and used to find
   the first still-unanswered question (`isFilled` mirrors the backend's own
   `_is_filled` in profile_progress.py, so the two can't disagree about what
   counts as answered) rather than always starting at question 1. */
function isFilled(value) {
  if (value === null || value === undefined) return false;
  if (typeof value === 'string') return value.trim() !== '';
  if (Array.isArray(value)) return value.length > 0;
  return true;
}

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
  const [yesNo, setYesNo] = useState({});      // 'yesno' type: {itemKey: true|false}

  const scrollRef = useRef(null);
  const taRef = useRef(null);
  const searchRef = useRef(null);
  const qiRef = useRef(0);
  // The founder's actual question list, once path is known -- starts as every
  // question (path unknown = show everything, matching effectiveQuestions'
  // own fail-open convention) and narrows the moment the stage question is
  // answered (see answer()). A ref, not state: index-based navigation
  // (qiRef, askQ(i)) already re-renders on every question change via the
  // state updates that accompany it, so this never needs its own re-render.
  const questionsRef = useRef(ALL_QUESTIONS);
  const awaitingRef = useRef(false);
  const profileRef = useRef({});
  // What each answered field showed in the transcript/side panel (the founder's
  // own words, or an option's label) -- kept separately from `profileRef`
  // because that holds the stored DB value (e.g. 'first_time'), which is never
  // what should be redisplayed. Only used to repaint the side panel on resume.
  const displayRef = useRef({});
  const started = useRef(false);
  const noteTimer = useRef(null);
  /* Abandoning onboarding mid-question used to fire a burst of setState calls on
     an unmounted component: the note timer was only ever cleared by the *next*
     bumpUnd, confirmField's two nested timeouts kept no handle at all, and the
     `await sleep(...)` chains in askQ/answer simply carried on. `alive` gates
     the async continuations; fieldTimers collects the rest. */
  const alive = useRef(true);
  const fieldTimers = useRef([]);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      clearTimeout(noteTimer.current);
      fieldTimers.current.forEach(clearTimeout);
      fieldTimers.current = [];
    };
  }, []);
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
    const { type } = questionsRef.current[activeQ];
    if (type === 'short' || type === 'long' || type === 'url') taRef.current?.focus();
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

  const confirmField = useCallback((key, text, animate) => {
    // Searches the full superset, not questionsRef.current -- keys are unique
    // across both paths, and a pure lookup-by-key has no ordering dependency.
    const q = ALL_QUESTIONS.find((x) => x.key === key);
    setEmptyGone(true);
    setSectionsOpen((o) => ({ ...o, [q.section]: true }));
    if (animate && !reduce) {
      setFields((f) => ({ ...f, [key]: { status: 'building', text } }));
      fieldTimers.current.push(setTimeout(() => {
        if (!alive.current) return;
        setFields((f) => ({ ...f, [key]: { status: 'on', text, justin: true } }));
        fieldTimers.current.push(setTimeout(() => {
          if (!alive.current) return;
          setFields((f) => ({ ...f, [key]: { ...f[key], justin: false } }));
        }, 800));
      }, 560));
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
    setYesNo({});
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
      // Path 1 (Stage 0) never asks `building` -- only `ideaName`, same
      // building_summary column. Path 2 never asks `ideaName`. Exactly one
      // of the two is ever set for a given founder.
      company: profileRef.current.building || profileRef.current.ideaName || prev.company,
      founderProfile: {
        ...(prev?.founderProfile || {}),
        ...profileRef.current,
      },
    }));
    addAlly(`That's everything I need, ${first}. I've got a clear read on you now — give me a moment to form a first impression.`);
    setShowBar(true);
  }, [addAlly, bumpUnd, first, setUser]);

  const askQ = useCallback(async (i) => {
    if (i >= questionsRef.current.length) { finish(); return; }
    const q = questionsRef.current[i];
    setTyping(true);
    await sleep(820); if (!alive.current) return;
    setTyping(false);
    addAlly(q.q);
    if (q.prompt) addAlly(q.prompt);
    present(i);
  }, [addAlly, present, finish]);

  /**
   * Commit an answer.
   * `value`   what gets stored (string, or array for multi-selects)
   * `extra`   fields the question collects alongside its main answer
   * `display` what the founder sees, when that differs from what we store
   */
  const answer = useCallback(async (value, extra, display) => {
    if (!awaitingRef.current) return;
    const isObj = typeof value === 'object' && value !== null && !Array.isArray(value);
    const empty = Array.isArray(value) ? value.length === 0
      : isObj ? Object.keys(value).length === 0
      : !String(value ?? '').trim();
    if (empty) return;

    awaitingRef.current = false;
    setActiveQ(-1);
    const i = qiRef.current;
    const q = questionsRef.current[i];
    // Arrays (multi-select) and plain objects (the 'yesno' reality-check
    // blocks) are stored as-is; everything else is a string.
    const stored = (Array.isArray(value) || isObj) ? value : String(value).trim();

    // The stage answer is the one place a founder's path becomes known --
    // re-filter the remaining question list right here. Every question up to
    // and including 'stage' is shown on both paths (see STAGE_GROUPS'
    // position in onboardingQuestions.js), so no already-assigned index ever
    // shifts under qiRef -- only what comes after this point narrows.
    if (q.type === 'stage') {
      const path = STAGE_BY_NAME[stored]?.path || null;
      questionsRef.current = effectiveQuestions(path);
      profileRef.current.path = path;
    }

    // Single-selects store the database value ('first_time', 'excited') and must
    // never show it -- the founder reads their own words back, not our enum.
    // Object answers (yesno) always arrive with an explicit `display` from the
    // caller -- displayOf() would otherwise stringify to "[object Object]".
    const shown = display || displayOf(stored);
    // Multi-selects read better replied against the raw array (the reply joins
    // them with "and"); everything else replies against what was actually shown.
    const replyInput = Array.isArray(stored) ? stored : shown;

    addMe(shown);
    setInput('');
    if (taRef.current) taRef.current.style.height = 'auto';
    const turn = { [q.key]: stored, ...(extra || {}) };
    profileRef.current = { ...profileRef.current, ...turn };
    displayRef.current = { ...displayRef.current, [q.key]: shown };
    confirmField(q.key, shown, true);
    const nextQi = i + 1;
    qiRef.current = nextQi;
    // Save just this turn's answer immediately -- see the "resume support"
    // note near the top of this file. Fire-and-forget like finish()'s own
    // save: a founder mid-flow should never be blocked on a network round
    // trip between questions, and a dropped PATCH here is still covered by
    // finish()'s full resend at the end (or, if they leave before finishing,
    // the founder simply resumes from the last question that DID land next
    // time -- worse than losing nothing, much better than losing everything).
    saveOnboardingProfile(turn).catch(() => {
      // Silent: the founder is mid-conversation with Ally, not filling out a
      // form, so surfacing a save error here would be a non-sequitur. Nothing
      // is lost from their perspective either way -- see the comment above.
    });

    await sleep(600); if (!alive.current) return;
    // questionsRef.current here is already the post-stage, path-narrowed list
    // when applicable -- the denominator shrinks the moment path is known,
    // rather than staying pinned to a count that includes questions this
    // founder will never be asked.
    const answered = questionsRef.current.filter((x) => profileRef.current[x.key] !== undefined).length;
    bumpUnd(Math.round((answered / questionsRef.current.length) * 100), 'Ally learned something new');

    setTyping(true);
    await sleep(900); if (!alive.current) return;
    setTyping(false);
    if (nextQi < questionsRef.current.length) {
      addAlly(replyRef.current(q.key, replyInput, { first }));
      await sleep(640); if (!alive.current) return;
      askQ(nextQi);
    } else {
      addAlly(replyRef.current(q.key, replyInput, { first }));
      await sleep(640); if (!alive.current) return;
      finish();
    }
  }, [addMe, confirmField, bumpUnd, addAlly, askQ, finish, first]);

  /** Only reachable on a question marked `optional` (currently just the
   * social handle) -- skips without storing anything, so the field simply
   * stays null rather than being answered with an empty string. */
  const skip = useCallback(async () => {
    if (!awaitingRef.current) return;
    awaitingRef.current = false;
    setActiveQ(-1);
    const i = qiRef.current;
    const nextQi = i + 1;
    qiRef.current = nextQi;
    addMe('Skipped');
    setTyping(true);
    await sleep(500); if (!alive.current) return;
    setTyping(false);
    if (nextQi < questionsRef.current.length) askQ(nextQi); else finish();
  }, [addMe, askQ, finish]);

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
      // The founder's ACTUAL saved progress -- not a same-device guess -- so
      // this resumes correctly even on a device that never asked any of these
      // questions before (see the "resume support" note near the top of this
      // file). Fails open to a fresh start: signed-out, offline, or genuinely
      // nothing saved yet all look the same here (empty answers), and all
      // three correctly fall through to starting at question 1 below.
      let answers = {};
      try {
        answers = toGuidedAnswers(await getProfile());
      } catch {
        answers = {};
      }

      // Path is only knowable once the stage question has actually been
      // answered; before that, every question is in scope -- same fail-open
      // convention as effectiveQuestions(null) itself.
      const path = answers.stage ? (STAGE_BY_NAME[answers.stage]?.path || null) : null;
      questionsRef.current = effectiveQuestions(path);
      profileRef.current.path = path;
      const active = questionsRef.current;

      // Live-reproduced: an optional question (currently just the social
      // handle) that was genuinely skipped is indistinguishable from "never
      // reached" by isFilled() alone -- both read as null, forever. Without
      // this, a founder who skipped it got stuck being re-asked it on every
      // single reload, with progress pinned at whatever index it sits at.
      // The fix needs no new persisted state: if ANY later question already
      // has an answer, this one can only have been passed through already
      // (skipped or answered) -- the founder could not have reached that
      // later question otherwise. An optional question with nothing later
      // filled either has genuinely not been reached yet, and is correctly
      // asked.
      const isResolved = (x, i) =>
        isFilled(answers[x.key]) ||
        (x.optional && active.slice(i + 1).some((later) => isFilled(answers[later.key])));

      const firstUnanswered = active.findIndex((x, i) => !isResolved(x, i));
      // -1 means every mapped field is already filled/resolved -- treat as
      // done rather than looping past the end of the list. GuidedLayout/Login
      // already redirect a founder whose profile is fully complete straight
      // to /app, so reaching this component at all should mean there's a
      // real gap; this only guards the rare edge where that check raced this
      // fetch.
      const startAt = firstUnanswered === -1 ? active.length : firstUnanswered;

      if (startAt > 0) {
        const filled = active.filter((x) => isFilled(answers[x.key]));
        profileRef.current = {
          ...profileRef.current,
          ...Object.fromEntries(filled.map((x) => [x.key, answers[x.key]])),
        };
        displayRef.current = Object.fromEntries(filled.map((x) => [
          x.key,
          // readable() stringifies an object to "[object Object]" -- the
          // 'yesno' blocks need the same per-item Yes/No summary the live
          // submit path already builds.
          x.type === 'yesno' && answers[x.key]
            ? x.items.map((it) => `${it.text}: ${answers[x.key][it.key] ? 'Yes' : 'No'}`).join(' · ')
            : readable(x.key, answers[x.key]),
        ]));
        qiRef.current = startAt;

        setEmptyGone(true);
        setFields(Object.fromEntries(
          filled.map((x) => [x.key, { status: 'on', text: displayRef.current[x.key] }]),
        ));
        setSectionsOpen(Object.fromEntries(filled.map((x) => [x.section, true])));
        setUndTarget(Math.round((startAt / active.length) * 100));

        // Live-reproduced: the side panel above already replays correctly (it
        // reads the founder's real answers), but the actual conversation
        // never did -- a reload showed only the two generic "welcome back"
        // messages with no sign the prior conversation had happened at all.
        // Synthesises the same alternating ally-question/founder-answer
        // bubbles the live flow itself builds, in `active`'s fixed order --
        // there is no per-turn timestamp to replay against (onboarding
        // answers are flat columns on founders, not a turn log the way
        // diagnosis answers are), so this reconstructs what was asked and
        // said, not a literal scrollback.
        setMessages(filled.flatMap((x) => {
          const turn = [{ who: 'ally', text: x.q }];
          if (x.prompt) turn.push({ who: 'ally', text: x.prompt });
          turn.push({ who: 'me', text: displayRef.current[x.key] });
          return turn;
        }));

        addAlly(`Welcome back, ${first} — picking up right where we left off.`);
        await sleep(700);
        askQ(startAt);
        return;
      }

      addAlly(`Welcome to GoXL AI, ${first}.`);
      await sleep(700); if (!alive.current) return;
      addAlly('Every entrepreneur has a unique story, a different challenge, and a bold vision for the future. In just a few minutes, help me understand yours.');
      await sleep(900); if (!alive.current) return;
      askQ(0);
    })();
  }, [introReady]);

  const q = activeQ >= 0 ? questionsRef.current[activeQ] : null;
  const isText = q && (q.type === 'short' || q.type === 'long' || q.type === 'url');

  /** A light heuristic, not a validator -- the backend's _validate_social_url
   * is the real check. This exists only to catch the case a founder types a
   * skip-like word ("skip", "n/a", "-", "none") into the text box instead of
   * clicking the actual Skip button below it: live-reproduced, the literal
   * word "Skip" got submitted as a real answer and only failed at the very
   * end (finish()'s batch save), silently and far too late to mean anything
   * to the founder. Anything with no dot at all cannot be a real domain
   * either way, so there is nothing lost by treating it as a skip instead of
   * a doomed save attempt. */
  const looksLikeUrl = (text) => {
    const s = text.trim();
    return s.length > 0 && !/\s/.test(s) && s.includes('.');
  };

  const submitFreeText = (text) => {
    if (q?.type === 'url' && q.optional && !looksLikeUrl(text)) { skip(); return; }
    answer(text);
  };

  // Enter sends on every free-text question, long ones included -- gating this
  // on type === 'short' meant Enter silently did nothing on the five long-text
  // questions, which is most of them. Shift+Enter still starts a new line.
  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submitFreeText(taRef.current.value);
    }
  };
  const sizeTa = () => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
  };

  const onInput = (e) => {
    setInput(e.target.value);
    sizeTa();
  };

  // Profile-build is pre-chat onboarding, not the paid chat surface -- voice
  // here is ungated, same product decision as the diagnosis mic (context:
  // 'diagnosis' matches the backend's VOICE_DIAGNOSIS feature, free on every
  // plan).
  const voice = useVoiceInput({
    context: 'diagnosis',
    onTranscribed: (text) => {
      // Sizing and focus both wait for the effect below: at this point the
      // field is still display:none (status is 'transcribing'), where
      // scrollHeight reads 0 and focus() is a no-op.
      setInput((prev) => (prev ? `${prev} ${text}` : text));
    },
    onError: () => showToast('Could not access the microphone — check your browser permissions.'),
  });

  /* See AllyChat for the same fix: measure (and focus) only once React has
     rendered the dictated text and the textarea is visible again. */
  useEffect(() => {
    if (voice.status !== 'idle') return;
    sizeTa();
    if (input) taRef.current?.focus();
  }, [input, voice.status]);

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
    if (q.otherField) {
      // The "other" option stays in the list as the marker that there is
      // more; the free text it reveals goes to its own column rather than
      // being appended as a pseudo-chip, so the same words are never stored
      // in two places. Applies to both 'chips' and 'multi' -- live-reproduced
      // gap this redesign fixes: current_challenges already offered an
      // "Other" option with nowhere for the typed text to go.
      answer(picked, other ? { [q.otherField]: other } : undefined);
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
    questionsRef.current.filter((x) => x.section === key && fields[x.key]?.status === 'on').length;

  const needsOther = (q?.type === 'chips' || q?.type === 'multi') && !!q?.otherValue && picked.includes(q.otherValue);
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
                {/* The canonical label (Stage 0 / Stage 0→1 / Stage 1→10+),
                    always visible alongside the friendly description. */}
                <span className="ob-card-tag">{g.group}</span>
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
              {/* Same group tag repeated here -- picking a specific stage
                  should never lose sight of which of the 3 groups it's in. */}
              <span className="ob-card-tag">{group.group}</span>
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
      // Picking the "other" option doesn't answer immediately -- it waits for
      // the free text behind it (spec: "If Other selected -> show free-text
      // input"), reusing `picked`/`otherText` the same way chips/multi do
      // rather than inventing separate state for a third control.
      const otherPending = q.otherValue && picked[0] === q.otherValue;
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
            disabled={otherPending}
          />
          {!otherPending && (
            <div className="ob-drop-list" role="listbox">
              {filteredOptions.length === 0 && (
                <p className="ob-drop-empty">No match — pick “Other”.</p>
              )}
              {filteredOptions.map((o) => {
                const v = optValue(o);
                return (
                  <button
                    key={v}
                    type="button"
                    role="option"
                    aria-selected="false"
                    className="ob-drop-opt"
                    onClick={() => (q.otherValue && v === q.otherValue ? setPicked([v]) : answer(v))}
                  >
                    {optLabel(o)}
                  </button>
                );
              })}
            </div>
          )}
          {otherPending && (
            <div className="ob-multi">
              <input
                className="ob-other"
                type="text"
                aria-label={q.otherPlaceholder || 'Tell us more'}
                value={otherText}
                placeholder={q.otherPlaceholder || 'Tell me more…'}
                onChange={(e) => setOtherText(e.target.value)}
                autoFocus
              />
              <div className="ob-multi-foot">
                <button type="button" className="ob-back" onClick={() => { setPicked([]); setOtherText(''); }}>
                  ← Back
                </button>
                <button
                  type="button"
                  className="btn btn-em ob-continue"
                  disabled={!otherText.trim()}
                  onClick={() => {
                    const text = otherText.trim();
                    answer(q.otherValue, q.otherField ? { [q.otherField]: text } : undefined, text);
                  }}
                >
                  Continue
                </button>
              </div>
            </div>
          )}
        </div>
      );
    }

    if (q.type === 'yesno') {
      const allAnswered = q.items.every((it) => yesNo[it.key] !== undefined);
      return (
        <div className="ob-yesno">
          {q.items.map((it) => (
            <div key={it.key} className="ob-yesno-row">
              <div className="ob-yesno-text">
                <span className="ob-yesno-claim">{it.text}</span>
                <span className="ob-yesno-sub">{it.sub}</span>
              </div>
              <div className="ob-yesno-btns">
                <button
                  type="button"
                  className={`sugg${yesNo[it.key] === true ? ' on' : ''}`}
                  aria-pressed={yesNo[it.key] === true}
                  onClick={() => setYesNo((y) => ({ ...y, [it.key]: true }))}
                >
                  Yes
                </button>
                <button
                  type="button"
                  className={`sugg${yesNo[it.key] === false ? ' on' : ''}`}
                  aria-pressed={yesNo[it.key] === false}
                  onClick={() => setYesNo((y) => ({ ...y, [it.key]: false }))}
                >
                  No
                </button>
              </div>
            </div>
          ))}
          <div className="ob-multi-foot">
            <span className="ob-count">{Object.keys(yesNo).length} of {q.items.length} answered</span>
            <button
              type="button"
              className="btn btn-em ob-continue"
              disabled={!allAnswered}
              onClick={() => {
                const display = q.items.map((it) => `${it.text}: ${yesNo[it.key] ? 'Yes' : 'No'}`).join(' · ');
                answer(yesNo, undefined, display);
              }}
            >
              Continue
            </button>
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
              aria-label={q.otherPlaceholder || 'Tell us more'}
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

    /* short / long / url free text */
    return (
      <div className="chat-input">
        <div className={`ci-row${voice.status !== 'idle' ? ' voice-live' : ''}`}>
          {voice.status !== 'idle' && (
            <VoiceBars
              getLevel={voice.getLevel}
              label={voice.status === 'transcribing' ? 'Transcribing…' : 'Listening…'}
            />
          )}
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
            className={`ci-btn mic${voice.status === 'recording' ? ' recording' : ''}`}
            type="button"
            aria-label="Voice input"
            aria-pressed={voice.status === 'recording'}
            disabled={voice.status === 'transcribing'}
            onClick={voice.toggle}
          >
            <svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>
          </button>
          <button className="ci-btn send" type="button" aria-label="Send" onClick={() => submitFreeText(input)}>
            <svg viewBox="0 0 24 24"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4z" /></svg>
          </button>
        </div>
        {q.optional && (
          <button type="button" className="ob-skip" onClick={skip}>
            Skip — I'd rather not share
          </button>
        )}
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
      {/* This step had no h1 at all — every sibling guided page has one, so a
          screen-reader user landing here got no page title. */}
      <h1 className="sr-only">Building your founder profile</h1>
      <div className="chat">
        <div className="chat-main">
          {/* aria-live alone announced nothing useful without a role or a name. */}
          <div className="chat-scroll" ref={scrollRef} role="log" aria-live="polite" aria-label="Your conversation with Ally">
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
          <h2>Building Your Founder DNA</h2>
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
              // The founder's own path-narrowed list -- a Path 1 founder never
              // sees a "Waiting…" row for a question (revenue, business
              // reality, …) they will never actually be asked.
              const qs = questionsRef.current.filter((x) => x.section === sec.key);
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
