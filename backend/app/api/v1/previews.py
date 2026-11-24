from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.app.api.deps import get_current_user, get_session
from backend.app.core.config import get_settings
from backend.app.domain.transpiler import LivePromptTranspiler
from backend.app.infrastructure.database.models.auth import UserModel
from backend.app.infrastructure.database.models.pipeline import AssetModel
from backend.app.infrastructure.database.models.project import ProjectModel
from backend.app.infrastructure.database.models.story import SceneModel, ShotModel
from backend.app.infrastructure.sd35_client import (
    ImageGenerationError,
    ImageGenerationRequest,
    RateLimitExceededError,
    ZeroGPUQuotaExceededError,
    get_image_provider,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Visual Previews & Storyboard"])


class GeneratePreviewRequest(BaseModel):
    prompt: str | None = Field(default=None, description="Custom prompt override; if omitted, compiled automatically")
    negative_prompt: str = Field(
        default="blurry, distorted, oversaturated, deformed, bad anatomy, lowres, text, watermark",
        description="Negative prompt guidance",
    )
    steps: int | None = Field(default=None, ge=1, le=50, description="Inference steps (default 28)")
    seed: int = Field(default=0, ge=0, le=2147483647, description="Seed for deterministic preview")
    randomize_seed: bool = Field(default=True, description="Whether to randomize seed")
    aspect_ratio: str = Field(default="16:9", description="16:9 (1024x576) or 1:1 (1024x1024)")
    provider: str | None = Field(default=None, description="Provider: '9router', 'sd35_large_hf', 'mock', 'auto'")
    model: str | None = Field(default=None, description="Model/combo identifier (e.g. 'gemini-3.1-flash-image')")
    enable_fallback: bool = Field(default=True, description="Enable automated failover on rate limit / quota exhaustion")


@router.get("/previews/providers", status_code=status.HTTP_200_OK)
async def list_preview_providers(
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """List available image generation providers, active model combos, and rate limit policies."""
    settings = get_settings()
    return {
        "data": {
            "default_provider": settings.image_provider_default,
            "fallback_chain": settings.fallback_chain_list,
            "providers": [
                {
                    "id": "ag_gemini_flash",
                    "name": "Antigravity / AG/Gemini 3.8 Flash",
                    "status": "online",
                    "default_model": "ag/gemini-3.8-flash",
                    "endpoint": f"{settings.effective_ninerouter_base_url}/images/generations",
                    "features": ["flash_speed", "sub_second_latency", "photorealistic_fidelity"],
                },
                {
                    "id": "9router",
                    "name": "9Router API Gateway",
                    "status": "online",
                    "default_model": settings.ninerouter_default_model,
                    "combo_models": settings.ninerouter_combo_list,
                    "endpoint": f"{settings.effective_ninerouter_base_url}/images/generations",
                    "rate_limits": {
                        "strategy": "multi_account_pool_failover",
                        "default_rpm": 60,
                        "free_tier_limits": "15 RPM / 1,500 RPD per key",
                    },
                    "features": ["multi_model_combos", "automatic_backoff", "cas_deduplication"],
                },
                {
                    "id": "sd35_large_hf",
                    "name": "Stability AI SD 3.5 Large (Hugging Face Spaces)",
                    "status": "online",
                    "endpoint": settings.sd35_space_url,
                    "rate_limits": {
                        "strategy": "zerogpu_quota",
                        "free_tier_limits": "60-90s GPU duration per rolling window",
                    },
                    "features": ["8B_diffusion", "35mm_film_grain", "sse_progress_stream"],
                },
                {
                    "id": "google_flow",
                    "name": "Google Flow Studio (5 Akun PRO Pool)",
                    "status": "online",
                    "endpoint": "/api/flow/images/generate",
                    "features": ["google_flow_pro", "5_account_failover", "virtual_display"],
                },
                {
                    "id": "mock",
                    "name": "Local Previs Engine / Offline Contingency",
                    "status": "online",
                    "rate_limits": {"strategy": "unlimited", "rpm": "infinite"},
                    "features": ["zero_latency", "deterministic_svg_webp", "network_resilience"],
                },
            ],
        }
    }


def _resolve_preview_resolution(aspect_ratio: str) -> tuple[int, int]:
    """Resolve lightweight 360p draft preview resolution (multiples of 8/16).
    
    GUARDRAIL: Strictly used for rapid preview iteration. Final master
    renders and production packages preserve full 4K / UHD resolution.
    """
    ar = aspect_ratio.strip()
    if ar == "16:9":
        return 640, 360
    elif ar == "9:16":
        return 360, 640
    elif ar == "2.39:1":
        return 864, 360
    return 360, 360


# Alias for backwards compatibility
_resolve_resolution = _resolve_preview_resolution


@router.post("/scenes/{scene_id}/generate-preview", status_code=status.HTTP_200_OK)
@router.post("/previews/scenes/{scene_id}/generate-preview", status_code=status.HTTP_200_OK)
async def generate_scene_preview(
    scene_id: str,
    payload: GeneratePreviewRequest = GeneratePreviewRequest(),
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Generate high-fidelity cinematic keyframe preview for a Scene using SD 3.5 Large."""
    s_uuid = uuid.UUID(scene_id)
    scene_stmt = select(SceneModel).where(SceneModel.id == s_uuid)
    scene = (await session.execute(scene_stmt)).scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    # Fetch project style code if available
    proj_stmt = select(ProjectModel).where(ProjectModel.id == scene.project_id)
    project = (await session.execute(proj_stmt)).scalar_one_or_none()
    style_code = project.target_style_code if project else "#Style 01"

    settings = get_settings()
    effective_provider = (payload.provider or settings.image_provider_default).lower()

    # Build prompt if not overridden using LivePromptTranspiler
    prompt = payload.prompt
    if not prompt or not prompt.strip():
        transpile_res = LivePromptTranspiler.transpile(
            provider_target=effective_provider,
            style_code=style_code,
            action_description=f"{scene.slugline}, {scene.narrative_goal}",
            aspect_ratio=payload.aspect_ratio,
        )
        prompt = transpile_res["positive_prompt"]

    width, height = _resolve_resolution(payload.aspect_ratio)
    steps = payload.steps or settings.sd35_default_steps

    req = ImageGenerationRequest(
        prompt=prompt,
        negative_prompt=payload.negative_prompt,
        seed=payload.seed,
        randomize_seed=payload.randomize_seed,
        width=width,
        height=height,
        guidance_scale=4.5,
        num_inference_steps=steps,
        provider=payload.provider,
        model=payload.model,
        enable_fallback=payload.enable_fallback,
    )

    provider = get_image_provider()

    try:
        result = await provider.generate(req)
    except ZeroGPUQuotaExceededError as e:
        logger.warning("zerogpu_quota_exceeded", scene_id=scene_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"ZeroGPU Quota Hugging Face habis: {str(e)}. "
                "Silakan beralih ke provider 9Router atau masukkan HF_TOKEN PRO."
            ),
        )
    except RateLimitExceededError as e:
        logger.warning("rate_limit_exceeded", scene_id=scene_id, error=str(e), provider=e.provider, model=e.model)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Rate limit / kuota habis pada {e.provider} ({e.model or 'combo'}): {str(e)}. "
                "Coba model lain dalam combo atau aktifkan provider fallback."
            ),
        )
    except ImageGenerationError as e:
        logger.error("image_generation_failed", scene_id=scene_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gagal generate gambar via visual engine: {str(e)}",
        )
    except Exception as e:
        logger.error("image_generation_unexpected", scene_id=scene_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Terjadi kesalahan internal saat generate preview: {str(e)}",
        )

    # Save reference into first shot if present
    shots_stmt = select(ShotModel).where(ShotModel.scene_id == s_uuid).order_by(ShotModel.shot_number.asc())
    shots = (await session.execute(shots_stmt)).scalars().all()
    primary_shot = shots[0] if shots else None

    if primary_shot:
        current_layers = dict(primary_shot.fg_bg_layers or {})
        current_layers["preview_url"] = result.local_url
        current_layers["preview_seed"] = result.seed
        primary_shot.fg_bg_layers = current_layers
    else:
        primary_shot = ShotModel(
            id=uuid.uuid4(),
            scene_id=scene.id,
            shot_number=1,
            duration_seconds=scene.duration_target,
            camera_code="#Cam 01",
            lens_code="#Lens 01",
            comp_code="#Comp 01",
            light_code="#Light 01",
            act_code="#Act 01",
            speed_code="#Speed 01",
            fg_bg_layers={"preview_url": result.local_url, "preview_seed": result.seed},
            status="PLANNED",
            created_at=datetime.now(timezone.utc),
        )
        session.add(primary_shot)
        await session.flush()

    # Register in AssetModel (CAS deduplication)
    asset_stmt = select(AssetModel).where(AssetModel.sha256_checksum == result.sha256_checksum)
    asset = (await session.execute(asset_stmt)).scalar_one_or_none()
    if not asset:
        asset = AssetModel(
            project_id=scene.project_id,
            shot_id=primary_shot.id if primary_shot else None,
            asset_type="SCENE_PREVIEW",
            storage_key=result.local_path,
            sha256_checksum=result.sha256_checksum,
            file_size_bytes=result.file_size_bytes,
            mime_type=result.mime_type,
            duration_seconds=scene.duration_target,
        )
        session.add(asset)
    elif primary_shot and not asset.shot_id:
        asset.shot_id = primary_shot.id

    await session.commit()

    return {
        "data": {
            "scene_id": str(scene.id),
            "shot_id": str(primary_shot.id) if primary_shot else None,
            "preview_url": result.local_url,
            "seed": result.seed,
            "prompt": prompt,
            "width": result.width,
            "height": result.height,
            "steps": result.steps,
            "provider": result.provider,
            "model": result.model,
            "rate_limit_info": result.rate_limit_info,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    }


@router.post("/projects/{project_id}/generate-preview", status_code=status.HTTP_200_OK)
@router.post("/previews/projects/{project_id}/generate-preview", status_code=status.HTTP_200_OK)
async def generate_project_concept_preview(
    project_id: str,
    payload: GeneratePreviewRequest = GeneratePreviewRequest(),
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Generate rapid 360p cinematic concept preview for Stage 1 or project-level visualization."""
    try:
        p_uuid = uuid.UUID(project_id)
        stmt = select(ProjectModel).where(ProjectModel.id == p_uuid)
    except ValueError:
        stmt = select(ProjectModel).where(ProjectModel.slug == project_id)

    project = (await session.execute(stmt)).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    settings = get_settings()
    effective_provider = (payload.provider or settings.image_provider_default).lower()

    # Build prompt if not overridden
    prompt = payload.prompt
    if not prompt or not prompt.strip():
        transpile_res = LivePromptTranspiler.transpile(
            provider_target=effective_provider,
            style_code=project.target_style_code or "#Style 01",
            action_description=f"Opening concept keyframe still for {project.title}",
            aspect_ratio=payload.aspect_ratio,
            model=payload.model,
        )
        prompt = transpile_res["positive_prompt"]

    width, height = _resolve_preview_resolution(payload.aspect_ratio)
    steps = payload.steps or settings.sd35_default_steps

    req = ImageGenerationRequest(
        prompt=prompt,
        negative_prompt=payload.negative_prompt,
        seed=payload.seed,
        randomize_seed=payload.randomize_seed,
        width=width,
        height=height,
        guidance_scale=4.5,
        num_inference_steps=steps,
        provider=payload.provider,
        model=payload.model,
        enable_fallback=payload.enable_fallback,
    )

    provider = get_image_provider()
    try:
        result = await provider.generate(req)
    except Exception as exc:
        logger.error("project_preview_failed", project_id=str(project.id), error=str(exc))
        raise HTTPException(status_code=500, detail=f"Failed to generate concept preview: {str(exc)}")

    # Check if scene 1 exists to attach
    scenes_stmt = select(SceneModel).where(SceneModel.project_id == project.id).order_by(SceneModel.scene_number.asc())
    scenes = (await session.execute(scenes_stmt)).scalars().all()
    primary_scene = scenes[0] if scenes else None

    # Register in AssetModel (CAS deduplication)
    asset_stmt = select(AssetModel).where(AssetModel.sha256_checksum == result.sha256_checksum)
    asset = (await session.execute(asset_stmt)).scalar_one_or_none()
    if not asset:
        asset = AssetModel(
            project_id=project.id,
            shot_id=None,
            asset_type="SCENE_PREVIEW",
            storage_key=result.local_path,
            sha256_checksum=result.sha256_checksum,
            file_size_bytes=result.file_size_bytes,
            mime_type=result.mime_type,
            duration_seconds=5.0,
        )
        session.add(asset)

    # Persist preview in project.settings for studio reloads
    current_settings = dict(project.settings or {})
    current_settings["preview_url"] = result.local_url
    current_settings["preview_seed"] = result.seed
    current_settings["preview_provider"] = result.provider
    if result.model:
        current_settings["preview_model"] = result.model
    project.settings = current_settings
    flag_modified(project, "settings")

    await session.commit()

    return {
        "status": "success",
        "preview_url": result.local_url,
        "seed": result.seed,
        "width": result.width,
        "height": result.height,
        "steps": result.steps,
        "provider": result.provider,
        "model": result.model,
        "rate_limit_info": result.rate_limit_info,
        "data": {
            "project_id": str(project.id),
            "scene_id": str(primary_scene.id) if primary_scene else None,
            "preview_url": result.local_url,
            "seed": result.seed,
            "prompt": prompt,
            "width": result.width,
            "height": result.height,
            "steps": result.steps,
            "provider": result.provider,
            "model": result.model,
            "rate_limit_info": result.rate_limit_info,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    }


@router.post("/shots/{shot_id}/generate-preview", status_code=status.HTTP_200_OK)
@router.post("/previews/shots/{shot_id}/generate-preview", status_code=status.HTTP_200_OK)
async def generate_shot_preview(
    shot_id: str,
    payload: GeneratePreviewRequest = GeneratePreviewRequest(),
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Generate high-fidelity optical keyframe preview for a specific cinematographic Shot."""
    sh_uuid = uuid.UUID(shot_id)
    shot_stmt = select(ShotModel).where(ShotModel.id == sh_uuid)
    shot = (await session.execute(shot_stmt)).scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")

    scene_stmt = select(SceneModel).where(SceneModel.id == shot.scene_id)
    scene = (await session.execute(scene_stmt)).scalar_one_or_none()

    slugline = scene.slugline if scene else "EXT. SCENE - DAY"
    narrative_goal = scene.narrative_goal if scene else ""

    settings = get_settings()
    effective_provider = (payload.provider or settings.image_provider_default).lower()

    # Build prompt if not provided using LivePromptTranspiler
    prompt = payload.prompt
    if not prompt or not prompt.strip():
        transpile_res = LivePromptTranspiler.transpile(
            provider_target=effective_provider,
            camera_code=shot.camera_code or "#Cam 01",
            lens_code=shot.lens_code or "#Lens 01",
            comp_code=shot.comp_code or "#Comp 01",
            light_code=shot.light_code or "#Light 01",
            act_code=shot.act_code or "#Act 01",
            speed_code=shot.speed_code or "#Speed 01",
            action_description=f"{slugline}, {narrative_goal}",
            aspect_ratio=payload.aspect_ratio,
        )
        prompt = transpile_res["positive_prompt"]

    width, height = _resolve_resolution(payload.aspect_ratio)
    steps = payload.steps or settings.sd35_default_steps

    req = ImageGenerationRequest(
        prompt=prompt,
        negative_prompt=payload.negative_prompt,
        seed=payload.seed,
        randomize_seed=payload.randomize_seed,
        width=width,
        height=height,
        guidance_scale=4.5,
        num_inference_steps=steps,
        provider=payload.provider,
        model=payload.model,
        enable_fallback=payload.enable_fallback,
    )

    provider = get_image_provider()

    try:
        result = await provider.generate(req)
    except ZeroGPUQuotaExceededError as e:
        logger.warning("zerogpu_quota_exceeded", shot_id=shot_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"ZeroGPU Quota Hugging Face habis: {str(e)}. "
                "Silakan beralih ke provider 9Router atau masukkan HF_TOKEN PRO."
            ),
        )
    except RateLimitExceededError as e:
        logger.warning("rate_limit_exceeded", shot_id=shot_id, error=str(e), provider=e.provider, model=e.model)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Rate limit / kuota habis pada {e.provider} ({e.model or 'combo'}): {str(e)}. "
                "Coba model lain dalam combo atau aktifkan provider fallback."
            ),
        )
    except ImageGenerationError as e:
        logger.error("image_generation_failed", shot_id=shot_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gagal generate gambar via visual engine: {str(e)}",
        )
    except Exception as e:
        logger.error("image_generation_unexpected", shot_id=shot_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Terjadi kesalahan internal saat generate preview shot: {str(e)}",
        )

    # Update shot
    current_layers = dict(shot.fg_bg_layers or {})
    current_layers["preview_url"] = result.local_url
    current_layers["preview_seed"] = result.seed
    shot.fg_bg_layers = current_layers

    # Register in AssetModel (CAS deduplication)
    if scene:
        asset_stmt = select(AssetModel).where(AssetModel.sha256_checksum == result.sha256_checksum)
        asset = (await session.execute(asset_stmt)).scalar_one_or_none()
        if not asset:
            asset = AssetModel(
                project_id=scene.project_id,
                shot_id=shot.id,
                asset_type="SHOT_PREVIEW",
                storage_key=result.local_path,
                sha256_checksum=result.sha256_checksum,
                file_size_bytes=result.file_size_bytes,
                mime_type=result.mime_type,
                duration_seconds=shot.duration_seconds,
            )
            session.add(asset)
        elif not asset.shot_id:
            asset.shot_id = shot.id

    await session.commit()

    return {
        "data": {
            "shot_id": str(shot.id),
            "scene_id": str(shot.scene_id),
            "preview_url": result.local_url,
            "seed": result.seed,
            "prompt": prompt,
            "width": result.width,
            "height": result.height,
            "steps": result.steps,
            "provider": result.provider,
            "model": result.model,
            "rate_limit_info": result.rate_limit_info,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    }


@router.get("/assets/previews/{filename}", status_code=status.HTTP_200_OK)
@router.head("/assets/previews/{filename}", status_code=status.HTTP_200_OK)
async def get_preview_asset(filename: str):
    """Serve downloaded preview images safely."""
    # Defend against directory traversal
    clean_filename = Path(filename).name
    if clean_filename != filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    settings = get_settings()
    file_path = settings.effective_preview_storage_path / clean_filename

    if not file_path.is_file() or not file_path.exists():
        raise HTTPException(status_code=404, detail="Preview image not found")

    ext = file_path.suffix.lower()
    media_type = "image/webp"
    if ext == ".png":
        media_type = "image/png"
    elif ext in (".jpg", ".jpeg"):
        media_type = "image/jpeg"

    return FileResponse(file_path, media_type=media_type)
