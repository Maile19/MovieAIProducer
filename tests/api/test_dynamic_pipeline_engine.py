import uuid
from fastapi.testclient import TestClient

from backend.app.infrastructure.database.models.auth import UserModel


def test_new_empty_project_pipeline_status(client: TestClient, auth_headers: dict[str, str]):
    """Ensure a brand new empty project has 0 completed stages, current working stage = 1, and no fake green ticks."""
    resp = client.post("/api/v1/projects", json={"title": "Empty Horizon"}, headers=auth_headers)
    assert resp.status_code == 201
    project_id = resp.json()["data"]["id"]

    status_resp = client.get(f"/api/v1/projects/{project_id}/pipeline-status", headers=auth_headers)
    assert status_resp.status_code == 200
    pdata = status_resp.json()["data"]

    metrics = pdata["header_metrics"]
    assert metrics["completed_stages_count"] == 0
    assert metrics["current_working_stage"] == 1
    assert metrics["completed_steps_count"] == 0
    assert metrics["current_working_step"] == 1

    stages = pdata["stages"]
    # S01 is in_progress because title exists but premise/logline is not yet set
    assert stages["S01"]["status"] in ("in_progress", "not_started")
    assert stages["S01"]["is_current"] is True

    # S02 through S16 must be not_started
    for i in range(2, 17):
        key = f"S{i:02d}"
        assert stages[key]["status"] == "not_started"
        assert stages[key]["is_current"] is False


def test_non_linear_navigation_invariance(client: TestClient, auth_headers: dict[str, str]):
    """Ensure that non-linear UI navigation or setting operational_stage does not falsify other stages."""
    resp = client.post("/api/v1/projects", json={"title": "Non-Linear Journey"}, headers=auth_headers)
    project_id = resp.json()["data"]["id"]

    # Emulate user navigating or clicking Stage 8 in the frontend
    put_resp = client.put(
        f"/api/v1/projects/{project_id}",
        json={"operational_stage": 8},
        headers=auth_headers,
    )
    assert put_resp.status_code == 200

    # Fetch status: stages S01..S07 must NOT be falsely marked completed!
    status_resp = client.get(f"/api/v1/projects/{project_id}/pipeline-status", headers=auth_headers)
    assert status_resp.status_code == 200
    pdata = status_resp.json()["data"]

    assert pdata["header_metrics"]["completed_stages_count"] == 0
    stages = pdata["stages"]
    for i in range(2, 8):
        key = f"S{i:02d}"
        assert stages[key]["status"] == "not_started", f"Stage {key} was falsely marked as {stages[key]['status']}"


def test_gate_signoff_transitions_and_persistence(client: TestClient, auth_headers: dict[str, str]):
    """Test full transition: not_started/in_progress -> awaiting_gate -> completed -> revoked."""
    # 1. Create project with premise
    resp = client.post(
        "/api/v1/projects",
        json={
            "title": "Cyber City 2099",
            "aspect_ratio": "2.39:1",
            "target_style_code": "#Style 01",
            "settings": {"logline": "A rogue detective uncovers a digital conspiracy in Neo Jakarta."},
        },
        headers=auth_headers,
    )
    project_id = resp.json()["data"]["id"]

    # S01 has premise, so it should be awaiting_gate
    status_resp = client.get(f"/api/v1/projects/{project_id}/pipeline-status", headers=auth_headers)
    assert status_resp.json()["data"]["stages"]["S01"]["status"] == "awaiting_gate"

    # 2. Approve Gate S01
    signoff_resp = client.post(
        f"/api/v1/projects/{project_id}/gate-signoff",
        json={"stage": 1, "action": "APPROVE", "notes": "Premise approved by Showrunner"},
        headers=auth_headers,
    )
    assert signoff_resp.status_code == 200
    s_data = signoff_resp.json()["data"]
    assert s_data["stages"]["S01"]["status"] == "completed"
    assert s_data["stages"]["S01"]["gate_signoff"]["action"] == "APPROVE"
    assert s_data["header_metrics"]["completed_stages_count"] == 1
    assert s_data["header_metrics"]["current_working_stage"] == 2

    # 3. Verify persistence on GET /projects/{id}
    proj_get = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert proj_get.status_code == 200
    p_details = proj_get.json()["data"]
    assert p_details["pipeline_status"]["stages"]["S01"]["status"] == "completed"
    assert p_details["operational_stage"] == 2

    # 4. Revoke Gate S01 (Reopen for revision)
    revoke_resp = client.post(
        f"/api/v1/projects/{project_id}/gate-signoff",
        json={"stage": 1, "action": "REVOKE", "notes": "Logline needs more punch"},
        headers=auth_headers,
    )
    assert revoke_resp.status_code == 200
    r_data = revoke_resp.json()["data"]
    assert r_data["stages"]["S01"]["status"] == "awaiting_gate"
    assert r_data["header_metrics"]["completed_stages_count"] == 0
    assert r_data["header_metrics"]["current_working_stage"] == 1


def test_artifact_removal_invalidates_stale_signoff(client: TestClient, auth_headers: dict[str, str]):
    """Artifact-First Guard: Removing underlying artifacts drops status even if a signoff entry exists."""
    resp = client.post(
        "/api/v1/projects",
        json={
            "title": "Artifact Guard Film",
            "settings": {"logline": "Initial logline premise."},
        },
        headers=auth_headers,
    )
    project_id = resp.json()["data"]["id"]

    # Approve S01
    client.post(
        f"/api/v1/projects/{project_id}/gate-signoff",
        json={"stage": 1, "action": "APPROVE", "notes": "Approved"},
        headers=auth_headers,
    )
    status_resp = client.get(f"/api/v1/projects/{project_id}/pipeline-status", headers=auth_headers)
    assert status_resp.json()["data"]["stages"]["S01"]["status"] == "completed"

    # Now remove the premise artifact completely (e.g. user clears logline/premise)
    client.put(
        f"/api/v1/projects/{project_id}",
        json={"settings": {"logline": ""}},
        headers=auth_headers,
    )

    # Re-fetch pipeline status: S01 must NOT remain completed!
    status_resp2 = client.get(f"/api/v1/projects/{project_id}/pipeline-status", headers=auth_headers)
    s01_status = status_resp2.json()["data"]["stages"]["S01"]["status"]
    assert s01_status in ("in_progress", "not_started"), f"Expected in_progress or not_started but got {s01_status}"
    assert status_resp2.json()["data"]["header_metrics"]["completed_stages_count"] == 0


def test_sync_16_stages_and_12_steps(client: TestClient, auth_headers: dict[str, str]):
    """Verify that 12 Steps map deterministically from 16 Stages in the pipeline-status response."""
    resp = client.post(
        "/api/v1/projects",
        json={
            "title": "Matrix Sync Film",
            "aspect_ratio": "16:9",
            "target_style_code": "#Style 02",
            "settings": {"logline": "Epic 12-step validation."},
        },
        headers=auth_headers,
    )
    project_id = resp.json()["data"]["id"]

    status_resp = client.get(f"/api/v1/projects/{project_id}/pipeline-status", headers=auth_headers)
    data = status_resp.json()["data"]

    # Verify all 16 stages exist
    assert len(data["stages"]) == 16
    for i in range(1, 17):
        assert f"S{i:02d}" in data["stages"]

    # Verify all 12 steps exist
    assert len(data["steps"]) == 12
    for step_num in range(1, 13):
        code = f"STEP_{step_num:02d}"
        assert code in data["steps"]
        step = data["steps"][code]
        assert step["status"] in ("completed", "in_progress", "not_started")


def test_pipeline_endpoints_multi_tenant_authorization(
    client: TestClient,
    auth_headers: dict[str, str],
    secondary_auth_headers: dict[str, str],
):
    """Verify that User B cannot read pipeline status or sign off gates on User A's project."""
    # 1. User A creates a production
    resp = client.post(
        "/api/v1/projects",
        json={"title": "User A Pipeline Isolation Film", "settings": {"logline": "Confidential premise"}},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    proj_id = resp.json()["data"]["id"]

    # 2. User B tries GET /pipeline-status -> must 404 (verify_project_access protects read)
    b_status = client.get(f"/api/v1/projects/{proj_id}/pipeline-status", headers=secondary_auth_headers)
    assert b_status.status_code == 404

    # 3. User B tries POST /gate-signoff -> must 404 or 403 (verify_project_access protects mutation)
    b_gate = client.post(
        f"/api/v1/projects/{proj_id}/gate-signoff",
        json={"stage": 1, "action": "APPROVE", "notes": "Unauthorized approval attempt"},
        headers=secondary_auth_headers,
    )
    assert b_gate.status_code in (403, 404)

    # 4. User A can successfully read status and sign off gate
    a_status = client.get(f"/api/v1/projects/{proj_id}/pipeline-status", headers=auth_headers)
    assert a_status.status_code == 200
    a_gate = client.post(
        f"/api/v1/projects/{proj_id}/gate-signoff",
        json={"stage": 1, "action": "APPROVE", "notes": "Authorized showrunner signoff"},
        headers=auth_headers,
    )
    assert a_gate.status_code == 200
    assert a_gate.json()["data"]["stages"]["S01"]["status"] == "completed"
    # Ensure operational_stage was synced to stage 2 in projects list/details
    p_get = client.get(f"/api/v1/projects/{proj_id}", headers=auth_headers)
    assert p_get.status_code == 200
    assert p_get.json()["data"]["operational_stage"] == 2
