from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.app.domain.screenwriter import POLYA_AI_DIRECTOR_SYSTEM_PROMPT, PolyaScreenwriterEngine


def test_world_props_full_context_ingestion(client: TestClient, auth_headers: dict[str, str]):
    """Test 1: Verify full DB ingestion (cast + storyboard scenes) into Polya AI Director LLM prompt."""
    # 1. Create project with #Style 07 (Epic High Fantasy)
    create_p = client.post(
        "/api/v1/projects",
        json={
            "title": "Disgraced: The Ash Wastes",
            "target_style_code": "#Style 07",
            "aspect_ratio": "2.39:1",
            "settings": {
                "genre": "Epic High Fantasy",
                "synopsis": "An exiled warrior battles across the frozen basalt crags to reclaim ancestral honor.",
            },
        },
        headers=auth_headers,
    )
    assert create_p.status_code == 201
    project_id = create_p.json()["data"]["id"]

    # 2. Seed Character Cast with dynamic states
    char1_resp = client.post(
        f"/api/v1/projects/{project_id}/characters",
        json={
            "name": "Captain Astrid",
            "role": "PROTAGONIST",
            "base_prompt": "Weathered Norse shieldmaiden with braided silver hair, scarred jawline, wolf-pelt armor",
            "narrative_summary": "Exiled captain seeking redemption after a tragic betrayal at the northern pass.",
        },
        headers=auth_headers,
    )
    assert char1_resp.status_code == 201
    char1_id = char1_resp.json()["data"]["id"]

    client.post(
        f"/api/v1/characters/{char1_id}/states",
        json={
            "state_code": "#State 01",
            "state_label": "Exile Baseline",
            "wardrobe": "Weathered leather hauberk with tattered fur mantle",
            "injuries_and_wear": "Frostbitten fingertips, minor cut across right eyebrow",
            "expression_anchor": "Steely grim resolve",
        },
        headers=auth_headers,
    )

    client.post(
        f"/api/v1/projects/{project_id}/characters",
        json={
            "name": "Warlord Vane",
            "role": "ANTAGONIST",
            "base_prompt": "Towering warlord clad in blackened iron plate armor, cold slate-gray eyes",
            "narrative_summary": "Usurper lord commanding the Iron Legion across the northern fjords.",
        },
        headers=auth_headers,
    )

    # 3. Seed Storyboard Scenes
    scene_slugs = [
        (1, 1, "EXT. ASH WASTES - DAY", "Astrid marches through blizzard alone"),
        (1, 2, "EXT. ASH WASTES - NIGHT", "Astrid makes camp beneath ancient basalt crags"),
        (2, 13, "INT. RUINED OUTPOST - NIGHT", "Vane ambushes Astrid at the broken watchtower"),
        (3, 26, "EXT. BASALT CRAGS - DUSK", "Astrid rallies rebel scouts for counter-stroke"),
        (4, 39, "INT. OBSIDIAN KEEP - MIDNIGHT", "Climactic duel between Astrid and Vane"),
    ]
    for act, sc_num, slug, goal in scene_slugs:
        client.post(
            f"/api/v1/projects/{project_id}/scenes",
            json={
                "act_number": act,
                "scene_number": sc_num,
                "slugline": slug,
                "narrative_goal": goal,
                "duration_target": 15.0 if act % 2 == 1 else 10.0,
            },
            headers=auth_headers,
        )

    # 4. Intercept _call_llm and inspect outgoing prompt messages
    captured_messages = []

    async def fake_call_llm(messages, retry_on_parse_error=True):
        captured_messages.extend(messages)
        return {
            "environments": [
                {
                    "code": "#Env 01",
                    "name": "Frozen Ash Wastes",
                    "architecture": "Vast expanse of jagged basalt monoliths",
                    "atmosphere": "Sub-zero drifting woodsmoke and ash flakes",
                    "lighting_code": "#Light 07",
                    "lighting_and_audio": "#Light 07 Overcast Soft (6000K diffused northern sky) • Room Tone: howling wind across ice crags",
                    "linked_scenes": "Act I (EXT. ASH WASTES - DAY)",
                    "lighting": "#Light 07 Overcast Soft diffused northern sky",
                    "audio": "Howling sub-zero wind across jagged basalt",
                },
                {"code": "#Env 02", "name": "Ruined Watchtower", "architecture": "Crumbling stone masonry", "atmosphere": "Heavy frost", "lighting_code": "#Light 04", "lighting_and_audio": "#Light 04 Silvery Blue Moonlight • Room Tone: creaking timber", "linked_scenes": "Act II (INT. RUINED OUTPOST)", "lighting": "Moonlight", "audio": "Creaking timber"},
                {"code": "#Env 03", "name": "Basalt Crags Stronghold", "architecture": "Volcanic cliff fortifications", "atmosphere": "Freezing gale", "lighting_code": "#Light 01", "lighting_and_audio": "#Light 01 Golden Hour Backlit • Room Tone: distant war horn", "linked_scenes": "Act III (EXT. BASALT CRAGS)", "lighting": "Golden rim", "audio": "War horn"},
                {"code": "#Env 04", "name": "Underground Runic Crypt", "architecture": "Subterranean basalt tomb", "atmosphere": "Permafrost stillness", "lighting_code": "#Light 06", "lighting_and_audio": "#Light 06 Cyan Bioluminescence • Room Tone: water drips", "linked_scenes": "Act III", "lighting": "Bioluminescence", "audio": "Water drips"},
                {"code": "#Env 05", "name": "Obsidian Keep Climax Arena", "architecture": "Vaulted stone throne room", "atmosphere": "Smoky embers", "lighting_code": "#Light 05", "lighting_and_audio": "#Light 05 Flickering Torch • Room Tone: clash of forged steel", "linked_scenes": "Act IV (INT. OBSIDIAN KEEP)", "lighting": "Flickering hearth", "audio": "Clash of forged steel"},
            ],
            "props": [
                {
                    "code": "#Prop 01",
                    "name": "Rune-Carved Bog Iron Seal",
                    "owner_character": "Captain Astrid",
                    "material_and_wear": "Hand-forged bog iron inlaid with beaten silver runes, notched edges",
                    "narrative_utility": "Hero ancestral heirloom anchoring Astrid's sacred vow of redemption",
                    "description": "Ancestral bog iron seal belonging to Captain Astrid",
                    "material": "Hand-forged bog iron inlaid with beaten silver runes",
                    "weight": "Hero ancestral heirloom anchoring Astrid's sacred vow of redemption",
                    "action": "Gripped firmly in clenched fist before entering battle",
                },
                {"code": "#Prop 02", "name": "Blackened Iron Claymore", "owner_character": "Warlord Vane", "material_and_wear": "Forged iron with blood-grooves", "narrative_utility": "Tyrannical weapon of conquest", "description": "Claymore wielded by Vane", "material": "Blackened iron", "weight": "Symbol of conquest", "action": "Drawn with metallic scrape"},
                {"code": "#Prop 03", "name": "Mammoth Bone Astrolabe", "owner_character": "Captain Astrid", "material_and_wear": "Carved ivory and brass gears", "narrative_utility": "Navigation instrument through northern blizzard", "description": "Astrolabe", "material": "Ivory", "weight": "Navigation tool", "action": "Held to eye level"},
                {"code": "#Prop 04", "name": "Iron Legion Oath-Stone", "owner_character": "Warlord Vane", "material_and_wear": "Fractured volcanic glass", "narrative_utility": "Binding covenant token", "description": "Oath-stone", "material": "Volcanic glass", "weight": "Binding token", "action": "Slammed on council table"},
                {"code": "#Prop 05", "name": "Ancestral Horn of the North", "owner_character": "Ensemble / World Artifact", "material_and_wear": "Aurochs horn banded in silver", "narrative_utility": "Rallying instrument", "description": "Rallying horn", "material": "Aurochs horn", "weight": "Rallying call", "action": "Sounded with deep war blast"},
            ],
        }

    with patch.object(PolyaScreenwriterEngine, "_call_llm", side_effect=fake_call_llm):
        gen_resp = client.post(
            f"/api/v1/projects/{project_id}/bible/generate-world-props",
            json={"additional_notes": "Emphasize sub-zero survival and Nordic tactile lore."},
            headers=auth_headers,
        )
        assert gen_resp.status_code == 200

    # 5. Verify system and user prompts
    assert len(captured_messages) >= 2
    system_msg = next(m["content"] for m in captured_messages if m["role"] == "system")
    user_msg = next(m["content"] for m in captured_messages if m["role"] == "user")

    assert "Polya AI Director" in system_msg
    assert "Hollywood Production Designer" in system_msg

    # Verify context ingestion into user prompt
    assert "Disgraced: The Ash Wastes" in user_msg
    assert "#Style 07" in user_msg
    assert "Captain Astrid" in user_msg
    assert "Warlord Vane" in user_msg
    assert "EXT. ASH WASTES" in user_msg
    assert "#Light 01" in user_msg
    assert "#Light 07" in user_msg
    assert "#Light 14" in user_msg


def test_world_props_llm_success_and_metadata(client: TestClient, auth_headers: dict[str, str]):
    """Test 2: Verify LLM success produces enriched fields and generation_meta."""
    create_p = client.post(
        "/api/v1/projects",
        json={
            "title": "Quantum Horizon",
            "target_style_code": "#Style 01",
            "settings": {"genre": "Sci-Fi / Cyberpunk", "synopsis": "An engineer breaches an orbital station core."},
        },
        headers=auth_headers,
    )
    project_id = create_p.json()["data"]["id"]

    mock_llm_payload = {
        "environments": [
            {
                "code": "#Env 01",
                "name": "Orbital Spire Command Core",
                "architecture": "Titanium aerogel trusses and modular holo-consoles",
                "atmosphere": "Air-scrubbed climate with zero humidity",
                "lighting_code": "#Light 01",
                "lighting_and_audio": "#Light 01 Volumetric Amber Rim (2800K warmth, cool console wash) • Room Tone: hum of coolant pumps, SNR 34 dB",
                "linked_scenes": "Act I (INT. COMMAND CORE)",
                "lighting": "#Light 01 Volumetric Amber Rim",
                "audio": "Continuous electronics hum, SNR 34 dB",
            },
            {"code": "#Env 02", "name": "Magnetic Airlock Bay", "architecture": "Steel bulkhead airlocks", "atmosphere": "Nitrogen steam", "lighting_code": "#Light 03", "lighting_and_audio": "#Light 03 Low-Key Chiaroscuro • Room Tone: servo whine", "linked_scenes": "Act II", "lighting": "Sodium vapor", "audio": "Servo whine"},
            {"code": "#Env 03", "name": "Sub-Reactor Catacombs", "architecture": "Magnetic piping vaults", "atmosphere": "Cryogenic haze", "lighting_code": "#Light 06", "lighting_and_audio": "#Light 06 Neon Cyberpunk • Room Tone: sub-bass pulse", "linked_scenes": "Act II-B", "lighting": "Cyan glow", "audio": "Sub-bass pulse"},
            {"code": "#Env 04", "name": "Derelict Sensor Array", "architecture": "Geodesic observatory dome", "atmosphere": "Static discharge", "lighting_code": "#Light 02", "lighting_and_audio": "#Light 02 Volumetric God Rays • Room Tone: antenna buffeting", "linked_scenes": "Act III", "lighting": "Starfield wash", "audio": "Antenna buffeting"},
            {"code": "#Env 05", "name": "Orbital Climax Spur", "architecture": "Cantilevered spur over atmosphere", "atmosphere": "Vacuum chill", "lighting_code": "#Light 05", "lighting_and_audio": "#Light 05 Silhouette Against Planet • Room Tone: screaming wind shear", "linked_scenes": "Act IV", "lighting": "Solar silhouette", "audio": "Wind shear"},
        ],
        "props": [
            {
                "code": "#Prop 01",
                "name": "Neural Overclock Key",
                "owner_character": "Chief Engineer Sean",
                "material_and_wear": "Matte carbon-fiber casing with micro-gold contacts and hairline scratches",
                "narrative_utility": "Identity key containing decrypted security clearance",
                "description": "Carbon-fiber neural key",
                "material": "Matte carbon-fiber",
                "weight": "Identity key",
                "action": "Inserted into neuro-port with tactile dual-click",
            },
            {"code": "#Prop 02", "name": "Ion Pulse Welder", "owner_character": "Chief Engineer Sean", "material_and_wear": "Machined titanium with heat-tinted nozzle", "narrative_utility": "Breach tool", "description": "Pulse welder", "material": "Titanium", "weight": "Breach tool", "action": "Armed with trigger snap"},
            {"code": "#Prop 03", "name": "Quantum Storage Shard", "owner_character": "Ensemble / World Artifact", "material_and_wear": "Synthetic black diamond crystal", "narrative_utility": "Mainframe data core", "description": "Storage shard", "material": "Synthetic diamond", "weight": "Data core", "action": "Locked into slot"},
            {"code": "#Prop 04", "name": "Atmospheric Rebreather Mask", "owner_character": "Chief Engineer Sean", "material_and_wear": "Silicone and polycarbonate", "narrative_utility": "Survival gear", "description": "Rebreather mask", "material": "Silicone", "weight": "Survival gear", "action": "Sealed over mouth"},
            {"code": "#Prop 05", "name": "Zero-Point Catalyst Pin", "owner_character": "Ensemble / World Artifact", "material_and_wear": "Magnetic torus core", "narrative_utility": "Overload detonator", "description": "Detonator pin", "material": "Magnetic torus", "weight": "Detonator", "action": "Twisted and armed"},
        ],
    }

    with patch.object(PolyaScreenwriterEngine, "_call_llm", new=AsyncMock(return_value=mock_llm_payload)):
        gen_resp = client.post(
            f"/api/v1/projects/{project_id}/bible/generate-world-props",
            json={},
            headers=auth_headers,
        )
        assert gen_resp.status_code == 200
        res_data = gen_resp.json()

    assert "generation_meta" in res_data
    meta = res_data["generation_meta"]
    assert meta["engine"] == "polya_ai_director_llm"
    assert meta["director_persona"] == "Polya AI Director"
    assert meta["fallback_reason"] is None
    assert meta["context_ingested"]["style_code"] == "#Style 01"

    # Verify enriched fields are returned
    env0 = res_data["environments"][0]
    assert env0["code"] == "#Env 01"
    assert env0["lighting_code"] == "#Light 01"
    assert "SNR" in env0["lighting_and_audio"]
    assert env0["linked_scenes"] == "Act I (INT. COMMAND CORE)"
    assert env0["lighting"]  # legacy
    assert env0["audio"]     # legacy

    prop0 = res_data["props"][0]
    assert prop0["code"] == "#Prop 01"
    assert prop0["owner_character"] == "Chief Engineer Sean"
    assert prop0["material_and_wear"]
    assert prop0["narrative_utility"]
    assert prop0["material"] # legacy
    assert prop0["weight"]   # legacy
    assert prop0["action"]   # legacy

    # Verify persistent retrieval from GET bible
    get_b = client.get(f"/api/v1/projects/{project_id}/bible", headers=auth_headers)
    assert get_b.status_code == 200
    b_rules = get_b.json()["data"]["world_rules"]
    assert b_rules["generation_meta"]["engine"] == "polya_ai_director_llm"
    assert len(b_rules["environments"]) == 5
    assert len(b_rules["props"]) == 5


def test_world_props_transparent_fallback_tagging(client: TestClient, auth_headers: dict[str, str]):
    """Test 3: Verify graceful fallback when LLM fails, with anti-silent fallback telemetry."""
    create_p = client.post(
        "/api/v1/projects",
        json={
            "title": "Nordic Eclipse",
            "target_style_code": "#Style 07",
            "settings": {"genre": "Epic High Fantasy", "synopsis": "Vikings clash under an eclipse."},
        },
        headers=auth_headers,
    )
    project_id = create_p.json()["data"]["id"]

    # Seed 1 character
    client.post(
        f"/api/v1/projects/{project_id}/characters",
        json={
            "name": "Bjorn Ironside",
            "role": "PROTAGONIST",
            "base_prompt": "Fierce warrior with braided beard and battle axe",
        },
        headers=auth_headers,
    )

    # Simulate LLM router network failure
    async def fail_llm(*args, **kwargs):
        raise ConnectionRefusedError("9Router LLM host 127.0.0.1:8080 unreachable")

    with patch.object(PolyaScreenwriterEngine, "_call_llm", side_effect=fail_llm):
        gen_resp = client.post(
            f"/api/v1/projects/{project_id}/bible/generate-world-props",
            json={},
            headers=auth_headers,
        )
        assert gen_resp.status_code == 200
        res_data = gen_resp.json()

    assert "generation_meta" in res_data
    meta = res_data["generation_meta"]
    assert meta["engine"] == "procedural_fallback"
    assert meta["model"] is None
    assert "unreachable" in meta["fallback_reason"].lower() or "connectionrefused" in meta["fallback_reason"].lower()

    # Verify fallback prop anchors to the existing character
    props = res_data["props"]
    assert len(props) == 5
    assert props[0]["owner_character"] == "Bjorn Ironside"

    # Verify fallback environments have canonical #Light codes and legacy keys
    envs = res_data["environments"]
    assert len(envs) == 5
    for i, e in enumerate(envs):
        assert e["code"] == f"#Env {i + 1:02d}"
        assert e["lighting_code"].startswith("#Light ")
        assert e["lighting"]
        assert e["audio"]
        assert e["lighting_and_audio"]


def test_world_props_stage_6_pipeline_gate(client: TestClient, auth_headers: dict[str, str]):
    """Test 4: Verify Stage 6 Pipeline status transitions to awaiting_gate / completed."""
    create_p = client.post(
        "/api/v1/projects",
        json={
            "title": "Stage 6 Verification Film",
            "settings": {"genre": "Drama", "synopsis": "A theatrical legal drama."},
        },
        headers=auth_headers,
    )
    project_id = create_p.json()["data"]["id"]

    # Before generating world and props, S06 is not_started
    s_before = client.get(f"/api/v1/projects/{project_id}/pipeline-status", headers=auth_headers)
    assert s_before.status_code == 200
    assert s_before.json()["data"]["stages"]["S06"]["status"] == "not_started"

    # Generate world & props
    gen_resp = client.post(
        f"/api/v1/projects/{project_id}/bible/generate-world-props",
        json={},
        headers=auth_headers,
    )
    assert gen_resp.status_code == 200

    # After generation, S06 is awaiting_gate (or completed if approved)
    s_after = client.get(f"/api/v1/projects/{project_id}/pipeline-status", headers=auth_headers)
    assert s_after.status_code == 200
    s06 = s_after.json()["data"]["stages"]["S06"]
    assert s06["status"] in ("awaiting_gate", "completed")
    assert s06["metrics"]["environments_count"] == 5
    assert s06["metrics"]["props_count"] == 5


def test_world_props_dna_freeze_locked_rejection(client: TestClient, auth_headers: dict[str, str]):
    """Test 5: Verify DNA Freeze rejects re-generation with HTTP 400 Bad Request."""
    create_p = client.post(
        "/api/v1/projects",
        json={"title": "Frozen DNA Project", "settings": {"synopsis": "A frozen world story."}},
        headers=auth_headers,
    )
    project_id = create_p.json()["data"]["id"]

    # Lock MPB
    lock_resp = client.post(
        f"/api/v1/projects/{project_id}/bible/lock",
        json={"approval_notes": "Locking Production Design", "confirm_dna_freeze": True},
        headers=auth_headers,
    )
    assert lock_resp.status_code == 200
    assert lock_resp.json()["data"]["is_locked"] is True

    # Generation should be rejected
    blocked = client.post(
        f"/api/v1/projects/{project_id}/bible/generate-world-props",
        json={},
        headers=auth_headers,
    )
    assert blocked.status_code == 400
    assert "locked" in blocked.json()["error"]["message"].lower()
