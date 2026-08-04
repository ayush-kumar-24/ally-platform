/**
 * services/planning.js — "Plan Your Day". Wraps POST/GET/PATCH /planning/*.
 *
 * The backend models a real Plan -> Goal -> Task hierarchy, but the UI only
 * ever shows one flat task list per founder, so this module hides that
 * structure behind a simple task-list API: ensureDefaultGoal() gets (or
 * lazily creates) the one plan + one goal every founder's tasks live under,
 * and everything else operates on tasks directly.
 */

import { get, patch, post } from './api';

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

export async function addTask(title, { priority = 'medium', dueDate = null } = {}) {
  const { goal } = await ensureDefaultGoal();
  return post(`/planning/goals/${goal.goal_id}/tasks`, {
    title, priority, due_date: dueDate,
  });
}

export function setTaskStatus(taskId, status) {
  return patch(`/planning/tasks/${taskId}`, { status });
}

/** Every not-done task with a due date on or before today -- what "Ally should
 * remind me" means in practice: tasks that are overdue or due today. */
export function isDueOrOverdue(task) {
  if (task.status === 'done' || !task.due_date) return false;
  return task.due_date <= new Date().toISOString().slice(0, 10);
}
