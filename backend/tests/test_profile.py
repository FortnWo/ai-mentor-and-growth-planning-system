import json

import pytest

from app.services import ai_service, chat_service

ADMIN_USERNAME = "admin"


@pytest.fixture(autouse=True)
def fast_portrait_summary(monkeypatch):
    monkeypatch.setattr(
        ai_service,
        "build_portrait_summary_response",
        lambda message: "你正在持续构建个人成长画像。",
    )
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


def create_student_user(client, index: int = 1):
    response = client.post(
        "/admin/users",
        json={
            "username": f"20220255{index:02d}",
            "email": f"profile_{index}@example.com",
            "password": "Student@12345",
            "full_name": f"Profile Student {index}",
            "major": "Engineering",
            "year_of_study": 1,
            "bio": "Profile testing student",
            "role": "user",
        },
        headers=admin_headers(client),
    )
    assert response.status_code == 201
    return response.json()


def login_student(client, username: str):
    response = client.post(
        "/auth/login",
        json={"username": username, "password": "Student@12345"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_get_profile_requires_auth(client):
    response = client.get("/profile/me")
    assert response.status_code == 401


def test_get_profile_returns_default_empty_structure(client):
    student = create_student_user(client, 1)
    token = login_student(client, student["username"])
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/profile/me", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["user_id"] == student["id"]
    assert data["interests"] == []
    assert data["skills"] == []
    assert data["goals"] == []
    assert data["study_habits"] == []
    assert data["personality"] == []
    assert data["preferences"] == []
    assert data["last_extracted_at"] is None


def test_update_profile_persists_values(client):
    student = create_student_user(client, 2)
    token = login_student(client, student["username"])
    headers = {"Authorization": f"Bearer {token}"}

    update_response = client.put(
        "/profile/me",
        json={
            "interests": ["AI", "ML"],
            "skills": ["Python", "FastAPI"],
            "goals": ["Build portfolio"],
            "study_habits": ["Review nightly"],
            "personality": ["Curious", "Persistent"],
            "preferences": ["Hands-on projects"],
        },
        headers=headers,
    )
    assert update_response.status_code == 200

    read_response = client.get("/profile/me", headers=headers)
    assert read_response.status_code == 200
    data = read_response.json()

    assert data["interests"] == ["AI", "ML"]
    assert data["skills"] == ["Python", "FastAPI"]
    assert data["goals"] == ["Build portfolio"]
    assert data["study_habits"] == ["Review nightly"]
    assert data["personality"] == ["Curious", "Persistent"]
    assert data["preferences"] == ["Hands-on projects"]


def test_refresh_profile_from_chat_updates_profile(client, monkeypatch):
    monkeypatch.setattr(chat_service, "process_message_in_background", lambda session_id, message: None)
    monkeypatch.setattr(chat_service, "build_ai_response", lambda message, **_: "Thanks for sharing your context.")
    monkeypatch.setattr(
        chat_service,
        "build_profile_extraction_response",
        lambda message: json.dumps(
            {
                "interests": ["machine learning"],
                "skills": ["python"],
                "goals": ["improve consistency"],
                "study_habits": ["study every night"],
                "personality": ["self-driven"],
                "preferences": ["short feedback loops"],
            }
        ),
    )

    student = create_student_user(client, 3)
    token = login_student(client, student["username"])
    headers = {"Authorization": f"Bearer {token}"}

    chat_response = client.post(
        "/chat",
        json={"message": "I enjoy machine learning and want to study every night."},
        headers=headers,
    )
    assert chat_response.status_code == 200

    refresh_response = client.post("/profile/me/refresh-from-chat", headers=headers)
    assert refresh_response.status_code == 200

    payload = refresh_response.json()
    assert payload["profile"]["interests"] == ["machine learning"]
    assert payload["profile"]["skills"] == ["python"]
    assert payload["profile"]["goals"] == ["improve consistency"]
    assert payload["extracted"]["study_habits"] == ["study every night"]


def test_get_profile_insights_returns_traits_and_summary(client, monkeypatch):
    monkeypatch.setattr(
        ai_service,
        "build_portrait_summary_response",
        lambda message: "你关注 AI 与 Python，目标明确，学习习惯稳定。",
    )

    student = create_student_user(client, 5)
    token = login_student(client, student["username"])
    headers = {"Authorization": f"Bearer {token}"}

    update_response = client.put(
        "/profile/me",
        json={
            "interests": ["AI"],
            "skills": ["Python"],
            "goals": ["Build portfolio"],
        },
        headers=headers,
    )
    assert update_response.status_code == 200

    insights_response = client.get("/profile/me/insights", headers=headers)
    assert insights_response.status_code == 200

    data = insights_response.json()
    assert data["portrait_summary"]
    assert len(data["traits"]) >= 3

    trait_keys = {trait["trait_key"] for trait in data["traits"]}
    assert "AI" in trait_keys
    assert "Python" in trait_keys

    ai_trait = next(trait for trait in data["traits"] if trait["trait_key"] == "AI")
    assert ai_trait["trait_type"] == "interest"
    assert ai_trait["source"] == "profile_update"
    assert ai_trait["confidence"] == 0.8


def test_get_profile_insights_requires_auth(client):
    response = client.get("/profile/me/insights")
    assert response.status_code == 401


def test_refresh_profile_invalid_llm_output_returns_conflict(client, monkeypatch):
    monkeypatch.setattr(chat_service, "process_message_in_background", lambda session_id, message: None)
    monkeypatch.setattr(chat_service, "build_ai_response", lambda message, **_: "Assistant response")
    monkeypatch.setattr(chat_service, "build_profile_extraction_response", lambda message: "not-valid-json")

    student = create_student_user(client, 4)
    token = login_student(client, student["username"])
    headers = {"Authorization": f"Bearer {token}"}

    chat_response = client.post(
        "/chat",
        json={"message": "I like learning by doing."},
        headers=headers,
    )
    assert chat_response.status_code == 200

    refresh_response = client.post("/profile/me/refresh-from-chat", headers=headers)
    assert refresh_response.status_code == 409
    assert "valid JSON" in refresh_response.json()["detail"]
