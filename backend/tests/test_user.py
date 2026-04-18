def make_user_payload(index: int = 1):
    return {
        "username": f"user_{index}",
        "email": f"user_{index}@example.com",
        "full_name": f"Student {index}",
        "major": "Computer Science",
        "year_of_study": 2,
        "bio": "Testing user profile",
    }


def test_create_user(client):
    response = client.post("/users", json=make_user_payload(1))
    assert response.status_code == 201

    data = response.json()
    assert data["id"] > 0
    assert data["username"] == "user_1"
    assert data["email"] == "user_1@example.com"


def test_get_user_by_id(client):
    create_response = client.post("/users", json=make_user_payload(2))
    user_id = create_response.json()["id"]

    response = client.get(f"/users/{user_id}")
    assert response.status_code == 200
    assert response.json()["username"] == "user_2"


def test_update_user(client):
    create_response = client.post("/users", json=make_user_payload(3))
    user_id = create_response.json()["id"]

    response = client.put(
        f"/users/{user_id}",
        json={
            "full_name": "Updated Student",
            "year_of_study": 4,
            "bio": "Updated bio",
        },
    )
    assert response.status_code == 200

    data = response.json()
    assert data["full_name"] == "Updated Student"
    assert data["year_of_study"] == 4
    assert data["bio"] == "Updated bio"


def test_create_user_duplicate_email_conflict(client):
    first = make_user_payload(4)
    second = make_user_payload(5)
    second["email"] = first["email"]

    first_response = client.post("/users", json=first)
    second_response = client.post("/users", json=second)

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_delete_user(client):
    create_response = client.post("/users", json=make_user_payload(6))
    user_id = create_response.json()["id"]

    delete_response = client.delete(f"/users/{user_id}")
    assert delete_response.status_code == 204

    fetch_response = client.get(f"/users/{user_id}")
    assert fetch_response.status_code == 404
