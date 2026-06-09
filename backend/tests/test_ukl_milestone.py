import pytest

from app.core.config import settings
from app.core.ukl_constants import REF_TYPE_BREAKDOWN, SLICE_TYPE_MILESTONE_ACHIEVEMENT
from app.models.action_plan import ActionPlan, ActionPlanItem, ActionPlanStatus
from app.models.goal import Goal, GoalBreakdown, GoalBreakdownStatus
from app.models.growth_record import GrowthRecord, GrowthRecordType
from app.models.user import User
from app.services import action_plan_service, ukl_service


@pytest.fixture
def sample_user(db_session):
    user = User(
        username="ukl4_milestone",
        email="ukl4milestone@example.com",
        password_hash="hashed",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _mock_milestone_ai(monkeypatch):
    from app.services import ai_service

    monkeypatch.setattr(
        ai_service,
        "build_milestone_achievement_response",
        lambda msg: "完成了重要阶段节点，离目标更近一步。",
    )
    monkeypatch.setattr(
        ai_service,
        "build_instant_feedback_response",
        lambda msg: "太棒了！这一步完成得很扎实，继续保持。",
    )


@pytest.fixture
def goal_with_secondary_plan(db_session, sample_user):
    goal = Goal(user_id=sample_user.id, title="学习 Python", priority="medium")
    db_session.add(goal)
    db_session.flush()

    main = GoalBreakdown(
        goal_id=goal.id,
        parent_id=None,
        title="Main Pillar",
        level=0,
        sequence=0,
        status=GoalBreakdownStatus.PENDING.value,
    )
    db_session.add(main)
    db_session.flush()

    secondary = GoalBreakdown(
        goal_id=goal.id,
        parent_id=main.id,
        title="Branch A",
        level=1,
        sequence=0,
        status=GoalBreakdownStatus.PENDING.value,
    )
    db_session.add(secondary)
    db_session.flush()

    plan = ActionPlan(
        goal_id=goal.id,
        main_breakdown_id=main.id,
        title="Plan",
        status=ActionPlanStatus.PENDING.value,
    )
    db_session.add(plan)
    db_session.flush()

    for idx, title in enumerate(("Task A1", "Task A2")):
        db_session.add(
            ActionPlanItem(
                plan_id=plan.id,
                breakdown_id=secondary.id,
                title=title,
                status=ActionPlanStatus.PENDING.value,
                sequence=idx,
            )
        )
    db_session.commit()
    db_session.refresh(goal)
    db_session.refresh(plan)
    db_session.refresh(secondary)
    db_session.refresh(main)
    return goal, plan, secondary, main


def test_secondary_branch_completion_does_not_create_branch_milestone(
    db_session, sample_user, goal_with_secondary_plan, monkeypatch
):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "MILESTONE_UKL_ENABLED", True)
    monkeypatch.setattr(settings, "INSTANT_FEEDBACK_ENABLED", True)
    _mock_milestone_ai(monkeypatch)

    goal, plan, secondary, main = goal_with_secondary_plan
    items = (
        db_session.query(ActionPlanItem)
        .filter(ActionPlanItem.plan_id == plan.id)
        .order_by(ActionPlanItem.sequence.asc())
        .all()
    )

    action_plan_service.update_action_plan_item_completion(
        db_session, sample_user.id, plan.id, items[0].id, completed=True
    )
    assert (
        db_session.query(GrowthRecord)
        .filter(
            GrowthRecord.user_id == sample_user.id,
            GrowthRecord.record_type == GrowthRecordType.MILESTONE.value,
        )
        .count()
        == 0
    )

    action_plan_service.update_action_plan_item_completion(
        db_session, sample_user.id, plan.id, items[1].id, completed=True
    )

    db_session.refresh(secondary)
    db_session.refresh(main)
    assert secondary.status == GoalBreakdownStatus.COMPLETED.value
    assert main.status == GoalBreakdownStatus.COMPLETED.value

    assert (
        db_session.query(GrowthRecord)
        .filter(
            GrowthRecord.user_id == sample_user.id,
            GrowthRecord.record_type == GrowthRecordType.MILESTONE.value,
            GrowthRecord.source_ref_id == secondary.id,
        )
        .count()
        == 0
    )

    milestone = (
        db_session.query(GrowthRecord)
        .filter(
            GrowthRecord.user_id == sample_user.id,
            GrowthRecord.record_type == GrowthRecordType.MILESTONE.value,
            GrowthRecord.source_ref_id == main.id,
        )
        .one()
    )
    assert milestone.summary
    assert "太棒了" in milestone.summary or "扎实" in milestone.summary

    slice_row = ukl_service.get_latest_slice(
        db_session,
        sample_user.id,
        SLICE_TYPE_MILESTONE_ACHIEVEMENT,
        ref_type=REF_TYPE_BREAKDOWN,
        ref_id=main.id,
    )
    assert slice_row is not None
    assert "Main Pillar" in slice_row.payload or "主支柱" in slice_row.payload


def test_main_node_completion_milestone_level(
    db_session, sample_user, monkeypatch
):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "MILESTONE_UKL_ENABLED", True)
    monkeypatch.setattr(settings, "INSTANT_FEEDBACK_ENABLED", False)
    _mock_milestone_ai(monkeypatch)

    goal = Goal(user_id=sample_user.id, title="Main Goal", priority="medium")
    db_session.add(goal)
    db_session.flush()

    main = GoalBreakdown(
        goal_id=goal.id,
        parent_id=None,
        title="Main Only",
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
        title="Only Task",
        status=ActionPlanStatus.PENDING.value,
        sequence=0,
    )
    db_session.add(item)
    db_session.commit()

    action_plan_service.update_action_plan_item_completion(
        db_session, sample_user.id, plan.id, item.id, completed=True
    )

    slice_row = ukl_service.get_latest_slice(
        db_session,
        sample_user.id,
        SLICE_TYPE_MILESTONE_ACHIEVEMENT,
        ref_type=REF_TYPE_BREAKDOWN,
        ref_id=main.id,
    )
    assert slice_row is not None
    assert '"milestone_level": "main"' in slice_row.payload or '"milestone_level":"main"' in slice_row.payload


def test_milestone_idempotent_on_repeat_sync(db_session, sample_user, goal_with_secondary_plan, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", False)
    monkeypatch.setattr(settings, "MILESTONE_UKL_ENABLED", False)

    goal, plan, secondary, main = goal_with_secondary_plan
    items = (
        db_session.query(ActionPlanItem)
        .filter(ActionPlanItem.plan_id == plan.id)
        .order_by(ActionPlanItem.sequence.asc())
        .all()
    )
    for item in items:
        action_plan_service.update_action_plan_item_completion(
            db_session, sample_user.id, plan.id, item.id, completed=True
        )

    count_first = (
        db_session.query(GrowthRecord)
        .filter(
            GrowthRecord.user_id == sample_user.id,
            GrowthRecord.record_type == GrowthRecordType.MILESTONE.value,
        )
        .count()
    )
    assert count_first == 1

    assert (
        db_session.query(GrowthRecord)
        .filter(
            GrowthRecord.user_id == sample_user.id,
            GrowthRecord.record_type == GrowthRecordType.MILESTONE.value,
            GrowthRecord.source_ref_id == secondary.id,
        )
        .count()
        == 0
    )
    assert (
        db_session.query(GrowthRecord)
        .filter(
            GrowthRecord.user_id == sample_user.id,
            GrowthRecord.record_type == GrowthRecordType.MILESTONE.value,
            GrowthRecord.source_ref_id == main.id,
        )
        .count()
        == 1
    )

    plan_row = action_plan_service.get_action_plan_for_user(db_session, sample_user.id, plan.id)
    assert plan_row is not None
    action_plan_service._sync_aggregate_plan_and_main_status(db_session, plan_row)
    db_session.commit()

    count_second = (
        db_session.query(GrowthRecord)
        .filter(
            GrowthRecord.user_id == sample_user.id,
            GrowthRecord.record_type == GrowthRecordType.MILESTONE.value,
        )
        .count()
    )
    assert count_second == count_first
