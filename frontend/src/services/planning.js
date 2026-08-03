/**
 * services/planning.js — Founder Action Plans (Plan → Goal → Task).
 *
 * Backs both Plan Your Day and Next Steps. Both read the same plans; they differ
 * only in how they present them, so they must not keep separate copies.
 */

import { get, post, patch, del, prune } from './api';

// --- plans -----------------------------------------------------------------

export function listPlans(includeArchived = false) {
  return get('/planning/plans', { params: { include_archived: includeArchived } });
}

export function createPlan({ title, description }) {
  // Optional string fields must be OMITTED, not sent as null -- the schema types
  // them as `str` with a default, so an explicit null is a 422.
  return post('/planning/plans', description ? { title, description } : { title });
}

/**
 * Flatten the plan-detail envelope.
 *
 * The API nests twice -- `{plan: {...}, goals: [{goal: {...}, tasks: [...]}]}` --
 * while every create/update endpoint returns the record flat. Callers that read
 * `plan.plan_id` or `goal.title` off the envelope silently get `undefined`, which
 * is how a request for `/planning/plans/undefined/goals` gets built. Normalising
 * on the way in means the page only ever sees one shape.
 */
export function normalisePlanDetail(detail) {
  if (!detail) return null;
  return {
    ...(detail.plan ?? detail),
    goals: (detail.goals ?? []).map(g => ({ ...(g.goal ?? g), tasks: g.tasks ?? [] })),
  };
}

/** A plan with its goals and their tasks nested, flattened to one shape. */
export async function getPlanDetail(planId) {
  return normalisePlanDetail(await get(`/planning/plans/${planId}`));
}

export function updatePlan(planId, changes) {
  return patch(`/planning/plans/${planId}`, changes);
}

export function archivePlan(planId) {
  return del(`/planning/plans/${planId}`);
}

export function restorePlan(planId) {
  return post(`/planning/plans/${planId}/restore`, {});
}

/** Turn the founder's diagnosis next-steps into a goal with tasks. */
export function seedFromDiagnosis(planId) {
  return post(`/planning/plans/${planId}/seed-from-diagnosis`, {});
}

// --- goals & tasks ---------------------------------------------------------

export function addGoal(planId, { title, description, priority, targetDate }) {
  return post(`/planning/plans/${planId}/goals`, prune({
    title, description, priority, target_date: targetDate,
  }));
}

export function updateGoal(goalId, changes) {
  return patch(`/planning/goals/${goalId}`, changes);
}

export function addTask(goalId, { title, description, priority, dueDate }) {
  return post(`/planning/goals/${goalId}/tasks`, prune({
    title, description, priority, due_date: dueDate,
  }));
}

export function updateTask(taskId, changes) {
  return patch(`/planning/tasks/${taskId}`, changes);
}

/** Toggle done/todo. `completed_at` is stamped server-side, never here. */
export function setTaskStatus(taskId, done) {
  return updateTask(taskId, { status: done ? 'done' : 'todo' });
}

/**
 * The founder's working plan, creating one on first use.
 *
 * Plan Your Day should not present an empty screen and make someone invent a
 * container before they can add a task, so the first visit quietly bootstraps one.
 */
export async function ensureActivePlan() {
  const { plans } = await listPlans();
  if (plans?.length) return getPlanDetail(plans[0].plan_id);
  const created = await createPlan({ title: 'My plan' });
  return getPlanDetail(created.plan_id);
}

/** Flatten a plan detail into a single task list for day-view rendering. */
export function flattenTasks(detail) {
  return (detail?.goals ?? []).flatMap(g =>
    (g.tasks ?? []).map(t => ({ ...t, goalTitle: g.title, goalId: g.goal_id })));
}
