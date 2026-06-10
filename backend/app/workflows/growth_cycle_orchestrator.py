"""成长周期事件编排：订阅领域事件并串联画像、拆解、计划等异步任务。

应用启动时调用 initialize_growth_cycle_orchestrator 注册 handler；
各 handler 在独立 session_scope 中执行业务逻辑，必要时发布后续事件。
"""

from __future__ import annotations

import logging

from app.core.db_session import session_scope
from app.core.domain_events import DomainEvent, DomainEventName
from app.core.event_bus import event_bus
from app.schemas.goal import GoalCreate
import app.services.breakdown_service as breakdown_service
import app.services.chat_service as chat_service
import app.services.goal_service as goal_service
import app.services.plan_service as plan_service
import app.services.profile_extraction_service as profile_extraction_service
import app.services.profile_service as profile_service
import app.services.ukl_prompt_service as ukl_prompt_service


logger = logging.getLogger("ai_mentor.orchestrator")
_INITIALIZED = False


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

    assistant_message_id = event.payload.get("assistant_message_id")
    profile_extraction_service.schedule_profile_extraction_from_chat(
        user_id=event.user_id,
        session_id=session_id,
        assistant_message_id=assistant_message_id if isinstance(assistant_message_id, int) else None,
        trace_id=event.trace_id,
    )


def _on_profile_updated(event: DomainEvent) -> None:
    extracted = event.payload.get("extracted")
    goals_raw = extracted.get("goals") if isinstance(extracted, dict) else []
    goal_titles = _normalize_goal_candidates(goals_raw)
    if not goal_titles:
        return

    with session_scope() as db:
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
                    description="从 AI 对话分析中检测到的目标。",
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


def _on_goal_detected(event: DomainEvent) -> None:
    goal_id = event.payload.get("goal_id")
    if not isinstance(goal_id, int) or goal_id <= 0:
        logger.warning("Skip goal detection event without valid goal_id trace_id=%s", event.trace_id)
        return

    prompt: str | None = None
    with session_scope() as db:
        goal = goal_service.get_goal_for_user(db, event.user_id, goal_id)
        if not goal:
            logger.warning("Goal not found for breakdown goal_id=%s user_id=%s", goal_id, event.user_id)
            return
        prompt = ukl_prompt_service.build_goal_breakdown_prompt(db, event.user_id, goal)

    raw_response = chat_service.build_goal_breakdown_response(prompt)
    breakdown_data = breakdown_service.parse_breakdown_response(raw_response)
    if not breakdown_data:
        logger.warning("Failed to parse goal breakdown for goal_id=%s", goal_id)
        return

    with session_scope() as db:
        success = breakdown_service.apply_breakdown_for_goal(db, event.user_id, goal_id, breakdown_data)
        if not success:
            logger.warning("Failed to apply goal breakdown for goal_id=%s", goal_id)
            return

        try:
            from app.services import ukl_narrative_service

            ukl_narrative_service.ingest_goal_intent_for_goal(db, event.user_id, goal_id)
        except Exception:
            logger.exception("Goal intent ingest failed goal_id=%s", goal_id)

    _publish_followup_event(
        DomainEventName.ON_GOAL_BREAKDOWN,
        source_event=event,
        payload={
            "goal_id": goal_id,
        },
    )


def _on_goal_breakdown(event: DomainEvent) -> None:
    goal_id = event.payload.get("goal_id")
    if not isinstance(goal_id, int) or goal_id <= 0:
        logger.warning("Skip goal breakdown event without valid goal_id trace_id=%s", event.trace_id)
        return

    plan_ids: list[int] = []
    with session_scope() as db:
        plans = plan_service.prepare_plans_for_goal(
            db,
            event.user_id,
            goal_id,
            reset_items=False,
        )
        if not plans:
            logger.warning("Failed to prepare action plans for goal_id=%s user_id=%s", goal_id, event.user_id)
            return
        plan_ids = [plan.id for plan in plans]

    plan_statuses: list[dict] = []
    for plan_id in plan_ids:
        try:
            with session_scope() as db:
                plan_service.generate_plan_with_retry(db, event.user_id, plan_id)
        except (RuntimeError, ValueError) as exc:
            with session_scope() as db:
                plan_service.mark_plan_failed(db, plan_id, str(exc))
            logger.warning(
                "Action plan generation failed plan_id=%s goal_id=%s user_id=%s error=%s",
                plan_id,
                goal_id,
                event.user_id,
                exc,
            )

        with session_scope() as db:
            refreshed = plan_service.get_plan_for_user(db, event.user_id, plan_id)
            plan_statuses.append(
                {
                    "plan_id": plan_id,
                    "plan_status": refreshed.status if refreshed else "failed",
                }
            )

    _publish_followup_event(
        DomainEventName.ON_ACTION_GENERATED,
        source_event=event,
        payload={
            "goal_id": goal_id,
            "plans": plan_statuses,
        },
    )


def _on_action_generated(event: DomainEvent) -> None:
    logger.info(
        "Action plan generated user_id=%s trace_id=%s payload=%s",
        event.user_id,
        event.trace_id,
        event.payload,
    )
    goal_id = event.payload.get("goal_id")
    with session_scope() as db:
        from app.services.ukl_execution_service import sync_execution_slices_for_user

        sync_execution_slices_for_user(
            db,
            event.user_id,
            goal_id=goal_id if isinstance(goal_id, int) else None,
        )


def _on_action_completed(event: DomainEvent) -> None:
    logger.info(
        "Action completed user_id=%s trace_id=%s payload=%s",
        event.user_id,
        event.trace_id,
        event.payload,
    )
    goal_id = event.payload.get("goal_id")
    with session_scope() as db:
        from app.services.ukl_execution_service import sync_execution_slices_for_user

        sync_execution_slices_for_user(
            db,
            event.user_id,
            goal_id=goal_id if isinstance(goal_id, int) else None,
        )


def _on_growth_updated(event: DomainEvent) -> None:
    logger.info(
        "Growth updated user_id=%s trace_id=%s payload=%s",
        event.user_id,
        event.trace_id,
        event.payload,
    )
    record_id = event.payload.get("record_id")
    if not isinstance(record_id, int):
        return
    try:
        from app.core.ai_worker import submit_ai_task
        from app.services import growth_service

        submit_ai_task(growth_service.process_record_summary_background, record_id)
    except Exception:
        logger.exception("Failed to schedule AI summary for record_id=%s", record_id)
    with session_scope() as db:
        from app.services.ukl_growth_service import ingest_growth_journal_for_record

        ingest_growth_journal_for_record(db, event.user_id, record_id)

        from app.services import ukl_pattern_service

        if ukl_pattern_service.should_refresh_growth_pattern(db, event.user_id):
            ukl_pattern_service.refresh_growth_pattern_for_user(db, event.user_id)


def _on_milestone_reached(event: DomainEvent) -> None:
    logger.info(
        "Milestone reached user_id=%s trace_id=%s payload=%s",
        event.user_id,
        event.trace_id,
        event.payload,
    )


def _on_growth_pattern_updated(event: DomainEvent) -> None:
    logger.info(
        "Growth pattern updated user_id=%s trace_id=%s payload=%s",
        event.user_id,
        event.trace_id,
        event.payload,
    )
    try:
        with session_scope() as db:
            profile_service.apply_growth_pattern_for_user(db, event.user_id)
    except Exception:
        logger.exception("Profile growth pattern reinforcement failed user_id=%s", event.user_id)


def initialize_growth_cycle_orchestrator() -> None:
    """向 event_bus 注册全部成长周期 handler（幂等，仅首次生效）。"""
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
    event_bus.subscribe(DomainEventName.ON_MILESTONE_REACHED.value, _on_milestone_reached)
    event_bus.subscribe(DomainEventName.ON_GROWTH_PATTERN_UPDATED.value, _on_growth_pattern_updated)

    _INITIALIZED = True
    logger.info("Growth cycle orchestrator initialized")
