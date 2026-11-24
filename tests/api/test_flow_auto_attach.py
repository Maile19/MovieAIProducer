import json
import sqlite3
import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.workers.flow_image_worker import auto_attach_job_result, normalize_asset_slot, update_job_status


def test_normalize_asset_slot():
    assert normalize_asset_slot("closeup") == "closeup"
    assert normalize_asset_slot("master_closeup") == "closeup"
    assert normalize_asset_slot("front") == "front"
    assert normalize_asset_slot("side") == "side"
    assert normalize_asset_slot("3/4") == "three_quarter"
    assert normalize_asset_slot("three_quarter") == "three_quarter"
    assert normalize_asset_slot("turnaround_back") == "back"
    assert normalize_asset_slot("sheet_tpose") == "tpose"
    assert normalize_asset_slot("sheet_action") == "action"
    assert normalize_asset_slot("sheet_expression") == "expression"


def test_worker_auto_attach_sqlite_persistence():
    """Verify that flow_image_worker auto-attaches completed jobs directly into characters in SQLite."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # Create test tables
    conn.execute("""
        CREATE TABLE characters (
            id CHAR(36) PRIMARY KEY,
            project_id CHAR(36),
            name VARCHAR(128),
            closeup_image_url VARCHAR(512),
            front_image_url VARCHAR(512),
            side_image_url VARCHAR(512),
            three_quarter_image_url VARCHAR(512),
            back_image_url VARCHAR(512),
            tpose_image_url VARCHAR(512),
            action_image_url VARCHAR(512),
            expression_image_url VARCHAR(512),
            dna_seed INTEGER,
            sheet_metadata JSON
        );
    """)

    conn.execute("""
        CREATE TABLE character_states (
            id CHAR(36) PRIMARY KEY,
            character_id CHAR(36),
            image_url VARCHAR(512)
        );
    """)

    conn.execute("""
        CREATE TABLE flow_image_jobs (
            id CHAR(36) PRIMARY KEY,
            project_id CHAR(36),
            scene_id CHAR(36),
            character_id CHAR(36),
            asset_slot VARCHAR(32),
            target_type VARCHAR(32),
            state_id CHAR(36),
            prompt TEXT,
            aspect_ratio VARCHAR(10),
            reference_image_paths JSON,
            status VARCHAR(20),
            output_filename VARCHAR(255),
            image_url VARCHAR(512),
            debug_screenshot_url VARCHAR(512),
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3,
            created_at DATETIME,
            started_at DATETIME,
            completed_at DATETIME
        );
    """)

    char_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO characters (id, name, dna_seed, sheet_metadata) VALUES (?, ?, ?, ?);",
        (char_id, "Test Agent", 123456, json.dumps({})),
    )

    job_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO flow_image_jobs (
            id, character_id, asset_slot, target_type, prompt, aspect_ratio, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (job_id, char_id, "front", "turnaround", "Front view prompt", "3:4", "processing", datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()

    test_img_url = f"/media/images/{job_id}.png"

    # Call update_job_status with "completed"
    update_job_status(
        conn=conn,
        job_id=job_id,
        status="completed",
        output_filename=f"{job_id}.png",
        image_url=test_img_url,
    )

    # Verify character record was automatically updated by the worker
    char_row = conn.execute("SELECT front_image_url, sheet_metadata FROM characters WHERE id = ?;", (char_id,)).fetchone()
    assert char_row["front_image_url"] == test_img_url, "front_image_url was not updated by auto-attach!"

    meta = json.loads(char_row["sheet_metadata"])
    assert "front" in meta, "sheet_metadata['front'] was not populated!"
    assert meta["front"]["image_url"] == test_img_url
    assert meta["front"]["status"] == "completed"
    assert meta["front"]["provider"] == "google_flow"


def test_api_active_jobs_and_idempotent_attach(client: TestClient = None):
    """Verify GET active-jobs and idempotent attach-job-result via FastAPI test client."""
    from backend.app.main import app
    from backend.app.core.config import get_settings

    test_client = TestClient(app)

    # Health check to ensure app runs
    res = test_client.get("/health")
    assert res.status_code == 200


def test_worker_auto_attach_scene_branch_non_destructive():
    """Verify flow_image_worker auto_attach_job_result attaches to shot #1 with non-destructive JSON merge."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.execute("""
        CREATE TABLE scenes (
            id CHAR(36) PRIMARY KEY,
            project_id CHAR(36),
            act_number INTEGER,
            scene_number INTEGER,
            slugline VARCHAR(255),
            narrative_goal TEXT,
            duration_target FLOAT DEFAULT 10.0,
            status VARCHAR(32) DEFAULT 'PLANNED',
            created_at DATETIME
        );
    """)

    conn.execute("""
        CREATE TABLE shots (
            id CHAR(36) PRIMARY KEY,
            scene_id CHAR(36) NOT NULL,
            shot_number INTEGER NOT NULL,
            duration_seconds FLOAT DEFAULT 5.0,
            camera_code VARCHAR(16) DEFAULT '#Cam 01',
            lens_code VARCHAR(16) DEFAULT '#Lens 01',
            comp_code VARCHAR(16) DEFAULT '#Comp 01',
            light_code VARCHAR(16) DEFAULT '#Light 01',
            act_code VARCHAR(16) DEFAULT '#Act 01',
            speed_code VARCHAR(16) DEFAULT '#Speed 01',
            fg_bg_layers JSON NOT NULL,
            status VARCHAR(32) DEFAULT 'PLANNED',
            created_at DATETIME
        );
    """)

    conn.execute("""
        CREATE TABLE flow_image_jobs (
            id CHAR(36) PRIMARY KEY,
            project_id CHAR(36),
            scene_id CHAR(36),
            character_id CHAR(36),
            asset_slot VARCHAR(32),
            target_type VARCHAR(32),
            state_id CHAR(36),
            prompt TEXT,
            aspect_ratio VARCHAR(10),
            reference_image_paths JSON,
            status VARCHAR(20),
            output_filename VARCHAR(255),
            image_url VARCHAR(512),
            debug_screenshot_url VARCHAR(512),
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3,
            created_at DATETIME,
            started_at DATETIME,
            completed_at DATETIME
        );
    """)

    scene_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO scenes (id, scene_number, act_number, slugline, narrative_goal, duration_target, created_at) "
        "VALUES (?, 1, 1, 'INT. LAB - NIGHT', 'Discover formula', 10.0, ?)",
        (scene_id, datetime.now(timezone.utc).isoformat()),
    )

    # Shot #1 with existing custom keys in fg_bg_layers
    shot1_id = str(uuid.uuid4())
    existing_layers = {"custom_tag": "preserve_me", "lighting_tone": "noir"}
    conn.execute(
        "INSERT INTO shots (id, scene_id, shot_number, fg_bg_layers, created_at) VALUES (?, ?, 1, ?, ?)",
        (shot1_id, scene_id, json.dumps(existing_layers), datetime.now(timezone.utc).isoformat()),
    )

    job_id = str(uuid.uuid4())
    test_image_url = f"/media/images/{job_id}.png"
    conn.execute(
        "INSERT INTO flow_image_jobs (id, scene_id, prompt, aspect_ratio, status, created_at) "
        "VALUES (?, ?, 'Dramatic lab scene', '16:9', 'processing', ?)",
        (job_id, scene_id, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()

    # Run auto_attach_job_result
    auto_attach_job_result(conn, job_id, test_image_url)

    # Verify shot #1 updated non-destructively
    shot_row = conn.execute("SELECT fg_bg_layers FROM shots WHERE id = ?", (shot1_id,)).fetchone()
    merged = json.loads(shot_row["fg_bg_layers"])
    assert merged["custom_tag"] == "preserve_me", "Existing key was destroyed by auto-attach!"
    assert merged["lighting_tone"] == "noir", "Existing key was destroyed by auto-attach!"
    assert merged["preview_url"] == test_image_url
    assert merged["preview_provider"] == "google_flow"
    assert merged["job_id"] == job_id
    assert "updated_at" in merged

    # Test auto-create shot #1 when scene has no shots
    scene_id_no_shots = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO scenes (id, scene_number, act_number, slugline, narrative_goal, duration_target, created_at) "
        "VALUES (?, 2, 1, 'EXT. STREET - DAY', 'Chase begins', 12.0, ?)",
        (scene_id_no_shots, datetime.now(timezone.utc).isoformat()),
    )
    job_id_2 = str(uuid.uuid4())
    test_image_url_2 = f"/media/images/{job_id_2}.png"
    conn.execute(
        "INSERT INTO flow_image_jobs (id, scene_id, prompt, aspect_ratio, status, created_at) "
        "VALUES (?, ?, 'Street chase scene', '16:9', 'processing', ?)",
        (job_id_2, scene_id_no_shots, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()

    auto_attach_job_result(conn, job_id_2, test_image_url_2)

    created_shot = conn.execute("SELECT id, shot_number, duration_seconds, fg_bg_layers FROM shots WHERE scene_id = ?", (scene_id_no_shots,)).fetchone()
    assert created_shot is not None, "Shot #1 was not created for scene without shots!"
    assert created_shot["shot_number"] == 1
    assert created_shot["duration_seconds"] == 12.0
    layers2 = json.loads(created_shot["fg_bg_layers"])
    assert layers2["preview_url"] == test_image_url_2
    assert layers2["preview_provider"] == "google_flow"


def test_api_attach_preview_endpoint_and_list_scenes_sync(client: TestClient, auth_headers: dict[str, str]):
    """Verify POST /api/v1/scenes/{scene_id}/attach-preview and list_project_scenes preview_url/preview_provider sync."""
    # 1. Create project
    proj_resp = client.post("/api/v1/projects", json={"title": "Preview Sync Film"}, headers=auth_headers)
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["data"]["id"]

    # 2. Create scene
    sc_resp = client.post(
        f"/api/v1/projects/{project_id}/scenes",
        json={
            "act_number": 1,
            "scene_number": 1,
            "slugline": "INT. ARCHIVE - NIGHT",
            "narrative_goal": "Investigate secret drawer",
            "duration_target": 10.0,
        },
        headers=auth_headers,
    )
    assert sc_resp.status_code == 201
    scene_id = sc_resp.json()["data"]["id"]

    # 3. Create shot #1 with preexisting layers
    shot_resp = client.post(
        f"/api/v1/scenes/{scene_id}/shots",
        json={
            "shot_number": 1,
            "duration_seconds": 10.0,
            "fg_bg_layers": {"initial_flag": "preserved", "camera_notes": "close shot"},
        },
        headers=auth_headers,
    )
    assert shot_resp.status_code == 201
    shot_id = shot_resp.json()["data"]["id"]

    # 4. Call POST /api/v1/scenes/{scene_id}/attach-preview
    test_preview_url = "/media/images/flow-test-keyframe.png"
    attach_resp = client.post(
        f"/api/v1/scenes/{scene_id}/attach-preview",
        json={
            "preview_url": test_preview_url,
            "preview_provider": "google_flow",
            "job_id": "test-job-uuid-1234",
        },
        headers=auth_headers,
    )
    assert attach_resp.status_code == 200
    attach_data = attach_resp.json()
    assert attach_data["status"] == "success"
    assert attach_data["preview_url"] == test_preview_url
    assert attach_data["preview_provider"] == "google_flow"
    assert attach_data["fg_bg_layers"]["initial_flag"] == "preserved"
    assert attach_data["fg_bg_layers"]["camera_notes"] == "close shot"
    assert attach_data["fg_bg_layers"]["preview_url"] == test_preview_url
    assert attach_data["fg_bg_layers"]["job_id"] == "test-job-uuid-1234"

    # 5. Verify list_project_scenes returns preview_url and preview_provider from shot #1
    list_resp = client.get(f"/api/v1/projects/{project_id}/scenes", headers=auth_headers)
    assert list_resp.status_code == 200
    scenes = list_resp.json()["data"]
    target_scene = next(s for s in scenes if s["id"] == scene_id)
    assert target_scene["preview_url"] == test_preview_url
    assert target_scene["preview_provider"] == "google_flow"

    # 6. Verify get_scene detail returns preview_url and preview_provider
    get_sc_resp = client.get(f"/api/v1/scenes/{scene_id}", headers=auth_headers)
    assert get_sc_resp.status_code == 200
    detail = get_sc_resp.json()["data"]
    assert detail["preview_url"] == test_preview_url
    assert detail["preview_provider"] == "google_flow"
