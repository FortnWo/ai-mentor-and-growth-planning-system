from datetime import date

import pytest

from app.core.config import settings
from app.core.ukl_constants import (
    REF_TYPE_GOAL,
    REF_TYPE_USER,
    SCENE_CHAT,
    SCENE_FEEDBACK,
    SLICE_TYPE_EPISODIC_NARRATIVE,
    SLICE_TYPE_GOAL_INTENT,
    SLICE_TYPE_GROWTH_PATTERN,
    SLICE_TYPE_PROFILE,
    SLICE_TYPE_WEEKLY_NARRATIVE,
)
from app.models.chat_session_summary import ChatSessionSummary
from app.models.goal import Goal
from app.models.growth_record import GrowthRecordType
from app.models.user import User
from app.services import (
    growth_record_service,
    growth_summary_service,
    profile_service,
    ukl_narrative_service,
    ukl_pattern_service,
    ukl_service,
)


@pytest.fixture
def sample_user(db_session):
    user = User(
        username="ukl4_pattern",
        email="ukl4pattern@example.com",
        password_hash="hashed",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_refresh_growth_pattern_for_user(db_session, sample_user, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "GROWTH_PATTERN_ENABLED", True)
    monkeypatch.setattr(settings, "GROWTH_PATTERN_CHECKIN_THRESHOLD", 2)

    from app.services import ai_service

    monkeypatch.setattr(
        ai_service,
        "build_growth_pattern_response",
        lambda msg: "本周坚持打卡，情绪积极，主题包括学习与自律。",
    )

    for idx in range(3):
        growth_record_service.create_growth_record(
            db_session,
            sample_user.id,
            title=f"打卡 {idx}",
            summary="完成了今日任务",
            record_type=GrowthRecordType.MANUAL.value,
            record_date="2026-06-01",
            commit=True,
        )

    payload = ukl_pattern_service.refresh_growth_pattern_for_user(
        db_session,
        sample_user.id,
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 7),
        force=True,
    )
    assert payload is not None

    row = ukl_service.get_latest_slice(
        db_session,
        sample_user.id,
        SLICE_TYPE_GROWTH_PATTERN,
        ref_type=REF_TYPE_USER,
        ref_id=sample_user.id,
    )
    assert row is not None
    assert "坚持" in row.payload or "打卡" in row.payload


def test_weekly_summary_writes_weekly_narrative_and_pattern(
    db_session, sample_user, monkeypatch
):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "GROWTH_PATTERN_ENABLED", True)

    from app.services import ai_service

    monkeypatch.setattr(
        ai_service,
        "build_weekly_summary_response",
        lambda msg: "本周进步明显，下周继续保持小步前进。",
    )
    monkeypatch.setattr(
        ai_service,
        "build_growth_pattern_response",
        lambda msg: "本周整体节奏稳定，情绪积极。",
    )

    start = date(2026, 6, 1)
    end = date(2026, 6, 7)
    growth_summary_service.create_weekly_summary(db_session, sample_user.id, start, end)

    weekly = ukl_service.get_latest_slice(
        db_session,
        sample_user.id,
        SLICE_TYPE_WEEKLY_NARRATIVE,
        ref_type=REF_TYPE_USER,
        ref_id=sample_user.id,
    )
    assert weekly is not None
    assert "进步" in weekly.payload

    bundle = ukl_service.assemble_context(
        db_session,
        sample_user.id,
        SCENE_FEEDBACK,
        start_date=start,
        end_date=end,
    )
    assert bundle.anchors.get("weekly_narrative")
    assert bundle.anchors.get("growth_pattern")


def test_goal_intent_and_episodic_narrative(db_session, sample_user, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "GOAL_INTENT_ENABLED", True)
    monkeypatch.setattr(settings, "EPISODIC_NARRATIVE_ENABLED", True)

    from app.services import ai_service

    monkeypatch.setattr(
        ai_service,
        "build_goal_intent_response",
        lambda msg: "用户希望系统掌握 Python 编程以提升职业竞争力。",
    )
    monkeypatch.setattr(
        ai_service,
        "build_episodic_narrative_response",
        lambda msg: "用户近期持续讨论学习目标，并在编程练习上保持进展。",
    )
    monkeypatch.setattr(
        ai_service,
        "build_growth_pattern_response",
        lambda msg: "近期学习节奏稳定。",
    )

    goal = Goal(user_id=sample_user.id, title="学 Python", description="职业提升", priority="medium")
    db_session.add(goal)
    db_session.commit()
    db_session.refresh(goal)

    ukl_narrative_service.ingest_goal_intent_for_goal(db_session, sample_user.id, goal.id)
    intent_row = ukl_service.get_latest_slice(
        db_session,
        sample_user.id,
        SLICE_TYPE_GOAL_INTENT,
        ref_type=REF_TYPE_GOAL,
        ref_id=goal.id,
    )
    assert intent_row is not None
    assert "Python" in intent_row.payload

    db_session.add(
        ChatSessionSummary(
            session_id=1,
            user_id=sample_user.id,
            summary="讨论了 Python 学习路径与每日练习安排。",
            summarized_through_message_id=10,
            message_count=12,
        )
    )
    db_session.commit()

    ukl_narrative_service.ingest_episodic_narrative_for_user(db_session, sample_user.id)
    episodic_row = ukl_service.get_latest_slice(
        db_session,
        sample_user.id,
        SLICE_TYPE_EPISODIC_NARRATIVE,
        ref_type=REF_TYPE_USER,
        ref_id=sample_user.id,
    )
    assert episodic_row is not None

    ukl_pattern_service.refresh_growth_pattern_for_user(
        db_session,
        sample_user.id,
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 7),
        force=True,
    )

    bundle = ukl_service.assemble_context(db_session, sample_user.id, SCENE_CHAT)
    assert bundle.anchors.get("episodic_narrative")
    assert bundle.anchors.get("growth_pattern")


def test_profile_reinforcement_on_growth_pattern(db_session, sample_user, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "GROWTH_PATTERN_ENABLED", True)
    monkeypatch.setattr(settings, "GROWTH_PATTERN_CHECKIN_THRESHOLD", 2)

    from app.services import ai_service

    monkeypatch.setattr(
        ai_service,
        "build_growth_pattern_response",
        lambda msg: "本周坚持打卡，情绪积极。",
    )
    monkeypatch.setattr(ai_service, "build_portrait_summary_response", lambda msg: "画像已更新")

    profile_service.get_or_create_profile_for_user(db_session, sample_user.id)
    ukl_service.ingest_profile_from_user(db_session, sample_user.id)
    db_session.commit()

    before = ukl_service.get_latest_slice(
        db_session,
        sample_user.id,
        SLICE_TYPE_PROFILE,
        ref_type=REF_TYPE_USER,
        ref_id=sample_user.id,
    )
    before_version = int(before.version or 1) if before else 0

    ukl_pattern_service.refresh_growth_pattern_for_user(
        db_session,
        sample_user.id,
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 7),
        force=True,
    )

    profile_service.apply_growth_pattern_for_user(db_session, sample_user.id)

    after = ukl_service.get_latest_slice(
        db_session,
        sample_user.id,
        SLICE_TYPE_PROFILE,
        ref_type=REF_TYPE_USER,
        ref_id=sample_user.id,
    )
    assert after is not None
    assert int(after.version or 1) > before_version
