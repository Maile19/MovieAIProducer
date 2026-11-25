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
        if slot == "expression":
            assert downstream["recommended_aspect_ratio"] == "16:9"
            assert "3-column by 2-row grid" in downstream["positive_prompt"]
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
    assert resolve_upscale_2k_target_dimensions("front") == (1536, 2048, "3:4")
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
        base_positive_prompt="Full body turnaround",
        base_negative_prompt=d12.negative_prompt,
    )
    neg12_tokens = {t.strip().lower() for t in up_12["negative_prompt"].split(",")}
    assert "unreal engine" not in neg12_tokens
    assert "cgi" not in neg12_tokens
    assert (up_12["target_width"], up_12["target_height"]) == (1536, 2048)

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
