from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from fastapi.testclient import TestClient
import pytest

from backend.app.api.v1.bible import compile_sheet_prompt
from backend.app.domain.catalog import (
    ACTING_MATRIX,
    CAMERA_MATRIX,
    COMPOSITION_MATRIX,
    LENS_MATRIX,
    LIGHTING_MATRIX,
    SPEED_MATRIX,
    STYLE_CATALOG,
    validate_matrix_code,
)
from backend.app.domain.screenwriter import STYLE_TAXONOMY_FAMILIES, get_style_family
from backend.app.domain.transpiler import LivePromptTranspiler


def test_style_catalog_family_parity_and_validator():
    expected_families = set(STYLE_TAXONOMY_FAMILIES.keys())
    assert len(STYLE_CATALOG) == 18

    for entry in STYLE_CATALOG:
        code = entry["code"]
        fam = entry.get("family")
        assert fam in expected_families, f"{code} missing valid family: {fam}"
        assert fam == get_style_family(code), f"{code} catalog family {fam} != get_style_family {get_style_family(code)}"
        assert validate_matrix_code("style", code) == code

    # Normalization and empty passthrough
    assert validate_matrix_code("cam", "  #cam 01  ") == "#Cam 01"
    assert validate_matrix_code("lens", None) is None
    assert validate_matrix_code("speed", "") == ""

    # Canonical layer lookups
    for layer, matrix in [
        ("style", STYLE_CATALOG),
        ("cam", CAMERA_MATRIX),
        ("lens", LENS_MATRIX),
        ("comp", COMPOSITION_MATRIX),
        ("light", LIGHTING_MATRIX),
        ("act", ACTING_MATRIX),
        ("speed", SPEED_MATRIX),
    ]:
        first_code = matrix[0]["code"]
        assert validate_matrix_code(layer, first_code) == first_code

    # Bogus codes rejected
    with pytest.raises(ValueError):
        validate_matrix_code("cam", "#Cam 99")
    with pytest.raises(ValueError):
        validate_matrix_code("lens", "invalid_lens")
    with pytest.raises(ValueError):
        validate_matrix_code("style", "#Style 99")


def test_frontend_studio_constants_catalog_parity():
    ts_path = Path("frontend/src/lib/studio-constants.ts")
    text = ts_path.read_text(encoding="utf-8")

    expected_pairs = [
        ("#Style 09", "Pixar / Disney 3D Animation"),
        ("#Comp 03", "Central Symmetry"),
        ("#Comp 06", "Frame Within a Frame"),
        ("#Speed 01", "Static / Locked-Off"),
        ("#Speed 05", "Hyper-Speed / Time-Lapse"),
    ]
    for code, label in expected_pairs:
        assert code in text
        assert f'"{label}"' in text, f"Missing aligned frontend label for {code}: {label}"


def test_shot_and_polish_api_rejects_bogus_matrix_codes(client: TestClient, auth_headers: dict[str, str]):
    proj_resp = client.post(
        "/api/v1/projects",
        json={"title": "Wave1 Matrix Validation Project", "target_style_code": "#Style 13"},
        headers=auth_headers,
    )
    assert proj_resp.status_code in (200, 201)
    project_id = proj_resp.json()["data"]["id"]

    scene_resp = client.post(
        f"/api/v1/projects/{project_id}/scenes",
        json={"act_number": 1, "scene_number": 1, "slugline": "INT. WORKSHOP - NIGHT", "narrative_goal": "Craft check"},
        headers=auth_headers,
    )
    assert scene_resp.status_code in (200, 201)
    scene_id = scene_resp.json()["data"]["id"]

    # Reject bogus camera_code on POST /scenes/{scene_id}/shots
    bad_shot = client.post(
        f"/api/v1/scenes/{scene_id}/shots",
        json={"camera_code": "#Cam 99", "duration_seconds": 3.0},
        headers=auth_headers,
    )
    assert bad_shot.status_code == 422

    # Reject bogus lens_code
    bad_lens = client.post(
        f"/api/v1/scenes/{scene_id}/shots",
        json={"lens_code": "invalid_lens", "duration_seconds": 3.0},
        headers=auth_headers,
    )
    assert bad_lens.status_code == 422

    # Create valid shot (including empty optional code tolerance)
    good_shot = client.post(
        f"/api/v1/scenes/{scene_id}/shots",
        json={"camera_code": "#Cam 01", "lens_code": "", "light_code": "#Light 05", "duration_seconds": 4.0},
        headers=auth_headers,
    )
    assert good_shot.status_code in (200, 201)
    shot_id = good_shot.json()["data"]["id"]

    # Reject bogus lens_code on PUT /shots/{shot_id}
    bad_update = client.put(
        f"/api/v1/shots/{shot_id}",
        json={"lens_code": "invalid_lens"},
        headers=auth_headers,
    )
    assert bad_update.status_code == 422

    # Allow partial empty/None update on PUT /shots/{shot_id}
    good_update = client.put(
        f"/api/v1/shots/{shot_id}",
        json={"lens_code": "#Lens 03", "comp_code": ""},
        headers=auth_headers,
    )
    assert good_update.status_code == 200

    # Reject bogus style_code on POST /scenes/{scene_id}/director-polish
    bad_polish = client.post(
        f"/api/v1/scenes/{scene_id}/director-polish",
        json={"style_code": "#Style 99"},
        headers=auth_headers,
    )
    assert bad_polish.status_code == 422


def test_compile_sheet_prompt_four_families_and_rag_cues():
    char = SimpleNamespace(
        id=uuid.uuid4(),
        dna_seed=654321,
        name="Kael",
        base_prompt="30yo courier with sharp cheekbones and copper aviator goggles",
        costume_design="worn ochre parka",
    )

    def run_sheet(style_code: str, cues: str = ""):
        proj = SimpleNamespace(target_style_code=style_code)
        bible = SimpleNamespace(
            style_parameters={"master_style_code": style_code},
            color_grading="Muted slate and amber highlights",
        )
        return compile_sheet_prompt(char, proj, bible, slot="closeup", director_rag_cues=cues)

    # Photorealistic #Style 02
    s02 = run_sheet("#Style 02", cues="IMAX 70mm silver halide texture")
    assert "Unretouched RAW photographic studio casting portrait" in s02["positive_prompt"]
    assert "IMAX 70mm silver halide texture" in s02["positive_prompt"]
    assert "(#D4D4D4)" not in s02["positive_prompt"]

    # Stylized 3D: Pixar (#Style 09), Donghua (#Style 06), Arcane (#Style 11)
    s09 = run_sheet("#Style 09")
    assert "3d" in s09["positive_prompt"].lower()
    assert "2D anime" not in s09["positive_prompt"]
    assert "RAW photographic" not in s09["positive_prompt"]
    for ban in ("cartoon", "illustration", "3d cartoon", "3d render", "anime"):
        assert ban not in s09["negative_prompt"].lower()

    s06 = run_sheet("#Style 06")
    s11 = run_sheet("#Style 11")
    for s3d in (s06, s11):
        assert "3d" in s3d["positive_prompt"].lower()
        assert "RAW photographic" not in s3d["positive_prompt"]
        assert "cartoon" not in s3d["negative_prompt"].lower()

    # Stop-Motion (#Style 13)
    s13 = run_sheet("#Style 13", cues="armature tabletop tungsten key")
    assert "stop-motion" in s13["positive_prompt"].lower()
    assert "clay" in s13["positive_prompt"].lower() or "plasticine" in s13["positive_prompt"].lower()
    assert "DSLR skin" not in s13["positive_prompt"]
    assert "armature tabletop tungsten key" in s13["positive_prompt"]
    for ban in ("clay", "stop-motion", "cartoon", "illustration", "miniature"):
        assert ban not in s13["negative_prompt"].lower()

    # Anime / 2D (#Style 16, #Style 17)
    s16 = run_sheet("#Style 16")
    s17 = run_sheet("#Style 17")
    for s2d in (s16, s17):
        assert "2d" in s2d["positive_prompt"].lower() or "animation" in s2d["positive_prompt"].lower()
        assert "RAW photographic" not in s2d["positive_prompt"]
        for ban in ("cartoon", "illustration", "anime", "watercolor", "graphic novel"):
            assert ban not in s2d["negative_prompt"].lower()


@pytest.mark.anyio
async def test_transpiler_7layer_hydration_and_style_safety():
    # Verify Lens optical_physics, Lighting tech specs (Kelvin), and Acting cue + micro-expression
    # are hydrated EVEN when action_description is non-empty!
    hydrated = LivePromptTranspiler.transpile(
        provider_target="9router",
        style_code="#Style 02",
        camera_code="#Cam 01",
        lens_code="#Lens 01",
        comp_code="#Comp 01",
        light_code="#Light 05",
        act_code="#Act 04",
        speed_code="#Speed 03",
        action_description="Character stares silently across the desk",
    )
    pos_low = hydrated["positive_prompt"].lower()
    assert "1800k" in pos_low  # From LIGHTING_MATRIX["#Light 05"]["technical_specifications"]
    assert "oval out-of-focus bokeh" in pos_low or "horizontal blue/streak lens flares" in pos_low  # From LENS_MATRIX["#Lens 01"]["optical_physics"]
    assert "soft downward eye saccade" in pos_low  # From ACTING_MATRIX["#Act 04"]["micro_expressions"]

    # Verify style safety across non-photorealistic styles & all image/video engines
    non_photo_styles = ["#Style 09", "#Style 13", "#Style 15", "#Style 16"]
    engines = ["9router", "sd35", "flux", "veo", "comfyui"]
    for st in non_photo_styles:
        for eng in engines:
            res = LivePromptTranspiler.transpile(
                provider_target=eng,
                style_code=st,
                action_description="Walking along the ridge at dusk",
            )
            neg_low = res["negative_prompt"].lower()
            p_low = res["positive_prompt"].lower()
            assert "photorealistic" not in p_low, f"{st}/{eng} leaked photorealistic into positive"
            assert "raw photographic" not in p_low, f"{st}/{eng} leaked RAW photographic into positive"
            for forbidden in ("cartoon", "illustration", "3d cartoon"):
                assert forbidden not in neg_low, f"{st}/{eng} leaked forbidden negative '{forbidden}'"

    # Verify transpile_with_rag includes flux and sd35 in compiled_engines
    with (
        patch("backend.app.domain.director_rag.DirectorRAGClient.retrieve", new_callable=AsyncMock, return_value={"director_context": "", "shots": [], "grammars": []}),
        patch(
            "backend.app.services.screenwriter_rag.ScreenwriterRAGClient.retrieve_scene_craft",
            new_callable=AsyncMock,
            return_value={"screenwriter_context": "", "crafts": []},
        ),
    ):
        rag_res = await LivePromptTranspiler.transpile_with_rag(
            provider_target="9router",
            style_code="#Style 13",
            action_description="Adjusting miniature brass gears",
        )
    assert "flux" in rag_res["compiled_engines"]
    assert "sd35" in rag_res["compiled_engines"]
    assert rag_res["metadata"]["style_family"] == "stop_motion"
    assert "cartoon" not in rag_res["compiled_engines"]["sd35"]["negative_prompt"].lower()
    assert "cartoon" not in rag_res["compiled_engines"]["flux"]["negative_prompt"].lower()


def test_previews_forward_sanitized_negative_prompt(client: TestClient, auth_headers: dict[str, str], tmp_path: Path):
    proj_resp = client.post(
        "/api/v1/projects",
        json={"title": "Anime Preview Negative Parity", "target_style_code": "#Style 15"},
        headers=auth_headers,
    )
    assert proj_resp.status_code in (200, 201)
    project_id = proj_resp.json()["data"]["id"]

    scene_resp = client.post(
        f"/api/v1/projects/{project_id}/scenes",
        json={"act_number": 1, "scene_number": 1, "slugline": "EXT. ROOFTOP - NIGHT", "narrative_goal": "Look out over city"},
        headers=auth_headers,
    )
    scene_id = scene_resp.json()["data"]["id"]
    shot_resp = client.post(
        f"/api/v1/scenes/{scene_id}/shots",
        json={"camera_code": "#Cam 01", "light_code": "#Light 06", "duration_seconds": 3.0},
        headers=auth_headers,
    )
    shot_id = shot_resp.json()["data"]["id"]

    captured_requests = []
    mock_img = tmp_path / "preview.webp"
    mock_img.write_bytes(b"RIFF0000WEBP")

    async def fake_generate(req):
        captured_requests.append(req)
        return SimpleNamespace(
            local_url=f"/api/v1/assets/previews/{mock_img.name}",
            local_path=str(mock_img),
            seed=req.seed,
            provider="mock",
            model="mock-v1",
            rate_limit_info=None,
            mime_type="image/webp",
            created_at=None,
        )

    fake_provider = MagicMock()
    fake_provider.generate = AsyncMock(side_effect=fake_generate)

    with (
        patch("backend.app.api.v1.previews.get_image_provider", return_value=fake_provider),
        patch("backend.app.domain.director_rag.DirectorRAGClient.retrieve", new_callable=AsyncMock, return_value={"director_context": "", "shots": [], "grammars": []}),
        patch(
            "backend.app.services.screenwriter_rag.ScreenwriterRAGClient.retrieve_scene_craft",
            new_callable=AsyncMock,
            return_value={"screenwriter_context": "", "crafts": []},
        ),
    ):
        prev_resp = client.post(
            f"/api/v1/shots/{shot_id}/generate-preview",
            json={
                "aspect_ratio": "16:9",
                "provider": "mock",
                "negative_prompt": "blurry, cartoon, anime, watermark",
            },
            headers=auth_headers,
        )
        proj_prev_resp = client.post(
            f"/api/v1/projects/{project_id}/generate-preview",
            json={
                "aspect_ratio": "16:9",
                "provider": "mock",
                "negative_prompt": "blurry, cartoon, anime, watermark",
            },
            headers=auth_headers,
        )

    assert prev_resp.status_code == 200
    assert proj_prev_resp.status_code == 200
    assert len(captured_requests) == 2
    for req_item in captured_requests:
        sent_neg = req_item.negative_prompt.lower()
        # Transpiler anime_2d negative guidance forwarded AND style-contradicting bans stripped
        assert "photorealistic" in sent_neg or "live-action" in sent_neg or "skin pores" in sent_neg
        assert "blurry" in sent_neg
        assert "cartoon" not in sent_neg
        assert "anime" not in sent_neg
