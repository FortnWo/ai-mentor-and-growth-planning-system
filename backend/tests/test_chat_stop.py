import pytest

from app.core.domain_events import DomainEventName
from app.schemas.chat import MessageDeliveryStatus
from app.services import chat_service
from tests.test_chat import create_user, login_user


def test_send_message_returns_pending_placeholder(client, monkeypatch):
    monkeypatch.setattr(chat_service, "build_ai_response", lambda message, **_: "late reply")

    create_user(client, 1)
    token = login_user(client, 1)
    response = client.post(
        "/chat",
        json={"message": "hello"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["assistant_message"] is not None
    assert data["assistant_message"]["status"] == "pending"
    assert data["assistant_message"]["content"] == ""


def test_stop_endpoint_marks_pending_message_cancelled(client, db_session):
    user_id = create_user(client, 2)
    token = login_user(client, 2)
    session = chat_service.create_session(db_session, user_id=user_id, title="t")
    chat_service.create_user_message(db_session, session=session, message="hello")
    placeholder = chat_service.create_assistant_placeholder(db_session, session)
    chat_service.chat_generation_registry.register(placeholder.id)

    stop_response = client.post(
        f"/chat/{session.id}/messages/{placeholder.id}/stop",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert stop_response.status_code == 204

    msgs = client.get(f"/chat/{session.id}/messages", headers={"Authorization": f"Bearer {token}"}).json()
    assistant = next(message for message in msgs if message["id"] == placeholder.id)
    assert assistant["status"] == "cancelled"
    assert assistant["content"] == chat_service.ASSISTANT_STOPPED_MESSAGE


def test_stop_endpoint_returns_409_when_not_pending(client, monkeypatch):
    ai_text = "Mocked AI reply for testing."
    empty_profile_json = (
        '{"interests":[],"skills":[],"goals":[],"study_habits":[],"personality":[],"preferences":[]}'
    )
    monkeypatch.setattr(chat_service, "build_ai_response", lambda message, **_: ai_text)
    monkeypatch.setattr(chat_service, "build_profile_extraction_response", lambda message: empty_profile_json)
    monkeypatch.setattr(
        chat_service,
        "generate_session_title",
        lambda user_message, assistant_message: chat_service.suggest_session_title(user_message),
    )
    create_user(client, 3)
    token = login_user(client, 3)
    send_response = client.post(
        "/chat",
        json={"message": "done"},
        headers={"Authorization": f"Bearer {token}"},
    )
    session_id = send_response.json()["session"]["id"]
    message_id = send_response.json()["assistant_message"]["id"]

    msgs = client.get(f"/chat/{session_id}/messages", headers={"Authorization": f"Bearer {token}"}).json()
    assistant = next(message for message in msgs if message["id"] == message_id)
    assert assistant["status"] == "completed"

    stop_response = client.post(
        f"/chat/{session_id}/messages/{message_id}/stop",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert stop_response.status_code == 409


def test_stopped_message_skips_profile_event(client, monkeypatch, db_session):
    published: list[str] = []

    def capture_publish(*, event_name, user_id, payload=None, trace_id=None, fail_fast=False):
        published.append(event_name)
        from app.core.domain_events import build_domain_event

        return build_domain_event(event_name=event_name, user_id=user_id, payload=payload, trace_id=trace_id)

    monkeypatch.setattr("app.services.chat_service.event_bus.publish", capture_publish)
    monkeypatch.setattr(chat_service, "build_ai_response", lambda message, **_: "done")

    user_id = create_user(client, 4)
    session = chat_service.create_session(db_session, user_id=user_id, title="t")
    chat_service.create_user_message(db_session, session=session, message="hi")
    placeholder = chat_service.create_assistant_placeholder(db_session, session)
    chat_service.chat_generation_registry.register(placeholder.id)
    chat_service.chat_generation_registry.request_stop(placeholder.id)

    chat_service.process_message_in_background(session.id, "hi", placeholder.id)

    db_session.expire_all()
    refreshed = chat_service.list_messages_for_session(db_session, session.id, user_id=user_id)
    assistant = [message for message in refreshed if message.role.value == "assistant"][-1]
    assert chat_service.infer_message_status(assistant.role, assistant.content) == MessageDeliveryStatus.CANCELLED
    assert DomainEventName.ON_CHAT_MESSAGE.value not in published
