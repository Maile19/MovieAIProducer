from datetime import datetime, timezone
import hashlib
import os
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
from backend.app.domain.screenwriter import PolyaScreenwriterEngine, sanitize_negative_prompts_for_style
from backend.app.domain.transpiler import LivePromptTranspiler
from backend.app.infrastructure.database.models.auth import UserModel
from backend.app.infrastructure.database.models.character import CharacterModel, CharacterStateModel
from backend.app.infrastructure.database.models.flow import FlowImageJobModel
from backend.app.infrastructure.database.models.pipeline import AssetModel
from backend.app.infrastructure.database.models.project import MasterProductionBibleModel, ProjectModel
from backend.app.infrastructure.database.models.story import SceneModel, ShotModel
from backend.app.infrastructure.reference_paths import validate_reference_image_paths
from backend.app.infrastructure.sd35_client import (
    ImageGenerationError,
    ImageGenerationRequest,
    RateLimitExceededError,
    ZeroGPUQuotaExceededError,
    get_image_provider,
)
from backend.app.api.v1.render_settings import (
    get_project_render_config,
    decrypt_key,
    resolve_effective_render_provider,
)
from backend.app.infrastructure.universal_image_adapter import (
    UniversalImageAdapter,
    UniversalImageRequest,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Visual Previews & Storyboard"])


def _resolve_effective_negative_prompt(
    payload_negative: str | None,
    transpiled_negative: str | None,
    style_code: str,
) -> str:
    """Merge engine negative prompt with caller guidance and strip style-contradicting bans."""
    seen: set[str] = set()
    merged_tokens: list[str] = []
    for source in (transpiled_negative, payload_negative):
        if not source or not isinstance(source, str):
            continue
        for tok in source.split(","):
            t = tok.strip()
            if not t:
                continue
            low = t.lower()
            if low not in seen:
                seen.add(low)
                merged_tokens.append(t)
    if not merged_tokens:
        return ""
    sanitized = sanitize_negative_prompts_for_style([", ".join(merged_tokens)], style_code)
    return sanitized[0] if sanitized else ""


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
                    "id": "gemini-direct",
                    "name": "Gemini API Direct (3.8 Flash & Imagen)",
                    "status": "online",
                    "endpoint": "https://generativelanguage.googleapis.com/v1beta",
                    "rate_limits": {
                        "strategy": "per_key_quota",
                        "free_tier_limits": "Google AI Studio API Keys",
                    },
                    "features": ["multimodal_inline", "imagen_4", "universal_adapter"],
                },
                {
                    "id": "sd35_large_hf",
                    "name": "Stability AI SD 3.5 Large (Legacy Space)",
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

    resolved_render = resolve_effective_render_provider(
        project_id=str(scene.project_id),
        requested_provider=payload.provider,
        requested_model=payload.model,
        ignored_override_values=("sd35_large_hf", "default", None),
        default_provider=settings.image_provider_default,
    )
    effective_provider = resolved_render["provider_id"]
    model_to_use = resolved_render["model_id"]
    base_url_to_use = resolved_render["base_url"]
    api_key_to_use = resolved_render["api_key"]
    use_universal_adapter = resolved_render["use_universal_adapter"]
    if not use_universal_adapter and effective_provider == "sd35_large_hf":
        effective_provider = "9router"

    # Load primary shot, bible, and cast character + act-mapped #State DNA before compiling prompt
    primary_shot_stmt = select(ShotModel).where(ShotModel.scene_id == scene.id).order_by(ShotModel.shot_number.asc())
    all_shots = (await session.execute(primary_shot_stmt)).scalars().all()
    primary_shot = all_shots[0] if all_shots else None

    char_stmt = select(CharacterModel).where(CharacterModel.project_id == scene.project_id).order_by(CharacterModel.created_at.asc())
    chars = list((await session.execute(char_stmt)).scalars().all())
    lead_char = None
    if chars:
        goal_low = (scene.narrative_goal or "").lower()
        lead_char = next((c for c in chars if c.name and c.name.lower() in goal_low), chars[0])

    lead_state = None
    if lead_char:
        st_rows = list(
            (
                await session.execute(
                    select(CharacterStateModel)
                    .where(CharacterStateModel.character_id == lead_char.id)
                    .order_by(CharacterStateModel.state_code.asc())
                )
            ).scalars().all()
        )
        if st_rows:
            t_num = PolyaScreenwriterEngine._resolve_act_to_state_number(scene.act_number, 4) or 1
            t_code = f"#State 0{t_num}"
            lead_state = next((s for s in st_rows if (s.state_code or "").upper() == t_code.upper()), st_rows[0])

    bible = (
        await session.execute(
            select(MasterProductionBibleModel)
            .where(MasterProductionBibleModel.project_id == scene.project_id)
            .order_by(MasterProductionBibleModel.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    bible_styles = bible.style_parameters if (bible and isinstance(bible.style_parameters, dict)) else {}
    style_code = bible_styles.get("master_style_code") or style_code

    # Build prompt if not overridden using LivePromptTranspiler + full Character/State DNA
    prompt = payload.prompt
    transpiled_negative: str | None = None
    if not prompt or not prompt.strip():
        proj_settings = project.settings if (project and isinstance(project.settings, dict)) else {}
        proj_genre = proj_settings.get("genre") or proj_settings.get("genre_tone")
        shot_layers = primary_shot.fg_bg_layers if (primary_shot and isinstance(primary_shot.fg_bg_layers, dict)) else {}
        transpile_res = await LivePromptTranspiler.transpile_with_rag(
            provider_target=effective_provider,
            style_code=style_code,
            camera_code=primary_shot.camera_code if primary_shot else "#Cam 01",
            lens_code=primary_shot.lens_code if primary_shot else "#Lens 01",
            comp_code=primary_shot.comp_code if primary_shot else "#Comp 01",
            light_code=primary_shot.light_code if primary_shot else "#Light 01",
            act_code=primary_shot.act_code if primary_shot else "#Act 01",
            speed_code=primary_shot.speed_code if primary_shot else "#Speed 01",
            character_dna=lead_char.base_prompt if lead_char else "",
            character_name=lead_char.name if lead_char else "",
            state_code=lead_state.state_code if lead_state else "#State 01",
            wardrobe=lead_state.wardrobe if lead_state else "",
            physical_damage=lead_state.injuries_and_wear if lead_state else "",
            emotional_anchor=lead_state.expression_anchor if lead_state else "",
            slugline=scene.slugline,
            narrative_goal=scene.narrative_goal,
            action_description=str(shot_layers.get("prompt_override") or "").strip() or f"{scene.slugline}, {scene.narrative_goal}",
            dialogue=primary_shot.dialogue if primary_shot else None,
            transition_type=primary_shot.transition_type if primary_shot else "NONE",
            audio_lead_seconds=shot_layers.get("audio_lead_seconds"),
            aspect_ratio=payload.aspect_ratio,
            genre=proj_genre,
            act_number=scene.act_number,
        )
        prompt = transpile_res["positive_prompt"]
        transpiled_negative = transpile_res.get("negative_prompt")
    else:
        transpiled_negative = LivePromptTranspiler.transpile(
            provider_target=effective_provider,
            style_code=style_code,
            model=payload.model,
        ).get("negative_prompt")

    effective_negative = _resolve_effective_negative_prompt(
        payload.negative_prompt,
        transpiled_negative,
        style_code,
    )

    width, height = _resolve_resolution(payload.aspect_ratio)
    steps = payload.steps or settings.sd35_default_steps

    # Validate reference image paths strictly in canonical order for Scene: [background_path, char_face_path, char_front_path]
    bg_cand = (
        primary_shot.fg_bg_layers.get("custom_background") or primary_shot.fg_bg_layers.get("preview_url")
        if (primary_shot and isinstance(primary_shot.fg_bg_layers, dict))
        else None
    )

    face_cand = lead_char.closeup_image_url if lead_char else None
    front_cand = lead_char.front_image_url if lead_char else None

    validated_refs = validate_reference_image_paths(
        background_path=bg_cand,
        char_face_path=face_cand,
        char_front_path=front_cand,
    )

    if effective_provider in ("google_flow", "google-flow"):
        flow_job = FlowImageJobModel(
            id=uuid.uuid4(),
            project_id=scene.project_id,
            scene_id=scene.id,
            shot_id=primary_shot.id if primary_shot else None,
            prompt=prompt,
            aspect_ratio=payload.aspect_ratio or "16:9",
            reference_image_paths=validated_refs if validated_refs else None,
            status="queued",
            retry_count=0,
            max_retries=3,
            created_at=datetime.now(timezone.utc),
        )
        session.add(flow_job)
        await session.commit()
        await session.refresh(flow_job)
        return {
            "status": "queued",
            "job_id": str(flow_job.id),
            "provider": "google_flow",
            "reference_image_paths": validated_refs,
            "message": "Scene preview generation job placed in Google Flow queue",
            "data": {
                "scene_id": str(scene.id),
                "job_id": str(flow_job.id),
                "provider": "google_flow",
                "prompt": prompt,
                "reference_image_paths": validated_refs,
                "status": "queued",
            },
        }

    if use_universal_adapter:
        adapter = UniversalImageAdapter()
        req = UniversalImageRequest(
            provider_id=effective_provider,
            model_id=model_to_use,
            prompt=prompt,
            negative_prompt=effective_negative,
            aspect_ratio=payload.aspect_ratio,
            width=width,
            height=height,
            seed=payload.seed,
            reference_image_paths=validated_refs,
            base_url_override=base_url_to_use,
            api_key_override=api_key_to_use,
            enable_fallback=payload.enable_fallback if payload.enable_fallback is not None else True,
        )
        try:
            result = await adapter.generate_image(req)
        except Exception as exc:
            logger.error("scene_preview_failed", scene_id=scene_id, provider=effective_provider, error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Preview generation failed via {effective_provider}: {str(exc)}",
            )
        res_url = result.local_url
        res_path = result.local_path
        res_seed = result.seed
        res_provider = result.provider_id
        res_model = result.model_id
        res_rate_limit = None
        res_mime = result.mime_type
        res_created_at = result.created_at
    else:
        req = ImageGenerationRequest(
            prompt=prompt,
            negative_prompt=effective_negative,
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
                detail=f"Terjadi kesalahan internal saat generate preview scene: {str(e)}",
            )
        res_url = result.local_url
        res_path = result.local_path
        res_seed = result.seed
        res_provider = result.provider
        res_model = result.model
        res_rate_limit = result.rate_limit_info
        res_mime = result.mime_type
        res_created_at = datetime.now(timezone.utc).isoformat()

    # Save reference into first shot if present
    shots_stmt = select(ShotModel).where(ShotModel.scene_id == s_uuid).order_by(ShotModel.shot_number.asc())
    shots = (await session.execute(shots_stmt)).scalars().all()
    primary_shot = shots[0] if shots else None

    if primary_shot:
        current_layers = dict(primary_shot.fg_bg_layers or {})
        current_layers["preview_url"] = res_url
        current_layers["preview_seed"] = res_seed
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
            fg_bg_layers={"preview_url": res_url, "preview_seed": res_seed},
            status="PLANNED",
            created_at=datetime.now(timezone.utc),
        )
        session.add(primary_shot)
        await session.flush()

    local_p = Path(res_path)
    sha_ck = hashlib.sha256(local_p.read_bytes()).hexdigest() if local_p.exists() else uuid.uuid4().hex
    file_sz = local_p.stat().st_size if local_p.exists() else 0

    # Register in AssetModel (CAS deduplication)
    asset_stmt = select(AssetModel).where(AssetModel.sha256_checksum == sha_ck)
    asset = (await session.execute(asset_stmt)).scalar_one_or_none()
    if not asset:
        asset = AssetModel(
            project_id=scene.project_id,
            shot_id=primary_shot.id if primary_shot else None,
            asset_type="SCENE_PREVIEW",
            storage_key=res_path,
            sha256_checksum=sha_ck,
            file_size_bytes=file_sz,
            mime_type=res_mime,
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
            "preview_url": res_url,
            "seed": res_seed,
            "prompt": prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "provider": res_provider,
            "model": res_model,
            "rate_limit_info": res_rate_limit,
            "created_at": res_created_at,
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

    resolved_render = resolve_effective_render_provider(
        project_id=str(project.id),
        requested_provider=payload.provider,
        requested_model=payload.model,
        ignored_override_values=("sd35_large_hf", "default", None),
        default_provider=settings.image_provider_default,
    )
    effective_provider = resolved_render["provider_id"]
    model_to_use = resolved_render["model_id"]
    base_url_to_use = resolved_render["base_url"]
    api_key_to_use = resolved_render["api_key"]
    use_universal_adapter = resolved_render["use_universal_adapter"]
    if not use_universal_adapter and effective_provider == "sd35_large_hf":
        effective_provider = "9router"

    # Build prompt if not overridden
    prompt = payload.prompt
    concept_style_code = project.target_style_code or "#Style 01"
    transpiled_negative: str | None = None
    if not prompt or not prompt.strip():
        proj_settings = project.settings if isinstance(project.settings, dict) else {}
        proj_genre = proj_settings.get("genre") or proj_settings.get("genre_tone")
        transpile_res = await LivePromptTranspiler.transpile_with_rag(
            provider_target=effective_provider,
            style_code=concept_style_code,
            action_description=f"Opening concept keyframe still for {project.title}",
            aspect_ratio=payload.aspect_ratio,
            model=payload.model,
            genre=proj_genre,
        )
        prompt = transpile_res["positive_prompt"]
        transpiled_negative = transpile_res.get("negative_prompt")
    else:
        transpiled_negative = LivePromptTranspiler.transpile(
            provider_target=effective_provider,
            style_code=concept_style_code,
            model=payload.model,
        ).get("negative_prompt")

    effective_negative = _resolve_effective_negative_prompt(
        payload.negative_prompt,
        transpiled_negative,
        concept_style_code,
    )

    width, height = _resolve_preview_resolution(payload.aspect_ratio)
    steps = payload.steps or settings.sd35_default_steps

    if use_universal_adapter:
        adapter = UniversalImageAdapter()
        req = UniversalImageRequest(
            provider_id=effective_provider,
            model_id=model_to_use,
            prompt=prompt,
            negative_prompt=effective_negative,
            aspect_ratio=payload.aspect_ratio,
            width=width,
            height=height,
            seed=payload.seed,
            base_url_override=base_url_to_use,
            api_key_override=api_key_to_use,
            enable_fallback=payload.enable_fallback if payload.enable_fallback is not None else True,
        )
        try:
            result = await adapter.generate_image(req)
        except Exception as exc:
            logger.error("project_preview_failed", project_id=str(project.id), error=str(exc))
            raise HTTPException(status_code=500, detail=f"Failed to generate concept preview: {str(exc)}")
        res_url = result.local_url
        res_path = result.local_path
        res_seed = result.seed
        res_provider = result.provider_id
        res_model = result.model_id
        res_mime = result.mime_type
    else:
        req = ImageGenerationRequest(
            prompt=prompt,
            negative_prompt=effective_negative,
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
        res_url = result.local_url
        res_path = result.local_path
        res_seed = result.seed
        res_provider = result.provider
        res_model = result.model
        res_mime = result.mime_type

    # Check if scene 1 exists to attach
    scenes_stmt = select(SceneModel).where(SceneModel.project_id == project.id).order_by(SceneModel.scene_number.asc())
    scenes = (await session.execute(scenes_stmt)).scalars().all()
    primary_scene = scenes[0] if scenes else None

    local_p = Path(res_path)
    sha_ck = hashlib.sha256(local_p.read_bytes()).hexdigest() if local_p.exists() else uuid.uuid4().hex
    file_sz = local_p.stat().st_size if local_p.exists() else 0

    # Register in AssetModel (CAS deduplication)
    asset_stmt = select(AssetModel).where(AssetModel.sha256_checksum == sha_ck)
    asset = (await session.execute(asset_stmt)).scalar_one_or_none()
    if not asset:
        asset = AssetModel(
            project_id=project.id,
            shot_id=None,
            asset_type="SCENE_PREVIEW",
            storage_key=res_path,
            sha256_checksum=sha_ck,
            file_size_bytes=file_sz,
            mime_type=res_mime,
            duration_seconds=5.0,
        )
        session.add(asset)

    # Persist preview in project.settings for studio reloads
    current_settings = dict(project.settings or {})
    current_settings["preview_url"] = res_url
    current_settings["preview_seed"] = res_seed
    current_settings["preview_provider"] = res_provider
    if res_model:
        current_settings["preview_model"] = res_model
    project.settings = current_settings
    flag_modified(project, "settings")

    await session.commit()

    return {
        "status": "success",
        "preview_url": res_url,
        "seed": res_seed,
        "width": width,
        "height": height,
        "steps": steps,
        "provider": res_provider,
        "model": res_model,
        "rate_limit_info": None,
        "data": {
            "project_id": str(project.id),
            "scene_id": str(primary_scene.id) if primary_scene else None,
            "preview_url": res_url,
            "seed": res_seed,
            "prompt": prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "provider": res_provider,
            "model": res_model,
            "rate_limit_info": None,
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

    resolved_render = resolve_effective_render_provider(
        project_id=str(scene.project_id) if scene else None,
        requested_provider=payload.provider,
        requested_model=payload.model,
        ignored_override_values=("sd35_large_hf", "default", None),
        default_provider=settings.image_provider_default,
    )
    effective_provider = resolved_render["provider_id"]
    model_to_use = resolved_render["model_id"]
    base_url_to_use = resolved_render["base_url"]
    api_key_to_use = resolved_render["api_key"]
    use_universal_adapter = resolved_render["use_universal_adapter"]
    if not use_universal_adapter and effective_provider == "sd35_large_hf":
        effective_provider = "9router"

    # Load Character + act-mapped #State DNA before compiling shot prompt
    lead_char = None
    lead_state = None
    if scene:
        char_stmt = select(CharacterModel).where(CharacterModel.project_id == scene.project_id).order_by(CharacterModel.created_at.asc())
        chars = list((await session.execute(char_stmt)).scalars().all())
        if chars:
            goal_low = (narrative_goal or "").lower()
            lead_char = next((c for c in chars if c.name and c.name.lower() in goal_low), chars[0])
            st_rows = list(
                (
                    await session.execute(
                        select(CharacterStateModel)
                        .where(CharacterStateModel.character_id == lead_char.id)
                        .order_by(CharacterStateModel.state_code.asc())
                    )
                ).scalars().all()
            )
            if st_rows:
                t_num = PolyaScreenwriterEngine._resolve_act_to_state_number(scene.act_number, 4) or 1
                t_code = f"#State 0{t_num}"
                lead_state = next((s for s in st_rows if (s.state_code or "").upper() == t_code.upper()), st_rows[0])

    # Resolve active project/bible style for both positive transpilation and style-safe negative guidance
    project = None
    bible = None
    if scene:
        proj_stmt = select(ProjectModel).where(ProjectModel.id == scene.project_id)
        project = (await session.execute(proj_stmt)).scalar_one_or_none()
        bible = (
            await session.execute(
                select(MasterProductionBibleModel)
                .where(MasterProductionBibleModel.project_id == scene.project_id)
                .order_by(MasterProductionBibleModel.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    bible_styles = bible.style_parameters if (bible and isinstance(bible.style_parameters, dict)) else {}
    shot_style_code = bible_styles.get("master_style_code") or (project.target_style_code if project else None) or "#Style 01"

    # Build prompt if not provided using LivePromptTranspiler + full Character/State DNA
    prompt = payload.prompt
    transpiled_negative: str | None = None
    if not prompt or not prompt.strip():
        proj_settings = project.settings if (project and isinstance(project.settings, dict)) else {}
        proj_genre = proj_settings.get("genre") or proj_settings.get("genre_tone")
        shot_layers_in = shot.fg_bg_layers if isinstance(shot.fg_bg_layers, dict) else {}
        transpile_res = await LivePromptTranspiler.transpile_with_rag(
            provider_target=effective_provider,
            style_code=shot_style_code,
            camera_code=shot.camera_code or "#Cam 01",
            lens_code=shot.lens_code or "#Lens 01",
            comp_code=shot.comp_code or "#Comp 01",
            light_code=shot.light_code or "#Light 01",
            act_code=shot.act_code or "#Act 01",
            speed_code=shot.speed_code or "#Speed 01",
            character_dna=lead_char.base_prompt if lead_char else "",
            character_name=lead_char.name if lead_char else "",
            state_code=lead_state.state_code if lead_state else "#State 01",
            wardrobe=lead_state.wardrobe if lead_state else "",
            physical_damage=lead_state.injuries_and_wear if lead_state else "",
            emotional_anchor=lead_state.expression_anchor if lead_state else "",
            slugline=slugline,
            narrative_goal=narrative_goal,
            action_description=str(shot_layers_in.get("prompt_override") or "").strip() or f"{slugline}, {narrative_goal}",
            dialogue=shot.dialogue,
            transition_type=shot.transition_type or "NONE",
            audio_lead_seconds=shot_layers_in.get("audio_lead_seconds"),
            aspect_ratio=payload.aspect_ratio,
            genre=proj_genre,
            act_number=scene.act_number if scene else None,
        )
        prompt = transpile_res["positive_prompt"]
        transpiled_negative = transpile_res.get("negative_prompt")
    else:
        transpiled_negative = LivePromptTranspiler.transpile(
            provider_target=effective_provider,
            style_code=shot_style_code,
            model=payload.model,
        ).get("negative_prompt")

    effective_negative = _resolve_effective_negative_prompt(
        payload.negative_prompt,
        transpiled_negative,
        shot_style_code,
    )

    width, height = _resolve_resolution(payload.aspect_ratio)
    steps = payload.steps or settings.sd35_default_steps

    # Validate reference image paths strictly in canonical order for Shot: [background_path, char_face_path, char_front_path]
    shot_layers = dict(shot.fg_bg_layers or {}) if isinstance(shot.fg_bg_layers, dict) else {}
    custom_bg = shot_layers.get("custom_background")

    primary_shot_stmt = select(ShotModel).where(ShotModel.scene_id == shot.scene_id).order_by(ShotModel.shot_number.asc())
    all_shots = (await session.execute(primary_shot_stmt)).scalars().all()
    primary_shot = all_shots[0] if all_shots else None
    scene_bg = (
        primary_shot.fg_bg_layers.get("preview_url")
        if (primary_shot and isinstance(primary_shot.fg_bg_layers, dict))
        else None
    )

    bg_cand = custom_bg or scene_bg

    face_cand = lead_char.closeup_image_url if lead_char else None
    front_cand = lead_char.front_image_url if lead_char else None

    validated_refs = validate_reference_image_paths(
        background_path=bg_cand,
        char_face_path=face_cand,
        char_front_path=front_cand,
    )

    if effective_provider in ("google_flow", "google-flow"):
        flow_job = FlowImageJobModel(
            id=uuid.uuid4(),
            project_id=scene.project_id if scene else None,
            scene_id=scene.id if scene else None,
            shot_id=shot.id,
            prompt=prompt,
            aspect_ratio=payload.aspect_ratio or "16:9",
            reference_image_paths=validated_refs if validated_refs else None,
            status="queued",
            retry_count=0,
            max_retries=3,
            created_at=datetime.now(timezone.utc),
        )
        session.add(flow_job)
        await session.commit()
        await session.refresh(flow_job)
        return {
            "status": "queued",
            "job_id": str(flow_job.id),
            "provider": "google_flow",
            "reference_image_paths": validated_refs,
            "message": "Shot visual keyframe generation job placed in Google Flow queue",
            "data": {
                "shot_id": str(shot.id),
                "scene_id": str(shot.scene_id),
                "job_id": str(flow_job.id),
                "provider": "google_flow",
                "prompt": prompt,
                "reference_image_paths": validated_refs,
                "status": "queued",
            },
        }

    if use_universal_adapter:
        adapter = UniversalImageAdapter()
        req = UniversalImageRequest(
            provider_id=effective_provider,
            model_id=model_to_use,
            prompt=prompt,
            negative_prompt=effective_negative,
            aspect_ratio=payload.aspect_ratio,
            width=width,
            height=height,
            seed=payload.seed,
            reference_image_paths=validated_refs,
            base_url_override=base_url_to_use,
            api_key_override=api_key_to_use,
            enable_fallback=payload.enable_fallback if payload.enable_fallback is not None else True,
        )
        try:
            result = await adapter.generate_image(req)
        except Exception as exc:
            logger.error("shot_preview_failed", shot_id=shot_id, provider=effective_provider, error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Preview generation failed via {effective_provider}: {str(exc)}",
            )
        res_url = result.local_url
        res_path = result.local_path
        res_seed = result.seed
        res_provider = result.provider_id
        res_model = result.model_id
        res_rate_limit = None
        res_mime = result.mime_type
        res_created_at = result.created_at
    else:
        req = ImageGenerationRequest(
            prompt=prompt,
            negative_prompt=effective_negative,
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
        res_url = result.local_url
        res_path = result.local_path
        res_seed = result.seed
        res_provider = result.provider
        res_model = result.model
        res_rate_limit = result.rate_limit_info
        res_mime = result.mime_type
        res_created_at = datetime.now(timezone.utc).isoformat()

    # Update shot
    current_layers = dict(shot.fg_bg_layers or {})
    current_layers["preview_url"] = res_url
    current_layers["preview_seed"] = res_seed
    shot.fg_bg_layers = current_layers

    # Register in AssetModel (CAS deduplication)
    if scene:
        local_p = Path(res_path)
        sha_ck = hashlib.sha256(local_p.read_bytes()).hexdigest() if local_p.exists() else uuid.uuid4().hex
        file_sz = local_p.stat().st_size if local_p.exists() else 0

        asset_stmt = select(AssetModel).where(AssetModel.sha256_checksum == sha_ck)
        asset = (await session.execute(asset_stmt)).scalar_one_or_none()
        if not asset:
            asset = AssetModel(
                project_id=scene.project_id,
                shot_id=shot.id,
                asset_type="SHOT_PREVIEW",
                storage_key=res_path,
                sha256_checksum=sha_ck,
                file_size_bytes=file_sz,
                mime_type=res_mime,
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
            "preview_url": res_url,
            "seed": res_seed,
            "prompt": prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "provider": res_provider,
            "model": res_model,
            "rate_limit_info": res_rate_limit,
            "created_at": res_created_at,
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
