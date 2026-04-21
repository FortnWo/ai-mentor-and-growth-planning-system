from datetime import datetime, timedelta, timezone


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


def make_student_payload(index: int = 1):
    return {
        "username": f"20220253{index:02d}",
        "email": f"student_{index}@example.com",
        "password": "Student@12345",
        "full_name": f"Student {index}",
        "major": "Computer Science",
        "year_of_study": 2,
        "bio": "Testing user profile",
        "role": "user",
    }


def test_admin_login_and_me(client):
    token = login_admin(client)
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["username"] == ADMIN_USERNAME
    assert response.json()["role"] == "admin"


def test_admin_can_create_student_user(client):
    response = client.post(
        "/admin/users",
        json=make_student_payload(1),
        headers=admin_headers(client),
    )
    assert response.status_code == 201

    data = response.json()
    assert data["id"] > 0
    assert data["username"] == "2022025301"
    assert data["email"] == "student_1@example.com"
    assert data["role"] == "user"


def test_student_username_must_be_ten_digits(client):
    payload = make_student_payload(2)
    payload["username"] = "student_2"

    response = client.post(
        "/admin/users",
        json=payload,
        headers=admin_headers(client),
    )
    assert response.status_code == 422


def test_admin_can_grant_and_revoke_admin_access(client):
    create_response = client.post(
        "/admin/users",
        json=make_student_payload(3),
        headers=admin_headers(client),
    )
    user_id = create_response.json()["id"]

    grant_response = client.patch(
        f"/admin/users/{user_id}/admin-access",
        json={
            "permission_level": "limited",
            "permissions": ["user.read"],
            "expires_at": (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)).isoformat(),
        },
        headers=admin_headers(client),
    )
    assert grant_response.status_code == 200
    assert grant_response.json()["role"] == "admin"
    assert grant_response.json()["admin_permissions"] == ["user.read"]

    student_login = client.post(
        "/auth/login",
        json={"username": "2022025303", "password": "Student@12345"},
    )
    assert student_login.status_code == 200
    student_token = student_login.json()["access_token"]

    list_response = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert list_response.status_code == 200

    revoke_response = client.delete(
        f"/admin/users/{user_id}/admin-access",
        headers=admin_headers(client),
    )
    assert revoke_response.status_code == 200
    assert revoke_response.json()["role"] == "user"

    denied_response = client.get(
        "/admin/users",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert denied_response.status_code == 403


def test_admin_can_update_and_delete_user(client):
    create_response = client.post(
        "/admin/users",
        json=make_student_payload(4),
        headers=admin_headers(client),
    )
    user_id = create_response.json()["id"]

    update_response = client.put(
        f"/admin/users/{user_id}",
        json={
            "full_name": "Updated Student",
            "year_of_study": 4,
            "bio": "Updated bio",
        },
        headers=admin_headers(client),
    )
    assert update_response.status_code == 200
    assert update_response.json()["full_name"] == "Updated Student"
    assert update_response.json()["year_of_study"] == 4

    delete_response = client.delete(f"/admin/users/{user_id}", headers=admin_headers(client))
    assert delete_response.status_code == 204

    fetch_response = client.get(f"/admin/users/{user_id}", headers=admin_headers(client))
    assert fetch_response.status_code == 404
