import json
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.core.ukl_constants import (
    REF_TYPE_GOAL,
    SCENE_ACTION_PLAN,
    SCENE_BREAKDOWN,
    SLICE_TYPE_BREAKDOWN_ANCHORS,
    SLICE_TYPE_BREAKDOWN_SUMMARY,
)
from app.models.action_plan import ActionPlan, ActionPlanItem, ActionPlanStatus
from app.models.goal import Goal, GoalBreakdown, GoalBreakdownStatus
from app.models.ukl_slice import UklSlice
from app.models.user import User
from app.schemas.ukl import BreakdownAnchorsPayload, BreakdownSummaryPayload
from app.services import (
    action_plan_service,
    breakdown_service,
    ukl_prompt_service,
    ukl_service,
)


@pytest.fixture
def sample_user(db_session):
    user = User(
        username="ukl2_user",
        email="ukl2@example.com",
        password_hash="hashed",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_goal(db_session, sample_user):
    goal = Goal(
        user_id=sample_user.id,
        title="Learn Python",
        description="每天学习 2 小时，每周完成一个小项目",
        priority="high",
    )
    db_session.add(goal)
    db_session.commit()
    db_session.refresh(goal)
    return goal


@pytest.fixture
def sample_breakdown_tree(db_session, sample_goal):
    main = GoalBreakdown(
        goal_id=sample_goal.id,
        parent_id=None,
        title="Foundation",
        description="Core skills",
        level=0,
        sequence=0,
        status=GoalBreakdownStatus.PENDING.value,
    )
    db_session.add(main)
    db_session.flush()

    sec_a = GoalBreakdown(
        goal_id=sample_goal.id,
        parent_id=main.id,
        title="Syntax",
        description="Basics",
        level=1,
        sequence=0,
        status=GoalBreakdownStatus.PENDING.value,
    )
    sec_b = GoalBreakdown(
        goal_id=sample_goal.id,
        parent_id=main.id,
        title="Projects",
        description="Practice",
        level=1,
        sequence=1,
        status=GoalBreakdownStatus.PENDING.value,
    )
    db_session.add_all([sec_a, sec_b])
    db_session.commit()
    db_session.refresh(main)
    db_session.refresh(sec_a)
    db_session.refresh(sec_b)
    return main, [sec_a, sec_b]


def _ingest_breakdown_fixtures(db_session, user_id: int, goal_id: int) -> None:
    ukl_service.ingest(
        db_session,
        user_id,
        slice_type=SLICE_TYPE_BREAKDOWN_SUMMARY,
        source_module="test",
        ref_type=REF_TYPE_GOAL,
        ref_id=goal_id,
        payload=BreakdownSummaryPayload(goal_id=goal_id, summary="拆解围绕基础与项目实践两条线推进。"),
    )
    ukl_service.ingest(
        db_session,
        user_id,
        slice_type=SLICE_TYPE_BREAKDOWN_ANCHORS,
        source_module="test",
        ref_type=REF_TYPE_GOAL,
        ref_id=goal_id,
        payload=BreakdownAnchorsPayload(
            goal_id=goal_id,
            critical_constraints=["每天学习 2 小时"],
            dependency_notes=["先 Syntax 后 Projects"],
        ),
    )
    db_session.commit()


def test_assemble_context_breakdown_includes_profile_and_workload(
    db_session, sample_user, sample_goal, monkeypatch
):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)

    bundle = ukl_service.assemble_context(
        db_session,
        sample_user.id,
        SCENE_BREAKDOWN,
        goal_id=sample_goal.id,
    )
    assert bundle.scene == SCENE_BREAKDOWN
    assert "profile_fields" in bundle.anchors
    assert "workload" in bundle.anchors
    assert bundle.anchors["entity_hints"]["goal_id"] == sample_goal.id
    assert "execution_feedback" not in bundle.anchors


def test_assemble_context_breakdown_refresh_includes_execution(
    db_session, sample_user, sample_goal, sample_breakdown_tree, monkeypatch
):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    main, _ = sample_breakdown_tree

    plan = ActionPlan(
        goal_id=sample_goal.id,
        main_breakdown_id=main.id,
        title="Plan",
        status=ActionPlanStatus.PENDING.value,
    )
    db_session.add(plan)
    db_session.flush()

    item = ActionPlanItem(
        plan_id=plan.id,
        breakdown_id=main.id,
        title="Task 1",
        status=ActionPlanStatus.COMPLETED.value,
        sequence=0,
    )
    db_session.add(item)
    db_session.commit()

    bundle = ukl_service.assemble_context(
        db_session,
        sample_user.id,
        SCENE_BREAKDOWN,
        goal_id=sample_goal.id,
        is_refresh=True,
    )
    execution = bundle.anchors.get("execution_feedback")
    assert execution is not None
    assert execution["total_items"] == 1
    assert execution["completed_items"] == 1


def test_assemble_context_action_plan_includes_breakdown_slices(
    db_session, sample_user, sample_goal, sample_breakdown_tree, monkeypatch
):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    main, _ = sample_breakdown_tree
    _ingest_breakdown_fixtures(db_session, sample_user.id, sample_goal.id)

    bundle = ukl_service.assemble_context(
        db_session,
        sample_user.id,
        SCENE_ACTION_PLAN,
        goal_id=sample_goal.id,
        main_breakdown_id=main.id,
    )
    assert bundle.scene == SCENE_ACTION_PLAN
    assert "breakdown_summary" in bundle.anchors
    assert "breakdown_anchors" in bundle.anchors
    assert any("拆解围绕" in block for block in bundle.narrative_blocks)


def test_build_goal_breakdown_prompt_ukl_on_contains_section(
    db_session, sample_user, sample_goal, monkeypatch
):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    prompt = ukl_prompt_service.build_goal_breakdown_prompt(db_session, sample_user.id, sample_goal)
    assert "[UKL 上下文]" in prompt
    assert "[Goal 实体]" in prompt
    assert sample_goal.title in prompt


def test_build_goal_breakdown_prompt_ukl_off_matches_legacy(
    db_session, sample_user, sample_goal, monkeypatch
):
    monkeypatch.setattr(settings, "UKL_ENABLED", False)
    legacy = ukl_prompt_service.build_legacy_goal_breakdown_prompt(db_session, sample_user.id, sample_goal)
    prompt = ukl_prompt_service.build_goal_breakdown_prompt(db_session, sample_user.id, sample_goal)
    assert prompt == legacy
    assert "[UKL 上下文]" not in prompt


def test_ingest_breakdown_slices_for_goal_writes_two_rows(
    db_session, sample_user, sample_goal, sample_breakdown_tree, monkeypatch
):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "BREAKDOWN_SUMMARY_ENABLED", True)

    from app.services import ai_service

    monkeypatch.setattr(
        ai_service,
        "build_breakdown_summary_response",
        lambda msg: "该目标拆解为基础语法与项目实践两阶段推进。",
    )

    breakdown_service.ingest_breakdown_slices_for_goal(db_session, sample_user.id, sample_goal.id)

    summary = ukl_service.get_latest_slice(
        db_session,
        sample_user.id,
        SLICE_TYPE_BREAKDOWN_SUMMARY,
        ref_type=REF_TYPE_GOAL,
        ref_id=sample_goal.id,
    )
    anchors = ukl_service.get_latest_slice(
        db_session,
        sample_user.id,
        SLICE_TYPE_BREAKDOWN_ANCHORS,
        ref_type=REF_TYPE_GOAL,
        ref_id=sample_goal.id,
    )
    assert summary is not None
    assert anchors is not None
    summary_payload = json.loads(summary.payload)
    assert "拆解" in summary_payload["summary"]
    anchors_payload = json.loads(anchors.payload)
    assert anchors_payload["goal_id"] == sample_goal.id


def test_apply_breakdown_triggers_ukl_ingest_when_enabled(
    db_session, sample_user, sample_goal, monkeypatch
):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "BREAKDOWN_SUMMARY_ENABLED", True)

    from app.services import ai_service

    monkeypatch.setattr(
        ai_service,
        "build_breakdown_summary_response",
        lambda msg: "自动写入的拆解摘要。",
    )

    breakdown_data = {
        "breakdowns": [
            {
                "title": "Phase A",
                "description": "Start",
                "children": [{"title": "Step 1", "description": "x", "children": []}],
            }
        ]
    }
    assert breakdown_service.apply_breakdown_for_goal(
        db_session, sample_user.id, sample_goal.id, breakdown_data
    )

    count = (
        db_session.query(UklSlice)
        .filter(
            UklSlice.user_id == sample_user.id,
            UklSlice.ref_type == REF_TYPE_GOAL,
            UklSlice.ref_id == sample_goal.id,
        )
        .count()
    )
    assert count == 2


def test_validate_secondary_coverage_pass_and_fail():
    secondary = [SimpleNamespace(id=11), SimpleNamespace(id=12)]
    lookup = {"11": 11, "12": 12, "10": 10}

    ok_items = [{"breakdown_ref": 11}, {"breakdown_ref": 12}]
    assert action_plan_service._validate_secondary_coverage(secondary, 10, ok_items, lookup) == []

    bad_items = [{"breakdown_ref": 11}]
    assert action_plan_service._validate_secondary_coverage(secondary, 10, bad_items, lookup) == ["12"]

    main_only_lookup = {"10": 10}
    assert action_plan_service._validate_secondary_coverage([], 10, [{"breakdown_ref": 10}], main_only_lookup) == []
    assert action_plan_service._validate_secondary_coverage([], 10, [], main_only_lookup) == ["10"]


def test_build_action_plan_prompt_ukl_on_contains_breakdown_section(
    db_session, sample_user, sample_goal, sample_breakdown_tree, monkeypatch
):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    main, secondary = sample_breakdown_tree
    _ingest_breakdown_fixtures(db_session, sample_user.id, sample_goal.id)

    prompt = ukl_prompt_service.build_action_plan_prompt_for_main(
        db_session,
        sample_goal,
        main,
        secondary,
        "2026-06-08",
    )
    assert "[UKL 上下文]" in prompt
    assert "[Breakdown 实体]" in prompt
    assert "拆解叙事" in prompt or "拆解围绕" in prompt
