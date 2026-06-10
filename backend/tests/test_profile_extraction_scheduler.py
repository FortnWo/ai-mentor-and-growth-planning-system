from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.models.user import User
from app.services import profile_extraction_service, profile_service


@pytest.fixture(autouse=True)
def reset_in_flight_users():
    with profile_extraction_service._in_flight_lock:
        profile_extraction_service._in_flight_user_ids.clear()
    yield
    with profile_extraction_service._in_flight_lock:
        profile_extraction_service._in_flight_user_ids.clear()


@pytest.fixture
def sample_user(db_session):
    user = User(
        username="profile_sched",
        email="profilesched@example.com",
        password_hash="hashed",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _add_user_message(db_session, session_id: int, content: str) -> ChatMessage:
    message = ChatMessage(session_id=session_id, role=MessageRole.USER, content=content)
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)
    return message


def _add_assistant_message(db_session, session_id: int, content: str = "好的，了解了。") -> ChatMessage:
    message = ChatMessage(session_id=session_id, role=MessageRole.ASSISTANT, content=content)
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)
    return message


@pytest.fixture
def chat_session(db_session, sample_user):
    session = ChatSession(user_id=sample_user.id, title="Test")
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


def test_should_trigger_profile_extraction_keywords_and_small_talk():
    assert profile_extraction_service.should_trigger_profile_extraction("我的目标是考研")
    assert not profile_extraction_service.should_trigger_profile_extraction("你好")
    assert not profile_extraction_service.should_trigger_profile_extraction("")


def test_bootstrap_with_profile_signal_schedules(db_session, sample_user, chat_session, monkeypatch):
    monkeypatch.setattr(settings, "PROFILE_EXTRACTION_ON_DEMAND_ENABLED", True)
    user_message = _add_user_message(db_session, chat_session.id, "我想学习数据分析，目标是三个月入门。")
    assistant_message = _add_assistant_message(db_session, chat_session.id)

    decision = profile_extraction_service.should_schedule_profile_extraction(
        db_session,
        sample_user.id,
        user_message=user_message.content,
    )
    assert decision.should_schedule is True
    assert decision.reason is None

    scheduled = profile_extraction_service.schedule_profile_extraction_from_chat(
        user_id=sample_user.id,
        session_id=chat_session.id,
        assistant_message_id=assistant_message.id,
        trace_id="trace-bootstrap",
    )
    assert scheduled.should_schedule is True


def test_bootstrap_small_talk_still_schedules(db_session, sample_user, chat_session, monkeypatch):
    monkeypatch.setattr(settings, "PROFILE_EXTRACTION_ON_DEMAND_ENABLED", True)
    user_message = _add_user_message(db_session, chat_session.id, "你好")
    _add_assistant_message(db_session, chat_session.id)

    decision = profile_extraction_service.should_schedule_profile_extraction(
        db_session,
        sample_user.id,
        user_message=user_message.content,
    )
    assert decision.should_schedule is True
    assert decision.reason is None


def test_non_bootstrap_small_talk_blocked_by_on_demand(
    db_session,
    sample_user,
    chat_session,
    monkeypatch,
):
    monkeypatch.setattr(settings, "PROFILE_EXTRACTION_ON_DEMAND_ENABLED", True)
    monkeypatch.setattr(settings, "PROFILE_EXTRACTION_MIN_INTERVAL_MINUTES", 0)

    profile = profile_service.get_or_create_profile_for_user(db_session, sample_user.id)
    profile.last_extracted_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
    db_session.add(profile)
    db_session.commit()

    _add_user_message(db_session, chat_session.id, "你好")

    decision = profile_extraction_service.should_schedule_profile_extraction(
        db_session,
        sample_user.id,
        user_message="你好",
    )
    assert decision.should_schedule is False
    assert decision.reason == "on_demand"


def test_throttle_blocks_until_interval_and_one_turn(
    db_session,
    sample_user,
    chat_session,
    monkeypatch,
):
    monkeypatch.setattr(settings, "PROFILE_EXTRACTION_MIN_INTERVAL_MINUTES", 5)
    monkeypatch.setattr(settings, "PROFILE_EXTRACTION_BURST_USER_TURNS", 3)
    monkeypatch.setattr(settings, "PROFILE_EXTRACTION_ON_DEMAND_ENABLED", False)

    profile = profile_service.get_or_create_profile_for_user(db_session, sample_user.id)
    profile.last_extracted_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    db_session.add(profile)
    db_session.commit()

    _add_user_message(db_session, chat_session.id, "这是一条足够长的新用户消息用于测试降频逻辑。")

    decision = profile_extraction_service.should_schedule_profile_extraction(
        db_session,
        sample_user.id,
        user_message="这是一条足够长的新用户消息用于测试降频逻辑。",
    )
    assert decision.should_schedule is False
    assert decision.reason == "throttled"


def test_throttle_passes_after_interval_and_one_turn(
    db_session,
    sample_user,
    chat_session,
    monkeypatch,
):
    monkeypatch.setattr(settings, "PROFILE_EXTRACTION_MIN_INTERVAL_MINUTES", 5)
    monkeypatch.setattr(settings, "PROFILE_EXTRACTION_BURST_USER_TURNS", 3)
    monkeypatch.setattr(settings, "PROFILE_EXTRACTION_ON_DEMAND_ENABLED", False)

    profile = profile_service.get_or_create_profile_for_user(db_session, sample_user.id)
    profile.last_extracted_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=6)
    db_session.add(profile)
    db_session.commit()

    _add_user_message(db_session, chat_session.id, "间隔已满，这条消息应允许抽取。")

    decision = profile_extraction_service.should_schedule_profile_extraction(
        db_session,
        sample_user.id,
        user_message="间隔已满，这条消息应允许抽取。",
    )
    assert decision.should_schedule is True


def test_throttle_burst_user_turns_bypasses_interval(
    db_session,
    sample_user,
    chat_session,
    monkeypatch,
):
    monkeypatch.setattr(settings, "PROFILE_EXTRACTION_MIN_INTERVAL_MINUTES", 60)
    monkeypatch.setattr(settings, "PROFILE_EXTRACTION_BURST_USER_TURNS", 3)
    monkeypatch.setattr(settings, "PROFILE_EXTRACTION_ON_DEMAND_ENABLED", False)

    profile = profile_service.get_or_create_profile_for_user(db_session, sample_user.id)
    profile.last_extracted_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    db_session.add(profile)
    db_session.commit()

    for index in range(3):
        _add_user_message(db_session, chat_session.id, f"爆发消息 {index + 1}")

    decision = profile_extraction_service.should_schedule_profile_extraction(
        db_session,
        sample_user.id,
        user_message="爆发消息 3",
    )
    assert decision.should_schedule is True


def test_disabled_flag_blocks_schedule(db_session, sample_user, chat_session, monkeypatch):
    monkeypatch.setattr(settings, "PROFILE_EXTRACTION_ENABLED", False)
    _add_user_message(db_session, chat_session.id, "我的目标是转行做数据分析")
    assistant = _add_assistant_message(db_session, chat_session.id)

    decision = profile_extraction_service.schedule_profile_extraction_from_chat(
        user_id=sample_user.id,
        session_id=chat_session.id,
        assistant_message_id=assistant.id,
        trace_id="trace-disabled",
    )
    assert decision.should_schedule is False
    assert decision.reason == "disabled"


def test_force_bypasses_gates(db_session, sample_user, chat_session, monkeypatch):
    monkeypatch.setattr(settings, "PROFILE_EXTRACTION_ON_DEMAND_ENABLED", True)

    profile = profile_service.get_or_create_profile_for_user(db_session, sample_user.id)
    profile.last_extracted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(profile)
    db_session.commit()

    _add_user_message(db_session, chat_session.id, "你好")

    decision = profile_extraction_service.should_schedule_profile_extraction(
        db_session,
        sample_user.id,
        user_message="你好",
        force=True,
    )
    assert decision.should_schedule is True


def test_in_flight_dedupes_second_schedule(db_session, sample_user, chat_session, monkeypatch):
    monkeypatch.setattr(settings, "PROFILE_EXTRACTION_ON_DEMAND_ENABLED", False)

    profile = profile_service.get_or_create_profile_for_user(db_session, sample_user.id)
    profile.last_extracted_at = None
    db_session.add(profile)
    db_session.commit()

    submitted: list[tuple] = []

    def capture_submit(fn, /, *args, **kwargs):
        submitted.append((fn, args, kwargs))

    monkeypatch.setattr(profile_extraction_service, "submit_ai_task", capture_submit)

    user_message = _add_user_message(db_session, chat_session.id, "第一条允许抽取的消息内容。")
    assistant = _add_assistant_message(db_session, chat_session.id)

    with profile_extraction_service._in_flight_lock:
        profile_extraction_service._in_flight_user_ids.add(sample_user.id)

    second = profile_extraction_service.schedule_profile_extraction_from_chat(
        user_id=sample_user.id,
        session_id=chat_session.id,
        assistant_message_id=assistant.id,
        trace_id="trace-in-flight",
    )
    assert second.should_schedule is False
    assert second.reason == "in_flight"
    assert submitted == []
