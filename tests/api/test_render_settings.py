import asyncio
import base64
import json
import sqlite3
from unittest.mock import patch, AsyncMock
import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

REAL_ASYNC_CLIENT = httpx.AsyncClient

from backend.app.main import create_app
from backend.app.api.v1.render_settings import (
    encrypt_key,
    decrypt_key,
    mask_key,
    get_db,
    _get_db_path,
    get_project_render_config,
)
from backend.app.infrastructure.universal_image_adapter import (
    UniversalImageAdapter,
    UniversalImageRequest,
    _resolve_dimensions,
    _resolve_kling_token,
    _resolve_adobe_credentials,
)


def test_encryption_and_masking():
    plain = "AIzaSySecretGeminiAPIKey987654321"
    encrypted = encrypt_key(plain)
    assert encrypted.startswith("enc:")
    assert encrypted != plain

    decrypted = decrypt_key(encrypted)
    assert decrypted == plain

    masked = mask_key(plain)
    assert "••••" in masked
    assert masked.startswith("AIza")
    assert masked.endswith("4321")

    # Already encrypted key shouldn't be re-encrypted
    assert encrypt_key(encrypted) == encrypted
    # Plain key fallback in decrypt_key
    assert decrypt_key("plain_legacy_key") == "plain_legacy_key"


def test_dimension_resolution():
    w, h = _resolve_dimensions("16:9", None, None)
    assert (w, h) == (1024, 576)

    w, h = _resolve_dimensions("1:1", None, None)
    assert (w, h) == (1024, 1024)

    w, h = _resolve_dimensions("9:16", None, None)
    assert (w, h) == (576, 1024)

    w, h = _resolve_dimensions("custom", 1280, 720)
    assert (w, h) == (1280, 720)


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as tc:
        yield tc


def test_render_settings_lifecycle_and_masking(client):
    proj_id = "test-project-obsidian-001"

    payload = {
        "activeProviderId": "gemini-direct",
        "applyToAllScenes": True,
        "configs": {
            "gemini-direct": {
                "baseUrl": "https://generativelanguage.googleapis.com/v1beta",
                "apiKey": "AIzaSySuperSecretDirectKey1234",
                "modelId": "gemini-3.8-flash",
            },
            "qwen-image-3": {
                "baseUrl": "https://dashscope-intl.aliyuncs.com/api/v1",
                "apiKey": "sk-dashscope-secret-token-9999",
                "modelId": "qwen-image-3.0",
            },
        },
        "freePortals": [
            {
                "id": "free-whisk",
                "name": "Google Whisk",
                "url": "https://labs.google/fx/tools/whisk",
                "note": "Daily free tier",
            }
        ],
    }

    # 1. Save settings
    put_res = client.put(f"/api/v1/projects/{proj_id}/render-provider", json=payload)
    assert put_res.status_code == 200
    put_data = put_res.json()
    assert put_data["status"] == "saved"
    assert put_data["activeProviderId"] == "gemini-direct"

    # 2. Check SQLite storage directly: verify encryption at rest
    conn = get_db()
    row = conn.execute(
        "SELECT provider_configs_json FROM project_render_settings WHERE project_id = ?",
        (proj_id,),
    ).fetchone()
    conn.close()
    assert row is not None
    stored_configs = json.loads(row["provider_configs_json"])
    assert stored_configs["gemini-direct"]["apiKey"].startswith("enc:")
    assert "AIzaSySuperSecretDirectKey1234" not in stored_configs["gemini-direct"]["apiKey"]

    # 3. Fetch settings via GET: verify masking
    get_res = client.get(f"/api/v1/projects/{proj_id}/render-provider")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["configured"] is True
    assert get_data["activeProviderId"] == "gemini-direct"
    assert get_data["applyToAllScenes"] is True
    assert len(get_data["freePortals"]) == 1

    # Verify masked key in HTTP response
    gemini_cfg = get_data["configs"]["gemini-direct"]
    assert "••••" in gemini_cfg["apiKey"]
    assert "AIza" in gemini_cfg["apiKey"]
    assert "1234" in gemini_cfg["apiKey"]
    assert gemini_cfg["apiKey"] != "AIzaSySuperSecretDirectKey1234"

    # 4. Save again with masked key: ensure raw encrypted key in DB is preserved
    update_payload = {
        "activeProviderId": "qwen-image-3",
        "applyToAllScenes": False,
        "configs": {
            "gemini-direct": {
                "baseUrl": "https://generativelanguage.googleapis.com/v1beta",
                "apiKey": gemini_cfg["apiKey"],  # Masked!
                "modelId": "gemini-3.8-flash",
            },
            "qwen-image-3": {
                "baseUrl": "https://dashscope-intl.aliyuncs.com/api/v1",
                "apiKey": "sk-dash••••9999",  # Masked!
                "modelId": "qwen-mt-image-2.0",
            },
        },
        "freePortals": get_data["freePortals"],
    }

    put2_res = client.put(f"/api/v1/projects/{proj_id}/render-provider", json=update_payload)
    assert put2_res.status_code == 200

    # Verify DB still decrypts to the original secret key
    conn2 = get_db()
    row2 = conn2.execute(
        "SELECT provider_configs_json FROM project_render_settings WHERE project_id = ?",
        (proj_id,),
    ).fetchone()
    conn2.close()
    stored2 = json.loads(row2["provider_configs_json"])
    decrypted_gemini = decrypt_key(stored2["gemini-direct"]["apiKey"])
    assert decrypted_gemini == "AIzaSySuperSecretDirectKey1234"


def test_test_key_endpoint_with_stored_credentials(client):
    proj_id = "test-project-obsidian-002"

    payload = {
        "activeProviderId": "9router",
        "applyToAllScenes": True,
        "configs": {
            "9router": {
                "baseUrl": "http://127.0.0.1:8080/v1",
                "apiKey": "sk-local-test-token",
                "modelId": "ag/gemini-3.8-flash",
            }
        },
        "freePortals": [],
    }
    client.put(f"/api/v1/projects/{proj_id}/render-provider", json=payload)

    # Call test-key with masked key -> should use decrypted stored key
    test_res = client.post(
        f"/api/v1/projects/{proj_id}/render-provider/test-key",
        json={
            "providerId": "9router",
            "baseUrl": "http://127.0.0.1:8080/v1",
            "apiKey": "sk-l••••oken",
            "modelId": "ag/gemini-3.8-flash",
        },
    )
    assert test_res.status_code == 200
    data = test_res.json()
    assert "ok" in data


TINY_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
TINY_PNG_BYTES = base64.b64decode(TINY_PNG_B64)


def test_invalid_token_handling_graceful(client):
    # 1. Direct decrypt_key handles invalid/corrupted token without crashing
    bad_token = "enc:gAAAAABinvalid_corrupted_fernet_token"
    assert decrypt_key(bad_token) == ""

    # 2. GET endpoint returns 200 (not 500) and provides empty key for re-entry
    proj_id = "test-corrupted-token-proj"
    conn = get_db()
    conn.execute(
        """
        INSERT OR REPLACE INTO project_render_settings 
        (project_id, active_provider_id, apply_to_all_scenes, provider_configs_json, free_portals_json, updated_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            proj_id,
            "gemini-direct",
            1,
            json.dumps({
                "gemini-direct": {
                    "baseUrl": "https://generativelanguage.googleapis.com/v1beta",
                    "apiKey": bad_token,
                    "modelId": "gemini-3.8-flash",
                }
            }),
            "[]",
        ),
    )
    conn.commit()
    conn.close()

    res = client.get(f"/api/v1/projects/{proj_id}/render-provider")
    assert res.status_code == 200
    data = res.json()
    assert data["configured"] is True
    assert data["configs"]["gemini-direct"]["apiKey"] == ""


def test_get_project_render_config(client):
    # Unconfigured project returns None
    unconf = get_project_render_config("non-existent-proj-999")
    assert unconf is None

    # Configured project returns active config with decrypted key
    proj_id = "test-render-config-lookup"
    payload = {
        "activeProviderId": "kling-image-4-0",
        "applyToAllScenes": True,
        "configs": {
            "kling-image-4-0": {
                "baseUrl": "https://api.klingai.com/v1",
                "apiKey": "ak_123:sk_456",
                "modelId": "kling-image-v4",
            }
        },
        "freePortals": [],
    }
    client.put(f"/api/v1/projects/{proj_id}/render-provider", json=payload)

    conf = get_project_render_config(proj_id)
    assert conf is not None
    assert conf["active_provider_id"] == "kling-image-4-0"
    assert conf["apply_to_all_scenes"] is True
    assert conf["api_key"] == "ak_123:sk_456"
    assert conf["model_id"] == "kling-image-v4"


def test_kling_jwt_resolution():
    ak = "my_access_key_kling"
    sk = "my_secret_key_kling_very_secret_123456"
    combined = f"{ak}:{sk}"

    token = _resolve_kling_token(combined)
    assert token != combined
    decoded = jwt.decode(token, sk, algorithms=["HS256"])
    assert decoded["iss"] == ak
    assert "exp" in decoded
    assert "nbf" in decoded

    # Bearer token remains unchanged
    existing_jwt = "header.payload.signature"
    assert _resolve_kling_token(existing_jwt) == existing_jwt


def test_adobe_firefly_credential_resolution():
    cid, tok = _resolve_adobe_credentials("client_abc:token_xyz")
    assert cid == "client_abc"
    assert tok == "token_xyz"

    cid_only, tok_only = _resolve_adobe_credentials("just_token_here")
    assert cid_only == ""
    assert tok_only == "just_token_here"


def test_gemini_direct_modalities_and_text_fallback(tmp_path):
    storage = tmp_path / "previews"
    adapter = UniversalImageAdapter(storage_path=storage)

    # 1. Successful generation: responseModalities checked & inlineData parsed
    captured_payloads = []

    def mock_gemini_success_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        captured_payloads.append(body)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "image/png",
                                        "data": TINY_PNG_B64,
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
        )

    req = UniversalImageRequest(
        provider_id="gemini-direct",
        model_id="gemini-3.8-flash",
        prompt="A cute cat in cinematic lighting",
        api_key_override="AIzaTestGeminiKey",
    )

    transport = httpx.MockTransport(mock_gemini_success_handler)
    with patch(
        "backend.app.infrastructure.universal_image_adapter.httpx.AsyncClient",
        side_effect=lambda **kwargs: REAL_ASYNC_CLIENT(transport=transport),
    ):
        res = asyncio.run(adapter._generate_gemini_direct(req, 1024, 576))
        assert res.mime_type == "image/png"
        assert len(captured_payloads) == 1
        payload = captured_payloads[0]
        assert "generationConfig" in payload
        assert payload["generationConfig"]["responseModalities"] == ["TEXT", "IMAGE"]

    # 2. Text-only response raises RuntimeError clearly for fallback
    def mock_gemini_text_only_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "I am unable to generate an image for this request."}
                            ]
                        }
                    }
                ]
            },
        )

    transport_text = httpx.MockTransport(mock_gemini_text_only_handler)
    with patch(
        "backend.app.infrastructure.universal_image_adapter.httpx.AsyncClient",
        side_effect=lambda **kwargs: REAL_ASYNC_CLIENT(transport=transport_text),
    ):
        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(adapter._generate_gemini_direct(req, 1024, 576))
        assert "returned text only without image data" in str(exc_info.value)


def test_protocol_handlers(tmp_path):
    storage = tmp_path / "previews"
    adapter = UniversalImageAdapter(storage_path=storage)

    # 1. Ideogram 4.0
    def ideogram_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/generate"):
            assert request.headers.get("Api-Key") == "ideo-secret-key"
            body = json.loads(request.content.decode("utf-8"))
            assert "image_request" in body
            assert body["image_request"]["aspect_ratio"] == "ASPECT_16_9"
            return httpx.Response(200, json={"data": [{"url": "https://mock.ideogram/out.png"}]})
        elif request.url.host == "mock.ideogram":
            return httpx.Response(200, content=TINY_PNG_BYTES)
        return httpx.Response(404)

    with patch(
        "backend.app.infrastructure.universal_image_adapter.httpx.AsyncClient",
        side_effect=lambda **kwargs: REAL_ASYNC_CLIENT(transport=httpx.MockTransport(ideogram_handler)),
    ):
        res = asyncio.run(
            adapter._generate_ideogram(
                UniversalImageRequest(
                    provider_id="ideogram-4-0",
                    prompt="Cyberpunk Tokyo neon",
                    api_key_override="ideo-secret-key",
                ),
                1024,
                576,
            )
        )
        assert res.provider_id == "ideogram-4-0"
        assert res.mime_type == "image/png"

    # 2. Leonardo Phoenix (Async submit + polling)
    def leonardo_handler(request: httpx.Request) -> httpx.Response:
        if "leonardo.ai" in request.url.host:
            assert request.headers.get("Authorization") == "Bearer leo-secret-key"
        if request.method == "POST" and request.url.path.endswith("/generations"):
            return httpx.Response(200, json={"sdGenerationJob": {"generationId": "gen-leo-001"}})
        elif request.method == "GET" and "/generations/gen-leo-001" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "generations_by_pk": {
                        "status": "COMPLETE",
                        "generated_images": [{"url": "https://mock.leonardo/leo.png"}],
                    }
                },
            )
        elif request.url.host == "mock.leonardo":
            return httpx.Response(200, content=TINY_PNG_BYTES)
        return httpx.Response(404)

    with patch(
        "backend.app.infrastructure.universal_image_adapter.httpx.AsyncClient",
        side_effect=lambda **kwargs: REAL_ASYNC_CLIENT(transport=httpx.MockTransport(leonardo_handler)),
    ), patch("backend.app.infrastructure.universal_image_adapter.asyncio.sleep", new_callable=AsyncMock):
        res = asyncio.run(
            adapter._generate_leonardo(
                UniversalImageRequest(
                    provider_id="leonardo-phoenix",
                    prompt="Fantasy mountain castle",
                    api_key_override="leo-secret-key",
                ),
                1024,
                576,
            )
        )
        assert res.provider_id == "leonardo-phoenix"
        assert res.remote_url == "https://mock.leonardo/leo.png"

    # 3. Luma Uni-1 (Async submit + polling)
    def luma_handler(request: httpx.Request) -> httpx.Response:
        if "lumalabs.ai" in request.url.host:
            assert request.headers.get("Authorization") == "Bearer luma-secret-key"
        if request.method == "POST" and request.url.path.endswith("/generations/image"):
            return httpx.Response(200, json={"id": "luma-job-001", "state": "queued"})
        elif request.method == "GET" and "/generations/luma-job-001" in request.url.path:
            return httpx.Response(
                200,
                json={"state": "completed", "assets": {"image": "https://mock.luma/luma.png"}},
            )
        elif request.url.host == "mock.luma":
            return httpx.Response(200, content=TINY_PNG_BYTES)
        return httpx.Response(404)

    with patch(
        "backend.app.infrastructure.universal_image_adapter.httpx.AsyncClient",
        side_effect=lambda **kwargs: REAL_ASYNC_CLIENT(transport=httpx.MockTransport(luma_handler)),
    ), patch("backend.app.infrastructure.universal_image_adapter.asyncio.sleep", new_callable=AsyncMock):
        res = asyncio.run(
            adapter._generate_luma(
                UniversalImageRequest(
                    provider_id="luma-uni-1",
                    prompt="Floating crystals in nebula",
                    api_key_override="luma-secret-key",
                ),
                1024,
                576,
            )
        )
        assert res.provider_id == "luma-uni-1"
        assert res.remote_url == "https://mock.luma/luma.png"

    # 4. Kling Image 4.0 (AK:SK -> HS256 JWT, async submit + polling)
    def kling_handler(request: httpx.Request) -> httpx.Response:
        if "klingai.com" in request.url.host:
            auth = request.headers.get("Authorization", "")
            assert auth.startswith("Bearer ey")  # HS256 JWT was generated
        if request.method == "POST" and request.url.path.endswith("/images/generations"):
            return httpx.Response(200, json={"data": {"task_id": "kling-task-001"}})
        elif request.method == "GET" and "/images/generations/kling-task-001" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "task_status": "succeed",
                        "task_result": {"images": [{"url": "https://mock.kling/kling.png"}]},
                    }
                },
            )
        elif request.url.host == "mock.kling":
            return httpx.Response(200, content=TINY_PNG_BYTES)
        return httpx.Response(404)

    with patch(
        "backend.app.infrastructure.universal_image_adapter.httpx.AsyncClient",
        side_effect=lambda **kwargs: REAL_ASYNC_CLIENT(transport=httpx.MockTransport(kling_handler)),
    ), patch("backend.app.infrastructure.universal_image_adapter.asyncio.sleep", new_callable=AsyncMock):
        res = asyncio.run(
            adapter._generate_kling(
                UniversalImageRequest(
                    provider_id="kling-image-4-0",
                    prompt="Mythical Asian dragon",
                    api_key_override="ak_kling_test:sk_kling_test_secret_32_bytes_long_ok",
                ),
                1024,
                576,
            )
        )
        assert res.provider_id == "kling-image-4-0"
        assert res.remote_url == "https://mock.kling/kling.png"

    # 5. Adobe Firefly 4 (client_id:access_token headers)
    def firefly_handler(request: httpx.Request) -> httpx.Response:
        if "adobe.io" in request.url.host:
            assert request.headers.get("x-api-key") == "adobe_cid_123"
            assert request.headers.get("Authorization") == "Bearer adobe_tok_456"
        if request.method == "POST" and request.url.path.endswith("/images/generate"):
            return httpx.Response(
                200,
                json={"outputs": [{"image": {"url": "https://mock.adobe/firefly.png"}}]},
            )
        elif request.url.host == "mock.adobe":
            return httpx.Response(200, content=TINY_PNG_BYTES)
        return httpx.Response(404)

    with patch(
        "backend.app.infrastructure.universal_image_adapter.httpx.AsyncClient",
        side_effect=lambda **kwargs: REAL_ASYNC_CLIENT(transport=httpx.MockTransport(firefly_handler)),
    ):
        res = asyncio.run(
            adapter._generate_adobe_firefly(
                UniversalImageRequest(
                    provider_id="adobe-firefly-4",
                    prompt="Futuristic starship interior",
                    api_key_override="adobe_cid_123:adobe_tok_456",
                ),
                1024,
                576,
            )
        )
        assert res.provider_id == "adobe-firefly-4"
        assert res.remote_url == "https://mock.adobe/firefly.png"


def test_resolve_effective_render_provider_precedence_and_aliases(client):
    from backend.app.api.v1.render_settings import resolve_effective_render_provider

    proj_id = "test-precedence-proj-001"
    configs = {
        "google-flow": {
            "baseUrl": "https://labs.google/fx/api",
            "apiKey": "",
            "modelId": "flow-imagen-anchor-pro",
        },
        "gpt-2-6": {
            "baseUrl": "https://api.openai.com/v1",
            "apiKey": "sk-proj-openai-secret",
            "modelId": "gpt-image-2.6",
        },
        "9router": {
            "baseUrl": "http://127.0.0.1:8080/v1",
            "apiKey": "sk-9router-local",
            "modelId": "ag/gemini-3.8-flash",
        },
    }

    # 1. Global apply_to_all_scenes=True must defeat stale '9router' + 'ag/gemini-3.8-flash'
    client.put(
        f"/api/v1/projects/{proj_id}/render-provider",
        json={
            "activeProviderId": "gpt-2-6",
            "applyToAllScenes": True,
            "configs": configs,
            "freePortals": [],
        },
    )
    resolved_global = resolve_effective_render_provider(
        project_id=proj_id,
        requested_provider="9router",
        requested_model="ag/gemini-3.8-flash",
        ignored_override_values=("ag_gemini_flash", "default", None),
    )
    assert resolved_global["provider_id"] == "gpt-2-6"
    assert resolved_global["model_id"] == "gpt-image-2.6"
    assert resolved_global["api_key"] == "sk-proj-openai-secret"
    assert resolved_global["use_universal_adapter"] is True

    # 2. Global google-flow must also match google_flow alias without leaking 9router model
    client.put(
        f"/api/v1/projects/{proj_id}/render-provider",
        json={
            "activeProviderId": "google-flow",
            "applyToAllScenes": True,
            "configs": configs,
            "freePortals": [],
        },
    )
    resolved_flow = resolve_effective_render_provider(
        project_id=proj_id,
        requested_provider="9router",
        requested_model="ag/gemini-3.8-flash",
        ignored_override_values=("sd35_large_hf", "default", None),
    )
    assert resolved_flow["provider_id"] == "google-flow"
    assert resolved_flow["model_id"] == "flow-imagen-anchor-pro"

    # Same-provider alias ('google_flow') preserves explicit model override if supplied
    resolved_flow_same = resolve_effective_render_provider(
        project_id=proj_id,
        requested_provider="google_flow",
        requested_model="flow-custom-model",
    )
    assert resolved_flow_same["provider_id"] == "google-flow"
    assert resolved_flow_same["model_id"] == "flow-custom-model"

    # 3. When apply_to_all_scenes=False, explicit per-request provider override is honored
    client.put(
        f"/api/v1/projects/{proj_id}/render-provider",
        json={
            "activeProviderId": "google-flow",
            "applyToAllScenes": False,
            "configs": configs,
            "freePortals": [],
        },
    )
    resolved_override = resolve_effective_render_provider(
        project_id=proj_id,
        requested_provider="gpt-2-6",
        requested_model=None,
    )
    assert resolved_override["provider_id"] == "gpt-2-6"
    assert resolved_override["model_id"] == "gpt-image-2.6"
    assert resolved_override["use_universal_adapter"] is True


def test_gpt_2_6_openai_protocol_1k_and_reference_edits(tmp_path):
    """Verify gpt-2-6 strips response_format/negative_prompt/seed, maps sizes, retries model alias, and uses /images/edits for refs."""
    storage = tmp_path / "previews"
    adapter = UniversalImageAdapter(storage_path=storage)

    ref1 = tmp_path / "card1.png"
    ref2 = tmp_path / "card3.png"
    ref1.write_bytes(TINY_PNG_BYTES)
    ref2.write_bytes(TINY_PNG_BYTES)

    seen_calls = []

    def openai_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/images/generations"):
            body = json.loads(request.content.decode("utf-8"))
            seen_calls.append(("generations", body))
            assert "response_format" not in body
            assert "negative_prompt" not in body
            assert "seed" not in body
            assert "Strictly avoid:" in body["prompt"]
            if body["model"] == "gpt-image-2.6":
                return httpx.Response(
                    404,
                    json={"error": {"message": "The model 'gpt-image-2.6' does not exist", "code": "model_not_found"}},
                )
            return httpx.Response(200, json={"data": [{"b64_json": TINY_PNG_B64}]})

        if request.url.path.endswith("/images/edits"):
            raw_body = request.content.decode("latin-1")
            seen_calls.append(("edits", raw_body))
            assert "gpt-image-2.6-flare" in raw_body or "gpt-image-1" in raw_body
            assert 'name="image[]"' in raw_body
            assert 'name="size"\r\n\r\n1024x1536' in raw_body
            return httpx.Response(200, json={"data": [{"b64_json": TINY_PNG_B64}]})

        return httpx.Response(404)

    with patch(
        "backend.app.infrastructure.universal_image_adapter.httpx.AsyncClient",
        side_effect=lambda **kwargs: REAL_ASYNC_CLIENT(transport=httpx.MockTransport(openai_handler)),
    ):
        # 1. Card 1 (no ref, 1:1) -> retries gpt-image-2.6 -> gpt-image-2.6-flare
        res1 = asyncio.run(
            adapter.generate_image(
                UniversalImageRequest(
                    provider_id="gpt-2-6",
                    model_id="gpt-image-2.6",
                    prompt="Studio casting closeup",
                    negative_prompt="blurry, CGI",
                    aspect_ratio="1:1",
                    width=1024,
                    height=1024,
                    seed=4242,
                    base_url_override="https://api.openai.com/v1",
                    api_key_override="sk-proj-test",
                    enable_fallback=False,
                )
            )
        )
        assert res1.model_id == "gpt-image-2.6-flare"
        assert seen_calls[0][0] == "generations"
        assert seen_calls[0][1]["size"] == "1024x1024"
        assert seen_calls[1][1]["model"] == "gpt-image-2.6-flare"

        # 2. Card 4 (2 refs, 3:4) -> /images/edits with image[] and 1024x1536
        res2 = asyncio.run(
            adapter.generate_image(
                UniversalImageRequest(
                    provider_id="gpt-2-6",
                    model_id="gpt-image-2.6-flare",
                    prompt="Side profile",
                    negative_prompt="blurry",
                    aspect_ratio="3:4",
                    width=768,
                    height=1024,
                    reference_image_paths=[str(ref1), str(ref2)],
                    base_url_override="https://api.openai.com/v1",
                    api_key_override="sk-proj-test",
                    enable_fallback=False,
                )
            )
        )
        assert res2.model_id == "gpt-image-2.6-flare"
        assert seen_calls[-1][0] == "edits"


def test_seedream_5_5_payload_and_misconfigured_endpoint_guard(tmp_path):
    """Verify seedream-5-5 rejects Alibaba MaaS URL clearly and omits sequential_image_generation on 5.5."""
    storage = tmp_path / "previews"
    adapter = UniversalImageAdapter(storage_path=storage)

    ref1 = tmp_path / "card1.png"
    ref1.write_bytes(TINY_PNG_BYTES)

    # 1. Misconfigured Alibaba Cloud URL fails immediately with clear diagnostic
    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(
            adapter.generate_image(
                UniversalImageRequest(
                    provider_id="seedream-5-5",
                    model_id="seedream-5.5",
                    prompt="Upscale portrait",
                    aspect_ratio="1:1",
                    width=2048,
                    height=2048,
                    reference_image_paths=[str(ref1)],
                    base_url_override="https://ws-os66oybk9aerfdmb.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
                    api_key_override="sk-ws-test",
                    enable_fallback=False,
                )
            )
        )
    assert "aliyuncs.com" in str(exc_info.value)
    assert "BytePlus ModelArk" in str(exc_info.value)

    # 2. Real BytePlus ModelArk omits sequential_image_generation on seedream-5.5 and retries size preset on 400 pixel error
    seen_payloads = []

    def byteplus_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        seen_payloads.append(body)
        assert "sequential_image_generation" not in body
        assert body["image"].startswith("data:image/png;base64,")
        if body["size"] == "2048x2048":
            return httpx.Response(400, json={"error": {"message": "InvalidParameter: pixel limit"}})
        assert body["size"] == "2K"
        return httpx.Response(200, json={"data": [{"b64_json": TINY_PNG_B64}]})

    with patch(
        "backend.app.infrastructure.universal_image_adapter.httpx.AsyncClient",
        side_effect=lambda **kwargs: REAL_ASYNC_CLIENT(transport=httpx.MockTransport(byteplus_handler)),
    ):
        res = asyncio.run(
            adapter.generate_image(
                UniversalImageRequest(
                    provider_id="seedream-5-5",
                    model_id="seedream-5.5",
                    prompt="Upscale portrait",
                    aspect_ratio="1:1",
                    width=2048,
                    height=2048,
                    reference_image_paths=[str(ref1)],
                    base_url_override="https://ark.ap-southeast.bytepluses.com/api/v3",
                    api_key_override="sk-byteplus-test",
                    enable_fallback=False,
                )
            )
        )
        assert res.provider_id == "seedream-5-5"
        assert len(seen_payloads) == 2


def test_ping_connection_google_flow_and_seedream_validation(tmp_path):
    """Verify google-flow ping handles synchronous check_socks5_health dict and seedream rejects aliyuncs."""
    adapter = UniversalImageAdapter(storage_path=tmp_path)

    with patch("backend.app.core.proxy_health.check_socks5_health", return_value={"healthy": False, "detail": "Proxy offline"}):
        res_off = asyncio.run(adapter.ping_connection("google-flow", "https://labs.google/fx/api", ""))
        assert res_off["ok"] is False
        assert "Proxy offline" in res_off["message"]

    with patch("backend.app.core.proxy_health.check_socks5_health", return_value={"healthy": True, "detail": "SOCKS5 handshake ok"}):
        res_on = asyncio.run(adapter.ping_connection("google_flow", "https://labs.google/fx/api", ""))
        assert res_on["ok"] is True
        assert "SOCKS5" in res_on["message"]

    res_seed = asyncio.run(
        adapter.ping_connection(
            "seedream-5-5",
            "https://ws-os66oybk9aerfdmb.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1",
            "sk-test",
            model_id="seedream-5.5",
        )
    )
    assert res_seed["ok"] is False
    assert "aliyuncs.com" in res_seed["message"]


def test_9router_uses_effective_key_and_preserves_primary_errors(tmp_path):
    """Verify 9router uses effective_ninerouter_api_key when DB key is empty, and primary errors aren't masked."""
    adapter = UniversalImageAdapter(storage_path=tmp_path)
    seen_auth_headers = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_auth_headers.append(request.headers.get("Authorization"))
        if "dashscope" in str(request.url):
            return httpx.Response(403, json={"code": "AccessDenied.Unpurchased", "message": "Access denied"})
        if "127.0.0.1:8080" in str(request.url):
            if request.headers.get("Authorization"):
                return httpx.Response(200, json={"data": [{"b64_json": TINY_PNG_B64}]})
            return httpx.Response(401, json={"error": {"message": "Missing API key"}})
        return httpx.Response(500)

    with patch(
        "backend.app.infrastructure.universal_image_adapter.httpx.AsyncClient",
        side_effect=lambda **kwargs: REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handler)),
    ):
        # 1. Empty api_key_override on 9router must still attach effective_ninerouter_api_key
        res_nr = asyncio.run(
            adapter.generate_image(
                UniversalImageRequest(
                    provider_id="9router",
                    model_id="gemini-3.1-flash-image",
                    prompt="Portrait",
                    api_key_override="",
                    enable_fallback=False,
                )
            )
        )
        assert res_nr.provider_id == "9router"
        assert seen_auth_headers[-1] and seen_auth_headers[-1].startswith("Bearer ")

        # 2. Non-retryable 403 on qwen-image-3 must surface DashScope 403 directly without masking via 9Router
        with pytest.raises(RuntimeError) as exc_403:
            asyncio.run(
                adapter.generate_image(
                    UniversalImageRequest(
                        provider_id="qwen-image-3",
                        model_id="qwen-image-3.0",
                        prompt="Portrait",
                        aspect_ratio="16:9",
                        api_key_override="sk-dash-test",
                        enable_fallback=True,
                    )
                )
            )
        assert "403" in str(exc_403.value)
        assert "AccessDenied.Unpurchased" in str(exc_403.value)

    # 3. Transient failure where 9Router fallback also fails must preserve both primary and fallback errors
    async def fail_primary(req, w, h):
        raise RuntimeError("Upstream 503 temporary outage")

    async def fail_fallback(req, w, h, reason):
        raise TimeoutError("9router read timeout")

    with patch.object(adapter, "_generate_ideogram", side_effect=fail_primary), patch.object(
        adapter, "_execute_9router_fallback", side_effect=fail_fallback
    ):
        with pytest.raises(RuntimeError) as exc_both:
            asyncio.run(
                adapter.generate_image(
                    UniversalImageRequest(
                        provider_id="ideogram-4-0",
                        prompt="Portrait",
                        api_key_override="ideo-key",
                        enable_fallback=True,
                    )
                )
            )
        assert "Upstream 503 temporary outage" in str(exc_both.value)
        assert "Auto-fallback 9Router also failed" in str(exc_both.value)


def test_oversized_2k_anchor_compressed_without_modifying_disk_file(tmp_path):
    """Oversized >1.5MB 2K PNG anchors are safely downscaled/compressed in memory without modifying disk originals."""
    import random
    from PIL import Image
    from backend.app.infrastructure.universal_image_adapter import _prepare_reference_bytes

    rng = random.Random(42)
    img = Image.new("RGB", (2048, 2048))
    # High-entropy noise guarantees raw PNG > 1.5MB
    raw_rgb = rng.randbytes(2048 * 2048 * 3)
    img = Image.frombytes("RGB", (2048, 2048), raw_rgb)
    big_png = tmp_path / "card1_2k.png"
    img.save(big_png, format="PNG")
    orig_bytes = big_png.read_bytes()
    assert len(orig_bytes) > 1_500_000

    prepared = _prepare_reference_bytes(str(big_png), max_bytes=1_500_000, max_dim=1280)
    assert prepared is not None
    comp_bytes, mime, fname = prepared
    assert mime == "image/jpeg"
    assert fname.endswith(".jpg")
    assert len(comp_bytes) <= 1_500_000
    # Original 2K file on disk must remain 100% untouched
    assert big_png.read_bytes() == orig_bytes


def test_dashscope_aspect_ratio_mapping_and_modal_override(client):
    """Verify qwen-image-3 maps 16:9/3:4/1:1 to DashScope-safe sizes and respect_request_provider honors modal override."""
    from backend.app.api.v1.render_settings import resolve_effective_render_provider

    assert UniversalImageAdapter._resolve_dashscope_size(1344, 768, "16:9", "qwen-image-3.0") == "1664*928"
    assert UniversalImageAdapter._resolve_dashscope_size(768, 1024, "3:4", "qwen-image-3.0") == "1140*1472"
    assert UniversalImageAdapter._resolve_dashscope_size(1024, 1024, "1:1", "qwen-image-3.0") == "1328*1328"

    proj_id = "test-modal-override-proj"
    client.put(
        f"/api/v1/projects/{proj_id}/render-provider",
        json={
            "activeProviderId": "seedream-5-5",
            "applyToAllScenes": True,
            "configs": {
                "seedream-5-5": {"baseUrl": "https://ark.ap-southeast.bytepluses.com/api/v3", "apiKey": "sk-s", "modelId": "seedream-5.5"},
                "gemini-direct": {"baseUrl": "https://generativelanguage.googleapis.com/v1beta", "apiKey": "AIza-modal", "modelId": "gemini-3.8-flash"},
            },
            "freePortals": [],
        },
    )
    resolved = resolve_effective_render_provider(
        project_id=proj_id,
        requested_provider="gemini-direct",
        requested_model=None,
        ignored_override_values=("ag_gemini_flash", "default", None),
        respect_request_provider=True,
    )
    assert resolved["provider_id"] == "gemini-direct"
    assert resolved["api_key"] == "AIza-modal"



