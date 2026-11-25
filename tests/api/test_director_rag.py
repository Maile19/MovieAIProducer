from unittest.mock import AsyncMock, patch
import httpx
import pytest

from backend.app.domain.director_rag import (
    DirectorRAGClient,
    map_target_engine,
    normalize_style_code,
    resolve_style_filter,
)
from backend.app.domain.screenwriter import PolyaScreenwriterEngine
from backend.app.domain.transpiler import LivePromptTranspiler


def _mock_rag_payload() -> dict:
    return {
        "director_context": "### POLIA AI DIRECTOR RETRIEVED FEW-SHOT CONTEXT",
        "grammars": [
            {
                "grammar_id": "seq_cyber_01",
                "title": "Rain Alley Pursuit",
                "similarity": 0.91,
                "director_master_rule": "Hold reverse angles across neon reflections before reveal",
                "lens_progression": "#Lens 05 -> #Lens 01",
                "lighting_evolution": "#Light 06 -> #Light 03",
                "pacing_curve": "Measured 4.5s tracking tightening to 1.8s cuts",
                "audio_bridge_strategy": "Rain ambience J-cut 1.2s prior to door breach",
                "dramatic_mini_arcs": [
                    {
                        "beat_range": "1-3",
                        "narrative_intent": "Pursuit",
                        "visual_strategy": "Telephoto lateral tracking",
                    }
                ],
            }
        ],
        "shots": [
            {
                "shot_id": "vid_001_shot_001",
                "similarity": 0.89,
                "genre": "Cyberpunk",
                "engine": "veo",
                "matrix_codes": {
                    "camera_code": "#Cam 18",
                    "lens_code": "#Lens 01",
                    "light_code": "#Light 06",
                },
                "positive_prompt": "Anamorphic rain-slicked neon tracking shot with crisp specular pavement reflections",
                "negative_prompt": "cartoon, plastic skin",
            }
        ],
    }


@pytest.mark.anyio
async def test_director_rag_client_graceful_fallbacks():
    # 1. Disabled flag returns empty without network call
    disabled_client = DirectorRAGClient(enabled=False)
    res_disabled = await disabled_client.retrieve("Hero walks into rain", genre="Cyberpunk")
    assert res_disabled == {"director_context": "", "shots": [], "grammars": []}

    # 2. Timeout falls back cleanly
    timeout_client = DirectorRAGClient(enabled=True, base_url="http://127.0.0.1:8765", timeout_sec=0.5)
    with patch("backend.app.domain.director_rag.httpx.AsyncClient.post", side_effect=httpx.ReadTimeout("timed out")):
        res_timeout = await timeout_client.retrieve("Hero walks into rain", genre="Cyberpunk")
        assert res_timeout == {"director_context": "", "shots": [], "grammars": []}

    # 3. Connection error falls back cleanly
    with patch("backend.app.domain.director_rag.httpx.AsyncClient.post", side_effect=httpx.ConnectError("refused")):
        res_conn = await timeout_client.retrieve("Hero walks into rain", genre="Cyberpunk")
        assert res_conn == {"director_context": "", "shots": [], "grammars": []}

    # 4. Empty KB response normalizes cleanly
    empty_resp = httpx.Response(200, json={"director_context": "empty", "shots": [], "grammars": []})
    with patch("backend.app.domain.director_rag.httpx.AsyncClient.post", return_value=empty_resp):
        res_empty = await timeout_client.retrieve("Hero walks into rain", genre="Cyberpunk")
        assert res_empty == {"director_context": "", "shots": [], "grammars": []}

    # 5. Engine mapping covers all 6 trainer engines
    assert map_target_engine("veo") == "veo"
    assert map_target_engine("google_flow") == "veo"
    assert map_target_engine("runway_gen3") == "runway"
    assert map_target_engine("kling_1.5") == "kling"
    assert map_target_engine("openai_sora") == "sora"
    assert map_target_engine("comfyui") == "wan2.1"
    assert map_target_engine("9router") == "flux"


@pytest.mark.anyio
async def test_screenwriter_rag_injection_and_polish_signature():
    engine = PolyaScreenwriterEngine()
    rag_payload = _mock_rag_payload()

    treatment_llm_output = {
        "title": "Neon Shadow",
        "logline": "A courier races through neon rain.",
        "theme": "Identity",
        "dramatic_premise": "Courier vs syndicate.",
        "acts": [
            {"act_number": i, "act_title": f"Act {i}", "start_scene": 1, "end_scene": 12, "dramatic_goal": "Goal", "key_beat": "Beat"}
            for i in range(1, 5)
        ],
    }

    with (
        patch.object(DirectorRAGClient, "retrieve", new=AsyncMock(return_value=rag_payload)),
        patch.object(engine, "_call_llm", new=AsyncMock(return_value=treatment_llm_output)) as mock_llm,
    ):
        await engine.generate_master_treatment(
            project_context={"title": "Neon Shadow", "genre_tone": "Cyberpunk", "synopsis": "Rain courier chase"},
            total_scenes=50,
        )
        sent_messages = mock_llm.call_args[0][0]
        user_prompt = sent_messages[1]["content"]
        assert "Hold reverse angles across neon reflections before reveal" in user_prompt
        assert "Measured 4.5s tracking tightening to 1.8s cuts" in user_prompt

    # Act scenes injection
    act_llm_output = {
        "act_summary": "Act I setup complete.",
        "scenes": [
            {
                "scene_number": i,
                "slugline": "EXT. NEON ALLEY - NIGHT",
                "narrative_goal": "Courier evades drones.",
                "speaking_character": "Kael",
                "dialogue": "Keep moving.",
            }
            for i in range(1, 13)
        ],
    }
    with (
        patch.object(DirectorRAGClient, "retrieve", new=AsyncMock(return_value=rag_payload)),
        patch.object(engine, "_call_llm", new=AsyncMock(return_value=act_llm_output)) as mock_act_llm,
    ):
        await engine.generate_act_scenes(
            act_number=1,
            total_scenes=50,
            treatment={
                "title": "Neon Shadow",
                "structure_type": "4_act",
                "acts": [{"act_number": 1, "act_title": "Setup", "dramatic_goal": "Escape sector", "key_beat": "Drone ambush"}],
            },
            project_context={"genre_tone": "Cyberpunk"},
        )
        act_prompt = mock_act_llm.call_args[0][0][1]["content"]
        assert "#Lens 05 -> #Lens 01" in act_prompt
        assert "Rain ambience J-cut 1.2s prior to door breach" in act_prompt

    # polish_scene_director_cut calls _call_llm(messages, retry_on_parse_error=True)
    polish_llm_output = {
        "slugline": "EXT. ROOFTOP HELIPAD - RAIN NIGHT",
        "narrative_goal": "Kael scans the flooded neon skyline below.",
        "dialogue": "They found the beacon.",
        "camera_code": "#Cam 19",
        "lighting_code": "#Light 06",
        "director_notes": "Dolly-in amplifies isolation against neon skyline.",
    }
    with patch.object(engine, "_call_llm", new=AsyncMock(return_value=polish_llm_output)) as mock_polish_llm:
        polished = await engine.polish_scene_director_cut(
            scene_number=1,
            slugline="ROOFTOP - NIGHT",
            narrative_goal="Hero watches city below.",
            dialogue="It is time.",
        )
        call_args, call_kwargs = mock_polish_llm.call_args
        assert isinstance(call_args[0], list)
        assert call_args[0][0]["role"] == "system"
        assert call_args[0][1]["role"] == "user"
        assert call_kwargs.get("retry_on_parse_error") is True
        assert polished["slugline"] == "EXT. ROOFTOP HELIPAD - RAIN NIGHT"
        assert polished["camera_code"] == "#Cam 19"


@pytest.mark.anyio
async def test_transpile_with_rag_preserves_mpb_dna_and_attaches_refs():
    rag_payload = _mock_rag_payload()
    kwargs = dict(
        provider_target="veo",
        style_code="#Style 09",  # Pixar / Disney 3D Animation
        camera_code="#Cam 18",
        lens_code="#Lens 01",
        comp_code="#Comp 01",
        light_code="#Light 06",
        act_code="#Act 06",
        speed_code="#Speed 03",
        character_dna="LOCKED_CHAR_ARYA_BLUE_EYES",
        env_dna="LOCKED_ENV_NEON_MARKET",
        action_description="sprinting through rain",
        preset_rules={"negative_prompt_additions": "watermark"},
    )
    sync_base = LivePromptTranspiler.transpile(**kwargs)
    with patch.object(DirectorRAGClient, "retrieve", new=AsyncMock(return_value=rag_payload)):
        res = await LivePromptTranspiler.transpile_with_rag(
            **kwargs,
            genre="Cyberpunk",
        )

    assert "LOCKED_CHAR_ARYA_BLUE_EYES" in res["positive_prompt"]
    assert "LOCKED_ENV_NEON_MARKET" in res["positive_prompt"]
    assert "#Cam 18" in res["positive_prompt"]
    assert "Anamorphic rain-slicked neon tracking shot" in res["positive_prompt"]
    assert res["negative_prompt"] == sync_base["negative_prompt"]
    assert len(res["rag_references"]) == 1
    assert res["rag_references"][0]["shot_id"] == "vid_001_shot_001"


def test_style_filter_sync_18_styles_and_legacy_mapping():
    assert normalize_style_code("#Style 01") == "#Style 01"
    assert normalize_style_code("style 1") == "#Style 01"
    assert normalize_style_code("STYLE_18") == "#Style 18"
    assert normalize_style_code("Transformers / Michael Bay") == "#Style 01"
    assert normalize_style_code("Pixar / Disney 3D Animation") == "#Style 09"

    # Explicit style_code always overrides legacy genre strings
    assert resolve_style_filter(style_code="#Style 01", genre="Action") == "#Style 01"
    assert resolve_style_filter(style_code="#Style 09", genre="Sci-Fi") == "#Style 09"
    # Legacy genres resolve to canonical #Style 01..#Style 18, never raw "Action"/"Sci-Fi"
    assert resolve_style_filter(genre="Action") == "#Style 01"
    assert resolve_style_filter(genre="Sci-Fi") == "#Style 02"
    assert resolve_style_filter(genre="Cyberpunk") == "#Style 02"
    assert resolve_style_filter(genre="#Style 15") == "#Style 15"
    assert resolve_style_filter() is None


@pytest.mark.anyio
async def test_director_rag_sends_canonical_style_and_falls_back_when_style_empty():
    captured_payloads = []

    async def fake_post(self, url, json=None, headers=None, **kwargs):
        captured_payloads.append(json)
        if json.get("genre") == "#Style 09":
            return httpx.Response(200, json={"director_context": "", "shots": [], "grammars": []})
        return httpx.Response(200, json=_mock_rag_payload())

    client = DirectorRAGClient(enabled=True, base_url="http://127.0.0.1:8765", timeout_sec=1.0)
    with patch("backend.app.domain.director_rag.httpx.AsyncClient.post", new=fake_post):
        # 1. Legacy genre "Action" -> sends "#Style 01"
        res_action = await client.retrieve("Desert mech explosion", genre="Action", engine="veo")
        assert len(res_action["shots"]) == 1
        assert captured_payloads[0]["genre"] == "#Style 01"

        # 2. Style with empty KB -> falls back safely to unfiltered genre=None
        res_empty_style = await client.retrieve("Toy room adventure", style_code="#Style 09", genre="Animation")
        assert len(res_empty_style["shots"]) == 1
        assert captured_payloads[1]["genre"] == "#Style 09"
        assert captured_payloads[2]["genre"] is None


@pytest.mark.anyio
async def test_screenwriter_and_transpiler_forward_style_code():
    engine = PolyaScreenwriterEngine()
    rag_payload = _mock_rag_payload()
    with (
        patch.object(DirectorRAGClient, "retrieve", new=AsyncMock(return_value=rag_payload)) as mock_retrieve,
        patch.object(engine, "_call_llm", new=AsyncMock(return_value={
            "title": "Mech Dawn",
            "logline": "Logline",
            "theme": "Theme",
            "dramatic_premise": "Premise",
            "acts": [{"act_number": i, "act_title": f"Act {i}", "start_scene": 1, "end_scene": 10, "dramatic_goal": "Goal", "key_beat": "Beat"} for i in range(1, 5)],
        })),
    ):
        await engine.generate_master_treatment(
            project_context={"title": "Mech Dawn", "genre_tone": "Action", "master_style_code": "#Style 01", "synopsis": "Desert mech clash"},
            total_scenes=40,
        )
        assert mock_retrieve.call_args.kwargs.get("style_code") == "#Style 01"

    with patch.object(DirectorRAGClient, "retrieve", new=AsyncMock(return_value=rag_payload)) as mock_transpile_retrieve:
        await LivePromptTranspiler.transpile_with_rag(
            provider_target="veo",
            style_code="#Style 08",
            action_description="Rainy Javanese courtyard",
            genre="Drama",
        )
        assert mock_transpile_retrieve.call_args.kwargs.get("style_code") == "#Style 08"
