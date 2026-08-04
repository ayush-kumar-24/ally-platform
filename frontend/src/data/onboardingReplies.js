/**
 * data/onboardingReplies.js — what Ally says back after each onboarding answer.
 *
 * Onboarding has no LLM behind it, so these are written rather than generated.
 * What they are not is a single fixed line per question: each question carries
 * three or four variants, one is drawn at random, and a variant is never reused
 * inside a session. Two founders answering the same twelve questions do not read
 * the same twelve replies.
 *
 * Variants are functions of the answer, so they can quote what the founder
 * actually said instead of talking past it.
 */

/** Quote a short answer inline; fall back to a generic phrase if it's long. */
function clip(text, max = 60) {
  const s = String(text ?? '').trim().replace(/\s+/g, ' ');
  if (!s) return '';
  return s.length <= max ? s : s.slice(0, max - 1).trimEnd() + '…';
}

/** "Sales, Hiring and Cash flow" — for multi-select answers. */
function list(values) {
  const items = (Array.isArray(values) ? values : [values]).filter(Boolean).map(String);
  if (items.length === 0) return '';
  if (items.length === 1) return items[0];
  return items.slice(0, -1).join(', ') + ' and ' + items[items.length - 1];
}

const lower = (s) => String(s ?? '').trim().toLowerCase();

/**
 * Reply pools. Each entry: an array of (answer, ctx) => string.
 * `answer` is the display form (string, or array for multi-selects).
 * `ctx` carries { first, stage, group } for replies that want them.
 */
export const REPLY_POOLS = {
  // Stage names are proper labels ("Prototype / MVP"), so they are never
  // downcased -- "prototype / mvp" reads like a typo.
  stage: [
    (a) => `${a} — that tells me a lot. The risks that matter are different at every stage, and I'll weigh them for yours.`,
    (a) => `Noted: ${a}. I'll stop myself giving you advice meant for a company three stages ahead.`,
    (a) => `${a} it is. That single answer changes which questions are worth your time later.`,
    (a) => `Good — you're at ${a}. I'd rather meet you where you actually are than where a framework assumes you are.`,
  ],

  building: [
    (a) => `“${clip(a, 80)}” — I can picture it. Thanks for keeping it concrete.`,
    () => `Got it. Being able to say it plainly is worth more than most founders realise.`,
    () => `That's clear enough that I already have questions about it — a good sign.`,
    () => `Understood. I'll hold that description against everything you tell me next.`,
  ],

  problem: [
    () => `That's the heart of it. Naming the problem that cleanly usually means you've felt it yourself.`,
    () => `Thank you — problems described in plain language are the ones that turn out to be real.`,
    () => `I follow. That's the thing everything else has to serve.`,
    () => `Noted, and I won't lose it. Most advice goes wrong by drifting away from the actual problem.`,
  ],

  why: [
    () => `Thank you for that. It's the part most founders skip, and it tells me what you'll protect even when it costs you speed.`,
    () => `That matters more than the business model. I'll remember it when the trade-offs get hard.`,
    () => `I'm glad you told me. Motivation like that is usually what's left when the strategy changes.`,
    () => `Understood. That's the thing to come back to on the weeks where nothing works.`,
  ],

  audience: [
    (a) => `${list(a)} — knowing exactly who it's for sharpens every recommendation I'll make.`,
    (a) => `Building for ${lower(list(a))}. That narrows what "good" even means here, which helps.`,
    (a) => `Got it — ${lower(list(a))}. I'll keep asking whether what we discuss actually serves them.`,
    () => `Clear. Founders who can name their audience without hedging tend to move faster.`,
  ],

  industry: [
    (a) => `${a}. Every industry has its own gravity — I'll factor in what usually pulls hardest in yours.`,
    (a) => `Noted, ${a}. That tells me which benchmarks are fair to hold you to and which aren't.`,
    (a) => `${a} — useful. I'll stop comparing you to businesses that play by different rules.`,
  ],

  challenges: [
    (a) => `${list(a)} — thank you for being direct. That's the thread I'll pull hardest on.`,
    (a) => `So it's ${lower(list(a))}. Naming it is most of the work; the rest we can actually plan around.`,
    (a) => `Understood — ${lower(list(a))}. I'd rather work on the real constraint than the comfortable one.`,
    () => `That's honest, and honestly it's the useful answer. Vague answers here waste everyone's time.`,
  ],

  goal90: [
    () => `A clear 90-day target. I'll hold everything I learn against whether it moves that.`,
    (a) => `“${clip(a, 70)}” — that's specific enough to be measurable, which is the hard part.`,
    () => `Good. Ninety days is long enough to matter and short enough to stay honest about.`,
    () => `Noted. If something we discuss doesn't serve that, I'll say so.`,
  ],

  vision: [
    () => `That's a strong north star. It tells me which trade-offs you'll be willing to make.`,
    () => `A year is a useful horizon — far enough to aim at, close enough to hold you to.`,
    () => `Understood. I'll check the 90-day plan actually points at that, not away from it.`,
    () => `Thank you. Knowing where you're headed makes it much easier to tell you what to ignore.`,
  ],

  support: [
    (a) => `${list(a)} — that's how I'll show up. Direct where it helps, quiet where it doesn't.`,
    (a) => `Got it: ${lower(list(a))}. I'll lead with those rather than making you ask.`,
    (a) => `Noted — you want me on ${lower(list(a))}. That shapes what I bring up unprompted.`,
    () => `Understood. I'd rather be useful in the ways you actually asked for.`,
  ],

  experience: [
    (a) => `${a} — that shapes how I pitch things: less hand-holding, more signal.`,
    (a) => `Good to know you're a ${lower(a)}. I'll calibrate how much I explain versus how much I assume.`,
    (a) => `${a}. I'll skip the basics you've already lived through.`,
  ],

  feeling: [
    (a) => `Thanks for saying so — ${lower(a)}. I'll factor how you're carrying this into how I pace us.`,
    (a) => `Noted, and it isn't a small thing. Feeling ${lower(a)} changes what good advice even looks like today.`,
    (a) => `${a} — I'll keep that in mind. There's no version of this where I ignore how you're doing.`,
    () => `Thank you for being honest about that. Most people give the polite answer here.`,
  ],

  reflection: [
    () => `That's a real answer, and a useful one. I've got a clear read on you now.`,
    () => `Thank you — that's the kind of thing that usually only comes out much later.`,
    () => `Understood. That's the piece I'd have had to guess at otherwise.`,
  ],
};

const FALLBACK = [
  () => `Got it — thank you.`,
  () => `Noted.`,
  () => `Understood, thank you.`,
];

/**
 * A session-scoped picker.
 *
 * Draws a random unused variant for a question and remembers it, so a founder
 * never sees the same reply twice even where pools overlap in tone. Once a pool
 * is exhausted it resets rather than going silent.
 */
export function createReplyPicker(random = Math.random) {
  const used = new Map(); // question key -> Set of variant indices already shown

  return function reply(key, answer, ctx = {}) {
    const pool = REPLY_POOLS[key] || FALLBACK;
    let seen = used.get(key);
    if (!seen || seen.size >= pool.length) {
      seen = new Set();
      used.set(key, seen);
    }

    const available = pool.map((_, i) => i).filter((i) => !seen.has(i));
    const index = available[Math.floor(random() * available.length)];
    seen.add(index);

    try {
      return pool[index](answer, ctx);
    } catch {
      // A reply that throws must never cost the founder their answer.
      return FALLBACK[0]();
    }
  };
}
