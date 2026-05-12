from __future__ import annotations

import logging

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.domain_events import DomainEvent, DomainEventName
from app.core.event_bus import event_bus
from app.schemas.goal import GoalCreate
from app.services import action_plan_service, chat_service, extended_profile_service, goal_service


logger = logging.getLogger("ai_mentor.orchestrator")
_INITIALIZED = False


def _build_goal_breakdown_prompt(goal_title: str, goal_description: str | None, user_extended_profile=None) -> str:
    lines: list[str] = []

    lines.append("Goal to break down:")
    lines.append(f"Title: {goal_title}")
    if goal_description:
        lines.append(f"Description: {goal_description}")

    if user_extended_profile:
        lines.append("\nUser profile context:")
        if user_extended_profile.goals:
            lines.append(f"User's goals: {', '.join(user_extended_profile.goals)}")
        if user_extended_profile.skills:
            lines.append(f"User's skills: {', '.join(user_extended_profile.skills)}")
        if user_extended_profile.interests:
            lines.append(f"User's interests: {', '.join(user_extended_profile.interests)}")

    return "\n".join(lines)


def _publish_followup_event(event_name: DomainEventName, *, source_event: DomainEvent, payload: dict) -> None:
    event_bus.publish(
        event_name=event_name.value,
        user_id=source_event.user_id,
        payload=payload,
        trace_id=source_event.trace_id,
        fail_fast=False,
    )


def _normalize_goal_candidates(raw_goals: object) -> list[str]:
    if not isinstance(raw_goals, list):
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_goals:
        title = str(item).strip()
        if not title:
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(title)
    return normalized


def _on_chat_message(event: DomainEvent) -> None:
    session_id = event.payload.get("session_id")
    if not isinstance(session_id, int) or session_id <= 0:
        logger.warning("Skip chat event without valid session_id trace_id=%s", event.trace_id)
        return

    db = SessionLocal()
    try:
        messages = extended_profile_service.list_recent_messages_for_session(
            db,
            session_id=session_id,
            limit=settings.PROFILE_EXTRACTION_MESSAGE_WINDOW,
        )
        extraction_input = extended_profile_service.build_extraction_input(messages)
        if not extraction_input:
            return

        raw_result = chat_service.build_profile_extraction_response(extraction_input)
        extraction_result = extended_profile_service.parse_extraction_result(raw_result)
        profile = extended_profile_service.apply_extraction_result_for_user(
            db,
            user_id=event.user_id,
            result=extraction_result,
        )

        _publish_followup_event(
            DomainEventName.ON_PROFILE_UPDATED,
            source_event=event,
            payload={
                "session_id": session_id,
                "profile_id": profile.id,
                "extracted": extraction_result.model_dump(),
            },
        )
    finally:
        db.close()


def _on_profile_updated(event: DomainEvent) -> None:
    extracted = event.payload.get("extracted")
    goals_raw = extracted.get("goals") if isinstance(extracted, dict) else []
    goal_titles = _normalize_goal_candidates(goals_raw)
    if not goal_titles:
        return

    db = SessionLocal()
    try:
        existing_goals = goal_service.list_goals_for_user(db, event.user_id)
        existing_titles = {
            (goal.title or "").strip().lower()
            for goal in existing_goals
            if (goal.title or "").strip()
        }

        for title in goal_titles:
            title_key = title.lower()
            if title_key in existing_titles:
                continue

            goal = goal_service.create_goal(
                db,
                event.user_id,
                GoalCreate(
                    title=title,
                    description="Detected from AI conversation analysis.",
                    priority="medium",
                    target_date=None,
                ),
            )
            existing_titles.add(title_key)
            _publish_followup_event(
                DomainEventName.ON_GOAL_DETECTED,
                source_event=event,
                payload={
                    "goal_id": goal.id,
                    "goal_title": goal.title,
                    "goal_description": goal.description,
                    "source": "profile_extraction",
                },
            )
    finally:
        db.close()


def _on_goal_detected(event: DomainEvent) -> None:
    goal_id = event.payload.get("goal_id")
    if not isinstance(goal_id, int) or goal_id <= 0:
        logger.warning("Skip goal detection event without valid goal_id trace_id=%s", event.trace_id)
        return

    db = SessionLocal()
    try:
        goal = goal_service.get_goal_for_user(db, event.user_id, goal_id)
        if not goal:
            logger.warning("Goal not found for breakdown goal_id=%s user_id=%s", goal_id, event.user_id)
            return

        user_profile = extended_profile_service.get_profile_for_user(db, event.user_id)
        prompt = _build_goal_breakdown_prompt(goal.title, goal.description, user_profile)
        raw_response = chat_service.build_goal_breakdown_response(prompt)
        breakdown_data = goal_service.parse_goal_breakdown_response(raw_response)
        if not breakdown_data:
            logger.warning("Failed to parse goal breakdown for goal_id=%s", goal_id)
            return

        success = goal_service.apply_goal_breakdown_for_user(db, event.user_id, goal_id, breakdown_data)
        if not success:
            logger.warning("Failed to apply goal breakdown for goal_id=%s", goal_id)
            return

        _publish_followup_event(
            DomainEventName.ON_GOAL_BREAKDOWN,
            source_event=event,
            payload={
                "goal_id": goal_id,
            },
        )
    finally:
        db.close()


def _on_goal_breakdown(event: DomainEvent) -> None:
    goal_id = event.payload.get("goal_id")
    if not isinstance(goal_id, int) or goal_id <= 0:
        logger.warning("Skip goal breakdown event without valid goal_id trace_id=%s", event.trace_id)
        return

    db = SessionLocal()
    try:
        plan = action_plan_service.prepare_action_plan_for_goal(
            db,
            event.user_id,
            goal_id,
            reset_items=False,
        )
        if not plan:
            logger.warning("Failed to prepare action plan for goal_id=%s user_id=%s", goal_id, event.user_id)
            return

        try:
            action_plan_service.generate_action_plan_with_retry(db, event.user_id, plan.id)
        except (RuntimeError, ValueError) as exc:
            action_plan_service.mark_action_plan_failed(db, plan.id, str(exc))
            logger.warning(
                "Action plan generation failed plan_id=%s goal_id=%s user_id=%s error=%s",
                plan.id,
                goal_id,
                event.user_id,
                exc,
            )

        refreshed = action_plan_service.get_action_plan_for_user(db, event.user_id, plan.id)
        _publish_followup_event(
            DomainEventName.ON_ACTION_GENERATED,
            source_event=event,
            payload={
                "goal_id": goal_id,
                "plan_id": plan.id,
                "plan_status": refreshed.status if refreshed else "failed",
            },
        )
    finally:
        db.close()


def _on_action_generated(event: DomainEvent) -> None:
    logger.info(
        "Action plan generated user_id=%s trace_id=%s payload=%s",
        event.user_id,
        event.trace_id,
        event.payload,
    )


def _on_action_completed(event: DomainEvent) -> None:
    logger.info(
        "Action completed user_id=%s trace_id=%s payload=%s",
        event.user_id,
        event.trace_id,
        event.payload,
    )


def _on_growth_updated(event: DomainEvent) -> None:
    logger.info(
        "Growth updated user_id=%s trace_id=%s payload=%s",
        event.user_id,
        event.trace_id,
        event.payload,
    )


def initialize_growth_cycle_orchestrator() -> None:
    global _INITIALIZED
    if _INITIALIZED:
        return

    event_bus.subscribe(DomainEventName.ON_CHAT_MESSAGE.value, _on_chat_message)
    event_bus.subscribe(DomainEventName.ON_PROFILE_UPDATED.value, _on_profile_updated)
    event_bus.subscribe(DomainEventName.ON_GOAL_DETECTED.value, _on_goal_detected)
    event_bus.subscribe(DomainEventName.ON_GOAL_BREAKDOWN.value, _on_goal_breakdown)
    event_bus.subscribe(DomainEventName.ON_ACTION_GENERATED.value, _on_action_generated)
    event_bus.subscribe(DomainEventName.ON_ACTION_COMPLETED.value, _on_action_completed)
    event_bus.subscribe(DomainEventName.ON_GROWTH_UPDATED.value, _on_growth_updated)

    _INITIALIZED = True
    logger.info("Growth cycle orchestrator initialized")

