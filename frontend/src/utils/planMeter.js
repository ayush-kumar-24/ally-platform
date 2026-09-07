/**
 * utils/planMeter.js -- one reading of the daily token meter, shared by every
 * surface that draws it.
 *
 * WHY THIS EXISTS AS A HELPER AND NOT AS THREE LOCAL EXPRESSIONS
 *
 * Usage can legitimately exceed the ceiling. The quota gate admits any request
 * where `used < limit` and only records the real token cost after the model has
 * replied (see backend app/plans/service.py -- the pre-check reserves nothing,
 * because the true cost is unknowable until the answer exists). So a founder at
 * 7,900 of 8,000 is allowed one more message and lands somewhere past 8,000. The
 * first diagnosis overshoots further still: it is unmetered by design, skips the
 * check entirely, and its tokens are recorded anyway.
 *
 * That is bounded and correct. What was not correct is how it read: the dashboard
 * clamped its BAR to 100% while printing the raw "8416 / 8000" beside it, so the
 * two halves of the same meter disagreed and the founder had no way to tell which
 * one was broken. The profile page had the identical split.
 *
 * Past the ceiling the honest thing to show is that the day is spent, not a
 * fraction that reads like a broken counter -- so `used` is clamped for display
 * and `atLimit` carries the real state. The exact overage is deliberately not
 * surfaced: it is an artefact of when the meter charges, not something a founder
 * did or can act on.
 */

/**
 * @param {{daily_tokens_used?: number, daily_token_limit?: number}|null|undefined} plan
 * @returns {{used:number, limit:number, pct:number, atLimit:boolean, hasLimit:boolean}}
 */
export function dailyTokenMeter(plan) {
  const limit = Number(plan?.daily_token_limit) || 0;
  const raw = Number(plan?.daily_tokens_used) || 0;
  const hasLimit = limit > 0;
  const atLimit = hasLimit && raw >= limit;
  return {
    // Clamped, so the number can never contradict the bar beside it.
    used: hasLimit ? Math.min(raw, limit) : raw,
    limit,
    pct: hasLimit ? Math.min(100, Math.round((raw / limit) * 100)) : 0,
    atLimit,
    hasLimit,
  };
}

/** "8,000 / 8,000" -- grouped, and never a fraction greater than one. */
export function formatTokenMeter(plan) {
  const { used, limit } = dailyTokenMeter(plan);
  return `${used.toLocaleString('en-IN')} / ${limit.toLocaleString('en-IN')}`;
}
