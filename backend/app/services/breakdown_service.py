import json
import logging
import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.ukl_constants import (
    CONSTRAINT_HINT_KEYWORDS,
    REF_TYPE_GOAL,
    SLICE_TYPE_BREAKDOWN_ANCHORS,
    SLICE_TYPE_BREAKDOWN_SUMMARY,
    SOURCE_MODULE_BREAKDOWN,
)
from app.models.goal import Goal, GoalBreakdown, GoalBreakdownStatus
from app.schemas.ukl import BreakdownAnchorsPayload, BreakdownSummaryPayload
from app.services import profile_service

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
        ingest_breakdown_slices_for_goal(db, user_id, goal_id)
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


def ingest_breakdown_slices_for_goal(db: Session, user_id: int, goal_id: int) -> None:
    if not settings.UKL_ENABLED or not settings.BREAKDOWN_SUMMARY_ENABLED:
        return

    try:
        goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user_id).first()
        if not goal:
            return

        tree_text = _format_breakdown_tree_for_summary(db, goal_id)
        if not tree_text.strip():
            return

        from app.services import ai_service, ukl_service

        summary_input = (
            f"目标：{goal.title}\n"
            f"描述：{goal.description or '（无）'}\n\n"
            f"拆解结构：\n{tree_text}"
        )
        summary_text = ai_service.build_breakdown_summary_response(summary_input).strip()
        if not summary_text:
            summary_text = f"目标「{goal.title}」已拆解为可执行子节点。"

        constraints = _extract_critical_constraints(db, user_id, goal)
        dependency_notes = _extract_dependency_notes(db, goal_id)

        now = datetime.utcnow()
        ukl_service.ingest(
            db,
            user_id,
            slice_type=SLICE_TYPE_BREAKDOWN_SUMMARY,
            source_module=SOURCE_MODULE_BREAKDOWN,
            ref_type=REF_TYPE_GOAL,
            ref_id=goal_id,
            payload=BreakdownSummaryPayload(
                goal_id=goal_id,
                summary=summary_text,
                entity_updated_at=now,
            ),
        )
        ukl_service.ingest(
            db,
            user_id,
            slice_type=SLICE_TYPE_BREAKDOWN_ANCHORS,
            source_module=SOURCE_MODULE_BREAKDOWN,
            ref_type=REF_TYPE_GOAL,
            ref_id=goal_id,
            payload=BreakdownAnchorsPayload(
                goal_id=goal_id,
                critical_constraints=constraints,
                dependency_notes=dependency_notes,
            ),
        )
        db.commit()
    except Exception:
        logger.exception("UKL breakdown slice ingest failed goal_id=%s user_id=%s", goal_id, user_id)


def _format_breakdown_tree_for_summary(db: Session, goal_id: int) -> str:
    nodes = (
        db.query(GoalBreakdown)
        .filter(GoalBreakdown.goal_id == goal_id)
        .order_by(GoalBreakdown.level.asc(), GoalBreakdown.sequence.asc(), GoalBreakdown.id.asc())
        .all()
    )
    lines: list[str] = []
    for node in nodes:
        indent = "  " * int(node.level or 0)
        desc = f" — {node.description}" if node.description else ""
        lines.append(f"{indent}- [{node.id}] {node.title}{desc}")
    return "\n".join(lines)


def _extract_critical_constraints(db: Session, user_id: int, goal: Goal) -> list[str]:
    constraints: list[str] = []
    seen: set[str] = set()

    description = (goal.description or "").strip()
    if description:
        for fragment in re.split(r"[。；;\n]", description):
            text = fragment.strip()
            if not text:
                continue
            if any(keyword in text for keyword in CONSTRAINT_HINT_KEYWORDS):
                key = text.lower()
                if key not in seen:
                    seen.add(key)
                    constraints.append(text)

    profile = profile_service.get_or_create_profile_for_user(db, user_id)
    for habit in (profile.study_habits or [])[:3]:
        text = str(habit).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        if any(keyword in text for keyword in CONSTRAINT_HINT_KEYWORDS):
            seen.add(key)
            constraints.append(text)

    return constraints[:10]


def _extract_dependency_notes(db: Session, goal_id: int) -> list[str]:
    nodes = (
        db.query(GoalBreakdown)
        .filter(GoalBreakdown.goal_id == goal_id)
        .order_by(GoalBreakdown.level.asc(), GoalBreakdown.sequence.asc(), GoalBreakdown.id.asc())
        .all()
    )
    if len(nodes) <= 1:
        return []

    notes: list[str] = []
    children_by_parent: dict[int | None, list[GoalBreakdown]] = {}
    for node in nodes:
        children_by_parent.setdefault(node.parent_id, []).append(node)

    roots = children_by_parent.get(None, [])
    if roots:
        root_titles = "、".join(n.title for n in roots[:5])
        notes.append(f"顶层拆解支柱：{root_titles}")

    for parent_id, children in children_by_parent.items():
        if parent_id is None or len(children) < 2:
            continue
        parent = next((n for n in nodes if n.id == parent_id), None)
        if not parent:
            continue
        child_titles = "、".join(c.title for c in children[:6])
        notes.append(f"「{parent.title}」下含 {len(children)} 个子节点：{child_titles}")

    return notes[:8]


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
