/**
 * services/planning.js — "Plan Your Day". Wraps POST/GET/PATCH /planning/*.
 *
 * The backend models a real Plan -> Goal -> Task hierarchy, but the UI only
 * ever shows one flat task list per founder, so this module hides that
 * structure behind a simple task-list API: ensureDefaultGoal() gets (or
 * lazily creates) the one plan + one goal every founder's tasks live under,
 * and everything else operates on tasks directly.
 */

import { del, get, patch, post } from './api';
import { browserTimezone } from './calendar';

const DEFAULT_PLAN_TITLE = 'My Plan';
const DEFAULT_GOAL_TITLE = 'Tasks';

/**
 * The founder's one ongoing plan + goal, creating them on first use. A new
 * founder has zero plans -- list_plans returns empty, not an error -- so this
 * is the only place "no plan yet" gets resolved into something tasks can
 * attach to.
 */
export async function ensureDefaultGoal() {
  const { plans } = await get('/planning/plans');
  let plan = plans[0];
  if (!plan) {
    plan = await post('/planning/plans', { title: DEFAULT_PLAN_TITLE });
  }
  const { goals } = await get(`/planning/plans/${plan.plan_id}/goals`);
  let goal = goals[0];
  if (!goal) {
    goal = await post(`/planning/plans/${plan.plan_id}/goals`, { title: DEFAULT_GOAL_TITLE });
  }
  return { plan, goal };
}

/** All tasks under the founder's default goal (creating it if needed). */
export async function listTasks() {
  const { goal } = await ensureDefaultGoal();
  const { tasks } = await get(`/planning/goals/${goal.goal_id}/tasks`);
  return tasks;
}

/**
 * Add a task. A `dueDate` is what makes it eligible for calendar sync — without
 * one it is a list item and nothing is pushed anywhere.
 *
 * `dueTime` is optional and drives the reminder: Google measures reminder
 * offsets backwards from the event start, so a task with a real time gets a
 * popup 30 minutes before it, and one with only a date is placed at the
 * server's default hour so the reminder still lands in the morning.
 *
 * The timezone rides along so "2pm" means 2pm where the founder is.
 */
export async function addTask(title, { priority = 'medium', dueDate = null,
                                       dueTime = null } = {}) {
  const { goal } = await ensureDefaultGoal();
  return post(`/planning/goals/${goal.goal_id}/tasks`, {
    title, priority, due_date: dueDate, due_time: dueTime,
    timezone: browserTimezone(),
  });
}

export function setTaskStatus(taskId, status) {
  return patch(`/planning/tasks/${taskId}`, { status });
}

/** Title, priority, date and time -- what the per-task edit menu exposes.
 * All optional so a caller only sends what actually changed; an explicit null
 * clears the field, which is why `undefined` and `null` are distinguished here
 * rather than collapsed. Changing a date or time updates the SAME calendar
 * event, because the task carries the id of the one it created. */
export function updateTask(taskId, { title, priority, dueDate, dueTime } = {}) {
  const body = { timezone: browserTimezone() };
  if (title !== undefined) body.title = title;
  if (priority !== undefined) body.priority = priority;
  if (dueDate !== undefined) body.due_date = dueDate;
  if (dueTime !== undefined) body.due_time = dueTime;
  return patch(`/planning/tasks/${taskId}`, body);
}

/** No undo -- unlike a plan (archived, restorable), a task has no restore
 * path once deleted. The caller is responsible for confirming with the
 * founder before calling this. */
export function deleteTask(taskId) {
  return del(`/planning/tasks/${taskId}`);
}

/** Every not-done task with a due date on or before today -- what "Ally should
 * remind me" means in practice: tasks that are overdue or due today. */
export function isDueOrOverdue(task) {
  if (task.status === 'done' || !task.due_date) return false;
  return task.due_date <= new Date().toISOString().slice(0, 10);
}
