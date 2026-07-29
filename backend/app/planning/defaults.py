"""Default values for new planning items."""

from __future__ import annotations

from app.planning.models import PlanStatus, Priority, ProgressStatus

DEFAULT_PLAN_STATUS = PlanStatus.ACTIVE
DEFAULT_PROGRESS = ProgressStatus.TODO
DEFAULT_PRIORITY = Priority.MEDIUM
