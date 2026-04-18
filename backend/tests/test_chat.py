def make_user_payload(index: int = 1):
    return {
        "username": f"chat_user_{index}",
        "email": f"chat_user_{index}@example.com",
        "full_name": f"Chat User {index}",
        "major": "Engineering",
        "year_of_study": 1,
        "bio": "Chat testing profile",
    }


def create_user(client, index: int = 1) -> int:
    response = client.post("/users", json=make_user_payload(index))
    assert response.status_code == 201
    return response.json()["id"]


def test_send_message_creates_session_and_assistant_reply(client):
    user_id = create_user(client, 1)

    response = client.post(
        "/chat",
        json={
            "user_id": user_id,
            "message": "I want to improve my learning consistency.",
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["session"]["id"] > 0
    assert data["session"]["user_id"] == user_id
    assert data["user_message"]["role"] == "user"
    assert data["assistant_message"]["role"] == "assistant"


def test_list_sessions_and_messages(client):
    user_id = create_user(client, 2)

    send_response = client.post(
        "/chat",
        json={
            "user_id": user_id,
            "message": "Help me plan my semester goals.",
        },
    )
    session_id = send_response.json()["session"]["id"]

    sessions_response = client.get("/chat/sessions", params={"user_id": user_id})
    assert sessions_response.status_code == 200
    assert len(sessions_response.json()) == 1
    assert sessions_response.json()[0]["id"] == session_id

    messages_response = client.get(
        f"/chat/{session_id}/messages",
        params={"user_id": user_id},
    )
    assert messages_response.status_code == 200

    messages = messages_response.json()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


def test_send_message_to_existing_session(client):
    user_id = create_user(client, 3)

    first = client.post(
        "/chat",
        json={"user_id": user_id, "message": "First message"},
    )
    session_id = first.json()["session"]["id"]

    second = client.post(
        "/chat",
        json={
            "user_id": user_id,
            "session_id": session_id,
            "message": "Second message",
        },
    )
    assert second.status_code == 200
    assert second.json()["session"]["id"] == session_id

    messages_response = client.get(
        f"/chat/{session_id}/messages",
        params={"user_id": user_id},
    )
    messages = messages_response.json()

    assert len(messages) == 4
    assert messages[-2]["content"] == "Second message"


def test_list_messages_with_invalid_session_returns_not_found(client):
    user_id = create_user(client, 4)
    response = client.get("/chat/9999/messages", params={"user_id": user_id})
    assert response.status_code == 404
