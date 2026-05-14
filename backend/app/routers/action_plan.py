import logging
import traceback

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.action_plan import ActionPlanStatus
from app.models.user import User
from app.schemas.action_plan import (
    ActionPlanCreate,
    ActionPlanDetailRead,
    ActionPlanItemCompletionUpdate,
    ActionPlanItemRead,
    ActionPlanRead,
)
from app.services import action_plan_service

router = APIRouter(prefix="/action-plans", tags=["action-plans"])
error_logger = logging.getLogger("ai_mentor.errors")


def _process_action_plan_in_background(plan_id: int, user_id: int) -> None:
    import app.core.database as database_module

    db = database_module.SessionLocal()
    try:
        plan = action_plan_service.generate_action_plan_with_retry(db, user_id, plan_id)
        if not plan:
            error_logger.warning("Action plan generation returned no plan plan_id=%s user_id=%s", plan_id, user_id)
    except ValueError as exc:
        error_logger.warning("Action plan generation failed plan_id=%s user_id=%s error=%s", plan_id, user_id, exc)
        action_plan_service.mark_action_plan_failed(db, plan_id, str(exc))
    except Exception as exc:
        error_logger.error(
            "Action plan generation failed plan_id=%s user_id=%s error=%s\n%s",
            plan_id,
            user_id,
            exc,
            traceback.format_exc(),
        )
        action_plan_service.mark_action_plan_failed(db, plan_id, str(exc))
    finally:
        db.close()


@router.post("", response_model=list[ActionPlanDetailRead], status_code=status.HTTP_202_ACCEPTED)
def create_action_plan(
    payload: ActionPlanCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not settings.ACTION_PLAN_ENABLED:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Action plan feature is disabled")

    existing = action_plan_service.list_action_plans_for_goal(db, current_user.id, payload.goal_id)
    already_in_progress = any(plan.status == ActionPlanStatus.IN_PROGRESS.value for plan in existing)
    if already_in_progress:
        details: list[ActionPlanDetailRead] = []
        for plan in existing:
            detail = action_plan_service.get_plan_detail(db, current_user.id, plan.id)
            if detail:
                details.append(detail)
        if not details:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action plan not found")
        return details

    prepared = action_plan_service.prepare_action_plans_for_goal(db, current_user.id, payload.goal_id, reset_items=False)
    if not prepared:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Goal not found or goal has no breakdown pillars yet",
        )

    for plan in prepared:
        background_tasks.add_task(_process_action_plan_in_background, plan.id, current_user.id)

    out: list[ActionPlanDetailRead] = []
    for plan in prepared:
        detail = action_plan_service.get_plan_detail(db, current_user.id, plan.id)
        if detail:
            out.append(detail)
    return out


@router.get("", response_model=list[ActionPlanRead])
def list_action_plans(
    goal_id: int | None = Query(default=None, ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if goal_id is not None:
        plans = action_plan_service.list_action_plans_for_goal(db, current_user.id, goal_id)
    else:
        plans = action_plan_service.list_action_plans_for_user(db, current_user.id)
    return [ActionPlanRead.model_validate(plan) for plan in plans]


@router.patch("/{plan_id}/items/{item_id}", response_model=ActionPlanItemRead)
def patch_action_plan_item_completion(
    plan_id: int,
    item_id: int,
    payload: ActionPlanItemCompletionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = action_plan_service.update_action_plan_item_completion(
        db,
        current_user.id,
        plan_id,
        item_id,
        completed=payload.completed,
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action plan item not found")
    return ActionPlanItemRead.model_validate(item)


@router.get("/{plan_id}", response_model=ActionPlanDetailRead)
def get_action_plan_detail(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan = action_plan_service.get_plan_detail(db, current_user.id, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action plan not found")
    return plan


@router.post("/{plan_id}/refresh", response_model=ActionPlanDetailRead, status_code=status.HTTP_202_ACCEPTED)
def refresh_action_plan(
    plan_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not settings.ACTION_PLAN_ENABLED:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Action plan feature is disabled")

    existing_plan = action_plan_service.get_action_plan_for_user(db, current_user.id, plan_id)
    already_in_progress = bool(existing_plan and existing_plan.status == ActionPlanStatus.IN_PROGRESS.value)
    if already_in_progress:
        plan = existing_plan
    else:
        plan = action_plan_service.prepare_action_plan_for_refresh(db, current_user.id, plan_id, reset_items=False)
        if not plan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action plan not found")
        background_tasks.add_task(_process_action_plan_in_background, plan.id, current_user.id)

    detail = action_plan_service.get_plan_detail(db, current_user.id, plan.id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action plan not found")
    return detail


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_action_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan = action_plan_service.get_action_plan_for_user(db, current_user.id, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action plan not found")

    db.delete(plan)
    db.commit()