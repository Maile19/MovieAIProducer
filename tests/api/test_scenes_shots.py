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
