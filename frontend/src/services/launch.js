/**
 * services/launch.js — the go-live gate.
 *
 * Two audiences, one state:
 *   - every visitor polls `getLaunchStatus()` to know whether the platform is
 *     open, and what to count down to if it is not. No token required, which
 *     matters: the people who most need this answer are the ones who cannot
 *     sign in yet.
 *   - the admin control room drives the four buttons below. They are Super
 *     Admin only, enforced server-side — see app/api/v1/admin/launch_router.py.
 *
 * `seconds_remaining` comes from the server on every poll and is never
 * recomputed here from `countdown_ends_at` against the browser's own clock.
 * Laptops in one room disagree about the time by seconds, which is exactly
 * enough for the countdown people are reading aloud together not to match.
 */

import { get, post } from './api';

/** Public. Unauthenticated, cheap, polled by everyone during a countdown. */
export function getLaunchStatus() {
  return get('/launch/status');
}

/** Admin: current state, including whether the launch button is pressable. */
export function getLaunchState() {
  return get('/admin/launch');
}

/** Admin: close the platform ahead of the event and set the countdown length. */
export function armLaunch(countdownSeconds) {
  return post('/admin/launch/arm', { countdown_seconds: countdownSeconds });
}

/** Admin: start the shared clock. Omitting the length keeps the armed one. */
export function startCountdown(countdownSeconds) {
  return post('/admin/launch/countdown',
    countdownSeconds ? { countdown_seconds: countdownSeconds } : {});
}

/** Admin: stop the clock. Doors stay shut. */
export function abortCountdown() {
  return post('/admin/launch/abort');
}

/** Admin: open the platform to everyone. Irreversible — see the module
 *  docstring in backend app/launch/__init__.py for why there is no undo. */
export function launchNow() {
  return post('/admin/launch/launch');
}

export const LAUNCH_STATES = {
  OPEN: 'open',
  ARMED: 'armed',
  COUNTING: 'counting',
  LAUNCHED: 'launched',
};
