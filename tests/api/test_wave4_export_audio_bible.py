import xml.etree.ElementTree as ET
from fastapi.testclient import TestClient


def test_wave4_bible_editing_export_audio_script_and_subtitles(client: TestClient, auth_headers: dict[str, str]):
    """Verify Wave 4: Character PUT Voice DNA/Narrative Summary, World/Props edit, full export, SSML audio script, and SRT/VTT subtitles."""
    # 1. Create project with Master Story Treatment in settings
    treatment_data = {
        "title": "Monsoon Protocol",
        "logline": "A courier smuggles an encrypted brass lens across a flooded rail network.",
        "theme": "Memory vs. Erasure",
        "dramatic_premise": "Ren must risk exposure to deliver the final testimony before the sluice gates seal.",
        "structure_type": "4_act",
        "structure_name": "Hollywood 4-Act Structure",
        "cold_open_30s": {"enabled": True, "hook_preview": "Water rises over the brass seal at dawn."},
        "acts": [
            {"act_number": 1, "act_title": "Act I: Setup", "start_scene": 1, "end_scene": 12, "dramatic_goal": "Accept the parcel", "key_beat": "Storm hits"},
            {"act_number": 2, "act_title": "Act II-A: Trials", "start_scene": 13, "end_scene": 25, "dramatic_goal": "Cross Canal Lock", "key_beat": "Ambush"},
            {"act_number": 3, "act_title": "Act II-B: Crisis", "start_scene": 26, "end_scene": 38, "dramatic_goal": "Sluice Failure", "key_beat": "Betrayal"},
            {"act_number": 4, "act_title": "Act III: Climax", "start_scene": 39, "end_scene": 50, "dramatic_goal": "Deliver Ledger", "key_beat": "Dawn Gate"},
        ],
        "act_summaries": {"1": "Ren departs the central archive."},
    }
    proj_resp = client.post(
        "/api/v1/projects",
        json={
            "title": "Monsoon Protocol",
            "target_style_code": "#Style 15",
            "settings": {"synopsis": treatment_data["logline"], "genre": "Anime Thriller", "treatment": treatment_data},
        },
        headers=auth_headers,
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["data"]["id"]

    # 2. Create character & verify PUT updates narrative_summary and voice_dna_profile
    ch_resp = client.post(
        f"/api/v1/projects/{project_id}/characters",
        json={
            "name": "Ren Sato",
            "role": "PROTAGONIST",
            "base_prompt": "Lean archivist in oilskin coat, isolated on #D4D4D4",
            "narrative_summary": "Initial bio",
            "voice_dna_profile": "Initial voice",
        },
        headers=auth_headers,
    )
    assert ch_resp.status_code == 201
    char_id = ch_resp.json()["data"]["id"]

    put_ch = client.put(
        f"/api/v1/projects/{project_id}/characters/{char_id}",
        json={
            "name": "Ren Sato",
            "role": "PROTAGONIST",
            "narrative_summary": "Guarded archivist haunted by the drowned district.",
            "voice_dna_profile": "Measured clipped clauses (~2.1 wps), calm under threat.",
        },
        headers=auth_headers,
    )
    assert put_ch.status_code == 200
    assert put_ch.json()["data"]["narrative_summary"] == "Guarded archivist haunted by the drowned district."
    assert put_ch.json()["data"]["voice_dna_profile"] == "Measured clipped clauses (~2.1 wps), calm under threat."

    # Add #State 01 & #State 02 with emotional anchors
    client.post(
        f"/api/v1/characters/{char_id}/states",
        json={
            "state_code": "#State 01",
            "state_label": "Baseline",
            "wardrobe": "Indigo trench coat",
            "injuries_and_wear": "Dry hem",
            "expression_anchor": "Stoic vigilance",
        },
        headers=auth_headers,
    )
    client.post(
        f"/api/v1/characters/{char_id}/states",
        json={
            "state_code": "#State 02",
            "state_label": "Weathered",
            "wardrobe": "Soaked oilskin coat",
            "injuries_and_wear": "Bandaged wrist",
            "expression_anchor": "Urgent panic",
        },
        headers=auth_headers,
    )

    # 3. Verify Bible PUT persists edited World Environments & Hero Props
    bible_put = client.put(
        f"/api/v1/projects/{project_id}/bible",
        json={
            "world_rules": {
                "environments": [
                    {
                        "code": "#Env 01",
                        "name": "Flooded Canal Lock",
                        "lighting_code": "#Light 06",
                        "architecture": "Rusting sluice gates over black water",
                        "atmosphere": "Cold mist & sodium glow",
                        "lighting_and_audio": "Sodium vapor + lapping water echo",
                    }
                ],
                "props": [
                    {
                        "code": "#Prop 01",
                        "name": "Sealed Brass Lens",
                        "owner_character": "Ren Sato",
                        "material_and_wear": "Tarnished brass cylinder with etched serial",
                        "narrative_utility": "Holds the city's unredacted flood ledger",
                        "action": "Twists open under pressure",
                    }
                ],
            }
        },
        headers=auth_headers,
    )
    assert bible_put.status_code == 200
    bible_get = client.get(f"/api/v1/projects/{project_id}/bible", headers=auth_headers)
    assert bible_get.json()["data"]["world_rules"]["environments"][0]["name"] == "Flooded Canal Lock"
    assert bible_get.json()["data"]["world_rules"]["props"][0]["name"] == "Sealed Brass Lens"

    # 4. Seed 3 scenes/shots testing J_CUT clamping (>=0.0), XML escaping (&, <, >), L_CUT trail, and SFX cue
    sc1 = client.post(
        f"/api/v1/projects/{project_id}/scenes",
        json={"act_number": 1, "scene_number": 1, "slugline": "EXT. CANAL LOCK - NIGHT", "narrative_goal": "Ren Sato checks the lock.", "duration_target": 5.0},
        headers=auth_headers,
    ).json()["data"]
    client.post(
        f"/api/v1/scenes/{sc1['id']}/shots",
        json={
            "shot_number": 1,
            "duration_seconds": 5.0,
            "dialogue": "Lock & seal <sector 4> > now.",
            "transition_type": "J_CUT",
            "fg_bg_layers": {"audio_lead_seconds": 1.5},
        },
        headers=auth_headers,
    )

    sc2 = client.post(
        f"/api/v1/projects/{project_id}/scenes",
        json={"act_number": 2, "scene_number": 2, "slugline": "INT. GATEHOUSE - NIGHT", "narrative_goal": "Ren Sato confronts the floodgate.", "duration_target": 10.0},
        headers=auth_headers,
    ).json()["data"]
    client.post(
        f"/api/v1/scenes/{sc2['id']}/shots",
        json={
            "shot_number": 1,
            "duration_seconds": 5.0,
            "dialogue": "Hold the line.",
            "transition_type": "J_CUT",
            "fg_bg_layers": {"audio_lead_seconds": 1.2},
        },
        headers=auth_headers,
    )
    client.post(
        f"/api/v1/scenes/{sc2['id']}/shots",
        json={
            "shot_number": 2,
            "duration_seconds": 5.0,
            "dialogue": "[SFX: Heavy iron sluice gate slams shut]",
            "transition_type": "L_CUT",
            "fg_bg_layers": {"audio_lead_seconds": 0.8},
        },
        headers=auth_headers,
    )

    # 5. Full-fidelity /export (JSON & Markdown)
    exp_json = client.get(f"/api/v1/projects/{project_id}/export?format=json", headers=auth_headers)
    assert exp_json.status_code == 200
    ej = exp_json.json()["data"]
    assert ej["treatment"]["logline"] == treatment_data["logline"]
    assert ej["treatment"]["theme"] == "Memory vs. Erasure"
    assert ej["characters"][0]["voice_dna_profile"] == "Measured clipped clauses (~2.1 wps), calm under threat."
    assert ej["characters"][0]["narrative_summary"] == "Guarded archivist haunted by the drowned district."
    assert ej["scenes"][0]["speaking_character"] == "Ren Sato"
    assert ej["scenes"][0]["transition_type"] == "J_CUT"
    assert ej["scenes"][0]["audio_lead_seconds"] == 1.5

    exp_md = client.get(f"/api/v1/projects/{project_id}/export?format=markdown", headers=auth_headers)
    assert exp_md.status_code == 200
    md_text = exp_md.text
    assert "Master Story Treatment & Beat Sheet" in md_text
    assert treatment_data["logline"] in md_text
    assert "Measured clipped clauses (~2.1 wps)" in md_text
    assert "Guarded archivist haunted by the drowned district." in md_text
    assert "Lock & seal" in md_text

    # 6. /audio-script (JSON + SSML XML + Markdown)
    as_json = client.get(f"/api/v1/projects/{project_id}/audio-script?format=json", headers=auth_headers)
    assert as_json.status_code == 200
    cues = as_json.json()["data"]["cues"]
    assert len(cues) == 3
    # Cue 1: shot_start=0.0, J_CUT 1.5s -> clamped >= 0.0
    assert cues[0]["start_seconds"] == 0.0
    assert cues[0]["speaker"] == "Ren Sato"
    assert "Measured clipped clauses" in cues[0]["voice_profile"]
    assert "&amp;" in cues[0]["ssml"] and "&lt;sector 4&gt;" in cues[0]["ssml"]
    # Cue 2: shot_start=5.0, J_CUT 1.2s -> 3.8s
    assert cues[1]["start_seconds"] == 3.8
    assert cues[1]["active_state_code"] == "#State 02"
    assert cues[1]["emotion_cue"] == "Urgent panic"
    # Cue 3: shot_end=15.0, L_CUT 0.8s -> 15.8s
    assert cues[2]["is_sfx"] is True
    assert cues[2]["end_seconds"] == 15.8

    as_ssml = client.get(f"/api/v1/projects/{project_id}/audio-script?format=ssml", headers=auth_headers)
    assert as_ssml.status_code == 200
    # Verify valid XML parsing of full SSML output
    ET.fromstring(as_ssml.text)

    as_md = client.get(f"/api/v1/projects/{project_id}/audio-script?format=markdown", headers=auth_headers)
    assert as_md.status_code == 200
    assert "AUDIO & TTS DELIVERY SCRIPT" in as_md.text

    # 7. /subtitles (.srt and .vtt, with include_sfx=false vs include_sfx=true)
    srt_no_sfx = client.get(f"/api/v1/projects/{project_id}/subtitles?format=srt&include_sfx=false", headers=auth_headers)
    assert srt_no_sfx.status_code == 200
    assert "00:00:00,000 -->" in srt_no_sfx.text
    assert "00:00:03,800 -->" in srt_no_sfx.text
    assert "Heavy iron sluice gate" not in srt_no_sfx.text

    srt_with_sfx = client.get(f"/api/v1/projects/{project_id}/subtitles?format=srt&include_sfx=true", headers=auth_headers)
    assert srt_with_sfx.status_code == 200
    assert "[SFX: Heavy iron sluice gate slams shut]" in srt_with_sfx.text

    vtt_resp = client.get(f"/api/v1/projects/{project_id}/subtitles?format=vtt&include_sfx=false", headers=auth_headers)
    assert vtt_resp.status_code == 200
    assert vtt_resp.text.startswith("WEBVTT")
    assert "00:00:03.800 -->" in vtt_resp.text
    assert "<v Ren Sato>" in vtt_resp.text
