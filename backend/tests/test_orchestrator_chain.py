import json

import pytest

from app.core.config import settings
from app.core.domain_events import DomainEventName, build_domain_event
from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.models.user import User
import app.workflows.growth_cycle_orchestrator as orchestrator


@pytest.fixture
def sample_user(db_session):
    user = User(
        username="orch_chain",
        email="orchchain@example.com",
        password_hash="hashed",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_on_chat_message_schedules_profile_extraction(db_session, sample_user, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", False)
    monkeypatch.setattr(settings, "PROFILE_EXTRACTION_ON_DEMAND_ENABLED", False)

    session = ChatSession(user_id=sample_user.id, title="Test")
    db_session.add(session)
    db_session.flush()

    user_message = ChatMessage(
        session_id=session.id,
        role=MessageRole.USER,
        content="我想学习数据分析，目标是三个月内入门。",
    )
    db_session.add(user_message)
    db_session.flush()

    assistant_message = ChatMessage(
        session_id=session.id,
        role=MessageRole.ASSISTANT,
        content="很好，我们可以一起制定计划。",
    )
    db_session.add(assistant_message)
    db_session.commit()

    scheduled_calls: list[dict] = []

    def capture_schedule(**kwargs):
        scheduled_calls.append(kwargs)
        from app.services.profile_extraction_service import ProfileExtractionScheduleDecision

        return ProfileExtractionScheduleDecision(True, None)

    monkeypatch.setattr(
        orchestrator.profile_extraction_service,
        "schedule_profile_extraction_from_chat",
        capture_schedule,
    )

    event = build_domain_event(
        event_name=DomainEventName.ON_CHAT_MESSAGE.value,
        user_id=sample_user.id,
        payload={
            "session_id": session.id,
            "assistant_message_id": assistant_message.id,
        },
    )

    orchestrator._on_chat_message(event)

    assert len(scheduled_calls) == 1
    assert scheduled_calls[0]["user_id"] == sample_user.id
    assert scheduled_calls[0]["session_id"] == session.id
    assert scheduled_calls[0]["assistant_message_id"] == assistant_message.id
    assert scheduled_calls[0]["trace_id"] == event.trace_id


def test_run_profile_extraction_from_chat_publishes_profile_updated(
    db_session,
    sample_user,
    monkeypatch,
):
    monkeypatch.setattr(settings, "UKL_ENABLED", False)

    session = ChatSession(user_id=sample_user.id, title="Test")
    db_session.add(session)
    db_session.flush()

    db_session.add(
        ChatMessage(
            session_id=session.id,
            role=MessageRole.USER,
            content="我想学习数据分析，目标是三个月内入门。",
        )
    )
    db_session.commit()

    from app.services import chat_service, goal_service, profile_extraction_service

    monkeypatch.setattr(
        chat_service,
        "build_profile_extraction_response",
        lambda msg: json.dumps(
            {
                "interests": ["数据分析"],
                "skills": [],
                "goals": ["三个月入门数据分析"],
                "study_habits": [],
                "personality": [],
                "preferences": [],
            }
        ),
    )
    monkeypatch.setattr(
        chat_service,
        "build_goal_breakdown_response",
        lambda msg: json.dumps({"nodes": []}),
    )
    monkeypatch.setattr(goal_service, "list_goals_for_user", lambda db, uid: [])

    published: list[str] = []

    def capture_publish(*, event_name, **kwargs):
        published.append(event_name)

    monkeypatch.setattr(profile_extraction_service.event_bus, "publish", capture_publish)

    profile_extraction_service.run_profile_extraction_from_chat(
        user_id=sample_user.id,
        session_id=session.id,
        trace_id="trace-run",
    )

    assert DomainEventName.ON_PROFILE_UPDATED.value in published


def test_orchestrator_handlers_import_profile_service():
    assert orchestrator.profile_service is not None
    assert hasattr(orchestrator.profile_service, "apply_extraction_result_for_user")
