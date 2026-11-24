from fastapi.testclient import TestClient

from backend.app.infrastructure.database.models.auth import UserModel


def test_list_projects_unauthorized(client: TestClient):
    client.cookies.clear()
    response = client.get("/api/v1/projects")
    assert response.status_code == 401


def test_create_and_get_project(client: TestClient, auth_headers: dict[str, str], test_user: UserModel):
    payload = {
        "title": "Nusantara 2099",
        "aspect_ratio": "16:9",
        "target_style_code": "#Style 08",
        "settings": {"tone": "cyberpunk noir"},
    }
    create_resp = client.post("/api/v1/projects", json=payload, headers=auth_headers)
    assert create_resp.status_code == 201
    data = create_resp.json()["data"]
    project_id = data["id"]
    assert data["title"] == "Nusantara 2099"
    assert data["target_style_code"] == "#Style 08"
    assert data["operational_stage"] == 1
    assert data["owner_id"] == str(test_user.id)

    # Get details
    get_resp = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    p_data = get_resp.json()["data"]
    assert p_data["id"] == project_id
    assert p_data["stats"]["bible_version"] == 1
    assert p_data["stats"]["bible_locked"] is False


def test_update_project(client: TestClient, auth_headers: dict[str, str]):
    # Create project first
    create_resp = client.post("/api/v1/projects", json={"title": "Project Alpha"}, headers=auth_headers)
    project_id = create_resp.json()["data"]["id"]

    # Update
    update_payload = {
        "title": "Project Alpha Remastered",
        "aspect_ratio": "9:16",
        "target_style_code": "#Style 02",
        "status": "IN_PRODUCTION",
    }
    update_resp = client.put(f"/api/v1/projects/{project_id}", json=update_payload, headers=auth_headers)
    assert update_resp.status_code == 200
    u_data = update_resp.json()["data"]
    assert u_data["title"] == "Project Alpha Remastered"
    assert u_data["aspect_ratio"] == "9:16"
    assert u_data["target_style_code"] == "#Style 02"
    assert u_data["status"] == "IN_PRODUCTION"


def test_advance_project_stage(client: TestClient, auth_headers: dict[str, str]):
    create_resp = client.post("/api/v1/projects", json={"title": "Stage Advance Test"}, headers=auth_headers)
    project_id = create_resp.json()["data"]["id"]
    assert create_resp.json()["data"]["operational_stage"] == 1

    advance_resp = client.post(f"/api/v1/projects/{project_id}/advance-stage", headers=auth_headers)
    assert advance_resp.status_code == 200
    adv_data = advance_resp.json()["data"]
    assert adv_data["operational_stage"] == 2
    assert "Visual Style" in adv_data["stage_name"]


def test_stage_gate_actions(client: TestClient, auth_headers: dict[str, str]):
    create_resp = client.post("/api/v1/projects", json={"title": "Gate Test Film"}, headers=auth_headers)
    project_id = create_resp.json()["data"]["id"]

    # 1. Action: REVISE
    revise_resp = client.post(
        f"/api/v1/projects/{project_id}/gate",
        json={"action": "REVISE", "notes": "Fix script pacing in Act I"},
        headers=auth_headers,
    )
    assert revise_resp.status_code == 200
    assert revise_resp.json()["data"]["status"] == "REVISION"

    # 2. Action: APPROVE
    approve_resp = client.post(
        f"/api/v1/projects/{project_id}/gate",
        json={"action": "APPROVE", "notes": "Approved for 50 scene storyboard", "target_stage": 3},
        headers=auth_headers,
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["data"]["operational_stage"] == 3
    assert approve_resp.json()["data"]["status"] == "IN_PRODUCTION"

    # 3. Action: LOCK
    lock_resp = client.post(
        f"/api/v1/projects/{project_id}/gate",
        json={"action": "LOCK", "notes": "Lock milestone baseline"},
        headers=auth_headers,
    )
    assert lock_resp.status_code == 200
    assert lock_resp.json()["data"]["status"] == "LOCKED"


def test_delete_project(client: TestClient, auth_headers: dict[str, str]):
    create_resp = client.post("/api/v1/projects", json={"title": "To Delete"}, headers=auth_headers)
    project_id = create_resp.json()["data"]["id"]

    del_resp = client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert del_resp.status_code == 200

    # Ensure not found
    get_resp = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_user_isolation_between_accounts(
    client: TestClient,
    auth_headers: dict[str, str],
    secondary_auth_headers: dict[str, str],
):
    """Verify strict multi-tenant isolation: User B cannot see, access, or delete User A's projects."""
    # 1. User A creates a production
    create_resp = client.post(
        "/api/v1/projects",
        json={"title": "User A Top Secret Film", "aspect_ratio": "16:9"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    user_a_proj_id = create_resp.json()["data"]["id"]

    # 2. User B lists projects — User A's project must NOT appear in User B's slate
    list_b_resp = client.get("/api/v1/projects", headers=secondary_auth_headers)
    assert list_b_resp.status_code == 200
    user_b_projects = list_b_resp.json()["data"]
    user_b_ids = [p["id"] for p in user_b_projects]
    assert user_a_proj_id not in user_b_ids

    # 3. User B attempts GET on User A's project -> must be rejected (404)
    get_b_resp = client.get(f"/api/v1/projects/{user_a_proj_id}", headers=secondary_auth_headers)
    assert get_b_resp.status_code == 404

    # 4. User B attempts DELETE on User A's project -> must be rejected (404 or 403)
    del_b_resp = client.delete(f"/api/v1/projects/{user_a_proj_id}", headers=secondary_auth_headers)
    assert del_b_resp.status_code in (403, 404)

    # 5. User B attempts advance-stage on User A's project -> must be rejected
    adv_b_resp = client.post(
        f"/api/v1/projects/{user_a_proj_id}/advance-stage",
        headers=secondary_auth_headers,
    )
    assert adv_b_resp.status_code in (403, 404)

    # 6. User A can still successfully access and delete their own project
    del_a_resp = client.delete(f"/api/v1/projects/{user_a_proj_id}", headers=auth_headers)
    assert del_a_resp.status_code == 200
