import asyncio
import os
from pathlib import Path
import tempfile
from unittest.mock import patch
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.infrastructure.reference_paths import (
    validate_reference_image_paths,
    resolve_url_to_local_path,
)
from backend.app.domain.screenwriter import PolyaScreenwriterEngine


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as tc:
        yield tc


def test_reference_image_paths_validation_and_ordering():
    """Verify [background_path, char_face_path, char_front_path] order and omission of empty/missing files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create 2 valid dummy images and 1 empty image
        bg_file = Path(tmpdir) / "background.jpg"
        bg_file.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 100)

        face_file = Path(tmpdir) / "face.png"
        face_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 100)

        empty_front_file = Path(tmpdir) / "front_empty.jpg"
        empty_front_file.write_bytes(b"")  # 0 bytes

        non_existent_file = Path(tmpdir) / "missing.jpg"

        # 1. Test full canonical candidate list
        res = validate_reference_image_paths(
            background_path=str(bg_file),
            char_face_path=str(face_file),
            char_front_path=str(empty_front_file),
            additional_paths=[str(non_existent_file), None, ""],
        )

        assert len(res) == 2
        assert res[0] == str(bg_file.resolve())
        assert res[1] == str(face_file.resolve())

        # 2. Test when background is missing, order of remaining valid anchors is preserved
        res2 = validate_reference_image_paths(
            background_path=None,
            char_face_path=str(face_file),
            char_front_path=None,
        )
        assert len(res2) == 1
        assert res2[0] == str(face_file.resolve())


@pytest.mark.anyio
async def test_dialogue_calibrator_deterministic_fallback():
    """Verify fallback deterministik calculates unified word_count / 2.8 seconds on LLM timeout."""
    engine = PolyaScreenwriterEngine()
    # 14 words line -> 14 / 2.8 = 5.0 seconds (exact ceiling)
    dialogue_14_words = "One two three four five six seven eight nine ten eleven twelve thirteen fourteen"
    # 21 words line -> 21 / 2.8 = 7.5 seconds (exceeds 5.0s target)
    dialogue_21_words = (
        "Alpha beta gamma delta epsilon zeta eta theta iota kappa lambda "
        "mu nu xi omicron pi rho sigma tau upsilon phi"
    )

    with patch.object(engine, "_call_llm", side_effect=asyncio.TimeoutError("LLM simulated timeout")):
        res = await engine.calibrate_dialogue_pacing(
            dialogue_text=dialogue_14_words,
            max_seconds=5.0,
        )
        assert res["word_count"] == 14
        assert res["estimated_duration_seconds"] == 5.0
        assert res["passes_duration_limit"] is True
        assert res["source"] == "deterministic_fallback"
        assert res["max_seconds"] == 5.0

        res2 = await engine.calibrate_dialogue_pacing(
            dialogue_text=dialogue_21_words,
            max_seconds=5.0,
        )
        assert res2["word_count"] == 21
        assert res2["estimated_duration_seconds"] == 7.5
        assert res2["passes_duration_limit"] is False
        assert res2["source"] == "deterministic_fallback"
    assert res2["passes_duration_limit"] is False


@pytest.mark.anyio
async def test_director_polish_preview_generation():
    """Verify director polish provides non-destructive suggestions."""
    engine = PolyaScreenwriterEngine()
    polished = await engine.polish_scene_director_cut(
        scene_number=1,
        slugline="ROOFTOP - NIGHT",
        narrative_goal="Hero watches city below.",
        dialogue="It is time.",
    )

    assert "slugline" in polished
    assert "narrative_goal" in polished
    assert "dialogue" in polished
    assert "director_notes" in polished
    assert len(polished["director_notes"]) > 10


def test_shot_background_inheritance_and_reset(client, auth_headers):
    """Test shot auto-inherits scene preview background, can be overridden, and can be reset."""
    # 1. Create a project
    proj_resp = client.post(
        "/api/v1/projects",
        json={"title": "Test Inheritance Film", "aspect_ratio": "16:9", "total_scenes": 50},
        headers=auth_headers,
    )
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["data"]["id"]

    # 2. Create a scene
    scene_resp = client.post(
        f"/api/v1/projects/{proj_id}/scenes",
        json={"act_number": 1, "scene_number": 1, "slugline": "EXT. COURTYARD - DAY", "narrative_goal": "Opening shot", "duration_target": 10.0},
        headers=auth_headers,
    )
    assert scene_resp.status_code == 201
    scene_id = scene_resp.json()["data"]["id"]

    # 3. Create Shot 1 (Primary shot with preview_url)
    s1_resp = client.post(
        f"/api/v1/scenes/{scene_id}/shots",
        json={
            "shot_number": 1,
            "duration_seconds": 5.0,
            "fg_bg_layers": {"preview_url": "/api/v1/assets/previews/scene_preview_001.webp"},
        },
        headers=auth_headers,
    )
    assert s1_resp.status_code == 201
    shot1_id = s1_resp.json()["data"]["id"]

    # 4. Create Shot 2 without preview_url or custom_background
    s2_resp = client.post(
        f"/api/v1/scenes/{scene_id}/shots",
        json={"shot_number": 2, "duration_seconds": 5.0},
        headers=auth_headers,
    )
    assert s2_resp.status_code == 201
    shot2_id = s2_resp.json()["data"]["id"]

    # 5. List shots: Shot 2 must have background_source = 'inherited' with Shot 1's preview_url
    list_resp = client.get(f"/api/v1/scenes/{scene_id}/shots", headers=auth_headers)
    assert list_resp.status_code == 200
    shots_data = list_resp.json()["data"]
    assert len(shots_data) == 2
    sh2 = next(s for s in shots_data if s["id"] == shot2_id)
    assert sh2["background_source"] == "inherited"
    assert sh2["effective_background_url"] == "/api/v1/assets/previews/scene_preview_001.webp"

    # 6. Override Shot 2 with custom background
    override_resp = client.post(
        f"/api/v1/shots/{shot2_id}/custom-background",
        json={"custom_background": "/custom_shot2_bg.jpg"},
        headers=auth_headers,
    )
    assert override_resp.status_code == 200
    assert override_resp.json()["background_source"] == "custom"

    # Verify list shows custom
    list_resp2 = client.get(f"/api/v1/scenes/{scene_id}/shots", headers=auth_headers)
    sh2_updated = next(s for s in list_resp2.json()["data"] if s["id"] == shot2_id)
    assert sh2_updated["background_source"] == "custom"
    assert sh2_updated["effective_background_url"] == "/custom_shot2_bg.jpg"

    # 7. Reset override
    reset_resp = client.post(f"/api/v1/shots/{shot2_id}/reset-background", headers=auth_headers)
    assert reset_resp.status_code == 200
    assert reset_resp.json()["background_source"] == "inherited"

    # Verify list shows inherited again
    list_resp3 = client.get(f"/api/v1/scenes/{scene_id}/shots", headers=auth_headers)
    sh2_reverted = next(s for s in list_resp3.json()["data"] if s["id"] == shot2_id)
    assert sh2_reverted["background_source"] == "inherited"
    assert sh2_reverted["effective_background_url"] == "/api/v1/assets/previews/scene_preview_001.webp"


def test_director_polish_preview_endpoint(client, auth_headers):
    """Test /director-polish endpoint returns suggestions preview without overwriting scene."""
    proj_resp = client.post(
        "/api/v1/projects",
        json={"title": "Polish Test Project", "aspect_ratio": "16:9", "total_scenes": 50},
        headers=auth_headers,
    )
    proj_id = proj_resp.json()["data"]["id"]

    scene_resp = client.post(
        f"/api/v1/projects/{proj_id}/scenes",
        json={"act_number": 1, "scene_number": 1, "slugline": "BASEMENT - NIGHT", "narrative_goal": "Detectives search.", "duration_target": 5.0},
        headers=auth_headers,
    )
    scene_id = scene_resp.json()["data"]["id"]

    # Call /director-polish
    polish_resp = client.post(
        f"/api/v1/scenes/{scene_id}/director-polish",
        json={"style_code": "#Style 01"},
        headers=auth_headers,
    )
    assert polish_resp.status_code == 200
    body = polish_resp.json()
    assert body["status"] == "success"
    data = body["data"]
    assert "original" in data
    assert "suggestions" in data
    assert data["original"]["slugline"] == "BASEMENT - NIGHT"
    assert "director_notes" in data["suggestions"]

    # Verify database was NOT modified (non-destructive)
    check_scene = client.get(f"/api/v1/projects/{proj_id}/scenes", headers=auth_headers)
    sc = check_scene.json()["data"][0]
    assert sc["slugline"] == "BASEMENT - NIGHT"  # Not overwritten!

