import json
import logging

from sqlalchemy.orm import Session

from app.models.goal import Goal, GoalBreakdown, GoalBreakdownStatus

logger = logging.getLogger(__name__)


def parse_breakdown_response(raw_text: str) -> dict | None:
    if not raw_text or not isinstance(raw_text, str):
        return None

    text = raw_text.strip()
    if not text:
        return None

    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
        try:
            payload = json.loads(text[start_idx : end_idx + 1])
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass

    logger.warning("Failed to parse goal breakdown response: %s", raw_text[:100])
    return None


def apply_breakdown_for_goal(
    db: Session,
    user_id: int,
    goal_id: int,
    breakdown_data: dict,
) -> bool:
    try:
        goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user_id).first()
        if not goal:
            return False

        db.query(GoalBreakdown).filter(GoalBreakdown.goal_id == goal_id).delete()
        breakdowns = _extract_breakdowns_from_response(breakdown_data)
        if not breakdowns:
            logger.warning("No breakdowns found in response for goal_id=%s", goal_id)
            return False

        _insert_breakdown_nodes(db, goal_id, breakdowns)
        db.commit()
        return True
    except Exception as exc:
        db.rollback()
        logger.error("Failed to apply goal breakdown for goal_id=%s: %s", goal_id, exc)
        return False


def refresh_breakdown_for_goal(
    db: Session,
    user_id: int,
    goal_id: int,
    breakdown_data: dict,
) -> bool:
    return apply_breakdown_for_goal(db, user_id, goal_id, breakdown_data)


def _extract_breakdowns_from_response(response_data: dict) -> list[dict] | None:
    if not isinstance(response_data, dict):
        return None

    for key in ["breakdowns", "breakdown", "subtasks", "steps", "tasks"]:
        if key in response_data:
            value = response_data[key]
            if isinstance(value, list):
                return value
            if isinstance(value, dict) and "items" in value:
                items = value.get("items")
                if isinstance(items, list):
                    return items
    return None


def _insert_breakdown_nodes(
    db: Session,
    goal_id: int,
    nodes: list[dict],
    parent_id: int | None = None,
    level: int = 0,
) -> None:
    for sequence, node_data in enumerate(nodes):
        breakdown = GoalBreakdown(
            goal_id=goal_id,
            parent_id=parent_id,
            title=node_data.get("title", "Untitled"),
            description=node_data.get("description", ""),
            level=level,
            sequence=sequence,
            status=GoalBreakdownStatus.PENDING.value,
        )
        db.add(breakdown)
        db.flush()

        children = node_data.get("children", [])
        if children:
            _insert_breakdown_nodes(db, goal_id, children, parent_id=breakdown.id, level=level + 1)

