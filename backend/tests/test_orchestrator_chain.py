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


def test_on_chat_message_chain_does_not_raise(db_session, sample_user, monkeypatch):
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

    from app.services import chat_service, goal_service

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

    event = build_domain_event(
        event_name=DomainEventName.ON_CHAT_MESSAGE.value,
        user_id=sample_user.id,
        payload={"session_id": session.id},
    )

    orchestrator._on_chat_message(event)
    orchestrator._on_profile_updated(
        build_domain_event(
            event_name=DomainEventName.ON_PROFILE_UPDATED.value,
            user_id=sample_user.id,
            payload={
                "session_id": session.id,
                "profile_id": 1,
                "extracted": {"goals": ["三个月入门数据分析"]},
            },
        )
    )


def test_orchestrator_handlers_import_profile_service():
    assert orchestrator.profile_service is not None
    assert hasattr(orchestrator.profile_service, "apply_extraction_result_for_user")
