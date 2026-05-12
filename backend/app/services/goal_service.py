import logging

from sqlalchemy.orm import Session

from app.models.goal import Goal, GoalBreakdown, GoalStatus, GoalPriority, GoalBreakdownStatus
from app.schemas.goal import (
    GoalCreate,
    GoalUpdate,
    GoalRead,
    GoalDetailRead,
    GoalBreakdownNode,
    GoalBreakdownTree,
)
import app.services.breakdown_service as breakdown_service

logger = logging.getLogger(__name__)


def get_goal_for_user(db: Session, user_id: int, goal_id: int) -> Goal | None:
    """获取用户的某个目标"""
    return db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user_id).first()


def list_goals_for_user(db: Session, user_id: int, status: str | None = None) -> list[Goal]:
    """列出用户的所有目标"""
    query = db.query(Goal).filter(Goal.user_id == user_id)
    if status:
        query = query.filter(Goal.status == status)
    return query.order_by(Goal.created_at.desc(), Goal.id.desc()).all()


def create_goal(db: Session, user_id: int, goal_in: GoalCreate) -> Goal:
    """创建目标"""
    goal = Goal(
        user_id=user_id,
        title=goal_in.title,
        description=goal_in.description,
        priority=goal_in.priority or GoalPriority.MEDIUM.value,
        target_date=goal_in.target_date,
        status=GoalStatus.ACTIVE.value,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def update_goal(db: Session, user_id: int, goal_id: int, goal_in: GoalUpdate) -> Goal | None:
    """更新目标元信息"""
    goal = get_goal_for_user(db, user_id, goal_id)
    if not goal:
        return None

    update_data = goal_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(goal, field, value)

    db.commit()
    db.refresh(goal)
    return goal


def delete_goal(db: Session, user_id: int, goal_id: int) -> bool:
    """删除目标及其所有拆解节点"""
    goal = get_goal_for_user(db, user_id, goal_id)
    if not goal:
        return False

    db.delete(goal)
    db.commit()
    return True


def _build_breakdown_node_tree(breakdown: GoalBreakdown) -> GoalBreakdownNode:
    """递归构建拆解节点树"""
    children = sorted(breakdown.children, key=lambda x: x.sequence)
    return GoalBreakdownNode(
        id=breakdown.id,
        title=breakdown.title,
        description=breakdown.description,
        level=breakdown.level,
        sequence=breakdown.sequence,
        status=breakdown.status.value if hasattr(breakdown.status, 'value') else breakdown.status,
        due_date=breakdown.due_date,
        children=[_build_breakdown_node_tree(child) for child in children],
        created_at=breakdown.created_at,
        updated_at=breakdown.updated_at,
    )


def _get_goal_breakdown_tree(db: Session, goal: Goal) -> GoalBreakdownTree:
    """构建目标的完整拆解树"""
    # 只获取根节点（parent_id 为 None）
    root_breakdowns = db.query(GoalBreakdown).filter(
        GoalBreakdown.goal_id == goal.id,
        GoalBreakdown.parent_id.is_(None),
    ).order_by(GoalBreakdown.sequence).all()

    root_nodes = [_build_breakdown_node_tree(bd) for bd in root_breakdowns]

    return GoalBreakdownTree(
        goal_id=goal.id,
        title=goal.title,
        description=goal.description,
        root_nodes=root_nodes,
    )


def get_goal_detail_for_user(db: Session, user_id: int, goal_id: int) -> GoalDetailRead | None:
    """获取目标详情包含拆解树"""
    goal = get_goal_for_user(db, user_id, goal_id)
    if not goal:
        return None

    breakdown_tree = _get_goal_breakdown_tree(db, goal)

    return GoalDetailRead(
        id=goal.id,
        user_id=goal.user_id,
        title=goal.title,
        description=goal.description,
        status=goal.status.value if hasattr(goal.status, 'value') else goal.status,
        priority=goal.priority.value if hasattr(goal.priority, 'value') else goal.priority,
        target_date=goal.target_date,
        created_at=goal.created_at,
        updated_at=goal.updated_at,
        breakdowns=breakdown_tree,
    )


def _clear_breakdowns_for_goal(db: Session, goal_id: int) -> None:
    """清除某个目标的所有拆解节点"""
    db.query(GoalBreakdown).filter(GoalBreakdown.goal_id == goal_id).delete()


def _insert_breakdown_nodes(
    db: Session,
    goal_id: int,
    nodes: list[dict],
    parent_id: int | None = None,
    level: int = 0,
) -> None:
    """递归插入拆解节点"""
    for sequence, node_data in enumerate(nodes):
        title = node_data.get("title", "Untitled")
        description = node_data.get("description", "")
        children = node_data.get("children", [])

        breakdown = GoalBreakdown(
            goal_id=goal_id,
            parent_id=parent_id,
            title=title,
            description=description,
            level=level,
            sequence=sequence,
            status=GoalBreakdownStatus.PENDING.value,
        )
        db.add(breakdown)
        db.flush()  # 获取自动生成的 ID

        if children:
            _insert_breakdown_nodes(db, goal_id, children, parent_id=breakdown.id, level=level + 1)


def parse_goal_breakdown_response(raw_text: str) -> dict | None:
    return breakdown_service.parse_breakdown_response(raw_text)


def _extract_breakdowns_from_response(response_data: dict) -> list[dict] | None:
    """从 AI 响应中提取 breakdowns 字段"""
    if not isinstance(response_data, dict):
        return None

    # 尝试多种可能的字段名
    for key in ["breakdowns", "breakdown", "subtasks", "steps", "tasks"]:
        if key in response_data:
            value = response_data[key]
            if isinstance(value, list):
                return value
            # 如果是字典，尝试从中提取列表
            if isinstance(value, dict) and "items" in value:
                items = value.get("items")
                if isinstance(items, list):
                    return items

    return None


def apply_goal_breakdown_for_user(
    db: Session,
    user_id: int,
    goal_id: int,
    breakdown_data: dict,
) -> bool:
    return breakdown_service.apply_breakdown_for_goal(db, user_id, goal_id, breakdown_data)


def create_goal_with_breakdown(
    db: Session,
    user_id: int,
    goal_in: GoalCreate,
    breakdown_data: dict | None = None,
) -> tuple[Goal, bool]:
    """
    创建目标，并可选地应用 AI 拆解结果。
    返回 (goal, breakdown_applied)。
    """
    goal = create_goal(db, user_id, goal_in)

    applied = False
    if breakdown_data:
        applied = apply_goal_breakdown_for_user(db, user_id, goal.id, breakdown_data)

    return goal, applied


def refresh_breakdown_for_user(
    db: Session,
    user_id: int,
    goal_id: int,
    breakdown_data: dict,
) -> bool:
    """重新拆解目标"""
    return breakdown_service.refresh_breakdown_for_goal(db, user_id, goal_id, breakdown_data)
