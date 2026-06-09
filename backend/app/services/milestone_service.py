from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, TypedDict

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.domain_events import DomainEventName
from app.core.event_bus import event_bus
from app.core.ukl_constants import (
    REF_TYPE_BREAKDOWN,
    SLICE_TYPE_MILESTONE_ACHIEVEMENT,
    SOURCE_MODULE_MILESTONE,
)
from app.models.goal import GoalBreakdown, GoalBreakdownStatus
from app.models.growth_record import GrowthRecord, GrowthRecordSource, GrowthRecordType
from app.schemas.ukl import MilestoneAchievementPayload
from app.services import ukl_instant_feedback_service, ukl_service
from app.services.growth_record_service import create_growth_record

logger = logging.getLogger(__name__)


class MilestoneFinalizeInfo(TypedDict):
    record_id: int
    goal_id: int
    breakdown_id: int
    milestone_level: str
    title: str
    plan_id: int


def _milestone_idempotency_key(breakdown_id: int) -> str:
    return f"milestone-breakdown-{breakdown_id}"


def _fallback_milestone_narrative(title: str, milestone_level: str) -> str:
    level_label = "主支柱" if milestone_level == "main" else "分支节点"
    return f"完成了{level_label}「{title}」，这是目标推进中的重要一步。"


def _ingest_milestone_achievement(
    db: Session,
    user_id: int,
    *,
    goal_id: int,
    breakdown_id: int,
    milestone_level: str,
    title: str,
) -> str:
    narrative = _fallback_milestone_narrative(title, milestone_level)
    if settings.UKL_ENABLED and settings.MILESTONE_UKL_ENABLED:
        try:
            from app.services import ai_service

            prompt = (
                f"目标节点：{title}\n"
                f"层级：{milestone_level}\n"
                f"goal_id={goal_id} breakdown_id={breakdown_id}"
            )
            generated = ai_service.build_milestone_achievement_response(prompt).strip()
            if generated:
                narrative = generated
        except Exception:
            logger.exception("Milestone achievement narrative failed breakdown_id=%s", breakdown_id)

    ukl_service.ingest(
        db,
        user_id,
        slice_type=SLICE_TYPE_MILESTONE_ACHIEVEMENT,
        source_module=SOURCE_MODULE_MILESTONE,
        ref_type=REF_TYPE_BREAKDOWN,
        ref_id=breakdown_id,
        payload=MilestoneAchievementPayload(
            goal_id=goal_id,
            breakdown_id=breakdown_id,
            milestone_level=milestone_level,
            title=title,
            narrative=narrative,
        ),
    )
    return narrative


def handle_breakdown_status_transition(
    db: Session,
    user_id: int,
    node: GoalBreakdown,
    old_status: str | None,
    new_status: str,
    *,
    plan_id: int,
    main_breakdown_id: int,
) -> MilestoneFinalizeInfo | None:
    """Create milestone entity in the current transaction; UKL/events run after commit."""
    if new_status != GoalBreakdownStatus.COMPLETED.value:
        return None
    if old_status == GoalBreakdownStatus.COMPLETED.value:
        return None

    milestone_level = "main" if node.id == main_breakdown_id else "child"
    title = (node.title or "里程碑").strip()
    idem = _milestone_idempotency_key(node.id)

    if (
        db.query(GrowthRecord)
        .filter(GrowthRecord.user_id == user_id, GrowthRecord.idempotency_key == idem)
        .first()
    ):
        return None

    summary = _fallback_milestone_narrative(title, milestone_level)
    record = create_growth_record(
        db,
        user_id,
        title=f"里程碑：{title}"[:255],
        summary=summary,
        content=f"来自行动计划 {plan_id} 的节点完成",
        record_type=GrowthRecordType.MILESTONE.value,
        source_type=GrowthRecordSource.MILESTONE.value,
        source_ref_id=node.id,
        occurred_at=datetime.utcnow(),
        idempotency_key=idem,
        commit=False,
        refresh=False,
    )

    logger.info(
        "Milestone recorded user_id=%s breakdown_id=%s level=%s record_id=%s",
        user_id,
        node.id,
        milestone_level,
        record.id,
    )

    if not (settings.UKL_ENABLED and settings.MILESTONE_UKL_ENABLED):
        return None

    return MilestoneFinalizeInfo(
        record_id=record.id,
        goal_id=node.goal_id,
        breakdown_id=node.id,
        milestone_level=milestone_level,
        title=title,
        plan_id=plan_id,
    )


def finalize_milestone_after_commit(user_id: int, info: MilestoneFinalizeInfo) -> None:
    """Run UKL ingest, instant feedback, and domain events on a committed milestone."""
    import app.core.database as database_module

    db = database_module.SessionLocal()
    try:
        record = (
            db.query(GrowthRecord)
            .filter(GrowthRecord.id == info["record_id"], GrowthRecord.user_id == user_id)
            .first()
        )
        if not record:
            return

        narrative = _ingest_milestone_achievement(
            db,
            user_id,
            goal_id=info["goal_id"],
            breakdown_id=info["breakdown_id"],
            milestone_level=info["milestone_level"],
            title=info["title"],
        )
        if settings.INSTANT_FEEDBACK_ENABLED:
            record.summary = ukl_instant_feedback_service.build_instant_feedback_summary(
                db,
                user_id,
                goal_id=info["goal_id"],
                breakdown_id=info["breakdown_id"],
                title=info["title"],
            )
        else:
            record.summary = narrative
        db.add(record)
        db.commit()

        event_bus.publish(
            event_name=DomainEventName.ON_MILESTONE_REACHED.value,
            user_id=user_id,
            payload={
                "goal_id": info["goal_id"],
                "breakdown_id": info["breakdown_id"],
                "milestone_level": info["milestone_level"],
                "plan_id": info["plan_id"],
                "record_id": info["record_id"],
            },
            fail_fast=False,
        )
        event_bus.publish(
            event_name=DomainEventName.ON_GROWTH_UPDATED.value,
            user_id=user_id,
            payload={
                "record_id": info["record_id"],
                "record_type": record.record_type,
                "source_type": record.source_type,
                "source": "milestone_reached",
            },
            fail_fast=False,
        )
    except Exception:
        db.rollback()
        logger.exception(
            "Milestone UKL finalize failed user_id=%s record_id=%s",
            user_id,
            info.get("record_id"),
        )
    finally:
        db.close()


def finalize_milestones_after_commit(user_id: int, pending: list[MilestoneFinalizeInfo]) -> None:
    for info in pending:
        finalize_milestone_after_commit(user_id, info)
