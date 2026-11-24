from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.app.domain.screenwriter import (
    POLYA_AI_DIRECTOR_SYSTEM_PROMPT,
    PolyaScreenwriterEngine,
    ProjectNarrativeContext,
    sanitize_negative_prompts_for_style,
)


def test_rules_invariants_full_context_ingestion(client: TestClient, auth_headers: dict[str, str]):
    """Gate 1: Verify full DB ingestion (Title, #Style, Cast, #Env/#Prop, Storyboard sluglines) in LLM payload."""
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

    # 4. Seed Environments (#Env 01 with #Light 07) and Props (#Prop 01 Bog Iron Seal) in Bible world_rules
    client.put(
        f"/api/v1/projects/{project_id}/bible",
        json={
            "world_rules": {
                "environments": [
                    {
                        "code": "#Env 01",
                        "name": "Frozen Ash Wastes",
                        "architecture": "Jagged basalt monoliths",
                        "atmosphere": "Sub-zero blizzard",
                        "lighting_code": "#Light 07",
                        "lighting": "Overcast soft northern sky",
                    }
                ],
                "props": [
                    {
                        "code": "#Prop 01",
                        "name": "Rune-Carved Bog Iron Seal",
                        "owner_character": "Captain Astrid",
                        "material_and_wear": "Hand-forged bog iron inlaid with beaten silver runes",
                        "narrative_utility": "Hero ancestral heirloom",
                    }
                ],
            }
        },
        headers=auth_headers,
    )

    # 5. Intercept _call_llm and inspect outgoing prompt messages
    captured_messages = []

    async def fake_call_llm(messages, retry_on_parse_error=True):
        captured_messages.extend(messages)
        return {
            "continuity_rules": [
                "Captain Astrid facial scar and silver hair braid orientation must remain invariant across all acts.",
                "Lighting in Frozen Ash Wastes is anchored to #Light 07 Overcast Soft with sub-zero atmospheric drift.",
                "Rune-Carved Bog Iron Seal must consistently exhibit battle notches along its bevel edge.",
                "Weathering on armor must progress strictly sequentially from #State 01 through #State 05.",
                "Color grade must adhere to #Style 07 desaturated earthen Nordic palette.",
            ],
            "negative_prompts": [
                "lowres, blurry, bad anatomy, bad hands, missing fingers, extra digits",
                "cartoonish 3D render, anime cel shading, watercolor artifacts",
                "oversaturated CGI gloss, plastic skin textures, uncanny valley",
                "unnatural physics, morphing limbs, flickering geometry",
                "watermarks, stock photo signatures, text overlays",
            ],
        }

    with patch.object(PolyaScreenwriterEngine, "_call_llm", side_effect=fake_call_llm):
        gen_resp = client.post(
            f"/api/v1/projects/{project_id}/bible/generate-rules-invariants",
            json={"additional_notes": "Emphasize tactile survival and Nordic frost continuity."},
            headers=auth_headers,
        )
        assert gen_resp.status_code == 200

    # 6. Verify context ingestion into user prompt
    assert len(captured_messages) >= 2
    system_msg = next(m["content"] for m in captured_messages if m["role"] == "system")
    user_msg = next(m["content"] for m in captured_messages if m["role"] == "user")

    assert "Polya AI Director" in system_msg
    assert "Disgraced: The Ash Wastes" in user_msg
    assert "#Style 07" in user_msg
    assert "Captain Astrid" in user_msg
    assert "Warlord Vane" in user_msg
    assert "EXT. ASH WASTES" in user_msg
    assert "#Env 01" in user_msg or "Frozen Ash Wastes" in user_msg
    assert "#Light 07" in user_msg
    assert "#Prop 01" in user_msg or "Bog Iron Seal" in user_msg


def test_rules_invariants_style_aware_clusters_and_conflict_guard():
    """Gate 2: Verify style-aware negative clusters across contrasting styles + style-conflict guard check."""
    engine = PolyaScreenwriterEngine()

    # 1. Test #Style 07 (Photorealistic High Fantasy)
    ctx_photo = ProjectNarrativeContext(
        project_id="test_photo",
        title="High Fantasy Epic",
        synopsis="Knights in mist.",
        genre_tone="Fantasy",
        master_style_code="#Style 07",
        style_name="Epic High Fantasy",
        aesthetic_directives="Weathered leather, authentic chainmail",
        color_grade_emulation="Desaturated earthen tones",
        world_setting="Nordic Realm",
    )
    res_photo = engine._generate_procedural_rules_and_invariants(ctx_photo)
    negs_photo = " ".join(res_photo["negative_prompts"]).lower()
    assert "cartoonish 3d render" in negs_photo or "anime cel shading" in negs_photo
    assert "photorealistic" not in negs_photo
    assert "35mm film" not in negs_photo

    # 2. Test #Style 15 (Anime Shinkai / Ufotable)
    ctx_anime = ProjectNarrativeContext(
        project_id="test_anime",
        title="Sky Wanderers",
        synopsis="Pilots across luminous clouds.",
        genre_tone="Anime",
        master_style_code="#Style 15",
        style_name="Anime (Shinkai / Ufotable)",
        aesthetic_directives="Hyper-detailed sky cloud formations, radiant god rays",
        color_grade_emulation="Luminous ultramarine blues",
        world_setting="Cloud Sea",
    )
    res_anime = engine._generate_procedural_rules_and_invariants(ctx_anime)
    negs_anime = " ".join(res_anime["negative_prompts"]).lower()
    assert "photorealistic live action" in negs_anime or "3d cgi gloss" in negs_anime
    assert "anime" not in negs_anime
    assert "cel shading" not in negs_anime

    # 3. Test #Style 10 (Stylized 3D Animation)
    ctx_3d = ProjectNarrativeContext(
        project_id="test_3d",
        title="Toy Kingdom",
        synopsis="Animated toys venture out.",
        genre_tone="Comedy Animation",
        master_style_code="#Style 10",
        style_name="DreamWorks / Illumination",
        aesthetic_directives="Snappy comedic character timing, expressive cartoon eyes",
        color_grade_emulation="High-contrast vibrant saturated primaries",
        world_setting="Toy Room",
    )
    res_3d = engine._generate_procedural_rules_and_invariants(ctx_3d)
    negs_3d = " ".join(res_3d["negative_prompts"]).lower()
    assert "live-action photograph" in negs_3d or "realistic film grain" in negs_3d
    assert "cartoonish 3d render" not in negs_3d
    assert "3d render" not in negs_3d

    # 4. Test #Style 13 (Stop-Motion Animation)
    ctx_stopmotion = ProjectNarrativeContext(
        project_id="test_stopmotion",
        title="Clay Odyssey",
        synopsis="Plasticine figures in miniature workshop.",
        genre_tone="Whimsical Adventure",
        master_style_code="#Style 13",
        style_name="Stop-Motion Animation",
        aesthetic_directives="Tactile plasticine / clay textures, visible fingerprint impressions",
        color_grade_emulation="Studio miniature warm spotlights",
        world_setting="Workshop",
    )
    res_stopmotion = engine._generate_procedural_rules_and_invariants(ctx_stopmotion)
    negs_stopmotion = " ".join(res_stopmotion["negative_prompts"]).lower()
    assert "smooth digital cgi" in negs_stopmotion or "60fps interpolation" in negs_stopmotion
    assert "clay textures" not in negs_stopmotion
    assert "stop-motion" not in negs_stopmotion

    # 5. Test Programmatic Style-Conflict Sanitizer directly
    # In #Style 15 (Anime), "anime cel shading" must be stripped even if LLM hallucinated it
    raw_anime_neg = ["anime cel shading, lowres, blurry", "cartoonish 3D render, bad hands"]
    sanitized_anime = sanitize_negative_prompts_for_style(raw_anime_neg, "#Style 15")
    assert "anime cel shading" not in sanitized_anime[0].lower()
    assert "lowres, blurry" in sanitized_anime[0]
    assert "cartoonish 3d render" in sanitized_anime[1].lower()

    # In #Style 10 (Stylized 3D), "cartoonish 3D render" must be stripped
    raw_3d_neg = ["cartoonish 3D render, lowres, blurry", "live action film grain"]
    sanitized_3d = sanitize_negative_prompts_for_style(raw_3d_neg, "#Style 10")
    assert "cartoonish 3d render" not in sanitized_3d[0].lower()
    assert "lowres, blurry" in sanitized_3d[0]

    # In #Style 13 (Stop-Motion), "clay textures" must be stripped
    raw_sm_neg = ["clay textures, blurry, missing digits", "hyper-glossy CGI"]
    sanitized_sm = sanitize_negative_prompts_for_style(raw_sm_neg, "#Style 13")
    assert "clay textures" not in sanitized_sm[0].lower()
    assert "blurry, missing digits" in sanitized_sm[0]


def test_rules_invariants_llm_success_and_metadata_persistence(client: TestClient, auth_headers: dict[str, str]):
    """Gate 3: Verify LLM-first success + rules_generation_meta persistence + non-destructive merge preserving envs & props."""
    create_p = client.post(
        "/api/v1/projects",
        json={
            "title": "Solaris Requiem",
            "target_style_code": "#Style 02",
            "settings": {"genre": "Sci-Fi", "synopsis": "An astronaut orbits an intelligent oceanic world."},
        },
        headers=auth_headers,
    )
    assert create_p.status_code == 201
    project_id = create_p.json()["data"]["id"]

    # Seed environments, props, and world_props generation_meta in world_rules
    client.put(
        f"/api/v1/projects/{project_id}/bible",
        json={
            "world_rules": {
                "environments": [
                    {"code": f"#Env {i+1:02d}", "name": f"Station Sector {i+1}", "lighting_code": "#Light 02"}
                    for i in range(5)
                ],
                "props": [
                    {"code": f"#Prop {i+1:02d}", "name": f"Hero Instrument {i+1}", "owner_character": "Astronaut Kris"}
                    for i in range(5)
                ],
                "generation_meta": {
                    "engine": "polya_ai_director_llm",
                    "model": "gemini-3.8-flash",
                },
            }
        },
        headers=auth_headers,
    )

    mock_llm_payload = {
        "continuity_rules": [
            "Astronaut Kris biometric facial contour and blue eye pupil dilation must remain invariant.",
            "Station Sector 01 volumetric God Rays must strictly follow #Light 02 specifications.",
            "Hero Instrument 01 titanium casing wear must maintain hairline scratches across all shots.",
            "Wardrobe pressure suit degradation must progress sequentially from #State 01 to #State 05.",
            "Master #Style 02 70mm IMAX resolution with naturalistic color timing must be enforced.",
        ],
        "negative_prompts": [
            "lowres, blurry, bad anatomy, bad hands, missing fingers, extra digits",
            "cartoonish 3D render, anime cel shading, watercolor artifacts",
            "oversaturated CGI gloss, plastic skin textures, uncanny valley",
            "unnatural physics, morphing limbs, flickering geometry, frame stutter",
            "watermarks, stock photo signatures, text overlays, copyright markings",
        ],
    }

    with patch.object(PolyaScreenwriterEngine, "_call_llm", new=AsyncMock(return_value=mock_llm_payload)):
        gen_resp = client.post(
            f"/api/v1/projects/{project_id}/bible/generate-rules-invariants",
            json={},
            headers=auth_headers,
        )
        assert gen_resp.status_code == 200
        res_data = gen_resp.json()

    assert "rules_generation_meta" in res_data
    meta = res_data["rules_generation_meta"]
    assert meta["engine"] == "polya_ai_director_llm"
    assert meta["director_persona"] == "Polya AI Director"
    assert meta["fallback_reason"] is None
    assert meta["context_ingested"]["style_code"] == "#Style 02"
    assert meta["context_ingested"]["environments_count"] == 5
    assert meta["context_ingested"]["props_count"] == 5

    # Verify dual keys in response
    assert len(res_data["continuity_rules"]) == 5
    assert res_data["continuity_rules"] == res_data["continuity_laws"]
    assert len(res_data["negative_prompts"]) == 5
    assert res_data["negative_prompts"] == res_data["prompt_negatives"]

    # Verify non-destructive merge: GET bible preserves existing environments, props, and generation_meta
    get_b = client.get(f"/api/v1/projects/{project_id}/bible", headers=auth_headers)
    assert get_b.status_code == 200
    b_rules = get_b.json()["data"]["world_rules"]
    assert len(b_rules["environments"]) == 5
    assert len(b_rules["props"]) == 5
    assert b_rules["generation_meta"]["engine"] == "polya_ai_director_llm"
    assert b_rules["rules_generation_meta"]["engine"] == "polya_ai_director_llm"
    assert len(b_rules["continuity_rules"]) == 5
    assert len(b_rules["negative_prompts"]) == 5


def test_rules_invariants_transparent_fallback_and_zero_cyberpunk(client: TestClient, auth_headers: dict[str, str]):
    """Gate 4: Verify transparent procedural fallback tagging + zero Cyberpunk leakage on LLM exception."""
    create_p = client.post(
        "/api/v1/projects",
        json={
            "title": "Viking Siege of Lindisfarne",
            "target_style_code": "#Style 07",
            "settings": {"genre": "Nordic Historical", "synopsis": "Vikings assault a storm-lashed monastery."},
        },
        headers=auth_headers,
    )
    project_id = create_p.json()["data"]["id"]

    client.post(
        f"/api/v1/projects/{project_id}/characters",
        json={
            "name": "Ragnar Lothbrok",
            "role": "PROTAGONIST",
            "base_prompt": "Battle-hardened Norse chieftain with braided beard and war axe",
        },
        headers=auth_headers,
    )

    # Simulate LLM outage
    async def fail_llm(*args, **kwargs):
        raise ConnectionRefusedError("9Router host unreachable")

    with patch.object(PolyaScreenwriterEngine, "_call_llm", side_effect=fail_llm):
        gen_resp = client.post(
            f"/api/v1/projects/{project_id}/bible/generate-rules-invariants",
            json={},
            headers=auth_headers,
        )
        assert gen_resp.status_code == 200
        res_data = gen_resp.json()

    assert "rules_generation_meta" in res_data
    meta = res_data["rules_generation_meta"]
    assert meta["engine"] == "procedural_fallback"
    assert meta["model"] is None
    assert "unreachable" in meta["fallback_reason"].lower() or "connectionrefused" in meta["fallback_reason"].lower()

    # Verify zero Cyberpunk leakage for Nordic Historical project
    all_rules_text = " ".join(res_data["continuity_rules"] + res_data["negative_prompts"]).lower()
    cyberpunk_tokens = ["cyberpunk", "monoblade", "plasma hue", "450nm", "wet asphalt", "03:42 am", "sodium vapor"]
    for token in cyberpunk_tokens:
        assert token not in all_rules_text, f"Detected Cyberpunk leakage token '{token}' in Nordic rules!"

    # Verify rules anchor to Ragnar Lothbrok
    assert any("Ragnar Lothbrok" in r for r in res_data["continuity_rules"])


def test_rules_invariants_dna_freeze_locked_rejection(client: TestClient, auth_headers: dict[str, str]):
    """Gate 5: Verify DNA Freeze (is_locked == True) rejects re-generation with HTTP 400 Bad Request."""
    create_p = client.post(
        "/api/v1/projects",
        json={"title": "Locked DNA Rules Project", "settings": {"synopsis": "A frozen kingdom story."}},
        headers=auth_headers,
    )
    project_id = create_p.json()["data"]["id"]

    # Lock MPB
    lock_resp = client.post(
        f"/api/v1/projects/{project_id}/bible/lock",
        json={"approval_notes": "Locking Rules and Invariants", "confirm_dna_freeze": True},
        headers=auth_headers,
    )
    assert lock_resp.status_code == 200
    assert lock_resp.json()["data"]["is_locked"] is True

    # Re-generation must fail with 400
    blocked = client.post(
        f"/api/v1/projects/{project_id}/bible/generate-rules-invariants",
        json={},
        headers=auth_headers,
    )
    assert blocked.status_code == 400
    assert "locked" in blocked.json()["error"]["message"].lower() or "frozen" in blocked.json()["error"]["message"].lower()


def test_rules_invariants_dual_key_sync_and_manual_crud(client: TestClient, auth_headers: dict[str, str]):
    """Gate 6: Verify dual-key synchronization & manual Showrunner PUT CRUD preservation."""
    create_p = client.post(
        "/api/v1/projects",
        json={
            "title": "Synchronized Dual-Key Epic",
            "target_style_code": "#Style 01",
            "settings": {"genre": "Action", "synopsis": "Explosive chase sequences."},
        },
        headers=auth_headers,
    )
    project_id = create_p.json()["data"]["id"]

    # 1. Generate rules procedurally (with immediate fallback)
    async def fail_llm(*args, **kwargs):
        raise ConnectionRefusedError("9Router host unreachable")

    with patch.object(PolyaScreenwriterEngine, "_call_llm", side_effect=fail_llm):
        gen_resp = client.post(
            f"/api/v1/projects/{project_id}/bible/generate-rules-invariants",
            json={},
            headers=auth_headers,
        )
    assert gen_resp.status_code == 200
    data = gen_resp.json()
    assert data["continuity_rules"] == data["continuity_laws"]
    assert data["negative_prompts"] == data["prompt_negatives"]

    # 2. Showrunner performs manual PUT with modified rules
    custom_laws = [
        "Law 1: Protagonist leather jacket tear pattern must remain on left sleeve.",
        "Law 2: Lens flare color is restricted to warm amber anamorphic streak.",
    ]
    custom_negs = [
        "lowres, blurry, bad anatomy",
        "cartoonish 3D render, anime cel shading",
    ]

    put_resp = client.put(
        f"/api/v1/projects/{project_id}/bible",
        json={
            "world_rules": {
                "continuity_laws": custom_laws,
                "prompt_negatives": custom_negs,
                "environments": [{"code": "#Env 01", "name": "Highway Interchange"}],
                "props": [{"code": "#Prop 01", "name": "Nitrous Oxide Tank"}],
            }
        },
        headers=auth_headers,
    )
    assert put_resp.status_code == 200

    # 3. Verify GET returns synchronized dual keys and preserved environments/props
    get_resp = client.get(f"/api/v1/projects/{project_id}/bible", headers=auth_headers)
    assert get_resp.status_code == 200
    wr = get_resp.json()["data"]["world_rules"]
    assert wr["continuity_laws"] == custom_laws
    assert wr["continuity_rules"] == custom_laws
    assert wr["prompt_negatives"] == custom_negs
    assert wr["negative_prompts"] == custom_negs
    assert len(wr["environments"]) == 1
    assert len(wr["props"]) == 1
