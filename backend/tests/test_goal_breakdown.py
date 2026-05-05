import json

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
            "username": f"202202550{index:01d}",
            "email": f"goal_test_{index}@example.com",
            "password": "Student@12345",
            "full_name": f"Goal Test Student {index}",
            "major": "Engineering",
            "year_of_study": 2,
            "bio": "Goal breakdown testing student",
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


def test_create_goal_requires_auth(client):
    response = client.post(
        "/goals",
        json={"title": "Learn Python", "priority": "high"},
    )
    assert response.status_code == 401


def test_create_goal_returns_created_goal(client, monkeypatch):
    """Test creating a goal with valid data"""
    monkeypatch.setattr(
        chat_service,
        "build_goal_breakdown_response",
        lambda message: json.dumps(
            {
                "breakdowns": [
                    {
                        "title": "Fundamentals",
                        "description": "Learn Python basics",
                        "children": [
                            {"title": "Variables & Types", "description": None, "children": []},
                            {"title": "Functions", "description": None, "children": []},
                        ],
                    },
                    {
                        "title": "Advanced Topics",
                        "description": "Async, testing, and more",
                        "children": [],
                    },
                ]
            }
        ),
    )

    student = create_student_user(client, 1)
    token = login_student(client, student["username"])
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/goals",
        json={
            "title": "Learn Python",
            "description": "Master Python programming for 3 months",
            "priority": "high",
            "target_date": "2026-12-31",
        },
        headers=headers,
    )

    assert response.status_code == 201
    data = response.json()

    assert data["title"] == "Learn Python"
    assert data["description"] == "Master Python programming for 3 months"
    assert data["priority"] == "high"
    assert data["status"] == "active"
    assert data["user_id"] == student["id"]
    assert data["target_date"] == "2026-12-31"


def test_list_goals_returns_user_goals(client, monkeypatch):
    """Test listing goals for authenticated user"""
    monkeypatch.setattr(
        chat_service,
        "build_goal_breakdown_response",
        lambda message: json.dumps({"breakdowns": []}),
    )

    student = create_student_user(client, 2)
    token = login_student(client, student["username"])
    headers = {"Authorization": f"Bearer {token}"}

    # Create multiple goals
    for i in range(3):
        client.post(
            "/goals",
            json={"title": f"Goal {i+1}", "priority": "medium"},
            headers=headers,
        )

    # List goals
    response = client.get("/goals", headers=headers)
    assert response.status_code == 200

    goals = response.json()
    assert len(goals) == 3
    assert all(goal["user_id"] == student["id"] for goal in goals)


def test_get_goal_detail_returns_goal_with_breakdown(client, monkeypatch):
    """Test getting goal detail with breakdown tree"""
    breakdown_response = {
        "breakdowns": [
            {
                "title": "Phase 1",
                "description": "Setup",
                "children": [
                    {"title": "Install tools", "description": None, "children": []},
                ],
            },
            {
                "title": "Phase 2",
                "description": "Development",
                "children": [],
            },
        ]
    }

    monkeypatch.setattr(
        chat_service,
        "build_goal_breakdown_response",
        lambda message: json.dumps(breakdown_response),
    )

    student = create_student_user(client, 3)
    token = login_student(client, student["username"])
    headers = {"Authorization": f"Bearer {token}"}

    # Create goal
    create_response = client.post(
        "/goals",
        json={"title": "Setup Development", "priority": "high"},
        headers=headers,
    )
    assert create_response.status_code == 201
    goal_id = create_response.json()["id"]

    # Get detail
    response = client.get(f"/goals/{goal_id}", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == goal_id
    assert data["title"] == "Setup Development"

    # Check breakdown tree
    assert "breakdowns" in data
    tree = data["breakdowns"]
    assert tree["goal_id"] == goal_id
    assert len(tree["root_nodes"]) == 2

    # Check first root node
    phase1 = tree["root_nodes"][0]
    assert phase1["title"] == "Phase 1"
    assert len(phase1["children"]) == 1
    assert phase1["children"][0]["title"] == "Install tools"


def test_get_goal_detail_not_found(client):
    """Test accessing non-existent goal returns 404"""
    student = create_student_user(client, 4)
    token = login_student(client, student["username"])
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/goals/99999", headers=headers)
    assert response.status_code == 404


def test_update_goal_persists_changes(client, monkeypatch):
    """Test updating goal metadata"""
    monkeypatch.setattr(
        chat_service,
        "build_goal_breakdown_response",
        lambda message: json.dumps({"breakdowns": []}),
    )

    student = create_student_user(client, 5)
    token = login_student(client, student["username"])
    headers = {"Authorization": f"Bearer {token}"}

    # Create goal
    create_response = client.post(
        "/goals",
        json={"title": "Original Title", "priority": "low"},
        headers=headers,
    )
    goal_id = create_response.json()["id"]

    # Update goal
    update_response = client.put(
        f"/goals/{goal_id}",
        json={"title": "Updated Title", "priority": "high", "status": "completed"},
        headers=headers,
    )
    assert update_response.status_code == 200

    data = update_response.json()
    assert data["title"] == "Updated Title"
    assert data["priority"] == "high"
    assert data["status"] == "completed"


def test_refresh_goal_breakdown_updates_tree(client, monkeypatch):
    """Test refreshing goal breakdown replaces old tree"""
    call_count = [0]

    def mock_breakdown_response(message):
        call_count[0] += 1
        if call_count[0] == 1:
            # First call - initial breakdown
            return json.dumps(
                {
                    "breakdowns": [
                        {"title": "Old Step 1", "description": None, "children": []},
                    ]
                }
            )
        else:
            # Second call - refreshed breakdown
            return json.dumps(
                {
                    "breakdowns": [
                        {"title": "New Step 1", "description": None, "children": []},
                        {"title": "New Step 2", "description": None, "children": []},
                    ]
                }
            )

    monkeypatch.setattr(
        chat_service,
        "build_goal_breakdown_response",
        mock_breakdown_response,
    )

    student = create_student_user(client, 6)
    token = login_student(client, student["username"])
    headers = {"Authorization": f"Bearer {token}"}

    # Create goal (gets first breakdown)
    create_response = client.post(
        "/goals",
        json={"title": "Test Refresh", "priority": "medium"},
        headers=headers,
    )
    goal_id = create_response.json()["id"]

    # Get initial detail
    detail1 = client.get(f"/goals/{goal_id}", headers=headers).json()
    assert len(detail1["breakdowns"]["root_nodes"]) == 1
    assert detail1["breakdowns"]["root_nodes"][0]["title"] == "Old Step 1"

    # Refresh breakdown
    refresh_response = client.post(
        f"/goals/{goal_id}/refresh-breakdown",
        headers=headers,
    )
    assert refresh_response.status_code == 202

    # Get updated detail
    detail2 = client.get(f"/goals/{goal_id}", headers=headers).json()
    assert len(detail2["breakdowns"]["root_nodes"]) == 2
    assert detail2["breakdowns"]["root_nodes"][0]["title"] == "New Step 1"
    assert detail2["breakdowns"]["root_nodes"][1]["title"] == "New Step 2"


def test_delete_goal_removes_goal_and_breakdowns(client, monkeypatch):
    """Test deleting goal cascades to breakdowns"""
    monkeypatch.setattr(
        chat_service,
        "build_goal_breakdown_response",
        lambda message: json.dumps(
            {
                "breakdowns": [
                    {"title": "Task 1", "description": None, "children": []},
                ]
            }
        ),
    )

    student = create_student_user(client, 7)
    token = login_student(client, student["username"])
    headers = {"Authorization": f"Bearer {token}"}

    # Create goal
    create_response = client.post(
        "/goals",
        json={"title": "Goal to Delete", "priority": "low"},
        headers=headers,
    )
    goal_id = create_response.json()["id"]

    # Verify exists
    response = client.get(f"/goals/{goal_id}", headers=headers)
    assert response.status_code == 200

    # Delete
    delete_response = client.delete(f"/goals/{goal_id}", headers=headers)
    assert delete_response.status_code == 204

    # Verify deleted
    response = client.get(f"/goals/{goal_id}", headers=headers)
    assert response.status_code == 404


def test_invalid_llm_output_handled_gracefully(client, monkeypatch):
    """Test handling of invalid JSON from LLM"""
    monkeypatch.setattr(
        chat_service,
        "build_goal_breakdown_response",
        lambda message: "This is not valid JSON at all!",
    )

    student = create_student_user(client, 8)
    token = login_student(client, student["username"])
    headers = {"Authorization": f"Bearer {token}"}

    # Create goal with invalid LLM response
    response = client.post(
        "/goals",
        json={"title": "Test Invalid Response", "priority": "medium"},
        headers=headers,
    )

    # Should still create the goal (202 Accepted for async processing)
    assert response.status_code == 201
    goal_id = response.json()["id"]

    # Get detail - should return empty breakdowns since parsing failed
    detail = client.get(f"/goals/{goal_id}", headers=headers).json()
    assert detail["breakdowns"]["root_nodes"] == []
