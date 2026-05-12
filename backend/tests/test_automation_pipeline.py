import json
import time

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


def create_student_user(client, index: int = 1):
    response = client.post(
        "/admin/users",
        json={
            "username": f"20220257{index:02d}",
            "email": f"automation_{index}@example.com",
            "password": "Student@12345",
            "full_name": f"Automation Student {index}",
            "major": "Engineering",
            "year_of_study": 2,
            "bio": "Automation testing student",
            "role": "user",
        },
        headers=admin_headers(client),
    )
    assert response.status_code == 201
    return response.json()


def login_student(client, username: str):
    response = client.post("/auth/login", json={"username": username, "password": "Student@12345"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_chat_message_triggers_closed_loop_pipeline(client, monkeypatch):
    student = create_student_user(client, 1)
    token = login_student(client, student["username"])
    headers = {"Authorization": f"Bearer {token}"}

    monkeypatch.setattr(chat_service, "build_ai_response", lambda message: "好的，我们开始吧。")
    monkeypatch.setattr(
        chat_service,
        "build_profile_extraction_response",
        lambda message: json.dumps(
            {
                "interests": ["英语学习"],
                "skills": ["英语基础"],
                "goals": ["通过英语六级"],
                "study_habits": ["晚间学习"],
                "personality": ["自律"],
                "preferences": ["短任务节奏"],
            }
        ),
    )
    monkeypatch.setattr(
        chat_service,
        "build_goal_breakdown_response",
        lambda message: json.dumps(
            {
                "breakdowns": [
                    {"title": "词汇积累", "description": "建立高频词基础", "children": []},
                    {"title": "真题训练", "description": "每周完成真题复盘", "children": []},
                ]
            }
        ),
    )
    monkeypatch.setattr(
        chat_service,
        "build_action_plan_response",
        lambda message: json.dumps(
            {
                "plan": {"title": "六级执行计划", "summary": "按周推进词汇与真题"},
                "items": [
                    {
                        "title": "每日背诵高频词",
                        "description": "每天 30 分钟",
                        "frequency": "daily",
                        "schedule": "21:00-21:30",
                        "status": "pending",
                        "start_date": "2026-05-01",
                        "due_date": "2026-05-31",
                        "sequence": 1,
                    }
                ],
            }
        ),
    )

    send_response = client.post(
        "/chat",
        json={"message": "我想在这学期通过英语六级，请帮我规划。"},
        headers=headers,
    )
    assert send_response.status_code == 200

    goal_id = None
    for _ in range(20):
        goals_response = client.get("/goals", headers=headers)
        assert goals_response.status_code == 200
        goals = goals_response.json()
        matched = [goal for goal in goals if goal["title"] == "通过英语六级"]
        if matched:
            goal_id = matched[0]["id"]
            break
        time.sleep(0.05)

    assert goal_id is not None

    goal_detail_response = client.get(f"/goals/{goal_id}", headers=headers)
    assert goal_detail_response.status_code == 200
    goal_detail = goal_detail_response.json()
    assert len(goal_detail["breakdowns"]["root_nodes"]) == 2

    profile_response = client.get("/profile/extended/me", headers=headers)
    assert profile_response.status_code == 200
    profile = profile_response.json()
    assert "通过英语六级" in profile["goals"]

    plans = []
    for _ in range(20):
        plans_response = client.get("/action-plans", headers=headers)
        assert plans_response.status_code == 200
        plans = plans_response.json()
        if any(plan["goal_id"] == goal_id for plan in plans):
            break
        time.sleep(0.05)

    assert any(plan["goal_id"] == goal_id for plan in plans)
