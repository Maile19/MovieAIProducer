from fastapi.testclient import TestClient


def test_matrix_catalog_endpoints(client: TestClient):
    # 1. Full catalog
    full_resp = client.get("/api/v1/catalog/matrix")
    assert full_resp.status_code == 200
    data = full_resp.json()["data"]
    assert len(data["styles"]) == 18
    assert len(data["lighting"]) == 14
    assert len(data["acting"]) == 24
    assert len(data["cameras"]) == 34
    assert len(data["lenses"]) == 6
    assert len(data["compositions"]) == 8
    assert len(data["speeds"]) == 5

    # 2. Filter by category
    style_resp = client.get("/api/v1/catalog/matrix?category=styles")
    assert style_resp.status_code == 200
    assert "styles" in style_resp.json()["data"]
    assert len(style_resp.json()["data"]["styles"]) == 18

    cam_resp = client.get("/api/v1/catalog/matrix?category=cam")
    assert cam_resp.status_code == 200
    assert "cameras" in cam_resp.json()["data"]
    assert len(cam_resp.json()["data"]["cameras"]) == 34


def test_prompt_transpiler_all_engines(client: TestClient):
    engines = ["veo", "kling", "runway", "sora", "comfyui"]

    for eng in engines:
        payload = {
            "provider_target": eng,
            "style_code": "#Style 08",  # Sinema Nusantara
            "camera_code": "#Cam 13",  # Low-Angle Hero Shot
            "lens_code": "#Lens 01",  # 2.0x Anamorphic
            "comp_code": "#Comp 01",  # Rule of Thirds
            "light_code": "#Light 06",  # Neon Cyberpunk
            "act_code": "#Act 06",  # Heroic Resolve
            "speed_code": "#Speed 03",  # Cinematic Paced
            "character_dna": "Arya, 32yo Indonesian female warrior",
            "state_code": "#State 01",
            "wardrobe": "Traditional batik motif cyber-armor",
            "env_dna": "Rain-slicked alleyway in Old Batavia",
            "action_description": "drawing energised keris blade",
            "fg_description": "Falling raindrops catching neon glow",
            "bg_description": "Distant magnetic monorail passing overhead",
            "aspect_ratio": "16:9",
        }
        resp = client.post("/api/v1/transpile", json=payload)
        assert resp.status_code == 200
        res_data = resp.json()["data"]
        assert "positive_prompt" in res_data
        assert "negative_prompt" in res_data
        assert len(res_data["positive_prompt"]) > 50
        assert "metadata" in res_data
        assert res_data["metadata"]["codes"]["style"] == "#Style 08"


def test_qc_scorecard_evaluation(client: TestClient, auth_headers: dict[str, str]):
    # 1. Test passing metrics
    pass_payload = {
        "face_similarity": 0.92,
        "clip_score": 0.88,
        "aesthetic_score": 8.9,
        "temporal_jitter": 0.05,
        "audio_snr_db": 36.0,
    }
    pass_resp = client.post("/api/v1/qc/evaluate", json=pass_payload)
    assert pass_resp.status_code == 200
    qc_pass = pass_resp.json()["data"]
    assert qc_pass["overall_score"] >= 0.85
    assert qc_pass["passed"] is True
    assert len(qc_pass["critical_defects"]) == 0

    # 2. Test failing metrics (severe temporal jitter and low face similarity)
    fail_payload = {
        "face_similarity": 0.55,
        "clip_score": 0.70,
        "aesthetic_score": 4.5,
        "temporal_jitter": 0.35,
        "audio_snr_db": 10.0,
    }
    fail_resp = client.post("/api/v1/qc/evaluate", json=fail_payload)
    assert fail_resp.status_code == 200
    qc_fail = fail_resp.json()["data"]
    assert qc_fail["overall_score"] < 0.75
    assert qc_fail["passed"] is False
    assert len(qc_fail["critical_defects"]) > 0

    # 3. Test saving QC report with valid shot_id
    # Create project and shot
    p_resp = client.post("/api/v1/projects", json={"title": "QC Project"}, headers=auth_headers)
    project_id = p_resp.json()["data"]["id"]
    sc_resp = client.post(
        f"/api/v1/projects/{project_id}/scenes",
        json={"act_number": 1, "scene_number": 1, "slugline": "EXT. COURTYARD - DAY"},
        headers=auth_headers,
    )
    scene_id = sc_resp.json()["data"]["id"]
    sh_resp = client.post(f"/api/v1/scenes/{scene_id}/shots", json={"shot_number": 1}, headers=auth_headers)
    shot_id = sh_resp.json()["data"]["id"]

    pass_payload["shot_id"] = shot_id
    save_qc_resp = client.post("/api/v1/qc/evaluate", json=pass_payload)
    assert save_qc_resp.status_code == 200
    assert "report_id" in save_qc_resp.json()["data"]


def test_export_package_json_and_markdown(client: TestClient, auth_headers: dict[str, str]):
    # 1. Create project, characters, scenes, and shots
    create_p = client.post("/api/v1/projects", json={"title": "Master Cut Production"}, headers=auth_headers)
    project_id = create_p.json()["data"]["id"]

    # Add character & state
    char_resp = client.post(
        f"/api/v1/projects/{project_id}/characters",
        json={"name": "Arya", "role": "PROTAGONIST", "base_prompt": "Female lead with cybernetic eye"},
        headers=auth_headers,
    )
    char_id = char_resp.json()["data"]["id"]
    client.post(
        f"/api/v1/characters/{char_id}/states",
        json={"state_code": "#State 01", "wardrobe": "Standard cybernetic suit"},
        headers=auth_headers,
    )

    # Add scene and shot
    sc_resp = client.post(
        f"/api/v1/projects/{project_id}/scenes",
        json={"act_number": 1, "scene_number": 1, "slugline": "INT. BRIDGE - NIGHT"},
        headers=auth_headers,
    )
    scene_id = sc_resp.json()["data"]["id"]
    client.post(
        f"/api/v1/scenes/{scene_id}/shots",
        json={"shot_number": 1, "camera_code": "#Cam 01", "light_code": "#Light 01", "dialogue": "All systems go."},
        headers=auth_headers,
    )

    # 2. Export JSON
    json_resp = client.get(f"/api/v1/projects/{project_id}/export?format=json", headers=auth_headers)
    assert json_resp.status_code == 200
    export_data = json_resp.json()["data"]
    assert export_data["project"]["title"] == "Master Cut Production"
    assert len(export_data["characters"]) == 1
    assert len(export_data["scenes"]) == 1
    assert len(export_data["scenes"][0]["shots"]) == 1

    # 3. Export Markdown
    md_resp = client.get(f"/api/v1/projects/{project_id}/export?format=markdown", headers=auth_headers)
    assert md_resp.status_code == 200
    assert "text/markdown" in md_resp.headers.get("content-type", "")
    md_text = md_resp.text
    assert "# MASTER CUT PRODUCTION - MASTER PRODUCTION PACKAGE" in md_text
    assert "Master Production Bible (MPB) Baseline" in md_text
    assert "Character: Arya" in md_text
    assert "INT. BRIDGE - NIGHT" in md_text
    assert "All systems go." in md_text
    assert "Quality Control Certification" in md_text
