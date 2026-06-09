from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.action_plan import ActionPlan, ActionPlanItem, ActionPlanStatus
from app.models.goal import Goal, GoalBreakdown, GoalBreakdownStatus, GoalStatus
from app.schemas.ukl import ExecutionFeedbackPayload, WorkloadSnapshotPayload


def compute_workload_snapshot(db: Session, user_id: int) -> WorkloadSnapshotPayload:
    goals = db.query(Goal).filter(Goal.user_id == user_id).all()
    active_goals = [g for g in goals if (g.status or GoalStatus.ACTIVE.value) == GoalStatus.ACTIVE.value]

    plans = (
        db.query(ActionPlan)
        .join(Goal, Goal.id == ActionPlan.goal_id)
        .filter(Goal.user_id == user_id)
        .all()
    )
    active_plans = [p for p in plans if p.status != ActionPlanStatus.COMPLETED.value]

    plan_ids = [p.id for p in plans]
    pending_items = 0
    in_progress_items = 0
    if plan_ids:
        items = db.query(ActionPlanItem).filter(ActionPlanItem.plan_id.in_(plan_ids)).all()
        for item in items:
            if item.status == ActionPlanStatus.COMPLETED.value:
                continue
            if item.status == ActionPlanStatus.IN_PROGRESS.value:
                in_progress_items += 1
            else:
                pending_items += 1

    return WorkloadSnapshotPayload(
        active_goal_count=len(active_goals),
        total_goal_count=len(goals),
        active_plan_count=len(active_plans),
        pending_item_count=pending_items,
        in_progress_item_count=in_progress_items,
    )


def compute_execution_feedback(db: Session, user_id: int, goal_id: int) -> ExecutionFeedbackPayload:
    plans = (
        db.query(ActionPlan)
        .join(Goal, Goal.id == ActionPlan.goal_id)
        .filter(Goal.user_id == user_id, ActionPlan.goal_id == goal_id)
        .all()
    )
    plan_ids = [p.id for p in plans]
    if not plan_ids:
        return ExecutionFeedbackPayload(goal_id=goal_id)

    items = db.query(ActionPlanItem).filter(ActionPlanItem.plan_id.in_(plan_ids)).all()
    total = len(items)
    completed = sum(1 for item in items if item.status == ActionPlanStatus.COMPLETED.value)
    rate = (completed / total) if total else 0.0

    by_breakdown: dict[str, dict[str, int]] = {}
    for item in items:
        if not item.breakdown_id:
            continue
        key = str(item.breakdown_id)
        bucket = by_breakdown.setdefault(key, {"total": 0, "completed": 0})
        bucket["total"] += 1
        if item.status == ActionPlanStatus.COMPLETED.value:
            bucket["completed"] += 1

    return ExecutionFeedbackPayload(
        goal_id=goal_id,
        total_items=total,
        completed_items=completed,
        completion_rate=round(rate, 3),
        by_breakdown_id=by_breakdown,
    )


def compute_execution_feedback_for_goal(db: Session, user_id: int, goal_id: int) -> ExecutionFeedbackPayload:
    return compute_execution_feedback(db, user_id, goal_id)
