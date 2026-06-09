import json

import pytest

from app.core.config import settings
from app.core.ukl_constants import (
    REF_TYPE_GOAL,
    REF_TYPE_USER,
    SCENE_ACTION_PLAN,
    SLICE_TYPE_EXECUTION_FEEDBACK,
    SLICE_TYPE_WORKLOAD_SNAPSHOT,
)
from app.models.action_plan import ActionPlan, ActionPlanItem, ActionPlanStatus
from app.models.goal import Goal, GoalBreakdown, GoalBreakdownStatus
from app.models.user import User
from app.schemas.ukl import WorkloadSnapshotPayload
from app.services import action_plan_service, ukl_execution_service, ukl_service


@pytest.fixture
def sample_user(db_session):
    user = User(
        username="ukl3_user",
        email="ukl3@example.com",
        password_hash="hashed",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def goal_with_plan(db_session, sample_user):
    goal = Goal(user_id=sample_user.id, title="Test Goal", priority="medium")
    db_session.add(goal)
    db_session.flush()

    main = GoalBreakdown(
        goal_id=goal.id,
        parent_id=None,
        title="Main",
        level=0,
        sequence=0,
        status=GoalBreakdownStatus.PENDING.value,
    )
    db_session.add(main)
    db_session.flush()

    plan = ActionPlan(
        goal_id=goal.id,
        main_breakdown_id=main.id,
        title="Plan",
        status=ActionPlanStatus.PENDING.value,
    )
    db_session.add(plan)
    db_session.flush()

    item = ActionPlanItem(
        plan_id=plan.id,
        breakdown_id=main.id,
        title="Task",
        status=ActionPlanStatus.PENDING.value,
        sequence=0,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(goal)
    db_session.refresh(plan)
    db_session.refresh(item)
    return goal, plan, item, main


def test_sync_execution_slices_writes_workload_and_execution(
    db_session, sample_user, goal_with_plan, monkeypatch
):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "EXECUTION_SLICE_ENABLED", True)

    goal, _, _, _ = goal_with_plan
    ukl_execution_service.sync_execution_slices_for_user(db_session, sample_user.id, goal_id=goal.id)

    workload = ukl_service.get_latest_slice(
        db_session,
        sample_user.id,
        SLICE_TYPE_WORKLOAD_SNAPSHOT,
        ref_type=REF_TYPE_USER,
        ref_id=sample_user.id,
    )
    execution = ukl_service.get_latest_slice(
        db_session,
        sample_user.id,
        SLICE_TYPE_EXECUTION_FEEDBACK,
        ref_type=REF_TYPE_GOAL,
        ref_id=goal.id,
    )
    assert workload is not None
    assert execution is not None


def test_item_completion_syncs_execution_slices(
    db_session, sample_user, goal_with_plan, monkeypatch
):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "EXECUTION_SLICE_ENABLED", True)

    goal, plan, item, _ = goal_with_plan
    action_plan_service.update_action_plan_item_completion(
        db_session,
        sample_user.id,
        plan.id,
        item.id,
        completed=True,
    )

    execution = ukl_service.get_latest_slice(
        db_session,
        sample_user.id,
        SLICE_TYPE_EXECUTION_FEEDBACK,
        ref_type=REF_TYPE_GOAL,
        ref_id=goal.id,
    )
    assert execution is not None
    payload = json.loads(execution.payload)
    assert payload["completed_items"] == 1


def test_assemble_prefers_workload_slice_over_compute(db_session, sample_user, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)

    custom = WorkloadSnapshotPayload(
        active_goal_count=99,
        total_goal_count=99,
        active_plan_count=0,
        pending_item_count=0,
        in_progress_item_count=0,
    )
    ukl_service.ingest(
        db_session,
        sample_user.id,
        slice_type=SLICE_TYPE_WORKLOAD_SNAPSHOT,
        source_module="test",
        ref_type=REF_TYPE_USER,
        ref_id=sample_user.id,
        payload=custom,
    )
    db_session.commit()

    goal = Goal(user_id=sample_user.id, title="G", priority="medium")
    db_session.add(goal)
    db_session.commit()

    bundle = ukl_service.assemble_context(
        db_session,
        sample_user.id,
        SCENE_ACTION_PLAN,
        goal_id=goal.id,
        main_breakdown_id=1,
    )
    assert bundle.anchors["workload"]["active_goal_count"] == 99


def test_assemble_workload_fallback_without_slice(db_session, sample_user, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)

    goal = Goal(user_id=sample_user.id, title="G", priority="medium")
    db_session.add(goal)
    db_session.commit()

    bundle = ukl_service.assemble_context(
        db_session,
        sample_user.id,
        SCENE_ACTION_PLAN,
        goal_id=goal.id,
        main_breakdown_id=1,
    )
    assert "workload" in bundle.anchors
    assert bundle.anchors["workload"]["total_goal_count"] >= 1
