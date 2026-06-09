"""Shared helpers for goal breakdown tree roles (goal wrapper / main pillar / branch)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.goal import GoalBreakdown


def list_root_breakdown_nodes(db: Session, goal_id: int) -> list[GoalBreakdown]:
    return (
        db.query(GoalBreakdown)
        .filter(GoalBreakdown.goal_id == goal_id, GoalBreakdown.parent_id.is_(None))
        .order_by(GoalBreakdown.sequence.asc(), GoalBreakdown.id.asc())
        .all()
    )


def list_direct_children(db: Session, parent_id: int) -> list[GoalBreakdown]:
    return (
        db.query(GoalBreakdown)
        .filter(GoalBreakdown.parent_id == parent_id)
        .order_by(GoalBreakdown.sequence.asc(), GoalBreakdown.id.asc())
        .all()
    )


def node_has_children(db: Session, node_id: int) -> bool:
    return (
        db.query(GoalBreakdown.id)
        .filter(GoalBreakdown.parent_id == node_id)
        .first()
        is not None
    )


def is_three_level_goal_wrapper(db: Session, roots: list[GoalBreakdown]) -> bool:
    """True when a single root has children that themselves have children (goal → mains → branches)."""
    if len(roots) != 1:
        return False
    children = list_direct_children(db, roots[0].id)
    if not children:
        return False
    return any(node_has_children(db, child.id) for child in children)


def list_main_breakdown_nodes(db: Session, goal_id: int) -> list[GoalBreakdown]:
    """Main pillars: each gets one action plan. Branches are their direct children."""
    roots = list_root_breakdown_nodes(db, goal_id)
    if not roots:
        return []
    if is_three_level_goal_wrapper(db, roots):
        return list_direct_children(db, roots[0].id)
    return roots


def list_main_breakdown_ids(db: Session, goal_id: int) -> list[int]:
    return [node.id for node in list_main_breakdown_nodes(db, goal_id)]
