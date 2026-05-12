import logging
from threading import RLock

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.event_bus import event_bus
from app.models.action_plan import ActionPlanItem, ActionPlanStatus
from app.models.chat import ChatSession
from app.models.goal import Goal
from app.models.growth_record import GrowthRecordSource, GrowthRecordType
from app.schemas.goal import GoalCreate
from app.services import action_plan_service, ai_service, extended_profile_service, goal_service
from app.services.growth_record_service import create_growth_record

logger = logging.getLogger(__name__)

EVENT_CHAT_MESSAGE = "on_chat_message"
EVENT_PROFILE_UPDATED = "on_profile_updated"
EVENT_GOAL_DETECTED = "on_goal_detected"
EVENT_GOAL_BREAKDOWN = "on_goal_breakdown"
EVENT_ACTION_GENERATED = "on_action_generated"
EVENT_ACTION_COMPLETED = "on_action_completed"
EVENT_GROWTH_UPDATED = "on_growth_updated"

_registered = False
_register_lock = RLock()


def ensure_handlers_registered() -> None:
    global _registered
    if _registered:
        return
    with _register_lock:
        if _registered:
            return
        event_bus.subscribe(EVENT_CHAT_MESSAGE, _on_chat_message)
        event_bus.subscribe(EVENT_PROFILE_UPDATED, _on_profile_updated)
        event_bus.subscribe(EVENT_GOAL_DETECTED, _on_goal_detected)
        event_bus.subscribe(EVENT_GOAL_BREAKDOWN, _on_goal_breakdown)
        event_bus.subscribe(EVENT_ACTION_GENERATED, _on_action_generated)
        event_bus.subscribe(EVENT_ACTION_COMPLETED, _on_action_completed)
        event_bus.subscribe(EVENT_GROWTH_UPDATED, _on_growth_updated)
        _registered = True


def run_chat_automation_pipeline(db: Session, *, session_id: int, user_id: int | None) -> None:
    ensure_handlers_registered()
    event_bus.publish(
        db,
        EVENT_CHAT_MESSAGE,
        {
            "session_id": session_id,
            "user_id": user_id,
        },
    )


def _on_chat_message(db: Session, payload: dict) -> None:
    if not settings.PROFILE_EXTRACTION_ENABLED:
        return

    session_id = int(payload.get("session_id", 0) or 0)
    user_id = payload.get("user_id")
    if not session_id:
        return

    if user_id is None:
        session_obj = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session_obj:
            return
        user_id = session_obj.user_id

    try:
        extraction_outcome = ai_service.extract_profile_from_session(
            db,
            session_id=session_id,
            user_id=user_id,
            message_window=settings.PROFILE_EXTRACTION_MESSAGE_WINDOW,
        )
    except Exception as exc:
        logger.warning(
            "Profile extraction pipeline failed session_id=%s user_id=%s error=%s",
            session_id,
            user_id,
            exc,
        )
        return

    if not extraction_outcome:
        return

    profile, extraction = extraction_outcome
    event_bus.publish(
        db,
        EVENT_PROFILE_UPDATED,
        {
            "user_id": user_id,
            "profile": profile,
            "goal_signals": extraction.goals,
        },
    )


def _on_profile_updated(db: Session, payload: dict) -> None:
    user_id = int(payload.get("user_id", 0) or 0)
    if not user_id:
        return

    profile = payload.get("profile")
    goal_signals = payload.get("goal_signals") or []
    candidate_titles: list[str] = []
    if isinstance(goal_signals, list):
        candidate_titles.extend([str(item).strip() for item in goal_signals])
    if profile is not None and getattr(profile, "goals", None):
        candidate_titles.extend([str(item).strip() for item in profile.goals])

    normalized_candidates: list[str] = []
    for title in candidate_titles:
        if not title:
            continue
        if title not in normalized_candidates:
            normalized_candidates.append(title)

    for title in normalized_candidates:
        if _goal_exists_for_user(db, user_id=user_id, title=title):
            continue

        goal = goal_service.create_goal(
            db,
            user_id,
            GoalCreate(
                title=title,
                description="来自聊天自动识别",
                priority="medium",
            ),
        )
        event_bus.publish(
            db,
            EVENT_GOAL_DETECTED,
            {
                "user_id": user_id,
                "goal_id": goal.id,
            },
        )


def _on_goal_detected(db: Session, payload: dict) -> None:
    if not settings.GOAL_BREAKDOWN_ENABLED:
        return

    user_id = int(payload.get("user_id", 0) or 0)
    goal_id = int(payload.get("goal_id", 0) or 0)
    if not user_id or not goal_id:
        return

    goal = goal_service.get_goal_for_user(db, user_id, goal_id)
    if not goal:
        return

    profile = extended_profile_service.get_profile_for_user(db, user_id)
    prompt = ai_service.build_goal_breakdown_prompt(goal, profile)

    try:
        raw_response = ai_service.generate_goal_breakdown(prompt)
        breakdown_data = goal_service.parse_goal_breakdown_response(raw_response)
    except Exception as exc:
        logger.warning("Goal breakdown pipeline failed goal_id=%s error=%s", goal_id, exc)
        return

    if not breakdown_data:
        return

    success = goal_service.apply_goal_breakdown_for_user(db, user_id, goal_id, breakdown_data)
    if not success:
        return

    event_bus.publish(
        db,
        EVENT_GOAL_BREAKDOWN,
        {
            "user_id": user_id,
            "goal_id": goal_id,
        },
    )


def _on_goal_breakdown(db: Session, payload: dict) -> None:
    if not settings.ACTION_PLAN_ENABLED:
        return

    user_id = int(payload.get("user_id", 0) or 0)
    goal_id = int(payload.get("goal_id", 0) or 0)
    if not user_id or not goal_id:
        return

    try:
        plan = action_plan_service.create_action_plan_for_goal(db, user_id, goal_id)
    except Exception as exc:
        logger.warning("Action plan pipeline failed goal_id=%s error=%s", goal_id, exc)
        return

    if not plan:
        return

    event_bus.publish(
        db,
        EVENT_ACTION_GENERATED,
        {
            "user_id": user_id,
            "plan_id": plan.id,
        },
    )


def _on_action_generated(db: Session, payload: dict) -> None:
    user_id = int(payload.get("user_id", 0) or 0)
    plan_id = int(payload.get("plan_id", 0) or 0)
    if not user_id or not plan_id:
        return

    completed_items = (
        db.query(ActionPlanItem)
        .filter(ActionPlanItem.plan_id == plan_id, ActionPlanItem.status == ActionPlanStatus.COMPLETED.value)
        .all()
    )
    for item in completed_items:
        event_bus.publish(
            db,
            EVENT_ACTION_COMPLETED,
            {
                "user_id": user_id,
                "action_item_id": item.id,
                "action_title": item.title,
                "action_description": item.description,
            },
        )


def _on_action_completed(db: Session, payload: dict) -> None:
    user_id = int(payload.get("user_id", 0) or 0)
    action_item_id = int(payload.get("action_item_id", 0) or 0)
    action_title = str(payload.get("action_title", "")).strip()
    action_description = payload.get("action_description")
    if not user_id or not action_item_id or not action_title:
        return

    idempotency_key = f"action-plan-item:{action_item_id}"
    record = create_growth_record(
        db,
        user_id,
        title=action_title,
        summary=action_description,
        content=f"自动回写：来自行动计划条目 {action_item_id}",
        record_type=GrowthRecordType.ACTION_PLAN.value,
        source_type=GrowthRecordSource.ACTION_PLAN.value,
        source_ref_id=action_item_id,
        idempotency_key=idempotency_key,
    )

    event_bus.publish(
        db,
        EVENT_GROWTH_UPDATED,
        {
            "user_id": user_id,
            "growth_title": record.title,
        },
    )


def _on_growth_updated(db: Session, payload: dict) -> None:
    user_id = int(payload.get("user_id", 0) or 0)
    growth_title = str(payload.get("growth_title", "")).strip()
    if not user_id or not growth_title:
        return

    profile = extended_profile_service.get_or_create_profile_for_user(db, user_id)
    updated_skills = extended_profile_service.merge_unique(profile.skills, [growth_title])
    if updated_skills == profile.skills:
        return

    profile.skills = updated_skills
    db.commit()
    db.refresh(profile)


def _goal_exists_for_user(db: Session, *, user_id: int, title: str) -> bool:
    normalized = title.strip().lower()
    if not normalized:
        return True

    existing_goals = db.query(Goal).filter(Goal.user_id == user_id).all()
    return any((goal.title or "").strip().lower() == normalized for goal in existing_goals)
