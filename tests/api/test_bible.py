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
