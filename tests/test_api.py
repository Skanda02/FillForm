from __future__ import annotations


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_get_profiles_empty(client):
    response = client.get("/api/profiles")
    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] == 0
    assert data["profiles"] == []


def test_create_and_get_profile(client, sample_profile_data):
    create_resp = client.post("/api/profiles", json=sample_profile_data)
    assert create_resp.status_code == 201
    created = create_resp.get_json()
    assert "id" in created
    assert created["name"] == "Test User"

    get_resp = client.get(f"/api/profiles/{created['id']}")
    assert get_resp.status_code == 200
    assert get_resp.get_json()["email"] == "test@example.com"


def test_get_profile_not_found(client):
    from bson import ObjectId

    fake_id = str(ObjectId())
    response = client.get(f"/api/profiles/{fake_id}")
    assert response.status_code == 404


def test_update_profile(client, sample_profile_data):
    create_resp = client.post("/api/profiles", json=sample_profile_data)
    profile_id = create_resp.get_json()["id"]

    update_resp = client.put(f"/api/profiles/{profile_id}", json={"name": "Updated Name"})
    assert update_resp.status_code == 200
    assert update_resp.get_json()["name"] == "Updated Name"


def test_delete_profile(client, sample_profile_data):
    create_resp = client.post("/api/profiles", json=sample_profile_data)
    profile_id = create_resp.get_json()["id"]

    delete_resp = client.delete(f"/api/profiles/{profile_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.get_json()["success"] is True

    get_resp = client.get(f"/api/profiles/{profile_id}")
    assert get_resp.status_code == 404


def test_get_default_profile(client, sample_profile_data):
    client.post("/api/profiles", json=sample_profile_data)
    response = client.get("/api/profiles/default")
    assert response.status_code == 200
    assert response.get_json()["name"] == "Test User"


def test_get_default_profile_not_found(client):
    response = client.get("/api/profiles/default")
    assert response.status_code == 404


def test_create_profile_no_data(client):
    response = client.post("/api/profiles", content_type="application/json")
    assert response.status_code == 400


def test_analyze_no_data(client):
    response = client.post("/api/analyze")
    assert response.status_code == 400


def test_check_eligibility_missing_params(client):
    response = client.post("/api/check-eligibility", json={"submission_id": 1})
    assert response.status_code == 400
    assert "required" in response.get_json()["error"]


def test_calendar_status(client):
    from bson import ObjectId

    fake_id = str(ObjectId())
    response = client.get(f"/api/calendar/status?profile_id={fake_id}")
    assert response.status_code == 200
    assert response.get_json()["connected"] is False


def test_calendar_status_no_profile_id(client):
    response = client.get("/api/calendar/status")
    assert response.status_code == 400


def test_auth_me_not_authenticated(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_auth_logout(client):
    response = client.post("/api/auth/logout")
    assert response.status_code == 200
    assert response.get_json()["success"] is True
