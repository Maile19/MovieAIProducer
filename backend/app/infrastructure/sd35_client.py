"""Stable Diffusion 3.5 Large Image Generation Client.

Provides an async client adapter to interface with Hugging Face Space
(stabilityai-stable-diffusion-3-5-large.hf.space) via Gradio REST/SSE API,
with extensible provider architecture for future multi-provider fallbacks (Fal.ai, Together AI).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any
import uuid

import httpx
import structlog

logger = structlog.get_logger(__name__)


class ImageGenerationError(Exception):
    """Base exception for visual generation errors."""
    pass


class ZeroGPUQuotaExceededError(ImageGenerationError):
    """Raised specifically when Hugging Face ZeroGPU quota is exhausted."""
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


class RateLimitExceededError(ImageGenerationError):
    """Raised when an AI provider's rate limit or quota is exceeded (HTTP 429)."""
    def __init__(
        self,
        message: str,
        provider: str = "unknown",
        model: str | None = None,
        retry_after: float | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.retry_after = retry_after
        self.details = details or {}


@dataclass
class ImageGenerationRequest:
    prompt: str
    negative_prompt: str = ""
    seed: int = 0
    randomize_seed: bool = True
    width: int = 1024
    height: int = 1024
    guidance_scale: float = 4.5
    num_inference_steps: int = 28
    provider: str | None = None
    model: str | None = None
    enable_fallback: bool = True
    reference_image_paths: list[str] = field(default_factory=list)


@dataclass
class ImageGenerationResult:
    local_path: str
    local_url: str
    remote_url: str | None
    seed: int
    width: int
    height: int
    steps: int
    file_size_bytes: int
    mime_type: str
    sha256_checksum: str
    provider: str = "sd35_large_hf"
    model: str | None = None
    rate_limit_info: dict[str, Any] | None = None


class ImageGenerationProvider(ABC):
    """Abstract provider interface for multi-engine visual storyboard generation."""

    @abstractmethod
    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """Generate an image from prompt and return local storage reference."""
        raise NotImplementedError


class SD35HuggingFaceProvider(ImageGenerationProvider):
    """Client for stabilityai/stable-diffusion-3.5-large hosted on Hugging Face Spaces."""

    def __init__(
        self,
        space_url: str = "https://stabilityai-stable-diffusion-3-5-large.hf.space",
        token: str = "",
        default_steps: int = 28,
        storage_path: Path = Path("./data/assets/previews"),
        public_url_prefix: str = "/api/v1/assets/previews",
        timeout_seconds: float = 180.0,
    ):
        self.space_url = space_url.rstrip("/")
        self.token = token.strip() if token else ""
        self.default_steps = default_steps
        self.storage_path = storage_path
        self.public_url_prefix = public_url_prefix.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "MovieAIProducer/1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        self.storage_path.mkdir(parents=True, exist_ok=True)
        headers = self._get_headers()

        steps = request.num_inference_steps if request.num_inference_steps > 0 else self.default_steps

        # Payload structure according to /gradio_api/info
        payload = {
            "data": [
                request.prompt,
                request.negative_prompt,
                request.seed,
                request.randomize_seed,
                request.width,
                request.height,
                request.guidance_scale,
                steps,
            ]
        }

        call_url = f"{self.space_url}/gradio_api/call/infer"
        logger.info("sd35_initiating_call", prompt=request.prompt[:60], steps=steps, space_url=self.space_url)

        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds)) as client:
            try:
                res = await client.post(call_url, headers=headers, json=payload)
            except Exception as e:
                logger.error("sd35_connection_failed", error=str(e), url=call_url)
                raise ImageGenerationError(f"Failed to connect to Hugging Face Space: {str(e)}") from e

            if res.status_code != 200:
                text_err = res.text[:300]
                logger.error("sd35_call_rejected", status_code=res.status_code, body=text_err)
                if "quota" in text_err.lower() or res.status_code == 429:
                    raise ZeroGPUQuotaExceededError(
                        f"ZeroGPU quota exceeded on Hugging Face: {text_err}"
                    )
                raise ImageGenerationError(f"Hugging Face Space rejected request ({res.status_code}): {text_err}")

            try:
                event_data = res.json()
                event_id = event_data.get("event_id")
            except Exception:
                raise ImageGenerationError(f"Invalid JSON response from Hugging Face Space: {res.text[:200]}")

            if not event_id:
                raise ImageGenerationError(f"No event_id returned by Hugging Face Space: {res.text[:200]}")

            # Now stream SSE from /gradio_api/call/infer/{event_id}
            poll_url = f"{self.space_url}/gradio_api/call/infer/{event_id}"
            logger.info("sd35_polling_sse", event_id=event_id)

            try:
                async with client.stream("GET", poll_url, headers=headers) as stream_resp:
                    if stream_resp.status_code != 200:
                        err_body = (await stream_resp.aread()).decode("utf-8", errors="ignore")[:300]
                        if "quota" in err_body.lower() or stream_resp.status_code == 429:
                            raise ZeroGPUQuotaExceededError(f"ZeroGPU quota exceeded: {err_body}")
                        raise ImageGenerationError(f"Failed to stream SSE ({stream_resp.status_code}): {err_body}")

                    current_event = None
                    async for raw_line in stream_resp.aiter_lines():
                        line = raw_line.strip()
                        if not line:
                            continue

                        if line.startswith("event:"):
                            current_event = line[6:].strip()
                            continue

                        if line.startswith("data:"):
                            data_str = line[5:].strip()
                            if current_event == "error":
                                self._handle_error_event(data_str)

                            elif current_event == "complete":
                                return await self._handle_complete_event(
                                    data_str,
                                    client=client,
                                    headers=headers,
                                    request=request,
                                    steps=steps,
                                )

                    # If stream ended without complete event:
                    raise ImageGenerationError("Hugging Face Space SSE stream ended unexpectedly without complete result.")
            except (ImageGenerationError, ZeroGPUQuotaExceededError):
                raise
            except Exception as e:
                logger.error("sd35_sse_stream_exception", error=str(e))
                raise ImageGenerationError(f"Error during SSE streaming from Hugging Face: {str(e)}") from e

    def _handle_error_event(self, data_str: str) -> None:
        try:
            err_obj = json.loads(data_str)
        except Exception:
            err_obj = {"error": data_str}

        err_msg = ""
        if isinstance(err_obj, dict):
            err_msg = err_obj.get("error") or err_obj.get("title") or json.dumps(err_obj)
        else:
            err_msg = str(err_obj)

        logger.error("sd35_sse_error_received", error_msg=err_msg)
        if "zerogpu quota" in err_msg.lower() or "quota" in err_msg.lower():
            raise ZeroGPUQuotaExceededError(
                f"ZeroGPU Quota Terlampaui: {err_msg}. Masukkan HF_TOKEN valid (atau akun Hugging Face PRO) di konfigurasi backend.",
                details=err_obj if isinstance(err_obj, dict) else {},
            )
        raise ImageGenerationError(f"Hugging Face SD 3.5 Generation Error: {err_msg}")

    async def _handle_complete_event(
        self,
        data_str: str,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        request: ImageGenerationRequest,
        steps: int,
    ) -> ImageGenerationResult:
        try:
            complete_data = json.loads(data_str)
        except Exception as e:
            raise ImageGenerationError(f"Failed to parse complete event data: {data_str[:200]}") from e

        # Gradio complete data: [ImageData, seed]
        image_info: dict[str, Any] = {}
        used_seed: int = request.seed
        if isinstance(complete_data, list) and len(complete_data) > 0:
            image_info = complete_data[0] or {}
            if len(complete_data) > 1 and isinstance(complete_data[1], (int, float)):
                used_seed = int(complete_data[1])
        elif isinstance(complete_data, dict):
            image_info = complete_data

        remote_url = image_info.get("url")
        remote_path = image_info.get("path")

        download_url = remote_url
        if not download_url:
            if remote_path:
                download_url = f"{self.space_url}/gradio_api/file={remote_path}"
            else:
                raise ImageGenerationError("No image URL or path returned in complete event.")

        if not download_url.startswith("http"):
            download_url = f"{self.space_url}/{download_url.lstrip('/')}"

        logger.info("sd35_downloading_image", url=download_url)
        img_res = await client.get(download_url, headers=headers)
        if img_res.status_code != 200:
            raise ImageGenerationError(
                f"Failed to download generated image from {download_url} ({img_res.status_code})"
            )

        image_bytes = img_res.content
        file_size = len(image_bytes)
        sha256 = hashlib.sha256(image_bytes).hexdigest()

        mime_type = image_info.get("mime_type") or img_res.headers.get("content-type") or "image/webp"
        ext = "webp"
        if "png" in mime_type:
            ext = "png"
        elif "jpeg" in mime_type or "jpg" in mime_type:
            ext = "jpg"

        file_id = f"sd35_{uuid.uuid4().hex[:12]}_{sha256[:8]}.{ext}"
        target_path = self.storage_path / file_id
        target_path.write_bytes(image_bytes)

        local_url = f"{self.public_url_prefix}/{file_id}"
        logger.info("sd35_saved_locally", local_path=str(target_path), local_url=local_url, size=file_size)

        return ImageGenerationResult(
            local_path=str(target_path),
            local_url=local_url,
            remote_url=download_url,
            seed=used_seed,
            width=request.width,
            height=request.height,
            steps=steps,
            file_size_bytes=file_size,
            mime_type=mime_type,
            sha256_checksum=sha256,
            provider="sd35_large_hf",
        )


class NineRouterImageProvider(ImageGenerationProvider):
    """Client for 9Router OpenAI-compatible /v1/images/generations API with Multi-Model Combo failover."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080/v1",
        api_key: str = "sk-3f8dbe69b93ed880-df5qur-b3936273",
        default_model: str = "gemini-3.1-flash-image",
        combo_models: list[str] | None = None,
        storage_path: Path = Path("./data/assets/previews"),
        public_url_prefix: str = "/api/v1/assets/previews",
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip() if api_key else ""
        self.default_model = default_model
        # Only retain models that genuinely support binary image generation (remove text/chat models)
        self.combo_models = combo_models or ["gemini-3.1-flash-image"]
        self.storage_path = storage_path
        self.public_url_prefix = public_url_prefix.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "MovieAIProducer-9Router/1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        import base64
        self.storage_path.mkdir(parents=True, exist_ok=True)
        headers = self._get_headers()

        candidates: list[str] = []
        if request.model and request.model.strip():
            candidates.append(request.model.strip())
        for cm in self.combo_models:
            if cm not in candidates:
                candidates.append(cm)
        if not candidates:
            candidates = [self.default_model]

        call_url = f"{self.base_url}/images/generations"
        last_error: Exception | None = None
        rate_limit_details: dict[str, Any] = {}
        successful_model: str | None = None
        raw_image_bytes: bytes | None = None
        mime_type = "image/webp"

        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds)) as client:
            for idx, candidate_model in enumerate(candidates):
                logger.info("9router_attempting_model", model=candidate_model, candidate_index=idx, prompt=request.prompt[:60])
                payload = {
                    "model": candidate_model,
                    "prompt": request.prompt,
                    "n": 1,
                    "size": f"{request.width}x{request.height}",
                    "response_format": "b64_json",
                }
                if request.negative_prompt:
                    payload["negative_prompt"] = request.negative_prompt
                if request.seed:
                    payload["seed"] = request.seed

                try:
                    res = await client.post(call_url, headers=headers, json=payload)
                except Exception as net_err:
                    logger.warning("9router_connection_error", model=candidate_model, error=str(net_err))
                    last_error = net_err
                    continue

                if res.status_code == 429 or "quota" in res.text.lower() or "rate limit" in res.text.lower():
                    logger.warning(
                        "9router_rate_limited",
                        model=candidate_model,
                        status_code=res.status_code,
                        error=res.text[:250],
                    )
                    rate_limit_details[candidate_model] = {
                        "status_code": res.status_code,
                        "error": res.text[:200],
                        "model": candidate_model,
                    }
                    last_error = RateLimitExceededError(
                        f"9Router rate limit/quota exceeded for model '{candidate_model}': {res.text[:200]}",
                        provider="9router",
                        model=candidate_model,
                        details=rate_limit_details,
                    )
                    continue

                if res.status_code != 200:
                    logger.warning("9router_model_rejected", model=candidate_model, status_code=res.status_code, body=res.text[:200])
                    last_error = ImageGenerationError(f"9Router rejected request with model '{candidate_model}' ({res.status_code}): {res.text[:200]}")
                    continue

                try:
                    data = res.json()
                except Exception as json_err:
                    last_error = ImageGenerationError(f"Failed to parse 9Router JSON: {res.text[:200]}")
                    continue

                items = data.get("data") if isinstance(data, dict) else None
                if not items or not isinstance(items, list) or len(items) == 0:
                    last_error = ImageGenerationError(f"No image data returned from 9Router: {res.text[:200]}")
                    continue

                first_item = items[0]
                b64 = first_item.get("b64_json")
                remote_url = first_item.get("url")

                if b64 and len(b64.strip()) > 0:
                    try:
                        decoded_bytes = base64.b64decode(b64)
                        # Ensure decoded bytes are raster binary (PNG, JPEG, WebP)
                        if decoded_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
                            mime_type = "image/png"
                        elif decoded_bytes.startswith(b"\xff\xd8\xff"):
                            mime_type = "image/jpeg"
                        elif decoded_bytes.startswith(b"RIFF") and len(decoded_bytes) >= 12 and decoded_bytes[8:12] == b"WEBP":
                            mime_type = "image/webp"
                        else:
                            logger.warning("9router_non_raster_bytes_returned", model=candidate_model)
                            last_error = ImageGenerationError(f"Model '{candidate_model}' returned non-raster binary data.")
                            continue

                        raw_image_bytes = decoded_bytes
                        successful_model = candidate_model
                        break
                    except Exception as b64_err:
                        logger.warning("9router_b64_decode_failed", error=str(b64_err))
                        last_error = ImageGenerationError(f"Failed to decode base64 image: {str(b64_err)}")
                        continue

                elif remote_url and remote_url.startswith("http"):
                    try:
                        img_res = await client.get(remote_url)
                        if img_res.status_code == 200:
                            content = img_res.content
                            if content.startswith(b"\x89PNG\r\n\x1a\n"):
                                mime_type = "image/png"
                            elif content.startswith(b"\xff\xd8\xff"):
                                mime_type = "image/jpeg"
                            elif content.startswith(b"RIFF") and len(content) >= 12 and content[8:12] == b"WEBP":
                                mime_type = "image/webp"
                            else:
                                logger.warning("9router_downloaded_non_raster", model=candidate_model)
                                last_error = ImageGenerationError(f"Downloaded asset from '{candidate_model}' is not a valid raster image.")
                                continue

                            raw_image_bytes = content
                            successful_model = candidate_model
                            break
                        else:
                            last_error = ImageGenerationError(f"Failed to fetch remote image from {remote_url}: HTTP {img_res.status_code}")
                            continue
                    except Exception as dl_err:
                        logger.warning("9router_image_download_failed", url=remote_url, error=str(dl_err))
                        last_error = ImageGenerationError(f"Failed to download image from {remote_url}: {str(dl_err)}")
                        continue

                else:
                    logger.warning("9router_missing_binary_image_payload", model=candidate_model)
                    last_error = ImageGenerationError(
                        f"Model '{candidate_model}' did not return binary image data (b64_json or url)."
                    )
                    continue

        if raw_image_bytes is None:
            if rate_limit_details or isinstance(last_error, RateLimitExceededError):
                raise RateLimitExceededError(
                    "Semua model gambar 9Router/Gemini sedang mencapai batas kuota (HTTP 429). Silakan pindah ke Google Flow [5 Akun PRO].",
                    provider="9router",
                    model=candidates[0] if candidates else self.default_model,
                    details=rate_limit_details,
                )
            raise ImageGenerationError(
                f"9Router failed across all candidate combo models ({', '.join(candidates)}): {str(last_error)}"
            )

        sha256 = hashlib.sha256(raw_image_bytes).hexdigest()
        file_size = len(raw_image_bytes)
        ext = "png" if "png" in mime_type else "webp" if "webp" in mime_type else "jpg" if "jpeg" in mime_type else "png"
        file_id = f"9router_{uuid.uuid4().hex[:12]}_{sha256[:8]}.{ext}"
        target_path = self.storage_path / file_id
        target_path.write_bytes(raw_image_bytes)

        local_url = f"{self.public_url_prefix}/{file_id}"
        logger.info(
            "9router_image_generated",
            model=successful_model,
            local_path=str(target_path),
            size=file_size,
        )

        return ImageGenerationResult(
            local_path=str(target_path),
            local_url=local_url,
            remote_url=None,
            seed=request.seed,
            width=request.width,
            height=request.height,
            steps=request.num_inference_steps,
            file_size_bytes=file_size,
            mime_type=mime_type,
            sha256_checksum=sha256,
            provider="9router",
            model=successful_model,
            rate_limit_info=rate_limit_details if rate_limit_details else None,
        )


class MockImageProvider(ImageGenerationProvider):
    """Deterministic local mock provider for tests, CI, and zero-downtime offline fallback."""

    def __init__(
        self,
        storage_path: Path = Path("./data/assets/previews"),
        public_url_prefix: str = "/api/v1/assets/previews",
    ):
        self.storage_path = storage_path
        self.public_url_prefix = public_url_prefix.rstrip("/")

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        self.storage_path.mkdir(parents=True, exist_ok=True)
        # Valid small WebP byte stream
        mock_bytes = b"RIFF\x1a\x00\x00\x00WEBPVP8 \x0e\x00\x00\x00\xb0\x01\x00\x9d\x01*\x01\x00\x01\x00\x00\x01\x08\x00\x00\x00"
        sha256 = hashlib.sha256(mock_bytes).hexdigest()
        file_id = f"mock_{uuid.uuid4().hex[:12]}_{sha256[:8]}.webp"
        target_path = self.storage_path / file_id
        target_path.write_bytes(mock_bytes)
        local_url = f"{self.public_url_prefix}/{file_id}"

        return ImageGenerationResult(
            local_path=str(target_path),
            local_url=local_url,
            remote_url=None,
            seed=request.seed,
            width=request.width,
            height=request.height,
            steps=request.num_inference_steps,
            file_size_bytes=len(mock_bytes),
            mime_type="image/webp",
            sha256_checksum=sha256,
            provider="mock",
            model="mock_local_engine",
        )


class DynamicImageProviderRouter(ImageGenerationProvider):
    """Intelligent router orchestrating dynamic provider switching, combo mapping, and tier fallbacks."""

    def __init__(
        self,
        providers: dict[str, ImageGenerationProvider],
        default_provider: str = "9router",
        fallback_chain: list[str] | None = None,
    ):
        self.providers = providers
        self.default_provider = default_provider
        self.fallback_chain = fallback_chain or ["9router", "sd35_large_hf", "mock"]

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        req_provider = (request.provider or self.default_provider).lower().strip()
        primary_provider = self.providers.get(req_provider)

        execution_order: list[tuple[str, ImageGenerationProvider]] = []
        if primary_provider:
            execution_order.append((req_provider, primary_provider))
        else:
            def_prov = self.providers.get(self.default_provider)
            if def_prov:
                execution_order.append((self.default_provider, def_prov))

        if request.enable_fallback:
            for fallback_name in self.fallback_chain:
                fb_norm = fallback_name.lower().strip()
                if fb_norm in self.providers and not any(p[0] == fb_norm for p in execution_order):
                    execution_order.append((fb_norm, self.providers[fb_norm]))

        if not execution_order:
            raise ImageGenerationError(f"No configured image providers available for request: '{req_provider}'")

        last_err: Exception | None = None
        attempted: list[str] = []

        for p_name, prov in execution_order:
            attempted.append(p_name)
            logger.info("router_executing_provider", provider=p_name, prompt=request.prompt[:50])
            try:
                result = await prov.generate(request)
                if len(attempted) > 1:
                    result.rate_limit_info = {
                        "fallback_triggered": True,
                        "primary_provider": req_provider,
                        "fallback_provider": p_name,
                        "attempted_chain": attempted,
                        "primary_error": str(last_err),
                    }
                return result
            except (ZeroGPUQuotaExceededError, RateLimitExceededError, ImageGenerationError) as err:
                logger.warning(
                    "provider_execution_failed",
                    provider=p_name,
                    error=str(err),
                    fallback_available=len(attempted) < len(execution_order),
                )
                last_err = err
                if not request.enable_fallback:
                    raise

        if last_err:
            raise last_err
        raise ImageGenerationError(f"All configured providers failed: {', '.join(attempted)}")


def get_image_provider(
    provider_type: str | None = None,
    space_url: str | None = None,
    token: str | None = None,
    default_steps: int | None = None,
    storage_path: Path | None = None,
    public_url_prefix: str | None = None,
) -> ImageGenerationProvider:
    """Factory creating configured ImageGenerationProvider (Dynamic Router or specific provider)."""
    from backend.app.core.config import get_settings
    settings = get_settings()

    effective_storage = storage_path or settings.effective_preview_storage_path
    effective_prefix = public_url_prefix or "/api/v1/assets/previews"

    hf_provider = SD35HuggingFaceProvider(
        space_url=space_url or settings.sd35_space_url,
        token=token if token is not None else settings.hf_token,
        default_steps=default_steps or settings.sd35_default_steps,
        storage_path=effective_storage,
        public_url_prefix=effective_prefix,
    )

    nine_router_provider = NineRouterImageProvider(
        base_url=settings.effective_ninerouter_base_url,
        api_key=settings.effective_ninerouter_api_key,
        default_model=settings.ninerouter_default_model,
        combo_models=settings.ninerouter_combo_list,
        storage_path=effective_storage,
        public_url_prefix=effective_prefix,
        timeout_seconds=settings.ninerouter_timeout_seconds,
        max_retries=settings.ninerouter_max_retries,
    )

    mock_provider = MockImageProvider(
        storage_path=effective_storage,
        public_url_prefix=effective_prefix,
    )

    router = DynamicImageProviderRouter(
        providers={
            "9router": nine_router_provider,
            "sd35_large_hf": hf_provider,
            "mock": mock_provider,
        },
        default_provider=settings.image_provider_default,
        fallback_chain=settings.fallback_chain_list,
    )

    if provider_type:
        pt = provider_type.lower().strip()
        if pt in ("9router", "nine_router"):
            return nine_router_provider
        elif pt in ("ag_gemini_flash", "antigravity", "gemini_flash", "ag/gemini-3.8-flash"):
            return nine_router_provider
        elif pt in ("sd35", "sd35_large_hf", "hf", "huggingface"):
            return hf_provider
        elif pt in ("mock", "offline"):
            return mock_provider
        elif pt in ("router", "dynamic", "auto"):
            return router

    return router
