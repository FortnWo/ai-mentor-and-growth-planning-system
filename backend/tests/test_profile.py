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
            "username": f"20220254{index:02d}",
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


def login_student(client, username: str, password: str):
    response = client.post(
        "/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_profile_me_requires_auth(client):
    response = client.get("/profile/me")
    assert response.status_code == 401


def test_profile_me_read_update_and_password_change(client):
    student = create_student_user(client, 1)
    token = login_student(client, student["username"], "Student@12345")
    headers = {"Authorization": f"Bearer {token}"}

    profile_response = client.get("/profile/me", headers=headers)
    assert profile_response.status_code == 200
    assert profile_response.json()["username"] == student["username"]

    update_response = client.put(
        "/profile/me",
        json={
            "full_name": "Updated Profile Student",
            "major": "AI Engineering",
            "year_of_study": 2,
            "bio": "Updated bio",
        },
        headers=headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["full_name"] == "Updated Profile Student"
    assert update_response.json()["major"] == "AI Engineering"

    password_response = client.patch(
        "/profile/me/password",
        json={
            "current_password": "Student@12345",
            "new_password": "Student@54321",
        },
        headers=headers,
    )
    assert password_response.status_code == 200

    relogin_response = client.post(
        "/auth/login",
        json={"username": student["username"], "password": "Student@54321"},
    )
    assert relogin_response.status_code == 200
