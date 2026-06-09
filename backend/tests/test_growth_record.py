import time

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

    list_resp = client.get("/growth-records", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) >= 1
    for item in items:
        rd = item.get("record_date")
        assert rd is None or isinstance(rd, str)


def test_action_plan_completion_writes_record(client, monkeypatch):
    student = create_student_user(client, 11)
    token = login_student(client, student["username"]) 
    headers = {"Authorization": f"Bearer {token}"}

    # create a goal with a single main pillar (one root node) mocked
    monkeypatch.setattr(
        chat_service,
        "build_goal_breakdown_response",
        lambda message: '{"breakdowns": [{"title": "Pillar 1", "description": "p1", "children": []}]}',
    )

    # mock action plan generation to return one completed item
    def mock_action_plan(_):
        return '{"plan": {"title": "Plan1", "summary": "s"}, "items": [{"title": "Done task", "description": "done", "status": "completed", "sequence": 1}]}'

    monkeypatch.setattr(chat_service, "build_action_plan_response", lambda message: mock_action_plan(message))

    create_goal = client.post("/goals", json={"title": "G1", "description": "desc"}, headers=headers)
    assert create_goal.status_code == 201
    goal_id = create_goal.json()["id"]

    resp = client.post("/action-plans", json={"goal_id": goal_id}, headers=headers)
    assert resp.status_code == 202
    plans = resp.json()
    assert isinstance(plans, list) and plans
    plan_id = plans[0]["id"]

    # poll for plan ready
    detail = None
    for _ in range(40):
        d = client.get(f"/action-plans/{plan_id}", headers=headers)
        if d.status_code == 200 and d.json().get("status") != "in_progress":
            detail = d.json()
            break
        time.sleep(0.05)

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


def test_daily_trend_merges_raw_when_aggregate_zero(client, db_session):
    """Trend API must reflect raw records even when daily aggregate row is all zeros."""
    from datetime import date

    from app.models.growth_aggregate import GrowthDailyAggregate

    student = create_student_user(client, 20)
    token = login_student(client, student["username"])
    headers = {"Authorization": f"Bearer {token}"}
    user_id = student["id"]

    payload = {
        "title": "Merge test",
        "summary": "x",
        "record_type": "manual",
        "idempotency_key": "merge-trend-zero-agg",
    }
    assert client.post("/growth-records", json=payload, headers=headers).status_code == 201

    today = date.today()
    agg = (
        db_session.query(GrowthDailyAggregate)
        .filter(GrowthDailyAggregate.user_id == user_id, GrowthDailyAggregate.record_date == today)
        .first()
    )
    if agg:
        agg.completed_count = 0
        agg.reflection_count = 0
        agg.milestone_count = 0
        agg.growth_score = 0
    else:
        db_session.add(
            GrowthDailyAggregate(
                user_id=user_id,
                record_date=today,
                completed_count=0,
                reflection_count=0,
                milestone_count=0,
                growth_score=0,
            )
        )
    db_session.commit()

    start = end = today.isoformat()
    trend = client.get(
        "/growth-records/trend/daily",
        params={"start_date": start, "end_date": end},
        headers=headers,
    )
    assert trend.status_code == 200
    assert trend.json()[0]["reflection_count"] >= 1

    stats = client.get(
        "/growth-records/stats",
        params={"start_date": start, "end_date": end},
        headers=headers,
    )
    assert stats.status_code == 200
    assert stats.json()["reflection_count"] >= 1


def test_daily_trend_uses_occurred_at_when_record_date_null(client, db_session):
    """Records with NULL record_date must still appear in trend/stats via occurred_at."""
    from datetime import date, datetime, timezone

    from app.models.growth_record import GrowthRecord, GrowthRecordSource, GrowthRecordType

    student = create_student_user(client, 21)
    token = login_student(client, student["username"])
    headers = {"Authorization": f"Bearer {token}"}
    user_id = student["id"]

    today = date.today()
    occurred = datetime(today.year, today.month, today.day, 12, 0, 0, tzinfo=timezone.utc)
    db_session.add(
        GrowthRecord(
            user_id=user_id,
            title="Legacy null record_date",
            summary="x",
            record_type=GrowthRecordType.MANUAL.value,
            source_type=GrowthRecordSource.MANUAL.value,
            occurred_at=occurred,
            record_date=None,
        )
    )
    db_session.commit()

    start = end = today.isoformat()
    trend = client.get(
        "/growth-records/trend/daily",
        params={"start_date": start, "end_date": end},
        headers=headers,
    )
    assert trend.status_code == 200
    assert trend.json()[0]["reflection_count"] >= 1

    stats = client.get(
        "/growth-records/stats",
        params={"start_date": start, "end_date": end},
        headers=headers,
    )
    assert stats.status_code == 200
    assert stats.json()["reflection_count"] >= 1
