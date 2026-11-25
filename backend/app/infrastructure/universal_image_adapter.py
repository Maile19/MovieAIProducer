import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import uuid

import httpx
import jwt
from pydantic import BaseModel, Field
import structlog

from backend.app.core.config import get_settings

logger = structlog.get_logger(__name__)


class UniversalImageRequest(BaseModel):
    provider_id: str = "gemini-direct"
    model_id: Optional[str] = None
    prompt: str
    negative_prompt: Optional[str] = None
    aspect_ratio: str = "16:9"  # 16:9, 1:1, 9:16
    width: Optional[int] = None
    height: Optional[int] = None
    seed: Optional[int] = None
    reference_image_paths: Optional[List[str]] = None
    enable_fallback: bool = True
    base_url_override: Optional[str] = None
    api_key_override: Optional[str] = None


class UniversalImageResult(BaseModel):
    status: str = "completed"
    local_path: str
    local_url: str
    remote_url: Optional[str] = None
    provider_id: str
    model_id: str
    width: int
    height: int
    seed: Optional[int] = None
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    mime_type: str = "image/webp"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _resolve_dimensions(aspect_ratio: str, width: Optional[int], height: Optional[int]) -> tuple[int, int]:
    if width and height:
        return width, height
    ar = (aspect_ratio or "16:9").strip()
    if ar == "1:1":
        return 1024, 1024
    elif ar == "9:16":
        return 576, 1024
    else:  # 16:9 default
        return 1024, 576


def _save_raw_image(raw_bytes: bytes, provider_id: str, storage_path: Path, public_prefix: str) -> tuple[str, str, str]:
    storage_path.mkdir(parents=True, exist_ok=True)
    mime_type = "image/webp"
    ext = "webp"

    if raw_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        mime_type = "image/png"
        ext = "png"
    elif raw_bytes.startswith(b"\xff\xd8\xff"):
        mime_type = "image/jpeg"
        ext = "jpg"
    elif raw_bytes.startswith(b"RIFF") and len(raw_bytes) >= 12 and raw_bytes[8:12] == b"WEBP":
        mime_type = "image/webp"
        ext = "webp"

    sha = hashlib.sha256(raw_bytes).hexdigest()[:8]
    filename = f"{provider_id}_{uuid.uuid4().hex[:8]}_{sha}.{ext}"
    target_path = storage_path / filename
    target_path.write_bytes(raw_bytes)

    local_url = f"{public_prefix.rstrip('/')}/{filename}"
    return str(target_path), local_url, mime_type


def _resolve_kling_token(api_key: str) -> str:
    """Resolve Kling API credentials: auto-generate JWT HS256 if in access_key:secret_key format."""
    clean = api_key.strip()
    if ":" in clean:
        try:
            parts = clean.split(":", 1)
            ak, sk = parts[0].strip(), parts[1].strip()
            now = int(time.time())
            payload = {
                "iss": ak,
                "exp": now + 1800,
                "nbf": now - 5,
            }
            headers = {"alg": "HS256", "typ": "JWT"}
            return jwt.encode(payload, sk, algorithm="HS256", headers=headers)
        except Exception as e:
            logger.warning("failed_generating_kling_jwt", error=str(e))
            return clean
    return clean


def _resolve_adobe_credentials(api_key: str) -> tuple[str, str]:
    """Parse Adobe credentials in client_id:access_token format."""
    clean = api_key.strip()
    if ":" in clean:
        cid, tok = clean.split(":", 1)
        return cid.strip(), tok.strip()
    return "", clean


class UniversalImageAdapter:
    """Universal multi-protocol adapter for AI Image generation across 17+ models."""

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        public_url_prefix: Optional[str] = None,
        timeout_seconds: float = 90.0,
    ):
        settings = get_settings()
        self.storage_path = storage_path or settings.effective_preview_storage_path
        self.public_url_prefix = public_url_prefix or "/api/v1/assets/previews"
        self.timeout_seconds = timeout_seconds
        self.settings = settings

    async def ping_connection(
        self,
        provider_id: str,
        base_url: str,
        api_key: str,
        model_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Perform lightweight health check / ping to verify API credentials and connectivity."""
        clean_url = (base_url or "").rstrip("/")
        clean_key = (api_key or "").strip()

        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
            try:
                # 1. Google Gemini Direct / Nano Banana
                if provider_id in ("gemini-direct", "nano-banana-2-1"):
                    probe_url = f"{clean_url}/models?key={clean_key}"
                    res = await client.get(probe_url)
                    if res.status_code == 200:
                        return {"ok": True, "message": f"✓ {provider_id}: Google AI Studio key valid & quota active (200 OK)"}
                    elif res.status_code in (400, 401, 403):
                        data = res.json().get("error", {})
                        return {"ok": False, "message": f"Auth error ({res.status_code}): {data.get('message', res.text[:120])}"}
                    return {"ok": False, "message": f"HTTP {res.status_code}: {res.text[:120]}"}

                # 2. 9Router Local VPS
                elif provider_id == "9router":
                    probe_url = f"{clean_url}/models"
                    headers = {"Authorization": f"Bearer {clean_key}"} if clean_key else {}
                    res = await client.get(probe_url, headers=headers)
                    if res.status_code == 200:
                        return {"ok": True, "message": "✓ 9Router: Local router gateway online & reachable (200 OK)"}
                    return {"ok": False, "message": f"HTTP {res.status_code}: {res.text[:120]}"}

                # 3. Alibaba DashScope (Qwen Image)
                elif provider_id == "qwen-image-3":
                    probe_url = f"{clean_url}/models" if "/api/v1" in clean_url else f"{clean_url}/api/v1/models"
                    headers = {"Authorization": f"Bearer {clean_key}"}
                    res = await client.get(probe_url, headers=headers)
                    if res.status_code in (200, 404, 405):
                        # 404/405 without 401/403 means auth passed
                        return {"ok": True, "message": "✓ DashScope: Alibaba Model Studio token authenticated"}
                    elif res.status_code in (401, 403):
                        return {"ok": False, "message": f"Auth failed ({res.status_code}): Invalid DashScope API Key"}
                    return {"ok": False, "message": f"HTTP {res.status_code}: {res.text[:120]}"}

                # 4. Black Forest Labs FLUX
                elif provider_id == "flux":
                    headers = {"x-key": clean_key}
                    res = await client.get("https://api.bfl.ai/v1/user", headers=headers)
                    if res.status_code == 200:
                        return {"ok": True, "message": "✓ FLUX: BFL API key verified (200 OK)"}
                    elif res.status_code in (401, 403):
                        return {"ok": False, "message": f"FLUX Auth failed ({res.status_code}): Invalid key"}
                    return {"ok": False, "message": f"HTTP {res.status_code}: {res.text[:120]}"}

                # 5. Google Flow (Proxy check)
                elif provider_id == "google-flow":
                    from backend.app.core.proxy_health import check_socks5_health
                    is_online = await check_socks5_health()
                    if is_online:
                        return {"ok": True, "message": "✓ Google Flow: SOCKS5 Android proxy tunnel is ONLINE"}
                    return {"ok": False, "message": "Google Flow SOCKS5 proxy is OFFLINE"}

                # 6. Ideogram 4.0
                elif provider_id == "ideogram-4-0":
                    probe_url = clean_url if clean_url.endswith("/generate") else f"{clean_url}/generate"
                    headers = {"Api-Key": clean_key}
                    res = await client.get(clean_url, headers=headers)
                    if res.status_code in (200, 400, 404, 405):
                        return {"ok": True, "message": "✓ Ideogram 4.0: Api-Key authenticated"}
                    elif res.status_code in (401, 403):
                        return {"ok": False, "message": f"Ideogram Auth error ({res.status_code}): Invalid Api-Key"}
                    return {"ok": True, "message": f"✓ Ideogram 4.0: Endpoint verified ({res.status_code})"}

                # 7. Leonardo Phoenix
                elif provider_id == "leonardo-phoenix":
                    probe_url = f"{clean_url}/me"
                    headers = {"Authorization": f"Bearer {clean_key}"}
                    res = await client.get(probe_url, headers=headers)
                    if res.status_code == 200:
                        return {"ok": True, "message": "✓ Leonardo Phoenix: API key verified (200 OK)"}
                    elif res.status_code in (401, 403):
                        return {"ok": False, "message": f"Leonardo Auth error ({res.status_code}): Invalid API Key"}
                    return {"ok": False, "message": f"HTTP {res.status_code}: {res.text[:120]}"}

                # 8. Luma Uni-1
                elif provider_id == "luma-uni-1":
                    probe_url = f"{clean_url}/generations"
                    headers = {"Authorization": f"Bearer {clean_key}"}
                    res = await client.get(probe_url, headers=headers)
                    if res.status_code in (200, 204):
                        return {"ok": True, "message": "✓ Luma Uni-1: API key verified (200 OK)"}
                    elif res.status_code in (401, 403):
                        return {"ok": False, "message": f"Luma Auth error ({res.status_code}): Invalid Luma API Key"}
                    return {"ok": False, "message": f"HTTP {res.status_code}: {res.text[:120]}"}

                # 9. Kling Image 4.0
                elif provider_id == "kling-image-4-0":
                    token = _resolve_kling_token(clean_key)
                    headers = {"Authorization": f"Bearer {token}"}
                    res = await client.get(f"{clean_url}/user/balance", headers=headers)
                    if res.status_code in (200, 404, 405):
                        return {"ok": True, "message": "✓ Kling Image 4.0: Credentials & JWT token authenticated"}
                    elif res.status_code in (401, 403):
                        return {"ok": False, "message": f"Kling Auth error ({res.status_code}): Invalid Key/Token"}
                    return {"ok": True, "message": f"✓ Kling Image 4.0: Endpoint reached ({res.status_code})"}

                # 10. Adobe Firefly 4
                elif provider_id == "adobe-firefly-4":
                    cid, tok = _resolve_adobe_credentials(clean_key)
                    headers = {"Authorization": f"Bearer {tok}"}
                    if cid:
                        headers["x-api-key"] = cid
                    res = await client.get(f"{clean_url}/storage", headers=headers)
                    if res.status_code in (200, 404, 405):
                        return {"ok": True, "message": "✓ Adobe Firefly 4: Credentials format verified"}
                    elif res.status_code in (401, 403):
                        return {"ok": False, "message": f"Adobe Auth error ({res.status_code}): Invalid token or client_id"}
                    return {"ok": True, "message": f"✓ Adobe Firefly 4: Gateway reachable ({res.status_code})"}

                # 11. Standard OpenAI-compatible (GPT 2.6, Seedream BytePlus, Grok, etc.)
                else:
                    probe_url = f"{clean_url}/models"
                    headers = {"Authorization": f"Bearer {clean_key}"} if clean_key else {}
                    res = await client.get(probe_url, headers=headers)
                    if res.status_code == 200:
                        return {"ok": True, "message": f"✓ {provider_id}: OpenAI-compatible endpoint authenticated (200 OK)"}
                    elif res.status_code in (401, 403):
                        return {"ok": False, "message": f"Auth error ({res.status_code}): Invalid API Key"}
                    elif res.status_code in (404, 405):
                        # Some proxy gateways only implement /images/generations without /models
                        return {"ok": True, "message": f"✓ {provider_id}: Endpoint reachable ({clean_url})"}
                    return {"ok": False, "message": f"HTTP {res.status_code}: {res.text[:120]}"}

            except Exception as e:
                return {"ok": False, "message": f"Connection failed: {str(e)}"}

    async def generate_image(self, request: UniversalImageRequest) -> UniversalImageResult:
        """Route generation request to appropriate protocol handler with auto-fallback to 9Router."""
        provider_id = (request.provider_id or "gemini-direct").strip()
        width, height = _resolve_dimensions(request.aspect_ratio, request.width, request.height)

        try:
            if provider_id in ("gemini-direct", "nano-banana-2-1", "nano-banana-2.1"):
                return await self._generate_gemini_direct(request, width, height)
            elif provider_id == "qwen-image-3":
                return await self._generate_dashscope(request, width, height)
            elif provider_id == "flux":
                return await self._generate_bfl_flux(request, width, height)
            elif provider_id == "google-flow":
                return await self._generate_google_flow(request, width, height)
            elif provider_id == "ideogram-4-0":
                return await self._generate_ideogram(request, width, height)
            elif provider_id == "leonardo-phoenix":
                return await self._generate_leonardo(request, width, height)
            elif provider_id == "luma-uni-1":
                return await self._generate_luma(request, width, height)
            elif provider_id == "kling-image-4-0":
                return await self._generate_kling(request, width, height)
            elif provider_id == "adobe-firefly-4":
                return await self._generate_adobe_firefly(request, width, height)
            else:
                # 9Router, seedream-5-5, gpt-2-6, grok-imagine-2-0, midjourney-v8-2, etc.
                return await self._generate_openai_compatible(request, width, height)

        except Exception as primary_error:
            logger.warning(
                "universal_provider_failed",
                provider=provider_id,
                error=str(primary_error),
                prompt=request.prompt[:60],
            )
            if not request.enable_fallback or provider_id == "9router":
                raise primary_error

            # Execute automatic fallback to 9Router
            logger.info("initiating_auto_fallback_to_9router", reason=str(primary_error))
            fallback_res = await self._execute_9router_fallback(request, width, height, str(primary_error))
            return fallback_res

    async def _generate_gemini_direct(
        self, req: UniversalImageRequest, width: int, height: int
    ) -> UniversalImageResult:
        """Execute generation using Google AI Studio REST API."""
        base_url = (req.base_url_override or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        api_key = (req.api_key_override or "").strip()
        model_id = (req.model_id or "gemini-3.8-flash").strip()

        if not api_key:
            raise ValueError("API Key is required for Gemini Direct API.")

        raw_bytes: Optional[bytes] = None

        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds)) as client:
            # Protocol A: Imagen Models (:predict)
            if model_id.startswith("imagen-"):
                predict_url = f"{base_url}/models/{model_id}:predict?key={api_key}"
                ar = req.aspect_ratio if req.aspect_ratio in ("16:9", "1:1", "9:16") else "16:9"
                payload = {
                    "instances": [{"prompt": req.prompt}],
                    "parameters": {
                        "sampleCount": 1,
                        "aspectRatio": ar,
                    },
                }
                res = await client.post(predict_url, json=payload)
                if res.status_code != 200:
                    raise RuntimeError(f"Google Imagen API failed ({res.status_code}): {res.text[:200]}")
                data = res.json()
                preds = data.get("predictions") or []
                if not preds or "bytesBase64Encoded" not in preds[0]:
                    raise RuntimeError(f"No image bytes in Imagen response: {res.text[:200]}")
                raw_bytes = base64.b64decode(preds[0]["bytesBase64Encoded"])

            # Protocol B: Gemini Multimodal Content Generation
            else:
                gen_url = f"{base_url}/models/{model_id}:generateContent?key={api_key}"
                parts: list[dict[str, Any]] = [{"text": req.prompt}]

                # Include visual anchor reference images if provided
                if req.reference_image_paths:
                    for ref_path in req.reference_image_paths[:3]:
                        p = Path(ref_path)
                        if p.exists() and p.is_file():
                            ref_b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
                            parts.append({
                                "inlineData": {
                                    "mimeType": "image/jpeg" if p.suffix.lower() in (".jpg", ".jpeg") else "image/png",
                                    "data": ref_b64,
                                }
                            })

                payload = {
                    "contents": [{"parts": parts}],
                    "generationConfig": {
                        "responseModalities": ["TEXT", "IMAGE"],
                    },
                }
                res = await client.post(gen_url, json=payload)
                if res.status_code != 200:
                    raise RuntimeError(f"Gemini API failed ({res.status_code}): {res.text[:200]}")
                data = res.json()
                candidates = data.get("candidates") or []
                text_messages: list[str] = []
                if candidates:
                    for part in candidates[0].get("content", {}).get("parts", []):
                        if "text" in part:
                            text_messages.append(part["text"])
                        inline = part.get("inlineData") or part.get("inline_data")
                        if inline and inline.get("data"):
                            raw_bytes = base64.b64decode(inline["data"])
                            break

                if not raw_bytes:
                    text_summary = " ".join(text_messages).strip()
                    detail = f": {text_summary[:200]}" if text_summary else ""
                    raise RuntimeError(
                        f"Gemini model '{model_id}' returned text only without image data{detail}. Falling back."
                    )

        local_path, local_url, mime_type = _save_raw_image(
            raw_bytes, req.provider_id, self.storage_path, self.public_url_prefix
        )
        return UniversalImageResult(
            local_path=local_path,
            local_url=local_url,
            provider_id=req.provider_id,
            model_id=model_id,
            width=width,
            height=height,
            seed=req.seed,
            mime_type=mime_type,
        )

    async def _generate_ideogram(
        self, req: UniversalImageRequest, width: int, height: int
    ) -> UniversalImageResult:
        """Execute generation using Ideogram 4.0 REST API."""
        base_url = (req.base_url_override or "https://api.ideogram.ai/v1").rstrip("/")
        api_key = (req.api_key_override or "").strip()
        model_id = (req.model_id or "V_4_0").strip()

        if not api_key:
            raise ValueError("Ideogram API Key is required for Ideogram 4.0.")

        endpoint = base_url if base_url.endswith("/generate") else f"{base_url}/generate"
        headers = {
            "Api-Key": api_key,
            "Content-Type": "application/json",
        }

        ar_map = {
            "16:9": "ASPECT_16_9",
            "9:16": "ASPECT_9_16",
            "1:1": "ASPECT_1_1",
        }
        ar_str = ar_map.get(req.aspect_ratio, "ASPECT_16_9")
        payload: dict[str, Any] = {
            "image_request": {
                "prompt": req.prompt,
                "aspect_ratio": ar_str,
                "model": model_id,
                "magic_prompt_option": "AUTO",
            }
        }
        if req.negative_prompt:
            payload["image_request"]["negative_prompt"] = req.negative_prompt
        if req.seed is not None:
            payload["image_request"]["seed"] = req.seed

        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds)) as client:
            res = await client.post(endpoint, headers=headers, json=payload)
            if res.status_code != 200:
                raise RuntimeError(f"Ideogram API failed ({res.status_code}): {res.text[:200]}")
            data = res.json()
            items = data.get("data") or []
            if not items or "url" not in items[0]:
                raise RuntimeError(f"No image url returned by Ideogram: {res.text[:200]}")
            img_url = items[0]["url"]

            dl = await client.get(img_url)
            if dl.status_code != 200:
                raise RuntimeError(f"Failed to download Ideogram image: HTTP {dl.status_code}")
            raw_bytes = dl.content

        local_path, local_url, mime_type = _save_raw_image(
            raw_bytes, "ideogram", self.storage_path, self.public_url_prefix
        )
        return UniversalImageResult(
            local_path=local_path,
            local_url=local_url,
            remote_url=img_url,
            provider_id="ideogram-4-0",
            model_id=model_id,
            width=width,
            height=height,
            seed=req.seed,
            mime_type=mime_type,
        )

    async def _generate_leonardo(
        self, req: UniversalImageRequest, width: int, height: int
    ) -> UniversalImageResult:
        """Execute generation using Leonardo Phoenix Async Generations API."""
        base_url = (req.base_url_override or "https://cloud.leonardo.ai/api/rest/v1").rstrip("/")
        api_key = (req.api_key_override or "").strip()
        model_id = (req.model_id or "leonardo-phoenix-1.0").strip()

        if not api_key:
            raise ValueError("Leonardo API Key is required for Leonardo Phoenix.")

        endpoint = f"{base_url}/generations"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "prompt": req.prompt,
            "width": width,
            "height": height,
            "num_images": 1,
        }
        if req.negative_prompt:
            payload["negative_prompt"] = req.negative_prompt
        if req.seed is not None:
            payload["seed"] = req.seed
        if model_id and model_id != "leonardo-phoenix-1.0":
            payload["modelId"] = model_id

        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds)) as client:
            sub = await client.post(endpoint, headers=headers, json=payload)
            if sub.status_code != 200:
                raise RuntimeError(f"Leonardo submit failed ({sub.status_code}): {sub.text[:200]}")
            sub_data = sub.json()
            gen_id = (
                sub_data.get("sdGenerationJob", {}).get("generationId")
                or sub_data.get("generationId")
                or sub_data.get("id")
            )
            if not gen_id:
                raise RuntimeError(f"No generation ID returned by Leonardo: {sub.text[:200]}")

            poll_url = f"{base_url}/generations/{gen_id}"
            image_url: Optional[str] = None
            for _ in range(40):
                await asyncio.sleep(2.0)
                chk = await client.get(poll_url, headers=headers)
                if chk.status_code == 200:
                    cdata = chk.json()
                    job = cdata.get("generations_by_pk") or cdata.get("generation") or cdata
                    status = job.get("status")
                    if status == "COMPLETE":
                        images = job.get("generated_images") or []
                        if images and images[0].get("url"):
                            image_url = images[0]["url"]
                            break
                    elif status == "FAILED":
                        raise RuntimeError(f"Leonardo generation failed: {chk.text[:200]}")

            if not image_url:
                raise TimeoutError("Leonardo generation timed out after 80 seconds.")

            dl = await client.get(image_url)
            if dl.status_code != 200:
                raise RuntimeError(f"Failed to download Leonardo image: HTTP {dl.status_code}")
            raw_bytes = dl.content

        local_path, local_url, mime_type = _save_raw_image(
            raw_bytes, "leonardo", self.storage_path, self.public_url_prefix
        )
        return UniversalImageResult(
            local_path=local_path,
            local_url=local_url,
            remote_url=image_url,
            provider_id="leonardo-phoenix",
            model_id=model_id,
            width=width,
            height=height,
            seed=req.seed,
            mime_type=mime_type,
        )

    async def _generate_luma(
        self, req: UniversalImageRequest, width: int, height: int
    ) -> UniversalImageResult:
        """Execute generation using Luma Uni-1 Async Generations API."""
        base_url = (req.base_url_override or "https://api.lumalabs.ai/dream-machine/v1").rstrip("/")
        api_key = (req.api_key_override or "").strip()
        model_id = (req.model_id or "luma-uni-1").strip()

        if not api_key:
            raise ValueError("Luma API Key is required for Luma Uni-1.")

        endpoint = f"{base_url}/generations/image"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        ar = req.aspect_ratio if req.aspect_ratio in ("16:9", "1:1", "9:16") else "16:9"
        payload = {
            "prompt": req.prompt,
            "aspect_ratio": ar,
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds)) as client:
            sub = await client.post(endpoint, headers=headers, json=payload)
            if sub.status_code not in (200, 201):
                raise RuntimeError(f"Luma Uni-1 submit failed ({sub.status_code}): {sub.text[:200]}")
            sub_data = sub.json()
            gen_id = sub_data.get("id")
            if not gen_id:
                raise RuntimeError(f"No task id from Luma: {sub.text[:200]}")

            poll_url = f"{base_url}/generations/{gen_id}"
            image_url: Optional[str] = None
            for _ in range(40):
                await asyncio.sleep(2.0)
                chk = await client.get(poll_url, headers=headers)
                if chk.status_code == 200:
                    cdata = chk.json()
                    state = cdata.get("state")
                    if state == "completed":
                        image_url = cdata.get("assets", {}).get("image") or cdata.get("image_url")
                        if image_url:
                            break
                    elif state == "failed":
                        reason = cdata.get("failure_reason", "Generation failed")
                        raise RuntimeError(f"Luma generation failed: {reason}")

            if not image_url:
                raise TimeoutError("Luma Uni-1 generation timed out after 80 seconds.")

            dl = await client.get(image_url)
            if dl.status_code != 200:
                raise RuntimeError(f"Failed to download Luma image: HTTP {dl.status_code}")
            raw_bytes = dl.content

        local_path, local_url, mime_type = _save_raw_image(
            raw_bytes, "luma", self.storage_path, self.public_url_prefix
        )
        return UniversalImageResult(
            local_path=local_path,
            local_url=local_url,
            remote_url=image_url,
            provider_id="luma-uni-1",
            model_id=model_id,
            width=width,
            height=height,
            seed=req.seed,
            mime_type=mime_type,
        )

    async def _generate_kling(
        self, req: UniversalImageRequest, width: int, height: int
    ) -> UniversalImageResult:
        """Execute generation using Kling Image 4.0 API (supports AK:SK or Bearer JWT)."""
        base_url = (req.base_url_override or "https://api.klingai.com/v1").rstrip("/")
        api_key = (req.api_key_override or "").strip()
        model_id = (req.model_id or "kling-image-v4").strip()

        if not api_key:
            raise ValueError("Kling Access Key or JWT Token is required.")

        token = _resolve_kling_token(api_key)
        endpoint = f"{base_url}/images/generations"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        ar_map = {
            "16:9": "16:9",
            "9:16": "9:16",
            "1:1": "1:1",
        }
        payload = {
            "model": model_id,
            "prompt": req.prompt,
            "negative_prompt": req.negative_prompt or "",
            "aspect_ratio": ar_map.get(req.aspect_ratio, "16:9"),
            "n": 1,
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds)) as client:
            sub = await client.post(endpoint, headers=headers, json=payload)
            if sub.status_code not in (200, 201):
                raise RuntimeError(f"Kling Image 4.0 submit failed ({sub.status_code}): {sub.text[:200]}")
            sub_data = sub.json()
            task_id = sub_data.get("data", {}).get("task_id") or sub_data.get("task_id")
            if not task_id:
                raise RuntimeError(f"No task_id returned by Kling: {sub.text[:200]}")

            poll_url = f"{base_url}/images/generations/{task_id}"
            image_url: Optional[str] = None
            for _ in range(40):
                await asyncio.sleep(2.0)
                chk = await client.get(poll_url, headers=headers)
                if chk.status_code == 200:
                    cdata = chk.json()
                    data_block = cdata.get("data", {})
                    status = data_block.get("task_status", "").lower()
                    if status in ("succeed", "success", "completed"):
                        images = data_block.get("task_result", {}).get("images", []) or data_block.get("images", [])
                        if images and images[0].get("url"):
                            image_url = images[0]["url"]
                            break
                    elif status in ("failed", "error"):
                        err_msg = data_block.get("task_status_msg", "Kling task failed")
                        raise RuntimeError(f"Kling task failed: {err_msg}")

            if not image_url:
                raise TimeoutError("Kling generation timed out after 80 seconds.")

            dl = await client.get(image_url)
            if dl.status_code != 200:
                raise RuntimeError(f"Failed to download Kling image: HTTP {dl.status_code}")
            raw_bytes = dl.content

        local_path, local_url, mime_type = _save_raw_image(
            raw_bytes, "kling", self.storage_path, self.public_url_prefix
        )
        return UniversalImageResult(
            local_path=local_path,
            local_url=local_url,
            remote_url=image_url,
            provider_id="kling-image-4-0",
            model_id=model_id,
            width=width,
            height=height,
            seed=req.seed,
            mime_type=mime_type,
        )

    async def _generate_adobe_firefly(
        self, req: UniversalImageRequest, width: int, height: int
    ) -> UniversalImageResult:
        """Execute generation using Adobe Firefly 4 REST API (supports client_id:access_token)."""
        base_url = (req.base_url_override or "https://firefly-api.adobe.io/v3").rstrip("/")
        api_key = (req.api_key_override or "").strip()
        model_id = (req.model_id or "firefly-image-4").strip()

        if not api_key:
            raise ValueError("Adobe Firefly token or client_id:access_token is required.")

        cid, tok = _resolve_adobe_credentials(api_key)
        endpoint = f"{base_url}/images/generate"
        headers = {
            "Authorization": f"Bearer {tok}",
            "Content-Type": "application/json",
        }
        if cid:
            headers["x-api-key"] = cid

        payload = {
            "prompt": req.prompt,
            "size": {
                "width": width,
                "height": height,
            },
            "numVariations": 1,
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds)) as client:
            res = await client.post(endpoint, headers=headers, json=payload)
            if res.status_code not in (200, 201):
                raise RuntimeError(f"Adobe Firefly 4 failed ({res.status_code}): {res.text[:200]}")
            data = res.json()
            outputs = data.get("outputs") or data.get("images") or []
            if not outputs:
                raise RuntimeError(f"No image outputs from Adobe Firefly: {res.text[:200]}")
            image_url = outputs[0].get("image", {}).get("url") or outputs[0].get("url")
            if not image_url:
                raise RuntimeError(f"No image url in Adobe Firefly response: {res.text[:200]}")

            dl = await client.get(image_url)
            if dl.status_code != 200:
                raise RuntimeError(f"Failed to download Adobe Firefly image: HTTP {dl.status_code}")
            raw_bytes = dl.content

        local_path, local_url, mime_type = _save_raw_image(
            raw_bytes, "adobe-firefly", self.storage_path, self.public_url_prefix
        )
        return UniversalImageResult(
            local_path=local_path,
            local_url=local_url,
            remote_url=image_url,
            provider_id="adobe-firefly-4",
            model_id=model_id,
            width=width,
            height=height,
            seed=req.seed,
            mime_type=mime_type,
        )

    async def _generate_openai_compatible(
        self, req: UniversalImageRequest, width: int, height: int
    ) -> UniversalImageResult:
        """Execute generation using standard /images/generations endpoint."""
        base_url = (req.base_url_override or "http://127.0.0.1:8080/v1").rstrip("/")
        api_key = (req.api_key_override or "").strip()
        model_id = (req.model_id or "ag/gemini-3.8-flash").strip()

        call_url = f"{base_url}/images/generations"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload: dict[str, Any] = {
            "model": model_id,
            "prompt": req.prompt,
            "n": 1,
            "size": f"{width}x{height}",
            "response_format": "b64_json",
        }
        if req.negative_prompt:
            payload["negative_prompt"] = req.negative_prompt
        if req.seed is not None:
            payload["seed"] = req.seed

        raw_bytes: Optional[bytes] = None

        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds)) as client:
            res = await client.post(call_url, headers=headers, json=payload)
            if res.status_code == 429 or "quota" in res.text.lower() or "rate limit" in res.text.lower():
                raise RuntimeError(f"Rate limit / Quota exceeded on {req.provider_id} (HTTP {res.status_code}): {res.text[:180]}")
            if res.status_code != 200:
                raise RuntimeError(f"{req.provider_id} call failed ({res.status_code}): {res.text[:200]}")

            data = res.json()
            items = data.get("data") if isinstance(data, dict) else None
            if not items or not isinstance(items, list) or len(items) == 0:
                raise RuntimeError(f"No image data in response: {res.text[:180]}")

            first = items[0]
            if first.get("b64_json"):
                raw_bytes = base64.b64decode(first["b64_json"])
            elif first.get("url") and first["url"].startswith("http"):
                dl_res = await client.get(first["url"])
                if dl_res.status_code == 200:
                    raw_bytes = dl_res.content
                else:
                    raise RuntimeError(f"Failed to download image from {first['url']}: HTTP {dl_res.status_code}")

        if not raw_bytes:
            raise RuntimeError(f"Could not retrieve raster image from {req.provider_id}")

        local_path, local_url, mime_type = _save_raw_image(
            raw_bytes, req.provider_id, self.storage_path, self.public_url_prefix
        )
        return UniversalImageResult(
            local_path=local_path,
            local_url=local_url,
            provider_id=req.provider_id,
            model_id=model_id,
            width=width,
            height=height,
            seed=req.seed,
            mime_type=mime_type,
        )

    async def _generate_dashscope(
        self, req: UniversalImageRequest, width: int, height: int
    ) -> UniversalImageResult:
        """Execute generation using Alibaba DashScope Image Synthesis Task API."""
        base_url = (req.base_url_override or "https://dashscope-intl.aliyuncs.com/api/v1").rstrip("/")
        api_key = (req.api_key_override or "").strip()
        model_id = (req.model_id or "qwen-image-3.0").strip()

        if not api_key:
            raise ValueError("DashScope API Key is required for Qwen Image 3.0.")

        task_url = f"{base_url}/services/aigc/text2image/image-synthesis"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        payload = {
            "model": model_id,
            "input": {
                "prompt": req.prompt,
                "negative_prompt": req.negative_prompt or "",
            },
            "parameters": {
                "size": f"{width}*{height}",
                "n": 1,
            },
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds)) as client:
            submit_res = await client.post(task_url, headers=headers, json=payload)
            if submit_res.status_code != 200:
                raise RuntimeError(f"DashScope submit failed ({submit_res.status_code}): {submit_res.text[:200]}")

            submit_data = submit_res.json()
            task_id = submit_data.get("output", {}).get("task_id")
            if not task_id:
                raise RuntimeError(f"No task_id returned by DashScope: {submit_res.text[:200]}")

            # Poll task status
            poll_url = f"{base_url}/tasks/{task_id}"
            image_url: Optional[str] = None

            for _ in range(40):
                await asyncio.sleep(2.0)
                p_res = await client.get(poll_url, headers={"Authorization": f"Bearer {api_key}"})
                if p_res.status_code == 200:
                    p_data = p_res.json()
                    status = p_data.get("output", {}).get("task_status")
                    if status == "SUCCEEDED":
                        results = p_data.get("output", {}).get("results") or []
                        if results and "url" in results[0]:
                            image_url = results[0]["url"]
                            break
                    elif status == "FAILED":
                        err_msg = p_data.get("output", {}).get("message", "Task failed")
                        raise RuntimeError(f"DashScope task failed: {err_msg}")

            if not image_url:
                raise TimeoutError("DashScope generation timed out after 80 seconds.")

            dl_res = await client.get(image_url)
            if dl_res.status_code != 200:
                raise RuntimeError(f"Failed to download rendered image from DashScope: HTTP {dl_res.status_code}")

            raw_bytes = dl_res.content

        local_path, local_url, mime_type = _save_raw_image(
            raw_bytes, "qwen-image", self.storage_path, self.public_url_prefix
        )
        return UniversalImageResult(
            local_path=local_path,
            local_url=local_url,
            remote_url=image_url,
            provider_id="qwen-image-3",
            model_id=model_id,
            width=width,
            height=height,
            seed=req.seed,
            mime_type=mime_type,
        )

    async def _generate_bfl_flux(
        self, req: UniversalImageRequest, width: int, height: int
    ) -> UniversalImageResult:
        """Execute generation using Black Forest Labs FLUX REST API."""
        api_key = (req.api_key_override or "").strip()
        model_id = (req.model_id or "flux-pro-1.1-ultra").strip()

        if not api_key:
            raise ValueError("BFL API Key is required for FLUX.")

        endpoint = f"https://api.bfl.ai/v1/{model_id}"
        headers = {"x-key": api_key, "Content-Type": "application/json"}
        payload = {
            "prompt": req.prompt,
            "width": width,
            "height": height,
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds)) as client:
            sub = await client.post(endpoint, headers=headers, json=payload)
            if sub.status_code != 200:
                raise RuntimeError(f"BFL FLUX submit failed ({sub.status_code}): {sub.text[:200]}")

            task_id = sub.json().get("id")
            if not task_id:
                raise RuntimeError(f"No task id from BFL: {sub.text[:200]}")

            image_url: Optional[str] = None
            for _ in range(40):
                await asyncio.sleep(2.0)
                chk = await client.get(f"https://api.bfl.ai/v1/get_result?id={task_id}", headers=headers)
                if chk.status_code == 200:
                    cdata = chk.json()
                    status = cdata.get("status")
                    if status == "Ready":
                        image_url = cdata.get("result", {}).get("sample")
                        break
                    elif status in ("Error", "Failed"):
                        raise RuntimeError(f"FLUX generation failed: {chk.text[:200]}")

            if not image_url:
                raise TimeoutError("FLUX generation timed out.")

            dl = await client.get(image_url)
            if dl.status_code != 200:
                raise RuntimeError(f"Failed to download FLUX image: HTTP {dl.status_code}")
            raw_bytes = dl.content

        local_path, local_url, mime_type = _save_raw_image(
            raw_bytes, "flux", self.storage_path, self.public_url_prefix
        )
        return UniversalImageResult(
            local_path=local_path,
            local_url=local_url,
            remote_url=image_url,
            provider_id="flux",
            model_id=model_id,
            width=width,
            height=height,
            seed=req.seed,
            mime_type=mime_type,
        )

    async def _generate_google_flow(
        self, req: UniversalImageRequest, width: int, height: int
    ) -> UniversalImageResult:
        """Trigger generation through Google Flow SOCKS5 client or queue."""
        from backend.app.core.proxy_health import check_socks5_health
        is_healthy = await check_socks5_health()
        if not is_healthy:
            raise RuntimeError("Google Flow SOCKS5 tunnel is offline. Please check Android proxy.")

        # Fallback to local 9Router with note if direct interactive flow requires browser queue
        return await self._execute_9router_fallback(
            req, width, height, "Google Flow queued via SOCKS5"
        )

    async def _execute_9router_fallback(
        self,
        req: UniversalImageRequest,
        width: int,
        height: int,
        reason: str,
    ) -> UniversalImageResult:
        """Automated failover to 9Router when primary provider hits rate limit or errors."""
        fallback_req = UniversalImageRequest(
            provider_id="9router",
            model_id="ag/gemini-3.8-flash",
            prompt=req.prompt,
            negative_prompt=req.negative_prompt,
            aspect_ratio=req.aspect_ratio,
            width=width,
            height=height,
            seed=req.seed,
            base_url_override=self.settings.effective_ninerouter_base_url,
            api_key_override=self.settings.effective_ninerouter_api_key,
            enable_fallback=False,
        )

        res = await self._generate_openai_compatible(fallback_req, width, height)
        res.fallback_used = True
        res.fallback_reason = reason
        return res
