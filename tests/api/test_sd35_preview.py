import base64
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from fastapi.testclient import TestClient
import pytest

from backend.app.core.config import get_settings
from backend.app.domain.transpiler import LivePromptTranspiler
from backend.app.infrastructure.sd35_client import (
    DynamicImageProviderRouter,
    ImageGenerationError,
    ImageGenerationRequest,
    ImageGenerationResult,
    MockImageProvider,
    NineRouterImageProvider,
    RateLimitExceededError,
    SD35HuggingFaceProvider,
    ZeroGPUQuotaExceededError,
    get_image_provider,
)


@pytest.mark.anyio
async def test_sd35_provider_success_flow(tmp_path: Path):
    """Test full SSE streaming lifecycle and local file saving on successful generation."""
    storage_dir = tmp_path / "previews"
    provider = SD35HuggingFaceProvider(
        space_url="https://mock-sd35.hf.space",
        token="hf_mock_token_123",
        default_steps=28,
        storage_path=storage_dir,
        public_url_prefix="/api/v1/assets/previews",
    )

    req = ImageGenerationRequest(
        prompt="Cinematic cyberpunk street",
        seed=42,
        randomize_seed=False,
        width=1024,
        height=576,
        num_inference_steps=28,
    )

    mock_image_bytes = b"RIFF\x00\x00\x00\x00WEBPVP8 \x00\x00\x00\x00"

    sse_lines = [
        "event: heartbeat",
        "data: null",
        "",
        "event: complete",
        'data: [{"url": "https://mock-sd35.hf.space/gradio_api/file=mock_img.webp", "mime_type": "image/webp"}, 42]',
        "",
    ]

    class MockStreamResponse:
        status_code = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def aiter_lines(self):
            for line in sse_lines:
                yield line

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def post(self, url, headers=None, json=None):
            assert "mock-sd35.hf.space/gradio_api/call/infer" in url
            assert headers.get("Authorization") == "Bearer hf_mock_token_123"
            assert json["data"][0] == "Cinematic cyberpunk street"
            assert json["data"][7] == 28
            resp = AsyncMock()
            resp.status_code = 200
            resp.json = lambda: {"event_id": "mock_event_xyz"}
            return resp

        def stream(self, method, url, headers=None):
            assert method == "GET"
            assert "mock_event_xyz" in url
            return MockStreamResponse()

        async def get(self, url, headers=None):
            assert "mock_img.webp" in url
            resp = AsyncMock()
            resp.status_code = 200
            resp.content = mock_image_bytes
            resp.headers = {"content-type": "image/webp"}
            return resp

    with patch("httpx.AsyncClient", MockClient):
        result = await provider.generate(req)

    assert isinstance(result, ImageGenerationResult)
    assert result.seed == 42
    assert result.steps == 28
    assert result.width == 1024
    assert result.height == 576
    assert result.local_url.startswith("/api/v1/assets/previews/sd35_")
    assert result.local_url.endswith(".webp")
    assert Path(result.local_path).exists()
    assert Path(result.local_path).read_bytes() == mock_image_bytes


@pytest.mark.anyio
async def test_sd35_provider_zerogpu_quota_handling(tmp_path: Path):
    """Test handling of Hugging Face ZeroGPU quota exceeded error in SSE stream."""
    storage_dir = tmp_path / "previews"
    provider = SD35HuggingFaceProvider(
        space_url="https://mock-sd35.hf.space",
        storage_path=storage_dir,
    )

    req = ImageGenerationRequest(prompt="A lonely astronaut on Mars")

    sse_lines = [
        "event: error",
        'data: {"error": "You have exceeded your ZeroGPU quota (65s requested vs. 82s left). Try again in 23:59:23. Authenticate with a Hugging Face token for more quota", "title": "ZeroGPU quota exceeded"}',
        "",
    ]

    class MockStreamResponse:
        status_code = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def aiter_lines(self):
            for line in sse_lines:
                yield line

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def post(self, url, headers=None, json=None):
            resp = AsyncMock()
            resp.status_code = 200
            resp.json = lambda: {"event_id": "quota_exceeded_event"}
            return resp

        def stream(self, method, url, headers=None):
            return MockStreamResponse()

    with patch("httpx.AsyncClient", MockClient):
        with pytest.raises(ZeroGPUQuotaExceededError) as exc_info:
            await provider.generate(req)

        assert "ZeroGPU Quota Terlampaui" in str(exc_info.value)
        assert "HF_TOKEN" in str(exc_info.value)


@pytest.mark.anyio
async def test_sd35_provider_general_error_handling(tmp_path: Path):
    """Test handling of general generation failure."""
    provider = SD35HuggingFaceProvider(storage_path=tmp_path / "previews")
    req = ImageGenerationRequest(prompt="Test prompt")

    sse_lines = [
        "event: error",
        'data: {"error": "CUDA out of memory in unet forward"}',
        "",
    ]

    class MockStreamResponse:
        status_code = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def aiter_lines(self):
            for line in sse_lines:
                yield line

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def post(self, url, headers=None, json=None):
            resp = AsyncMock()
            resp.status_code = 200
            resp.json = lambda: {"event_id": "general_err_event"}
            return resp

        def stream(self, method, url, headers=None):
            return MockStreamResponse()

    with patch("httpx.AsyncClient", MockClient):
        with pytest.raises(ImageGenerationError) as exc_info:
            await provider.generate(req)

        assert "CUDA out of memory" in str(exc_info.value)


def test_api_generate_scene_preview_endpoints(client: TestClient, auth_headers: dict[str, str], tmp_path: Path):
    """Test FastAPI scene preview generation endpoint and ZeroGPU quota 429 response."""
    # 1. Create project & scene
    proj_resp = client.post("/api/v1/projects", json={"title": "SD 3.5 Preview Film"}, headers=auth_headers)
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["data"]["id"]

    scene_resp = client.post(
        f"/api/v1/projects/{project_id}/scenes",
        json={
            "act_number": 1,
            "scene_number": 1,
            "slugline": "EXT. RAIN-SLICK ALLEYWAY - NIGHT",
            "narrative_goal": "Detective Kai finds the encrypted neural chip",
            "duration_target": 10.0,
            "auto_split_shots": True,
        },
        headers=auth_headers,
    )
    assert scene_resp.status_code == 201
    scene_id = scene_resp.json()["data"]["id"]

    # 2. Test successful generate scene preview with mock provider
    mock_result = ImageGenerationResult(
        local_path=str(tmp_path / "mock_preview.webp"),
        local_url="/api/v1/assets/previews/sd35_test123_abc.webp",
        remote_url="https://mock.space/img.webp",
        seed=1337,
        width=1024,
        height=576,
        steps=28,
        file_size_bytes=1024,
        mime_type="image/webp",
        sha256_checksum=f"abcdef{uuid.uuid4().hex[:10]}",
        provider="sd35_large_hf",
    )

    mock_provider = AsyncMock()
    mock_provider.generate.return_value = mock_result

    with patch("backend.app.api.v1.previews.get_image_provider", return_value=mock_provider):
        prev_resp = client.post(
            f"/api/v1/scenes/{scene_id}/generate-preview",
            json={"aspect_ratio": "16:9", "steps": 28},
            headers=auth_headers,
        )
        assert prev_resp.status_code == 200
        prev_data = prev_resp.json()["data"]
        assert prev_data["preview_url"] == "/api/v1/assets/previews/sd35_test123_abc.webp"
        assert prev_data["seed"] == 1337
        assert prev_data["scene_id"] == scene_id

        # Verify get_scene now includes preview_url
        get_s_resp = client.get(f"/api/v1/scenes/{scene_id}", headers=auth_headers)
        assert get_s_resp.status_code == 200
        assert get_s_resp.json()["data"]["preview_url"] == "/api/v1/assets/previews/sd35_test123_abc.webp"

    # 3. Test ZeroGPU quota error translates to HTTP 429
    mock_quota_err = ZeroGPUQuotaExceededError("ZeroGPU Quota Terlampaui: 65s requested vs 82s left")
    mock_quota_provider = AsyncMock()
    mock_quota_provider.generate.side_effect = mock_quota_err

    with patch("backend.app.api.v1.previews.get_image_provider", return_value=mock_quota_provider):
        quota_resp = client.post(
            f"/api/v1/scenes/{scene_id}/generate-preview",
            json={"aspect_ratio": "16:9"},
            headers=auth_headers,
        )
        assert quota_resp.status_code == 429
        assert "ZeroGPU Quota" in quota_resp.json()["error"]["message"]
        assert "HF_TOKEN" in quota_resp.json()["error"]["message"]


def test_api_generate_shot_preview_and_asset_serving(client: TestClient, auth_headers: dict[str, str], tmp_path: Path):
    """Test shot preview generation and static asset file serving."""
    # 1. Create project, scene, shot
    proj = client.post("/api/v1/projects", json={"title": "Shot Preview Film"}, headers=auth_headers).json()["data"]["id"]
    scene = client.post(
        f"/api/v1/projects/{proj}/scenes",
        json={
            "act_number": 1,
            "scene_number": 1,
            "slugline": "INT. PENTHOUSE LAB - DAY",
            "narrative_goal": "Dr. Sarah uncovers the synthetic virus code",
        },
        headers=auth_headers,
    ).json()["data"]["id"]

    shot = client.post(
        f"/api/v1/scenes/{scene}/shots",
        json={
            "shot_number": 1,
            "camera_code": "#Cam 01",
            "lens_code": "#Lens 01",
            "comp_code": "#Comp 01",
            "light_code": "#Light 01",
            "duration_seconds": 5.0,
        },
        headers=auth_headers,
    ).json()["data"]["id"]

    # 2. Mock generate shot preview
    mock_shot_res = ImageGenerationResult(
        local_path=str(tmp_path / "shot_prev.webp"),
        local_url="/api/v1/assets/previews/sd35_shot_xyz.webp",
        remote_url="https://mock.space/shot.webp",
        seed=5555,
        width=1024,
        height=576,
        steps=28,
        file_size_bytes=2048,
        mime_type="image/webp",
        sha256_checksum=f"deadbeef{uuid.uuid4().hex[:10]}",
        provider="sd35_large_hf",
    )

    mock_p = AsyncMock()
    mock_p.generate.return_value = mock_shot_res

    with patch("backend.app.api.v1.previews.get_image_provider", return_value=mock_p):
        shot_prev_resp = client.post(
            f"/api/v1/shots/{shot}/generate-preview",
            json={"aspect_ratio": "16:9"},
            headers=auth_headers,
        )
        assert shot_prev_resp.status_code == 200
        assert shot_prev_resp.json()["data"]["preview_url"] == "/api/v1/assets/previews/sd35_shot_xyz.webp"

        # Check list shots returns preview_url
        shots_list = client.get(f"/api/v1/scenes/{scene}/shots", headers=auth_headers).json()["data"]
        assert len(shots_list) >= 1
        assert shots_list[0]["preview_url"] == "/api/v1/assets/previews/sd35_shot_xyz.webp"

    # 3. Test asset serving route
    settings = get_settings()
    settings.preview_storage_path.mkdir(parents=True, exist_ok=True)
    test_asset_file = settings.preview_storage_path / "sd35_mock_asset.webp"
    test_asset_file.write_bytes(b"RIFF\x00\x00\x00\x00WEBPVP8 \x00\x00\x00\x00")

    # Success fetch
    asset_resp = client.get("/api/v1/assets/previews/sd35_mock_asset.webp")
    assert asset_resp.status_code == 200
    assert "image/webp" in asset_resp.headers["content-type"]
    assert len(asset_resp.content) > 0

    # Directory traversal prevention
    dt_resp = client.get("/api/v1/assets/previews/../../etc/passwd")
    assert dt_resp.status_code in (400, 404)

    # 404 Not Found
    nf_resp = client.get("/api/v1/assets/previews/non_existent_keyframe.webp")
    assert nf_resp.status_code == 404


@pytest.mark.anyio
async def test_9router_provider_b64_success(tmp_path: Path):
    """Test 9Router image provider receiving b64_json payload and saving locally."""
    storage_dir = tmp_path / "previews"
    provider = NineRouterImageProvider(
        base_url="http://mock-9router:8080/v1",
        api_key="sk-test-key",
        default_model="gemini-3.1-flash-image",
        storage_path=storage_dir,
    )

    req = ImageGenerationRequest(
        prompt="Neo Tokyo cyberpunk street in 16:9 widescreen",
        seed=101,
        width=1024,
        height=576,
    )

    mock_webp_bytes = b"RIFF\x1a\x00\x00\x00WEBPVP8 \x0e\x00\x00\x00\xb0\x01\x00\x9d\x01*\x01\x00\x01\x00\x00\x01\x08\x00\x00\x00"
    b64_data = base64.b64encode(mock_webp_bytes).decode("utf-8")

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def post(self, url, headers=None, json=None):
            assert "mock-9router:8080/v1/images/generations" in url
            assert headers.get("Authorization") == "Bearer sk-test-key"
            assert json.get("model") == "gemini-3.1-flash-image"
            resp = AsyncMock()
            resp.status_code = 200
            resp.text = '{"created": 1795180000, "data": [{"b64_json": "' + b64_data + '"}]}'
            resp.json = lambda: {"created": 1795180000, "data": [{"b64_json": b64_data}]}
            return resp

    with patch("httpx.AsyncClient", MockClient):
        result = await provider.generate(req)

    assert isinstance(result, ImageGenerationResult)
    assert result.provider == "9router"
    assert result.model == "gemini-3.1-flash-image"
    assert result.local_url.startswith("/api/v1/assets/previews/9router_")
    assert Path(result.local_path).exists()
    assert Path(result.local_path).read_bytes() == mock_webp_bytes


@pytest.mark.anyio
async def test_9router_provider_combo_failover_on_429(tmp_path: Path):
    """Test 9Router combo failover when primary model hits HTTP 429 quota limit."""
    storage_dir = tmp_path / "previews"
    provider = NineRouterImageProvider(
        base_url="http://mock-9router:8080/v1",
        combo_models=["gemini-3.1-flash-image", "geminis", "ag/gemini-3.8-flash"],
        storage_path=storage_dir,
    )

    req = ImageGenerationRequest(prompt="Ancient Mayan temple")

    mock_webp_bytes = b"RIFF\x1a\x00\x00\x00WEBPVP8 \x0e\x00\x00\x00\xb0\x01\x00\x9d\x01*\x01\x00\x01\x00\x00\x01\x08\x00\x00\x00"
    b64_data = base64.b64encode(mock_webp_bytes).decode("utf-8")

    call_count = 0

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def post(self, url, headers=None, json=None):
            nonlocal call_count
            call_count += 1
            resp = AsyncMock()
            if json.get("model") == "gemini-3.1-flash-image":
                resp.status_code = 429
                resp.text = '{"error": {"message": "You exceeded your current quota for gemini-3.1-flash-image"}}'
            else:
                resp.status_code = 200
                resp.text = '{"created": 1795180000, "data": [{"b64_json": "' + b64_data + '"}]}'
                resp.json = lambda: {"created": 1795180000, "data": [{"b64_json": b64_data}]}
            return resp

    with patch("httpx.AsyncClient", MockClient):
        result = await provider.generate(req)

    assert call_count == 2
    assert result.provider == "9router"
    assert result.model == "geminis"
    assert result.rate_limit_info is not None
    assert "gemini-3.1-flash-image" in result.rate_limit_info


@pytest.mark.anyio
async def test_dynamic_provider_router_fallback_chain(tmp_path: Path):
    """Test DynamicImageProviderRouter falling back from 9Router to SD35 to Mock."""
    mock_9router = AsyncMock()
    mock_9router.generate.side_effect = RateLimitExceededError("All 9Router accounts exhausted", provider="9router")

    mock_sd35 = AsyncMock()
    mock_sd35.generate.side_effect = ZeroGPUQuotaExceededError("ZeroGPU quota exceeded")

    mock_local = MockImageProvider(storage_path=tmp_path / "previews")

    router = DynamicImageProviderRouter(
        providers={
            "9router": mock_9router,
            "sd35_large_hf": mock_sd35,
            "mock": mock_local,
        },
        default_provider="9router",
        fallback_chain=["9router", "sd35_large_hf", "mock"],
    )

    req = ImageGenerationRequest(prompt="Final scene cliffhanger", enable_fallback=True)
    result = await router.generate(req)

    assert result.provider == "mock"
    assert result.rate_limit_info is not None
    assert result.rate_limit_info.get("fallback_triggered") is True
    assert result.rate_limit_info.get("primary_provider") == "9router"
    assert result.rate_limit_info.get("fallback_provider") == "mock"


def test_api_get_preview_providers(client: TestClient, auth_headers: dict[str, str]):
    """Test discovery endpoint GET /api/v1/previews/providers."""
    resp = client.get("/api/v1/previews/providers", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["default_provider"] == "9router"
    assert "9router" in data["fallback_chain"]
    assert "sd35_large_hf" in data["fallback_chain"]
    assert "mock" in data["fallback_chain"]

    prov_ids = [p["id"] for p in data["providers"]]
    assert "9router" in prov_ids
    assert "sd35_large_hf" in prov_ids
    assert "mock" in prov_ids


def test_resolve_preview_resolution_360p():
    """Verify lightweight 360p draft preview resolution calculation across aspect ratios."""
    from backend.app.api.v1.previews import _resolve_preview_resolution, _resolve_resolution

    assert _resolve_preview_resolution("16:9") == (640, 360)
    assert _resolve_preview_resolution("9:16") == (360, 640)
    assert _resolve_preview_resolution("2.39:1") == (864, 360)
    assert _resolve_preview_resolution("1:1") == (360, 360)
    # Check backwards compatible alias
    assert _resolve_resolution("16:9") == (640, 360)


def test_live_prompt_transpiler_9router_target():
    """Test LivePromptTranspiler compiles prompts with 9Router multi-model target."""
    compiled = LivePromptTranspiler.transpile(
        provider_target="9router",
        style_code="#Style 01",
        camera_code="#Cam 01",
        lens_code="#Lens 01",
        comp_code="#Comp 01",
        light_code="#Light 01",
        act_code="#Act 01",
        speed_code="#Speed 01",
        character_dna="Cyber detective",
        action_description="inspects holographic clue",
        aspect_ratio="16:9",
    )

    assert compiled["provider_target"] == "9router"
    assert "Cinematic keyframe film still in 16:9 aspect ratio" in compiled["positive_prompt"]
    assert "Cyber detective" in compiled["positive_prompt"]
    assert "35mm motion picture film stock" in compiled["positive_prompt"]
    assert compiled["metadata"]["target_engine"] == "9router_multimodel_v1"
    assert compiled["positive"] == compiled["positive_prompt"]

    # Test with specific model: ag/gemini-3.8-flash
    compiled_model = LivePromptTranspiler.transpile(
        provider_target="9router",
        style_code="#Style 01",
        action_description="inspects holographic clue",
        aspect_ratio="16:9",
        model="ag/gemini-3.8-flash",
    )
    assert compiled_model["metadata"]["target_engine"] == "9router_ag_gemini_3_8_flash"
    assert compiled_model["metadata"]["selected_model"] == "ag/gemini-3.8-flash"


def test_sd35_hf_dimension_clamping_all_aspect_ratios():
    """Verify SD 3.5 Large clamping math for 16:9, 9:16, 2.39:1, 1:1, ensuring step-alignment (multiples of 64)."""
    from backend.app.infrastructure.sd35_client import clamp_sd35_dimensions

    # 1. 16:9 (640x360 input) -> 1024x576 (or 960x512)
    w_16_9, h_16_9 = clamp_sd35_dimensions(640, 360)
    assert w_16_9 in (1024, 960)
    assert h_16_9 in (576, 512)
    assert w_16_9 % 64 == 0
    assert h_16_9 % 64 == 0
    assert 512 <= w_16_9 <= 1024
    assert 512 <= h_16_9 <= 1024

    # 2. 9:16 (360x640 input) -> 576x1024 (vertical aspect ratio preserved)
    w_9_16, h_9_16 = clamp_sd35_dimensions(360, 640)
    assert w_9_16 == 576
    assert h_9_16 == 1024
    assert w_9_16 % 64 == 0
    assert h_9_16 % 64 == 0
    assert 512 <= w_9_16 <= 1024
    assert 512 <= h_9_16 <= 1024
    # Aspect ratio check: portrait orientation preserved
    assert h_9_16 > w_9_16

    # 3. 2.39:1 (864x360 input) -> 1024x512
    w_239, h_239 = clamp_sd35_dimensions(864, 360)
    assert w_239 == 1024
    assert h_239 == 512
    assert w_239 % 64 == 0
    assert h_239 % 64 == 0
    assert 512 <= w_239 <= 1024
    assert 512 <= h_239 <= 1024

    # 4. 1:1 (360x360 input) -> 512x512
    w_1_1, h_1_1 = clamp_sd35_dimensions(360, 360)
    assert w_1_1 == 512
    assert h_1_1 == 512
    assert w_1_1 % 64 == 0
    assert h_1_1 % 64 == 0


@pytest.mark.anyio
async def test_dynamic_router_429_failover_and_thread_safety(tmp_path: Path):
    """Verify thread-safe per-request routing and automated failover when 9Router hits 429 quota."""
    mock_9router = AsyncMock()
    mock_9router.generate.side_effect = RateLimitExceededError("Rate limit 429 quota hit", provider="9router")

    mock_hf = AsyncMock()
    mock_hf.generate.side_effect = ZeroGPUQuotaExceededError("ZeroGPU quota exhausted")

    mock_fallback = MockImageProvider(storage_path=tmp_path / "previews")

    router = DynamicImageProviderRouter(
        providers={
            "9router": mock_9router,
            "sd35_large_hf": mock_hf,
            "mock": mock_fallback,
        },
        default_provider="9router",
        fallback_chain=["9router", "sd35_large_hf", "mock"],
    )

    # Request specifies 9router with fallback enabled
    req = ImageGenerationRequest(
        prompt="Cyberpunk street in rain",
        provider="9router",
        enable_fallback=True,
    )

    orig_default = router.default_provider
    res = await router.generate(req)

    # Thread-safety check: default_provider was not mutated on router instance
    assert router.default_provider == orig_default
    assert res.provider == "mock"
    assert res.rate_limit_info is not None
    assert res.rate_limit_info.get("fallback_triggered") is True
    assert res.rate_limit_info.get("primary_provider") == "9router"
    assert res.rate_limit_info.get("fallback_provider") == "mock"

    # With fallback disabled, RateLimitExceededError must be raised
    req_no_fallback = ImageGenerationRequest(
        prompt="Cyberpunk street in rain",
        provider="9router",
        enable_fallback=False,
    )
    with pytest.raises(RateLimitExceededError):
        await router.generate(req_no_fallback)


def test_project_preview_route_alias_and_sqlite_persistence(
    client: TestClient,
    auth_headers: dict[str, str],
    tmp_path: Path,
):
    """Verify /projects/{id}/generate-preview and /previews/projects/{id}/generate-preview route alias + flag_modified persistence."""
    # 1. Create test project
    proj_resp = client.post("/api/v1/projects", json={"title": "Route Alias Concept Test"}, headers=auth_headers)
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["data"]["id"]

    mock_res = ImageGenerationResult(
        local_path=str(tmp_path / "concept.webp"),
        local_url="/api/v1/assets/previews/concept_test_123.webp",
        remote_url=None,
        seed=123456,
        width=640,
        height=360,
        steps=20,
        file_size_bytes=1024,
        mime_type="image/webp",
        sha256_checksum=f"hash_{uuid.uuid4().hex[:12]}",
        provider="mock",
    )
    mock_p = AsyncMock()
    mock_p.generate.return_value = mock_res

    with patch("backend.app.api.v1.previews.get_image_provider", return_value=mock_p):
        # 2. Test primary route
        res1 = client.post(
            f"/api/v1/projects/{proj_id}/generate-preview",
            json={"aspect_ratio": "16:9"},
            headers=auth_headers,
        )
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["preview_url"] == "/api/v1/assets/previews/concept_test_123.webp"
        assert data1["data"]["preview_url"] == "/api/v1/assets/previews/concept_test_123.webp"
        assert data1["provider"] == "mock"

        # Verify SQLite persistence via GET project
        get_proj = client.get(f"/api/v1/projects/{proj_id}", headers=auth_headers)
        assert get_proj.status_code == 200
        settings = get_proj.json()["data"].get("settings") or {}
        assert settings.get("preview_url") == "/api/v1/assets/previews/concept_test_123.webp"
        assert settings.get("preview_seed") == 123456
        assert settings.get("preview_provider") == "mock"

        # 3. Test route alias
        res2 = client.post(
            f"/api/v1/previews/projects/{proj_id}/generate-preview",
            json={"aspect_ratio": "9:16"},
            headers=auth_headers,
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["preview_url"] == "/api/v1/assets/previews/concept_test_123.webp"
        assert data2["data"]["project_id"] == proj_id
