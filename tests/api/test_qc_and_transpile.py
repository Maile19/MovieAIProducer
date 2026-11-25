from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from backend.app.domain.director_rag import DirectorRAGClient
from backend.app.services.screenwriter_rag import ScreenwriterRAGClient


def test_real_qc_scene_audit_and_project_summary(client: TestClient, auth_headers: dict[str, str]):
    """Verify /qc/audit-scene/{scene_id} and /projects/{id}/qc/summary compute real dynamic scores."""
    proj_resp = client.post(
        "/api/v1/projects",
        json={
            "title": "Monsoon Courier",
            "target_style_code": "#Style 15",
            "settings": {"synopsis": "A courier crosses a flooded station.", "genre": "Anime Drama"},
        },
        headers=auth_headers,
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["data"]["id"]

    # Empty project summary -> 0 scenes
    empty_sum = client.get(f"/api/v1/projects/{project_id}/qc/summary", headers=auth_headers)
    assert empty_sum.status_code == 200
    assert empty_sum.json()["data"]["total_scenes"] == 0
    assert empty_sum.json()["data"]["continuum_score"] == 0.0

    # Create flawed scene: malformed slugline, 0 shots, no characters
    sc_resp = client.post(
        f"/api/v1/projects/{project_id}/scenes",
        json={
            "act_number": 1,
            "scene_number": 1,
            "slugline": "DOCK",
            "narrative_goal": "Wait",
            "duration_target": 5.0,
        },
        headers=auth_headers,
    )
    assert sc_resp.status_code == 201
    scene_id = sc_resp.json()["data"]["id"]

    audit_low = client.post(f"/api/v1/qc/audit-scene/{scene_id}", headers=auth_headers)
    assert audit_low.status_code == 200
    low_data = audit_low.json()["data"]
    assert low_data["status"] == "FAIL"
    assert low_data["asset_status"] == "pending_asset"
    assert low_data["metrics"]["face_similarity_insightface"] is None
    assert low_data["sub_scores"]["optical_coverage"] == 0
    assert any("0 configured shots" in iss["message"] for iss in low_data["issues"])

    # Add character with Voice DNA + #State 01 + upload/set sheet URL
    ch_resp = client.post(
        f"/api/v1/projects/{project_id}/characters",
        json={
            "name": "Ren Sato",
            "role": "PROTAGONIST",
            "base_prompt": "Young courier in rain-soaked coat, sharp amber eyes, isolated on #D4D4D4",
            "voice_dna_profile": "Clipped understated clauses (~2.0 wps).",
        },
        headers=auth_headers,
    )
    assert ch_resp.status_code == 201
    char_id = ch_resp.json()["data"]["id"]
    client.post(
        f"/api/v1/characters/{char_id}/states",
        json={
            "state_code": "#State 01",
            "state_label": "Baseline",
            "wardrobe": "Indigo waxed canvas coat",
            "injuries_and_wear": "Muddy boots",
            "expression_anchor": "Guarded poise",
        },
        headers=auth_headers,
    )

    # Fix slugline, narrative_goal, add calibrated shot with valid codes, and attach preview
    client.put(
        f"/api/v1/scenes/{scene_id}",
        json={
            "slugline": "EXT. FLOODED DOCK - NIGHT",
            "narrative_goal": "Ren Sato secures the waterproof ledger before the patrol boat arrives.",
            "dialogue": "Keep the lantern shuttered.",
            "camera_code": "#Cam 02",
            "lighting_code": "#Light 06",
            "transition_type": "J_CUT",
            "audio_lead_seconds": 1.0,
        },
        headers=auth_headers,
    )
    client.post(
        f"/api/v1/scenes/{scene_id}/attach-preview",
        json={"preview_url": "/static/previews/test_keyframe.png", "preview_provider": "mock"},
        headers=auth_headers,
    )

    audit_fixed = client.post(f"/api/v1/qc/audit-scene/{scene_id}", headers=auth_headers)
    assert audit_fixed.status_code == 200
    fixed_data = audit_fixed.json()["data"]
    assert fixed_data["overall_score_100"] > low_data["overall_score_100"]
    assert fixed_data["sub_scores"]["narrative_pacing"] == 100
    assert fixed_data["sub_scores"]["optical_coverage"] == 100
    assert fixed_data["sub_scores"]["asset_readiness"] >= 50
    assert fixed_data["asset_status"] in ("partial", "ready")

    # Add over-limit dialogue and verify score drops
    client.put(
        f"/api/v1/scenes/{scene_id}",
        json={
            "dialogue": "One two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty",
        },
        headers=auth_headers,
    )
    audit_overflow = client.post(f"/api/v1/qc/audit-scene/{scene_id}", headers=auth_headers)
    assert audit_overflow.status_code == 200
    overflow_data = audit_overflow.json()["data"]
    assert overflow_data["overall_score_100"] < fixed_data["overall_score_100"]
    assert any("Dialogue overflow" in iss["message"] for iss in overflow_data["issues"])

    # Project QC summary reflects real score
    summary_resp = client.get(f"/api/v1/projects/{project_id}/qc/summary", headers=auth_headers)
    assert summary_resp.status_code == 200
    sum_data = summary_resp.json()["data"]
    assert sum_data["total_scenes"] == 1
    assert sum_data["continuum_score"] == overflow_data["overall_score_100"]


def test_dual_rag_transpile_db_hydration_and_preview_dna(client: TestClient, auth_headers: dict[str, str]):
    """Verify /transpile DB DNA hydration, Dual-RAG (8765+8766), real audio_bridge, and previews.py DNA injection."""
    proj_resp = client.post(
        "/api/v1/projects",
        json={
            "title": "Glass Harbor",
            "target_style_code": "#Style 15",
            "aspect_ratio": "16:9",
            "settings": {"synopsis": "Courier escapes harbor lockdown.", "genre": "Anime Thriller"},
        },
        headers=auth_headers,
    )
    project_id = proj_resp.json()["data"]["id"]

    char_resp = client.post(
        f"/api/v1/projects/{project_id}/characters",
        json={
            "name": "Ren Sato",
            "role": "PROTAGONIST",
            "base_prompt": "Lean archivist with silver-rimmed glasses and rain-matted hair",
            "voice_dna_profile": "Sparse clipped cadence",
        },
        headers=auth_headers,
    )
    char_id = char_resp.json()["data"]["id"]
    client.post(
        f"/api/v1/characters/{char_id}/states",
        json={
            "state_code": "#State 02",
            "state_label": "Weathered",
            "wardrobe": "Charcoal oilskin trench coat",
            "injuries_and_wear": "Bandaged left wrist",
            "expression_anchor": "Narrowed watchful gaze",
        },
        headers=auth_headers,
    )

    sc_resp = client.post(
        f"/api/v1/projects/{project_id}/scenes",
        json={
            "act_number": 2,
            "scene_number": 14,
            "slugline": "EXT. HARBOR LOCK - NIGHT",
            "narrative_goal": "Ren Sato slips past the floodlights along the wet catwalk.",
            "duration_target": 10.0,
        },
        headers=auth_headers,
    )
    scene_id = sc_resp.json()["data"]["id"]
    sh_resp = client.post(
        f"/api/v1/scenes/{scene_id}/shots",
        json={
            "shot_number": 1,
            "camera_code": "#Cam 07",
            "lens_code": "#Lens 02",
            "comp_code": "#Comp 05",
            "light_code": "#Light 06",
            "dialogue": "Stay below the rail.",
            "transition_type": "J_CUT",
            "fg_bg_layers": {"audio_lead_seconds": 1.4},
        },
        headers=auth_headers,
    )
    shot_id = sh_resp.json()["data"]["id"]

    mock_dir = {
        "director_context": "",
        "grammars": [],
        "shots": [{"shot_id": "d1", "visual_cues": "Wet asphalt reflections under sodium glow"}],
    }
    mock_sw = {
        "prompt_block": "[SCREENWRITER CRAFT] Subtext micro-turn.",
        "writing_directives": {"action_beat_grammar": "Lean silhouette tension before turn"},
        "style_family": "anime_2d",
        "items": [{"title": "Harbor Stealth", "subtext_visual_cue": "Knuckles whitening around brass latch"}],
    }

    with (
        patch.object(DirectorRAGClient, "retrieve", new=AsyncMock(return_value=mock_dir)) as m_dir,
        patch.object(ScreenwriterRAGClient, "retrieve_scene_craft", new=AsyncMock(return_value=mock_sw)) as m_sw,
    ):
        tr_resp = client.post(
            "/api/v1/transpile",
            json={
                "provider_target": "seedance",
                "project_id": project_id,
                "scene_id": scene_id,
                "shot_id": shot_id,
            },
            headers=auth_headers,
        )
        assert tr_resp.status_code == 200
        assert m_dir.called and m_sw.called
        tr_data = tr_resp.json()["data"]
        pos = tr_data["positive_prompt"]
        assert "Ren Sato" in pos
        assert "silver-rimmed glasses" in pos
        assert "Charcoal oilskin trench coat" in pos
        assert "Lean silhouette tension before turn" in pos
        assert tr_data["metadata"]["audio_bridge"]["transition_type"] == "J_CUT"
        assert tr_data["metadata"]["audio_bridge"]["j_cut_offset_seconds"] == -1.4
        assert tr_data["metadata"]["continuity_sources"]["director_rag_hits"] == 1
        assert tr_data["metadata"]["continuity_sources"]["screenwriter_rag_hits"] == 1
        assert "google_flow" in tr_data["compiled_engines"]
        assert "kling" in tr_data["compiled_engines"]
        assert "seedance" in tr_data["compiled_engines"]

        # Verify previews.py injects character DNA & active state into generated prompt
        sc_prev = client.post(
            f"/api/v1/scenes/{scene_id}/generate-preview",
            json={"provider": "mock"},
            headers=auth_headers,
        )
        assert sc_prev.status_code == 200
        sc_prompt = sc_prev.json()["data"]["prompt"]
        assert "silver-rimmed glasses" in sc_prompt
        assert "Charcoal oilskin trench coat" in sc_prompt

        sh_prev = client.post(
            f"/api/v1/shots/{shot_id}/generate-preview",
            json={"provider": "mock"},
            headers=auth_headers,
        )
        assert sh_prev.status_code == 200
        sh_prompt = sh_prev.json()["data"]["prompt"]
        assert "silver-rimmed glasses" in sh_prompt
        assert "Charcoal oilskin trench coat" in sh_prompt
