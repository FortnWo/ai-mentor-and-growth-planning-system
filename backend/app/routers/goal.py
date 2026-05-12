import logging
import traceback

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.models.user import User
from app.schemas.goal import GoalCreate, GoalRead, GoalUpdate, GoalDetailRead
from app.services import ai_service, goal_service, extended_profile_service

router = APIRouter(prefix="/goals", tags=["goals"])
error_logger = logging.getLogger("ai_mentor.errors")


def _process_goal_breakdown_in_background(
    goal_id: int,
    user_id: int,
) -> None:
    """
    后台任务：触发 AI 目标拆解并持久化结果。
    """
    import app.core.database as database_module

    db = database_module.SessionLocal()
    try:
        # 获取用户扩展画像作为上下文
        user_profile = extended_profile_service.get_profile_for_user(db, user_id)

        goal = goal_service.get_goal_for_user(db, user_id, goal_id)
        if not goal:
            return

        # 构建 Prompt
        prompt = ai_service.build_goal_breakdown_prompt(goal, user_profile)

        # 调用 AI
        raw_response = ai_service.generate_goal_breakdown(prompt)

        # 解析 AI 响应
        breakdown_data = goal_service.parse_goal_breakdown_response(raw_response)
        if not breakdown_data:
            error_logger.warning("Failed to parse goal breakdown for goal_id=%s", goal_id)
            return

        # 应用拆解结果到数据库
        success = goal_service.apply_goal_breakdown_for_user(db, user_id, goal_id, breakdown_data)
        if not success:
            error_logger.warning("Failed to apply goal breakdown for goal_id=%s", goal_id)

    except Exception as exc:
        error_logger.error(
            "Goal breakdown background task failed for goal_id=%s: %s\n%s",
            goal_id,
            exc,
            traceback.format_exc(),
        )
    finally:
        db.close()


@router.post("", response_model=GoalRead, status_code=status.HTTP_201_CREATED)
def create_goal(
    payload: GoalCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建目标并异步触发 AI 拆解"""
    if not settings.GOAL_BREAKDOWN_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Goal breakdown feature is disabled",
        )

    # 创建目标
    goal = goal_service.create_goal(db, current_user.id, payload)

    # 后台触发 AI 拆解
    background_tasks.add_task(
        _process_goal_breakdown_in_background,
        goal.id,
        current_user.id,
    )

    return GoalRead.model_validate(goal)


@router.get("", response_model=list[GoalRead])
def list_goals(
    status: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列出用户的目标"""
    goals = goal_service.list_goals_for_user(db, current_user.id, status=status)
    return [GoalRead.model_validate(goal) for goal in goals]


@router.get("/{goal_id}", response_model=GoalDetailRead)
def get_goal_detail(
    goal_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取目标详情包含拆解树"""
    try:
        goal_detail = goal_service.get_goal_detail_for_user(db, current_user.id, goal_id)
        if not goal_detail:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
        return goal_detail
    except HTTPException:
        raise
    except Exception as exc:
        origin = request.headers.get("origin") if request is not None else None
        error_logger.error(
            "get_goal_detail failed goal_id=%s user_id=%s origin=%s error=%s\n%s",
            goal_id,
            current_user.id,
            origin,
            exc,
            traceback.format_exc(),
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal Server Error") from exc


@router.put("/{goal_id}", response_model=GoalRead)
def update_goal(
    goal_id: int,
    payload: GoalUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新目标元信息"""
    goal = goal_service.update_goal(db, current_user.id, goal_id, payload)
    if not goal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    return GoalRead.model_validate(goal)


@router.post("/{goal_id}/refresh-breakdown", status_code=status.HTTP_202_ACCEPTED)
def refresh_goal_breakdown(
    goal_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """重新拆解目标"""
    if not settings.GOAL_BREAKDOWN_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Goal breakdown feature is disabled",
        )

    goal = goal_service.get_goal_for_user(db, current_user.id, goal_id)
    if not goal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")

    # 后台重新拆解
    background_tasks.add_task(
        _process_goal_breakdown_in_background,
        goal.id,
        current_user.id,
    )

    return {"message": "Goal breakdown refresh started"}


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除目标及其拆解节点"""
    deleted = goal_service.delete_goal(db, current_user.id, goal_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
