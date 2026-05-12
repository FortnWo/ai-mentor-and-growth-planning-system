from sqlalchemy.orm import Session

from app.models.action_plan import ActionPlan
import app.services.action_plan_service as action_plan_service


def get_plan_for_user(db: Session, user_id: int, plan_id: int) -> ActionPlan | None:
    return action_plan_service.get_action_plan_for_user(db, user_id, plan_id)


def get_plan_for_goal(db: Session, user_id: int, goal_id: int) -> ActionPlan | None:
    return action_plan_service.get_action_plan_for_goal(db, user_id, goal_id)


def list_plans_for_user(db: Session, user_id: int) -> list[ActionPlan]:
    return action_plan_service.list_action_plans_for_user(db, user_id)


def get_plan_detail(db: Session, user_id: int, plan_id: int):
    return action_plan_service.get_plan_detail(db, user_id, plan_id)


def prepare_plan_for_goal(
    db: Session,
    user_id: int,
    goal_id: int,
    reset_items: bool = False,
) -> ActionPlan | None:
    return action_plan_service.prepare_action_plan_for_goal(
        db,
        user_id,
        goal_id,
        reset_items=reset_items,
    )


def prepare_plan_for_refresh(
    db: Session,
    user_id: int,
    plan_id: int,
    *,
    reset_items: bool = False,
) -> ActionPlan | None:
    return action_plan_service.prepare_action_plan_for_refresh(
        db,
        user_id,
        plan_id,
        reset_items=reset_items,
    )


def generate_plan_with_retry(
    db: Session,
    user_id: int,
    plan_id: int,
    max_attempts: int = 3,
    base_delay_seconds: float = 1.0,
) -> ActionPlan:
    return action_plan_service.generate_action_plan_with_retry(
        db,
        user_id,
        plan_id,
        max_attempts=max_attempts,
        base_delay_seconds=base_delay_seconds,
    )


def mark_plan_failed(db: Session, plan_id: int, error_message: str | None = None) -> bool:
    action_plan_service.mark_action_plan_failed(db, plan_id, error_message)
    return True


def delete_plan_for_user(db: Session, user_id: int, plan_id: int) -> bool:
    plan = action_plan_service.get_action_plan_for_user(db, user_id, plan_id)
    if not plan:
        return False
    db.delete(plan)
    db.commit()
    return True

