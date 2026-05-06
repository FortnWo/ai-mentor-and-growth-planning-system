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
            "email": f"action_plan_{index}@example.com",
            "password": "Student@12345",
            "full_name": f"Action Plan Student {index}",
            "major": "Engineering",
            "year_of_study": 2,
            "bio": "Action plan testing student",
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


def _mock_goal_breakdown_response(title_prefix: str = "Phase"):
    return json.dumps(
        {
            "breakdowns": [
                {
                    "title": f"{title_prefix} 1",
                    "description": "Setup the plan",
                    "children": [
                        {"title": f"{title_prefix} 1.1", "description": "First substep", "children": []},
                    ],
                },
                {
                    "title": f"{title_prefix} 2",
                    "description": "Execute the plan",
                    "children": [],
                },
            ]
        }
    )


def _create_goal_with_breakdowns(client, monkeypatch, student_headers, goal_title: str = "Launch Project"):
    monkeypatch.setattr(chat_service, "build_goal_breakdown_response", lambda message: _mock_goal_breakdown_response())

    create_response = client.post(
        "/goals",
        json={
            "title": goal_title,
            "description": "Build and launch a project",
            "priority": "high",
            "target_date": "2026-12-31",
        },
        headers=student_headers,
    )
    assert create_response.status_code == 201

    goal_id = create_response.json()["id"]
    detail_response = client.get(f"/goals/{goal_id}", headers=student_headers)
    assert detail_response.status_code == 200
    detail = detail_response.json()
    root_nodes = detail["breakdowns"]["root_nodes"]
    assert root_nodes
    return goal_id, detail


def test_action_plans_require_auth(client):
    response = client.get("/action-plans")
    assert response.status_code == 401


def test_create_action_plan_persists_items(client, monkeypatch):
    student = create_student_user(client, 1)
    token = login_student(client, student["username"])
    headers = {"Authorization": f"Bearer {token}"}

    goal_id, goal_detail = _create_goal_with_breakdowns(client, monkeypatch, headers)
    root_nodes = goal_detail["breakdowns"]["root_nodes"]

    first_breakdown_id = root_nodes[0]["id"]
    second_breakdown_id = root_nodes[1]["id"]

    monkeypatch.setattr(
        chat_service,
        "build_action_plan_response",
        lambda message: json.dumps(
            {
                "plan": {
                    "title": "Launch Execution Plan",
                    "summary": "A practical plan to move the goal forward.",
                },
                "items": [
                    {
                        "title": "Complete foundation work",
                        "description": "Finish the first milestone",
                        "frequency": "weekly",
                        "schedule": "Every Monday",
                        "status": "pending",
                        "start_date": "2026-05-01",
                        "due_date": "2026-05-07",
                        "sequence": 1,
                        "breakdown_ref": first_breakdown_id,
                    },
                    {
                        "title": "Ship the second milestone",
                        "description": "Turn the next breakdown into action",
                        "frequency": "once",
                        "schedule": "One-time execution",
                        "status": "in_progress",
                        "start_date": "2026-05-08",
                        "due_date": "2026-05-15",
                        "sequence": 2,
                        "breakdown_ref": second_breakdown_id,
                    },
                ],
            }
        ),
    )

    response = client.post("/action-plans", json={"goal_id": goal_id}, headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["goal_id"] == goal_id
    assert data["title"] == "Launch Execution Plan"
    assert len(data["items"]) == 2
    assert data["items"][0]["breakdown_id"] == first_breakdown_id
    assert data["items"][1]["breakdown_id"] == second_breakdown_id

    list_response = client.get("/action-plans", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_get_action_plan_detail_includes_items(client, monkeypatch):
    student = create_student_user(client, 2)
    token = login_student(client, student["username"])
    headers = {"Authorization": f"Bearer {token}"}

    goal_id, goal_detail = _create_goal_with_breakdowns(client, monkeypatch, headers, goal_title="Study Sprint")
    breakdown_id = goal_detail["breakdowns"]["root_nodes"][0]["id"]

    monkeypatch.setattr(
        chat_service,
        "build_action_plan_response",
        lambda message: json.dumps(
            {
                "plan": {"title": "Study Sprint Plan", "summary": "One clear sequence."},
                "items": [
                    {
                        "title": "Block calendar time",
                        "description": "Reserve focused time blocks",
                        "frequency": "daily",
                        "schedule": "Weekdays 20:00-22:00",
                        "status": "pending",
                        "start_date": "2026-05-01",
                        "due_date": "2026-05-05",
                        "sequence": 1,
                        "breakdown_ref": breakdown_id,
                    }
                ],
            }
        ),
    )

    create_response = client.post("/action-plans", json={"goal_id": goal_id}, headers=headers)
    assert create_response.status_code == 200
    plan_id = create_response.json()["id"]

    detail_response = client.get(f"/action-plans/{plan_id}", headers=headers)
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == plan_id
    assert detail["items"]
    assert detail["items"][0]["breakdown_id"] == breakdown_id


def test_refresh_action_plan_overwrites_items(client, monkeypatch):
    student = create_student_user(client, 3)
    token = login_student(client, student["username"])
    headers = {"Authorization": f"Bearer {token}"}

    goal_id, _ = _create_goal_with_breakdowns(client, monkeypatch, headers, goal_title="Consistency Goal")

    call_count = [0]

    def mock_action_plan_response(message: str):
        call_count[0] += 1
        if call_count[0] == 1:
            return json.dumps(
                {
                    "plan": {"title": "Consistency Plan", "summary": "First draft"},
                    "items": [
                        {
                            "title": "Old item",
                            "description": "Will be replaced",
                            "frequency": "weekly",
                            "schedule": "Week 1",
                            "status": "pending",
                            "start_date": "2026-05-01",
                            "due_date": "2026-05-07",
                            "sequence": 1,
                        }
                    ],
                }
            )

        return json.dumps(
            {
                "plan": {"title": "Consistency Plan", "summary": "Refreshed draft"},
                "items": [
                    {
                        "title": "New item",
                        "description": "Replacement plan item",
                        "frequency": "daily",
                        "schedule": "Every weekday",
                        "status": "in_progress",
                        "start_date": "2026-05-08",
                        "due_date": "2026-05-14",
                        "sequence": 1,
                    },
                    {
                        "title": "New follow-up",
                        "description": "Another refreshed step",
                        "frequency": "once",
                        "schedule": "After the first step",
                        "status": "pending",
                        "start_date": "2026-05-15",
                        "due_date": "2026-05-21",
                        "sequence": 2,
                    },
                ],
            }
        )

    monkeypatch.setattr(chat_service, "build_action_plan_response", mock_action_plan_response)

    create_response = client.post("/action-plans", json={"goal_id": goal_id}, headers=headers)
    assert create_response.status_code == 200
    plan_id = create_response.json()["id"]
    assert [item["title"] for item in create_response.json()["items"]] == ["Old item"]

    refresh_response = client.post(f"/action-plans/{plan_id}/refresh", headers=headers)
    assert refresh_response.status_code == 200
    refreshed = refresh_response.json()
    assert [item["title"] for item in refreshed["items"]] == ["New item", "New follow-up"]


def test_invalid_action_plan_json_returns_conflict(client, monkeypatch):
    student = create_student_user(client, 4)
    token = login_student(client, student["username"])
    headers = {"Authorization": f"Bearer {token}"}

    goal_id, _ = _create_goal_with_breakdowns(client, monkeypatch, headers, goal_title="Invalid JSON Goal")

    monkeypatch.setattr(chat_service, "build_action_plan_response", lambda message: "this is not valid json")

    response = client.post("/action-plans", json={"goal_id": goal_id}, headers=headers)
    assert response.status_code == 409
    assert "valid JSON" in response.json()["detail"]


def test_get_missing_action_plan_returns_not_found(client, monkeypatch):
    student = create_student_user(client, 5)
    token = login_student(client, student["username"])
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/action-plans/99999", headers=headers)
    assert response.status_code == 404