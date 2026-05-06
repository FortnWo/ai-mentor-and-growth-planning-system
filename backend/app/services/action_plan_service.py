import json
import logging
from collections import defaultdict

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.action_plan import ActionPlan, ActionPlanFrequency, ActionPlanItem, ActionPlanStatus
from app.models.goal import Goal, GoalBreakdown
from app.models.extended_profile import UserExtendedProfile
from app.schemas.action_plan import ActionPlanDetailRead

logger = logging.getLogger(__name__)


def get_action_plan_for_user(db: Session, user_id: int, plan_id: int) -> ActionPlan | None:
    return (
        db.query(ActionPlan)
        .join(Goal, Goal.id == ActionPlan.goal_id)
        .filter(ActionPlan.id == plan_id, Goal.user_id == user_id)
        .first()
    )


def get_action_plan_for_goal(db: Session, user_id: int, goal_id: int) -> ActionPlan | None:
    return (
        db.query(ActionPlan)
        .join(Goal, Goal.id == ActionPlan.goal_id)
        .filter(ActionPlan.goal_id == goal_id, Goal.user_id == user_id)
        .first()
    )


def list_action_plans_for_user(db: Session, user_id: int) -> list[ActionPlan]:
    return (
        db.query(ActionPlan)
        .join(Goal, Goal.id == ActionPlan.goal_id)
        .filter(Goal.user_id == user_id)
        .order_by(ActionPlan.created_at.desc(), ActionPlan.id.desc())
        .all()
    )


def get_plan_detail(db: Session, user_id: int, plan_id: int) -> ActionPlanDetailRead | None:
    plan = get_action_plan_for_user(db, user_id, plan_id)
    if not plan:
        return None

    return ActionPlanDetailRead.model_validate(plan)


def create_action_plan_for_goal(db: Session, user_id: int, goal_id: int) -> ActionPlan | None:
    goal = _get_goal_for_user(db, user_id, goal_id)
    if not goal:
        return None

    raw_response = _generate_action_plan_response(db, goal)
    payload = parse_action_plan_response(raw_response)
    if payload is None:
        raise ValueError("AI output is not valid JSON")

    return _upsert_action_plan(db, goal, payload)


def refresh_action_plan(db: Session, user_id: int, plan_id: int) -> ActionPlan | None:
    plan = get_action_plan_for_user(db, user_id, plan_id)
    if not plan:
        return None

    goal = _get_goal_for_user(db, user_id, plan.goal_id)
    if not goal:
        return None

    raw_response = _generate_action_plan_response(db, goal)
    payload = parse_action_plan_response(raw_response)
    if payload is None:
        raise ValueError("AI output is not valid JSON")

    return _upsert_action_plan(db, goal, payload, existing_plan=plan)


def _get_goal_for_user(db: Session, user_id: int, goal_id: int) -> Goal | None:
    return db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user_id).first()


def _generate_action_plan_response(db: Session, goal: Goal) -> str:
    from app.services import chat_service, extended_profile_service

    profile = extended_profile_service.get_profile_for_user(db, goal.user_id)
    breakdowns = _list_breakdowns_for_goal(db, goal.id)
    prompt = _build_action_plan_prompt(goal, breakdowns, profile)
    return chat_service.build_action_plan_response(prompt)


def _build_action_plan_prompt(goal: Goal, breakdowns: list[GoalBreakdown], profile: UserExtendedProfile | None) -> str:
    lines: list[str] = []
    lines.append("Goal context:")
    lines.append(f"Title: {goal.title}")
    if goal.description:
        lines.append(f"Description: {goal.description}")
    if goal.priority:
        lines.append(f"Priority: {goal.priority}")
    if goal.target_date:
        lines.append(f"Target date: {goal.target_date}")

    if profile:
        profile_bits: list[str] = []
        if profile.goals:
            profile_bits.append(f"goals={', '.join(profile.goals)}")
        if profile.skills:
            profile_bits.append(f"skills={', '.join(profile.skills)}")
        if profile.interests:
            profile_bits.append(f"interests={', '.join(profile.interests)}")
        if profile.study_habits:
            profile_bits.append(f"study_habits={', '.join(profile.study_habits)}")
        if profile.preferences:
            profile_bits.append(f"preferences={', '.join(profile.preferences)}")
        if profile_bits:
            lines.append("\nExtended profile context:")
            lines.extend(profile_bits)

    lines.append("\nGoal breakdown context:")
    lines.extend(_format_breakdown_tree_lines(breakdowns))

    lines.append(
        "\nReturn strict JSON with structure: {\"plan\": {\"title\": string, \"summary\": string}, "
        "\"items\": [{\"title\": string, \"description\": string|null, \"frequency\": string, "
        "\"schedule\": string|null, \"status\": string, \"start_date\": string|null, "
        "\"due_date\": string|null, \"sequence\": number, \"breakdown_ref\": number|string|null}] }"
    )

    return "\n".join(lines)


def _list_breakdowns_for_goal(db: Session, goal_id: int) -> list[GoalBreakdown]:
    return (
        db.query(GoalBreakdown)
        .filter(GoalBreakdown.goal_id == goal_id)
        .order_by(GoalBreakdown.level.asc(), GoalBreakdown.sequence.asc(), GoalBreakdown.id.asc())
        .all()
    )


def _format_breakdown_tree_lines(breakdowns: list[GoalBreakdown]) -> list[str]:
    if not breakdowns:
        return ["- No breakdowns available"]

    children_map: dict[int | None, list[GoalBreakdown]] = defaultdict(list)
    for breakdown in breakdowns:
        children_map[breakdown.parent_id].append(breakdown)

    for nodes in children_map.values():
        nodes.sort(key=lambda item: (item.sequence, item.id))

    lines: list[str] = []
    limit = max(settings.ACTION_PLAN_CONTEXT_MESSAGE_WINDOW, 1)
    visited = 0

    def walk(node_list: list[GoalBreakdown], depth: int = 0) -> None:
        nonlocal visited
        for node in node_list:
            if visited >= limit:
                return
            indent = "  " * depth
            description = f" - {node.description}" if node.description else ""
            due_date = f", due {node.due_date}" if node.due_date else ""
            lines.append(
                f"{indent}- [{node.id}] {node.title}{description}"
                f" (level={node.level}, status={node.status}{due_date})"
            )
            visited += 1
            walk(children_map.get(node.id, []), depth + 1)

    walk(children_map.get(None, []))

    if visited >= limit and len(breakdowns) > limit:
        lines.append(f"- ... truncated at {limit} nodes for context budget")

    return lines


def _upsert_action_plan(
    db: Session,
    goal: Goal,
    payload: dict,
    existing_plan: ActionPlan | None = None,
) -> ActionPlan:
    plan_data = payload.get("plan") if isinstance(payload.get("plan"), dict) else {}
    items_data = payload.get("items") if isinstance(payload.get("items"), list) else []

    plan = existing_plan or get_action_plan_for_goal(db, goal.user_id, goal.id)
    if plan is None:
        plan = ActionPlan(goal_id=goal.id, title=_normalize_plan_title(goal, plan_data), summary=_normalize_text(plan_data.get("summary")))
        db.add(plan)
        db.flush()
    else:
        plan.title = _normalize_plan_title(goal, plan_data)
        plan.summary = _normalize_text(plan_data.get("summary"))

    plan.status = _normalize_status(plan_data.get("status"), default=ActionPlanStatus.PENDING.value)

    db.query(ActionPlanItem).filter(ActionPlanItem.plan_id == plan.id).delete(synchronize_session=False)

    normalized_items = _normalize_items_payload(items_data)
    if not normalized_items:
        logger.warning("Action plan generation produced no items for goal_id=%s", goal.id)

    breakdown_lookup = _build_breakdown_lookup(db, goal.id)

    for item_data in normalized_items:
        breakdown_ref = item_data.get("breakdown_ref")
        breakdown_id = _resolve_breakdown_ref(breakdown_ref, breakdown_lookup)

        db.add(
            ActionPlanItem(
                plan_id=plan.id,
                breakdown_id=breakdown_id,
                title=item_data["title"],
                description=item_data.get("description"),
                frequency=_normalize_frequency(item_data.get("frequency")),
                schedule=_normalize_text(item_data.get("schedule")),
                status=_normalize_status(item_data.get("status"), default=ActionPlanStatus.PENDING.value),
                start_date=_normalize_date(item_data.get("start_date")),
                due_date=_normalize_date(item_data.get("due_date")),
                sequence=item_data["sequence"],
            )
        )

    db.commit()
    db.refresh(plan)
    return plan


def parse_action_plan_response(raw_text: str) -> dict | None:
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

    logger.warning("Failed to parse action plan response: %s", raw_text[:120])
    return None


def _normalize_plan_title(goal: Goal, plan_data: dict) -> str:
    title = plan_data.get("title") if isinstance(plan_data, dict) else None
    text = _normalize_text(title)
    return text or f"{goal.title} Action Plan"


def _normalize_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_status(value: object, *, default: str) -> str:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {status.value for status in ActionPlanStatus}:
            return normalized
    return default


def _normalize_frequency(value: object) -> str:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {frequency.value for frequency in ActionPlanFrequency}:
            return normalized
    return ActionPlanFrequency.CUSTOM.value


def _normalize_date(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_items_payload(items_data: object) -> list[dict]:
    if not isinstance(items_data, list):
        return []

    normalized_items: list[dict] = []
    for sequence, raw_item in enumerate(items_data):
        if not isinstance(raw_item, dict):
            continue

        title = _normalize_text(raw_item.get("title")) or f"Action Item {sequence + 1}"
        normalized_items.append(
            {
                "title": title,
                "description": _normalize_text(raw_item.get("description")),
                "frequency": _normalize_frequency(raw_item.get("frequency")),
                "schedule": _normalize_text(raw_item.get("schedule")),
                "status": _normalize_status(raw_item.get("status"), default=ActionPlanStatus.PENDING.value),
                "start_date": _normalize_date(raw_item.get("start_date")),
                "due_date": _normalize_date(raw_item.get("due_date")),
                "sequence": _normalize_sequence(raw_item.get("sequence"), sequence),
                "breakdown_ref": raw_item.get("breakdown_ref"),
            }
        )

    return normalized_items


def _normalize_sequence(value: object, fallback: int) -> int:
    try:
        if value is None or value == "":
            return fallback
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _build_breakdown_lookup(db: Session, goal_id: int) -> dict[str, int]:
    lookup: dict[str, int] = {}
    for breakdown in _list_breakdowns_for_goal(db, goal_id):
        lookup[str(breakdown.id)] = breakdown.id
        title_key = _normalize_lookup_key(breakdown.title)
        if title_key:
            lookup[title_key] = breakdown.id
    return lookup


def _resolve_breakdown_ref(value: object, breakdown_lookup: dict[str, int]) -> int | None:
    if value is None:
        return None

    if isinstance(value, int):
        return value if str(value) in breakdown_lookup else None

    text = str(value).strip()
    if not text:
        return None

    lookup_key = _normalize_lookup_key(text)
    if lookup_key and lookup_key in breakdown_lookup:
        return breakdown_lookup[lookup_key]

    if text.isdigit() and text in breakdown_lookup:
        return breakdown_lookup[text]

    return None


def _normalize_lookup_key(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None