"""Unit & integration tests for CASTING_CLOSEUP_REALISTIC_V1 Hybrid Compiler & Style Gate."""

from __future__ import annotations

from pathlib import Path
import json
from types import SimpleNamespace
import uuid
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import httpx
from PIL import Image
import pytest

from backend.app.api.v1.bible import _apply_sheet_overrides, compile_sheet_prompt
from backend.app.domain.character_prompt_compiler import (
    CASTING_CLOSEUP_PRESET_ID,
    FROZEN_NEGATIVE_PROMPT,
    LAYER_1_QUALITY_AND_SKIN_DNA,
    STYLE_GATE_FULL,
    STYLE_GATE_LIGHT_OVERRIDE,
    STYLE_GATE_STRICT_BYPASS,
    UPSCALE_2K_LOCK_PREFIX,
    DirectorCastingVariables,
    DirectorCharacterDynamicSlots,
    build_deterministic_dynamic_slots,
    compile_upscale_2k_prompt,
    resolve_casting_style_gate,
    resolve_provider_dimensions,
    resolve_style_gate,
    resolve_upscale_2k_target_dimensions,
)
from backend.app.domain.director_rag import DirectorRAGClient
from backend.app.domain.transpiler import LivePromptTranspiler
from backend.app.infrastructure.database.models.character import CharacterModel, CharacterStateModel
from backend.app.infrastructure.database.models.project import MasterProductionBibleModel, ProjectModel
from backend.app.infrastructure.universal_image_adapter import (
    UniversalImageAdapter,
    UniversalImageRequest,
    UniversalImageResult,
    supports_native_2k_upscale,
)


def _make_char_proj_bible(style_code: str = "#Style 02", *, face_ref: bool = False):
    proj_id = uuid.uuid4()
    char = CharacterModel(
        id=uuid.uuid4(),
        project_id=proj_id,
        name="Baskara Mahendra",
        role="PROTAGONIST",
        base_prompt=(
            "34-year-old Indonesian man with angular jawline, weathered brow, deep-set dark brown eyes, "
            "faint scar across left cheek, short textured black hair, wearing a worn dark olive waxed-canvas "
            "field jacket collar over charcoal cotton henley, isolated on a flat seamless Neutral Matte "
            "Light-Medium Studio Gray (#D4D4D4) studio background, even softbox lighting"
        ),
        dna_seed=424242,
        face_ref_asset_id=uuid.uuid4() if face_ref else None,
        closeup_image_url="/api/v1/assets/previews/card1.png",
        front_image_url="/api/v1/assets/previews/card3.png",
    )
    proj = ProjectModel(id=proj_id, title="Nusantara Drift", slug="nusantara-drift", target_style_code=style_code)
    bible = MasterProductionBibleModel(
        id=uuid.uuid4(),
        project_id=proj_id,
        version=1,
        style_parameters={"master_style_code": style_code},
    )
    return char, proj, bible


def test_style_gate_routing_all_18_styles():
    """Verify Style Gate classifies all 18 canonical styles accurately into full, light_override, and strict_bypass."""
    assert len(STYLE_GATE_FULL | STYLE_GATE_LIGHT_OVERRIDE | STYLE_GATE_STRICT_BYPASS) == 18

    for code in sorted(STYLE_GATE_FULL):
        dec = resolve_style_gate(code)
        assert dec.routing_mode == "full"
        assert dec.layer_1_text == LAYER_1_QUALITY_AND_SKIN_DNA
        assert "airbrushed skin" in dec.negative_prompt

    # #Style 05 K-Drama light override
    d05 = resolve_style_gate("#Style 05")
    assert d05.routing_mode == "light_override"
    assert "editorial human skin with soft porcelain clarity" in d05.layer_1_text
    assert "natural dry lip texture" not in d05.layer_1_text
    assert "beauty filter" in d05.negative_prompt

    # #Style 12 UE5 Metahuman MUST strip CGI, 3D render, Unreal Engine from negative prompt
    d12 = resolve_style_gate("#Style 12")
    assert d12.routing_mode == "light_override"
    assert "Unreal Engine 5 Metahuman" in d12.layer_1_text
    neg12_tokens = {t.strip().lower() for t in d12.negative_prompt.split(",")}
    assert "cgi" not in neg12_tokens
    assert "3d render" not in neg12_tokens
    assert "unreal engine" not in neg12_tokens
    assert "airbrushed skin" in neg12_tokens

    # #Style 18 Vintage 1970s adjusts color grading to 35mm archival film
    d18 = resolve_style_gate("#Style 18")
    assert d18.routing_mode == "light_override"
    assert "35mm archival Technicolor" in d18.layer_1_text
    assert "Unedited 16-bit RAW" not in d18.layer_1_text

    # Strict bypass for all non-photorealistic styles (#Style 06, 09, 10, 11, 13, 14, 15, 16, 17)
    for code in sorted(STYLE_GATE_STRICT_BYPASS):
        dec = resolve_style_gate(code)
        assert dec.routing_mode == "strict_bypass"
        char, proj, bible = _make_char_proj_bible(code)
        c1 = compile_sheet_prompt(char, proj, bible, "closeup")
        assert c1["routing_mode"] == "strict_bypass"
        assert c1["preset_id"] is None
        assert "Hasselblad X2D" not in c1["positive_prompt"]
        assert "85mm portrait lens at f/4.5" not in c1["positive_prompt"]
        assert "visible pores on cheeks" not in c1["positive_prompt"]


def test_layer_separation_card1_vs_cards_2_to_8_vs_states_and_scene_bypass():
    """Verify Layer 1+2+3 on Card 1, Layer 1+2 only on Cards 2-8 & States, and full bypass on scene transpiler."""
    char, proj, bible = _make_char_proj_bible("#Style 02")

    # Card 1: Layer 1 + Layer 2 + Layer 3, no old 100mm f/5.6, no shot RAG leakage
    c1 = compile_sheet_prompt(
        char,
        proj,
        bible,
        "closeup",
        director_rag_cues="dramatic neon rim light low-angle wide tracking shot",
    )
    assert c1["preset_id"] == CASTING_CLOSEUP_PRESET_ID
    assert c1["routing_mode"] == "full"
    assert c1["layers_applied"] == ["layer_1", "layer_2", "layer_3"]
    assert c1["recommended_aspect_ratio"] == "1:1"
    assert c1["width"] == 1024
    assert c1["height"] == 1024
    assert "Hasselblad X2D / Phase One" in c1["positive_prompt"]
    assert "85mm portrait lens at f/4.5, ISO 100" in c1["positive_prompt"]
    assert "Square 1:1 framing." in c1["positive_prompt"]
    assert "butterfly/clamshell studio lighting" in c1["positive_prompt"]
    assert "visible pores on cheeks, nose, and forehead" in c1["positive_prompt"]
    assert "100mm macro-portrait" not in c1["positive_prompt"]
    assert "f/5.6" not in c1["positive_prompt"]
    assert "85mm prime lens at f/8" not in c1["positive_prompt"]
    assert "neon rim light" not in c1["positive_prompt"]
    assert c1["negative_prompt"] == FROZEN_NEGATIVE_PROMPT

    # Cards 2-8: Layer 1 + Layer 2 ONLY (NO Layer 3 close-up headshot / Square 1:1 / 85mm f/4.5)
    for slot in ("expression", "front", "side", "three_quarter", "back", "tpose", "action"):
        downstream = compile_sheet_prompt(char, proj, bible, slot)
        assert downstream["layers_applied"] == ["layer_1", "layer_2"]
        assert "visible pores on cheeks" in downstream["positive_prompt"]
        assert "butterfly/clamshell studio lighting" in downstream["positive_prompt"]
        assert "close-up headshot from head to upper shoulders" not in downstream["positive_prompt"]
        assert "Square 1:1 framing" not in downstream["positive_prompt"]
        assert "85mm portrait lens at f/4.5" not in downstream["positive_prompt"]
        if slot in ("expression", "front"):
            assert downstream["recommended_aspect_ratio"] == "16:9"
            if slot == "expression":
                assert "3-column by 2-row grid" in downstream["positive_prompt"]
            else:
                assert "3-column, 4-panel" in downstream["positive_prompt"]
                assert "NO head shown" in downstream["positive_prompt"]
        else:
            assert downstream["recommended_aspect_ratio"] == "3:4"

    # Dynamic State: Layer 1 + Layer 2 ONLY, preserving injuries_and_wear cleanly
    state = CharacterStateModel(
        id=uuid.uuid4(),
        character_id=char.id,
        state_code="#State 03",
        state_label="Crisis Damage",
        wardrobe="Torn olive field jacket, mud-stained",
        injuries_and_wear="Bleeding scratch across eyebrow, sweat and ash",
        expression_anchor="Gritted jaw, fierce focus",
    )
    st_compiled = compile_sheet_prompt(char, proj, bible, "state", target_state=state)
    assert st_compiled["layers_applied"] == ["layer_1", "layer_2"]
    assert "Bleeding scratch across eyebrow" in st_compiled["positive_prompt"]
    assert "butterfly/clamshell studio lighting" in st_compiled["positive_prompt"]
    assert "close-up headshot from head to upper shoulders" not in st_compiled["positive_prompt"]
    assert "85mm portrait lens at f/4.5" not in st_compiled["positive_prompt"]

    # Storyboard / Scene Transpiler MUST bypass CASTING_CLOSEUP_REALISTIC_V1 completely
    scene_res = LivePromptTranspiler.transpile(
        provider_target="google_flow",
        style_code="#Style 02",
        camera_code="#Cam 07",
        lens_code="#Lens 01",
        light_code="#Light 01",
        action_description="Hero walks across misty bridge at dawn",
    )
    assert "butterfly/clamshell studio lighting" not in scene_res["positive_prompt"]
    assert "Square 1:1 framing" not in scene_res["positive_prompt"]


def test_sheet_overrides_priority_over_frozen_template():
    """User manual sheet_overrides remain highest priority when present."""
    char, proj, bible = _make_char_proj_bible("#Style 02")
    compiled = compile_sheet_prompt(char, proj, bible, "closeup")
    eff = _apply_sheet_overrides(
        compiled,
        {
            "prompt_override": "USER CUSTOM CLOSEUP OVERRIDE",
            "negative_prompt_override": "custom ban, watermark",
        },
        "#Style 02",
    )
    assert eff["has_override"] is True
    assert eff["effective_prompt"] == "USER CUSTOM CLOSEUP OVERRIDE"
    assert eff["effective_negative_prompt"] == "custom ban, watermark"


def test_provider_2k_square_and_1k_autocap():
    """Initial 1K stays 1024x1024 across providers; 2K targets 2048x2048 on 2K providers and caps to 1K on 1K providers."""
    assert resolve_casting_style_gate("#Style 02") == resolve_style_gate("#Style 02")
    assert DirectorCastingVariables is DirectorCharacterDynamicSlots

    for prov_2k in ("seedream-5-5", "flux", "qwen-image-3", "adobe-firefly-4", "google-flow"):
        assert resolve_provider_dimensions(prov_2k, 1024, 1024, "1:1") == (1024, 1024)
        assert resolve_provider_dimensions(prov_2k, 2048, 2048, "1:1") == (2048, 2048)

    for prov_1k in ("9router", "ag_gemini_flash", "sd35_large_hf", "gpt-2-6", "leonardo-phoenix", "mock"):
        assert resolve_provider_dimensions(prov_1k, 1024, 1024, "1:1") == (1024, 1024)
        assert resolve_provider_dimensions(prov_1k, 2048, 2048, "1:1") == (1024, 1024)

    assert resolve_upscale_2k_target_dimensions("closeup") == (2048, 2048, "1:1")
    assert resolve_upscale_2k_target_dimensions("expression") == (2048, 1152, "16:9")
    assert resolve_upscale_2k_target_dimensions("front") == (2048, 1152, "16:9")
    assert resolve_upscale_2k_target_dimensions("front", aspect_ratio="3:4") == (1536, 2048, "3:4")
    assert resolve_upscale_2k_target_dimensions("state") == (2048, 2048, "1:1")


@pytest.mark.anyio
async def test_universal_adapter_9router_fallback_caps_2k_to_1k(tmp_path):
    """If a 2048x2048 1:1 Seedream request fails over to 9Router, fallback must cap to 1024x1024."""
    adapter = UniversalImageAdapter(storage_path=tmp_path)
    captured_sizes = []

    async def fake_openai_compat(req: UniversalImageRequest, width: int, height: int):
        captured_sizes.append((req.provider_id, width, height))
        if req.provider_id == "seedream-5-5":
            raise RuntimeError("Seedream transient 503")
        return SimpleNamespace(
            status="completed",
            local_path=str(tmp_path / "ok.png"),
            local_url="/api/v1/assets/previews/ok.png",
            remote_url=None,
            provider_id="9router",
            model_id="ag/gemini-3.8-flash",
            width=width,
            height=height,
            seed=req.seed,
            fallback_used=False,
            fallback_reason=None,
            mime_type="image/png",
        )

    with patch.object(adapter, "_generate_openai_compatible", side_effect=fake_openai_compat):
        res = await adapter.generate_image(
            UniversalImageRequest(
                provider_id="seedream-5-5",
                prompt="test portrait",
                aspect_ratio="1:1",
                width=2048,
                height=2048,
                enable_fallback=True,
            )
        )

    assert captured_sizes[0] == ("seedream-5-5", 2048, 2048)
    assert captured_sizes[1] == ("9router", 1024, 1024)
    assert res.fallback_used is True


@pytest.mark.anyio
async def test_director_casting_slots_contract_and_offline_fallback():
    """Verify 5-variable Director contract sanitization and offline fallback when bridge 8765 is unreachable."""
    # 1. Offline bridge returns None gracefully
    with patch("backend.app.domain.director_rag.httpx.AsyncClient.post", side_effect=httpx.ConnectError("8765 offline")):
        res = await DirectorRAGClient(enabled=True).retrieve_character_casting_slots(
            character_name="Baskara",
            raw_biometric_text="34yo man with scar",
            style_code="#Style 02",
        )
    assert res is None

    # 2. Sanitization strips camera/lighting/hex/name leaks even if supplied by Director cache
    slots = build_deterministic_dynamic_slots(
        base_prompt="ignored",
        char_name="Baskara",
        style_code="#Style 02",
        cached_slots={
            "character_identity_and_facial_features": "Baskara is a 34yo man shot on 50mm f/1.4 with neon rim lighting #D4D4D4",
            "facial_expression": "calm neutral gaze",
            "hair_style_and_color": "Short dark hair",
            "wardrobe_and_accessories_tactile_details": "worn canvas collar",
            "studio_backdrop_tone": "neutral medium-grey",
            "routing_hint": "strict_bypass",  # Style Gate must override this for #Style 02
        },
    )
    assert isinstance(slots, DirectorCharacterDynamicSlots)
    assert "Baskara" not in slots.character_identity_and_facial_features
    assert "50mm" not in slots.character_identity_and_facial_features
    assert "neon rim lighting" not in slots.character_identity_and_facial_features
    assert "#D4D4D4" not in slots.character_identity_and_facial_features
    assert slots.routing_hint == "full"


def test_upscale_2k_prompt_compiler_and_capabilities():
    """Verify upscale_2k prompt compiler respects Style Gate, overrides, strict_bypass, and capabilities."""
    # Photorealistic full + sheet override
    up_photo = compile_upscale_2k_prompt(
        slot_key="closeup",
        style_code="#Style 02",
        base_positive_prompt="MANUAL OVERRIDE SUBJECT",
        base_negative_prompt=FROZEN_NEGATIVE_PROMPT,
        has_override=True,
    )
    assert up_photo["positive_prompt"].startswith(UPSCALE_2K_LOCK_PREFIX)
    assert "MANUAL OVERRIDE SUBJECT" in up_photo["positive_prompt"]
    assert LAYER_1_QUALITY_AND_SKIN_DNA in up_photo["positive_prompt"]
    assert (up_photo["target_width"], up_photo["target_height"]) == (2048, 2048)

    # #Style 12 keeps CGI/3D/Unreal Engine stripped in negative prompt
    d12 = resolve_casting_style_gate("#Style 12")
    up_12 = compile_upscale_2k_prompt(
        slot_key="front",
        style_code="#Style 12",
        base_positive_prompt="4-panel composite reference",
        base_negative_prompt=d12.negative_prompt,
    )
    neg12_tokens = {t.strip().lower() for t in up_12["negative_prompt"].split(",")}
    assert "unreal engine" not in neg12_tokens
    assert "cgi" not in neg12_tokens
    assert (up_12["target_width"], up_12["target_height"]) == (2048, 1152)
    assert up_12["aspect_ratio"] == "16:9"
    assert "4-panel composite grid layout" in up_12["positive_prompt"]

    # Card 2 (expression): preserves 3x2 6-panel grid layout and facial biometric identity
    up_expr = compile_upscale_2k_prompt(
        slot_key="expression",
        style_code="#Style 02",
        base_positive_prompt="3x2 expression sheet grid",
        base_negative_prompt=FROZEN_NEGATIVE_PROMPT,
    )
    assert up_expr["positive_prompt"].startswith(UPSCALE_2K_LOCK_PREFIX)
    assert (up_expr["target_width"], up_expr["target_height"]) == (2048, 1152)
    assert up_expr["aspect_ratio"] == "16:9"
    assert "3-column by 2-row (3x2) 6-panel expression grid layout" in up_expr["positive_prompt"]
    assert "identical facial biometric identity" in up_expr["positive_prompt"]

    # strict_bypass (Anime #Style 15): NO skin pores, NO Hasselblad
    up_anime = compile_upscale_2k_prompt(
        slot_key="closeup",
        style_code="#Style 15",
        base_positive_prompt="2D anime character portrait",
        base_negative_prompt="photorealism",
        style_family="anime_2d",
    )
    assert up_anime["positive_prompt"].startswith(UPSCALE_2K_LOCK_PREFIX)
    assert "visible pores on cheeks" not in up_anime["positive_prompt"]
    assert "Hasselblad" not in up_anime["positive_prompt"]
    assert "cel-shading" in up_anime["positive_prompt"]

    # Provider 2K capability checks
    assert supports_native_2k_upscale("seedream-5-5")[0] is True
    assert supports_native_2k_upscale("flux", "flux-kontext-pro")[0] is True
    assert supports_native_2k_upscale("gemini-direct", "gemini-3.1-flash-image")[0] is True
    assert supports_native_2k_upscale("gemini-direct", "imagen-4.0-generate-001")[0] is False
    assert supports_native_2k_upscale("9router")[0] is False
    assert supports_native_2k_upscale("sd35_large_hf")[0] is False
    assert supports_native_2k_upscale("google-flow")[0] is False


def test_upscale_2k_and_revert_1k_end_to_end(client: TestClient, auth_headers: dict[str, str], tmp_path: Path):
    """Test /upscale-asset (Card 1, Card 2, State), PIL pixel check, sheet_overrides, 1K-cap warning, and /revert-asset."""
    from backend.app.core.config import get_settings

    settings = get_settings()
    storage_dir = settings.effective_preview_storage_path
    storage_dir.mkdir(parents=True, exist_ok=True)

    proj_resp = client.post(
        "/api/v1/projects",
        json={"title": "Upscale 2K E2E", "target_style_code": "#Style 02"},
        headers=auth_headers,
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["data"]["id"]

    char_resp = client.post(
        f"/api/v1/projects/{project_id}/characters",
        json={
            "name": "Baskara Test",
            "role": "PROTAGONIST",
            "base_prompt": "34yo man with short dark hair and olive jacket",
            "dna_seed": 424242,
        },
        headers=auth_headers,
    )
    assert char_resp.status_code == 201
    char_id = char_resp.json()["data"]["id"]

    # Create a State
    st_resp = client.post(
        f"/api/v1/characters/{char_id}/states",
        json={
            "state_code": "#State 03",
            "state_label": "Battle Damaged",
            "wardrobe": "Torn olive jacket",
            "injuries_and_wear": "Scratch on left eyebrow",
            "expression_anchor": "Fierce focus",
        },
        headers=auth_headers,
    )
    assert st_resp.status_code == 201
    state_id = st_resp.json()["data"]["id"]

    # Seed 1K images on disk for Card 1, Card 2, and State
    card1_1k = storage_dir / f"test_c1_1k_{uuid.uuid4().hex[:6]}.png"
    card2_1k = storage_dir / f"test_c2_1k_{uuid.uuid4().hex[:6]}.png"
    state_1k = storage_dir / f"test_st_1k_{uuid.uuid4().hex[:6]}.png"
    Image.new("RGB", (1024, 1024), (180, 180, 180)).save(card1_1k, format="PNG")
    Image.new("RGB", (1344, 768), (180, 180, 180)).save(card2_1k, format="PNG")
    Image.new("RGB", (1024, 1024), (180, 180, 180)).save(state_1k, format="PNG")

    card1_1k_url = f"/api/v1/assets/previews/{card1_1k.name}"
    card2_1k_url = f"/api/v1/assets/previews/{card2_1k.name}"
    state_1k_url = f"/api/v1/assets/previews/{state_1k.name}"

    from backend.app.infrastructure.database.models.character import CharacterModel, CharacterStateModel
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    engine = create_engine(f"sqlite:///{settings.database_path}")
    with Session(engine) as db:
        c = db.execute(select(CharacterModel).where(CharacterModel.id == uuid.UUID(char_id))).scalar_one()
        c.closeup_image_url = card1_1k_url
        c.expression_image_url = card2_1k_url
        st = db.execute(select(CharacterStateModel).where(CharacterStateModel.id == uuid.UUID(state_id))).scalar_one()
        st.image_url = state_1k_url
        db.commit()

    # Add manual sheet_override on Card 1
    ov_resp = client.put(
        f"/api/v1/projects/{project_id}/characters/{char_id}/sheet-overrides",
        json={"slot_key": "closeup", "prompt_override": "CUSTOM USER CLOSEUP OVERRIDE"},
        headers=auth_headers,
    )
    assert ov_resp.status_code == 200

    # Without 2K provider configured, upscale returns clear 422
    fail_resp = client.post(
        f"/api/v1/bible/characters/{char_id}/upscale-asset",
        json={"slot_key": "closeup"},
        headers=auth_headers,
    )
    assert fail_resp.status_code == 422

    # Configure 9Router active + Seedream 5.5 available -> auto-routes to Seedream 5.5
    put_cfg = client.put(
        f"/api/v1/projects/{project_id}/render-provider",
        json={
            "activeProviderId": "9router",
            "applyToAllScenes": True,
            "configs": {
                "9router": {"baseUrl": "http://127.0.0.1:8080/v1", "apiKey": "sk-9r", "modelId": "ag/gemini-3.8-flash"},
                "seedream-5-5": {"baseUrl": "https://ark.ap-southeast.bytepluses.com/api/v3", "apiKey": "sk-seedream-test", "modelId": "seedream-5.5"},
            },
            "freePortals": [],
        },
    )
    assert put_cfg.status_code == 200

    captured_reqs = []

    async def fake_upscale_generate(req: UniversalImageRequest):
        captured_reqs.append(req)
        out_name = f"{req.provider_id}_{uuid.uuid4().hex[:6]}{req.filename_suffix or ''}.png"
        out_path = storage_dir / out_name
        # Write actual target resolution PNG so PIL.Image verification reads real pixels
        Image.new("RGB", (req.width or 2048, req.height or 2048), (200, 200, 200)).save(out_path, format="PNG")
        return UniversalImageResult(
            local_path=str(out_path),
            local_url=f"/api/v1/assets/previews/{out_name}",
            provider_id=req.provider_id,
            model_id=req.model_id or "seedream-5.5",
            width=req.width or 2048,
            height=req.height or 2048,
            is_2k=max(req.width or 2048, req.height or 2048) >= 1920,
            seed=req.seed,
            mime_type="image/png",
        )

    with patch("backend.app.api.v1.bible.UniversalImageAdapter") as MockAdapterCls:
        MockAdapterCls.return_value.generate_image = AsyncMock(side_effect=fake_upscale_generate)

        # 1. Upscale Card 1 -> 2048x2048
        r_c1 = client.post(
            f"/api/v1/bible/characters/{char_id}/upscale-asset",
            json={"slot_key": "closeup"},
            headers=auth_headers,
        )
        assert r_c1.status_code == 200, r_c1.text
        d1 = r_c1.json()
        assert d1["is_2k"] is True
        assert d1["resolution_width"] == 2048
        assert d1["resolution_height"] == 2048
        assert d1["previous_1k_url"] == card1_1k_url
        assert "_2k_" in d1["image_url"]
        assert d1["auto_routed_from"] == "9router"
        assert UPSCALE_2K_LOCK_PREFIX in captured_reqs[0].prompt
        assert "CUSTOM USER CLOSEUP OVERRIDE" in captured_reqs[0].prompt
        assert captured_reqs[0].reference_image_paths == [str(card1_1k.resolve())]
        assert captured_reqs[0].enable_fallback is False

        # 2. Upscale Card 2 -> 2048x1152
        r_c2 = client.post(
            f"/api/v1/bible/characters/{char_id}/upscale-asset",
            json={"slot_key": "expression"},
            headers=auth_headers,
        )
        assert r_c2.status_code == 200
        d2 = r_c2.json()
        assert d2["resolution_width"] == 2048
        assert d2["resolution_height"] == 1152
        assert d2["is_2k"] is True

        # 3. Upscale Dynamic State -> 2048x2048
        r_st = client.post(
            f"/api/v1/bible/characters/{char_id}/upscale-asset",
            json={"slot_key": "state", "state_id": state_id},
            headers=auth_headers,
        )
        assert r_st.status_code == 200
        dst = r_st.json()
        assert dst["resolution_width"] == 2048
        assert dst["resolution_height"] == 2048
        assert dst["is_2k"] is True
        assert dst["previous_1k_url"] == state_1k_url

    # Verify downstream compile_sheet_prompt now uses Card 1's 2K URL as master reference anchor!
    with Session(engine) as db:
        c_updated = db.execute(select(CharacterModel).where(CharacterModel.id == uuid.UUID(char_id))).scalar_one()
        assert c_updated.closeup_image_url == d1["image_url"]
        compiled_front = compile_sheet_prompt(c_updated, None, None, "front")
        assert compiled_front["ref_candidates"][0][1] == d1["image_url"]

    # 4. Revert Card 1 back to 1K
    rev_resp = client.post(
        f"/api/v1/bible/characters/{char_id}/revert-asset",
        json={"slot_key": "closeup"},
        headers=auth_headers,
    )
    assert rev_resp.status_code == 200
    rev_data = rev_resp.json()
    assert rev_data["image_url"] == card1_1k_url
    assert rev_data["is_2k"] is False
    assert rev_data["resolution_width"] == 1024

    # 5. If provider returns < 1920px, server MUST NOT label it 2K (is_2k == False)
    async def fake_sub2k_generate(req: UniversalImageRequest):
        out_name = f"{req.provider_id}_{uuid.uuid4().hex[:6]}_sub2k.png"
        out_path = storage_dir / out_name
        Image.new("RGB", (1024, 1024), (190, 190, 190)).save(out_path, format="PNG")
        return UniversalImageResult(
            local_path=str(out_path),
            local_url=f"/api/v1/assets/previews/{out_name}",
            provider_id=req.provider_id,
            model_id="seedream-5.5",
            width=1024,
            height=1024,
            is_2k=False,
            seed=req.seed,
            mime_type="image/png",
        )

    with patch("backend.app.api.v1.bible.UniversalImageAdapter") as MockAdapterCls:
        MockAdapterCls.return_value.generate_image = AsyncMock(side_effect=fake_sub2k_generate)
        r_sub = client.post(
            f"/api/v1/bible/characters/{char_id}/upscale-asset",
            json={"slot_key": "closeup"},
            headers=auth_headers,
        )
    assert r_sub.status_code == 200
    assert r_sub.json()["is_2k"] is False
    assert r_sub.json()["resolution_width"] == 1024


def test_upscale_2k_skips_misconfigured_seedream_and_isolates_failure(
    client: TestClient, auth_headers: dict[str, str]
):
    """Verify misconfigured Seedream endpoint is not auto-routed, upscale errors are concise, and DB/manifest/normal generate stay isolated."""
    from backend.app.core.config import get_settings
    from backend.app.infrastructure.database.models.character import CharacterModel
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    settings = get_settings()
    storage_dir = settings.effective_preview_storage_path
    storage_dir.mkdir(parents=True, exist_ok=True)

    proj_resp = client.post(
        "/api/v1/projects",
        json={"title": "Upscale Isolation Test", "target_style_code": "#Style 02"},
        headers=auth_headers,
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["data"]["id"]

    char_resp = client.post(
        f"/api/v1/projects/{project_id}/characters",
        json={
            "name": "Aria Vance",
            "role": "PROTAGONIST",
            "base_prompt": "28yo woman with dark braided hair and weathered jacket",
            "dna_seed": 112233,
        },
        headers=auth_headers,
    )
    assert char_resp.status_code == 201
    char_id = char_resp.json()["data"]["id"]

    card1_1k = storage_dir / f"iso_c1_1k_{uuid.uuid4().hex[:6]}.png"
    Image.new("RGB", (1024, 1024), (175, 175, 175)).save(card1_1k, format="PNG")
    card1_1k_url = f"/api/v1/assets/previews/{card1_1k.name}"

    engine = create_engine(f"sqlite:///{settings.database_path}")
    with Session(engine) as db:
        c = db.execute(select(CharacterModel).where(CharacterModel.id == uuid.UUID(char_id))).scalar_one()
        c.closeup_image_url = card1_1k_url
        c.sheet_metadata = {
            "closeup": {
                "image_url": card1_1k_url,
                "width": 1024,
                "height": 1024,
                "resolution_width": 1024,
                "resolution_height": 1024,
                "is_2k": False,
                "status": "completed",
            }
        }
        db.commit()

    # 1. Exact production scenario: gpt-2-6 active + seedream-5-5 misconfigured with aliyuncs.com
    put_mis = client.put(
        f"/api/v1/projects/{project_id}/render-provider",
        json={
            "activeProviderId": "gpt-2-6",
            "applyToAllScenes": True,
            "configs": {
                "gpt-2-6": {
                    "baseUrl": "https://api.openai.com/v1",
                    "apiKey": "sk-proj-test",
                    "modelId": "gpt-image-2.6",
                },
                "seedream-5-5": {
                    "baseUrl": "https://ws-os66oybk9aerfdmb.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
                    "apiKey": "sk-ws-alibaba-key",
                    "modelId": "seedream-5.5",
                },
            },
            "freePortals": [],
        },
    )
    assert put_mis.status_code == 200

    res_422 = client.post(
        f"/api/v1/bible/characters/{char_id}/upscale-asset",
        json={"slot_key": "closeup"},
        headers=auth_headers,
    )
    assert res_422.status_code == 422
    err_422 = res_422.json()["error"]
    assert err_422["code"] == "UPSCALE_2K_PROVIDER_UNSUPPORTED"
    assert "aliyuncs.com" in err_422["message"]

    # 2. Valid BytePlus Seedream config where upstream raises empty ReadTimeout("") -> concise 502 + zero DB corruption
    put_valid = client.put(
        f"/api/v1/projects/{project_id}/render-provider",
        json={
            "activeProviderId": "gpt-2-6",
            "applyToAllScenes": True,
            "configs": {
                "gpt-2-6": {
                    "baseUrl": "https://api.openai.com/v1",
                    "apiKey": "sk-proj-test",
                    "modelId": "gpt-image-2.6",
                },
                "seedream-5-5": {
                    "baseUrl": "https://ark.ap-southeast.bytepluses.com/api/v3",
                    "apiKey": "sk-byteplus-valid",
                    "modelId": "seedream-5.5",
                },
            },
            "freePortals": [],
        },
    )
    assert put_valid.status_code == 200

    with patch("backend.app.api.v1.bible.UniversalImageAdapter") as MockAdapterCls:
        MockAdapterCls.return_value.generate_image = AsyncMock(side_effect=httpx.ReadTimeout(""))
        res_502 = client.post(
            f"/api/v1/bible/characters/{char_id}/upscale-asset",
            json={"slot_key": "closeup"},
            headers=auth_headers,
        )
    assert res_502.status_code == 502
    assert "ReadTimeout" in res_502.json()["error"]["message"]

    # DB & sheet_metadata for Card 1 must be 100% untouched
    with Session(engine) as db:
        c_after = db.execute(select(CharacterModel).where(CharacterModel.id == uuid.UUID(char_id))).scalar_one()
        assert c_after.closeup_image_url == card1_1k_url
        assert c_after.sheet_metadata["closeup"]["image_url"] == card1_1k_url
        assert c_after.sheet_metadata["closeup"]["is_2k"] is False

    # 3. Normal 1K generation on another card (Card 3 front) still works seamlessly
    front_out = storage_dir / f"iso_front_1k_{uuid.uuid4().hex[:6]}.png"
    Image.new("RGB", (1024, 1536), (170, 170, 170)).save(front_out, format="PNG")

    async def fake_normal_1k(req: UniversalImageRequest):
        return UniversalImageResult(
            local_path=str(front_out),
            local_url=f"/api/v1/assets/previews/{front_out.name}",
            provider_id="gpt-2-6",
            model_id="gpt-image-2.6-flare",
            width=1024,
            height=1536,
            is_2k=False,
            seed=req.seed,
            mime_type="image/png",
        )

    with patch("backend.app.api.v1.bible.UniversalImageAdapter") as MockAdapterCls:
        MockAdapterCls.return_value.generate_image = AsyncMock(side_effect=fake_normal_1k)
        res_front = client.post(
            f"/api/v1/characters/{char_id}/generate-asset",
            json={"target_type": "turnaround", "angle": "front", "aspect_ratio": "3:4"},
            headers=auth_headers,
        )
    assert res_front.status_code == 200
    assert res_front.json()["status"] == "completed"
    assert res_front.json()["provider"] == "gpt-2-6"

    # 4. Preview upscale failure leaves preview_manifest.json 100% untouched
    token = f"iso_{uuid.uuid4().hex[:8]}"
    temp_dir = settings.effective_preview_storage_path.parent / "temp_previews" / token
    temp_dir.mkdir(parents=True, exist_ok=True)
    (temp_dir / "closeup.png").write_bytes(card1_1k.read_bytes())
    manifest_path = temp_dir / "preview_manifest.json"
    orig_manifest = {"closeup": {"active_file": "closeup.png", "resolution_width": 1024, "resolution_height": 1024, "is_2k": False}}
    manifest_path.write_text(json.dumps(orig_manifest), encoding="utf-8")

    with patch("backend.app.api.v1.bible.UniversalImageAdapter") as MockAdapterCls:
        MockAdapterCls.return_value.generate_image = AsyncMock(side_effect=RuntimeError("Upstream error"))
        res_prev = client.post(
            f"/api/v1/projects/{project_id}/characters/preview/upscale",
            json={"preview_token": token, "slot": "closeup", "name": "Aria"},
            headers=auth_headers,
        )
    assert res_prev.status_code == 502
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == orig_manifest


def test_manual_upscale_2k_kit_prompts_download_upload_and_revert(
    client: TestClient, auth_headers: dict[str, str]
):
    """Test Manual Upscale 2K Kit across Cards 1-8 & Dynamic States: sheet-prompts preload, /upscale-prompt, /download-asset, PIL upload 2K/1K detection & /revert-asset."""
    import io
    from backend.app.core.config import get_settings
    from backend.app.infrastructure.database.models.character import CharacterModel, CharacterStateModel
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    settings = get_settings()
    storage_dir = settings.effective_preview_storage_path
    storage_dir.mkdir(parents=True, exist_ok=True)

    # 1. Create projects across Style Gate modes: full (#Style 02), light_override (#Style 12), strict_bypass (#Style 15)
    def _create_char(style_code: str, name: str):
        p_resp = client.post(
            "/api/v1/projects",
            json={"title": f"Kit {style_code}", "target_style_code": style_code},
            headers=auth_headers,
        )
        assert p_resp.status_code == 201
        pid = p_resp.json()["data"]["id"]
        c_resp = client.post(
            f"/api/v1/projects/{pid}/characters",
            json={
                "name": name,
                "role": "PROTAGONIST",
                "base_prompt": "32yo woman with sharp eyes, dark braided hair, olive jacket",
                "dna_seed": 778899,
            },
            headers=auth_headers,
        )
        assert c_resp.status_code == 201
        cid = c_resp.json()["data"]["id"]
        return pid, cid

    pid_full, cid_full = _create_char("#Style 02", "Sari Nusantara")
    pid_12, cid_12 = _create_char("#Style 12", "Vex Metahuman")
    pid_15, cid_15 = _create_char("#Style 15", "Ren Anime")

    # Create Dynamic States (#State 01 and #State 03 with physical damage) for cid_full
    st1_resp = client.post(
        f"/api/v1/characters/{cid_full}/states",
        json={
            "state_code": "#State 01",
            "state_label": "Baseline Patrol",
            "wardrobe": "olive tactical jacket and dark trousers",
            "injuries_and_wear": "None",
            "expression_anchor": "calm alert gaze",
        },
        headers=auth_headers,
    )
    assert st1_resp.status_code == 201, st1_resp.text
    st1_id = st1_resp.json()["data"]["id"]

    st3_resp = client.post(
        f"/api/v1/characters/{cid_full}/states",
        json={
            "state_code": "#State 03",
            "state_label": "Battle Damaged",
            "wardrobe": "torn olive tactical jacket with mud splatters",
            "injuries_and_wear": "fresh cheekbone cut, dried mud and soot on sleeve",
            "expression_anchor": "gritted jaw, intense exhausted stare",
        },
        headers=auth_headers,
    )
    assert st3_resp.status_code == 201, st3_resp.text
    st3_id = st3_resp.json()["data"]["id"]

    # Apply manual sheet_override on Card 1, Card 4 (side), and #State 01 for full mode
    ov = client.put(
        f"/api/v1/projects/{pid_full}/characters/{cid_full}/sheet-overrides",
        json={"slot_key": "closeup", "prompt_override": "MANUAL_KIT_OVERRIDE_CLOSEUP"},
        headers=auth_headers,
    )
    assert ov.status_code == 200
    ov_side = client.put(
        f"/api/v1/projects/{pid_full}/characters/{cid_full}/sheet-overrides",
        json={"slot_key": "side", "prompt_override": "MANUAL_KIT_OVERRIDE_SIDE"},
        headers=auth_headers,
    )
    assert ov_side.status_code == 200
    ov_st1 = client.put(
        f"/api/v1/projects/{pid_full}/characters/{cid_full}/sheet-overrides",
        json={"slot_key": "#State 01", "prompt_override": "MANUAL_KIT_OVERRIDE_STATE01"},
        headers=auth_headers,
    )
    assert ov_st1.status_code == 200

    # 2. Assert GET /sheet-prompts & GET /upscale-prompt NEVER invoke AI image providers
    with patch("backend.app.api.v1.bible.UniversalImageAdapter") as MockAdapterCls, \
         patch("backend.app.api.v1.bible.get_image_provider") as MockGetProv:
        # GET /sheet-prompts preload covers ALL Cards 1-8 and ALL Dynamic States
        sp_resp = client.get(f"/api/v1/bible/characters/{cid_full}/sheet-prompts", headers=auth_headers)
        assert sp_resp.status_code == 200, sp_resp.text
        sp_data = sp_resp.json()["data"]
        prompts_map = sp_data["prompts"]
        states_prompts_map = sp_data["states_prompts"]

        expected_card_targets = (
            ("closeup", {"width": 2048, "height": 2048, "aspect_ratio": "1:1"}),
            ("expression", {"width": 2048, "height": 1152, "aspect_ratio": "16:9"}),
            ("front", {"width": 2048, "height": 1152, "aspect_ratio": "16:9"}),
            ("side", {"width": 1536, "height": 2048, "aspect_ratio": "3:4"}),
            ("three_quarter", {"width": 1536, "height": 2048, "aspect_ratio": "3:4"}),
            ("back", {"width": 1536, "height": 2048, "aspect_ratio": "3:4"}),
            ("tpose", {"width": 1536, "height": 2048, "aspect_ratio": "3:4"}),
            ("action", {"width": 1536, "height": 2048, "aspect_ratio": "3:4"}),
        )
        for allowed_slot, expected_target in expected_card_targets:
            item = prompts_map[allowed_slot]
            assert item["upscale_2k_target"] == expected_target
            assert item["style_gate_mode"] == "full"
            assert UPSCALE_2K_LOCK_PREFIX in item["upscale_2k_prompt"]
            assert item["upscale_2k_negative_prompt"]

        assert "3-column by 2-row (3x2) 6-panel expression grid layout" in prompts_map["expression"]["upscale_2k_prompt"]
        assert "MANUAL_KIT_OVERRIDE_CLOSEUP" in prompts_map["closeup"]["upscale_2k_prompt"]
        assert "MANUAL_KIT_OVERRIDE_SIDE" in prompts_map["side"]["upscale_2k_prompt"]

        # Dynamic States in /sheet-prompts also carry upscale_2k_* fields
        for sc in ("#State 01", "#State 03"):
            st_item = states_prompts_map[sc]
            assert st_item["upscale_2k_target"] == {"width": 2048, "height": 2048, "aspect_ratio": "1:1"}
            assert st_item["style_gate_mode"] == "full"
            assert UPSCALE_2K_LOCK_PREFIX in st_item["upscale_2k_prompt"]
            assert st_item["upscale_2k_negative_prompt"]
        assert "MANUAL_KIT_OVERRIDE_STATE01" in states_prompts_map["#State 01"]["upscale_2k_prompt"]
        assert "authentic state-specific surface wear and imperfections" in states_prompts_map["#State 03"]["upscale_2k_prompt"]

        # GET /upscale-prompt read-only endpoint for ALL 8 cards
        for allowed_slot, expected_target in expected_card_targets:
            up_res = client.get(
                f"/api/v1/bible/characters/{cid_full}/upscale-prompt?slot_key={allowed_slot}",
                headers=auth_headers,
            )
            assert up_res.status_code == 200, up_res.text
            assert up_res.json()["slot_key"] == allowed_slot
            assert up_res.json()["upscale_2k_target"] == expected_target
            assert UPSCALE_2K_LOCK_PREFIX in up_res.json()["upscale_2k_prompt"]

        # GET /upscale-prompt for Dynamic States (both query param & dedicated route)
        up_st3_q = client.get(
            f"/api/v1/bible/characters/{cid_full}/upscale-prompt?slot_key=state&state_id={st3_id}",
            headers=auth_headers,
        )
        assert up_st3_q.status_code == 200, up_st3_q.text
        assert up_st3_q.json()["slot_key"] == "state"
        assert up_st3_q.json()["state_id"] == st3_id
        assert up_st3_q.json()["state_code"] == "#State 03"
        assert up_st3_q.json()["upscale_2k_target"] == {"width": 2048, "height": 2048, "aspect_ratio": "1:1"}
        assert "fresh cheekbone cut" in up_st3_q.json()["upscale_2k_prompt"]

        up_st1_ded = client.get(
            f"/api/v1/bible/characters/{cid_full}/states/{st1_id}/upscale-prompt",
            headers=auth_headers,
        )
        assert up_st1_ded.status_code == 200, up_st1_ded.text
        assert "MANUAL_KIT_OVERRIDE_STATE01" in up_st1_ded.json()["upscale_2k_prompt"]

        # Reject unknown slot or bare 'state' without state_id with HTTP 400
        for bad_slot in ("state", "unknown"):
            bad_res = client.get(
                f"/api/v1/bible/characters/{cid_full}/upscale-prompt?slot_key={bad_slot}",
                headers=auth_headers,
            )
            assert bad_res.status_code in (400, 422), f"Expected 400/422 for {bad_slot}, got {bad_res.status_code}"

        # Style Gate compliance: #Style 12 (light_override, strips cgi/3d render/unreal engine) & #Style 15 (strict_bypass)
        up_12 = client.get(
            f"/api/v1/bible/characters/{cid_12}/upscale-prompt?slot_key=side",
            headers=auth_headers,
        )
        assert up_12.status_code == 200
        d12 = up_12.json()
        assert d12["style_gate_mode"] == "light_override"
        neg12 = {t.strip().lower() for t in d12["upscale_2k_negative_prompt"].split(",")}
        assert "cgi" not in neg12
        assert "3d render" not in neg12
        assert "unreal engine" not in neg12

        up_15 = client.get(
            f"/api/v1/bible/characters/{cid_15}/upscale-prompt?slot_key=action",
            headers=auth_headers,
        )
        assert up_15.status_code == 200
        d15 = up_15.json()
        assert d15["style_gate_mode"] == "strict_bypass"
        assert "visible pores on cheeks" not in d15["upscale_2k_prompt"]
        assert "Hasselblad" not in d15["upscale_2k_prompt"]

        MockAdapterCls.assert_not_called()
        MockGetProv.assert_not_called()

    # 3. Seed 1K files for Cards 1-8 & Dynamic States and test GET /download-asset
    def _seed_png(name: str, w: int, h: int) -> str:
        p = storage_dir / f"{name}_{uuid.uuid4().hex[:6]}.png"
        Image.new("RGB", (w, h), (120, 120, 120)).save(p, format="PNG")
        return f"/api/v1/assets/previews/{p.name}"

    c1_1k_url = _seed_png("kit_c1_1k", 1024, 1024)
    c2_1k_url = _seed_png("kit_c2_1k", 1344, 768)
    c3_1k_url = _seed_png("kit_c3_1k", 768, 1024)
    c4_1k_url = _seed_png("kit_c4_1k", 768, 1024)
    c5_1k_url = _seed_png("kit_c5_1k", 768, 1024)
    c6_1k_url = _seed_png("kit_c6_1k", 768, 1024)
    c7_1k_url = _seed_png("kit_c7_1k", 768, 1024)
    c8_1k_url = _seed_png("kit_c8_1k", 768, 1024)
    st3_1k_url = _seed_png("kit_st3_1k", 1024, 1024)

    engine = create_engine(f"sqlite:///{settings.database_path}")
    with Session(engine) as db:
        c = db.execute(select(CharacterModel).where(CharacterModel.id == uuid.UUID(cid_full))).scalar_one()
        c.closeup_image_url = c1_1k_url
        c.expression_image_url = c2_1k_url
        c.front_image_url = c3_1k_url
        c.side_image_url = c4_1k_url
        c.three_quarter_image_url = c5_1k_url
        c.back_image_url = c6_1k_url
        c.tpose_image_url = c7_1k_url
        c.action_image_url = c8_1k_url
        c.sheet_metadata = {
            "closeup": {"image_url": c1_1k_url, "width": 1024, "height": 1024, "is_2k": False},
            "expression": {"image_url": c2_1k_url, "width": 1344, "height": 768, "is_2k": False},
            "front": {"image_url": c3_1k_url, "width": 768, "height": 1024, "is_2k": False},
            "side": {"image_url": c4_1k_url, "width": 768, "height": 1024, "is_2k": False},
            "three_quarter": {"image_url": c5_1k_url, "width": 768, "height": 1024, "is_2k": False},
            "back": {"image_url": c6_1k_url, "width": 768, "height": 1024, "is_2k": False},
            "tpose": {"image_url": c7_1k_url, "width": 768, "height": 1024, "is_2k": False},
            "action": {"image_url": c8_1k_url, "width": 768, "height": 1024, "is_2k": False},
            f"state_{st3_id}": {"image_url": st3_1k_url, "width": 1024, "height": 1024, "is_2k": False},
        }
        st3_obj = db.execute(select(CharacterStateModel).where(CharacterStateModel.id == uuid.UUID(st3_id))).scalar_one()
        st3_obj.image_url = st3_1k_url
        db.commit()

    for dl_slot in ("closeup", "expression", "front", "side", "three_quarter", "back", "tpose", "action"):
        dl_res = client.get(
            f"/api/v1/bible/characters/{cid_full}/download-asset?slot_key={dl_slot}",
            headers=auth_headers,
        )
        assert dl_res.status_code == 200, dl_res.text
        assert "attachment" in dl_res.headers.get("content-disposition", "").lower()
        assert f"sari-nusantara_{dl_slot}_1k.png" in dl_res.headers.get("content-disposition", "")
        assert dl_res.headers.get("cache-control") == "no-store"

    dl_st3 = client.get(
        f"/api/v1/bible/characters/{cid_full}/download-asset?slot_key=state&state_id={st3_id}",
        headers=auth_headers,
    )
    assert dl_st3.status_code == 200, dl_st3.text
    assert "attachment" in dl_st3.headers.get("content-disposition", "").lower()
    assert "sari-nusantara_state_03_1k.png" in dl_st3.headers.get("content-disposition", "")
    assert dl_st3.headers.get("cache-control") == "no-store"

    dl_st3_ded = client.get(
        f"/api/v1/bible/characters/{cid_full}/states/{st3_id}/download-asset",
        headers=auth_headers,
    )
    assert dl_st3_ded.status_code == 200
    assert "sari-nusantara_state_03_1k.png" in dl_st3_ded.headers.get("content-disposition", "")

    for bad_slot in ("state", "unknown"):
        dl_bad = client.get(
            f"/api/v1/bible/characters/{cid_full}/download-asset?slot_key={bad_slot}",
            headers=auth_headers,
        )
        assert dl_bad.status_code in (400, 422)

    # 4. Manual Replace via upload-sheet: 2048x2048 -> is_2k=True + previous_1k_url saved; <1920 -> is_2k=False
    buf_2k = io.BytesIO()
    Image.new("RGB", (2048, 2048), (180, 180, 180)).save(buf_2k, format="PNG")
    up_2k_resp = client.post(
        f"/api/v1/bible/characters/{cid_full}/upload-sheet",
        data={"slot": "closeup"},
        files={"file": ("upscaled_closeup.png", buf_2k.getvalue(), "image/png")},
        headers=auth_headers,
    )
    assert up_2k_resp.status_code == 200, up_2k_resp.text
    u2k = up_2k_resp.json()
    assert u2k["is_2k"] is True
    assert u2k["resolution_width"] == 2048
    assert u2k["resolution_height"] == 2048
    assert u2k["previous_1k_url"] == c1_1k_url
    assert u2k["sheet_metadata"]["is_2k"] is True
    assert u2k["sheet_metadata"]["previous_1k_url"] == c1_1k_url
    assert u2k["sheet_metadata"]["source"] == "manual_upload"

    # Card 1's new 2K URL must immediately become Master Anchor for downstream Cards 2-8
    with Session(engine) as db:
        c_2k = db.execute(select(CharacterModel).where(CharacterModel.id == uuid.UUID(cid_full))).scalar_one()
        assert c_2k.closeup_image_url == u2k["image_url"]
        compiled_side = compile_sheet_prompt(c_2k, None, None, "side")
        assert compiled_side["ref_candidates"][0][1] == u2k["image_url"]

    # Manual Replace with < 1920px on front -> is_2k=False + previous_1k_url preserved
    buf_1k = io.BytesIO()
    Image.new("RGB", (960, 1280), (140, 140, 140)).save(buf_1k, format="PNG")
    up_1k_resp = client.post(
        f"/api/v1/bible/characters/{cid_full}/upload-sheet",
        data={"slot": "front"},
        files={"file": ("front_1k.png", buf_1k.getvalue(), "image/png")},
        headers=auth_headers,
    )
    assert up_1k_resp.status_code == 200, up_1k_resp.text
    u1k = up_1k_resp.json()
    assert u1k["is_2k"] is False
    assert u1k["resolution_width"] == 960
    assert u1k["resolution_height"] == 1280
    assert u1k["previous_1k_url"] == c3_1k_url

    # 5. POST /revert-asset reverts Card 1 back to 1K cleanly
    rev_c1 = client.post(
        f"/api/v1/bible/characters/{cid_full}/revert-asset",
        json={"slot_key": "closeup"},
        headers=auth_headers,
    )
    assert rev_c1.status_code == 200, rev_c1.text
    rc1 = rev_c1.json()
    assert rc1["image_url"] == c1_1k_url
    assert rc1["is_2k"] is False
    assert rc1["resolution_width"] == 1024
    assert rc1["resolution_height"] == 1024

    # 6. Backward compatibility: legacy portrait front (960x1280) keeps 3:4 2K target, while landscape 2K (2048x1152) uses 16:9
    up_legacy = client.get(
        f"/api/v1/bible/characters/{cid_full}/upscale-prompt?slot_key=front",
        headers=auth_headers,
    )
    assert up_legacy.status_code == 200
    assert up_legacy.json()["upscale_2k_target"] == {"width": 1536, "height": 2048, "aspect_ratio": "3:4"}

    buf_front_2k = io.BytesIO()
    Image.new("RGB", (2048, 1152), (180, 180, 180)).save(buf_front_2k, format="PNG")
    up_front_2k_resp = client.post(
        f"/api/v1/bible/characters/{cid_full}/upload-sheet",
        data={"slot": "front"},
        files={"file": ("front_4panel_2k.png", buf_front_2k.getvalue(), "image/png")},
        headers=auth_headers,
    )
    assert up_front_2k_resp.status_code == 200
    uf2k = up_front_2k_resp.json()
    assert uf2k["is_2k"] is True
    assert uf2k["resolution_width"] == 2048
    assert uf2k["resolution_height"] == 1152

    up_landscape = client.get(
        f"/api/v1/bible/characters/{cid_full}/upscale-prompt?slot_key=front",
        headers=auth_headers,
    )
    assert up_landscape.status_code == 200
    assert up_landscape.json()["upscale_2k_target"] == {"width": 2048, "height": 1152, "aspect_ratio": "16:9"}

    # 7. Card 2 (expression) full Manual Upscale 2K Kit Replace -> 2K Ready -> Revert 1K cycle
    buf_expr_2k = io.BytesIO()
    Image.new("RGB", (2048, 1152), (185, 185, 185)).save(buf_expr_2k, format="PNG")
    up_expr_2k_resp = client.post(
        f"/api/v1/bible/characters/{cid_full}/upload-sheet",
        data={"slot": "expression"},
        files={"file": ("expression_3x2_2k.png", buf_expr_2k.getvalue(), "image/png")},
        headers=auth_headers,
    )
    assert up_expr_2k_resp.status_code == 200, up_expr_2k_resp.text
    ue2k = up_expr_2k_resp.json()
    assert ue2k["slot"] == "expression"
    assert ue2k["is_2k"] is True
    assert ue2k["resolution_width"] == 2048
    assert ue2k["resolution_height"] == 1152
    assert ue2k["previous_1k_url"] == c2_1k_url

    rev_c2 = client.post(
        f"/api/v1/bible/characters/{cid_full}/revert-asset",
        json={"slot_key": "expression"},
        headers=auth_headers,
    )
    assert rev_c2.status_code == 200, rev_c2.text
    assert rev_c2.json()["image_url"] == c2_1k_url

    # 8. Row 2 Card (Card 4: side) Replace (1536x2048 -> is_2k=True, <1920 -> is_2k=False) & Revert 1K
    buf_side_2k = io.BytesIO()
    Image.new("RGB", (1536, 2048), (175, 175, 175)).save(buf_side_2k, format="PNG")
    up_side_2k = client.post(
        f"/api/v1/bible/characters/{cid_full}/upload-sheet",
        data={"slot": "side"},
        files={"file": ("side_2k.png", buf_side_2k.getvalue(), "image/png")},
        headers=auth_headers,
    )
    assert up_side_2k.status_code == 200, up_side_2k.text
    us2k = up_side_2k.json()
    assert us2k["slot"] == "side"
    assert us2k["is_2k"] is True
    assert us2k["resolution_width"] == 1536
    assert us2k["resolution_height"] == 2048
    assert us2k["previous_1k_url"] == c4_1k_url

    rev_c4 = client.post(
        f"/api/v1/bible/characters/{cid_full}/revert-asset",
        json={"slot_key": "side"},
        headers=auth_headers,
    )
    assert rev_c4.status_code == 200, rev_c4.text
    assert rev_c4.json()["image_url"] == c4_1k_url
    assert rev_c4.json()["is_2k"] is False
    assert rev_c4.json()["resolution_width"] == 768
    assert rev_c4.json()["resolution_height"] == 1024

    # 9. Dynamic State (#State 03) Manual Upload (<1920 -> is_2k=False; 2048x2048 -> is_2k=True, previous_1k_url saved) & Revert 1K
    buf_st_1k = io.BytesIO()
    Image.new("RGB", (1024, 1024), (130, 130, 130)).save(buf_st_1k, format="PNG")
    up_st_1k = client.post(
        f"/api/v1/bible/characters/{cid_full}/states/{st3_id}/upload-image",
        files={"file": ("state3_1k.png", buf_st_1k.getvalue(), "image/png")},
        headers=auth_headers,
    )
    assert up_st_1k.status_code == 200, up_st_1k.text
    ust1k = up_st_1k.json()
    assert ust1k["is_2k"] is False
    assert ust1k["resolution_width"] == 1024
    assert ust1k["resolution_height"] == 1024
    assert ust1k["previous_1k_url"] == st3_1k_url

    up_st_2k = client.post(
        f"/api/v1/bible/characters/{cid_full}/states/{st3_id}/upload-image",
        files={"file": ("state3_2k.png", buf_2k.getvalue(), "image/png")},
        headers=auth_headers,
    )
    assert up_st_2k.status_code == 200, up_st_2k.text
    ust2k = up_st_2k.json()
    assert ust2k["slot"] == "state"
    assert ust2k["state_id"] == st3_id
    assert ust2k["is_2k"] is True
    assert ust2k["resolution_width"] == 2048
    assert ust2k["resolution_height"] == 2048
    assert ust2k["previous_1k_url"] == ust1k["image_url"]
    assert ust2k["sheet_metadata"]["source"] == "manual_upload"

    # List characters reflects state 2K metadata cleanly from JSON column
    chars_resp = client.get(f"/api/v1/projects/{pid_full}/characters", headers=auth_headers)
    assert chars_resp.status_code == 200
    char_entry = next(ch for ch in chars_resp.json()["data"] if ch["id"] == cid_full)
    st3_entry = next(st for st in char_entry["states"] if st["id"] == st3_id)
    assert st3_entry["image_url"] == ust2k["image_url"]
    assert st3_entry["is_2k"] is True
    assert st3_entry["resolution_width"] == 2048
    assert st3_entry["resolution_height"] == 2048
    assert st3_entry["previous_1k_url"] == ust1k["image_url"]

    rev_st3 = client.post(
        f"/api/v1/bible/characters/{cid_full}/revert-asset",
        json={"slot_key": "state", "state_id": st3_id},
        headers=auth_headers,
    )
    assert rev_st3.status_code == 200, rev_st3.text
    rst3 = rev_st3.json()
    assert rst3["image_url"] == ust1k["image_url"]
    assert rst3["is_2k"] is False
    assert rst3["resolution_width"] == 1024
    assert rst3["resolution_height"] == 1024


def test_row2_multimodal_anchor_role_separation_and_anti_closeup_guards():
    """Verify Card 4-8 role separation, Card 5 anti-close-up framing + negatives, Card 6 rear wardrobe lock, and zero RAG leak."""
    char, proj, bible = _make_char_proj_bible("#Style 02")

    # a) Card 5 (3/4 Hero Angle): [Card 1, Card 3], explicit role separation, 3/4 full-body framing, anti-close-up negatives
    c5 = compile_sheet_prompt(
        char,
        proj,
        bible,
        "three_quarter",
        director_rag_cues="Cinematic photograph, 2.39:1. weathered dwarf warrior in leather armor",
    )
    assert c5["anchors_used"] == ["Card 1 Character Close-Up", "Card 3 Full Body Front"]
    assert "Image 1 (Card 1 Close-Up) is locked STRICTLY for biometric facial identity" in c5["positive_prompt"]
    assert "DO NOT copy the tight close-up headshot crop" in c5["positive_prompt"]
    assert "Image 2 (Card 3 4-Panel Composite) is locked STRICTLY for 100% full-body wardrobe" in c5["positive_prompt"]
    assert "Full-body 3/4 heroic view" in c5["positive_prompt"]
    assert "NEVER a close-up, headshot, or shoulder-cropped portrait" in c5["positive_prompt"]
    assert "dwarf warrior" not in c5["positive_prompt"]
    for ban in ("close-up", "extreme close-up", "headshot", "face-only portrait", "cropped at shoulders", "tight face framing", "passport photo"):
        assert ban in c5["negative_prompt"].lower()
        assert ban in c5["copy_ready_text"].lower()

    # b) Card 6 (Back View): [Card 3, Card 1] order (Card 3 = Image 1 Primary), Card 1 demoted to hair/age only, strict rear lock
    c6 = compile_sheet_prompt(
        char,
        proj,
        bible,
        "back",
        director_rag_cues="Cinematic photograph, 2.39:1. column of cloaked rangers riding across ridge",
    )
    assert c6["anchors_used"] == ["Card 3 Full Body Front", "Card 1 Character Close-Up"]
    assert c6["ref_candidates"][0][0] == "Card 3 Full Body Front"
    assert c6["ref_candidates"][1][0] == "Card 1 Character Close-Up"
    assert "Reference Image 1 (Card 3 4-Panel Composite — PRIMARY ANCHOR)" in c6["positive_prompt"]
    assert "Panel 4 (the right-hand full-body rear wardrobe column of Image 1)" in c6["positive_prompt"]
    assert "Reference Image 2 (Card 1 Close-Up — SECONDARY HAIR/AGE REFERENCE ONLY)" in c6["positive_prompt"]
    assert "DO NOT render a frontal face" in c6["positive_prompt"]
    assert "cloaked rangers" not in c6["positive_prompt"]
    assert "swapped jacket" in c6["negative_prompt"].lower()
    assert "visible front face" in c6["negative_prompt"].lower()

    # c) Cards 4, 7, 8 (Side, T-Pose, Action): strict Card 3 wardrobe lock & anti-close-up guard
    for slot in ("side", "tpose", "action"):
        c_slot = compile_sheet_prompt(char, proj, bible, slot)
        assert c_slot["anchors_used"] == ["Card 1 Character Close-Up", "Card 3 Full Body Front"]
        assert "Image 1 (Card 1 Close-Up) is locked STRICTLY for biometric facial identity" in c_slot["positive_prompt"]
        assert "Image 2 (Card 3 4-Panel Composite) is locked STRICTLY for 100% full-body wardrobe" in c_slot["positive_prompt"]
        assert "close-up" in c_slot["negative_prompt"].lower()
        assert "headshot" in c_slot["negative_prompt"].lower()


@pytest.mark.anyio
async def test_multi_anchor_delivery_flow_and_2k_compression_providers(
    client: TestClient, auth_headers: dict[str, str], tmp_path: Path
):
    """Verify Row 2 multi-anchor paths & ordering in Google Flow queue and non-dropping 2K compression in Gemini/GPT."""
    from backend.app.core.config import get_settings
    from backend.app.infrastructure.database.models.character import CharacterModel
    from backend.app.infrastructure.database.models.flow import FlowImageJobModel
    from backend.workers.flow_image_worker import _is_perceptual_clone_of_refs
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    settings = get_settings()
    storage_dir = settings.effective_preview_storage_path
    storage_dir.mkdir(parents=True, exist_ok=True)

    proj_resp = client.post(
        "/api/v1/projects",
        json={"title": "Multi-Anchor Delivery Test", "target_style_code": "#Style 02"},
        headers=auth_headers,
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["data"]["id"]

    # Configure Google Flow as active provider
    put_flow = client.put(
        f"/api/v1/projects/{project_id}/render-provider",
        json={
            "activeProviderId": "google-flow",
            "applyToAllScenes": True,
            "configs": {
                "google-flow": {
                    "baseUrl": "https://labs.google/fx/api",
                    "apiKey": "",
                    "modelId": "flow-imagen-anchor-pro",
                }
            },
            "freePortals": [],
        },
    )
    assert put_flow.status_code == 200

    char_resp = client.post(
        f"/api/v1/projects/{project_id}/characters",
        json={
            "name": "Orin Anchor Test",
            "role": "PROTAGONIST",
            "base_prompt": "65yo man, long white hair and beard, wears moss-covered fur coat and woven hemp tunic, trousers, leather boots",
            "dna_seed": 991122,
        },
        headers=auth_headers,
    )
    assert char_resp.status_code == 201
    char_id = char_resp.json()["data"]["id"]

    # Create real Card 1 and oversized (>1.5MB) Card 3 files on disk
    import os
    c1_file = storage_dir / f"ma_c1_{uuid.uuid4().hex[:6]}.png"
    c3_file = storage_dir / f"ma_c3_{uuid.uuid4().hex[:6]}.png"
    Image.new("RGB", (1024, 1024), (120, 140, 110)).save(c1_file, format="PNG")
    # High-entropy 2048x1152 image (>1.5MB PNG) to verify 2K anchor compression never drops Card 3
    noise_bytes = os.urandom(2048 * 1152 * 3)
    Image.frombytes("RGB", (2048, 1152), noise_bytes).save(c3_file, format="PNG")
    assert c3_file.stat().st_size > 1_500_000

    c1_url = f"/api/v1/assets/previews/{c1_file.name}"
    c3_url = f"/api/v1/assets/previews/{c3_file.name}"

    engine = create_engine(f"sqlite:///{settings.database_path}")
    with Session(engine) as db:
        c = db.execute(select(CharacterModel).where(CharacterModel.id == uuid.UUID(char_id))).scalar_one()
        c.closeup_image_url = c1_url
        c.front_image_url = c3_url
        db.commit()

    # 1. Google Flow jobs for Cards 4, 5, 6, 7, 8 must preserve exact multi-anchor ordering & fold anti-closeup bans
    expected_orders = {
        "side": [str(c1_file.resolve()), str(c3_file.resolve())],
        "three_quarter": [str(c1_file.resolve()), str(c3_file.resolve())],
        "back": [str(c3_file.resolve()), str(c1_file.resolve())],
        "tpose": [str(c1_file.resolve()), str(c3_file.resolve())],
        "action": [str(c1_file.resolve()), str(c3_file.resolve())],
    }

    with patch("backend.app.api.v1.bible._assert_socks5_healthy_for_flow", new_callable=AsyncMock):
        for slot, exp_paths in expected_orders.items():
            res = client.post(
                f"/api/v1/characters/{char_id}/generate-asset",
                json={"target_type": "turnaround", "angle": slot, "aspect_ratio": "3:4"},
                headers=auth_headers,
            )
            assert res.status_code == 200, res.text
            job_id = res.json()["job_id"]
            with Session(engine) as db:
                job = db.execute(select(FlowImageJobModel).where(FlowImageJobModel.id == uuid.UUID(job_id))).scalar_one()
                assert job.reference_image_paths == exp_paths
                assert job.aspect_ratio == "3:4"
                assert "Strictly avoid:" in job.prompt
                assert "close-up" in job.prompt.lower()
                if slot == "back":
                    assert "swapped jacket" in job.prompt.lower()

    # 2. Gemini Direct payload preserves BOTH anchors in exact order and compresses 2K Card 3 without dropping it
    adapter = UniversalImageAdapter(storage_path=tmp_path)
    captured_gemini_payloads = []
    out_png_buf = __import__("io").BytesIO()
    Image.new("RGB", (768, 1024), (200, 200, 200)).save(out_png_buf, format="PNG")
    fake_b64_out = __import__("base64").b64encode(out_png_buf.getvalue()).decode("utf-8")

    async def fake_gemini_post(url, json=None, **kwargs):
        captured_gemini_payloads.append(json)
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/png", "data": fake_b64_out}}]}}]},
        )

    with patch("backend.app.infrastructure.universal_image_adapter.httpx.AsyncClient.post", side_effect=fake_gemini_post):
        await adapter.generate_image(
            UniversalImageRequest(
                provider_id="gemini-direct",
                model_id="gemini-3.1-flash-image",
                prompt="Card 5 3/4 Hero",
                negative_prompt="close-up, headshot",
                aspect_ratio="3:4",
                width=768,
                height=1024,
                reference_image_paths=[str(c1_file.resolve()), str(c3_file.resolve())],
                api_key_override="AIza-test",
                enable_fallback=False,
            )
        )
    parts = captured_gemini_payloads[0]["contents"][0]["parts"]
    assert len(parts) == 3  # 1 text + 2 inlineData images (Card 1 & compressed 2K Card 3)
    assert "inlineData" in parts[1] and "inlineData" in parts[2]
    assert len(__import__("base64").b64decode(parts[2]["inlineData"]["data"])) <= 1_500_000

    # 3. Flow Worker perceptual clone guard rejects re-encoded JPEG of Card 1 while allowing distinct render
    reencoded_c1 = __import__("io").BytesIO()
    Image.open(c1_file).convert("RGB").save(reencoded_c1, format="JPEG", quality=85)
    assert _is_perceptual_clone_of_refs(reencoded_c1.getvalue(), [str(c1_file), str(c3_file)]) is True
    distinct_render = __import__("io").BytesIO()
    Image.new("RGB", (896, 1200), (40, 90, 180)).save(distinct_render, format="PNG")
    assert _is_perceptual_clone_of_refs(distinct_render.getvalue(), [str(c1_file), str(c3_file)]) is False


def test_downstream_batch_scope_strictly_cards_4_to_8_plus_states(
    client: TestClient, auth_headers: dict[str, str]
):
    """Verify downstream batch slots exclude Row 1 (Cards 1-3) while single-card Row 1 render still works."""
    from backend.app.domain.character_prompt_compiler import (
        ROW1_MASTER_ANCHOR_SLOTS,
        ROW2_DOWNSTREAM_BATCH_SLOTS,
    )

    assert ROW1_MASTER_ANCHOR_SLOTS == ("closeup", "expression", "front")
    assert ROW2_DOWNSTREAM_BATCH_SLOTS == ("side", "three_quarter", "back", "tpose", "action")
    assert len(ROW2_DOWNSTREAM_BATCH_SLOTS) == 5
    assert set(ROW1_MASTER_ANCHOR_SLOTS).isdisjoint(set(ROW2_DOWNSTREAM_BATCH_SLOTS))

    # Frontend batch estimator & orchestrator strictly exclude Card 2 (expression) & Card 3 (front)
    tsx = Path("frontend/src/components/bible/CharacterMatrixTab.tsx").read_text(encoding="utf-8")
    est_start = tsx.index("const calculateEstimatedAssets =")
    est_end = tsx.index("const handleOpenBatchModal =")
    est_block = tsx[est_start:est_end]
    assert "c.expression_image_url" not in est_block
    assert "c.front_image_url" not in est_block
    for col in ("c.side_image_url", "c.three_quarter_image_url", "c.back_image_url", "c.tpose_image_url", "c.action_image_url"):
        assert col in est_block

    # Regression: single-card manual render on Row 1 (Card 1, Card 2, Card 3) via /generate-asset still works
    proj_resp = client.post("/api/v1/projects", json={"title": "Row1 Single Render Check", "target_style_code": "#Style 02"}, headers=auth_headers)
    assert proj_resp.status_code == 201
    pid = proj_resp.json()["data"]["id"]
    char_resp = client.post(
        f"/api/v1/projects/{pid}/characters",
        json={"name": "Row1 Tester", "role": "PROTAGONIST", "base_prompt": "30yo ranger in olive coat", "dna_seed": 556677},
        headers=auth_headers,
    )
    assert char_resp.status_code == 201
    cid = char_resp.json()["data"]["id"]

    put_cfg = client.put(
        f"/api/v1/projects/{pid}/render-provider",
        json={
            "activeProviderId": "gpt-2-6",
            "applyToAllScenes": True,
            "configs": {
                "gpt-2-6": {
                    "baseUrl": "https://api.openai.com/v1",
                    "apiKey": "sk-proj-test",
                    "modelId": "gpt-image-2.6",
                }
            },
            "freePortals": [],
        },
    )
    assert put_cfg.status_code == 200

    async def fake_row1_gen(req: UniversalImageRequest):
        return UniversalImageResult(
            local_path="data/assets/previews/row1_ok.png",
            local_url="/api/v1/assets/previews/row1_ok.png",
            provider_id=req.provider_id,
            model_id=req.model_id or "gpt-image-2.6",
            width=req.width or 1024,
            height=req.height or 1024,
            seed=req.seed,
        )

    with patch("backend.app.api.v1.bible.UniversalImageAdapter") as MockAdapterCls:
        MockAdapterCls.return_value.generate_image = AsyncMock(side_effect=fake_row1_gen)
        for target_type, angle in (("sheet", "closeup"), ("sheet", "expression"), ("turnaround", "front")):
            r = client.post(
                f"/api/v1/characters/{cid}/generate-asset",
                json={"target_type": target_type, "angle": angle},
                headers=auth_headers,
            )
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "completed"
            assert r.json()["angle"] == angle
