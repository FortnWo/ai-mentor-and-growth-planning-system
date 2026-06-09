from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.ukl_constants import (
    REF_TYPE_GOAL,
    REF_TYPE_USER,
    SLICE_TYPE_EXECUTION_FEEDBACK,
    SLICE_TYPE_WORKLOAD_SNAPSHOT,
    SOURCE_MODULE_ACTION_PLAN,
)
from app.models.goal import Goal, GoalStatus
from app.schemas.ukl import ExecutionFeedbackPayload, WorkloadSnapshotPayload
from app.services import ukl_projection_service, ukl_service

logger = logging.getLogger(__name__)


def ingest_workload_snapshot_for_user(db: Session, user_id: int) -> None:
    payload = ukl_projection_service.compute_workload_snapshot(db, user_id)
    ukl_service.ingest(
        db,
        user_id,
        slice_type=SLICE_TYPE_WORKLOAD_SNAPSHOT,
        source_module=SOURCE_MODULE_ACTION_PLAN,
        ref_type=REF_TYPE_USER,
        ref_id=user_id,
        payload=payload,
    )


def ingest_execution_feedback_for_goal(db: Session, user_id: int, goal_id: int) -> None:
    payload = ukl_projection_service.compute_execution_feedback(db, user_id, goal_id)
    ukl_service.ingest(
        db,
        user_id,
        slice_type=SLICE_TYPE_EXECUTION_FEEDBACK,
        source_module=SOURCE_MODULE_ACTION_PLAN,
        ref_type=REF_TYPE_GOAL,
        ref_id=goal_id,
        payload=payload,
    )


def _list_active_goal_ids(db: Session, user_id: int) -> list[int]:
    goals = (
        db.query(Goal.id)
        .filter(Goal.user_id == user_id, Goal.status == GoalStatus.ACTIVE.value)
        .order_by(Goal.updated_at.desc(), Goal.id.desc())
        .all()
    )
    return [row[0] for row in goals]


def sync_execution_slices_for_user(db: Session, user_id: int, *, goal_id: int | None = None) -> None:
    if not settings.UKL_ENABLED or not settings.EXECUTION_SLICE_ENABLED:
        return
    try:
        ingest_workload_snapshot_for_user(db, user_id)
        if goal_id is not None:
            ingest_execution_feedback_for_goal(db, user_id, goal_id)
        else:
            for gid in _list_active_goal_ids(db, user_id):
                ingest_execution_feedback_for_goal(db, user_id, gid)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("UKL execution slice sync failed user_id=%s goal_id=%s", user_id, goal_id)


def maybe_sync_execution_slices(db: Session, user_id: int, *, goal_id: int | None = None) -> None:
    sync_execution_slices_for_user(db, user_id, goal_id=goal_id)
