import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.app.domain.screenwriter import (
    PolyaScreenwriterEngine,
    SceneBlueprintItem,
    ActBlueprintData,
    MasterTreatmentData,
    ActTreatmentItem,
    get_act_bounds,
    _determine_scene_duration,
)


def test_get_act_bounds_scaling():
    """Verify 4-Act quartile boundary calculations for 50, 100, 200, 420, and 450 scenes."""
    # 50 scenes
    b50 = get_act_bounds(50)
    assert b50[0] == (1, 12)
    assert b50[1] == (13, 25)
    assert b50[2] == (26, 38)
    assert b50[3] == (39, 50)
    assert sum(end - start + 1 for start, end in b50) == 50

    # 100 scenes
    b100 = get_act_bounds(100)
    assert b100[0] == (1, 25)
    assert b100[1] == (26, 50)
    assert b100[2] == (51, 75)
    assert b100[3] == (76, 100)
    assert sum(end - start + 1 for start, end in b100) == 100

    # 200 scenes
    b200 = get_act_bounds(200)
    assert b200[0] == (1, 50)
    assert b200[1] == (51, 100)
    assert b200[2] == (101, 150)
    assert b200[3] == (151, 200)
    assert sum(end - start + 1 for start, end in b200) == 200

    # 420 scenes
    b420 = get_act_bounds(420)
    assert b420[0] == (1, 105)
    assert b420[1] == (106, 210)
    assert b420[2] == (211, 315)
    assert b420[3] == (316, 420)
    assert sum(end - start + 1 for start, end in b420) == 420

    # 450 scenes
    b450 = get_act_bounds(450)
    assert b450[0] == (1, 112)
    assert b450[1] == (113, 225)
    assert b450[2] == (226, 338)
    assert b450[3] == (339, 450)
    assert sum(end - start + 1 for start, end in b450) == 450


def test_determine_scene_duration_pacing():
    """Verify pacing rules: dynamic vs flat modes."""
    # Dynamic mode: Act I & III have breathing room (15s), Act II & IV are tension/action (10s)
    assert _determine_scene_duration(1, "dynamic") == 15.0
    assert _determine_scene_duration(2, "dynamic") == 10.0
    assert _determine_scene_duration(3, "dynamic") == 15.0
    assert _determine_scene_duration(4, "dynamic") == 10.0
    assert _determine_scene_duration(5, "dynamic") == 15.0

    # Flat modes
    assert _determine_scene_duration(1, "flat_5s") == 5.0
    assert _determine_scene_duration(2, "flat_10s") == 10.0
    assert _determine_scene_duration(3, "flat_15s") == 15.0


def test_generate_master_treatment_with_cast_and_bible():
    """Verify treatment generation correctly constructs prompt with Cast & Bible context."""
    engine = PolyaScreenwriterEngine()

    characters = [
        {"name": "Arya Vance", "role": "Protagonist", "narrative_summary": "Rogue neural runner seeking redemption."},
        {"name": "Kaelen Voss", "role": "Antagonist", "narrative_summary": "Syndicate enforcer obsessed with order."},
    ]
    project_ctx = {
        "title": "Neon Syndicate",
        "logline": "A rogue runner uncovers a neural conspiracy.",
        "genre": "Cyberpunk Thriller",
        "visual_tone": "High contrast neon and perpetual rain",
    }

    mock_treatment_data = {
        "title": "Neon Syndicate",
        "logline": "A rogue runner uncovers a neural conspiracy in Neo Jakarta.",
        "theme": "Free will vs artificial destiny",
        "dramatic_premise": "Arya struggles between her syndicate programming and human empathy.",
        "total_scenes": 50,
        "acts": [
            {"act_number": 1, "act_title": "Ordinary Reality", "start_scene": 1, "end_scene": 12, "dramatic_goal": "Arya uncovers anomaly", "key_beat": "Threshold crossing"},
            {"act_number": 2, "act_title": "Rising Syndicate", "start_scene": 13, "end_scene": 25, "dramatic_goal": "Kaelen pursues Arya", "key_beat": "Midpoint betrayal"},
            {"act_number": 3, "act_title": "The Abyss", "start_scene": 26, "end_scene": 38, "dramatic_goal": "All seems lost", "key_beat": "Breakthrough revelation"},
            {"act_number": 4, "act_title": "Final Convergence", "start_scene": 39, "end_scene": 50, "dramatic_goal": "Climactic duel with Kaelen", "key_beat": "Master resolution"},
        ],
    }

    captured_messages = None

    async def fake_call_llm(messages: list[dict[str, str]], retry_on_parse_error: bool = True) -> dict:
        nonlocal captured_messages
        captured_messages = messages
        return dict(mock_treatment_data)

    async def run():
        with patch.object(engine, "_call_llm", side_effect=fake_call_llm):
            return await engine.generate_master_treatment(
                project_title="Neon Syndicate",
                premise="Arya fights the Syndicate",
                total_scenes=50,
                characters=characters,
                project_context=project_ctx,
            )

    result = asyncio.run(run())

    assert not result.get("used_fallback")
    assert result["logline"] == mock_treatment_data["logline"]
    assert len(result["acts"]) == 4
    assert result["acts"][0]["act_number"] == 1
    # Verify cast & bible appeared in prompt
    assert captured_messages is not None
    user_prompt = captured_messages[1]["content"]
    assert "Arya Vance" in user_prompt
    assert "Kaelen Voss" in user_prompt
    assert "High contrast neon" in user_prompt


def test_generate_act_scenes_chunking_and_intra_act_handover():
    """Verify intra-act sub-chunking (>18 scenes) passes last 3 scenes as context to next chunk."""
    engine = PolyaScreenwriterEngine()

    characters = [{"name": "Arya Vance", "role": "Protagonist"}]
    messages_received = []

    # Simulate generating Act 1 of a 100-scene project (Act 1 = scenes 1 to 25 -> Chunk 1: 1-18, Chunk 2: 19-25)
    async def fake_call_llm(messages: list[dict[str, str]], retry_on_parse_error: bool = True) -> dict:
        messages_received.append(messages)
        user_prompt = messages[1]["content"]
        # Determine if this is chunk 1 or chunk 2 from prompt
        if "Scene 1 to Scene 18" in user_prompt:
            scenes = [
                {
                    "scene_number": i,
                    "slugline": f"EXT. SECTOR {i} - NIGHT",
                    "narrative_goal": f"Beat {i} progression",
                    "primary_character": "Arya Vance",
                    "dialogue": f"Lines for scene {i}.",
                    "duration_seconds": 15.0,
                }
                for i in range(1, 19)
            ]
        else:
            scenes = [
                {
                    "scene_number": i,
                    "slugline": f"EXT. SECTOR {i} - DAWN",
                    "narrative_goal": f"Beat {i} progression",
                    "primary_character": "Arya Vance",
                    "dialogue": f"Follow-up lines for scene {i}.",
                    "duration_seconds": 15.0,
                }
                for i in range(19, 26)
            ]
        return {
            "act_number": 1,
            "act_title": "Setup",
            "act_summary": "Arya journeys into the deep network.",
            "scenes": scenes,
        }

    async def run():
        with patch.object(engine, "_call_llm", side_effect=fake_call_llm):
            return await engine.generate_act_scenes(
                act_number=1,
                total_scenes=100,
                duration_mode="dynamic",
                premise="Arya's ascent",
                characters=characters,
            )

    result = asyncio.run(run())

    assert not result.get("used_fallback")
    assert len(result["scenes"]) == 25
    assert result["scenes"][0]["scene_number"] == 1
    assert result["scenes"][-1]["scene_number"] == 25
    # Two LLM calls were made due to chunking
    assert len(messages_received) == 2
    # Verify second chunk received intra-act handover of the preceding scenes
    second_prompt = messages_received[1][1]["content"]
    assert "Direct Narrative Handover from previous scenes" in second_prompt
    assert "Scene 18" in second_prompt


def test_json_clean_and_repair():
    """Verify dirty Markdown fences and 1x auto-repair for broken JSON."""
    engine = PolyaScreenwriterEngine()

    # 1. Dirty markdown JSON with trailing comma
    dirty_text = """```json
    {
      "logline": "Repaired logline",
      "theme": "Honor",
      "acts": [
        {"act_number": 1, "title": "Act 1", "dramatic_arc": "Start", "key_turning_point": "Break"},
      ]
    }
    ```"""
    parsed = engine._clean_and_parse_json(dirty_text)
    assert parsed is not None
    assert parsed["logline"] == "Repaired logline"

    # 2. Repair via LLM on broken JSON
    call_count = 0

    mock_resp1 = MagicMock()
    mock_resp1.status_code = 200
    mock_resp1.json.return_value = {
        "choices": [{"message": {"content": "This is completely broken {not json"}}]
    }

    mock_resp2 = MagicMock()
    mock_resp2.status_code = 200
    mock_resp2.json.return_value = {
        "choices": [{"message": {"content": json.dumps({"repaired": True, "value": 42})}}]
    }

    async def fake_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_resp1
        return mock_resp2

    async def run():
        with patch("httpx.AsyncClient.post", side_effect=fake_post):
            return await engine._call_llm([{"role": "user", "content": "Hello"}], retry_on_parse_error=True)

    repaired_res = asyncio.run(run())
    assert repaired_res.get("repaired") is True
    assert call_count == 2


def test_blueprint_api_treatment_and_generate_act(client: TestClient, auth_headers: dict[str, str]):
    """Verify backend endpoints /blueprint/treatment and /blueprint/generate-act end-to-end."""
    # 1. Create project
    create_p = client.post("/api/v1/projects", json={"title": "Polya Screenplay Feature"}, headers=auth_headers)
    assert create_p.status_code == 201
    project_id = create_p.json()["data"]["id"]

    # 2. Seed a character
    char_resp = client.post(
        f"/api/v1/projects/{project_id}/characters",
        json={
            "name": "Detective Vane",
            "role": "PROTAGONIST",
            "base_prompt": "Cybernetic detective in worn trenchcoat with neon ocular implant.",
            "narrative_summary": "Cynical detective on cybernetic investigation.",
        },
        headers=auth_headers,
    )
    assert char_resp.status_code == 201

    mock_treatment = {
        "title": "Polya Screenplay Feature",
        "logline": "Detective Vane investigates a rogue intelligence.",
        "theme": "Free will in the machine age",
        "dramatic_premise": "Vane uncovers a shadow AI network.",
        "total_scenes": 50,
        "acts": [
            {"act_number": 1, "act_title": "Setup", "start_scene": 1, "end_scene": 12, "dramatic_goal": "Discovery", "key_beat": "Inciting Incident"},
            {"act_number": 2, "act_title": "Trials", "start_scene": 13, "end_scene": 25, "dramatic_goal": "Escalation", "key_beat": "Midpoint"},
            {"act_number": 3, "act_title": "Crisis", "start_scene": 26, "end_scene": 38, "dramatic_goal": "Dark Night", "key_beat": "Climax Turn"},
            {"act_number": 4, "act_title": "Resolution", "start_scene": 39, "end_scene": 50, "dramatic_goal": "Final Duel", "key_beat": "Denouement"},
        ],
    }

    mock_act_scenes = {
        "act_number": 1,
        "act_title": "Setup",
        "act_summary": "Detective Vane enters the neural core.",
        "scenes": [
            {
                "scene_number": i,
                "slugline": f"INT. NEON HUB {i} - NIGHT",
                "narrative_goal": f"Investigate node {i}",
                "primary_character": "Detective Vane",
                "dialogue": f"Tracing signal {i} to the core.",
                "duration_seconds": 15.0,
            }
            for i in range(1, 13)
        ],
    }

    async def fake_call_llm(messages: list[dict[str, str]], retry_on_parse_error: bool = True) -> dict:
        user_content = messages[-1]["content"] if messages else ""
        if "Treatment" in user_content or "Story Treatment" in user_content:
            return dict(mock_treatment)
        return dict(mock_act_scenes)

    with patch.object(PolyaScreenwriterEngine, "_call_llm", side_effect=fake_call_llm):
        # 3. Call generate blueprint treatment
        treat_resp = client.post(
            f"/api/v1/projects/{project_id}/blueprint/treatment",
            json={
                "total_scenes": 50,
                "duration_mode": "dynamic",
                "premise": "Detective Vane investigates a rogue intelligence.",
                "clear_existing": True,
            },
            headers=auth_headers,
        )
        assert treat_resp.status_code == 200
        treat_data = treat_resp.json()["data"]
        assert "logline" in treat_data
        assert len(treat_data.get("acts", [])) == 4

        # 4. Generate Act 1
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
        act1_data = act1_resp.json()["data"]
        assert act1_data["act_number"] == 1
        assert act1_data["scenes_generated"] == 12  # Act 1 of 50 scenes is 12 scenes
        assert act1_data["shots_generated"] >= 12

    # 5. Verify scenes in DB
    scenes_resp = client.get(f"/api/v1/projects/{project_id}/scenes?act=1", headers=auth_headers)
    assert scenes_resp.status_code == 200
    scenes = scenes_resp.json()["data"]
    assert len(scenes) == 12
    assert scenes[0]["act_number"] == 1
    assert scenes[0]["scene_number"] == 1
    # Check that shots were auto-split and primary dialogue exists
    first_scene_id = scenes[0]["id"]
    shots_resp = client.get(f"/api/v1/projects/{project_id}/scenes/{first_scene_id}/shots", headers=auth_headers)
    assert shots_resp.status_code == 200
    shots = shots_resp.json()["data"]
    assert len(shots) >= 1


def test_get_act_bounds_multi_structures_scaling():
    """Verify get_act_bounds() produces strictly zero gap, zero overlap, and exact sum for all 4 structures (50-450 scenes)."""
    structures = ["3_act", "4_act", "youtube_viral", "5_act"]
    scales = [50, 100, 150, 200, 300, 420, 450]

    for st in structures:
        expected_acts = 3 if st == "3_act" else (5 if st == "5_act" else 4)
        for total in scales:
            bounds = get_act_bounds(total, structure_type=st)
            assert len(bounds) == expected_acts, f"Expected {expected_acts} acts for {st}, got {len(bounds)}"
            assert bounds[0][0] == 1, f"First act must start at 1 for {st} ({total} scenes)"
            assert bounds[-1][1] == total, f"Last act must end at {total} for {st} ({total} scenes)"

            total_calculated = 0
            for i in range(len(bounds)):
                start, end = bounds[i]
                assert start <= end, f"Inverted bounds {start} > {end} in {st} ({total} scenes)"
                total_calculated += (end - start + 1)
                if i > 0:
                    prev_start, prev_end = bounds[i - 1]
                    assert start == prev_end + 1, f"Gap or overlap detected between act {i} and {i+1} in {st}: {prev_end} -> {start}"

            assert total_calculated == total, f"Total scene sum mismatch for {st} ({total} scenes): got {total_calculated}"


def test_strict_llm_mode_no_mock_fallback_on_failure():
    """Verify Strict LLM Mode raises RuntimeError on LLM failure and never returns hardcoded sci-fi/distopian mock strings."""
    engine = PolyaScreenwriterEngine()

    async def failing_llm(*args, **kwargs):
        raise RuntimeError("OpenAI connection timed out after 120s")

    with patch.object(engine, "_call_llm", side_effect=failing_llm):
        # 1. generate_master_treatment must fail with RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(
                engine.generate_master_treatment(
                    project_title="Strict Test",
                    premise="Failure scenario",
                    total_scenes=50,
                )
            )
        err_msg = str(exc_info.value)
        assert "timed out" in err_msg or "failed" in err_msg
        # Assert forbidden legacy mock phrases never appear
        assert "World Ordinary Life" not in err_msg
        assert "Sensor perimeter" not in err_msg
        assert "defensive grid" not in err_msg

        # 2. generate_act_scenes must fail with RuntimeError
        with pytest.raises(RuntimeError) as exc_info2:
            asyncio.run(
                engine.generate_act_scenes(
                    act_number=1,
                    total_scenes=50,
                    duration_mode="dynamic",
                    premise="Failure scenario",
                )
            )
        err_msg2 = str(exc_info2.value)
        assert "timed out" in err_msg2 or "failed" in err_msg2
        assert "World Ordinary Life" not in err_msg2
        assert "Sensor perimeter" not in err_msg2


def test_analyze_narrative_structure():
    """Verify analyze_narrative_structure() returns recommendation, strategic rationale, and all 4 structure options."""
    engine = PolyaScreenwriterEngine()

    project_context = {
        "title": "Cosmic Pranks",
        "synopsis": "A clumsy space alien plays harmless slapstick pranks across the galaxy on YouTube shorts.",
        "genre_tone": "Kids Animation Slapstick",
        "master_style_code": "#Style 01",
        "total_scenes": 50,
    }

    result = engine.analyze_narrative_structure(project_context)

    assert result["recommended_structure"] == "youtube_viral"
    assert "retensi audiens" in result["strategic_rationale"] or "YouTube Viral" in result["strategic_rationale"]
    assert len(result["options"]) == 4

    opt_keys = {opt["structure_type"] for opt in result["options"]}
    assert opt_keys == {"3_act", "4_act", "youtube_viral", "5_act"}

    yt_opt = next(o for o in result["options"] if o["structure_type"] == "youtube_viral")
    assert yt_opt["acts_count"] == 4
    assert len(yt_opt["act_labels"]) == 4

    five_opt = next(o for o in result["options"] if o["structure_type"] == "5_act")
    assert five_opt["acts_count"] == 5
    assert len(five_opt["act_labels"]) == 5


def test_blueprint_recommend_structure_api(client: TestClient, auth_headers: dict[str, str]):
    """Verify POST /api/v1/projects/{project_id}/blueprint/recommend-structure returns 200 with advisory data."""
    # 1. Create project with intimate indie drama synopsis
    create_p = client.post(
        "/api/v1/projects",
        json={
            "title": "Polya Advisory Test",
            "settings": {
                "synopsis": "An intimate indie drama character study exploring forgiveness and redemption.",
                "genre": "Indie Drama",
            },
        },
        headers=auth_headers,
    )
    assert create_p.status_code == 201
    project_id = create_p.json()["data"]["id"]

    resp = client.post(
        f"/api/v1/projects/{project_id}/blueprint/recommend-structure",
        json={"total_scenes": 100},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["recommended_structure"] == "3_act"
    assert "3 Babak" in data["strategic_rationale"]
    assert len(data["options"]) == 4


def test_legacy_instant_blueprint_deprecated_400(client: TestClient, auth_headers: dict[str, str]):
    """Verify legacy instant_structural on POST /projects/{project_id}/scenes returns 400 Bad Request."""
    create_p = client.post("/api/v1/projects", json={"title": "Legacy Blueprint Test"}, headers=auth_headers)
    assert create_p.status_code == 201
    project_id = create_p.json()["data"]["id"]

    resp = client.post(
        f"/api/v1/projects/{project_id}/scenes",
        json={"generate_blueprint": True, "total_scenes": 50},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    err_text = (
        resp.json().get("error", {}).get("message", "")
        or resp.json().get("detail", "")
        or resp.text
    )
    assert "deprecated" in err_text.lower()
    assert "/blueprint/" in err_text
