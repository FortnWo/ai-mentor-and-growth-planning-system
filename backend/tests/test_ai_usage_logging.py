from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.models.system_config import AIUsageLog
from app.models.user import User
from app.services import ai_service, chat_service
from tests.test_chat import admin_headers, create_user
from tests.test_user import login_admin


def _mock_llm_response(*, text: str = "ok", input_tokens: int = 10, output_tokens: int = 5):
    return SimpleNamespace(
        output_text=text,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        output=[],
    )


def _patch_openai_create(monkeypatch, response=None):
    response = response or _mock_llm_response()

    mock_client = MagicMock()
    mock_client.responses.create.return_value = response

    monkeypatch.setattr(ai_service, "_get_ai_client", lambda: mock_client)
    monkeypatch.setattr(ai_service.settings, "LLM_MODEL", "gpt-test", raising=False)
    return mock_client


def test_log_usage_persists_with_user_id(db_session):
    response = _mock_llm_response(input_tokens=12, output_tokens=3)
    ai_service._log_usage("gpt-test", "chat", response, user_id=42)

    row = db_session.query(AIUsageLog).one()
    assert row.user_id == 42
    assert row.prompt_tokens == 12
    assert row.completion_tokens == 3
    assert row.task == "chat"


def test_log_usage_without_usage_metadata_still_inserts_row(db_session):
    response = SimpleNamespace(output_text="hi")
    ai_service._log_usage("gpt-test", "chat", response, user_id=7)

    row = db_session.query(AIUsageLog).one()
    assert row.user_id == 7
    assert row.prompt_tokens == 0
    assert row.completion_tokens == 0


def test_build_chat_response_logs_user_id(monkeypatch, db_session):
    _patch_openai_create(monkeypatch)
    ai_service.build_chat_response("hello", user_id=99)

    row = db_session.query(AIUsageLog).one()
    assert row.user_id == 99
    assert row.task == "chat"
    assert row.prompt_tokens == 10


def test_build_admin_chat_response_logs_user_id(monkeypatch, db_session):
    _patch_openai_create(monkeypatch)
    ai_service.build_admin_chat_response("admin question", db=db_session, user_id=1)

    rows = db_session.query(AIUsageLog).all()
    assert len(rows) >= 1
    assert all(r.user_id == 1 for r in rows)
    assert rows[0].task == "admin_chat"


def test_usage_logs_api_filters_by_username(client, db_session):
    student_id = create_user(client, 1)
    student = db_session.query(User).filter(User.id == student_id).one()
    username = student.username

    db_session.add(
        AIUsageLog(
            user_id=student_id,
            model="gpt-test",
            prompt_tokens=100,
            completion_tokens=50,
            task="chat",
        )
    )
    db_session.commit()

    response = client.get(
        "/admin/system/logs/usage",
        params={"period": "week", "username": username},
        headers={"Authorization": f"Bearer {login_admin(client)}"},
    )
    assert response.status_code == 200
    stats = response.json()["stats"]
    assert any(row["calls"] >= 1 for row in stats)
    assert sum(row["prompt_tokens"] for row in stats) >= 100


def test_usage_logs_debug_endpoint(client, db_session):
    db_session.add(
        AIUsageLog(
            user_id=None,
            model="gpt-test",
            prompt_tokens=1,
            completion_tokens=1,
            task="chat",
        )
    )
    db_session.commit()

    response = client.get(
        "/admin/system/logs/usage/debug",
        headers={"Authorization": f"Bearer {login_admin(client)}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["table_exists"] is True
    assert data["total_rows"] >= 1
    assert data["null_user_id_rows"] >= 1
    assert len(data["last_rows"]) >= 1


def test_process_message_in_background_logs_owner_user_id(client, monkeypatch, db_session):
    user_id = create_user(client, 2)
    user = db_session.query(User).filter(User.id == user_id).one()

    session = chat_service.create_session(db_session, user_id=user.id, title="t")
    chat_service.create_user_message(db_session, session=session, message="hi")

    captured: dict[str, int | None] = {}

    def fake_build_ai_response(message, *, instructions=None, db=None, user_id=None):
        captured["user_id"] = user_id
        ai_service._log_usage(
            "gpt-test",
            "chat",
            _mock_llm_response(),
            user_id=user_id,
        )
        return "mocked reply"

    monkeypatch.setattr(chat_service, "build_ai_response", fake_build_ai_response)

    placeholder = chat_service.create_assistant_placeholder(db_session, session)
    chat_service.process_message_in_background(session.id, "follow up", placeholder.id)

    assert captured["user_id"] == user.id
    row = db_session.query(AIUsageLog).filter(AIUsageLog.user_id == user.id).one()
    assert row.task == "chat"
