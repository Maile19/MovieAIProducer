from fastapi.testclient import TestClient


def test_50_scene_blueprint_generation_and_filtering(client: TestClient, auth_headers: dict[str, str]):
    # 1. Create project
    create_p = client.post("/api/v1/projects", json={"title": "Epic Cyberpunk Saga"}, headers=auth_headers)
    project_id = create_p.json()["data"]["id"]

    # 2. Bulk generate standard 50-Scene 4-Act Blueprint
    blueprint_resp = client.post(
        f"/api/v1/projects/{project_id}/scenes",
        json={"generate_blueprint": True},
        headers=auth_headers,
    )
    assert blueprint_resp.status_code == 201
    assert blueprint_resp.json()["data"]["scenes_generated"] == 50

    # 3. List all scenes
    all_scenes_resp = client.get(f"/api/v1/projects/{project_id}/scenes", headers=auth_headers)
    assert all_scenes_resp.status_code == 200
    scenes = all_scenes_resp.json()["data"]
    assert len(scenes) == 50
    assert scenes[0]["scene_number"] == 1
    assert scenes[0]["act_number"] == 1
    assert scenes[49]["scene_number"] == 50
    assert scenes[49]["act_number"] == 4

    # 4. Filter by Act 1 (Scenes 1-12)
    act1_resp = client.get(f"/api/v1/projects/{project_id}/scenes?act=1", headers=auth_headers)
    assert act1_resp.status_code == 200
    act1_scenes = act1_resp.json()["data"]
    assert len(act1_scenes) == 12

    # 5. Filter by Act 2 (Scenes 13-25)
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
    # 1. Test 100-Scene Generation with Dynamic Hollywood Pacing (15s Acts I & III, 10s Acts II & IV)
    create_p100 = client.post("/api/v1/projects", json={"title": "100-Scene Featurette"}, headers=auth_headers)
    p100_id = create_p100.json()["data"]["id"]

    bp100_resp = client.post(
        f"/api/v1/projects/{p100_id}/scenes",
        json={
            "generate_blueprint": True,
            "total_scenes": 100,
            "duration_mode": "dynamic",
            "auto_split_shots": True,
        },
        headers=auth_headers,
    )
    assert bp100_resp.status_code == 201
    bp100_data = bp100_resp.json()["data"]
    assert bp100_data["scenes_generated"] == 100
    # Dynamic mode: Act 1 (25 * 3 = 75) + Act 2 (25 * 2 = 50) + Act 3 (25 * 3 = 75) + Act 4 (25 * 2 = 50) = 250 shots
    assert bp100_data["shots_generated"] == 250
    assert bp100_data["duration_mode"] == "dynamic"

    # Verify Act distribution for 100 scenes (25 per act)
    act1_resp = client.get(f"/api/v1/projects/{p100_id}/scenes?act=1", headers=auth_headers)
    assert act1_resp.status_code == 200
    act1_scenes = act1_resp.json()["data"]
    assert len(act1_scenes) == 25
    assert act1_scenes[0]["duration_target"] == 15.0
    assert act1_scenes[0]["shots_count"] == 3

    act2_resp = client.get(f"/api/v1/projects/{p100_id}/scenes?act=2", headers=auth_headers)
    assert act2_resp.status_code == 200
    act2_scenes = act2_resp.json()["data"]
    assert len(act2_scenes) == 25
    assert act2_scenes[0]["duration_target"] == 10.0
    assert act2_scenes[0]["shots_count"] == 2

    # 2. Test 420-Scene Generation with Flat 10s Pacing and Bulk SQLite Insertion
    create_p420 = client.post("/api/v1/projects", json={"title": "420-Scene Full Feature"}, headers=auth_headers)
    p420_id = create_p420.json()["data"]["id"]

    bp420_resp = client.post(
        f"/api/v1/projects/{p420_id}/scenes",
        json={
            "generate_blueprint": True,
            "total_scenes": 420,
            "duration_mode": "flat_10s",
            "auto_split_shots": True,
        },
        headers=auth_headers,
    )
    assert bp420_resp.status_code == 201
    bp420_data = bp420_resp.json()["data"]
    assert bp420_data["scenes_generated"] == 420
    # 420 scenes @ 10s = 2 shots each = 840 shots
    assert bp420_data["shots_generated"] == 840
    assert bp420_data["duration_mode"] == "flat_10s"

    # Check Act 1 count: 420 / 4 = 105 scenes
    act1_420 = client.get(f"/api/v1/projects/{p420_id}/scenes?act=1", headers=auth_headers)
    assert act1_420.status_code == 200
    assert len(act1_420.json()["data"]) == 105
    assert act1_420.json()["data"][0]["duration_target"] == 10.0

    # 3. Test Legacy flat_5s Mode
    create_p5s = client.post("/api/v1/projects", json={"title": "Legacy 5s Film"}, headers=auth_headers)
    p5s_id = create_p5s.json()["data"]["id"]

    bp5s_resp = client.post(
        f"/api/v1/projects/{p5s_id}/scenes",
        json={
            "generate_blueprint": True,
            "total_scenes": 50,
            "duration_mode": "flat_5s",
            "auto_split_shots": True,
        },
        headers=auth_headers,
    )
    assert bp5s_resp.status_code == 201
    bp5s_data = bp5s_resp.json()["data"]
    assert bp5s_data["scenes_generated"] == 50
    assert bp5s_data["shots_generated"] == 50
    assert bp5s_data["duration_mode"] == "flat_5s"

    # 4. Test clear_existing=True overwrite
    re_bp = client.post(
        f"/api/v1/projects/{p5s_id}/scenes",
        json={
            "generate_blueprint": True,
            "total_scenes": 100,
            "duration_mode": "flat_15s",
            "clear_existing": True,
        },
        headers=auth_headers,
    )
    assert re_bp.status_code == 201
    re_scenes = client.get(f"/api/v1/projects/{p5s_id}/scenes", headers=auth_headers).json()["data"]
    assert len(re_scenes) == 100


def test_staged_llm_writer_phase_a_and_phase_b(client: TestClient, auth_headers: dict[str, str]):
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


