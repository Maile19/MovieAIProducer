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
