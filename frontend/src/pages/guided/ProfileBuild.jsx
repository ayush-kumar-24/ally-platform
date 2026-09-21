import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import {
  clearOnboardingAnswers,
  getProfile,
  saveOnboardingProfile,
  toGuidedAnswers,
} from '../../services/profile';
import { readable } from '../../utils/profileDisplay';
import { useVoiceInput } from '../../hooks/useVoiceInput';
import useAutoScroll from '../../hooks/useAutoScroll';
import VoiceBars from '../../components/VoiceBars';
import MessageActions from '../../components/MessageActions';
import {
  QUESTIONS as ALL_QUESTIONS,
  activeOptions,
  askableByKey,
  activeParts,
  effectiveQuestions,
  questionCount,
  questionKeys,
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

/* An option is a bare string, a {label,value} card, or a {value,paths} entry
   that is path-filtered but displayed verbatim -- the last has no separate
   label, so it falls back to its own value rather than rendering `undefined`. */
const optLabel = (o) => (typeof o === 'string' ? o : (o.label ?? o.value));
const optValue = (o) => (typeof o === 'string' ? o : o.value);

/** The control awaiting an answer: a plain question, or a group's active part. */
function controlFor(question, path, idx) {
  if (!question) return null;
  if (question.type !== 'group') return question;
  return activeParts(question, path)[idx] || null;
}

/* The DNA side panel lists FACTS, not questions -- a group's parts each earn
   their own row (Stage, Experience, Monthly Revenue) even though the three are
   one question in the flow. Parts inherit their group's section. */
function panelRowsFor(questions, path) {
  return questions.flatMap((x) => (
    x.type === 'group'
      ? activeParts(x, path).map((part) => ({ ...part, section: x.section }))
      : [x]
  ));
}

/** What the founder sees in the DNA panel and in their own chat bubble. */
const displayOf = (value) => (Array.isArray(value) ? value.join(', ') : String(value ?? ''));

/* The bubbles for a set of already-answered rows, in question order: Ally's
   question (and its prompt), then the founder's own answer.

   Every 'me' bubble carries the KEY of the fact it answers. That is what makes
   an answer editable afterwards -- without it a bubble is just text, and there
   is no way back from "the founder tapped Edit on this line" to "this is their
   monthly revenue". The live flow tags its bubbles the same way as it goes.

   Used on resume and again when a changed stage re-plans the flow, because
   there is no per-turn log to replay: onboarding answers are flat columns on
   founders, not a turn log the way diagnosis answers are. */
function transcriptFor(rows, displays) {
  return rows.flatMap((x) => {
    const turn = [{ who: 'ally', text: x.q }];
    if (x.prompt) turn.push({ who: 'ally', text: x.prompt });
    turn.push({ who: 'me', text: displays[x.key], key: x.key });
    return turn;
  });
}

/* The index of the first question on `path` that still needs an answer, or -1
   when every one of them is resolved.

   Live-reproduced: an optional question (currently just the social handle)
   that was genuinely skipped is indistinguishable from "never reached" by
   isFilled() alone -- both read as null, forever. Without the second clause a
   founder who skipped it got stuck being re-asked it on every single reload.
   The fix needs no new persisted state: if ANY later question already has an
   answer, this one can only have been passed through already (skipped or
   answered) -- the founder could not have reached that later question
   otherwise. An optional question with nothing later filled either has
   genuinely not been reached yet, and is correctly asked.

   `from` skips questions the flow is already past. In a first run through
   that changes nothing -- nothing ahead of the frontier is ever answered --
   but it stops being the same thing once a changed stage has re-planned the
   flow: the founder is put back at the first gap, and questions AFTER that
   gap that survived the re-plan already have answers. Marching blindly on
   asked those again, and left two contradictory bubbles standing for the one
   question. */
function firstUnresolved(active, path, answers, from = 0) {
  const anyFilled = (x) => questionKeys(x, path).some((k) => isFilled(answers[k]));
  const allFilled = (x) => questionKeys(x, path).every((k) => isFilled(answers[k]));
  return active.findIndex((x, i) => i >= from && !(
    allFilled(x) || (x.optional && active.slice(i + 1).some(anyFilled))
  ));
}

/* Where to pick the flow back up: which question, which part of it, and the
   parts of that question already answered -- seeded back into the group's
   buffer so the group still commits whole. A founder who answered the stage
   but left before the experience card must not be asked their stage again.
   startAt === active.length means there is nothing left to ask. */
function resumePoint(active, path, answers) {
  const found = firstUnresolved(active, path, answers);
  const startAt = found === -1 ? active.length : found;
  const question = active[startAt];
  const parts = question && question.type === 'group' ? activeParts(question, path) : [];
  const startPart = Math.max(0, parts.findIndex((pt) => !isFilled(answers[pt.key])));
  const buf = Object.fromEntries(
    parts.slice(0, startPart)
      .filter((pt) => isFilled(answers[pt.key]))
      .map((pt) => [pt.key, answers[pt.key]]),
  );
  return { startAt, startPart, buf };
}

export default function ProfileBuild() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  /* Arrived from the profile page's completeness ring rather than from
     onboarding itself -- see FounderProfile. Same screen, same answers, same
     edit affordance; it only changes what Ally says at the end and where the
     Continue button goes, because a founder who came here to check something
     is not partway through signing up. */
  const review = searchParams.get('review') === '1';
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
  /* The answer currently being CHANGED, if any: { key, q, label }. State, not
     just a ref, because the banner above the control and the per-bubble Edit
     buttons both render from it. editRef holds the flow position to return to
     once the edit is committed or cancelled, for the same reason partIdxRef
     shadows partIdx -- commitEdit reads it inside a useCallback, where the
     state value would be a stale capture. */
  const [editing, setEditing] = useState(null);
  const editRef = useRef(null);

  /* Which part of a `group` question is being asked. A ref shadows it because
     answer() reads it inside a useCallback, where the state value would be a
     stale capture; the state copy exists only so the control re-renders. */
  const [partIdx, setPartIdx] = useState(0);
  const partIdxRef = useRef(0);
  /* A group's answers accumulate here and are committed together when its last
     part is answered, so one question means one commit and one panel update. */
  const groupBufRef = useRef({});

  /* Follows the transcript as it grows. The answer control mounting under the
     last question, and each bubble's entry animation, both add height after
     the message itself is committed -- the old one-shot jump ran before that
     and left the newest question sitting below the fold. */
  const scrollRef = useAutoScroll([messages, typing, activeQ]);
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
  /* The founder's path, once the stage answer reveals it. Read by the option
     and part filters during render; kept as a ref rather than state because
     every write to it is immediately followed by a setActiveQ that re-renders. */
  const pathRef = useRef(null);
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


  /* Focus the answer control as each question appears. Someone answering
     thirteen questions in a row should never have to click into the box first.
     This lives here rather than in present() because the control only mounts
     once activeQ has been set. */
  useEffect(() => {
    if (activeQ < 0) return;
    const ctl = controlFor(questionsRef.current[activeQ], pathRef.current, partIdx);
    if (!ctl) return;
    const { type } = ctl;
    if (type === 'short' || type === 'long' || type === 'url') taRef.current?.focus();
    else if (type === 'dropdown') searchRef.current?.focus();
  }, [activeQ, partIdx]);

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
  /* `key` is the fact this bubble answers -- see transcriptFor. Every founder
     bubble carries one so the Edit button under it knows what it is editing. */
  const addMe = useCallback((text, key) => setMessages((m) => [...m, { who: 'me', text, key }]), []);

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
    /* Looks up the full superset rather than questionsRef.current -- keys are
       unique across both paths, and a pure lookup-by-key has no ordering
       dependency. It has to search the ASKED questions, though, not the eleven
       top-level ones: stage, experience and revenue are PARTS of Q3's group,
       so `QUESTIONS.find((x) => x.key === 'stage')` came back undefined and
       `q.section` below threw the moment a founder picked their stage --
       taking down the entire onboarding screen mid-flow. askableByKey()
       descends into a group's parts and gives them their group's section.

       Still optional-chained: which panel section to open is a presentation
       detail, and it must never again be the reason a founder loses the
       screen they are halfway through. */
    const q = askableByKey(key);
    setEmptyGone(true);
    if (q?.section) setSectionsOpen((o) => ({ ...o, [q.section]: true }));
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

  /** Clear the per-control working state. Runs between a group's parts too,
   *  where the question index deliberately does NOT change. */
  const resetControls = useCallback(() => {
    setStageGroup(null);
    setPicked([]);
    setOtherText('');
    setSearch('');
    setInput('');
    setYesNo({});
  }, []);

  const present = useCallback((i, startPart = 0, buf = {}) => {
    resetControls();
    partIdxRef.current = startPart;
    setPartIdx(startPart);
    // Resuming mid-group seeds the buffer with the parts already answered, so
    // the commit at the end of the group still writes the whole question.
    groupBufRef.current = buf;
    awaitingRef.current = true;
    setActiveQ(i);
  }, [resetControls]);

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
      // Q4's name part. Path 1 labels an idea, Path 2 names a product -- two
      // mutually exclusive parts writing one key, so this reads one key.
      company: profileRef.current.buildingName || prev.company,
      founderProfile: {
        ...(prev?.founderProfile || {}),
        ...profileRef.current,
      },
    }));
    addAlly(review
      ? `That's everything you've told me, ${first}. Tap Edit under any answer to change it — I'll save it as you go.`
      : `That's everything I need, ${first}. I've got a clear read on you now — give me a moment to form a first impression.`);
    setShowBar(true);
  }, [addAlly, bumpUnd, first, setUser, review]);

  const askQ = useCallback(async (i, startPart = 0, buf = {}) => {
    if (i >= questionsRef.current.length) { finish(); return; }
    const q = questionsRef.current[i];
    setTyping(true);
    await sleep(820); if (!alive.current) return;
    setTyping(false);
    if (q.type === 'group') {
      const parts = activeParts(q, pathRef.current);
      const first = parts[startPart];
      // The group's own headline is worth saying only when it adds something:
      // not when it repeats the first part's wording (Q3), and not when the
      // path has narrowed the group to a single part, where the headline would
      // be introducing a set of one -- and, for Q9 on Path 1, addressing a
      // business that does not exist.
      if (q.q && parts.length > 1 && first && q.q !== first.q && startPart === 0) addAlly(q.q);
      if (first) {
        addAlly(first.q);
        if (first.prompt) addAlly(first.prompt);
      }
    } else {
      addAlly(q.q);
      if (q.prompt) addAlly(q.prompt);
    }
    present(i, startPart, buf);
  }, [addAlly, present, finish]);

  /* --- changing an answer already given -------------------------------------
     Live-reported, and the reason this exists at all: a founder who picked the
     wrong option had no way back. Onboarding wrote the answer straight to the
     profile and moved on, and the only bubble actions were Copy. "If any user
     selected something wrong then there's no chance they can change it."

     Deliberately NOT folded into answer(). answer() is flow control: it
     advances the part, the question index, the progress bar and the reply Ally
     gives next. An edit changes one fact and puts the founder back exactly
     where they were, which is the opposite of all of that. */

  /**
   * Commit an edit, in place of the bubble it belongs to.
   *
   * `opts.clear` is the optional-question case (currently just the social
   * handle): the founder used Skip while editing, which means "take what I
   * said before back off my profile", not "store an empty string".
   */
  const commitEdit = useCallback(async (value, extra, display, opts = {}) => {
    const ed = editRef.current;
    if (!ed) return;
    editRef.current = null;
    setEditing(null);
    awaitingRef.current = false;
    setActiveQ(-1);
    resetControls();

    const ctl = ed.ctl;
    const isObj = typeof value === 'object' && value !== null && !Array.isArray(value);
    const stored = opts.clear ? null
      : (Array.isArray(value) || isObj) ? value : String(value).trim();
    const shown = opts.clear ? 'Skipped' : (display || displayOf(stored));

    if (opts.clear) {
      delete profileRef.current[ctl.key];
    } else {
      profileRef.current = { ...profileRef.current, [ctl.key]: stored, ...(extra || {}) };
    }
    displayRef.current = { ...displayRef.current, [ctl.key]: shown };
    /* No build animation on an edit: that row is already on the panel, and
       sending it back through "Building…" reads as though Ally were learning
       it for the first time. */
    confirmField(ctl.key, shown, false);
    /* The founder's own bubble is REWRITTEN rather than a second one appended.
       Two bubbles answering the same question, one of them no longer true, is
       exactly the confusion an edit is supposed to remove. */
    setMessages((ms) => ms.map((m) => (
      m.who === 'me' && m.key === ctl.key ? { ...m, text: shown } : m
    )));

    /* Unlike a mid-flow answer, an edit is told whether it saved. Mid-flow a
       dropped PATCH costs nothing a founder would notice -- finish() resends
       everything, and resume covers the rest. An edit is a deliberate act with
       a specific expectation, so silently not saving it is the one outcome
       worth interrupting for. */
    const saved = opts.clear
      ? clearOnboardingAnswers([ctl.key])
      : saveOnboardingProfile({ [ctl.key]: stored, ...(extra || {}) })
        .then((result) => { if (!result.ok) throw new Error(result.failed.join(', ')); });
    saved
      .then(() => showToast('Updated.'))
      .catch(() => showToast("That didn't save — check your connection and try again."));

    /* Changing the STAGE re-plans the rest of the flow, because the stage is
       the only answer either path branches on. The founder chose this
       deliberately, so the honest response is to keep every answer that still
       applies, let go of the ones that cannot apply any more, and ask whatever
       the new stage newly makes relevant. */
    let cleared = null;
    if (ctl.type === 'stage' && !opts.clear) {
      const path = STAGE_BY_NAME[stored]?.path || null;
      if (path !== pathRef.current) {
        const before = panelRowsFor(questionsRef.current, pathRef.current);
        pathRef.current = path;
        questionsRef.current = effectiveQuestions(path);
        profileRef.current.path = path;
        const after = panelRowsFor(questionsRef.current, path);
        const live = new Set(after.map((x) => x.key));

        // Whole answers with no question behind them on the new path.
        const gone = before.filter((x) => !live.has(x.key) && x.key in profileRef.current);
        /* ...and single OPTIONS that presuppose an operating business, inside
           answers whose question itself survived. Leaving "Cash flow" in the
           challenges of a founder who has moved back to exploring an idea is
           not a harmless leftover: the diagnosis reads it as a real signal.
           Same rule the option-level `paths` filter applies when asking. */
        const trimmed = [];
        after.forEach((row) => {
          if (row.type !== 'chips' && row.type !== 'multi') return;
          const current = profileRef.current[row.key];
          if (!Array.isArray(current) || current.length === 0) return;
          const allowed = new Set(activeOptions(row, path).map(optValue));
          /* Only a value this question KNOWS and no longer offers is dropped.
             Anything unrecognised is left exactly where it is: a value can
             reach this row from somewhere other than these chips (a founder's
             own words through the summary screen, a column filled before an
             option list was last edited), and silently deleting a founder's
             answer because it is not on a list we recognise would be a far
             worse bug than the leftover this is here to clean up. */
          const known = new Set((row.options || []).map(optValue));
          const kept = current.filter((v) => allowed.has(v) || !known.has(v));
          if (kept.length !== current.length) trimmed.push([row, kept]);
        });

        const emptied = trimmed.filter(([, kept]) => kept.length === 0).map(([row]) => row);
        const clearKeys = gone.concat(emptied).map((x) => x.key);
        gone.concat(emptied).forEach((x) => {
          delete profileRef.current[x.key];
          delete displayRef.current[x.key];
        });
        trimmed.filter(([, kept]) => kept.length > 0).forEach(([row, kept]) => {
          profileRef.current[row.key] = kept;
          displayRef.current[row.key] = displayOf(kept);
        });

        if (clearKeys.length) {
          clearOnboardingAnswers(clearKeys).catch(() => showToast(
            "Your stage is saved, but clearing the answers it replaced didn't go through.",
          ));
        }
        const rewrites = Object.fromEntries(
          trimmed.filter(([, kept]) => kept.length > 0).map(([row, kept]) => [row.key, kept]),
        );
        if (Object.keys(rewrites).length) saveOnboardingProfile(rewrites).catch(() => {});

        /* Repaint the panel and the transcript against the NEW question list,
           rather than leaving rows and bubbles standing for questions this
           founder is no longer asked. */
        const standing = after.filter((x) => displayRef.current[x.key] !== undefined);
        setFields(Object.fromEntries(
          standing.map((x) => [x.key, { status: 'on', text: displayRef.current[x.key] }]),
        ));
        setSectionsOpen(Object.fromEntries(standing.map((x) => [x.section, true])));
        setMessages(transcriptFor(standing, displayRef.current));
        cleared = gone.concat(emptied).map((x) => x.label);
      }
    }

    const active = questionsRef.current;
    const answered = active.filter(
      (x) => questionKeys(x, pathRef.current).every((k) => isFilled(profileRef.current[k])),
    ).length;
    bumpUnd(Math.round((answered / questionCount(pathRef.current)) * 100), 'Answer updated');

    if (cleared) {
      await sleep(600); if (!alive.current) return;
      addAlly("Got it — that changes where you are, so let me re-plan the rest.");
      if (cleared.length) {
        addAlly(`These don't apply at your new stage, so I've taken them off your profile: ${cleared.join(', ')}.`);
      }
      const { startAt, startPart, buf } = resumePoint(active, pathRef.current, profileRef.current);
      if (startAt < active.length) {
        qiRef.current = startAt;
        askQ(startAt, startPart, buf);
        return;
      }
      addAlly('Everything else you told me still applies — there is nothing new to ask.');
      if (!complete) finish();
      return;
    }

    /* No re-plan: put them back exactly where the edit interrupted them. A
       founder editing question 2 mid-flow returns to question 7, still
       awaiting the same answer, with the group's buffer intact. */
    if (ed.wasAwaiting && ed.wasActiveQ >= 0) {
      groupBufRef.current = ed.returnBuf;
      partIdxRef.current = ed.returnPart;
      setPartIdx(ed.returnPart);
      awaitingRef.current = true;
      setActiveQ(ed.wasActiveQ);
    }
  }, [addAlly, askQ, bumpUnd, complete, confirmField, finish, resetControls, showToast]);

  /** Open the control for an answer already given, seeded with it. */
  const startEdit = useCallback((key) => {
    if (!key || editRef.current) return;
    const active = questionsRef.current;
    let qi = -1;
    let pi = 0;
    for (let i = 0; i < active.length; i += 1) {
      const x = active[i];
      if (x.type === 'group') {
        const at = activeParts(x, pathRef.current).findIndex((pt) => pt.key === key);
        if (at >= 0) { qi = i; pi = at; break; }
      } else if (x.key === key) { qi = i; break; }
    }
    // Not a question this founder is asked any more (their stage changed since
    // the bubble was written). Nothing to edit; the bubble is already gone.
    if (qi < 0) return;
    const ctl = controlFor(active[qi], pathRef.current, pi);
    if (!ctl) return;

    editRef.current = {
      ctl,
      returnPart: partIdxRef.current,
      returnBuf: groupBufRef.current,
      wasAwaiting: awaitingRef.current,
      wasActiveQ: activeQ,
    };
    setEditing({ key, q: ctl.q, label: ctl.label });

    resetControls();
    // Seeded with what they said before, so an edit is a correction rather
    // than answering the question again from nothing.
    const previous = profileRef.current[ctl.key];
    if (ctl.type === 'chips' || ctl.type === 'multi') {
      setPicked(Array.isArray(previous) ? previous : (previous ? [previous] : []));
      if (ctl.otherField) setOtherText(profileRef.current[ctl.otherField] || '');
    } else if (ctl.type === 'yesno') {
      if (previous && typeof previous === 'object') setYesNo(previous);
    } else if (ctl.type === 'short' || ctl.type === 'long' || ctl.type === 'url') {
      setInput(typeof previous === 'string' ? previous : '');
    }

    partIdxRef.current = pi;
    setPartIdx(pi);
    awaitingRef.current = true;
    setActiveQ(qi);
  }, [activeQ, resetControls]);

  /** Leave the answer as it was and go back to the flow. */
  const cancelEdit = useCallback(() => {
    const ed = editRef.current;
    if (!ed) return;
    editRef.current = null;
    setEditing(null);
    resetControls();
    groupBufRef.current = ed.returnBuf;
    partIdxRef.current = ed.returnPart;
    setPartIdx(ed.returnPart);
    awaitingRef.current = ed.wasAwaiting;
    setActiveQ(ed.wasActiveQ);
  }, [resetControls]);

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

    /* An edit changes one fact and returns; it does not advance the flow.
       Dispatched here rather than in each of the eight controls, so every
       control is editable by construction and none of them has to know. */
    if (editRef.current) { await commitEdit(value, extra, display); return; }

    awaitingRef.current = false;
    setActiveQ(-1);
    const i = qiRef.current;
    const q = questionsRef.current[i];
    const isGroup = q.type === 'group';
    // What was actually just answered: the question itself, or the group's
    // current part. Everything below keys off this, not off `q`.
    const ctl = controlFor(q, pathRef.current, partIdxRef.current);
    // Arrays (multi-select) and plain objects (the 'yesno' reality-check
    // blocks) are stored as-is; everything else is a string.
    const stored = (Array.isArray(value) || isObj) ? value : String(value).trim();

    // The stage answer is the one place a founder's path becomes known --
    // re-filter the remaining question list right here. Every question at or
    // before the one holding the stage part is shown on both paths (see
    // onboardingQuestions.js), so no already-assigned index ever shifts under
    // qiRef -- only what comes after this point narrows. The group's own part
    // list narrows too, which is what drops the revenue part for Stage 0.
    if (ctl.type === 'stage') {
      const path = STAGE_BY_NAME[stored]?.path || null;
      pathRef.current = path;
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

    addMe(shown, ctl.key);
    setInput('');
    if (taRef.current) taRef.current.style.height = 'auto';

    // Each part lands in the DNA panel as it is given -- the panel lists facts
    // learned, not questions closed, so a founder watches Stage, Experience and
    // Revenue appear one by one even though they are one question.
    displayRef.current = { ...displayRef.current, [ctl.key]: shown };
    confirmField(ctl.key, shown, true);

    if (isGroup) {
      groupBufRef.current = { ...groupBufRef.current, [ctl.key]: stored, ...(extra || {}) };
      // Recomputed AFTER the narrowing above, so answering "Stage 0" here
      // removes the revenue part from this very group rather than one question
      // too late.
      const parts = activeParts(q, pathRef.current);
      const nextPart = partIdxRef.current + 1;
      if (nextPart < parts.length) {
        // Still inside the same question: advance the part, stay on the index.
        // Deliberately no save and no progress bump yet -- a half-answered
        // question is not progress, and a partial group must not be written as
        // though it were complete.
        profileRef.current = { ...profileRef.current, ...groupBufRef.current };
        partIdxRef.current = nextPart;
        setPartIdx(nextPart);
        resetControls();
        setTyping(true);
        await sleep(700); if (!alive.current) return;
        setTyping(false);
        addAlly(parts[nextPart].q);
        if (parts[nextPart].prompt) addAlly(parts[nextPart].prompt);
        awaitingRef.current = true;
        setActiveQ(i);
        return;
      }
    }

    const turn = isGroup
      ? { ...groupBufRef.current, [ctl.key]: stored, ...(extra || {}) }
      : { [q.key]: stored, ...(extra || {}) };
    profileRef.current = { ...profileRef.current, ...turn };
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
    // Counted in QUESTIONS, not in answers: a group is one question and only
    // counts once all of its parts (on this path) are in. Otherwise Q3 alone
    // would move the bar three times and the founder would see 11 questions
    // reported as 14.
    const answered = questionsRef.current.filter(
      (x) => questionKeys(x, pathRef.current).every((k) => profileRef.current[k] !== undefined),
    ).length;
    bumpUnd(Math.round((answered / questionCount(pathRef.current)) * 100), 'Ally learned something new');

    setTyping(true);
    await sleep(900); if (!alive.current) return;
    setTyping(false);
    // Keyed on the control that was just answered -- a group has no reply of
    // its own, and its last part is what the founder actually just said.
    addAlly(replyRef.current(ctl.key, replyInput, { first }));
    await sleep(640); if (!alive.current) return;
    const ahead = firstUnresolved(questionsRef.current, pathRef.current, profileRef.current, nextQi);
    if (ahead === -1) { finish(); return; }
    qiRef.current = ahead;
    askQ(ahead);
  }, [addMe, confirmField, bumpUnd, addAlly, askQ, finish, first, resetControls, commitEdit]);

  /** Only reachable on a control marked `optional` (currently just the social
   * handle) -- skips without storing anything, so the field simply stays null
   * rather than being answered with an empty string.
   *
   * Skipping a GROUP's part advances the part, not the question: marking one
   * part optional must not silently skip the parts after it. No part is
   * optional today, so this path is unreachable -- it is here so that marking
   * one optional later is a one-line change rather than a silent bug. */
  const skip = useCallback(async () => {
    if (!awaitingRef.current) return;
    /* Skipping while EDITING means "take what I said before back off my
       profile", not "move past this question" -- there is no flow to move
       past. commitEdit clears the stored answer instead. */
    if (editRef.current) { await commitEdit(null, undefined, undefined, { clear: true }); return; }
    awaitingRef.current = false;
    setActiveQ(-1);
    const i = qiRef.current;
    const q = questionsRef.current[i];
    // Captured before the part index advances below, so a skipped answer's
    // bubble still names the fact it stands for and stays editable.
    const ctl = controlFor(q, pathRef.current, partIdxRef.current);

    if (q.type === 'group') {
      const parts = activeParts(q, pathRef.current);
      const nextPart = partIdxRef.current + 1;
      if (nextPart < parts.length) {
        addMe('Skipped', ctl?.key);
        partIdxRef.current = nextPart;
        setPartIdx(nextPart);
        resetControls();
        setTyping(true);
        await sleep(500); if (!alive.current) return;
        setTyping(false);
        addAlly(parts[nextPart].q);
        if (parts[nextPart].prompt) addAlly(parts[nextPart].prompt);
        awaitingRef.current = true;
        setActiveQ(i);
        return;
      }
    }

    const nextQi = i + 1;
    qiRef.current = nextQi;
    addMe('Skipped', ctl?.key);
    setTyping(true);
    await sleep(500); if (!alive.current) return;
    setTyping(false);
    const ahead = firstUnresolved(questionsRef.current, pathRef.current, profileRef.current, nextQi);
    if (ahead === -1) { finish(); return; }
    qiRef.current = ahead;
    askQ(ahead);
  }, [addMe, addAlly, askQ, finish, resetControls, commitEdit]);

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
      pathRef.current = path;
      questionsRef.current = effectiveQuestions(path);
      profileRef.current.path = path;
      const active = questionsRef.current;
      // The flat list of facts behind those questions -- a group's parts each
      // have their own saved answer, so resume reasons in parts and only
      // rolls up to questions when deciding where to restart.
      const rows = panelRowsFor(active, path);

      // startAt === active.length means every mapped field is already
      // filled/resolved -- treated as done rather than looping past the end of
      // the list. Reaching this component at all used to mean there was a real
      // gap (GuidedLayout redirects a completed profile to /app), but a
      // founder arriving from the profile page's completeness ring is exempt
      // from that redirect on purpose: for them this is the normal case, and
      // the whole transcript below is what they came to read.
      //
      // firstUnresolved/resumePoint are shared with commitEdit, which needs
      // exactly the same answer after a changed stage re-plans the flow.
      const { startAt, startPart, buf: resumeBuf } = resumePoint(active, path, answers);

      if (startAt > 0 || startPart > 0) {
        const filled = rows.filter((x) => isFilled(answers[x.key]));
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
        // transcriptFor synthesises the same alternating ally-question/
        // founder-answer bubbles the live flow itself builds, in `active`'s
        // fixed order -- there is no per-turn timestamp to replay against, so
        // this reconstructs what was asked and said, not a literal scrollback.
        setMessages(transcriptFor(filled, displayRef.current));

        /* In review mode with nothing left to ask, finish() is a beat away and
           says "tap Edit under any answer" itself -- saying it here too put
           the same instruction in two consecutive bubbles. */
        addAlly(review
          ? (startAt >= active.length
            ? `Here's everything you've told me so far, ${first}.`
            : `Here's everything you've told me so far, ${first} — tap Edit under any answer to change it. Let's fill in the rest.`)
          : `Welcome back, ${first} — picking up right where we left off.`);
        await sleep(700);
        askQ(startAt, startPart, resumeBuf);
        return;
      }

      addAlly(`Welcome to GoXL AI, ${first}.`);
      await sleep(700); if (!alive.current) return;
      addAlly('Every entrepreneur has a unique story, a different challenge, and a bold vision for the future. In just a few minutes, help me understand yours.');
      await sleep(900); if (!alive.current) return;
      askQ(0);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [introReady]);

  const q = activeQ >= 0 ? questionsRef.current[activeQ] : null;
  /* The control on screen. For a `group` question that is its current part --
     everything below (the input type, its options, its cap, its Skip button)
     belongs to the part, not to the question wrapping it. */
  const ctrl = controlFor(q, pathRef.current, partIdx);
  const isText = ctrl && (ctrl.type === 'short' || ctrl.type === 'long' || ctrl.type === 'url');

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
    if (ctrl?.type === 'url' && ctrl.optional && !looksLikeUrl(text)) { skip(); return; }
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
    inputRef: taRef,
  });

  /* See AllyChat for the same fix: measure only once React has rendered the
     dictated text and the textarea is visible again.

     Focus is no longer taken here. This effect runs on every keystroke, so
     the focus() it used to call fired on all of them, not just the one that
     mattered -- which meant a founder who clicked away mid-sentence was
     dragged back into the field by their own half-typed answer. The hook now
     focuses exactly once, when a transcript lands, and puts the caret at the
     end so Enter sends it. */
  useEffect(() => {
    if (voice.status !== 'idle') return;
    sizeTa();
  }, [input, voice.status]);

  /* --- control handlers ---------------------------------------------------- */

  const toggle = (value) => {
    setPicked((cur) => {
      if (cur.includes(value)) return cur.filter((v) => v !== value);
      // At the cap, a further pick BUMPS THE OLDEST rather than being ignored
      // (spec v2.4 Q10). Silently dropping the tap was the old behaviour and
      // read as a broken chip: nothing moved, and nothing said why.
      if (ctrl?.max && cur.length >= ctrl.max) return [...cur.slice(1), value];
      return [...cur, value];
    });
  };

  const submitPicked = () => {
    if (picked.length === 0) return;
    const other = otherText.trim();
    if (ctrl.otherField) {
      // The "other" option stays in the list as the marker that there is
      // more; the free text it reveals goes to its own column rather than
      // being appended as a pseudo-chip, so the same words are never stored
      // in two places. Applies to both 'chips' and 'multi' -- live-reproduced
      // gap this redesign fixes: current_challenges already offered an
      // "Other" option with nowhere for the typed text to go.
      answer(picked, other ? { [ctrl.otherField]: other } : undefined);
      return;
    }
    answer(picked);
  };

  const filteredOptions = useMemo(() => {
    if (!ctrl || ctrl.type !== 'dropdown') return [];
    const opts = activeOptions(ctrl, pathRef.current);
    const term = search.trim().toLowerCase();
    if (!term) return opts;
    return opts.filter((o) => optLabel(o).toLowerCase().includes(term));
  }, [ctrl, search]);

  /* Facts, not questions -- Q3 contributes Stage, Experience and (on Path 2)
     Monthly Revenue as three separate rows a founder watches fill in. */
  const panelRows = panelRowsFor(questionsRef.current, pathRef.current);

  /* Chapter eyebrow + progress bar (spec v2.4 s2). The eyebrow shifts at each
     section boundary so four sections read as one continuous conversation
     rather than four stapled-together blocks, and the step counter is in
     QUESTIONS -- a group counts once, however many parts it asks. */
  /* The flow's own position, which is not activeQ while an earlier answer is
     being edited -- the eyebrow and the step counter must not jump back to
     "Question 3 of 11" because the founder is fixing their stage from
     question 9. */
  const flowQi = editing && editRef.current ? editRef.current.wasActiveQ : activeQ;
  const flowQ = flowQi >= 0 ? questionsRef.current[flowQi] : null;
  const chapter = flowQ ? SECTIONS.find((sec) => sec.key === flowQ.section) : null;
  // questionCount(), not questionsRef.current.length -- before the stage answer
  // that list is the superset of both paths, and showing its length made the
  // total drop from 12 to 11 mid-flow. Indices are safe to read directly: every
  // question at or before the stage part is on both paths, so position 1-3
  // means the same thing either way.
  const totalQs = questionCount(pathRef.current);
  const stepNo = flowQi >= 0 ? flowQi + 1 : 0;
  const sectionCount = (key) =>
    panelRows.filter((x) => x.section === key && fields[x.key]?.status === 'on').length;

  /* Edits are offered only when the founder is actually being asked something
     (the flow is parked on a control) or the flow is finished. In between --
     while Ally is typing its reply and the next question is queued behind an
     await -- an edit would be clobbered a moment later by the askQ() that
     continuation is about to run. One edit at a time, too: the banner's Cancel
     is the way out of the one already open. */
  const canEdit = !editing && (activeQ >= 0 || complete);

  const needsOther = (ctrl?.type === 'chips' || ctrl?.type === 'multi') && !!ctrl?.otherValue && picked.includes(ctrl.otherValue);
  const atMax = ctrl?.max ? picked.length >= ctrl.max : false;

  /* --- the input region, one control per question type --------------------- */
  function renderControl() {
    if (!ctrl) return null;

    if (ctrl.type === 'stage') {
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

    if (ctrl.type === 'single') {
      return (
        <div className="suggs">
          {activeOptions(ctrl, pathRef.current).map((o) => (
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

    if (ctrl.type === 'dropdown') {
      // Picking the "other" option doesn't answer immediately -- it waits for
      // the free text behind it (spec: "If Other selected -> show free-text
      // input"), reusing `picked`/`otherText` the same way chips/multi do
      // rather than inventing separate state for a third control.
      const otherPending = ctrl.otherValue && picked[0] === ctrl.otherValue;
      return (
        <div className="ob-drop">
          <label className="sr-only" htmlFor="obSearch">{ctrl.q}</label>
          <input
            id="obSearch"
            ref={searchRef}
            className="ob-search"
            type="text"
            value={search}
            placeholder={ctrl.placeholder}
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
                    /* optLabel as the display, the same way the single-select
                       cards above already do it. Industry stores the canonical
                       industries.industry_name ('BFSI / FinTech') while the
                       founder picked a fuller label ('Banking, Financial
                       Services & Insurance (BFSI) / FinTech') -- without this
                       their own bubble read back the abbreviation they had not
                       chosen. The panel and the summary were already right:
                       both go through labelFor(). */
                    onClick={() => (ctrl.otherValue && v === ctrl.otherValue
                      ? setPicked([v])
                      : answer(v, undefined, optLabel(o)))}
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
                aria-label={ctrl.otherPlaceholder || 'Tell us more'}
                value={otherText}
                placeholder={ctrl.otherPlaceholder || 'Tell me more…'}
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
                    answer(ctrl.otherValue, ctrl.otherField ? { [ctrl.otherField]: text } : undefined, text);
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

    if (ctrl.type === 'yesno') {
      const allAnswered = ctrl.items.every((it) => yesNo[it.key] !== undefined);
      return (
        <div className="ob-yesno">
          {ctrl.items.map((it) => (
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
            <span className="ob-count">{Object.keys(yesNo).length} of {ctrl.items.length} answered</span>
            <button
              type="button"
              className="btn btn-em ob-continue"
              disabled={!allAnswered}
              onClick={() => {
                const display = ctrl.items.map((it) => `${it.text}: ${yesNo[it.key] ? 'Yes' : 'No'}`).join(' · ');
                answer(yesNo, undefined, display);
              }}
            >
              Continue
            </button>
          </div>
        </div>
      );
    }

    if (ctrl.type === 'chips' || ctrl.type === 'multi') {
      return (
        <div className="ob-multi">
          <div className="ob-chips">
            {activeOptions(ctrl, pathRef.current).map((o) => {
              const v = optValue(o);
              const on = picked.includes(v);
              return (
                <button
                  key={v}
                  type="button"
                  className={`sugg${on ? ' on' : ''}`}
                  aria-pressed={on}
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
              aria-label={ctrl.otherPlaceholder || 'Tell us more'}
              value={otherText}
              placeholder={ctrl.otherPlaceholder || 'Tell me more…'}
              onChange={(e) => setOtherText(e.target.value)}
            />
          )}

          <div className="ob-multi-foot">
            <span className="ob-count">
              {ctrl.max
                ? `${picked.length} of ${ctrl.max} chosen${atMax ? ' — picking another swaps the first' : ''}`
                : `${picked.length} chosen`}
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
              hint={voice.status === 'recording' ? 'Enter to stop · Esc to discard' : null}
            />
          )}
          <label className="sr-only" htmlFor="profText">Your answer to Ally</label>
          <textarea
            id="profText"
            ref={taRef}
            rows={ctrl.type === 'long' ? 2 : 1}
            placeholder={ctrl.placeholder || 'Type your answer…'}
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
        {ctrl.optional && (
          <button type="button" className="ob-skip" onClick={skip}>
            Skip — I'd rather not share
          </button>
        )}
        {ctrl.examples && (
          <p className="ci-hint">For example: {ctrl.examples.join(' · ')}</p>
        )}
        {!ctrl.examples && (
          <p className="ci-hint">
            Ally is building your founder profile as you talk · Enter to send
            {ctrl.type === 'long' ? ' · Shift+Enter for a new line' : ''}
          </p>
        )}
      </div>
    );
  }

  return (
    /* has-jbar: the closing bar is position:fixed over the bottom of the
       viewport (see the inline style on it below), which used to be harmless
       because it only appeared once the flow was over and no answer control
       was left on screen. Editing an answer after that -- the whole point of
       review mode -- puts a control back underneath it, with its last row of
       options and its Continue button sitting under the bar and unclickable.
       The padding gives the control somewhere to be. */
    <section className={`view chat-view active${showBar ? ' has-jbar' : ''}`} id="v-profile">
      {/* This step had no h1 at all — every sibling guided page has one, so a
          screen-reader user landing here got no page title. */}
      <h1 className="sr-only">Building your founder profile</h1>
      <div className="chat">
        <div className="chat-main">
          {chapter && (
            <div className="ob-chapter">
              <div className="ob-chapter-row">
                <span className="ob-chapter-t">{chapter.chapter}</span>
                <span className="ob-chapter-n">Question {stepNo} of {totalQs}</span>
              </div>
              <div
                className="ob-chapter-bar"
                role="progressbar"
                aria-valuenow={stepNo}
                aria-valuemin={0}
                aria-valuemax={totalQs}
                aria-label="Onboarding progress"
              >
                <i style={{ width: `${totalQs ? (stepNo / totalQs) * 100 : 0}%` }} />
              </div>
            </div>
          )}
          {/* aria-live alone announced nothing useful without a role or a name. */}
          <div className="chat-scroll" ref={scrollRef} role="log" aria-live="polite" aria-label="Your conversation with Ally">
            {messages.map((m, i) => (
              <div key={i} className={`msg ${m.who === 'me' ? 'me' : 'ally'}`}>
                {/* Ally is the product's mark, not a monogram -- "A" read as
                    another person's initial next to the founder's own. */}
                <span className={`m-av ${m.who === 'me' ? 'me' : 'ally'}`}>
                  {m.who === 'me' ? initial : <img src="/ally-logo-mark-on-dark.png" alt="" />}
                </span>
                <div>
                  <div className="bubble">{m.text}</div>
                  {/* The founder's own answers are editable in place; Ally's
                      questions are not, so they get Copy alone. */}
                  <MessageActions
                    text={m.text}
                    what={m.who === 'me' ? 'your answer' : "Ally's question"}
                    onEdit={m.who === 'me' && m.key && canEdit ? () => startEdit(m.key) : undefined}
                  />
                </div>
              </div>
            ))}
            {typing && (
              <div className="typing">
                <span className="m-av ally"><img src="/ally-logo-mark-on-dark.png" alt="" /></span>
                <div className="bubble"><span className="td"><span /><span /><span /></span></div>
              </div>
            )}
          </div>

          {editing && (
            <div className="ob-editing">
              <span className="ob-editing-t">
                <span className="ob-editing-tag">Editing</span>
                {editing.q}
              </span>
              <button type="button" className="ob-back ob-editing-x" onClick={cancelEdit}>
                Cancel
              </button>
            </div>
          )}
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
              const qs = panelRows.filter((x) => x.section === sec.key);
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
          <span className="jb-note">
            {review ? 'Every change is saved as you make it.' : 'Your Founder DNA is ready.'}
          </span>
          <div className="spacer" />
          {/* A founder who came from the profile page's ring came to check
              something, not to be walked through the rest of onboarding --
              sending them on to /guided/tour from here would restart a
              sequence they finished weeks ago. */}
          <button
            className="btn btn-em cta-pulse"
            type="button"
            onClick={() => navigate(review ? '/app/profile' : '/guided/tour')}
          >
            {review ? 'Back to my profile' : 'Continue'} <svg viewBox="0 0 24 24" className="w-4 h-4 inline-block ml-1" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
          </button>
        </div>
      )}
    </section>
  );
}
