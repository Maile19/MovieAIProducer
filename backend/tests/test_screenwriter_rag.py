"""Tests for Phase 3 Screenwriter RAG integration in MovieAIProducer."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend.app.domain.director_rag import DirectorRAGClient
from backend.app.domain.screenwriter import (
    PolyaScreenwriterEngine,
    ProjectNarrativeContext,
    parse_structured_slugline,
)
from backend.app.services.screenwriter_rag import (
    ScreenwriterRAGClient,
    empty_screenwriter_rag_result,
)


def _mock_sw_payload(label: str = "Screenwriter Craft Sample") -> dict:
    return {
        "prompt_block": f"[SCREENWRITER CRAFT] {label}\n[VOICE DNA & 5-STATE ARC] Contrast cadence.",
        "writing_directives": {
            "dialogue_density": "High-contrast cadence (1.5-2.8 wps)",
            "action_beat_grammar": "Graphic keyframe clarity",
            "preferred_jl_cut_cadence": "L-cut ambient holds",
            "pacing_rules": "Exploit 'ma' stillness before burst acceleration.",
        },
        "style_family": "anime_2d",
        "items": [{"title": label, "rule_text": "Every scene must turn a dramatic value."}],
    }


def _mock_director_payload() -> dict:
    return {
        "director_context": "### POLIA AI DIRECTOR RETRIEVED FEW-SHOT CONTEXT",
        "grammars": [
            {
                "grammar_id": "seq_01",
                "title": "Neon Pursuit",
                "director_master_rule": "Hold reverse angles across wet asphalt",
                "lens_progression": "#Lens 05 -> #Lens 01",
                "lighting_evolution": "#Light 06 -> #Light 03",
                "pacing_curve": "Measured 4.5s tracking tightening to 1.8s cuts",
                "audio_bridge_strategy": "Rain ambience J-cut 1.2s before breach",
            }
        ],
        "shots": [],
    }


@pytest.mark.anyio
async def test_screenwriter_rag_client_live_all_5_endpoints():
    client = ScreenwriterRAGClient(enabled=True, base_url="http://127.0.0.1:8766", timeout_sec=1.5)

    r_voice = await client.retrieve_character_voice(
        style_code="#Style 14", genre_tone="Anime Sci-Fi", roles=["PROTAGONIST", "ANTAGONIST"]
    )
    assert r_voice["style_family"] == "anime_2d"
    assert len(r_voice["items"]) > 0
    assert "[VOICE DNA & 5-STATE ARC]" in r_voice["prompt_block"]

    r_struct = await client.retrieve_structure_rules(
        style_code="#Style 07", structure_type="5_act", total_scenes=120, query="freytag turning point"
    )
    assert r_struct["style_family"] == "photorealistic"
    assert len(r_struct["items"]) > 0
    assert "[SCREENWRITER CRAFT]" in r_struct["prompt_block"]

    r_treat = await client.retrieve_treatment_beats(
        style_code="#Style 11", structure_type="youtube_viral", genre_tone="Steampunk", premise="30s cold open"
    )
    assert r_treat["style_family"] == "stylized_3d"
    assert len(r_treat["items"]) > 0

    r_scene = await client.retrieve_scene_craft(
        style_code="#Style 14", act_number=1, narrative_goal="establish_isolation", duration_tier="5s_max14"
    )
    assert r_scene["style_family"] == "anime_2d"
    assert len(r_scene["items"]) > 0
    assert all(it["dialogue_word_count"] <= 14 for it in r_scene["items"])

    r_dlg = await client.retrieve_dialogue_cut(
        style_code="#Style 02", max_words=14, dialogue_text="Why are you leaving?"
    )
    assert r_dlg["style_family"] == "photorealistic"
    assert len(r_dlg["items"]) > 0
    assert all(it["word_count"] <= 14 for it in r_dlg["items"])


@pytest.mark.anyio
async def test_screenwriter_rag_client_graceful_fallbacks():
    disabled = ScreenwriterRAGClient(enabled=False)
    assert await disabled.retrieve_scene_craft(style_code="#Style 01", narrative_goal="test") == empty_screenwriter_rag_result()

    client = ScreenwriterRAGClient(enabled=True, base_url="http://127.0.0.1:8766", timeout_sec=0.5)
    with patch("backend.app.services.screenwriter_rag.httpx.AsyncClient.post", side_effect=httpx.ReadTimeout("timeout")):
        res_to = await client.retrieve_dialogue_cut(style_code="#Style 01", max_words=14, dialogue_text="Hello")
        assert res_to == empty_screenwriter_rag_result()

    with patch("backend.app.services.screenwriter_rag.httpx.AsyncClient.post", side_effect=httpx.ConnectError("refused")):
        res_conn = await client.retrieve_treatment_beats(style_code="#Style 01", premise="Chase")
        assert res_conn == empty_screenwriter_rag_result()

    with patch("backend.app.services.screenwriter_rag.httpx.Client.post", side_effect=httpx.ConnectError("refused")):
        res_sync = client.retrieve_structure_rules_sync(style_code="#Style 01", structure_type="4_act")
        assert res_sync == empty_screenwriter_rag_result()


def test_parse_structured_slugline_edge_cases():
    p1 = parse_structured_slugline("EXT. ASH WASTES - TWILIGHT")
    assert p1 == {
        "setting": "EXT.",
        "location": "ASH WASTES",
        "time_of_day": "TWILIGHT",
        "normalized": "EXT. ASH WASTES - TWILIGHT",
    }

    p2 = parse_structured_slugline("INT./EXT. MECH COCKPIT - RAINY NIGHT")
    assert p2["setting"] == "INT./EXT."
    assert p2["location"] == "MECH COCKPIT"
    assert p2["time_of_day"] == "RAINY NIGHT"
    assert p2["normalized"] == "INT./EXT. MECH COCKPIT - RAINY NIGHT"

    p3 = parse_structured_slugline("EXT. RUINED CITY")
    assert p3["setting"] == "EXT."
    assert p3["location"] == "RUINED CITY"
    assert p3["time_of_day"] == ""
    assert p3["normalized"] == "EXT. RUINED CITY"

    p4 = parse_structured_slugline("ROOFTOP - NIGHT")
    assert p4["setting"] == ""
    assert p4["location"] == "ROOFTOP"
    assert p4["time_of_day"] == "NIGHT"

    p5 = parse_structured_slugline("   ")
    assert p5 == {"setting": "", "location": "", "time_of_day": "", "normalized": ""}


@pytest.mark.anyio
async def test_prompt_assembly_and_offline_resilience_across_all_hooks():
    engine = PolyaScreenwriterEngine()
    sw_payload = _mock_sw_payload("Anime Rain Bridge")
    dir_payload = _mock_director_payload()

    ctx = ProjectNarrativeContext(
        project_id="proj-1",
        title="Glass Monsoon",
        synopsis="A courier crosses a flooded city to deliver an unsealed letter.",
        genre_tone="Anime Drama",
        master_style_code="#Style 15",
        style_name="Anime (Shinkai / Ufotable)",
        aesthetic_directives="Hyper-detailed sky cloud formations, god rays, expressive eyes.",
        color_grade_emulation="Luminous ultramarine blues and sunset magentas.",
        world_setting="Flooded Coastal Tokyo",
    )

    # 1. Hook 1: generate_cast_ensemble
    cast_llm_out = {
        "cast_rationale": "Strong ideological contrast.",
        "characters": [
            {
                "name": f"Hero {i}",
                "role": "PROTAGONIST" if i == 0 else ("ANTAGONIST" if i == 1 else "ALLY"),
                "narrative_summary": "Core role",
                "base_visual_prompt": "Portrait isolated on #D4D4D4",
                "voice_dna_profile": "Crisp cadence",
                "states": [{"state_number": s, "state_label": f"S{s}", "wardrobe": "Coat"} for s in range(1, 6)],
            }
            for i in range(5)
        ],
    }
    with (
        patch.object(ScreenwriterRAGClient, "retrieve_character_voice", new=AsyncMock(return_value=sw_payload)),
        patch.object(engine, "_call_llm", new=AsyncMock(return_value=cast_llm_out)) as mock_cast_llm,
    ):
        await engine.generate_cast_ensemble(ctx)
        cast_prompt = mock_cast_llm.call_args[0][0][1]["content"]
        assert "[VOICE DNA & 5-STATE ARC]" in cast_prompt

    # 2. Hook 2: analyze_narrative_structure (sync)
    with patch.object(ScreenwriterRAGClient, "retrieve_structure_rules_sync", return_value=sw_payload):
        adv = engine.analyze_narrative_structure(ctx, total_scenes=100)
        assert "Screenwriter Invariant" in adv["strategic_rationale"]

    # 3. Hook 3: generate_master_treatment
    treat_llm_out = {
        "title": "Glass Monsoon",
        "logline": "Logline",
        "theme": "Theme",
        "dramatic_premise": "Premise",
        "acts": [
            {"act_number": i, "act_title": f"Act {i}", "start_scene": 1, "end_scene": 10, "dramatic_goal": "Goal", "key_beat": "Beat"}
            for i in range(1, 5)
        ],
    }
    with (
        patch.object(ScreenwriterRAGClient, "retrieve_treatment_beats", new=AsyncMock(return_value=sw_payload)),
        patch.object(DirectorRAGClient, "retrieve", new=AsyncMock(return_value=dir_payload)),
        patch.object(engine, "_call_llm", new=AsyncMock(return_value=treat_llm_out)) as mock_treat_llm,
    ):
        await engine.generate_master_treatment(project_context=ctx, total_scenes=40, structure_type="4_act")
        treat_prompt = mock_treat_llm.call_args[0][0][1]["content"]
        assert "[SCREENWRITER CRAFT & DRAMATURGY]" in treat_prompt
        assert "[DIRECTOR VISUAL GRAMMAR]" in treat_prompt

    # 4. Hook 4: generate_act_scenes (verifies style_name, style_family, writing_directives + dual RAG)
    act_llm_out = {
        "act_summary": "Act I complete.",
        "scenes": [
            {
                "scene_number": i,
                "slugline": "EXT. FLOODED TRACKS - DUSK",
                "narrative_goal": "Courier inspects the soaked parcel.",
                "speaking_character": "Hero 0",
                "dialogue": "Still dry.",
            }
            for i in range(1, 11)
        ],
    }
    with (
        patch.object(ScreenwriterRAGClient, "retrieve_scene_craft", new=AsyncMock(return_value=sw_payload)),
        patch.object(DirectorRAGClient, "retrieve", new=AsyncMock(return_value=dir_payload)),
        patch.object(engine, "_call_llm", new=AsyncMock(return_value=act_llm_out)) as mock_act_llm,
    ):
        await engine.generate_act_scenes(
            act_number=1,
            total_scenes=40,
            treatment={"title": "Glass Monsoon", "structure_type": "4_act", "acts": [{"act_number": 1, "act_title": "Act I", "dramatic_goal": "Establish isolation", "key_beat": "Rain"}]},
            project_context=ctx,
        )
        act_prompt = mock_act_llm.call_args[0][0][1]["content"]
        assert "Anime (Shinkai / Ufotable)" in act_prompt
        assert "Style Family: anime_2d" in act_prompt
        assert "Style Writing Directives:" in act_prompt
        assert "[SCREENWRITER CRAFT & SCENE EXEMPLARS]" in act_prompt
        assert "[DIRECTOR VISUAL GRAMMAR]" in act_prompt

    # 5. Hook 5: calibrate_dialogue_pacing
    calib_llm_out = {
        "word_count": 3,
        "syllable_count": 4,
        "estimated_duration_seconds": 1.2,
        "passes_duration_limit": True,
        "transition_type": "HARD_CUT",
        "audio_lead_seconds": 0.0,
        "analysis": "Crisp line.",
        "trimmed_suggestion": None,
    }
    with (
        patch.object(ScreenwriterRAGClient, "retrieve_dialogue_cut", new=AsyncMock(return_value=sw_payload)),
        patch.object(engine, "_call_llm", new=AsyncMock(return_value=calib_llm_out)) as mock_cal_llm,
    ):
        await engine.calibrate_dialogue_pacing("Leave the key.", max_seconds=5.0, style_code="#Style 15")
        cal_msgs = mock_cal_llm.call_args.kwargs.get("messages") or mock_cal_llm.call_args.args[0]
        cal_prompt = cal_msgs[1]["content"]
        assert "[SCREENWRITER CRAFT & SUBTEXT CUTS]" in cal_prompt

    # 6. Hook 6: polish_scene_director_cut
    polish_llm_out = {
        "slugline": "EXT. FLOODED TRACKS - TWILIGHT",
        "narrative_goal": "Elevated goal",
        "dialogue": "Still dry.",
        "camera_code": "#Cam 03",
        "lighting_code": "#Light 06",
        "director_notes": "Tight.",
    }
    with (
        patch.object(ScreenwriterRAGClient, "retrieve_scene_craft", new=AsyncMock(return_value=sw_payload)),
        patch.object(ScreenwriterRAGClient, "retrieve_dialogue_cut", new=AsyncMock(return_value=sw_payload)),
        patch.object(DirectorRAGClient, "retrieve", new=AsyncMock(return_value=dir_payload)),
        patch.object(engine, "_call_llm", new=AsyncMock(return_value=polish_llm_out)) as mock_pol_llm,
    ):
        await engine.polish_scene_director_cut(
            scene_number=1,
            slugline="FLOODED TRACKS - DUSK",
            narrative_goal="Courier stands in rain.",
            dialogue="Waiting.",
            style_code="#Style 15",
        )
        pol_prompt = mock_pol_llm.call_args[0][0][1]["content"]
        assert "[SCREENWRITER CRAFT & SUBTEXT]" in pol_prompt
        assert "[DIRECTOR VISUAL GRAMMAR]" in pol_prompt

    # 7. Graceful operation when Screenwriter RAG (8766) is completely unreachable
    with (
        patch("backend.app.services.screenwriter_rag.httpx.AsyncClient.post", side_effect=httpx.ConnectError("8766 down")),
        patch("backend.app.domain.director_rag.httpx.AsyncClient.post", side_effect=httpx.ConnectError("8765 down")),
        patch.object(engine, "_call_llm", new=AsyncMock(return_value=act_llm_out)),
    ):
        res_offline = await engine.generate_act_scenes(
            act_number=1,
            total_scenes=40,
            treatment={"title": "Glass Monsoon", "structure_type": "4_act", "acts": [{"act_number": 1, "act_title": "Act I", "dramatic_goal": "Setup", "key_beat": "Hook"}]},
            project_context=ctx,
        )
        assert res_offline["scenes_count"] == 10


@pytest.mark.anyio
async def test_wave1_hermes_ideation_and_voice_state_continuity_chain():
    """Verify HermesNova RAG 8766 + style DNA wiring, Voice DNA + 5-State continuity, and bible engine methods."""
    from backend.app.domain.hermes_engine import HermesNovaEngine
    from backend.app.domain.screenwriter import STYLE_FAMILY_WRITING_DIRECTIVES

    sw_payload = _mock_sw_payload("Shinkai Monologue Craft")
    hermes = HermesNovaEngine()

    # 1. HermesNova titles injects RAG 8766 + STYLE_FAMILY_WRITING_DIRECTIVES
    titles_llm = {
        "recommendations": [
            {"rank": i, "title": f"Glass Sky #{i}", "trend_hook": "Dramatic promise", "target_keywords": ["Anime", "Sky"], "hook_score": 9.2}
            for i in range(1, 11)
        ],
        "seo_description_tags": ["Anime Drama", "#Style 15"],
    }
    with (
        patch.object(ScreenwriterRAGClient, "retrieve_structure_rules", new=AsyncMock(return_value=sw_payload)) as mock_struct_rag,
        patch.object(hermes, "_call_llm", new=AsyncMock(return_value=(titles_llm, "llm"))) as mock_titles_llm,
    ):
        t_res = await hermes.generate_10_titles(
            preset_name="Anime Prestige",
            category="anime",
            target_style_code="#Style 15",
            seed_premise="A courier delivers an unsealed letter across flooded rail tracks.",
        )
        assert t_res["source"] == "llm"
        assert mock_struct_rag.called
        titles_user_prompt = mock_titles_llm.call_args[0][0][1]["content"]
        assert "Style Taxonomy Family: anime_2d" in titles_user_prompt
        assert "[SCREENWRITER CRAFT & DRAMATURGY]" in titles_user_prompt
        assert STYLE_FAMILY_WRITING_DIRECTIVES["anime_2d"] in titles_user_prompt or sw_payload["writing_directives"]["pacing_rules"] in titles_user_prompt

    # 2. HermesNova synopses injects RAG 8766 retrieve_treatment_beats + 8-10 min arc framing
    syn_llm = {
        "synopses": [
            {
                "rank": i,
                "angle_label": f"Angle {i}",
                "synopsis": f"Courier confronts past betrayal #{i}.",
                "retention_hook": "Silent platform bell at dawn",
                "target_audience": "Anime Drama Viewers",
            }
            for i in range(1, 11)
        ]
    }
    with (
        patch.object(ScreenwriterRAGClient, "retrieve_treatment_beats", new=AsyncMock(return_value=sw_payload)) as mock_treat_rag,
        patch.object(hermes, "_call_llm", new=AsyncMock(return_value=(syn_llm, "llm"))) as mock_syn_llm,
    ):
        s_res = await hermes.generate_10_synopses(
            locked_title="Glass Sky",
            preset_name="Anime Prestige",
            target_style_code="#Style 15",
            seed_premise="Unsealed confession on the last train.",
        )
        assert s_res["source"] == "llm"
        assert mock_treat_rag.called
        syn_user_prompt = mock_syn_llm.call_args[0][0][1]["content"]
        assert "Style Taxonomy Family: anime_2d" in syn_user_prompt
        assert "8-10 minute" in syn_user_prompt
        assert "[SCREENWRITER CRAFT & DRAMATURGY]" in syn_user_prompt

    # 3. Cast Voice DNA + 5-State chaining into generate_act_scenes, calibrate_dialogue_pacing, polish_scene_director_cut
    engine = PolyaScreenwriterEngine()
    cast_with_states = [
        {
            "name": "Ren Sato",
            "role": "PROTAGONIST",
            "narrative_summary": "Stoic archivist concealing guilt.",
            "voice_dna_profile": "Sparse, clipped clauses (~1.9 wps), drops pronouns under grief.",
            "states": [
                {"state_code": "#State 01", "state_label": "Baseline", "wardrobe": "Pressed indigo coat", "injuries_and_wear": "Unmarked", "expression_anchor": "Guarded poise"},
                {"state_code": "#State 02", "state_label": "Weathered", "wardrobe": "Soaked hem", "injuries_and_wear": "Mud cuffs", "expression_anchor": "Tight jaw"},
                {"state_code": "#State 03", "state_label": "Wounded", "wardrobe": "Torn left lapel", "injuries_and_wear": "Bandaged wrist", "expression_anchor": "Hollow tremor"},
                {"state_code": "#State 04", "state_label": "Fracture", "wardrobe": "Coat discarded, rolled sleeves", "injuries_and_wear": "Cut brow", "expression_anchor": "Unblinking resolve"},
                {"state_code": "#State 05", "state_label": "Catharsis", "wardrobe": "Dry linen shirt", "injuries_and_wear": "Healing scar", "expression_anchor": "Open stillness"},
            ],
        }
    ]
    ctx = ProjectNarrativeContext(
        project_id="proj-chain",
        title="Glass Monsoon",
        synopsis="A stoic archivist delivers a final confession.",
        genre_tone="Anime Drama",
        master_style_code="#Style 15",
        style_name="Anime (Shinkai / Ufotable)",
        aesthetic_directives="Wet glass reflections.",
        color_grade_emulation="Cobalt & amber.",
        world_setting="Flooded Terminal",
        cast_characters=cast_with_states,
    )

    assert engine._resolve_act_to_state_number(1, 5) == 1
    assert engine._resolve_act_to_state_number(3, 5) == 3
    assert engine._resolve_act_to_state_number(5, 5) == 5
    assert engine._resolve_act_to_state_number(3, 4) == 4

    act_llm_out = {
        "act_summary": "Act V complete.",
        "scenes": [
            {
                "scene_number": i,
                "slugline": "EXT. PIER - DAWN",
                "narrative_goal": "Ren hands over the letter.",
                "speaking_character": "Ren Sato",
                "dialogue": "Read it alone.",
            }
            for i in range(41, 51)
        ],
    }
    with (
        patch.object(ScreenwriterRAGClient, "retrieve_scene_craft", new=AsyncMock(return_value=sw_payload)),
        patch.object(DirectorRAGClient, "retrieve", new=AsyncMock(return_value={"director_context": "", "grammars": [], "shots": []})),
        patch.object(engine, "_call_llm", new=AsyncMock(return_value=act_llm_out)) as mock_act_llm,
    ):
        await engine.generate_act_scenes(
            act_number=5,
            total_scenes=50,
            structure_type="5_act",
            treatment={
                "title": "Glass Monsoon",
                "structure_type": "5_act",
                "acts": [{"act_number": k, "act_title": f"Act {k}", "dramatic_goal": "Arc", "key_beat": "Beat"} for k in range(1, 6)],
            },
            project_context=ctx,
            characters=cast_with_states,
        )
        act5_prompt = mock_act_llm.call_args[0][0][1]["content"]
        assert "Sparse, clipped clauses (~1.9 wps)" in act5_prompt
        assert "Active #State 05" in act5_prompt
        assert "Dry linen shirt" in act5_prompt

    # 4. auto_generate_character & suggest_character_state use ScreenwriterRAGClient (8766)
    with (
        patch.object(ScreenwriterRAGClient, "retrieve_character_voice", new=AsyncMock(return_value=sw_payload)) as mock_voice_rag,
        patch.object(engine, "_call_llm", new=AsyncMock(return_value={
            "name": "Ren Sato",
            "role_suggestion": "Protagonist",
            "archetype_and_bio": "Guarded archivist.",
            "voice_dna_profile": "Sparse clipped cadence.",
            "base_visual_prompt": "Young archivist isolated on #D4D4D4 studio background",
        })),
    ):
        auto_res = await engine.auto_generate_character(project_context=ctx, mode="all")
        assert mock_voice_rag.called
        assert auto_res["voice_dna_profile"] == "Sparse clipped cadence."

    with (
        patch.object(ScreenwriterRAGClient, "retrieve_character_voice", new=AsyncMock(return_value=sw_payload)) as mock_state_rag,
        patch.object(engine, "_call_llm", new=AsyncMock(return_value={
            "wardrobe": "Fringed indigo coat heavy with rainwater.",
            "injuries_and_wear": "Shallow cut across left brow.",
            "expression_anchor": "Set jaw, eyes fixed ahead.",
        })),
    ):
        st_res = await engine.suggest_character_state(
            project_context=ctx,
            character=cast_with_states[0],
            state_code="#State 04",
        )
        assert mock_state_rag.called
        assert "Fringed indigo coat" in st_res["wardrobe"]


@pytest.mark.anyio
async def test_wave2_multi_option_polish_dialogue_coverage_and_treatment_variants():
    """Verify Wave 2 multi-option polish takes, dialogue alternatives, dual-brain coverage split, and 3 treatment pitches."""
    engine = PolyaScreenwriterEngine()
    sw_payload = _mock_sw_payload("Subtext Micro-Turn")
    dir_payload = _mock_director_payload()

    # 1. Polish returns backward-compatible keys + 3 distinct creative takes (both LLM and timeout fallback)
    polish_llm = {
        "options": [
            {
                "take_id": "subtext_heavy",
                "label": "Subtext-Heavy",
                "angle_rationale": "Silent refusal",
                "slugline": "EXT. PIER - DAWN",
                "narrative_goal": "Ren slides the wet envelope back without looking up.",
                "dialogue": "You came early.",
                "camera_code": "#Cam 02",
                "lighting_code": "#Light 06",
                "transition_type": "L_CUT",
                "director_notes": "Hold on clenched knuckles.",
            },
            {
                "take_id": "visceral_kinetic",
                "label": "Visceral / Kinetic",
                "angle_rationale": "Physical urgency",
                "slugline": "EXT. PIER - DAWN",
                "narrative_goal": "Ren slams the parcel onto the railing as ferry horns blare.",
                "dialogue": "Move before the tide hits.",
                "camera_code": "#Cam 18",
                "lighting_code": "#Light 01",
                "transition_type": "J_CUT",
                "director_notes": "Handheld push mirrors adrenaline.",
            },
            {
                "take_id": "minimalist_poetic",
                "label": "Minimalist / Poetic",
                "angle_rationale": "Visual stillness",
                "slugline": "EXT. PIER - DAWN",
                "narrative_goal": "Raindrops blur ink across the seal as dawn breaks.",
                "dialogue": "[SFX: Harbor bell tolls once across stillness]",
                "camera_code": "#Cam 13",
                "lighting_code": "#Light 04",
                "transition_type": "HARD_CUT",
                "director_notes": "Let 'ma' stillness carry closure.",
            },
        ]
    }
    with (
        patch.object(ScreenwriterRAGClient, "retrieve_scene_craft", new=AsyncMock(return_value=sw_payload)),
        patch.object(ScreenwriterRAGClient, "retrieve_dialogue_cut", new=AsyncMock(return_value=sw_payload)),
        patch.object(DirectorRAGClient, "retrieve", new=AsyncMock(return_value=dir_payload)),
        patch.object(engine, "_call_llm", new=AsyncMock(return_value=polish_llm)),
    ):
        p_res = await engine.polish_scene_director_cut(
            scene_number=10,
            slugline="PIER - DAWN",
            narrative_goal="Ren delivers parcel.",
            dialogue="Here it is.",
            style_code="#Style 15",
        )
        assert "slugline" in p_res and "narrative_goal" in p_res and "director_notes" in p_res
        assert len(p_res["options"]) == 3
        assert {o["take_id"] for o in p_res["options"]} == {"subtext_heavy", "visceral_kinetic", "minimalist_poetic"}
        assert all("word_count" in o and "transition_type" in o for o in p_res["options"])

    with (
        patch.object(ScreenwriterRAGClient, "retrieve_scene_craft", new=AsyncMock(return_value=sw_payload)),
        patch.object(ScreenwriterRAGClient, "retrieve_dialogue_cut", new=AsyncMock(return_value=sw_payload)),
        patch.object(DirectorRAGClient, "retrieve", new=AsyncMock(return_value=dir_payload)),
        patch.object(engine, "_call_llm", side_effect=RuntimeError("LLM offline")),
    ):
        p_fb = await engine.polish_scene_director_cut(
            scene_number=10,
            slugline="PIER - DAWN",
            narrative_goal="Ren delivers parcel.",
            style_code="#Style 15",
        )
        assert len(p_fb["options"]) == 3
        assert len({o["camera_code"] for o in p_fb["options"]}) == 3

    # 2. Dialogue Calibration returns 3 alternatives with deterministic 2.8 wps counts
    cal_llm = {
        "word_count": 99,
        "estimated_duration_seconds": 40.0,
        "analysis": "Keep breath taut.",
        "trimmed_suggestion": "Read this tonight.",
        "alternatives": [
            {"id": "subtext_cut", "label": "Subtext-Heavy", "dialogue": "The seal is still unbroken."},
            {"id": "urgent_clipped", "label": "Urgent / Clipped", "dialogue": "Take it and run."},
            {"id": "emotional_poetic", "label": "Emotional / Poetic", "dialogue": "Dawn remembers what we buried."},
        ],
    }
    with (
        patch.object(ScreenwriterRAGClient, "retrieve_dialogue_cut", new=AsyncMock(return_value=sw_payload)),
        patch.object(engine, "_call_llm", new=AsyncMock(return_value=cal_llm)),
    ):
        c_res = await engine.calibrate_dialogue_pacing(
            dialogue_text="Please read this letter before sunrise arrives over the flooded pier tonight.",
            max_seconds=5.0,
            style_code="#Style 15",
        )
        assert len(c_res["alternatives"]) == 3
        for alt in c_res["alternatives"]:
            expected_wc = len(alt["dialogue"].split())
            assert alt["word_count"] == expected_wc
            assert alt["estimated_duration_seconds"] == round(expected_wc / 2.8, 2)
            assert alt["passes_duration_limit"] is True

    # 3. Dual-brain plan_scene_shot_split honors coverage_style & style-aware optics fallback
    with (
        patch.object(ScreenwriterRAGClient, "retrieve_scene_craft", new=AsyncMock(return_value=sw_payload)),
        patch.object(DirectorRAGClient, "retrieve", new=AsyncMock(return_value=dir_payload)),
        patch.object(engine, "_call_llm", side_effect=RuntimeError("offline")),
    ):
        oner = await engine.plan_scene_shot_split(
            scene_number=3, slugline="EXT. ALLEY - NIGHT", narrative_goal="Unbroken chase.", target_duration=10.0, coverage_style="visceral_oner", style_code="#Style 15"
        )
        assert len(oner) == 1 and oner[0]["duration_seconds"] == 10.0 and oner[0]["light_code"] == "#Light 06"

        montage = await engine.plan_scene_shot_split(
            scene_number=4, slugline="EXT. ALLEY - NIGHT", narrative_goal="Rapid clash.", target_duration=10.0, coverage_style="rapid_montage", style_code="#Style 15"
        )
        assert len(montage) == 3

    # 4. Treatment variants calls both RAGs and returns 3 distinct variants
    variant_llm = {
        "variants": [
            {
                "variant_id": v_id,
                "pitch_label": lbl,
                "pitch_hook": f"Hook for {v_id}",
                "title": "Glass Monsoon",
                "logline": f"Logline {v_id}",
                "theme": "Duty",
                "dramatic_premise": f"Premise {v_id}",
                "cold_open_hook": "Letter sinks toward turbine blades.",
                "acts": [{"act_number": a, "act_title": f"Act {a}", "dramatic_goal": f"Goal {a}", "key_beat": f"Beat {a}"} for a in range(1, 5)],
            }
            for v_id, lbl in [
                ("character_tragedy_redemption", "Character Tragedy / Redemption"),
                ("high_stakes_escalation_twist", "High-Stakes Escalation / Twist"),
                ("atmospheric_mythic_arc", "Atmospheric Mythic Arc"),
            ]
        ]
    }
    ctx = ProjectNarrativeContext(
        project_id="proj-v",
        title="Glass Monsoon",
        synopsis="Courier crosses flooded city.",
        genre_tone="Anime Drama",
        master_style_code="#Style 15",
        style_name="Anime (Shinkai / Ufotable)",
        aesthetic_directives="Wet glass.",
        color_grade_emulation="Cobalt.",
        world_setting="Flooded Tokyo",
    )
    with (
        patch.object(ScreenwriterRAGClient, "retrieve_treatment_beats", new=AsyncMock(return_value=sw_payload)) as mock_sw,
        patch.object(DirectorRAGClient, "retrieve", new=AsyncMock(return_value=dir_payload)) as mock_dir,
        patch.object(engine, "_call_llm", new=AsyncMock(return_value=variant_llm)),
    ):
        vars_out = await engine.generate_treatment_variants(
            project_context=ctx, total_scenes=50, structure_type="4_act", cold_open_30s={"enabled": True}
        )
        assert mock_sw.called and mock_dir.called
        assert len(vars_out) == 3
        assert vars_out[0]["acts"][0]["start_scene"] == 1
        assert vars_out[0]["acts"][3]["end_scene"] == 50
