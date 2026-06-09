import json

import pytest

from app.core.config import settings
from app.core.ukl_constants import (
    REF_TYPE_USER,
    SLICE_TYPE_EPISODIC_NARRATIVE,
    SLICE_TYPE_PROFILE,
)
from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.models.chat_session_summary import ChatSessionSummary
from app.models.user import User
from app.schemas.profile import UserProfileUpdate
from app.services import chat_context_service, profile_service, ukl_memory_fact_service, ukl_service


@pytest.fixture
def chat_user(db_session):
    user = User(
        username="ctx_user",
        email="ctx@example.com",
        password_hash="hashed",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def chat_session(db_session, chat_user):
    session = ChatSession(user_id=chat_user.id, title="ctx session")
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


def _add_message(db_session, session_id: int, role: MessageRole, content: str) -> ChatMessage:
    message = ChatMessage(session_id=session_id, role=role, content=content)
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)
    return message


def test_legacy_context_includes_full_history(db_session, chat_session, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", False)
    _add_message(db_session, chat_session.id, MessageRole.USER, "first question")
    _add_message(db_session, chat_session.id, MessageRole.ASSISTANT, "first answer")

    prompt = chat_context_service.build_chat_context(
        db_session,
        user_id=chat_session.user_id,
        session_id=chat_session.id,
        current_user_message="second question",
    )
    assert "first question" in prompt
    assert "first answer" in prompt
    assert "second question" in prompt


def test_ukl_context_includes_profile_section(db_session, chat_user, chat_session, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_SUMMARY_USE_THRESHOLD", 100)

    profile_service.update_profile_for_user(
        db_session,
        chat_user.id,
        UserProfileUpdate(interests=["music"]),
    )
    ukl_service.ingest_profile_from_user(db_session, chat_user.id)
    db_session.commit()

    _add_message(db_session, chat_session.id, MessageRole.USER, "hello")

    prompt = chat_context_service.build_chat_context(
        db_session,
        user_id=chat_user.id,
        session_id=chat_session.id,
        current_user_message="hello",
    )
    assert "[用户画像]" in prompt
    assert "hello" in prompt


def test_ukl_long_session_uses_summary_not_early_messages(db_session, chat_user, chat_session, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_WORK_MEMORY_MAX_MESSAGES", 4)
    monkeypatch.setattr(settings, "CHAT_SUMMARY_USE_THRESHOLD", 6)

    for index in range(8):
        _add_message(db_session, chat_session.id, MessageRole.USER, f"early-msg-{index}")
        _add_message(db_session, chat_session.id, MessageRole.ASSISTANT, f"early-reply-{index}")

    db_session.add(
        ChatSessionSummary(
            session_id=chat_session.id,
            user_id=chat_user.id,
            summary="你们之前讨论了学习节奏与考试压力。",
            summarized_through_message_id=8,
            message_count=8,
        )
    )
    db_session.commit()

    prompt = chat_context_service.build_chat_context(
        db_session,
        user_id=chat_user.id,
        session_id=chat_session.id,
        current_user_message="latest question",
    )
    assert "[本会话Earlier摘要]" in prompt
    assert "学习节奏" in prompt
    assert "early-msg-0" not in prompt
    assert "latest question" in prompt


def test_ukl_long_session_without_summary_limits_work_memory(db_session, chat_user, chat_session, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_WORK_MEMORY_MAX_MESSAGES", 4)
    monkeypatch.setattr(settings, "CHAT_SUMMARY_USE_THRESHOLD", 6)

    for index in range(8):
        _add_message(db_session, chat_session.id, MessageRole.USER, f"msg-{index}")
        _add_message(db_session, chat_session.id, MessageRole.ASSISTANT, f"reply-{index}")

    prompt = chat_context_service.build_chat_context(
        db_session,
        user_id=chat_user.id,
        session_id=chat_session.id,
        current_user_message="newest",
    )
    assert "msg-0" not in prompt
    assert "msg-7" in prompt or "reply-7" in prompt
    assert "newest" in prompt


def test_profile_fallback_when_no_ukl_slice(db_session, chat_user, chat_session, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_SUMMARY_USE_THRESHOLD", 100)

    profile = profile_service.get_or_create_profile_for_user(db_session, chat_user.id)
    profile.portrait_summary = "你正在稳步建立学习习惯。"
    db_session.commit()

    prompt = chat_context_service.build_chat_context(
        db_session,
        user_id=chat_user.id,
        session_id=chat_session.id,
        current_user_message="hi",
    )
    assert "稳步建立学习习惯" in prompt


def test_update_session_summary_upserts(db_session, chat_user, chat_session, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_SESSION_SUMMARY_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_WORK_MEMORY_MAX_MESSAGES", 4)
    monkeypatch.setattr(settings, "CHAT_SUMMARY_USE_THRESHOLD", 6)
    monkeypatch.setattr(
        "app.services.ai_service.build_session_summary_response",
        lambda prior, dialogue, **_: f"摘要：{dialogue[:20]}",
    )

    messages: list[ChatMessage] = []
    for index in range(10):
        messages.append(_add_message(db_session, chat_session.id, MessageRole.USER, f"u{index}"))
        messages.append(_add_message(db_session, chat_session.id, MessageRole.ASSISTANT, f"a{index}"))

    row = chat_context_service.update_session_summary(
        db_session,
        session_id=chat_session.id,
        user_id=chat_user.id,
    )
    db_session.commit()

    assert row is not None
    assert row.summary.startswith("摘要：")
    assert row.summarized_through_message_id == messages[15].id


def test_post_chat_works_with_ukl_enabled(client, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    ai_text = "Mocked UKL chat reply."
    empty_profile_json = (
        '{"interests":[],"skills":[],"goals":[],"study_habits":[],"personality":[],"preferences":[]}'
    )

    from app.services import chat_service

    monkeypatch.setattr(chat_service, "build_ai_response", lambda message, **_: ai_text)
    monkeypatch.setattr(chat_service, "build_profile_extraction_response", lambda message: empty_profile_json)
    monkeypatch.setattr(
        chat_service,
        "generate_session_title",
        lambda user_message, assistant_message: chat_service.suggest_session_title(user_message),
    )
    monkeypatch.setattr(
        chat_context_service,
        "schedule_session_summary_update",
        lambda session_id, user_id: None,
    )
    monkeypatch.setattr(chat_context_service, "_schedule_lazy_profile_ingest", lambda user_id: None)

    admin_login = client.post("/auth/login", json={"username": "admin", "password": "Admin@12345"})
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]
    create_resp = client.post(
        "/admin/users",
        json={
            "username": "2022025999",
            "email": "ukl_chat@example.com",
            "password": "Student@12345",
            "full_name": "UKL Chat",
            "major": "Engineering",
            "year_of_study": 1,
            "bio": "UKL chat test",
            "role": "user",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_resp.status_code == 201
    user_login = client.post(
        "/auth/login",
        json={"username": "2022025999", "password": "Student@12345"},
    )
    assert user_login.status_code == 200
    user_token = user_login.json()["access_token"]

    response = client.post(
        "/chat",
        json={"message": "Tell me about planning."},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 200


def test_tier2_memory_facts_included_when_gate_hits(db_session, chat_user, chat_session, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "MEMORY_FACT_ENABLED", True)
    monkeypatch.setattr(settings, "MEMORY_FACT_EMBEDDING_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_SUMMARY_USE_THRESHOLD", 100)

    monkeypatch.setattr(
        "app.services.ai_service.create_embedding",
        lambda text: [1.0, 0.0, 0.0],
    )

    ukl_service.ingest_profile_from_user(db_session, chat_user.id)
    ukl_memory_fact_service.ingest_memory_fact(
        db_session,
        chat_user.id,
        fact="用户每周三晚上有空学英语",
        session_id=chat_session.id,
        message_id=1,
        salience=0.9,
    )
    db_session.commit()

    prompt = chat_context_service.build_chat_context(
        db_session,
        user_id=chat_user.id,
        session_id=chat_session.id,
        current_user_message="你还记得之前说过什么时候学英语吗",
    )
    assert "[相关事实记忆]" in prompt
    assert "每周三晚上有空学英语" in prompt


def test_tier2_memory_facts_excluded_without_gate(db_session, chat_user, chat_session, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "MEMORY_FACT_ENABLED", True)
    monkeypatch.setattr(settings, "MEMORY_FACT_EMBEDDING_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_SUMMARY_USE_THRESHOLD", 100)

    ukl_service.ingest_profile_from_user(db_session, chat_user.id)
    ukl_memory_fact_service.ingest_memory_fact(
        db_session,
        chat_user.id,
        fact="用户每周三晚上有空学英语",
        session_id=chat_session.id,
        message_id=2,
        salience=0.9,
    )
    db_session.commit()

    prompt = chat_context_service.build_chat_context(
        db_session,
        user_id=chat_user.id,
        session_id=chat_session.id,
        current_user_message="今天天气不错",
    )
    assert "[相关事实记忆]" not in prompt


def test_episodic_extra_still_gated(db_session, chat_user, chat_session, monkeypatch):
    monkeypatch.setattr(settings, "UKL_ENABLED", True)
    monkeypatch.setattr(settings, "CHAT_SUMMARY_USE_THRESHOLD", 100)

    ukl_service.ingest(
        db_session,
        chat_user.id,
        slice_type=SLICE_TYPE_EPISODIC_NARRATIVE,
        source_module="test",
        ref_type=REF_TYPE_USER,
        ref_id=chat_user.id,
        payload={"summary": "用户最近在准备期末考试。", "updated_at": None},
    )
    ukl_service.ingest_profile_from_user(db_session, chat_user.id)
    db_session.commit()

    gated_prompt = chat_context_service.build_chat_context(
        db_session,
        user_id=chat_user.id,
        session_id=chat_session.id,
        current_user_message="还记得上次的进度吗",
    )
    plain_prompt = chat_context_service.build_chat_context(
        db_session,
        user_id=chat_user.id,
        session_id=chat_session.id,
        current_user_message="聊聊今天的安排",
    )
    assert "[跨会话记忆]" in gated_prompt
    assert "期末考试" in gated_prompt
    assert "[跨会话记忆]" not in plain_prompt
