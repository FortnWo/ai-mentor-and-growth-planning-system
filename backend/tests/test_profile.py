def make_user_payload(index: int = 1):
    return {
        "username": f"profile_user_{index}",
        "email": f"profile_user_{index}@example.com",
        "full_name": f"Profile User {index}",
        "major": "Computer Science",
        "year_of_study": 3,
        "bio": "Profile integration test user",
    }


def test_create_profile(client):
    payload = make_user_payload(1)
    response = client.post("/profile", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == payload["username"]
    assert data["email"] == payload["email"]


def test_get_profile(client):
    payload = make_user_payload(2)
    create_resp = client.post("/profile", json=payload)
    assert create_resp.status_code == 201
    user_id = create_resp.json()["id"]

    response = client.get(f"/profile/{user_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user_id
    assert data["email"] == payload["email"]


def test_update_profile(client):
    payload = make_user_payload(3)
    create_resp = client.post("/profile", json=payload)
    assert create_resp.status_code == 201
    user_id = create_resp.json()["id"]

    update_payload = {"bio": "Updated in MySQL test", "year_of_study": 4}
    update_resp = client.patch(f"/profile/{user_id}", json=update_payload)
    assert update_resp.status_code == 200
    updated_data = update_resp.json()
    assert updated_data["bio"] == update_payload["bio"]
    assert updated_data["year_of_study"] == update_payload["year_of_study"]


def test_create_profile_duplicate_email(client):
    payload = make_user_payload(4)
    response1 = client.post("/profile", json=payload)
    assert response1.status_code == 201

    duplicate_payload = make_user_payload(5)
    duplicate_payload["email"] = payload["email"]
    response2 = client.post("/profile", json=duplicate_payload)
    assert response2.status_code == 409


def test_get_profile_not_found(client):
    response = client.get("/profile/99999999")
    assert response.status_code == 404

