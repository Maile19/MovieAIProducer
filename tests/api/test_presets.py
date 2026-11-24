import uuid
from fastapi.testclient import TestClient

from backend.app.domain.qc import QCEvaluationEngine
from backend.app.domain.transpiler import LivePromptTranspiler
from backend.app.infrastructure.database.models.auth import UserModel


def test_list_presets(client: TestClient, auth_headers: dict[str, str]):
    response = client.get("/api/v1/presets", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) >= 1
    # Check that seed preset exists
    slugs = [p["slug"] for p in data]
    assert "youtube-global-kids-comedy-non-verbal" in slugs

    seed = next(p for p in data if p["slug"] == "youtube-global-kids-comedy-non-verbal")
    assert seed["is_system"] is True
    assert seed["category"] == "kids_comedy"
    assert seed["preset_data"]["project_defaults"]["target_style_code"] == "#Style 10"


def test_create_and_get_preset(client: TestClient, auth_headers: dict[str, str]):
    payload = {
        "name": "Custom Sci-Fi Anime",
        "slug": "custom-scifi-anime",
        "description": "High-octane mecha anime",
        "category": "anime",
        "preset_data": {
            "project_defaults": {"aspect_ratio": "16:9", "target_style_code": "#Style 06"},
            "bible_blueprint": {"style_parameters": {"render_pipeline": "Cel-Shaded"}},
        },
    }
    create_resp = client.post("/api/v1/presets", json=payload, headers=auth_headers)
    assert create_resp.status_code == 201
    preset_id = create_resp.json()["data"]["id"]

    get_resp = client.get(f"/api/v1/presets/{preset_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    p_data = get_resp.json()["data"]
    assert p_data["name"] == "Custom Sci-Fi Anime"
    assert p_data["is_system"] is False


def test_system_preset_immutability(client: TestClient, auth_headers: dict[str, str]):
    # Find system preset
    list_resp = client.get("/api/v1/presets", headers=auth_headers)
    seed = next(p for p in list_resp.json()["data"] if p["is_system"])

    # Attempt PUT
    update_resp = client.put(
        f"/api/v1/presets/{seed['id']}",
        json={"name": "Hacked Preset"},
        headers=auth_headers,
    )
    assert update_resp.status_code == 400
    err_msg = update_resp.json().get("error", {}).get("message") or update_resp.json().get("detail", "")
    assert "System seed presets cannot be modified" in err_msg

    # Attempt DELETE
    del_resp = client.delete(f"/api/v1/presets/{seed['id']}", headers=auth_headers)
    assert del_resp.status_code == 400
    err_del = del_resp.json().get("error", {}).get("message") or del_resp.json().get("detail", "")
    assert "System seed presets cannot be deleted" in err_del


def test_create_project_with_preset(client: TestClient, auth_headers: dict[str, str]):
    payload = {
        "title": "Slapstick Adventure Ep 1",
        "preset_id": "youtube-global-kids-comedy-non-verbal",
    }
    resp = client.post("/api/v1/projects", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    p_data = resp.json()["data"]
    project_id = p_data["id"]

    # Target style should be #Style 10 from preset
    assert p_data["target_style_code"] == "#Style 10"
    assert p_data["aspect_ratio"] == "16:9"

    # Verify Bible received the preset's style_parameters and world_rules
    bible_resp = client.get(f"/api/v1/projects/{project_id}/bible", headers=auth_headers)
    assert bible_resp.status_code == 200
    b_data = bible_resp.json()["data"]
    assert b_data["style_parameters"]["master_style_code"] == "#Style 10"
    assert b_data["world_rules"]["visual_non_verbal_mode"]["enabled"] is True


def test_save_project_as_preset_and_apply(client: TestClient, auth_headers: dict[str, str]):
    # 1. Create base project
    proj_resp = client.post(
        "/api/v1/projects",
        json={"title": "Original Template Project", "target_style_code": "#Style 02"},
        headers=auth_headers,
    )
    assert proj_resp.status_code == 201
    source_project_id = proj_resp.json()["data"]["id"]

    # 2. Save as preset
    save_resp = client.post(
        f"/api/v1/projects/{source_project_id}/save-as-preset",
        json={
            "name": "Extracted Studio Preset",
            "category": "cinema",
            "description": "Extracted from Original Template",
        },
        headers=auth_headers,
    )
    assert save_resp.status_code == 201
    new_preset_id = save_resp.json()["data"]["id"]

    # 3. Create destination project
    dest_resp = client.post(
        "/api/v1/projects",
        json={"title": "Destination Project", "target_style_code": "#Style 01"},
        headers=auth_headers,
    )
    dest_project_id = dest_resp.json()["data"]["id"]

    # 4. Apply preset
    apply_resp = client.post(
        f"/api/v1/projects/{dest_project_id}/apply-preset",
        json={"preset_id": new_preset_id},
        headers=auth_headers,
    )
    assert apply_resp.status_code == 200
    assert apply_resp.json()["data"]["target_style_code"] == "#Style 02"


def test_apply_preset_locked_bible_conflict(client: TestClient, auth_headers: dict[str, str]):
    # Create project and lock its bible
    proj_resp = client.post(
        "/api/v1/projects",
        json={"title": "Locked Production"},
        headers=auth_headers,
    )
    project_id = proj_resp.json()["data"]["id"]

    # Lock Bible
    lock_resp = client.post(
        f"/api/v1/projects/{project_id}/bible/lock",
        json={"approval_notes": "DNA Freeze Active", "confirm_dna_freeze": True},
        headers=auth_headers,
    )
    assert lock_resp.status_code == 200

    # Attempt to apply preset -> Expect 409 Conflict
    apply_resp = client.post(
        f"/api/v1/projects/{project_id}/apply-preset",
        json={"preset_id": "youtube-global-kids-comedy-non-verbal"},
        headers=auth_headers,
    )
    assert apply_resp.status_code == 409
    conflict_msg = apply_resp.json().get("error", {}).get("message") or apply_resp.json().get("detail", "")
    assert "Master Production Bible is locked" in conflict_msg


def test_transpiler_non_verbal_mode():
    res = LivePromptTranspiler.transpile(
        provider_target="veo",
        style_code="#Style 10",
        camera_code="#Cam 19",
        lens_code="#Lens 02",
        comp_code="#Comp 01",
        light_code="#Light 02",
        speed_code="#Speed 03",
        is_non_verbal=True,
        preset_rules={
            "positive_prompt_modifiers": "DreamWorks Illumination aesthetic, punchy bounce light",
            "negative_prompt_additions": "spoken words, subtitles",
        },
    )
    assert "DreamWorks Illumination aesthetic" in res["positive_prompt"]
    assert "spoken words" in res["negative_prompt"]
    assert res["metadata"]["audio_bridge"]["non_verbal_mode"] is True
    assert res["metadata"]["audio_bridge"]["j_cut_offset_seconds"] == -1.2
    assert res["metadata"]["audio_bridge"]["l_cut_offset_seconds"] == 1.0


def test_qc_custom_thresholds():
    # Regular evaluation with marginal scores
    res_default = QCEvaluationEngine.evaluate(
        face_similarity=0.78,
        temporal_jitter=0.18,
    )
    # Under standard thresholds, face 0.78 is a warning, not critical defect
    assert len(res_default["critical_defects"]) == 0

    # Under Kids Comedy strict thresholds (face >= 0.82, jitter < 0.15)
    res_strict = QCEvaluationEngine.evaluate(
        face_similarity=0.70,
        temporal_jitter=0.28,
        custom_thresholds={
            "face_similarity": 0.82,
            "temporal_jitter": 0.15,
            "overall_score": 0.85,
        },
    )
    assert len(res_strict["critical_defects"]) > 0
    assert res_strict["passed"] is False


def test_seed_preset_cold_open_montage_structure(client: TestClient, auth_headers: dict[str, str]):
    """Verify seed preset contains cold_open_30s specifications."""
    list_resp = client.get("/api/v1/presets", headers=auth_headers)
    assert list_resp.status_code == 200
    data = list_resp.json()["data"]
    seed = next(p for p in data if p["slug"] == "youtube-global-kids-comedy-non-verbal")

    story_defs = seed["preset_data"]["storyboard_defaults"]
    assert "cold_open_30s" in story_defs
    co = story_defs["cold_open_30s"]
    assert co["enabled"] is True
    assert co["reserved_scenes"] == "01-03"
    assert co["duration_seconds"] == 30.0
    assert co["shots_count"] == 6

    struct = co["structure"]
    assert "In-Media-Res Shock Hook" in struct["scene_01"]["title"]
    assert "Fast Slapstick Chaos Tease" in struct["scene_02"]["title"]
    assert "Peak Climax Preview" in struct["scene_03"]["title"]


def test_cold_open_treatment_and_act_scenes_generation(client: TestClient, auth_headers: dict[str, str]):
    """Verify StagedStoryWriter generates Cold Open for Scenes 01-03 and Ordinary World at Scene 04."""
    # 1. Create project with Kids Comedy preset
    proj_resp = client.post(
        "/api/v1/projects",
        json={
            "title": "Bloop and Clack Comedy Episode 1",
            "preset_id": "youtube-global-kids-comedy-non-verbal",
        },
        headers=auth_headers,
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["data"]["id"]

    # 2. Generate Phase A treatment (50 scenes)
    treatment_resp = client.post(
        f"/api/v1/projects/{project_id}/blueprint/treatment",
        json={"total_scenes": 50, "duration_mode": "dynamic"},
        headers=auth_headers,
    )
    assert treatment_resp.status_code == 200
    treatment_data = treatment_resp.json()["data"]
    assert treatment_data.get("cold_open_30s", {}).get("enabled") is True
    act1_info = next(a for a in treatment_data["acts"] if a["act_number"] == 1)
    assert "Cold Open (Scenes 01-03)" in act1_info["dramatic_goal"]
    assert "Scene 04" in act1_info["dramatic_goal"]

    # 3. Generate Phase B Act 1 scenes (Scenes 01-12)
    act1_resp = client.post(
        f"/api/v1/projects/{project_id}/blueprint/generate-act",
        json={
            "act_number": 1,
            "total_scenes": 50,
            "duration_mode": "dynamic",
            "auto_split_shots": True,
        },
        headers=auth_headers,
    )
    assert act1_resp.status_code == 200
    assert act1_resp.json()["data"]["scenes_generated"] == 12

    # 4. Fetch created scenes
    scenes_resp = client.get(f"/api/v1/projects/{project_id}/scenes", headers=auth_headers)
    assert scenes_resp.status_code == 200
    scenes = scenes_resp.json()["data"]
    assert len(scenes) == 12

    sc1 = next(s for s in scenes if s["scene_number"] == 1)
    sc2 = next(s for s in scenes if s["scene_number"] == 2)
    sc3 = next(s for s in scenes if s["scene_number"] == 3)
    sc4 = next(s for s in scenes if s["scene_number"] == 4)

    # Verify Cold Open durations: 10s each = 30s total
    assert sc1["duration_target"] == 10.0
    assert sc2["duration_target"] == 10.0
    assert sc3["duration_target"] == 10.0
    # 2 shots each = 6 shots total across scenes 1 to 3
    assert sc1["shots_count"] == 2
    assert sc2["shots_count"] == 2
    assert sc3["shots_count"] == 2

    # Verify cold open narrative goals and sluglines
    assert "COLD OPEN" in sc1["slugline"]
    assert "In-Media-Res Shock Hook" in sc1["narrative_goal"]
    assert "COLD OPEN" in sc2["slugline"]
    assert "Fast Slapstick Chaos Tease" in sc2["narrative_goal"]
    assert "COLD OPEN" in sc3["slugline"]
    assert "Peak Climax Preview" in sc3["narrative_goal"]

    # Verify Scene 04 initiates the Linear Ordinary World
    assert "ORDINARY WORLD BEGINS" in sc4["slugline"]
    assert "Ordinary World" in sc4["narrative_goal"]

    # 5. Verify Cold Open shots have authentic camera codes and SFX
    shots_s1_resp = client.get(f"/api/v1/scenes/{sc1['id']}/shots", headers=auth_headers)
    assert shots_s1_resp.status_code == 200
    shots_s1 = shots_s1_resp.json()["data"]
    assert len(shots_s1) == 2
    assert shots_s1[0]["camera_code"] == "#Cam 19"  # Dolly-In hook
    assert shots_s1[1]["camera_code"] == "#Cam 23"  # 360 Orbital hook
    assert "[SFX:" in shots_s1[0]["dialogue"]

    shots_s2_resp = client.get(f"/api/v1/scenes/{sc2['id']}/shots", headers=auth_headers)
    assert shots_s2_resp.status_code == 200
    shots_s2 = shots_s2_resp.json()["data"]
    assert len(shots_s2) == 2
    assert shots_s2[0]["camera_code"] == "#Cam 25"  # Reaction camera
    assert "[SFX:" in shots_s2[0]["dialogue"]

    shots_s3_resp = client.get(f"/api/v1/scenes/{sc3['id']}/shots", headers=auth_headers)
    assert shots_s3_resp.status_code == 200
    shots_s3 = shots_s3_resp.json()["data"]
    assert len(shots_s3) == 2
    assert shots_s3[1]["transition_type"] == "L_CUT"
    assert "Tape Rewind" in shots_s3[1]["dialogue"]


def test_cold_open_instant_blueprint_creation(client: TestClient, auth_headers: dict[str, str]):
    """Verify legacy instant structural blueprint on POST /scenes is deprecated and returns 400 Bad Request."""
    proj_resp = client.post(
        "/api/v1/projects",
        json={
            "title": "Instant Blueprint Slapstick Show",
            "preset_id": "youtube-global-kids-comedy-non-verbal",
        },
        headers=auth_headers,
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["data"]["id"]

    bp_resp = client.post(
        f"/api/v1/projects/{project_id}/scenes",
        json={
            "generate_blueprint": True,
            "total_scenes": 50,
            "duration_mode": "dynamic",
            "auto_split_shots": True,
        },
        headers=auth_headers,
    )
    assert bp_resp.status_code == 400
    err_msg = bp_resp.json().get("error", {}).get("message", "") or bp_resp.text
    assert "deprecated" in err_msg.lower()

