"""Planning errors. AppError subclasses -> mapped to consistent JSON, fail closed."""

from fastapi import status

from app.middleware.error_handler import AppError


class PlanningError(AppError):
    """Base for planning failures."""


class PlanNotFoundError(PlanningError):
    def __init__(self, plan_id: str):
        super().__init__(f"Plan '{plan_id}' was not found.", status_code=status.HTTP_404_NOT_FOUND)


class GoalNotFoundError(PlanningError):
    def __init__(self, goal_id: str):
        super().__init__(f"Goal '{goal_id}' was not found.", status_code=status.HTTP_404_NOT_FOUND)


class TaskNotFoundError(PlanningError):
    def __init__(self, task_id: str):
        super().__init__(f"Task '{task_id}' was not found.", status_code=status.HTTP_404_NOT_FOUND)


class InvalidPlanningInputError(PlanningError):
    def __init__(self, field: str, reason: str):
        super().__init__(f"Invalid {field}: {reason}.", status_code=422)


class InvalidPlanStateError(PlanningError):
    def __init__(self, plan_id: str, state: str, action: str):
        super().__init__(f"Cannot {action} plan '{plan_id}' while it is {state}.",
                         status_code=status.HTTP_409_CONFLICT)
