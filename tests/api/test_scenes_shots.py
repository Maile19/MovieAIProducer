from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app.domain.screenwriter import PolyaScreenwriterEngine


def test_50_scene_blueprint_generation_and_filtering(client: TestClient, auth_headers: dict[str, str]):
    # 1. Create project
    create_p = client.post("/api/v1/projects", json={"title": "Epic Cyberpunk Saga"}, headers=auth_headers)
    project_id = create_p.json()["data"]["id"]

    # 2. Verify legacy instant blueprint is deprecated -> returns 400
    blueprint_resp = client.post(
        f"/api/v1/projects/{project_id}/scenes",
        json={"generate_blueprint": True},
        headers=auth_headers,
    )
    assert blueprint_resp.status_code == 400
    err_msg = blueprint_resp.json().get("error", {}).get("message", "") or blueprint_resp.text
    assert "deprecated" in err_msg.lower()

    # 3. Seed 50 scenes via CRUD
    for i in range(1, 51):
        act = 1 if i <= 12 else (2 if i <= 25 else (3 if i <= 38 else 4))
        client.post(
            f"/api/v1/projects/{project_id}/scenes",
            json={
                "act_number": act,
                "scene_number": i,
                "slugline": f"EXT. SECTOR {i} - NIGHT",
                "narrative_goal": f"Beat {i}",
                "duration_target": 15.0 if act % 2 == 1 else 10.0,
            },
            headers=auth_headers,
        )

    # 4. List all scenes
    all_scenes_resp = client.get(f"/api/v1/projects/{project_id}/scenes", headers=auth_headers)
    assert all_scenes_resp.status_code == 200
    scenes = all_scenes_resp.json()["data"]
    assert len(scenes) == 50
    assert scenes[0]["scene_number"] == 1
    assert scenes[0]["act_number"] == 1
    assert scenes[49]["scene_number"] == 50
    assert scenes[49]["act_number"] == 4

    # 5. Filter by Act 1 (Scenes 1-12)
    act1_resp = client.get(f"/api/v1/projects/{project_id}/scenes?act=1", headers=auth_headers)
    assert act1_resp.status_code == 200
    act1_scenes = act1_resp.json()["data"]
    assert len(act1_scenes) == 12

    # 6. Filter by Act 2 (Scenes 13-25)
    act2_resp = client.get(f"/api/v1/projects/{project_id}/scenes?act=2", headers=auth_headers)
    assert act2_resp.status_code == 200
    assert len(act2_resp.json()["data"]) == 13


def test_scene_crud_and_dialogue_calibration(client: TestClient, auth_headers: dict[str, str]):
    create_p = client.post("/api/v1/projects", json={"title": "Scene CRUD Film"}, headers=auth_headers)
    project_id = create_p.json()["data"]["id"]

    # 1. Create single scene
    scene_payload = {
        "act_number": 1,
        "scene_number": 1,
        "slugline": "EXT. NEO JAKARTA - NIGHT",
        "narrative_goal": "Introduce dystopian street atmosphere and Arya's arrival",
        "duration_target": 5.0,
    }
    sc_resp = client.post(f"/api/v1/projects/{project_id}/scenes", json=scene_payload, headers=auth_headers)
    assert sc_resp.status_code == 201
    scene_id = sc_resp.json()["data"]["id"]

    # 2. Get scene
    get_sc = client.get(f"/api/v1/scenes/{scene_id}", headers=auth_headers)
    assert get_sc.status_code == 200
    assert get_sc.json()["data"]["slugline"] == "EXT. NEO JAKARTA - NIGHT"

    # 3. Update scene
    put_sc = client.put(
        f"/api/v1/scenes/{scene_id}",
        json={"slugline": "EXT. NEO JAKARTA - DUSK", "status": "APPROVED"},
        headers=auth_headers,
    )
    assert put_sc.status_code == 200
    assert put_sc.json()["data"]["slugline"] == "EXT. NEO JAKARTA - DUSK"
    assert put_sc.json()["data"]["status"] == "APPROVED"

    # 4. Dialogue Calibration (within 5s limit)
    calib_payload = {
        "raw_text": "Sistem keamanan distrik sudah padam, kita harus bergerak sekarang.",
        "character_name": "Arya",
        "max_seconds": 5.0,
    }
    calib_resp = client.post(f"/api/v1/scenes/{scene_id}/calibrate-dialogue", json=calib_payload, headers=auth_headers)
    assert calib_resp.status_code == 200
    cal_data = calib_resp.json()["data"]
    assert cal_data["word_count"] == 9
    assert cal_data["passes_5s_limit"] is True
    assert cal_data["passes_duration_limit"] is True
    assert cal_data["max_allowed_words"] == 14
    assert cal_data["transition_type"] in ("J_CUT", "L_CUT", "HARD_CUT")

    # 4b. Deterministic override: even if live LLM returns bogus word_count, spoken-word math wins
    async def bogus_llm(*args, **kwargs):
        return {
            "word_count": 99,
            "syllable_count": 200,
            "estimated_duration_seconds": 40.0,
            "passes_duration_limit": False,
            "transition_type": "J_CUT",
            "audio_lead_seconds": 1.0,
            "analysis": "LLM qualitative feedback preserved.",
            "trimmed_suggestion": None,
        }

    with patch.object(PolyaScreenwriterEngine, "_call_llm", side_effect=bogus_llm):
        ov_resp = client.post(
            f"/api/v1/scenes/{scene_id}/calibrate-dialogue",
            json={"raw_text": "[NON-VERBAL] Hold the gate shut now.", "max_seconds": 5.0},
            headers=auth_headers,
        )
    assert ov_resp.status_code == 200
    ov_data = ov_resp.json()["data"]
    assert ov_data["word_count"] == 5
    assert ov_data["passes_duration_limit"] is True
    assert ov_data["passes_5s_limit"] is True
    assert ov_data["analysis"] == "LLM qualitative feedback preserved."

    # 4c. Scene dialogue persistence & exposure in GET /scenes/{id} and GET /projects/{id}/scenes
    put_dlg = client.put(
        f"/api/v1/scenes/{scene_id}",
        json={"dialogue": "Hold the gate shut now."},
        headers=auth_headers,
    )
    assert put_dlg.status_code == 200
    assert put_dlg.json()["data"]["dialogue"] == "Hold the gate shut now."
    assert client.get(f"/api/v1/scenes/{scene_id}", headers=auth_headers).json()["data"]["dialogue"] == "Hold the gate shut now."
    listed = client.get(f"/api/v1/projects/{project_id}/scenes", headers=auth_headers).json()["data"]
    assert any(item["id"] == scene_id and item["dialogue"] == "Hold the gate shut now." for item in listed)

    # 5. Delete scene
    del_sc = client.delete(f"/api/v1/scenes/{scene_id}", headers=auth_headers)
    assert del_sc.status_code == 200
    assert client.get(f"/api/v1/scenes/{scene_id}", headers=auth_headers).status_code == 404


def test_shots_crud_lifecycle(client: TestClient, auth_headers: dict[str, str]):
    create_p = client.post("/api/v1/projects", json={"title": "Shots Test Film"}, headers=auth_headers)
    project_id = create_p.json()["data"]["id"]

    # Create scene
    sc_resp = client.post(
        f"/api/v1/projects/{project_id}/scenes",
        json={"act_number": 1, "scene_number": 1, "slugline": "INT. LAB - NIGHT"},
        headers=auth_headers,
    )
    scene_id = sc_resp.json()["data"]["id"]

    # 1. Create Shot #1
    shot1_payload = {
        "shot_number": 1,
        "duration_seconds": 5.0,
        "camera_code": "#Cam 13",  # Low-Angle Hero Shot
        "lens_code": "#Lens 01",  # 2.0x Anamorphic
        "comp_code": "#Comp 01",  # Rule of Thirds
        "light_code": "#Light 06",  # Neon Cyberpunk
        "act_code": "#Act 06",  # Heroic Resolve
        "speed_code": "#Speed 03",  # Cinematic Paced
        "fg_bg_layers": {"fg": "Holographic interface sparks", "bg": "Data servers blinking cyan"},
        "dialogue": "Target locked.",
        "transition_type": "J_CUT",
    }
    shot_resp = client.post(f"/api/v1/scenes/{scene_id}/shots", json=shot1_payload, headers=auth_headers)
    assert shot_resp.status_code == 201
    shot1_data = shot_resp.json()["data"]
    shot_id = shot1_data["id"]
    assert shot1_data["camera_code"] == "#Cam 13"
    assert shot1_data["light_code"] == "#Light 06"

    # 2. List shots for scene
    list_shots_resp = client.get(f"/api/v1/scenes/{scene_id}/shots", headers=auth_headers)
    assert list_shots_resp.status_code == 200
    shots = list_shots_resp.json()["data"]
    assert len(shots) == 1
    assert shots[0]["shot_number"] == 1

    # 3. Get single shot
    get_shot_resp = client.get(f"/api/v1/shots/{shot_id}", headers=auth_headers)
    assert get_shot_resp.status_code == 200
    assert get_shot_resp.json()["data"]["id"] == shot_id

    # 4. Update shot
    put_shot_resp = client.put(
        f"/api/v1/shots/{shot_id}",
        json={"act_code": "#Act 03", "status": "APPROVED"},
        headers=auth_headers,
    )
    assert put_shot_resp.status_code == 200
    assert put_shot_resp.json()["data"]["act_code"] == "#Act 03"
    assert put_shot_resp.json()["data"]["status"] == "APPROVED"

    # 5. Delete shot
    del_shot_resp = client.delete(f"/api/v1/shots/{shot_id}", headers=auth_headers)
    assert del_shot_resp.status_code == 200
    assert client.get(f"/api/v1/shots/{shot_id}", headers=auth_headers).status_code == 404


def test_dynamic_duration_pacing_and_auto_split(client: TestClient, auth_headers: dict[str, str]):
    create_p = client.post("/api/v1/projects", json={"title": "Multi-Duration Studio Film"}, headers=auth_headers)
    project_id = create_p.json()["data"]["id"]

    # Create scene with 10s duration
    scene_payload = {
        "act_number": 2,
        "scene_number": 15,
        "slugline": "INT. CYPHER LAB - NIGHT",
        "narrative_goal": "Decrypt the syndicate memory core before the breach team arrives",
        "duration_target": 10.0,
    }
    sc_resp = client.post(f"/api/v1/projects/{project_id}/scenes", json=scene_payload, headers=auth_headers)
    assert sc_resp.status_code == 201
    scene_id = sc_resp.json()["data"]["id"]

    # 1. Test 5s Pacing Calibration
    # 5s -> max 14 words
    pass_5s = client.post(
        f"/api/v1/scenes/{scene_id}/calibrate-dialogue",
        json={"raw_text": "Perimeter runtuh, evakuasi segera dimulai.", "max_seconds": 5.0},
        headers=auth_headers,
    )
    assert pass_5s.status_code == 200
    d5 = pass_5s.json()["data"]
    assert d5["max_allowed_words"] == 14
    assert d5["passes_duration_limit"] is True
    assert d5["passes_5s_limit"] is True

    # Overflow 5s (> 14 words)
    fail_5s = client.post(
        f"/api/v1/scenes/{scene_id}/calibrate-dialogue",
        json={
            "raw_text": "Sistem mainframe sudah diretas oleh sindikat dan seluruh akses protokol distrik ditutup secara permanen oleh pengawas kota.",
            "max_seconds": 5.0,
        },
        headers=auth_headers,
    )
    assert fail_5s.status_code == 200
    assert fail_5s.json()["data"]["passes_duration_limit"] is False
    assert fail_5s.json()["data"]["passes_5s_limit"] is False

    # 2. Test 10s Pacing Calibration
    # 10s -> max 28 words
    pass_10s = client.post(
        f"/api/v1/scenes/{scene_id}/calibrate-dialogue",
        json={
            "raw_text": "Sistem mainframe sudah diretas oleh sindikat dan seluruh akses protokol distrik ditutup secara permanen oleh pengawas kota.",
            "max_seconds": 10.0,
        },
        headers=auth_headers,
    )
    assert pass_10s.status_code == 200
    d10 = pass_10s.json()["data"]
    assert d10["max_allowed_words"] == 28
    assert d10["passes_duration_limit"] is True
    assert d10["passes_5s_limit"] is True  # Alias matches passes_duration_limit

    # 3. Test 15s Pacing Calibration
    # 15s -> max 42 words
    long_text_35_words = (
        "Arya kita tidak punya banyak waktu sebelum seluruh pangkalan ini diledakkan dari orbit oleh armada Syndicate "
        "ambil inti memori itu lalu aktifkan pelindung darurat kita harus melarikan diri lewat saluran ventilasi bawah tanah sekarang juga"
    )
    pass_15s = client.post(
        f"/api/v1/scenes/{scene_id}/calibrate-dialogue",
        json={"raw_text": long_text_35_words, "max_seconds": 15.0},
        headers=auth_headers,
    )
    assert pass_15s.status_code == 200
    d15 = pass_15s.json()["data"]
    assert d15["max_allowed_words"] == 42
    assert d15["passes_duration_limit"] is True
    assert d15["passes_5s_limit"] is True

    # 4. Test Proportional Audio Transitions (>75% J_CUT, <40% HARD_CUT, 40-75% L_CUT)
    # Fast dialogue (2 words on 10s: ~0.86s, ratio 0.086 < 0.40) -> HARD_CUT
    fast_resp = client.post(
        f"/api/v1/scenes/{scene_id}/calibrate-dialogue",
        json={"raw_text": "Awas bahaya!", "max_seconds": 10.0},
        headers=auth_headers,
    )
    assert fast_resp.json()["data"]["transition_type"] == "HARD_CUT"

    # Dense dialogue (23 words on 10s: ~8.21s, ratio 0.821 > 0.75) -> J_CUT
    dense_resp = client.post(
        f"/api/v1/scenes/{scene_id}/calibrate-dialogue",
        json={
            "raw_text": "Sistem keamanan distrik sudah padam total dan seluruh unit penjaga lapis baja sedang bergerak sangat cepat menuju ke pintu masuk utama lantai tiga laboratorium.",
            "max_seconds": 10.0,
        },
        headers=auth_headers,
    )
    assert dense_resp.json()["data"]["transition_type"] == "J_CUT"

    # Balanced dialogue (12 words on 10s: ~5.15s, ratio 0.515 between 0.40 and 0.75) -> L_CUT
    balanced_resp = client.post(
        f"/api/v1/scenes/{scene_id}/calibrate-dialogue",
        json={
            "raw_text": "Kita harus memotong kabel transmisi daya sebelum generator darurat distrik menyala kembali.",
            "max_seconds": 10.0,
        },
        headers=auth_headers,
    )
    assert balanced_resp.json()["data"]["transition_type"] == "L_CUT"

    # 5. Test Auto-Split Endpoint (10s scene -> 2 shots @ 5.0s with camera variation)
    split_10s_resp = client.post(
        f"/api/v1/scenes/{scene_id}/auto-split",
        json={"target_duration": 10.0},
        headers=auth_headers,
    )
    assert split_10s_resp.status_code == 200
    split_data = split_10s_resp.json()["data"]
    assert split_data["shots_count"] == 2
    assert split_data["target_duration"] == 10.0
    shots_10s = split_data["shots"]
    assert len(shots_10s) == 2
    assert shots_10s[0]["duration_seconds"] == 5.0
    assert shots_10s[1]["duration_seconds"] == 5.0
    assert shots_10s[0]["camera_code"] != shots_10s[1]["camera_code"]

    # 6. Test Auto-Split Endpoint (15s scene -> 3 shots @ 5.0s with camera variation)
    split_15s_resp = client.post(
        f"/api/v1/scenes/{scene_id}/auto-split",
        json={"target_duration": 15.0},
        headers=auth_headers,
    )
    assert split_15s_resp.status_code == 200
    split_15s_data = split_15s_resp.json()["data"]
    assert split_15s_data["shots_count"] == 3
    assert split_15s_data["target_duration"] == 15.0
    shots_15s = split_15s_data["shots"]
    assert len(shots_15s) == 3
    assert all(s["duration_seconds"] == 5.0 for s in shots_15s)
    camera_codes = {s["camera_code"] for s in shots_15s}
    assert len(camera_codes) == 3  # 3 varied camera angles

    # 7. Test Idempotency (Repeated clicks on Auto-Split does not duplicate shots)
    repeat_split = client.post(
        f"/api/v1/scenes/{scene_id}/auto-split",
        json={"target_duration": 15.0},
        headers=auth_headers,
    )
    assert repeat_split.status_code == 200
    repeat_data = repeat_split.json()["data"]
    assert repeat_data["shots_count"] == 3
    assert [s["id"] for s in repeat_data["shots"]] == [s["id"] for s in shots_15s]


def test_flexible_blueprint_generation_scales_and_durations(client: TestClient, auth_headers: dict[str, str]):
    """Verify legacy instant blueprint on POST /projects/{project_id}/scenes is rejected with 400."""
    create_p = client.post("/api/v1/projects", json={"title": "100-Scene Featurette"}, headers=auth_headers)
    project_id = create_p.json()["data"]["id"]

    bp_resp = client.post(
        f"/api/v1/projects/{project_id}/scenes",
        json={
            "generate_blueprint": True,
            "total_scenes": 100,
            "duration_mode": "dynamic",
            "auto_split_shots": True,
        },
        headers=auth_headers,
    )
    assert bp_resp.status_code == 400
    err_text = bp_resp.json().get("error", {}).get("message", "") or bp_resp.text
    assert "deprecated" in err_text.lower()
    assert "/blueprint/" in err_text


def test_staged_llm_writer_phase_a_and_phase_b(client: TestClient, auth_headers: dict[str, str]):
    import re

    async def fake_llm(messages: list[dict[str, str]], retry_on_parse_error: bool = True) -> dict:
        user_content = messages[-1]["content"] if messages else ""
        if "Treatment" in user_content:
            total = 50 if "Total Scenes Target: 50" in user_content else 100
            b1 = 12 if total == 50 else 25
            b2 = 25 if total == 50 else 50
            b3 = 38 if total == 50 else 75
            return {
                "title": "Chronicles of Arya",
                "logline": "A rogue operative seeks to liberate an imprisoned synthetic mind.",
                "theme": "Liberation",
                "dramatic_premise": "Arya defies the syndicate.",
                "total_scenes": total,
                "acts": [
                    {"act_number": 1, "act_title": "Setup", "start_scene": 1, "end_scene": b1, "dramatic_goal": "Setup", "key_beat": "Beat 1"},
                    {"act_number": 2, "act_title": "Confrontation", "start_scene": b1 + 1, "end_scene": b2, "dramatic_goal": "Trials", "key_beat": "Beat 2"},
                    {"act_number": 3, "act_title": "Crisis", "start_scene": b2 + 1, "end_scene": b3, "dramatic_goal": "Dark Night", "key_beat": "Beat 3"},
                    {"act_number": 4, "act_title": "Resolution", "start_scene": b3 + 1, "end_scene": total, "dramatic_goal": "Resolution", "key_beat": "Beat 4"},
                ],
            }

        # Sub-chunk scene writing
        match = re.search(r"Scene (\d+) to Scene (\d+)", user_content)
        if match:
            s_start = int(match.group(1))
            s_end = int(match.group(2))
        else:
            s_start, s_end = 1, 12

        return {
            "act_number": 1,
            "act_title": "Dynamic Act",
            "act_summary": "Arya executes the next phase of the operation.",
            "scenes": [
                {
                    "scene_number": i,
                    "slugline": f"EXT. SECTOR {i} - NIGHT",
                    "narrative_goal": f"Arya advances beat {i}",
                    "primary_character": "Arya",
                    "dialogue": f"Dialogue line for scene {i}.",
                    "duration_seconds": 15.0,
                }
                for i in range(s_start, s_end + 1)
            ],
        }

    with patch.object(PolyaScreenwriterEngine, "_call_llm", side_effect=fake_llm):
        # 1. Create project with characters
        create_p = client.post("/api/v1/projects", json={"title": "Chronicles of Arya"}, headers=auth_headers)
        project_id = create_p.json()["data"]["id"]

        client.post(
            f"/api/v1/projects/{project_id}/characters",
            json={
                "name": "Arya",
                "role": "Cybernetic Infiltrator",
                "base_prompt": "Female operative with glowing neural interface tattoo",
            },
            headers=auth_headers,
        )

        # 2. Phase A: Master Treatment & Beat Sheet
        treat_resp = client.post(
            f"/api/v1/projects/{project_id}/blueprint/treatment",
            json={
                "total_scenes": 100,
                "duration_mode": "dynamic",
                "premise": "A rogue operative seeks to liberate an imprisoned synthetic mind.",
                "clear_existing": True,
            },
            headers=auth_headers,
        )
        assert treat_resp.status_code == 200
        treatment = treat_resp.json()["data"]
        assert treatment["title"] == "Chronicles of Arya"
        assert "logline" in treatment
        assert len(treatment["acts"]) == 4
        assert treatment["acts"][0]["start_scene"] == 1
        assert treatment["acts"][0]["end_scene"] == 25

        # 3. Phase B: Generate Act 1
        act1_resp = client.post(
            f"/api/v1/projects/{project_id}/blueprint/generate-act",
            json={
                "act_number": 1,
                "total_scenes": 100,
                "duration_mode": "dynamic",
                "auto_split_shots": True,
            },
            headers=auth_headers,
        )
        assert act1_resp.status_code == 200
        act1_data = act1_resp.json()["data"]
        assert act1_data["act_number"] == 1
        assert act1_data["scenes_generated"] == 25
        assert act1_data["total_saved_for_project"] == 25
        assert act1_data["act_summary"] != ""

        # Check status endpoint
        status_resp = client.get(f"/api/v1/projects/{project_id}/blueprint/status", headers=auth_headers)
        assert status_resp.status_code == 200
        st_data = status_resp.json()["data"]
        assert st_data["has_treatment"] is True
        assert st_data["total_scenes"] == 25
        assert 1 in st_data["completed_acts"]

        # 4. Phase B: Generate Act 2 (with persistent context from Act 1)
        act2_resp = client.post(
            f"/api/v1/projects/{project_id}/blueprint/generate-act",
            json={
                "act_number": 2,
                "total_scenes": 100,
                "duration_mode": "dynamic",
                "auto_split_shots": True,
            },
            headers=auth_headers,
        )
        assert act2_resp.status_code == 200
        act2_data = act2_resp.json()["data"]
        assert act2_data["act_number"] == 2
        assert act2_data["scenes_generated"] == 25
        assert act2_data["total_saved_for_project"] == 50

        # 5. Full Batch Write Orchestration Test (50 scenes)
        bw_project = client.post("/api/v1/projects", json={"title": "Staged End-to-End Saga"}, headers=auth_headers).json()["data"]["id"]
        bw_resp = client.post(
            f"/api/v1/projects/{bw_project}/blueprint/batch-write",
            json={
                "total_scenes": 50,
                "duration_mode": "dynamic",
                "premise": "A covert team executes an impossible memory-heist.",
                "auto_split_shots": True,
                "clear_existing": True,
            },
            headers=auth_headers,
        )
        assert bw_resp.status_code == 200
        bw_data = bw_resp.json()["data"]
        assert bw_data["total_scenes"] == 50
        assert bw_data["total_shots"] > 50
        assert len(bw_data["acts"]) == 4

        # Verify scenes have populated slugline, narrative_goal, and shots have dialogue
        all_scenes = client.get(f"/api/v1/projects/{bw_project}/scenes", headers=auth_headers).json()["data"]
        assert len(all_scenes) == 50
        for s in all_scenes:
            assert s["slugline"] != ""
            assert s["narrative_goal"] != ""
            assert s["shots_count"] >= 1


def test_wave1_act5_filter_unified_pacing_zero_slapstick_and_voice_continuity(client: TestClient, auth_headers: dict[str, str]):
    """Verify Wave 1 fixes: Act 5 filter, unified 2.8 wps math, non-slapstick cues, and Voice DNA/5-State wiring."""
    from unittest.mock import AsyncMock

    # 1. Create stylized anime project with Act 5 scenes + Character with Voice DNA & States
    proj_resp = client.post(
        "/api/v1/projects",
        json={
            "title": "Crimson Rain Protocol",
            "target_style_code": "#Style 15",
            "settings": {"synopsis": "A reluctant courier crosses a flooded city before dawn.", "genre": "Anime Drama"},
        },
        headers=auth_headers,
    )
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["data"]["id"]

    # Create character with Voice DNA + #State 01 & #State 05
    char_resp = client.post(
        f"/api/v1/projects/{proj_id}/characters",
        json={
            "name": "Ren Sato",
            "role": "PROTAGONIST",
            "base_prompt": "Stoic courier isolated on #D4D4D4",
            "voice_dna_profile": "Measured deadpan brevity (~1.9 wps), speaks in clipped imperatives.",
        },
        headers=auth_headers,
    )
    assert char_resp.status_code == 201
    char_id = char_resp.json()["data"]["id"]
    client.post(
        f"/characters/{char_id}/states" if False else f"/api/v1/characters/{char_id}/states",
        json={
            "state_code": "#State 05",
            "state_label": "Catharsis",
            "wardrobe": "Salt-stained dark trench coat",
            "injuries_and_wear": "Splinted left hand",
            "expression_anchor": "Calm eyes despite tremor",
        },
        headers=auth_headers,
    )

    # 2. Seed Act 4 & Act 5 scenes and verify GET ?act=5 works without 422
    sc4 = client.post(
        f"/api/v1/projects/{proj_id}/scenes",
        json={"act_number": 4, "scene_number": 40, "slugline": "EXT. BRIDGE - RAIN", "narrative_goal": "Ren loses the map.", "duration_target": 5.0},
        headers=auth_headers,
    ).json()["data"]
    sc5 = client.post(
        f"/api/v1/projects/{proj_id}/scenes",
        json={"act_number": 5, "scene_number": 50, "slugline": "EXT. PIER - DAWN", "narrative_goal": "Ren faces Kazuo.", "duration_target": 5.0},
        headers=auth_headers,
    )
    assert sc5.status_code == 201
    sc5_id = sc5.json()["data"]["id"]

    act5_list = client.get(f"/api/v1/projects/{proj_id}/scenes?act=5", headers=auth_headers)
    assert act5_list.status_code == 200
    assert len(act5_list.json()["data"]) == 1
    assert act5_list.json()["data"][0]["act_number"] == 5

    # 3. Unified 2.8 wps calibration: 14 words at 5.0s -> 5.0s exact, passes_duration_limit=True + Voice DNA passed
    with patch.object(
        PolyaScreenwriterEngine,
        "calibrate_dialogue_pacing",
        new=AsyncMock(return_value={
            "word_count": 14,
            "syllable_count": 18,
            "estimated_duration_seconds": 5.0,
            "passes_duration_limit": True,
            "passes_5s_limit": True,
            "max_allowed_words": 14,
            "max_seconds": 5.0,
            "transition_type": "J_CUT",
            "audio_lead_seconds": 1.0,
            "analysis": "Aligned.",
            "trimmed_suggestion": None,
            "source": "llm",
        }),
    ) as mock_cal:
        cal_resp = client.post(
            f"/api/v1/scenes/{sc5_id}/calibrate-dialogue",
            json={
                "raw_text": "One two three four five six seven eight nine ten eleven twelve thirteen fourteen",
                "character_name": "Ren Sato",
                "max_seconds": 5.0,
            },
            headers=auth_headers,
        )
        assert cal_resp.status_code == 200
        assert mock_cal.call_args.kwargs["style_code"] == "#Style 15"
        assert "clipped imperatives" in (mock_cal.call_args.kwargs["voice_dna_profile"] or "")
        assert mock_cal.call_args.kwargs["active_state"]["wardrobe"] == "Salt-stained dark trench coat"

    # Real deterministic 2.8 wps math verification
    real_det = PolyaScreenwriterEngine._compute_dialogue_pacing_metrics(
        "One two three four five six seven eight nine ten eleven twelve thirteen fourteen", 5.0
    )
    assert real_det["estimated_duration_seconds"] == 5.0
    assert real_det["passes_duration_limit"] is True

    # 4. Polish passes project_context, Voice DNA, active State, and adjacent scenes
    with patch.object(
        PolyaScreenwriterEngine,
        "polish_scene_director_cut",
        new=AsyncMock(return_value={
            "slugline": "EXT. PIER - DAWN",
            "narrative_goal": "Polished goal",
            "dialogue": "Take it.",
            "camera_code": "#Cam 03",
            "lighting_code": "#Light 06",
            "director_notes": "Tight.",
        }),
    ) as mock_pol:
        pol_resp = client.post(
            f"/api/v1/scenes/{sc5_id}/director-polish",
            json={"slugline": "EXT. PIER - DAWN", "narrative_goal": "Ren faces Kazuo."},
            headers=auth_headers,
        )
        assert pol_resp.status_code == 200
        assert mock_pol.call_args.kwargs["style_code"] == "#Style 15"
        assert mock_pol.call_args.kwargs["project_context"] is not None
        assert "clipped imperatives" in (mock_pol.call_args.kwargs["voice_dna_profile"] or "")
        assert mock_pol.call_args.kwargs["adjacent_scenes"]["prev"]["scene_number"] == 40
        assert mock_pol.call_args.kwargs["active_state"]["state_code"] == "#State 05"

    # 5. Cold open with enable_cold_open=True on anime project emits zero slapstick SFX & zero "Environmental cue:"
    async def fake_cold_llm(messages: list[dict[str, str]], retry_on_parse_error: bool = True) -> dict:
        prompt_text = messages[-1]["content"] if messages else ""
        if "Treatment" in prompt_text:
            return {
                "title": "Crimson Rain Protocol",
                "logline": "A courier races the tide.",
                "theme": "Duty",
                "dramatic_premise": "One last delivery.",
                "acts": [
                    {"act_number": 1, "act_title": "Act I", "start_scene": 1, "end_scene": 5, "dramatic_goal": "Setup", "key_beat": "Storm"},
                    {"act_number": 2, "act_title": "Act II", "start_scene": 6, "end_scene": 10, "dramatic_goal": "Trials", "key_beat": "Flood"},
                    {"act_number": 3, "act_title": "Act III", "start_scene": 11, "end_scene": 15, "dramatic_goal": "Crisis", "key_beat": "Betrayal"},
                    {"act_number": 4, "act_title": "Act IV", "start_scene": 16, "end_scene": 20, "dramatic_goal": "Climax", "key_beat": "Dawn"},
                ],
            }
        return {
            "act_summary": "Act 1 done.",
            "scenes": [
                {
                    "scene_number": i,
                    "slugline": f"EXT. SECTOR {i} - NIGHT",
                    "narrative_goal": f"Ren evades patrol {i}",
                    "speaking_character": "Ren Sato",
                    "dialogue": "" if i <= 4 else f"Hold position {i}.",
                }
                for i in range(1, 6)
            ],
        }

    with patch.object(PolyaScreenwriterEngine, "_call_llm", side_effect=fake_cold_llm):
        co_resp = client.post(
            f"/api/v1/projects/{proj_id}/blueprint/generate-act",
            json={
                "act_number": 1,
                "total_scenes": 20,
                "duration_mode": "dynamic",
                "auto_split_shots": True,
                "enable_cold_open": True,
            },
            headers=auth_headers,
        )
        assert co_resp.status_code == 200
        proj_scenes = client.get(f"/api/v1/projects/{proj_id}/scenes?act=1", headers=auth_headers).json()["data"]
        for sc in proj_scenes:
            shots = client.get(f"/api/v1/scenes/{sc['id']}/shots", headers=auth_headers).json()["data"]
            for sh in shots:
                dlg = sh.get("dialogue") or ""
                assert "Boing" not in dlg
                assert "Record Scratch" not in dlg
                assert "Tape Rewind" not in dlg
                assert "Environmental cue:" not in dlg


def test_wave2_api_polish_takes_dialogue_alternatives_autosplit_coverage_and_treatment_variants(
    client: TestClient, auth_headers: dict[str, str]
):
    """Verify Wave 2 API endpoints: 3 polish takes + primary shot apply, 3 dialogue alternatives, coverage auto-split, shot PUT, and 3 treatment variants."""
    from unittest.mock import AsyncMock

    proj_resp = client.post(
        "/api/v1/projects",
        json={
            "title": "Wave 2 Anime Thriller",
            "target_style_code": "#Style 15",
            "settings": {"synopsis": "An archivistsmuggles a coded lens out of a flooded citadel.", "genre": "Anime Thriller"},
        },
        headers=auth_headers,
    )
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["data"]["id"]

    sc_resp = client.post(
        f"/api/v1/projects/{proj_id}/scenes",
        json={
            "act_number": 1,
            "scene_number": 1,
            "slugline": "EXT. CANAL LOCK - NIGHT",
            "narrative_goal": "Ren hides the cipher capsule inside a lantern.",
            "duration_target": 10.0,
        },
        headers=auth_headers,
    )
    assert sc_resp.status_code == 201
    scene_id = sc_resp.json()["data"]["id"]

    # 1. Dual-brain auto-split with coverage_style presets (non-blind anime optics) + full Shot PUT update
    with patch.object(PolyaScreenwriterEngine, "_call_llm", side_effect=RuntimeError("offline fallback")):
        split_rapid = client.post(
            f"/api/v1/scenes/{scene_id}/auto-split",
            json={"target_duration": 10.0, "coverage_style": "rapid_montage"},
            headers=auth_headers,
        )
        assert split_rapid.status_code == 200
        sr_data = split_rapid.json()["data"]
        assert sr_data["coverage_style"] == "rapid_montage"
        assert sr_data["shots_count"] == 3
        assert sr_data["shots"][0]["light_code"] == "#Light 06"  # anime_2d style optics, not blind #Light 01
        first_shot_id = sr_data["shots"][0]["id"]

        split_oner = client.post(
            f"/api/v1/scenes/{scene_id}/auto-split",
            json={"target_duration": 10.0, "coverage_style": "visceral_oner"},
            headers=auth_headers,
        )
        assert split_oner.status_code == 200
        assert split_oner.json()["data"]["shots_count"] == 1
        assert split_oner.json()["data"]["shots"][0]["duration_seconds"] == 10.0
        assert split_oner.json()["data"]["shots"][0]["id"] == first_shot_id

    shot_put = client.put(
        f"/api/v1/shots/{first_shot_id}",
        json={
            "camera_code": "#Cam 07",
            "light_code": "#Light 08",
            "act_code": "#Act 05",
            "speed_code": "#Speed 02",
            "dialogue": "Keep the shutter down.",
            "transition_type": "L_CUT",
            "prompt_override": "Raindrops streaked across lantern brass",
        },
        headers=auth_headers,
    )
    assert shot_put.status_code == 200
    sp_out = shot_put.json()["data"]
    assert sp_out["camera_code"] == "#Cam 07"
    assert sp_out["light_code"] == "#Light 08"
    assert sp_out["act_code"] == "#Act 05"
    assert sp_out["speed_code"] == "#Speed 02"
    assert sp_out["transition_type"] == "L_CUT"
    assert sp_out["prompt_override"] == "Raindrops streaked across lantern brass"

    # 2. Director Polish returns 3 options + backward-compatible suggestions, and Scene PUT updates primary shot
    with patch.object(PolyaScreenwriterEngine, "_call_llm", side_effect=RuntimeError("offline fallback")):
        pol_resp = client.post(
            f"/api/v1/scenes/{scene_id}/director-polish",
            json={"slugline": "EXT. CANAL LOCK - NIGHT", "narrative_goal": "Ren hides the cipher capsule.", "dialogue": "Stay low.", "camera_code": "#Cam 07", "lighting_code": "#Light 08"},
            headers=auth_headers,
        )
        assert pol_resp.status_code == 200
        pol_data = pol_resp.json()["data"]
        assert "suggestions" in pol_data
        assert len(pol_data["options"]) == 3
        take2 = pol_data["options"][1]
        assert take2["take_id"] == "visceral_kinetic"
        assert take2["camera_code"] and take2["lighting_code"] and take2["transition_type"]

    apply_resp = client.put(
        f"/api/v1/scenes/{scene_id}",
        json={
            "slugline": take2["slugline"],
            "narrative_goal": take2["narrative_goal"],
            "dialogue": take2["dialogue"],
            "camera_code": take2["camera_code"],
            "lighting_code": take2["lighting_code"],
            "transition_type": take2["transition_type"],
            "audio_lead_seconds": 1.2,
        },
        headers=auth_headers,
    )
    assert apply_resp.status_code == 200
    assert apply_resp.json()["data"]["camera_code"] == take2["camera_code"]
    assert apply_resp.json()["data"]["lighting_code"] == take2["lighting_code"]
    assert apply_resp.json()["data"]["transition_type"] == take2["transition_type"]

    get_after_apply = client.get(f"/api/v1/scenes/{scene_id}", headers=auth_headers).json()["data"]
    assert get_after_apply["camera_code"] == take2["camera_code"]
    assert get_after_apply["lighting_code"] == take2["lighting_code"]
    assert get_after_apply["transition_type"] == take2["transition_type"]
    assert get_after_apply["audio_lead_seconds"] == 1.2
    listed_after_apply = client.get(f"/api/v1/projects/{proj_id}/scenes", headers=auth_headers).json()["data"]
    assert listed_after_apply[0]["camera_code"] == take2["camera_code"]
    assert listed_after_apply[0]["lighting_code"] == take2["lighting_code"]

    # 3. Calibrate dialogue returns 3 deterministic 2.8 wps alternatives
    with patch.object(PolyaScreenwriterEngine, "_call_llm", side_effect=RuntimeError("offline fallback")):
        cal_resp = client.post(
            f"/api/v1/scenes/{scene_id}/calibrate-dialogue",
            json={"raw_text": "One two three four five six seven eight nine ten eleven twelve", "max_seconds": 5.0},
            headers=auth_headers,
        )
        assert cal_resp.status_code == 200
        cal_data = cal_resp.json()["data"]
        assert len(cal_data["alternatives"]) == 3
        assert cal_data["word_count"] == 12
        assert cal_data["estimated_duration_seconds"] == round(12 / 2.8, 2)

    # 4. Treatment Variants returns 3 pitches & selected_treatment locks straight into /blueprint/treatment
    mock_vars = [
        {
            "variant_id": v_id,
            "pitch_label": lbl,
            "pitch_hook": "Sharp contrast",
            "title": "Wave 2 Anime Thriller",
            "logline": f"Logline {v_id}",
            "theme": "Sacrifice",
            "dramatic_premise": "Premise",
            "total_scenes": 50,
            "structure_type": "4_act",
            "structure_name": "Hollywood 4-Act Structure",
            "acts": [{"act_number": a, "act_title": f"Act {a}", "start_scene": (a - 1) * 12 + 1, "end_scene": a * 12, "dramatic_goal": f"Goal {a}", "key_beat": f"Beat {a}"} for a in range(1, 5)],
            "cold_open_30s": {"enabled": True},
        }
        for v_id, lbl in [
            ("character_tragedy_redemption", "Character Tragedy / Redemption"),
            ("high_stakes_escalation_twist", "High-Stakes Escalation / Twist"),
            ("atmospheric_mythic_arc", "Atmospheric Mythic Arc"),
        ]
    ]
    with patch.object(PolyaScreenwriterEngine, "generate_treatment_variants", new=AsyncMock(return_value=mock_vars)):
        var_resp = client.post(
            f"/api/v1/projects/{proj_id}/blueprint/treatment-variants",
            json={"total_scenes": 50, "structure_type": "4_act", "enable_cold_open": True},
            headers=auth_headers,
        )
        assert var_resp.status_code == 200
        variants = var_resp.json()["data"]["variants"]
        assert len(variants) == 3

    lock_resp = client.post(
        f"/api/v1/projects/{proj_id}/blueprint/treatment",
        json={
            "total_scenes": 50,
            "structure_type": "4_act",
            "enable_cold_open": True,
            "selected_treatment": variants[1],
        },
        headers=auth_headers,
    )
    assert lock_resp.status_code == 200
    assert lock_resp.json()["data"]["logline"] == "Logline high_stakes_escalation_twist"


