from fastapi.testclient import TestClient


def test_bible_crud_and_lock(client: TestClient, auth_headers: dict[str, str]):
    # 1. Create project
    create_p = client.post("/api/v1/projects", json={"title": "Bible Test Project"}, headers=auth_headers)
    project_id = create_p.json()["data"]["id"]

    # 2. Get initial Bible
    get_b = client.get(f"/api/v1/projects/{project_id}/bible", headers=auth_headers)
    assert get_b.status_code == 200
    b_data = get_b.json()["data"]
    assert b_data["version"] == 1
    assert b_data["is_locked"] is False

    # 3. Update Bible
    update_payload = {
        "style_parameters": {"color_palette": "Teal and Orange", "master_style_code": "#Style 01"},
        "world_rules": {"gravity": "0.8g", "atmosphere": "neon haze"},
    }
    put_b = client.put(f"/api/v1/projects/{project_id}/bible", json=update_payload, headers=auth_headers)
    assert put_b.status_code == 200
    assert put_b.json()["data"]["style_parameters"]["color_palette"] == "Teal and Orange"
    assert put_b.json()["data"]["world_rules"]["gravity"] == "0.8g"

    # 4. Lock Bible (DNA Freeze)
    lock_resp = client.post(
        f"/api/v1/projects/{project_id}/bible/lock",
        json={"approval_notes": "Locked by Showrunner for Scene Gen", "confirm_dna_freeze": True},
        headers=auth_headers,
    )
    assert lock_resp.status_code == 200
    assert lock_resp.json()["data"]["is_locked"] is True
    assert lock_resp.json()["data"]["locked_at"] is not None

    # 5. Verify subsequent updates fail with 400
    blocked_put = client.put(
        f"/api/v1/projects/{project_id}/bible",
        json={"style_parameters": {"color_palette": "Pink"}},
        headers=auth_headers,
    )
    assert blocked_put.status_code == 400
    err_msg = blocked_put.json()["error"]["message"].lower()
    assert "locked" in err_msg


def test_character_and_state_management(client: TestClient, auth_headers: dict[str, str]):
    # 1. Create project
    create_p = client.post("/api/v1/projects", json={"title": "Character Project"}, headers=auth_headers)
    project_id = create_p.json()["data"]["id"]

    # 2. Create Character
    char_payload = {
        "name": "Captain Arya",
        "role": "PROTAGONIST",
        "base_prompt": "35-year-old female pilot with sharp jawline, cybernetic right eye, tactical jumpsuit",
    }
    char_resp = client.post(f"/api/v1/projects/{project_id}/characters", json=char_payload, headers=auth_headers)
    assert char_resp.status_code == 201
    char_data = char_resp.json()["data"]
    character_id = char_data["id"]
    assert char_data["name"] == "Captain Arya"
    assert char_data["role"] == "PROTAGONIST"

    # 3. Add Character State #State 01
    state_payload = {
        "state_code": "#State 01",
        "wardrobe": "Pristine pilot leather jacket, flight harness",
        "injuries_and_wear": "None, freshly groomed",
        "expression_anchor": "Steely determination",
    }
    state_resp = client.post(f"/api/v1/characters/{character_id}/states", json=state_payload, headers=auth_headers)
    assert state_resp.status_code == 201
    s_data = state_resp.json()["data"]
    assert s_data["state_code"] == "#State 01"
    assert s_data["wardrobe"] == "Pristine pilot leather jacket, flight harness"

    # 4. List characters with states
    list_resp = client.get(f"/api/v1/projects/{project_id}/characters", headers=auth_headers)
    assert list_resp.status_code == 200
    chars = list_resp.json()["data"]
    assert len(chars) == 1
    assert chars[0]["name"] == "Captain Arya"
    assert len(chars[0]["states"]) == 1
    assert chars[0]["states"][0]["state_code"] == "#State 01"

    # 5. Verify Sheet Prompts Endpoint (Cards 1-7 Available Immediately)
    prompts_resp = client.get(f"/api/v1/characters/{character_id}/sheet-prompts", headers=auth_headers)
    assert prompts_resp.status_code == 200
    p_data = prompts_resp.json()["data"]
    assert p_data["character_name"] == "Captain Arya"
    assert p_data["dna_seed"] is not None
    prompts_map = p_data["prompts"]

    expected_backdrop = "neutral medium-grey studio backdrop"
    expected_lighting = "butterfly/clamshell studio lighting"

    for slot in ["front", "side", "three_quarter", "back", "tpose", "action", "expression"]:
        assert slot in prompts_map
        item = prompts_map[slot]
        assert item["positive_prompt"]
        assert item["negative_prompt"]
        assert item["copy_ready_text"]
        assert item["recommended_aspect_ratio"] == ("16:9" if slot in ("expression", "front") else "3:4")
        if slot == "expression":
            assert item["width"] == 1344
            assert item["height"] == 768
            assert "3-column by 2-row grid" in item["positive_prompt"]
        elif slot == "front":
            assert item["width"] == 1344
            assert item["height"] == 768
            assert "3-column, 4-panel" in item["positive_prompt"]
        else:
            assert item["width"] == 768
            assert item["height"] == 1024

        # Verify Imagen 3 prose standards: no literal hex codes in positive prompt, clean 5500K lighting & gray backdrop
        assert "#D4D4D4" not in item["positive_prompt"]
        assert expected_backdrop in item["positive_prompt"]
        assert expected_lighting in item["positive_prompt"]

    # Verify Dynamic States Prompts (#State 01 - #State 05)
    assert "states_prompts" in p_data
    states_map = p_data["states_prompts"]
    assert "#State 01" in states_map
    st_item = states_map["#State 01"]
    assert st_item["positive_prompt"]
    assert "#D4D4D4" not in st_item["positive_prompt"]
    assert expected_backdrop in st_item["positive_prompt"]
    assert expected_lighting in st_item["positive_prompt"]
    assert st_item["recommended_aspect_ratio"] == "1:1"
    assert st_item["width"] == 1024
    assert st_item["height"] == 1024

    # 6. Verify Manual Sheet Upload Endpoint (Card 1 Front View)
    import io
    from PIL import Image
    from pathlib import Path
    from backend.app.api.v1.bible import _url_to_local_path

    # Create dummy PNG in memory (2500x1500 to test downscaling to <= 2048)
    dummy_img = Image.new("RGB", (2500, 1500), color=(100, 150, 200))
    buf = io.BytesIO()
    dummy_img.save(buf, format="PNG")
    buf.seek(0)

    upload_resp = client.post(
        f"/api/v1/characters/{character_id}/upload-sheet",
        data={"slot": "front"},
        files={"file": ("test_phone_photo.png", buf.getvalue(), "image/png")},
        headers=auth_headers,
    )
    assert upload_resp.status_code == 200
    u_data = upload_resp.json()
    assert u_data["status"] == "completed"
    assert u_data["slot"] == "front"
    new_url = u_data["image_url"]
    assert new_url.startswith("/api/v1/assets/previews/char_")
    assert u_data["width"] == 2048
    assert u_data["height"] == 1229
    assert u_data["sheet_metadata"]["source"] == "manual_upload"

    # Verify physical file resolution for Google Flow visual anchoring
    local_path = _url_to_local_path(new_url)
    assert local_path is not None
    assert Path(local_path).exists()

    # Clean up test artifact from disk
    try:
        Path(local_path).unlink()
    except Exception:
        pass


def test_character_invalid_uuid_handling(client: TestClient, auth_headers: dict[str, str]):
    # Non-UUID character_id (like "char_1" from template/mock) must return 400 Bad Request, NOT unhandled 500
    res_gen = client.post(
        "/api/v1/characters/char_1/generate-asset",
        json={"target_type": "turnaround", "angle": "front"},
        headers=auth_headers,
    )
    assert res_gen.status_code == 400
    assert "Invalid character_id format" in res_gen.text

    res_prompts = client.get(
        "/api/v1/characters/char_1/sheet-prompts",
        headers=auth_headers,
    )
    assert res_prompts.status_code == 400
    assert "Invalid character_id format" in res_prompts.text


def test_generate_world_props_endpoint(client: TestClient, auth_headers: dict[str, str]):
    # 1. Create a project
    create_p = client.post(
        "/api/v1/projects",
        json={
            "title": "Disgraced: The Last Awakening",
            "settings": {
                "genre": "Epic High Fantasy",
                "synopsis": "An exiled warrior seeks redemption in the frozen northern fjords.",
            },
        },
        headers=auth_headers,
    )
    assert create_p.status_code == 201
    project_id = create_p.json()["data"]["id"]

    # 2. Call generate-world-props endpoint
    gen_resp = client.post(
        f"/api/v1/projects/{project_id}/bible/generate-world-props",
        json={"additional_notes": "Include Norse ruins and ancient runic weapons"},
        headers=auth_headers,
    )
    assert gen_resp.status_code == 200
    res_data = gen_resp.json()
    assert res_data["status"] == "success"
    assert "environments" in res_data
    assert "props" in res_data
    assert len(res_data["environments"]) == 5
    assert len(res_data["props"]) == 5

    # Verify #Env 01 through #Env 05
    for i, env in enumerate(res_data["environments"]):
        assert env["code"] == f"#Env {i + 1:02d}"
        assert env["name"]
        assert env["architecture"]
        assert env["atmosphere"]
        assert env["lighting"]
        assert env["audio"]

    # Verify #Prop 01 through #Prop 05
    for i, prop in enumerate(res_data["props"]):
        assert prop["code"] == f"#Prop {i + 1:02d}"
        assert prop["name"]
        assert prop["material"]
        assert prop["weight"]
        assert prop["action"]

    # 3. Verify MPB GET reflects the generated environments and props
    get_b = client.get(f"/api/v1/projects/{project_id}/bible", headers=auth_headers)
    assert get_b.status_code == 200
    b_rules = get_b.json()["data"]["world_rules"]
    assert len(b_rules["environments"]) == 5
    assert len(b_rules["props"]) == 5

    # 4. Lock Bible and verify generate-world-props is rejected with 400
    lock_resp = client.post(
        f"/api/v1/projects/{project_id}/bible/lock",
        json={"approval_notes": "Locking DNA", "confirm_dna_freeze": True},
        headers=auth_headers,
    )
    assert lock_resp.status_code == 200

    blocked_gen = client.post(
        f"/api/v1/projects/{project_id}/bible/generate-world-props",
        json={},
        headers=auth_headers,
    )
    assert blocked_gen.status_code == 400
    assert "locked" in blocked_gen.json()["error"]["message"].lower()
