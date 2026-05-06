import logging
import traceback

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.action_plan import ActionPlanCreate, ActionPlanDetailRead, ActionPlanRead
from app.services import action_plan_service

router = APIRouter(prefix="/action-plans", tags=["action-plans"])
error_logger = logging.getLogger("ai_mentor.errors")


@router.post("", response_model=ActionPlanDetailRead)
def create_action_plan(
    payload: ActionPlanCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not settings.ACTION_PLAN_ENABLED:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Action plan feature is disabled")

    try:
        plan = action_plan_service.create_action_plan_for_goal(db, current_user.id, payload.goal_id)
        if not plan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
        detail = action_plan_service.get_plan_detail(db, current_user.id, plan.id)
        if not detail:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action plan not found")
        return detail
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("", response_model=list[ActionPlanRead])
def list_action_plans(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plans = action_plan_service.list_action_plans_for_user(db, current_user.id)
    return [ActionPlanRead.model_validate(plan) for plan in plans]


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


@router.post("/{plan_id}/refresh", response_model=ActionPlanDetailRead)
def refresh_action_plan(
    plan_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not settings.ACTION_PLAN_ENABLED:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Action plan feature is disabled")

    try:
        plan = action_plan_service.refresh_action_plan(db, current_user.id, plan_id)
        if not plan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action plan not found")
        detail = action_plan_service.get_plan_detail(db, current_user.id, plan.id)
        if not detail:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action plan not found")
        return detail
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        error_logger.error(
            "refresh_action_plan failed plan_id=%s user_id=%s error=%s\n%s",
            plan_id,
            current_user.id,
            exc,
            traceback.format_exc(),
        )
        raise


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