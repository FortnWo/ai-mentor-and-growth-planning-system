import json

from app.services import chat_service


ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin@12345"


def login_admin(client):
    response = client.post(
        "/auth/login",
        json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD,
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def admin_headers(client):
    return {"Authorization": f"Bearer {login_admin(client)}"}


def create_student_user(client, index: int = 1):
    response = client.post(
        "/admin/users",
        json={
            "username": f"20220256{index:02d}",
            "email": f"growth_{index}@example.com",
            "password": "Student@12345",
            "full_name": f"Growth Student {index}",
            "major": "Engineering",
            "year_of_study": 2,
            "bio": "Growth testing student",
            "role": "user",
        },
        headers=admin_headers(client),
    )
    assert response.status_code == 201
    return response.json()


def login_student(client, username: str):
    response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": "Student@12345",
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_manual_create_and_idempotency(client):
    student = create_student_user(client, 10)
    token = login_student(client, student["username"]) 
    headers = {"Authorization": f"Bearer {token}"}

    payload = {"title": "小胜利", "summary": "完成了 30 分钟复习", "idempotency_key": "test-key-1"}
    r1 = client.post("/growth-records", json=payload, headers=headers)
    assert r1.status_code == 201
    r2 = client.post("/growth-records", json=payload, headers=headers)
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


def test_action_plan_completion_writes_record(client, monkeypatch):
    student = create_student_user(client, 11)
    token = login_student(client, student["username"]) 
    headers = {"Authorization": f"Bearer {token}"}

    breakdown_json = json.dumps(
        {
            "breakdowns": [
                {
                    "title": "Main",
                    "description": None,
                    "children": [{"title": "Sub", "description": None, "children": []}],
                }
            ]
        }
    )
    monkeypatch.setattr(chat_service, "build_goal_breakdown_response", lambda message: breakdown_json)
    monkeypatch.setattr(
        chat_service,
        "build_action_plan_response",
        lambda msg: json.dumps({"plan": {"title": "Plan1", "summary": "s"}, "items": []}),
    )

    create_goal = client.post("/goals", json={"title": "G1", "description": "desc"}, headers=headers)
    assert create_goal.status_code == 201
    goal_id = create_goal.json()["id"]

    detail_goal = client.get(f"/goals/{goal_id}", headers=headers)
    assert detail_goal.status_code == 200
    assert detail_goal.json()["breakdowns"]["root_nodes"]

    # mock action plan generation to return one completed item
    def mock_action_plan(_):
        return '{"plan": {"title": "Plan1", "summary": "s"}, "items": [{"title": "Done task", "description": "done", "status": "completed", "sequence": 1}]}'

    monkeypatch.setattr(chat_service, "build_action_plan_response", lambda message: mock_action_plan(message))

    resp = client.post("/action-plans", json={"goal_id": goal_id}, headers=headers)
    assert resp.status_code == 202
    created = resp.json()
    assert isinstance(created, list)
    plan_id = created[0]["id"]

    # poll for plan ready
    detail = None
    for _ in range(20):
        d = client.get(f"/action-plans/{plan_id}", headers=headers)
        if d.status_code == 200 and d.json().get("status") != "in_progress":
            detail = d.json()
            break

    assert detail is not None

    # now check growth records list
    list_resp = client.get("/growth-records", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert any(item["title"] == "Done task" for item in items)

    stats_resp = client.get("/growth-records/stats", headers=headers)
    assert stats_resp.status_code == 200
    assert stats_resp.json()["completed_count"] >= 1


def test_aggregation_updated_on_create(client):
    student = create_student_user(client, 12)
    token = login_student(client, student["username"]) 
    headers = {"Authorization": f"Bearer {token}"}

    payload = {"title": "Today reflection", "summary": "学习 1 小时", "record_type": "manual", "idempotency_key": "agg-test-1"}
    r = client.post("/growth-records", json=payload, headers=headers)
    assert r.status_code == 201

    stats = client.get("/growth-records/stats", headers=headers)
    assert stats.status_code == 200
    data = stats.json()
    assert data["reflection_count"] >= 1


def test_daily_trend_endpoint(client):
    student = create_student_user(client, 13)
    token = login_student(client, student["username"])
    headers = {"Authorization": f"Bearer {token}"}

    from datetime import date, timedelta

    today = date.today()
    start = (today - timedelta(days=2)).isoformat()
    end = today.isoformat()

    r = client.get("/growth-records/trend/daily", params={"start_date": start, "end_date": end}, headers=headers)
    assert r.status_code == 200
    points = r.json()
    assert len(points) == 3
    assert all("record_date" in p for p in points)

    payload = {"title": "Trend day", "summary": "x", "record_type": "manual", "idempotency_key": "trend-1"}
    assert client.post("/growth-records", json=payload, headers=headers).status_code == 201

    r2 = client.get("/growth-records/trend/daily", params={"start_date": start, "end_date": end}, headers=headers)
    assert r2.status_code == 200
    today_point = next((p for p in r2.json() if p["record_date"] == end), None)
    assert today_point is not None
    assert today_point["reflection_count"] >= 1
