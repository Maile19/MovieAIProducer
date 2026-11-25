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

