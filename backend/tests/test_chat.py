import pytest
import time

from app.core.config import settings
from app.services import chat_service

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@12345"


def login_admin(client):
    response = client.post(
        "/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def admin_headers(client):
    return {"Authorization": f"Bearer {login_admin(client)}"}


def make_user_payload(index: int = 1):
    return {
        "username": f"20220253{index:02d}",
        "email": f"chat_user_{index}@example.com",
        "password": "Student@12345",
        "full_name": f"Chat User {index}",
        "major": "Engineering",
        "year_of_study": 1,
        "bio": "Chat testing profile",
        "role": "user",
    }


def create_user(client, index: int = 1) -> int:
    response = client.post(
        "/admin/users",
        json=make_user_payload(index),
        headers=admin_headers(client),
    )
    assert response.status_code == 201
    return response.json()["id"]


def login_user(client, index: int = 1):
    username = f"20220253{index:02d}"
    response = client.post("/auth/login", json={"username": username, "password": "Student@12345"})
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture()
def mocked_ai_response(monkeypatch):
    ai_text = "Mocked AI reply for testing."

    monkeypatch.setattr(chat_service, "build_ai_response", lambda message: ai_text)
    return ai_text


def test_send_message_creates_session_and_assistant_reply(client, mocked_ai_response):
    user_id = create_user(client, 1)
    token = login_user(client, 1)
    response = client.post(
        "/chat",
        json={
            "message": "I want to improve my learning consistency.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["session"]["id"] > 0
    assert data["session"]["user_id"] == user_id
    assert data["user_message"]["role"] == "user"
    # assistant_message may be produced in background; poll until it appears
    if data.get("assistant_message") is None:
        start = time.time()
        timeout = 5.0
        while time.time() - start < timeout:
            msgs_resp = client.get(f"/chat/{data['session']['id']}/messages", headers={"Authorization": f"Bearer {token}"})
            msgs = msgs_resp.json()
            if any(m["role"] == "assistant" for m in msgs):
                break
            time.sleep(0.1)

    # final fetch
    msgs_resp = client.get(f"/chat/{data['session']['id']}/messages", headers={"Authorization": f"Bearer {token}"})
    msgs = msgs_resp.json()
    assert any(m["role"] == "assistant" for m in msgs)
    assistant = [m for m in msgs if m["role"] == "assistant"][0]
    assert assistant["content"] == mocked_ai_response
    assert assistant["status"] == "completed"


def test_list_sessions_and_messages(client, mocked_ai_response):
    user_id = create_user(client, 2)
    token = login_user(client, 2)

    send_response = client.post(
        "/chat",
        json={
            "message": "Help me plan my semester goals.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    session_id = send_response.json()["session"]["id"]

    sessions_response = client.get("/chat/sessions", headers={"Authorization": f"Bearer {token}"})
    assert sessions_response.status_code == 200
    assert len(sessions_response.json()) == 1
    assert sessions_response.json()[0]["id"] == session_id

    messages_response = client.get(f"/chat/{session_id}/messages", headers={"Authorization": f"Bearer {token}"})
    assert messages_response.status_code == 200

    messages = messages_response.json()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == mocked_ai_response


def test_send_message_to_existing_session(client, mocked_ai_response):
    user_id = create_user(client, 3)
    token = login_user(client, 3)

    first = client.post(
        "/chat",
        json={"message": "First message"},
        headers={"Authorization": f"Bearer {token}"},
    )
    session_id = first.json()["session"]["id"]
    second = client.post(
        "/chat",
        json={
            "session_id": session_id,
            "message": "Second message",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert second.status_code == 200
    assert second.json()["session"]["id"] == session_id
    messages_response = client.get(f"/chat/{session_id}/messages", headers={"Authorization": f"Bearer {token}"})
    messages = messages_response.json()

    assert len(messages) == 4
    assert messages[-2]["content"] == "Second message"
    assert messages[-1]["content"] == mocked_ai_response


def test_list_messages_with_invalid_session_returns_not_found(client):
    user_id = create_user(client, 4)
    token = login_user(client, 4)
    response = client.get("/chat/9999/messages", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


def test_list_messages_allows_empty_assistant_placeholder(client, mocked_ai_response):
    create_user(client, 40)
    token = login_user(client, 40)

    send_response = client.post(
        "/chat",
        json={
            "message": "Test placeholder behavior.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert send_response.status_code == 200
    session_id = send_response.json()["session"]["id"]

    from app.core.database import SessionLocal
    from app.models.chat import ChatMessage, MessageRole

    db = SessionLocal()
    try:
        db.add(
            ChatMessage(
                session_id=session_id,
                role=MessageRole.ASSISTANT,
                content="",
            )
        )
        db.commit()
    finally:
        db.close()

    messages_response = client.get(f"/chat/{session_id}/messages", headers={"Authorization": f"Bearer {token}"})
    assert messages_response.status_code == 200
    messages = messages_response.json()
    assert any(m["role"] == "assistant" and m["content"] == "" and m["status"] == "pending" for m in messages)


def test_delete_session_removes_session_and_messages(client, mocked_ai_response):
    user_id = create_user(client, 5)
    token = login_user(client, 5)

    send_response = client.post(
        "/chat",
        json={
            "message": "Please help me organize my week.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    session_id = send_response.json()["session"]["id"]

    delete_response = client.delete(f"/chat/{session_id}", headers={"Authorization": f"Bearer {token}"})
    assert delete_response.status_code == 204
    sessions_response = client.get("/chat/sessions", headers={"Authorization": f"Bearer {token}"})
    assert sessions_response.status_code == 200
    assert sessions_response.json() == []

    messages_response = client.get(f"/chat/{session_id}/messages", headers={"Authorization": f"Bearer {token}"})
    assert messages_response.status_code == 404


def test_rename_session_updates_the_session_title(client, mocked_ai_response):
    user_id = create_user(client, 6)
    token = login_user(client, 6)

    send_response = client.post(
        "/chat",
        json={
            "message": "Draft my weekly study plan.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    session_id = send_response.json()["session"]["id"]

    rename_response = client.patch(
        f"/chat/{session_id}",
        json={"title": "Weekly Study Sprint"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert rename_response.status_code == 200
    assert rename_response.json()["id"] == session_id
    assert rename_response.json()["title"] == "Weekly Study Sprint"

    sessions_response = client.get("/chat/sessions", headers={"Authorization": f"Bearer {token}"})
    assert sessions_response.status_code == 200
    assert sessions_response.json()[0]["title"] == "Weekly Study Sprint"


def test_extract_response_text_from_responses_api_output():
    fake_response = type(
        "FakeResponse",
        (),
        {
            "output_text": None,
            "output": [
                type(
                    "FakeMessage",
                    (),
                    {
                        "type": "message",
                        "content": [
                            type(
                                "FakeContent",
                                (),
                                {
                                    "type": "output_text",
                                    "text": "Hello from the model.",
                                },
                            )
                        ],
                    },
                )
            ],
        },
    )()

    text = chat_service._extract_response_text(fake_response)
    assert text == "Hello from the model."


@pytest.mark.skipif(
    not settings.LLM_API_KEY or not settings.RUN_LIVE_AI_TESTS,
    reason="Live AI test requires LLM_API_KEY and RUN_LIVE_AI_TESTS=1",
)
def test_build_ai_response_live_call():
    text = chat_service.build_ai_response("你好呀")
    assert isinstance(text, str)
    assert text.strip()
