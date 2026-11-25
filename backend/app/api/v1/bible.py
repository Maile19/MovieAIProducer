from datetime import datetime, timezone
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import re
import shutil
import time
from typing import Any, Literal
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
import httpx
from PIL import Image, ImageOps
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass

from backend.app.api.deps import get_current_user, get_session
from backend.app.core.config import get_settings
from backend.app.domain.catalog import STYLE_CATALOG
from backend.app.infrastructure.database.models.auth import UserModel
from backend.app.infrastructure.database.models.character import (
    CharacterModel,
    CharacterStateModel,
)
from backend.app.domain.screenwriter import (
    PolyaScreenwriterEngine,
    ProjectNarrativeContext,
    extract_project_narrative_context,
    generate_unique_deterministic_seed,
)
from backend.app.core.proxy_health import DEFAULT_SOCKS5_URL, check_socks5_health, get_cached_socks5_health
from backend.app.infrastructure.database.models.flow import FlowImageJobModel, FlowSettingModel
from backend.app.infrastructure.database.models.project import (
    MasterProductionBibleModel,
    ProjectModel,
)
from backend.app.infrastructure.database.models.story import SceneModel
from backend.app.infrastructure.sd35_client import (
    ImageGenerationRequest,
    ImageGenerationError,
    RateLimitExceededError,
    get_image_provider,
)
from backend.app.api.v1.render_settings import get_project_render_config, decrypt_key
from backend.app.infrastructure.universal_image_adapter import (
    UniversalImageAdapter,
    UniversalImageRequest,
)

router = APIRouter(tags=["Master Production Bible"])


logger = logging.getLogger(__name__)


async def _assert_socks5_healthy_for_flow(session: AsyncSession) -> None:
    """Pre-flight check: Verifies Android SOCKS5 proxy handshake before accepting Google Flow jobs."""
    stmt = select(FlowSettingModel).where(FlowSettingModel.key == "socks5_proxy")
    res = await session.execute(stmt)
    setting = res.scalar_one_or_none()
    proxy_url = setting.value if setting and setting.value else DEFAULT_SOCKS5_URL
    health = get_cached_socks5_health(proxy_url, ttl_seconds=3.0)
    if not health["healthy"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error_code": "SOCKS5_PROXY_OFFLINE",
                "message": f"Proxy SOCKS5 Android ({health['proxy_url']}) sedang offline. Pastikan aplikasi SOCKS5 / reverse tunnel di HP Android sudah aktif.",
                "proxy_detail": health["detail"],
            },
        )


class BibleUpdateRequest(BaseModel):
    style_parameters: dict[str, Any] | None = None
    world_rules: dict[str, Any] | None = None


class BibleLockRequest(BaseModel):
    approval_notes: str = Field(default="Showrunner DNA freeze approval", description="Lock justification")
    confirm_dna_freeze: bool = Field(default=True, description="Explicit confirmation of DNA immutability")


class WorldPropsGenerateRequest(BaseModel):
    additional_notes: str | None = Field(default=None, description="Optional extra directives for Polya AI Screenwriter")


class RulesInvariantsGenerateRequest(BaseModel):
    additional_notes: str | None = Field(default=None, description="Optional extra directives for Polya AI Director")


class CharacterGenerateCastRequest(BaseModel):
    replace_existing: bool = Field(default=True, description="Whether to replace existing characters")
    preferred_count: int | None = Field(default=None, ge=5, le=8, description="Preferred cast count between 5 and 8")
    additional_notes: str | None = Field(default=None, description="Optional extra directives for Polya AI Screenwriter")


class CharacterGenerateOneRequest(BaseModel):
    preferred_role: str | None = Field(default=None, description="Optional preferred role (e.g. DEUTERAGONIST, MENTOR)")
    custom_directive: str | None = Field(default=None, description="Optional custom directive for Polya AI")


class CharacterRegenerateRequest(BaseModel):
    preserve_role: bool = Field(default=True, description="Whether to preserve the character's existing role")
    custom_directive: str | None = Field(default=None, description="Optional custom directive for Polya AI")


class CharacterUpdateRequest(BaseModel):
    name: str | None = None
    role: str | None = None
    base_prompt: str | None = None
    voice_dna_profile: str | None = None
    narrative_summary: str | None = None
    dna_seed: int | None = None


class CharacterCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    role: str = Field(default="PROTAGONIST", description="PROTAGONIST, ANTAGONIST, DEUTERAGONIST, MENTOR, EXTRAS")
    base_prompt: str = Field(description="Base visual and physical prompt description")
    narrative_summary: str | None = None
    voice_dna_profile: str | None = None
    face_ref_asset_id: str | None = None
    voice_ref_asset_id: str | None = None
    dna_seed: int | None = None
    preview_token: str | None = None
    closeup_image_url: str | None = None


class CharacterAutoGenerateDraft(BaseModel):
    name: str | None = None
    role: str | None = None
    role_suggestion: str | None = None
    archetype_and_bio: str | None = None
    voice_dna_profile: str | None = None
    base_visual_prompt: str | None = None
    dna_seed: int | None = None


class CharacterAutoGenerateRequest(BaseModel):
    llm_provider: str = Field(default="9router", description="Direct LLM API provider: '9router', 'gemini', 'agy'")
    mode: str = Field(default="all", description="'all', 'name', 'suggestion', or 'visual_prompt'")
    current_draft: CharacterAutoGenerateDraft = Field(default_factory=CharacterAutoGenerateDraft)


class CharacterPreviewRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    role: str = Field(default="PROTAGONIST")
    base_visual_prompt: str = Field(description="Base visual prompt")
    dna_seed: int | None = Field(default=None)
    image_provider: str = Field(default="ag_gemini_flash", description="Image provider: 'ag_gemini_flash', 'google_flow', '9router', 'sd35_large_hf', 'mock'")
    model: str | None = None
    target: str = Field(default="closeup", description="'closeup', 'expression', 'front', 'both', or 'all'")
    aspect_ratio: str | None = Field(default=None, description="Aspect ratio override, e.g. '3:4', '16:9', '1:1'")
    preview_token: str | None = None


class CharacterPreviewAttachRequest(BaseModel):
    preview_token: str
    job_id: str
    slot: str = Field(description="'closeup', 'expression', or 'front'")


class CharacterStateCreateRequest(BaseModel):
    scene_id: str | None = None
    state_code: str = Field(default="#State 01", description="#State 01 to #State 05")
    state_label: str | None = None
    wardrobe: str = Field(description="Costume and attire description")
    injuries_and_wear: str = Field(default="", description="Persistent physical damage, dirt, blood")
    expression_anchor: str = Field(default="", description="Default emotional anchor")


class CharacterStateUpdateRequest(BaseModel):
    scene_id: str | None = None
    state_code: str | None = None
    state_label: str | None = None
    wardrobe: str | None = None
    injuries_and_wear: str | None = None
    expression_anchor: str | None = None


class StateSuggestionRequest(BaseModel):
    state_code: str = Field(..., pattern=r"^#State 0[1-5]$", description="State code #State 01-05")
    target_field: Literal["all", "wardrobe", "injuries", "expression", "injuries_and_wear", "expression_anchor"] = "all"
    current_values: dict[str, str] = Field(default_factory=dict)
    previous_value: str | None = None
    is_regeneration: bool = False
    llm_provider: str | None = "9router"


class StateSuggestionData(BaseModel):
    state_code: str
    target_field: str
    wardrobe: str | None = None
    injuries_and_wear: str | None = None
    expression_anchor: str | None = None


class StateSuggestionResponse(BaseModel):
    status: str = "success"
    data: StateSuggestionData


def _clean_state_text(val: str | None) -> str | None:
    if not val:
        return val
    s = str(val).strip().strip('"').strip("'")
    prefixes = [
        r"^wardrobe\s*:\s*",
        r"^costume\s*:\s*",
        r"^attire\s*:\s*",
        r"^injuries\s*(?:&|and)?\s*(?:wear|physical damage)?\s*:\s*",
        r"^physical damage\s*:\s*",
        r"^expression\s*(?:anchor)?\s*:\s*",
        r"^emotional anchor\s*:\s*",
    ]
    for p in prefixes:
        s = re.sub(p, "", s, flags=re.IGNORECASE).strip()
    return " ".join(s.split())


def _procedural_state_generator(
    character_name: str,
    base_visual_prompt: str,
    state_code: str,
    target_field: str = "all",
    previous_value: str | None = None,
    current_values: dict[str, str] | None = None,
    is_regeneration: bool = False,
) -> dict[str, str | None]:
    """Procedural context-aware fallback generator when LLM is unavailable or for instant fallback."""
    base_lower = (base_visual_prompt or "").lower()
    costume_ref = "signature tailored attire"
    if "overcoat" in base_lower:
        costume_ref = "tactical charcoal overcoat and structured underlayer"
    elif "suit" in base_lower or "eva" in base_lower:
        costume_ref = "tailored technical suit with modular seams"
    elif "jacket" in base_lower:
        costume_ref = "tactical jacket over performance base layer"
    elif "trenchcoat" in base_lower:
        costume_ref = "dark tailored trenchcoat"

    presets = {
        "#State 01": {
            "wardrobe": [
                f"Pristine, immaculate {costume_ref}, sharply pressed with zero defects or wrinkles, collars securely fastened.",
                f"Impeccably maintained {costume_ref}, pristine textile weave catching light evenly with crisp architectural lines.",
            ],
            "injuries": [
                "Zero fresh wounds or defects; skin texture remains clean and well-groomed, natural biological baseline.",
                "Pristine biometric baseline, unblemished complexion with clear skin pores and groomed facial features.",
            ],
            "expression": [
                "Vigilant, disciplined ocular focus with a calm, calculating composure.",
                "Quiet intellectual intensity, unflinching gaze projecting seasoned composure and sharp focus.",
            ],
        },
        "#State 02": {
            "wardrobe": [
                f"{costume_ref.capitalize()} exhibiting minor wear, fine atmospheric dust clinging to fabric folds, and loosened collar fastener.",
                f"Slight creasing along the sleeves and dusty hems of the {costume_ref}, unbuttoned upper layer revealing undergarment.",
            ],
            "injuries": [
                "Faint perspiration sheen across forehead with subtle construction dust settling along the jawline.",
                "Minor superficial abrasion near the cheekbone, faint smudges of grime, and mild signs of physical fatigue.",
            ],
            "expression": [
                "Fatigued yet vigilant gaze, subtle eyelid strain indicating mounting cognitive pressure.",
                "Guarded ocular scanning, slightly narrowed eyes carrying the weight of early exhaustion.",
            ],
        },
        "#State 03": {
            "wardrobe": [
                f"Jagged tear along the left shoulder seam of the {costume_ref}, frayed synthetic fibers exposing protective lining.",
                f"Significant fabric scuffs, singed lapels, and torn hem threads across the {costume_ref} from acute kinetic impacts.",
            ],
            "injuries": [
                "Streak of dark coagulated blood tracing from the temple down the cheek, surrounded by mottled bruising.",
                "Noticeable lacerations across the knuckles, inflamed singe marks on collarbone, and swollen contusion near the brow.",
            ],
            "expression": [
                "Adrenaline-charged intensity, bloodshot eyes and clenched jaw radiating fierce defiance.",
                "Piercing, hyper-focused glare through pain, tight facial muscles set in survival desperation.",
            ],
        },
        "#State 04": {
            "wardrobe": [
                f"Heavily shredded and disheveled {costume_ref}, unfastened closures hanging loose, soiled with dark stains.",
                f"Soot-caked, partially unraveled {costume_ref} with torn structural seams and bloodstained interior lining.",
            ],
            "injuries": [
                "Prominent facial contusions, smeared grime mixed with dried blood across temples, faint muscular tremors.",
                "Severe bruising around the ocular socket, dried arterial spray on neck, and cracked, parched lips.",
            ],
            "expression": [
                "Hollow, haunted stare bearing deep psychological trauma, pupils dilated in acute sensory shock.",
                "Fractured, vacant gaze transitioning into visceral despair, mouth set in an anguished tremor.",
            ],
        },
        "#State 05": {
            "wardrobe": [
                f"Weathered, battle-hardened {costume_ref} stripped of excess bulk, scorched edges blending into final silhouette.",
                f"Permanently scarred and battle-worn {costume_ref}, singed fibers settling into a resolute, transformed appearance.",
            ],
            "injuries": [
                "Battle-scarred topography with healing burns and dried soot etched permanently into skin texture.",
                "Luminescent singe contours and fading hematomas symbolizing ultimate physical endurance.",
            ],
            "expression": [
                "Transcendent clarity, absolute peaceful resolve and emotional catharsis shining through severe exhaustion.",
                "Profound stillness in the gaze, sorrow surrendered to ultimate acceptance and unshakable resolution.",
            ],
        },
    }

    state_dict = presets.get(state_code, presets["#State 01"])
    var_idx = 1 if (is_regeneration or previous_value) else 0

    w_list = state_dict["wardrobe"]
    i_list = state_dict["injuries"]
    e_list = state_dict["expression"]

    w_val = w_list[var_idx % len(w_list)]
    i_val = i_list[var_idx % len(i_list)]
    e_val = e_list[var_idx % len(e_list)]

    tf = target_field.lower().strip()
    if tf == "all":
        return {
            "wardrobe": w_val,
            "injuries_and_wear": i_val,
            "expression_anchor": e_val,
        }
    elif tf == "wardrobe":
        if previous_value and previous_value.strip() == w_val.strip() and len(w_list) > 1:
            w_val = w_list[(var_idx + 1) % len(w_list)]
        return {"wardrobe": w_val, "injuries_and_wear": None, "expression_anchor": None}
    elif tf in ("injuries", "injuries_and_wear"):
        if previous_value and previous_value.strip() == i_val.strip() and len(i_list) > 1:
            i_val = i_list[(var_idx + 1) % len(i_list)]
        return {"wardrobe": None, "injuries_and_wear": i_val, "expression_anchor": None}
    elif tf in ("expression", "expression_anchor"):
        if previous_value and previous_value.strip() == e_val.strip() and len(e_list) > 1:
            e_val = e_list[(var_idx + 1) % len(e_list)]
        return {"wardrobe": None, "injuries_and_wear": None, "expression_anchor": e_val}

    return {
        "wardrobe": w_val,
        "injuries_and_wear": i_val,
        "expression_anchor": e_val,
    }



def _parse_uuid(val: Any, field_name: str = "ID") -> uuid.UUID:
    if not val:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} is required and must be a valid UUID.",
        )
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name} format: '{val}'. Expected a valid UUID.",
        )


def _safe_uuid(val: Any) -> uuid.UUID | None:
    if not val:
        return None
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError, AttributeError):
        return None


async def _resolve_project(project_id: str, session: AsyncSession) -> ProjectModel:
    try:
        p_uuid = uuid.UUID(project_id)
        stmt = select(ProjectModel).where(ProjectModel.id == p_uuid)
    except ValueError:
        stmt = select(ProjectModel).where(ProjectModel.slug == project_id)

    res = await session.execute(stmt)
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/projects/{project_id}/bible", status_code=status.HTTP_200_OK)
async def get_project_bible(
    project_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve active Master Production Bible for the project."""
    project = await _resolve_project(project_id, session)

    stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == project.id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    bible = (await session.execute(stmt)).scalar_one_or_none()

    if not bible:
        # Auto-create baseline version 1 if missing
        now = datetime.now(timezone.utc)
        bible = MasterProductionBibleModel(
            id=uuid.uuid4(),
            project_id=project.id,
            version=1,
            is_locked=False,
            style_parameters={"master_style_code": project.target_style_code},
            world_rules={},
            created_at=now,
            updated_at=now,
        )
        session.add(bible)
        await session.commit()
        await session.refresh(bible)

    return {
        "data": {
            "id": str(bible.id),
            "project_id": str(project.id),
            "version": bible.version,
            "is_locked": bible.is_locked,
            "locked_at": bible.locked_at.isoformat() if bible.locked_at else None,
            "locked_by_user_id": str(bible.locked_by_user_id) if bible.locked_by_user_id else None,
            "style_parameters": bible.style_parameters,
            "world_rules": bible.world_rules,
            "created_at": bible.created_at.isoformat(),
            "updated_at": bible.updated_at.isoformat(),
        }
    }


@router.put("/projects/{project_id}/bible", status_code=status.HTTP_200_OK)
async def update_project_bible(
    project_id: str,
    payload: BibleUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Update active MPB parameters. Fails if Bible is locked."""
    project = await _resolve_project(project_id, session)

    stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == project.id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    bible = (await session.execute(stmt)).scalar_one_or_none()
    if not bible:
        raise HTTPException(status_code=404, detail="Bible not found")

    if bible.is_locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Master Production Bible is locked. DNA freeze is active; create a new version to modify.",
        )

    if payload.style_parameters is not None:
        bible.style_parameters = payload.style_parameters
    if payload.world_rules is not None:
        merged_rules = dict(payload.world_rules)
        if "continuity_rules" in merged_rules and "continuity_laws" not in merged_rules:
            merged_rules["continuity_laws"] = merged_rules["continuity_rules"]
        elif "continuity_laws" in merged_rules and "continuity_rules" not in merged_rules:
            merged_rules["continuity_rules"] = merged_rules["continuity_laws"]

        if "negative_prompts" in merged_rules and "prompt_negatives" not in merged_rules:
            merged_rules["prompt_negatives"] = merged_rules["negative_prompts"]
        elif "prompt_negatives" in merged_rules and "negative_prompts" not in merged_rules:
            merged_rules["negative_prompts"] = merged_rules["prompt_negatives"]

        bible.world_rules = merged_rules
        flag_modified(bible, "world_rules")

    bible.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(bible)

    return {
        "data": {
            "id": str(bible.id),
            "project_id": str(project.id),
            "version": bible.version,
            "is_locked": bible.is_locked,
            "style_parameters": bible.style_parameters,
            "world_rules": bible.world_rules,
            "updated_at": bible.updated_at.isoformat(),
        }
    }


@router.post("/projects/{project_id}/bible/lock", status_code=status.HTTP_200_OK)
async def lock_project_bible(
    project_id: str,
    payload: BibleLockRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Freeze Master Production Bible version into immutable baseline."""
    project = await _resolve_project(project_id, session)

    stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == project.id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    bible = (await session.execute(stmt)).scalar_one_or_none()
    if not bible:
        raise HTTPException(status_code=404, detail="Bible not found")

    now = datetime.now(timezone.utc)
    bible.is_locked = True
    bible.locked_at = now
    bible.locked_by_user_id = current_user.id
    bible.updated_at = now

    await session.commit()
    await session.refresh(bible)

    return {
        "data": {
            "id": str(bible.id),
            "project_id": str(project.id),
            "version": bible.version,
            "is_locked": bible.is_locked,
            "locked_at": bible.locked_at.isoformat() if bible.locked_at else None,
            "locked_by_user_id": str(bible.locked_by_user_id) if bible.locked_by_user_id else None,
            "approval_notes": payload.approval_notes,
            "message": "Master Production Bible DNA locked successfully.",
        }
    }


@router.post("/projects/{project_id}/bible/generate-world-props", status_code=status.HTTP_200_OK)
async def generate_world_props_endpoint(
    project_id: str,
    payload: WorldPropsGenerateRequest | None = None,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Generate 5 Key Environments (#Env 01 - 05) and 5 Signature Hero Props (#Prop 01 - 05) using Polya AI Director."""
    project = await _resolve_project(project_id, session)

    stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == project.id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    bible = (await session.execute(stmt)).scalar_one_or_none()
    if not bible:
        now = datetime.now(timezone.utc)
        bible = MasterProductionBibleModel(
            project_id=project.id,
            version=1,
            is_locked=False,
            style_parameters={"master_style_code": project.target_style_code},
            world_rules={},
            created_at=now,
            updated_at=now,
        )
        session.add(bible)
        await session.commit()
        await session.refresh(bible)

    if bible.is_locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Master Production Bible is locked (DNA Frozen). Create a new revision to modify world and props.",
        )

    # 1. Ingest Character Cast & Dynamic States from DB
    char_stmt = select(CharacterModel).where(CharacterModel.project_id == project.id).order_by(CharacterModel.created_at.asc())
    char_rows = (await session.execute(char_stmt)).scalars().all()
    characters_list = []
    for c in char_rows:
        state_stmt = select(CharacterStateModel).where(CharacterStateModel.character_id == c.id).order_by(CharacterStateModel.state_code.asc())
        st_rows = (await session.execute(state_stmt)).scalars().all()
        meta = c.sheet_metadata or {}
        characters_list.append({
            "id": str(c.id),
            "name": c.name,
            "role": c.role,
            "narrative_profile": getattr(c, "narrative_summary", None) or meta.get("narrative_summary") or "",
            "base_visual_prompt": c.base_prompt,
            "states": [
                {
                    "state_code": s.state_code,
                    "state_label": s.state_label or s.state_code,
                    "wardrobe": s.wardrobe,
                    "injuries_and_wear": s.injuries_and_wear,
                    "expression_anchor": s.expression_anchor,
                }
                for s in st_rows
            ],
        })

    # 2. Ingest 50-Scene Storyboard & Sluglines from DB
    scene_stmt = (
        select(SceneModel)
        .where(SceneModel.project_id == project.id)
        .order_by(SceneModel.act_number.asc(), SceneModel.scene_number.asc())
    )
    scene_rows = (await session.execute(scene_stmt)).scalars().all()
    scenes_list = [
        {
            "scene_number": sc.scene_number,
            "act_number": sc.act_number,
            "slugline": sc.slugline,
            "narrative_goal": sc.narrative_goal,
        }
        for sc in scene_rows
    ]

    try:
        context = extract_project_narrative_context(project, bible, characters=characters_list, scenes=scenes_list)
    except ValueError as exc:
        title = (project.title or "").strip()
        if not title:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        settings = project.settings if isinstance(project.settings, dict) else {}
        genre_tone = settings.get("genre") or settings.get("tone") or "Cinematic Film"
        context = ProjectNarrativeContext(
            project_id=str(project.id),
            title=title,
            synopsis=f"A cinematic {genre_tone} production titled '{title}' exploring immersive environments and signature hero props.",
            genre_tone=str(genre_tone),
            master_style_code=project.target_style_code or "#Style 01",
            style_name="Hollywood Cinematic",
            aesthetic_directives="",
            color_grade_emulation="",
            world_setting="Cinematic Universe",
            continuity_rules=[],
            visual_dna_parameters={},
            environments_summary="",
            props_summary="",
            aspect_ratio=project.aspect_ratio or "16:9",
            operational_stage=project.operational_stage or 1,
            cast_characters=characters_list,
            storyboard_scenes=scenes_list,
        )

    notes = payload.additional_notes if payload else None
    engine = PolyaScreenwriterEngine()
    try:
        gen_data = await engine.generate_world_and_props(context=context, additional_notes=notes)
    except Exception as exc:
        logger.error("Polya AI Director generate_world_and_props failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Polya AI Director failed to generate world and props: {exc}",
        )

    updated_rules = dict(bible.world_rules or {})
    updated_rules["environments"] = gen_data.get("environments", [])
    updated_rules["props"] = gen_data.get("props", [])
    if "generation_meta" in gen_data:
        updated_rules["generation_meta"] = gen_data["generation_meta"]

    bible.world_rules = updated_rules
    flag_modified(bible, "world_rules")
    bible.updated_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(bible)

    return {
        "status": "success",
        "project_id": str(project.id),
        "environments": bible.world_rules.get("environments", []),
        "props": bible.world_rules.get("props", []),
        "generation_meta": bible.world_rules.get("generation_meta"),
        "data": {
            "id": str(bible.id),
            "project_id": str(project.id),
            "version": bible.version,
            "is_locked": bible.is_locked,
            "world_rules": bible.world_rules,
            "updated_at": bible.updated_at.isoformat(),
        },
    }


@router.post("/projects/{project_id}/bible/generate-rules-invariants", status_code=status.HTTP_200_OK)
async def generate_rules_invariants_endpoint(
    project_id: str,
    payload: RulesInvariantsGenerateRequest | None = None,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Generate visual continuity laws and global negative prompts using Polya AI Director."""
    project = await _resolve_project(project_id, session)

    stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == project.id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    bible = (await session.execute(stmt)).scalar_one_or_none()
    if not bible:
        now = datetime.now(timezone.utc)
        bible = MasterProductionBibleModel(
            project_id=project.id,
            version=1,
            is_locked=False,
            style_parameters={"master_style_code": project.target_style_code},
            world_rules={},
            created_at=now,
            updated_at=now,
        )
        session.add(bible)
        await session.commit()
        await session.refresh(bible)

    if bible.is_locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Master Production Bible is locked (DNA Frozen). Create a new revision to modify rules and invariants.",
        )

    # 1. Ingest Character Cast & Dynamic States from DB
    char_stmt = select(CharacterModel).where(CharacterModel.project_id == project.id).order_by(CharacterModel.created_at.asc())
    char_rows = (await session.execute(char_stmt)).scalars().all()
    characters_list = []
    for c in char_rows:
        state_stmt = select(CharacterStateModel).where(CharacterStateModel.character_id == c.id).order_by(CharacterStateModel.state_code.asc())
        st_rows = (await session.execute(state_stmt)).scalars().all()
        meta = c.sheet_metadata or {}
        characters_list.append({
            "id": str(c.id),
            "name": c.name,
            "role": c.role,
            "narrative_profile": getattr(c, "narrative_summary", None) or meta.get("narrative_summary") or "",
            "base_visual_prompt": c.base_prompt,
            "states": [
                {
                    "state_code": s.state_code,
                    "state_label": s.state_label or s.state_code,
                    "wardrobe": s.wardrobe,
                    "injuries_and_wear": s.injuries_and_wear,
                    "expression_anchor": s.expression_anchor,
                }
                for s in st_rows
            ],
        })

    # 2. Ingest 50-Scene Storyboard & Sluglines from DB
    scene_stmt = (
        select(SceneModel)
        .where(SceneModel.project_id == project.id)
        .order_by(SceneModel.act_number.asc(), SceneModel.scene_number.asc())
    )
    scene_rows = (await session.execute(scene_stmt)).scalars().all()
    scenes_list = [
        {
            "scene_number": sc.scene_number,
            "act_number": sc.act_number,
            "slugline": sc.slugline,
            "narrative_goal": sc.narrative_goal,
        }
        for sc in scene_rows
    ]

    try:
        context = extract_project_narrative_context(project, bible, characters=characters_list, scenes=scenes_list)
    except ValueError as exc:
        title = (project.title or "").strip()
        if not title:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        settings = project.settings if isinstance(project.settings, dict) else {}
        genre_tone = settings.get("genre") or settings.get("tone") or "Cinematic Film"
        raw_envs = (bible.world_rules or {}).get("environments", [])
        structured_envs = [e for e in raw_envs if isinstance(e, dict)] if isinstance(raw_envs, list) else []
        raw_props = (bible.world_rules or {}).get("props", [])
        structured_props = [p for p in raw_props if isinstance(p, dict)] if isinstance(raw_props, list) else []
        context = ProjectNarrativeContext(
            project_id=str(project.id),
            title=title,
            synopsis=f"A cinematic {genre_tone} production titled '{title}' exploring visual continuity and generative invariant rules.",
            genre_tone=str(genre_tone),
            master_style_code=project.target_style_code or "#Style 01",
            style_name="Hollywood Cinematic",
            aesthetic_directives="",
            color_grade_emulation="",
            world_setting="Cinematic Universe",
            continuity_rules=[],
            visual_dna_parameters={},
            environments_summary="",
            props_summary="",
            aspect_ratio=project.aspect_ratio or "16:9",
            operational_stage=project.operational_stage or 1,
            cast_characters=characters_list,
            storyboard_scenes=scenes_list,
            environments=structured_envs,
            props=structured_props,
        )

    notes = payload.additional_notes if payload else None
    engine = PolyaScreenwriterEngine()
    try:
        gen_data = await engine.generate_rules_and_invariants(context=context, additional_notes=notes)
    except Exception as exc:
        logger.error("Polya AI Director generate_rules_and_invariants failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Polya AI Director failed to generate rules and invariants: {exc}",
        )

    # Non-destructive merge preserving environments, props, and generation_meta
    updated_rules = dict(bible.world_rules or {})
    updated_rules["continuity_rules"] = gen_data.get("continuity_rules", [])
    updated_rules["continuity_laws"] = gen_data.get("continuity_laws", updated_rules["continuity_rules"])
    updated_rules["negative_prompts"] = gen_data.get("negative_prompts", [])
    updated_rules["prompt_negatives"] = gen_data.get("prompt_negatives", updated_rules["negative_prompts"])
    if "rules_generation_meta" in gen_data:
        updated_rules["rules_generation_meta"] = gen_data["rules_generation_meta"]

    bible.world_rules = updated_rules
    flag_modified(bible, "world_rules")
    bible.updated_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(bible)

    return {
        "status": "success",
        "project_id": str(project.id),
        "continuity_rules": bible.world_rules.get("continuity_rules", []),
        "continuity_laws": bible.world_rules.get("continuity_laws", []),
        "negative_prompts": bible.world_rules.get("negative_prompts", []),
        "prompt_negatives": bible.world_rules.get("prompt_negatives", []),
        "rules_generation_meta": bible.world_rules.get("rules_generation_meta"),
        "data": {
            "id": str(bible.id),
            "project_id": str(project.id),
            "version": bible.version,
            "is_locked": bible.is_locked,
            "world_rules": bible.world_rules,
            "updated_at": bible.updated_at.isoformat(),
        },
    }


# Character & State Management endpoints


@router.get("/projects/{project_id}/characters", status_code=status.HTTP_200_OK)
async def list_characters(
    project_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """List characters and their registered states for the project."""
    project = await _resolve_project(project_id, session)

    stmt = select(CharacterModel).where(CharacterModel.project_id == project.id).order_by(CharacterModel.created_at.asc())
    characters = (await session.execute(stmt)).scalars().all()

    data = []
    for c in characters:
        state_stmt = select(CharacterStateModel).where(CharacterStateModel.character_id == c.id).order_by(CharacterStateModel.state_code.asc())
        states = (await session.execute(state_stmt)).scalars().all()
        # Ensure deterministic seed if missing
        seed_val = c.dna_seed
        if not seed_val:
            seed_val = int(hashlib.sha256(str(c.id).encode()).hexdigest()[:8], 16) % 900000 + 100000

        meta = c.sheet_metadata or {}
        data.append(
            {
                "id": str(c.id),
                "name": c.name,
                "role": c.role,
                "narrative_summary": getattr(c, "narrative_summary", None) or meta.get("narrative_summary") or "",
                "voice_dna_profile": getattr(c, "voice_dna_profile", None) or meta.get("voice_dna_profile") or "",
                "base_prompt": c.base_prompt,
                "face_ref_asset_id": str(c.face_ref_asset_id) if c.face_ref_asset_id else None,
                "voice_ref_asset_id": str(c.voice_ref_asset_id) if c.voice_ref_asset_id else None,
                "closeup_image_url": c.closeup_image_url,
                "front_image_url": c.front_image_url,
                "side_image_url": c.side_image_url,
                "three_quarter_image_url": c.three_quarter_image_url,
                "back_image_url": c.back_image_url,
                "tpose_image_url": c.tpose_image_url,
                "action_image_url": c.action_image_url,
                "expression_image_url": c.expression_image_url,
                "dna_seed": seed_val,
                "sheet_metadata": meta,
                "states": [
                    {
                        "id": str(s.id),
                        "state_code": s.state_code,
                        "state_label": getattr(s, "state_label", None) or s.state_code,
                        "wardrobe": s.wardrobe,
                        "injuries_and_wear": s.injuries_and_wear,
                        "expression_anchor": s.expression_anchor,
                        "scene_id": str(s.scene_id) if s.scene_id else None,
                        "image_url": s.image_url,
                    }
                    for s in states
                ],
                "created_at": c.created_at.isoformat(),
            }
        )

    return {"data": data}


@router.post("/projects/{project_id}/characters", status_code=status.HTTP_201_CREATED)
async def create_character(
    project_id: str,
    payload: CharacterCreateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Register a new character identity with locked DNA seed and promote pre-creation visual previews if provided."""
    project = await _resolve_project(project_id, session)

    char_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    det_seed = payload.dna_seed or (int(hashlib.sha256(str(char_id).encode()).hexdigest()[:8], 16) % 900000 + 100000)

    face_id = _safe_uuid(payload.face_ref_asset_id)
    voice_id = _safe_uuid(payload.voice_ref_asset_id)

    closeup_url = None
    expression_url = None
    front_url = None
    initial_metadata: dict[str, Any] = {}

    settings = get_settings()
    perm_storage = settings.effective_preview_storage_path
    perm_storage.mkdir(parents=True, exist_ok=True)

    # Asset promotion from staging folder
    if payload.preview_token:
        clean_token = Path(payload.preview_token).name
        temp_dir = perm_storage.parent / "temp_previews" / clean_token
        if not temp_dir.exists():
            temp_dir = Path("./data/assets/temp_previews") / clean_token

        if temp_dir.exists():
            closeup_src = temp_dir / "closeup.png"
            if closeup_src.exists():
                closeup_name = f"char_{str(char_id)[:8]}_closeup_{uuid.uuid4().hex[:8]}.png"
                closeup_dest = perm_storage / closeup_name
                shutil.copyfile(closeup_src, closeup_dest)
                closeup_url = f"/api/v1/assets/previews/{closeup_name}"
                initial_metadata["closeup"] = {
                    "image_url": closeup_url,
                    "source": "pre_creation_gatekeeper",
                    "status": "completed",
                    "seed": det_seed,
                    "rendered_at": now.isoformat(),
                }

            expr_src = temp_dir / "expression.png"
            if expr_src.exists():
                expr_name = f"char_{str(char_id)[:8]}_expression_{uuid.uuid4().hex[:8]}.png"
                expr_dest = perm_storage / expr_name
                shutil.copyfile(expr_src, expr_dest)
                expression_url = f"/api/v1/assets/previews/{expr_name}"
                initial_metadata["expression"] = {
                    "image_url": expression_url,
                    "source": "pre_creation_gatekeeper",
                    "status": "completed",
                    "seed": det_seed,
                    "rendered_at": now.isoformat(),
                }

            front_src = temp_dir / "front.png"
            if front_src.exists():
                front_name = f"char_{str(char_id)[:8]}_front_{uuid.uuid4().hex[:8]}.png"
                front_dest = perm_storage / front_name
                shutil.copyfile(front_src, front_dest)
                front_url = f"/api/v1/assets/previews/{front_name}"
                initial_metadata["front"] = {
                    "image_url": front_url,
                    "source": "pre_creation_gatekeeper",
                    "status": "completed",
                    "seed": det_seed,
                    "rendered_at": now.isoformat(),
                }

            # Atomically remove temporary staging directory after promotion
            shutil.rmtree(temp_dir, ignore_errors=True)

    char = CharacterModel(
        id=char_id,
        project_id=project.id,
        name=payload.name,
        role=payload.role,
        base_prompt=payload.base_prompt,
        narrative_summary=getattr(payload, "narrative_summary", None),
        voice_dna_profile=getattr(payload, "voice_dna_profile", None),
        face_ref_asset_id=face_id,
        voice_ref_asset_id=voice_id,
        closeup_image_url=closeup_url or payload.closeup_image_url,
        front_image_url=front_url,
        expression_image_url=expression_url,
        dna_seed=det_seed,
        sheet_metadata=initial_metadata,
        created_at=now,
    )
    session.add(char)
    await session.commit()
    await session.refresh(char)

    return {
        "data": {
            "id": str(char.id),
            "name": char.name,
            "role": char.role,
            "narrative_summary": char.narrative_summary,
            "voice_dna_profile": char.voice_dna_profile,
            "base_prompt": char.base_prompt,
            "dna_seed": char.dna_seed,
            "closeup_image_url": char.closeup_image_url,
            "front_image_url": char.front_image_url,
            "expression_image_url": char.expression_image_url,
            "sheet_metadata": char.sheet_metadata,
            "created_at": char.created_at.isoformat(),
        }
    }


# ==============================================================================
# Polya AI (Screenwriter) Cast & Character Generation Endpoints
# ==============================================================================

@router.post("/projects/{project_id}/characters/generate-cast", status_code=status.HTTP_201_CREATED)
async def generate_cast_endpoint(
    project_id: str,
    payload: CharacterGenerateCastRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Generate a cohesive ensemble cast (5 to 8 characters) using Polya AI Screenwriter."""
    project = await _resolve_project(project_id, session)

    # 1. Existing character check
    existing_stmt = select(CharacterModel).where(CharacterModel.project_id == project.id)
    existing_chars = (await session.execute(existing_stmt)).scalars().all()

    if existing_chars and not payload.replace_existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Proyek sudah memiliki karakter. Konfirmasi penggantian (replace_existing=true) diperlukan sebelum me-regenerate seluruh cast.",
        )

    # 2. Extract ProjectNarrativeContext from SQLite
    mpb_stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == project.id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    bible = (await session.execute(mpb_stmt)).scalar_one_or_none()
    try:
        context = extract_project_narrative_context(project, bible)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # 3. Call Polya AI Screenwriter Engine
    engine = PolyaScreenwriterEngine()
    try:
        ensemble_data = await engine.generate_cast_ensemble(
            context=context,
            preferred_count=payload.preferred_count,
            additional_notes=payload.additional_notes,
        )
    except Exception as exc:
        logger.error("Polya AI generate_cast failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Polya AI Screenwriter gagal men-generate cast: {exc}",
        )

    now = datetime.now(timezone.utc)
    used_seeds: set[int] = set()

    # 4. Atomic SQLite Transaction (Zero Auto Image Render)
    try:
        if existing_chars:
            for old_c in existing_chars:
                await session.delete(old_c)
            await session.flush()

        created_chars = []
        for idx, c_data in enumerate(ensemble_data.characters):
            char_id = uuid.uuid4()
            seed = generate_unique_deterministic_seed(
                str(project.id), c_data.name, used_seeds, salt=f"cast_{idx}_{time.time_ns()}"
            )

            meta = {
                "source": "polya_ai_screenwriter",
                "cast_rationale": ensemble_data.cast_rationale,
                "narrative_summary": c_data.narrative_summary,
                "voice_dna_profile": c_data.voice_dna_profile,
            }

            char_obj = CharacterModel(
                id=char_id,
                project_id=project.id,
                name=c_data.name,
                role=c_data.role,
                base_prompt=c_data.base_visual_prompt,
                narrative_summary=c_data.narrative_summary,
                voice_dna_profile=c_data.voice_dna_profile,
                dna_seed=seed,
                sheet_metadata=meta,
                created_at=now,
            )
            session.add(char_obj)
            await session.flush()

            # Insert 5 dynamic states
            state_codes = ["#State 01", "#State 02", "#State 03", "#State 04", "#State 05"]
            states_output = []
            for s_idx, s_data in enumerate(c_data.states[:5]):
                st_id = uuid.uuid4()
                st_code = state_codes[s_idx]
                st_obj = CharacterStateModel(
                    id=st_id,
                    character_id=char_id,
                    state_code=st_code,
                    state_label=s_data.state_label,
                    wardrobe=s_data.wardrobe,
                    injuries_and_wear=s_data.physical_damage,
                    expression_anchor=s_data.emotional_anchor,
                    image_url=None,  # STRICTLY ZERO AUTO IMAGE RENDER
                    created_at=now,
                )
                session.add(st_obj)
                states_output.append({
                    "id": str(st_id),
                    "state_code": st_code,
                    "state_label": s_data.state_label,
                    "wardrobe": s_data.wardrobe,
                    "injuries_and_wear": s_data.physical_damage,
                    "expression_anchor": s_data.emotional_anchor,
                    "image_url": None,
                })

            created_chars.append({
                "id": str(char_id),
                "name": char_obj.name,
                "role": char_obj.role,
                "narrative_summary": char_obj.narrative_summary,
                "voice_dna_profile": char_obj.voice_dna_profile,
                "base_prompt": char_obj.base_prompt,
                "dna_seed": char_obj.dna_seed,
                "closeup_image_url": None,
                "front_image_url": None,
                "side_image_url": None,
                "three_quarter_image_url": None,
                "back_image_url": None,
                "tpose_image_url": None,
                "action_image_url": None,
                "expression_image_url": None,
                "sheet_metadata": char_obj.sheet_metadata,
                "states": states_output,
                "created_at": char_obj.created_at.isoformat(),
            })

        await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.error("Failed to commit generated cast: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal menyimpan ensemble cast ke SQLite: {exc}",
        )

    return {
        "status": "success",
        "cast_rationale": ensemble_data.cast_rationale,
        "count": len(created_chars),
        "generated_count": len(created_chars),
        "data": created_chars,
    }


@router.post("/projects/{project_id}/characters/generate-one", status_code=status.HTTP_201_CREATED)
async def generate_one_character_endpoint(
    project_id: str,
    payload: CharacterGenerateOneRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Generate exactly 1 complementary character using Polya AI Screenwriter with sibling anti-duplication."""
    project = await _resolve_project(project_id, session)

    chars_stmt = select(CharacterModel).where(CharacterModel.project_id == project.id)
    existing_chars = (await session.execute(chars_stmt)).scalars().all()
    sibling_data = [
        {"id": str(c.id), "name": c.name, "role": c.role, "base_prompt": c.base_prompt}
        for c in existing_chars
    ]
    existing_seeds = {c.dna_seed for c in existing_chars if c.dna_seed is not None}

    mpb_stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == project.id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    bible = (await session.execute(mpb_stmt)).scalar_one_or_none()
    try:
        context = extract_project_narrative_context(project, bible)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    engine = PolyaScreenwriterEngine()
    try:
        char_data = await engine.generate_one_character(
            context=context,
            sibling_characters=sibling_data,
            preferred_role=payload.preferred_role,
            custom_directive=payload.custom_directive,
        )
    except Exception as exc:
        logger.error("Polya AI generate_one_character failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Polya AI Screenwriter gagal men-generate karakter baru: {exc}",
        )

    now = datetime.now(timezone.utc)
    char_id = uuid.uuid4()
    seed = generate_unique_deterministic_seed(
        str(project.id), char_data.name, existing_seeds, salt=f"one_{len(existing_chars)}_{time.time_ns()}"
    )

    try:
        meta = {
            "source": "polya_ai_screenwriter",
            "narrative_summary": char_data.narrative_summary,
            "voice_dna_profile": char_data.voice_dna_profile,
        }

        char_obj = CharacterModel(
            id=char_id,
            project_id=project.id,
            name=char_data.name,
            role=char_data.role,
            base_prompt=char_data.base_visual_prompt,
            narrative_summary=char_data.narrative_summary,
            voice_dna_profile=char_data.voice_dna_profile,
            dna_seed=seed,
            sheet_metadata=meta,
            created_at=now,
        )
        session.add(char_obj)
        await session.flush()

        state_codes = ["#State 01", "#State 02", "#State 03", "#State 04", "#State 05"]
        states_output = []
        for s_idx, s_data in enumerate(char_data.states[:5]):
            st_id = uuid.uuid4()
            st_code = state_codes[s_idx]
            st_obj = CharacterStateModel(
                id=st_id,
                character_id=char_id,
                state_code=st_code,
                state_label=s_data.state_label,
                wardrobe=s_data.wardrobe,
                injuries_and_wear=s_data.physical_damage,
                expression_anchor=s_data.emotional_anchor,
                image_url=None,  # STRICTLY ZERO AUTO IMAGE RENDER
                created_at=now,
            )
            session.add(st_obj)
            states_output.append({
                "id": str(st_id),
                "state_code": st_code,
                "state_label": s_data.state_label,
                "wardrobe": s_data.wardrobe,
                "injuries_and_wear": s_data.physical_damage,
                "expression_anchor": s_data.emotional_anchor,
                "image_url": None,
            })

        await session.commit()
        await session.refresh(char_obj)
    except Exception as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal menyimpan karakter baru ke SQLite: {exc}",
        )

    return {
        "status": "success",
        "data": {
            "id": str(char_id),
            "name": char_obj.name,
            "role": char_obj.role,
            "narrative_summary": char_obj.narrative_summary,
            "voice_dna_profile": char_obj.voice_dna_profile,
            "base_prompt": char_obj.base_prompt,
            "dna_seed": char_obj.dna_seed,
            "closeup_image_url": None,
            "front_image_url": None,
            "side_image_url": None,
            "three_quarter_image_url": None,
            "back_image_url": None,
            "tpose_image_url": None,
            "action_image_url": None,
            "expression_image_url": None,
            "sheet_metadata": char_obj.sheet_metadata,
            "states": states_output,
            "created_at": char_obj.created_at.isoformat(),
        },
    }


@router.post("/projects/{project_id}/characters/{character_id}/regenerate", status_code=status.HTTP_200_OK)
async def regenerate_character_endpoint(
    project_id: str,
    character_id: str,
    payload: CharacterRegenerateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Isolated single-character regeneration using Polya AI Screenwriter with sibling anti-duplication."""
    project = await _resolve_project(project_id, session)
    c_uuid = _parse_uuid(character_id, "character_id")

    char_stmt = select(CharacterModel).where(
        CharacterModel.id == c_uuid,
        CharacterModel.project_id == project.id,
    )
    char = (await session.execute(char_stmt)).scalar_one_or_none()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    siblings_stmt = select(CharacterModel).where(
        CharacterModel.project_id == project.id,
        CharacterModel.id != char.id,
    )
    siblings = (await session.execute(siblings_stmt)).scalars().all()
    sibling_data = [
        {"id": str(c.id), "name": c.name, "role": c.role, "base_prompt": c.base_prompt}
        for c in siblings
    ]
    existing_seeds = {c.dna_seed for c in siblings if c.dna_seed is not None}

    mpb_stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == project.id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    bible = (await session.execute(mpb_stmt)).scalar_one_or_none()
    try:
        context = extract_project_narrative_context(project, bible)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    engine = PolyaScreenwriterEngine()
    try:
        char_data = await engine.regenerate_single_character(
            context=context,
            target_character={
                "id": str(char.id),
                "name": char.name,
                "role": char.role,
                "base_prompt": char.base_prompt,
            },
            sibling_characters=sibling_data,
            preserve_role=payload.preserve_role,
            custom_directive=payload.custom_directive,
        )
    except Exception as exc:
        logger.error("Polya AI regenerate_single_character failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Polya AI Screenwriter gagal meregenerate karakter: {exc}",
        )

    now = datetime.now(timezone.utc)
    new_seed = generate_unique_deterministic_seed(
        str(project.id), char_data.name, existing_seeds, salt=f"regen_{time.time_ns()}"
    )

    try:
        char.name = char_data.name
        if not payload.preserve_role:
            char.role = char_data.role
        char.base_prompt = char_data.base_visual_prompt
        char.narrative_summary = char_data.narrative_summary
        char.voice_dna_profile = char_data.voice_dna_profile
        char.dna_seed = new_seed

        # Reset images to prevent visual mismatch with previous character identity
        char.closeup_image_url = None
        char.front_image_url = None
        char.side_image_url = None
        char.three_quarter_image_url = None
        char.back_image_url = None
        char.tpose_image_url = None
        char.action_image_url = None
        char.expression_image_url = None
        char.sheet_metadata = {
            "source": "polya_ai_screenwriter_regenerate",
            "regenerated_at": now.isoformat(),
            "narrative_summary": char_data.narrative_summary,
            "voice_dna_profile": char_data.voice_dna_profile,
        }

        # Replace states for this character only
        del_states_stmt = select(CharacterStateModel).where(CharacterStateModel.character_id == char.id)
        old_states = (await session.execute(del_states_stmt)).scalars().all()
        for old_st in old_states:
            await session.delete(old_st)
        await session.flush()

        state_codes = ["#State 01", "#State 02", "#State 03", "#State 04", "#State 05"]
        states_output = []
        for s_idx, s_data in enumerate(char_data.states[:5]):
            st_id = uuid.uuid4()
            st_code = state_codes[s_idx]
            st_obj = CharacterStateModel(
                id=st_id,
                character_id=char.id,
                state_code=st_code,
                state_label=s_data.state_label,
                wardrobe=s_data.wardrobe,
                injuries_and_wear=s_data.physical_damage,
                expression_anchor=s_data.emotional_anchor,
                image_url=None,  # STRICTLY ZERO AUTO IMAGE RENDER
                created_at=now,
            )
            session.add(st_obj)
            states_output.append({
                "id": str(st_id),
                "state_code": st_code,
                "state_label": s_data.state_label,
                "wardrobe": s_data.wardrobe,
                "injuries_and_wear": s_data.physical_damage,
                "expression_anchor": s_data.emotional_anchor,
                "image_url": None,
            })

        await session.commit()
        await session.refresh(char)
    except Exception as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengupdate karakter di SQLite: {exc}",
        )

    return {
        "status": "success",
        "data": {
            "id": str(char.id),
            "name": char.name,
            "role": char.role,
            "narrative_summary": char.narrative_summary,
            "voice_dna_profile": char.voice_dna_profile,
            "base_prompt": char.base_prompt,
            "dna_seed": char.dna_seed,
            "closeup_image_url": None,
            "front_image_url": None,
            "side_image_url": None,
            "three_quarter_image_url": None,
            "back_image_url": None,
            "tpose_image_url": None,
            "action_image_url": None,
            "expression_image_url": None,
            "sheet_metadata": char.sheet_metadata,
            "states": states_output,
            "created_at": char.created_at.isoformat(),
        },
    }


@router.put("/projects/{project_id}/characters/{character_id}", status_code=status.HTTP_200_OK)
@router.patch("/projects/{project_id}/characters/{character_id}", status_code=status.HTTP_200_OK)
async def update_character_endpoint(
    project_id: str,
    character_id: str,
    payload: CharacterUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Inline update character fields (name, role, base_prompt, voice_dna_profile, etc.)."""
    project = await _resolve_project(project_id, session)
    c_uuid = _parse_uuid(character_id, "character_id")

    char_stmt = select(CharacterModel).where(
        CharacterModel.id == c_uuid,
        CharacterModel.project_id == project.id,
    )
    char = (await session.execute(char_stmt)).scalar_one_or_none()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    if payload.name is not None and payload.name.strip():
        char.name = payload.name.strip()
    if payload.role is not None and payload.role.strip():
        char.role = payload.role.strip().upper()
    if payload.base_prompt is not None and payload.base_prompt.strip():
        char.base_prompt = payload.base_prompt.strip()
    if payload.voice_dna_profile is not None:
        char.voice_dna_profile = payload.voice_dna_profile.strip()
    if payload.narrative_summary is not None:
        char.narrative_summary = payload.narrative_summary.strip()
    if payload.dna_seed is not None:
        char.dna_seed = int(payload.dna_seed)

    await session.commit()
    await session.refresh(char)

    return {
        "status": "success",
        "data": {
            "id": str(char.id),
            "name": char.name,
            "role": char.role,
            "narrative_summary": char.narrative_summary,
            "voice_dna_profile": char.voice_dna_profile,
            "base_prompt": char.base_prompt,
            "dna_seed": char.dna_seed,
            "created_at": char.created_at.isoformat(),
        },
    }


@router.delete("/projects/{project_id}/characters/{character_id}", status_code=status.HTTP_200_OK)
async def delete_character_endpoint(
    project_id: str,
    character_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Permanently delete an individual character and its cascade states."""
    project = await _resolve_project(project_id, session)
    c_uuid = _parse_uuid(character_id, "character_id")

    char_stmt = select(CharacterModel).where(
        CharacterModel.id == c_uuid,
        CharacterModel.project_id == project.id,
    )
    char = (await session.execute(char_stmt)).scalar_one_or_none()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    await session.delete(char)
    await session.commit()

    return {"status": "success", "message": f"Character {character_id} deleted successfully"}


@router.post("/characters/{character_id}/states", status_code=status.HTTP_201_CREATED)
async def create_character_state(
    character_id: str,
    payload: CharacterStateCreateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Register dynamic state evolution (#State 01-05) for character."""
    c_uuid = _parse_uuid(character_id, "character_id")
    char_stmt = select(CharacterModel).where(CharacterModel.id == c_uuid)
    char = (await session.execute(char_stmt)).scalar_one_or_none()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    scene_uuid = _safe_uuid(payload.scene_id)
    state_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    state = CharacterStateModel(
        id=state_id,
        character_id=char.id,
        scene_id=scene_uuid,
        state_code=payload.state_code,
        state_label=payload.state_label or payload.state_code,
        wardrobe=payload.wardrobe,
        injuries_and_wear=payload.injuries_and_wear,
        expression_anchor=payload.expression_anchor,
        created_at=now,
    )
    session.add(state)
    await session.commit()
    await session.refresh(state)

    return {
        "data": {
            "id": str(state.id),
            "character_id": str(char.id),
            "state_code": state.state_code,
            "state_label": state.state_label or state.state_code,
            "wardrobe": state.wardrobe,
            "injuries_and_wear": state.injuries_and_wear,
            "expression_anchor": state.expression_anchor,
            "scene_id": str(state.scene_id) if state.scene_id else None,
            "created_at": state.created_at.isoformat(),
        }
    }


@router.post("/characters/{character_id}/states/suggest", status_code=status.HTTP_200_OK)
async def suggest_character_state(
    character_id: str,
    payload: StateSuggestionRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Generate context-aware character state progression suggestions (#State 01-#State 05) using 9Router (geminis)."""
    c_uuid = _parse_uuid(character_id, "character_id")
    char_stmt = select(CharacterModel).where(CharacterModel.id == c_uuid)
    char = (await session.execute(char_stmt)).scalar_one_or_none()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    # 1. Project Context
    project_stmt = select(ProjectModel).where(ProjectModel.id == char.project_id)
    project = (await session.execute(project_stmt)).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    film_title = project.title
    p_settings = project.settings if isinstance(project.settings, dict) else {}
    treatment = p_settings.get("treatment") or {}
    synopsis = (
        p_settings.get("synopsis")
        or p_settings.get("description")
        or treatment.get("logline")
        or treatment.get("theme")
        or "Epic cinematic narrative feature production."
    )
    genre_tone = p_settings.get("tone") or p_settings.get("genre") or "Cinematic Film"

    # 2. Master Production Bible Context
    mpb_stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == project.id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    bible = (await session.execute(mpb_stmt)).scalar_one_or_none()
    style_code = (
        bible.style_parameters.get("master_style_code")
        if bible and bible.style_parameters
        else None
    ) or project.target_style_code or "#Style 01"

    setting_world = (
        (bible.world_rules.get("setting") or bible.world_rules.get("world_name"))
        if bible and bible.world_rules
        else p_settings.get("setting") or "Cinematic Universe"
    )

    style_def = next((s for s in STYLE_CATALOG if s.get("code") == style_code), None) or STYLE_CATALOG[0]
    style_name = style_def.get("name", "Hollywood Cinematic")

    # 3. Full Dramatic Arc Context across all acts (compact summary per act/beat, no 6-scene truncation)
    scenes_stmt = (
        select(SceneModel.act_number, SceneModel.scene_number, SceneModel.slugline, SceneModel.narrative_goal)
        .where(SceneModel.project_id == project.id)
        .order_by(SceneModel.scene_number.asc())
    )
    scenes_rows = (await session.execute(scenes_stmt)).all()
    if scenes_rows:
        act_buckets: dict[int, list[str]] = {}
        for a_num, s_num, slug, goal in scenes_rows:
            act_buckets.setdefault(int(a_num or 1), []).append(f"Sc {s_num} ({slug}): {str(goal or '')[:55]}")
        arc_parts = []
        for a_num in sorted(act_buckets.keys()):
            items = act_buckets[a_num]
            sampled = items[:2] + (items[-1:] if len(items) > 2 else [])
            arc_parts.append(f"Act {a_num} ({len(items)} scenes): " + " -> ".join(sampled))
        scenes_summary = "\n".join(arc_parts)
    else:
        scenes_summary = "Multi-act narrative arc spanning Act I (setup), Act II (rising stakes), Act III (confrontation), and Climax/Resolution."

    # 4. Cross-State Continuity
    prior_states_stmt = (
        select(CharacterStateModel)
        .where(CharacterStateModel.character_id == char.id)
        .order_by(CharacterStateModel.state_code.asc())
    )
    prior_states = (await session.execute(prior_states_stmt)).scalars().all()
    prior_states_formatted = [
        f"- {ps.state_code} ({ps.state_label or ''}): Wardrobe: {ps.wardrobe} | Injuries/Wear: {ps.injuries_and_wear} | Expression: {ps.expression_anchor}"
        for ps in prior_states
    ]
    prior_states_text = "\n".join(prior_states_formatted) if prior_states_formatted else "None registered yet."

    # 5. Delegate to PolyaScreenwriterEngine (RAG 8766 + Voice DNA + 18-Style taxonomy)
    curr_vals = payload.current_values or {}
    t_field = payload.target_field.lower().strip()

    llm_prov = (payload.llm_provider or "9router").lower().strip()
    model_choice = "geminis"
    if "gemini" in llm_prov and "9router" not in llm_prov:
        model_choice = "gc/gemini-2.5-flash"
    elif "agy" in llm_prov:
        model_choice = "Agy"

    try:
        proj_ctx: ProjectNarrativeContext | dict[str, Any] = extract_project_narrative_context(project, bible=bible)
    except Exception:
        proj_ctx = {
            "title": film_title,
            "synopsis": synopsis,
            "genre_tone": genre_tone,
            "master_style_code": style_code,
            "style_name": style_name,
            "world_setting": setting_world,
        }

    result_data = None
    try:
        engine = PolyaScreenwriterEngine(model=model_choice, timeout=15.0)
        result_data = await engine.suggest_character_state(
            project_context=proj_ctx,
            character=char,
            state_code=payload.state_code,
            target_field=t_field,
            current_values=curr_vals,
            previous_value=payload.previous_value,
            is_regeneration=payload.is_regeneration,
            scenes_summary=scenes_summary,
            prior_states_text=prior_states_text,
        )
    except Exception as exc:
        logger.warning(f"PolyaScreenwriterEngine state suggest failed or timed out: {exc}. Using contextual procedural generator.")

    # Synonym key mapping and cleaning
    key_map = {
        "injuries": "injuries_and_wear",
        "injuries_wear": "injuries_and_wear",
        "physical_damage": "injuries_and_wear",
        "wear_and_tear": "injuries_and_wear",
        "damage": "injuries_and_wear",
        "expression": "expression_anchor",
        "emotional_anchor": "expression_anchor",
        "emotions": "expression_anchor",
        "costume": "wardrobe",
        "attire": "wardrobe",
        "outfit": "wardrobe",
    }
    normalized = {}
    if isinstance(result_data, dict):
        for k, v in result_data.items():
            norm_k = key_map.get(k.lower().strip(), k.lower().strip())
            if isinstance(v, str):
                normalized[norm_k] = _clean_state_text(v)

    wardrobe_val = None
    injuries_val = None
    expr_val = None

    if t_field == "all":
        wardrobe_val = normalized.get("wardrobe")
        injuries_val = normalized.get("injuries_and_wear")
        expr_val = normalized.get("expression_anchor")
        if not wardrobe_val or not injuries_val or not expr_val:
            procedural = _procedural_state_generator(
                char.name,
                char.base_prompt,
                payload.state_code,
                target_field="all",
                previous_value=payload.previous_value,
                current_values=payload.current_values,
                is_regeneration=payload.is_regeneration,
            )
            wardrobe_val = wardrobe_val or procedural.get("wardrobe")
            injuries_val = injuries_val or procedural.get("injuries_and_wear")
            expr_val = expr_val or procedural.get("expression_anchor")
    elif t_field == "wardrobe":
        wardrobe_val = normalized.get("wardrobe")
        if not wardrobe_val:
            procedural = _procedural_state_generator(
                char.name,
                char.base_prompt,
                payload.state_code,
                target_field="wardrobe",
                previous_value=payload.previous_value,
                current_values=payload.current_values,
                is_regeneration=True,
            )
            wardrobe_val = procedural.get("wardrobe")
    elif t_field in ("injuries", "injuries_and_wear"):
        injuries_val = normalized.get("injuries_and_wear")
        if not injuries_val:
            procedural = _procedural_state_generator(
                char.name,
                char.base_prompt,
                payload.state_code,
                target_field="injuries",
                previous_value=payload.previous_value,
                current_values=payload.current_values,
                is_regeneration=True,
            )
            injuries_val = procedural.get("injuries_and_wear")
    elif t_field in ("expression", "expression_anchor"):
        expr_val = normalized.get("expression_anchor")
        if not expr_val:
            procedural = _procedural_state_generator(
                char.name,
                char.base_prompt,
                payload.state_code,
                target_field="expression",
                previous_value=payload.previous_value,
                current_values=payload.current_values,
                is_regeneration=True,
            )
            expr_val = procedural.get("expression_anchor")

    return {
        "status": "success",
        "data": {
            "state_code": payload.state_code,
            "target_field": t_field,
            "wardrobe": wardrobe_val,
            "injuries_and_wear": injuries_val,
            "expression_anchor": expr_val,
        },
    }


@router.put("/characters/{character_id}/states/{state_id}", status_code=status.HTTP_200_OK)
async def update_character_state(
    character_id: str,
    state_id: str,
    payload: CharacterStateUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Update an existing character state (#State 01-#State 05)."""
    c_uuid = _parse_uuid(character_id, "character_id")
    s_uuid = _parse_uuid(state_id, "state_id")
    state_stmt = select(CharacterStateModel).where(
        CharacterStateModel.id == s_uuid,
        CharacterStateModel.character_id == c_uuid,
    )
    state = (await session.execute(state_stmt)).scalar_one_or_none()
    if not state:
        raise HTTPException(status_code=404, detail="Character state not found")

    if payload.scene_id is not None:
        state.scene_id = _safe_uuid(payload.scene_id)
    if payload.state_code is not None:
        state.state_code = payload.state_code
    if payload.state_label is not None:
        state.state_label = payload.state_label
    if payload.wardrobe is not None:
        state.wardrobe = payload.wardrobe
    if payload.injuries_and_wear is not None:
        state.injuries_and_wear = payload.injuries_and_wear
    if payload.expression_anchor is not None:
        state.expression_anchor = payload.expression_anchor

    await session.commit()
    await session.refresh(state)

    return {
        "data": {
            "id": str(state.id),
            "character_id": str(state.character_id),
            "state_code": state.state_code,
            "state_label": state.state_label or state.state_code,
            "wardrobe": state.wardrobe,
            "injuries_and_wear": state.injuries_and_wear,
            "expression_anchor": state.expression_anchor,
            "scene_id": str(state.scene_id) if state.scene_id else None,
            "image_url": state.image_url,
            "created_at": state.created_at.isoformat(),
        }
    }


@router.delete("/characters/{character_id}/states/{state_id}", status_code=status.HTTP_200_OK)
async def delete_character_state(
    character_id: str,
    state_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Delete a character dynamic state."""
    c_uuid = _parse_uuid(character_id, "character_id")
    s_uuid = _parse_uuid(state_id, "state_id")
    state_stmt = select(CharacterStateModel).where(
        CharacterStateModel.id == s_uuid,
        CharacterStateModel.character_id == c_uuid,
    )
    state = (await session.execute(state_stmt)).scalar_one_or_none()
    if not state:
        raise HTTPException(status_code=404, detail="Character state not found")

    await session.delete(state)
    await session.commit()

    return {
        "status": "success",
        "message": "Character state deleted successfully",
        "id": str(s_uuid),
    }


def _url_to_local_path(url: str | None) -> str | None:
    """Resolve API/web preview URL to an absolute filesystem path for local workers."""
    if not url:
        return None
    clean = url.split("?")[0].strip()
    settings = get_settings()

    # Previews storage
    for prefix in ("/api/v1/assets/previews/", "/assets/previews/"):
        if clean.startswith(prefix):
            fn = clean[len(prefix):]
            p = settings.effective_preview_storage_path / fn
            if p.exists():
                return str(p.resolve())
            rel_p = Path("./data/assets/previews") / fn
            if rel_p.exists():
                return str(rel_p.resolve())

    # Temporary previews storage
    for prefix in (
        "/api/v1/assets/temp-previews/",
        "/api/v1/assets/temp_previews/",
        "/assets/temp-previews/",
        "/assets/temp_previews/",
    ):
        if clean.startswith(prefix):
            fn = clean[len(prefix):]
            p = settings.effective_preview_storage_path.parent / "temp_previews" / fn
            if p.exists():
                return str(p.resolve())
            rel_p = Path("./data/assets/temp_previews") / fn
            if rel_p.exists():
                return str(rel_p.resolve())

    # Media images
    if clean.startswith("/media/images/"):
        fn = clean.replace("/media/images/", "")
        p = Path("/var/www/producer-media/images") / fn
        if p.exists():
            return str(p.resolve())

    if os.path.exists(clean):
        return str(Path(clean).resolve())
    return None


def cleanup_stale_temp_previews(max_age_seconds: int = 86400):
    """Purge temporary preview folders older than 24 hours."""
    try:
        settings = get_settings()
        temp_base = settings.effective_preview_storage_path.parent / "temp_previews"
        if not temp_base.exists():
            temp_base = Path("./data/assets/temp_previews")
        if not temp_base.exists():
            return
        now = time.time()
        for item in temp_base.iterdir():
            if item.is_dir():
                try:
                    if now - item.stat().st_mtime > max_age_seconds:
                        shutil.rmtree(item, ignore_errors=True)
                except Exception:
                    pass
    except Exception:
        pass


def validate_raster_image_bytes(data: bytes, min_size: int = 2048) -> tuple[str, str]:
    """
    Validate that bytes represent a valid raster image (PNG, JPEG, WebP) with size > min_size.
    Rejects SVG, HTML, empty/truncated files, or non-raster payloads.
    Returns: (extension including dot e.g. '.png', mime_type e.g. 'image/png')
    Raises: HTTPException(502) if invalid.
    """
    # Check for text/svg/html first
    prefix_lower = (data[:256] if data else b"").lower()
    if b"<svg" in prefix_lower or b"<?xml" in prefix_lower or b"<!doctype" in prefix_lower or b"<html" in prefix_lower:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="SVG / vector markup is strictly rejected. Only binary raster formats (PNG, JPEG, WebP) are allowed as biometric anchors.",
        )

    if not data or len(data) <= min_size:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Preview image payload is empty or smaller than minimum allowed threshold ({len(data) if data else 0} bytes <= {min_size} bytes). Staged file must be valid raster binary.",
        )

    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image/jpeg"
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP":
        return ".webp", "image/webp"

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="Invalid image magic bytes: Only binary raster images (PNG, JPEG, WebP) are accepted.",
    )


def validate_raster_image_file(file_path: Path | str, min_size: int = 2048) -> tuple[str, str]:
    """Inspect file on disk and validate raster magic bytes and size."""
    p = Path(file_path)
    if not p.is_file() or not p.exists():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Preview image file not found on disk: {p}",
        )
    return validate_raster_image_bytes(p.read_bytes(), min_size=min_size)


def process_uploaded_image(file_bytes: bytes, max_dimension: int = 2048) -> tuple[bytes, int, int]:
    """Normalize smartphone upload: register HEIF, fix EXIF orientation, convert RGB/RGBA, downscale if > 2048px."""
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except Exception:
        pass

    try:
        img = Image.open(io.BytesIO(file_bytes))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uploaded file is not a valid or readable image: {str(exc)}",
        )

    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")

    w, h = img.size
    longest = max(w, h)
    if longest > max_dimension:
        scale = max_dimension / float(longest)
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        img = img.resize((new_w, new_h), resample=Image.Resampling.LANCZOS)
        w, h = img.size

    out_buf = io.BytesIO()
    img.save(out_buf, format="PNG", optimize=True)
    return out_buf.getvalue(), w, h


STANDARD_STUDIO_BACKGROUND = (
    "isolated on a flat seamless Neutral Matte Light-Medium Studio Gray (#D4D4D4) studio background, "
    "even softbox lighting, zero environment props or color cast, "
    "plain solid neutral light-medium studio gray seamless backdrop (#D4D4D4), "
    "flat matte cyclorama background, completely empty background, zero scenery, "
    "zero props, even soft diffused neutral studio lighting, clean character reference sheet, "
    "isolated full subject"
)

STUDIO_EXCLUSION_DIRECTIVE = (
    "no background scenery, no environment, no landscape, no interior room, "
    "no architecture, no bokeh background, no dramatic colored rim light, "
    "no props, no text, no watermark"
)


def _clean_style_directives_for_character_sheet(text: str, is_stylized: bool = False) -> str:
    """Strip scenic, environmental, weather, and camera motion overrides from style directives."""
    import re
    conflicts = [
        "lush watercolor nature backgrounds",
        "painterly flora",
        "whimsical wind gusts",
        "hyper-detailed sky cloud formations",
        "photorealistic god rays",
        "glistening water reflections",
        "ancient moss-covered masonry",
        "sweeping nordic landscape horizons",
        "melancholic cityscapes",
        "gritty steampunk industrialism",
        "physical miniature set materials",
        "stylized rain downpours",
        "hard-boiled detective noir",
        "warm bamboo and teak wood textures",
        "tropical humidity haze",
        "practical oil-lamp glows",
        "debris-laden air",
        "theatrical wind machines",
        "ethereal mist",
        "pastel atmospheric scattering",
        "low-angle hero rotation",
        "sweeping crane movements",
        "saturated golden hour",
        "heavy tungsten edge lighting",
        "gentle naturalistic backlighting",
        "overcast northern european lighting",
        "sunset magentas",
        "warm golden light",
        "neon reflections, wet asphalt",
        "deep space contrast, sterile chrome, orbital scale",
        "volumetric luminescence, ancient lore, epic vistas",
        "vibrant cloudscapes",
    ]
    cleaned = text
    for c in conflicts:
        cleaned = re.sub(re.escape(c) + r"[,.]?", "", cleaned, flags=re.IGNORECASE)
    if is_stylized:
        cleaned = re.sub(r"\bphotorealistic\b", "expressive", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r",\s*,+", ",", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.")
    if cleaned and not cleaned.endswith("."):
        cleaned += "."
    if is_stylized:
        return cleaned or "Crisp clean linework, dimensional anime cel-shading, vibrant character palette."
    return cleaned or "Pristine dynamic range, lifelike skin pores, crisp micro-texture detail."


def _clean_color_grade_for_character_sheet(text: str, is_stylized: bool = False) -> str:
    """Strip environmental and location lighting overrides from color grade emulation."""
    import re
    conflicts = [
        "heavy tungsten edge lighting",
        "gentle naturalistic backlighting",
        "overcast northern european lighting",
        "sunset magentas",
        "warm golden light",
        "warm tungsten shadows",
        "glistening water reflections",
        "creamy bokeh highlights",
    ]
    cleaned = text
    for c in conflicts:
        cleaned = re.sub(re.escape(c) + r"[,.]?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r",\s*,+", ",", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.")
    if cleaned and not cleaned.endswith("."):
        cleaned += "."
    if is_stylized:
        return cleaned or "Pure neutral white balance, vibrant anime palette emulation."
    return cleaned or "Naturalistic color timing, neutral balanced 65mm sensor reproduction."


def _extract_biometric_and_collar(base_prompt: str, char_name: str | None = None) -> tuple[str, str]:
    """Extract clean affirmative anatomical profile and collar/wardrobe details for ultra-realistic Imagen 3 prose.

    Strips character names (to prevent ethnic/text bias), brackets, bullets, hex codes, framing/lighting conflicts,
    and extracts/falls back wardrobe collar without grammatical artifacts.
    """
    import re

    text = (base_prompt or "").strip()

    # Strip square brackets headers, bullets, and literal hex color codes (#D4D4D4, etc.)
    text = re.sub(r"#[0-9a-fA-F]{3,6}", "", text)
    text = re.sub(r"\[.*?\]", "", text)
    text = text.replace("•", "").replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text).strip(" ,.")

    # Strip character name and preceding 'name:' indicators to prevent ethnic/name bias in visual prompt
    if char_name:
        text = re.sub(
            rf"(?:^|\b)(?:name\s*[:=]\s*)?{re.escape(char_name)}\b[\s,:\-—]*(?:is\s+)?",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip(" ,.")

    # Strip leading 'Cinematic close-up portrait of' or 'Portrait of'
    text = re.sub(r"^(?:cinematic\s+)?(?:close-up\s+|headshot\s+)?portrait\s+of\s+", "", text, flags=re.IGNORECASE).strip(" ,.")

    # Strip camera shot, framing, and angle conflicts (e.g., 'displayed in a cinematic wide-angle shot')
    framing_patterns = [
        r"(?:displayed|captured|framed|filmed|shot|seen)?\s*(?:in\s+)?(?:a\s+)?(?:cinematic\s+)?(?:wide-angle|wide\s+shot|medium\s+shot|close-up|extreme\s+close-up|full-body|establishing\s+shot|over-the-shoulder|dutch\s+angle|low\s+angle|high\s+angle|isometric|action\s+pose|profile\s+view)\s*(?:shot|view|angle|framing|perspective)?(?:\s+with\s+[^,.;]*(?:contrast|lighting|light))?",
        r"displayed in [^,.;]*(?:shot|view|angle|framing|contrast|lighting)[^,.;]*",
        r"(?:captured|framed|filmed|shot|seen)\s+in\s+[^,.;]*(?:shot|view|angle|framing|contrast|lighting)[^,.;]*",
    ]
    for fp in framing_patterns:
        text = re.sub(fp, "", text, flags=re.IGNORECASE).strip(" ,.")

    # Strip lighting overrides or colored spill descriptions embedded in base prompt
    lighting_spill_patterns = [
        r"(?:with\s+)?(?:high-octane|cinematic|dramatic|moody|harsh|neon|volumetric|naturalistic|golden\s+hour|sunset|rim|tungsten|shadowy|chiaroscuro)\s*(?:lighting|light|contrast|illumination|ambiance|atmosphere|flare|reflections?)",
        r"(?:that|which)?\s*casts?\s+[^,.;]*(?:light|glow|reflection)[^,.;]*(?:onto|on)\s+[^,.;]*",
        r"captured in [^,.;]+(?:lighting|flares)[^,.;]*",
        r"with intense (?:lens )?flares[^,.;]*",
        r"with glowing [^,.;]*",
        r"glowing\s+",
    ]
    for lp in lighting_spill_patterns:
        text = re.sub(lp, "", text, flags=re.IGNORECASE).strip(" ,.")

    # Strip trailing background overrides embedded in base prompt to keep studio cyclorama clean
    studio_boilerplate_patterns = [
        r",?\s*isolated\s+(?:on|in|against)\s+a\s+flat\s+(?:seamless|neutral).*",
        r",?\s*(?:even\s+)?softbox\s+lighting.*",
        r",?\s*zero\s+environment\s+props.*",
        r",?\s*(?:clean\s+)?studio\s+background.*",
        r",?\s*uniform\s+(?:non-directional\s+)?illumination.*",
        r",?\s*character\s+model\s+sheet\s+background.*",
        r",?\s*captured\s+with\s+a\s+shallow\s+depth\s+of\s+field.*",
        r"\b(?:standing|isolated)\s*(?:on|in|against)?\s*$",
    ]
    for sbp in studio_boilerplate_patterns:
        text = re.sub(sbp, "", text, flags=re.IGNORECASE).strip(" ,.")

    # Normalize punctuation and whitespace
    text = re.sub(r",\s*\.", ".", text)
    text = re.sub(r",\s*,+", ",", text)
    text = re.sub(r"\s+", " ", text).strip(" ,.")

    # Wardrobe collar extraction from base_prompt
    clothing_patterns = [
        r"(?:he\s+wears|she\s+wears|they\s+wear|the\s+character\s+wears|wearing|dressed in|outfitted in|styled with)\s+([^,.;]+(?:\bcollar\b|jacket|coat|shirt|suit|sweater|hoodie|uniform|vest|turtleneck|crewneck|armor|trenchcoat|tunic|gown|dress|robe|hanfu|bodysuit|cape|cloak|blouse)[^,.;]*)",
        r"([^,.;]*(?:\bcollar\b|jacket|coat|shirt|suit|sweater|hoodie|uniform|vest|turtleneck|crewneck|armor|trenchcoat|tunic|gown|dress|robe|hanfu|bodysuit|cape|cloak|blouse)[^,.;]*)",
    ]
    wardrobe_collar = "a simple neutral charcoal-gray crewneck collar"
    for pat in clothing_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            item = m.group(1).strip()
            # Strip subject pronouns and verbs to prevent 'a He wears...'
            item = re.sub(r"^(?:he\s+wears|she\s+wears|they\s+wear|the\s+character\s+wears|wearing|dressed in|outfitted in|styled with)\s+", "", item, flags=re.IGNORECASE).strip()
            item = re.sub(r"^(?:a|an|the)\s+", "", item, flags=re.IGNORECASE).strip()
            if re.search(r"\bcollar\b", item, re.IGNORECASE):
                wardrobe_collar = f"a {item}"
            elif any(k in item.lower() for k in ("vest", "gown", "dress", "robe", "hanfu", "jacket", "suit", "armor", "hoodie", "sweater", "tunic", "top", "blouse", "shirt", "crewneck", "turtleneck")):
                wardrobe_collar = f"a {item}"
            else:
                wardrobe_collar = f"a {item} collar"
            break

    # Strip lighting spill and glow phrases from wardrobe_collar to preserve pure neutral illumination
    for lp in [
        r"(?:that|which)?\s*casts?\s+[^,.;]*(?:light|glow|reflection)[^,.;]*(?:onto|on)\s+[^,.;]*",
        r"glowing\s+",
        r"with glowing [^,.;]*",
    ]:
        wardrobe_collar = re.sub(lp, "", wardrobe_collar, flags=re.IGNORECASE).strip(" ,.")

    # Clean double articles
    wardrobe_collar = re.sub(r"^a\s+(?:a|an|the)\s+", "a ", wardrobe_collar, flags=re.IGNORECASE).strip()

    biometric_profile = text or "an authentic human individual"
    return biometric_profile, wardrobe_collar


def _sanitize_character_base_prompt(base_prompt: str) -> str:
    """Sanitize base_prompt by stripping studio boilerplate, hex codes, and bracket headers."""
    import re
    text = (base_prompt or "").strip()
    # Strip square brackets headers, bullets, and literal hex color codes (#D4D4D4, etc.)
    text = re.sub(r"#[0-9a-fA-F]{3,6}", "", text)
    text = re.sub(r"\[.*?\]", "", text)
    text = text.replace("•", "").replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text).strip(" ,.")

    studio_boilerplate_patterns = [
        r",?\s*isolated\s+(?:on|in|against)\s+a\s+flat\s+(?:seamless|neutral).*",
        r",?\s*(?:even\s+)?softbox\s+lighting.*",
        r",?\s*zero\s+environment\s+props.*",
        r",?\s*(?:clean\s+)?studio\s+background.*",
        r",?\s*uniform\s+(?:non-directional\s+)?illumination.*",
        r",?\s*character\s+model\s+sheet\s+background.*",
        r",?\s*captured\s+with\s+a\s+shallow\s+depth\s+of\s+field.*",
        r"\b(?:standing|isolated)\s*(?:on|in|against)?\s*$",
    ]
    for sbp in studio_boilerplate_patterns:
        text = re.sub(sbp, "", text, flags=re.IGNORECASE).strip(" ,.")

    text = re.sub(r",\s*\.", ".", text)
    text = re.sub(r",\s*,+", ",", text)
    return re.sub(r"\s+", " ", text).strip(" ,.")


def _extract_full_body_costume(base_prompt: str, wardrobe_collar: str, char_name: str | None = None) -> str:
    """Extract complete head-to-toe costume description for full-body and turnaround casting sheets.

    Ensures consistent, complete wardrobe description without brackets, hex codes, or country/name bias.
    """
    import re

    text = (base_prompt or "").strip()

    # Strip square brackets headers, bullets, and literal hex color codes (#D4D4D4, etc.)
    text = re.sub(r"#[0-9a-fA-F]{3,6}", "", text)
    text = re.sub(r"\[.*?\]", "", text)
    text = text.replace("•", "").replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text).strip(" ,.")

    # Strip character name and preceding 'name:' indicators to prevent ethnic/name bias
    if char_name:
        text = re.sub(
            rf"(?:^|\b)(?:name\s*[:=]\s*)?{re.escape(char_name)}\b[\s,:\-—]*(?:is\s+)?",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip(" ,.")

    # Strip lighting overrides or colored spill descriptions
    lighting_spill_patterns = [
        r"(?:with\s+)?(?:high-octane|cinematic|dramatic|moody|harsh|neon|volumetric|naturalistic|golden\s+hour|sunset|rim|tungsten|shadowy|chiaroscuro)\s*(?:lighting|light|contrast|illumination|ambiance|atmosphere|flare|reflections?)",
        r"(?:that|which)?\s*casts?\s+[^,.;]*(?:light|glow|reflection)[^,.;]*(?:onto|on)\s+[^,.;]*",
        r"captured in [^,.;]+(?:lighting|flares)[^,.;]*",
        r"with intense (?:lens )?flares[^,.;]*",
        r"glowing\s+",
        r"with glowing [^,.;]*",
    ]
    for lp in lighting_spill_patterns:
        text = re.sub(lp, "", text, flags=re.IGNORECASE).strip(" ,.")

    # Strip trailing background overrides embedded in base prompt to keep wardrobe clean
    studio_boilerplate_patterns = [
        r",?\s*isolated\s+(?:on|in|against)\s+a\s+flat\s+(?:seamless|neutral).*",
        r",?\s*(?:even\s+)?softbox\s+lighting.*",
        r",?\s*zero\s+environment\s+props.*",
        r",?\s*(?:clean\s+)?studio\s+background.*",
        r",?\s*uniform\s+(?:non-directional\s+)?illumination.*",
        r",?\s*character\s+model\s+sheet\s+background.*",
        r",?\s*captured\s+with\s+a\s+shallow\s+depth\s+of\s+field.*",
        r"\b(?:standing|isolated)\s*(?:on|in|against)?\s*$",
    ]
    for sbp in studio_boilerplate_patterns:
        text = re.sub(sbp, "", text, flags=re.IGNORECASE).strip(" ,.")

    # Detect explicit sleeve attributes if mentioned anywhere in text
    sleeve_match = re.search(
        r"\b(sleeveless|short-sleeved|short\s+sleeves?|long-sleeved|long\s+sleeves?|flutter\s+sleeves?|cap\s+sleeves?|rolled-up\s+sleeves?|puffy\s+sleeves?|bell\s+sleeves?|elbow-length\s+sleeves?)\b",
        text,
        re.IGNORECASE,
    )
    explicit_sleeve = sleeve_match.group(1).lower() if sleeve_match else None

    costume_patterns = [
        r"(?:he\s+wears|she\s+wears|they\s+wear|the\s+character\s+wears|wearing|dressed in|outfitted in|styled with)\s+([^.;]+(?:\bcollar\b|jacket|coat|suit|uniform|vest|tunic|armor|trenchcoat|sweater|trousers|pants|boots|shoes|overalls|jumpsuit|robe|cloak|gown|dress|hanfu|cheongsam|qipao|skirt|bodysuit|sleeveless)[^.;]*)",
        r"([^.;]*(?:trousers|pants|combat boots|leather boots|utility belt|tactical gear|full suit|uniform|gown|dress|robe|hanfu|skirt|jumpsuit)[^.;]*)",
    ]
    extracted_costume = ""
    for pat in costume_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            extracted_costume = m.group(1).strip()
            extracted_costume = re.sub(r"^(?:he\s+wears|she\s+wears|they\s+wear|the\s+character\s+wears|wearing|dressed in|outfitted in|styled with)\s+", "", extracted_costume, flags=re.IGNORECASE).strip(" ,.")
            break

    if extracted_costume:
        for sbp in studio_boilerplate_patterns:
            extracted_costume = re.sub(sbp, "", extracted_costume, flags=re.IGNORECASE).strip(" ,.")

    # Lower body & full body keywords
    full_body_and_lower_keywords = [
        "pants", "trouser", "boot", "shoe", "leg", "skirt", "suit", "uniform",
        "jumpsuit", "overalls", "cloak", "robe", "tunic", "gown", "dress",
        "hanfu", "cheongsam", "qipao", "kimono", "bodysuit"
    ]
    is_full_or_lower = extracted_costume and any(k in extracted_costume.lower() for k in full_body_and_lower_keywords)

    if is_full_or_lower:
        clean_ext = re.sub(r"^(?:he\s+wears|she\s+wears|they\s+wear|the\s+character\s+wears|wearing|dressed in|outfitted in|styled with)\s+", "", extracted_costume, flags=re.IGNORECASE).strip()
        clean_ext = re.sub(r"^(?:a|an|the)\s+", "", clean_ext, flags=re.IGNORECASE).strip()
        if explicit_sleeve and explicit_sleeve not in clean_ext.lower():
            clean_ext = f"{clean_ext} with {explicit_sleeve}"
        return f"a {clean_ext}"

    # If only upper garment was extracted or wardrobe_collar is available, synthesize complete head-to-toe costume
    clean_collar = wardrobe_collar
    clean_collar = re.sub(r"^(?:he\s+wears|she\s+wears|they\s+wear|the\s+character\s+wears|wearing|dressed in|outfitted in|styled with)\s+", "", clean_collar, flags=re.IGNORECASE).strip()
    for prefix in ["a ", "an ", "the "]:
        if clean_collar.lower().startswith(prefix):
            clean_collar = clean_collar[len(prefix):]
            break

    for sbp in studio_boilerplate_patterns:
        clean_collar = re.sub(sbp, "", clean_collar, flags=re.IGNORECASE).strip(" ,.")

    # Safe collar normalization without truncation (preventing 'high-collar' -> 'high-')
    if clean_collar.lower().endswith(" collar"):
        costume_base = clean_collar[:-7].strip(" ,.")
    elif "-collar" in clean_collar.lower():
        costume_base = re.sub(r"(\w+)-collar\b", r"\1-collared", clean_collar, flags=re.IGNORECASE)
        costume_base = re.sub(r"\bcollar\b", "", costume_base, flags=re.IGNORECASE).strip(" ,.")
    elif "collar" in clean_collar.lower():
        costume_base = re.sub(r"\bcollar\b", "", clean_collar, flags=re.IGNORECASE).strip(" ,.")
    else:
        costume_base = clean_collar

    for sbp in studio_boilerplate_patterns:
        costume_base = re.sub(sbp, "", costume_base, flags=re.IGNORECASE).strip(" ,.")

    costume_base = re.sub(r"^(?:a|an|the)\s+", "", costume_base, flags=re.IGNORECASE).strip()
    costume_base = re.sub(r"\s+", " ", costume_base).strip(" ,.")

    # Check if costume_base is a full-body garment (never append trousers to gowns/dresses/robes)
    full_body_garments = ["gown", "dress", "robe", "hanfu", "cheongsam", "qipao", "kimono", "jumpsuit", "overalls", "bodysuit"]
    if any(g in costume_base.lower() for g in full_body_garments):
        if explicit_sleeve and explicit_sleeve not in costume_base.lower():
            costume_base = f"{costume_base} with {explicit_sleeve}"
        return f"a {costume_base} and clean minimalist studio footwear"

    # For upper garments, pair with matching trousers
    if explicit_sleeve and explicit_sleeve not in costume_base.lower():
        costume_base = f"{costume_base} with {explicit_sleeve}"
    return f"a {costume_base} paired with tailored matching trousers and clean minimalist studio footwear"


def compile_sheet_prompt(
    character: CharacterModel,
    project: ProjectModel | None,
    bible: MasterProductionBibleModel | None,
    slot: str,
    target_state: CharacterStateModel | None = None,
    prompt_override: str | None = None,
    aspect_ratio: str | None = None,
) -> dict[str, Any]:
    """Pure compiler producing project-synced master prompts for any of the 8 cards or dynamic states."""
    norm_slot = (slot or "closeup").lower().strip()
    if norm_slot in ("closeup", "close_up", "headshot", "portrait", "master_closeup", "slot_1"):
        slot_key = "closeup"
    elif norm_slot in ("three_quarter", "3/4", "threequarter", "turnaround_three_quarter"):
        slot_key = "three_quarter"
    elif norm_slot in ("tpose", "sheet_tpose", "t_pose"):
        slot_key = "tpose"
    elif norm_slot in ("action", "sheet_action"):
        slot_key = "action"
    elif norm_slot in ("expression", "sheet_expression"):
        slot_key = "expression"
    elif norm_slot in ("back", "turnaround_back"):
        slot_key = "back"
    elif norm_slot in ("side", "turnaround_side"):
        slot_key = "side"
    elif norm_slot == "state":
        slot_key = "state"
    else:
        slot_key = "front"

    # Deterministic DNA Seed
    dna_seed = character.dna_seed or (int(hashlib.sha256(str(character.id).encode()).hexdigest()[:8], 16) % 900000 + 100000)

    # Resolve Master Visual Style and Aesthetic Directives from MPB, Project, or Catalog
    style_code = (
        (bible.style_parameters.get("master_style_code") if bible and bible.style_parameters else None)
        or (project.target_style_code if project else None)
        or "#Style 01"
    )

    style_def = next((s for s in STYLE_CATALOG if s.get("code") == style_code), None) or STYLE_CATALOG[0]
    style_name = str(style_def.get("name") or "Hollywood Cinematic")
    style_family = str(style_def.get("family") or "")

    aesthetic_directives = (
        bible.style_parameters.get("aesthetic_directives")
        if bible and bible.style_parameters and bible.style_parameters.get("aesthetic_directives")
        else style_def.get("aesthetic_directives", "")
    )
    color_grade_emulation = (
        bible.style_parameters.get("color_grade_emulation")
        if bible and bible.style_parameters and bible.style_parameters.get("color_grade_emulation")
        else style_def.get("color_grade_emulation", "")
    )
    project_title = (project.title if project else "") or ""

    combined_style = f"{style_name} {style_code} {style_family}".lower()
    is_stylized = any(
        k in combined_style
        for k in ("anime", "cartoon", "2d", "comic", "manga", "pixar", "claymation", "illustration")
    )

    clean_directives = _clean_style_directives_for_character_sheet(aesthetic_directives, is_stylized=is_stylized)
    clean_palette = _clean_color_grade_for_character_sheet(color_grade_emulation, is_stylized=is_stylized)

    # Runtime boilerplate sanitization on base_prompt to purge any leaked studio tags or softbox terms
    sanitized_base_prompt = _sanitize_character_base_prompt(character.base_prompt)

    biometric_profile, wardrobe_collar = _extract_biometric_and_collar(
        sanitized_base_prompt,
        char_name=character.name,
    )
    full_body_costume = _extract_full_body_costume(
        sanitized_base_prompt,
        wardrobe_collar=wardrobe_collar,
        char_name=character.name,
    )

    char_name = character.name.strip() if character.name and character.name.strip() else "the subject"

    # Card Technical Directives & Framing Specifications
    if slot_key == "closeup":
        card_title = "Card 1: Character Close-Up (Master Anchor)"
        card_aspect = aspect_ratio or "3:4"
        width, height = (768, 1024)
        ref_candidates = []
        if getattr(character, "face_ref_asset_id", None):
            ref_candidates.append(("Face Reference Asset", str(character.face_ref_asset_id)))

        if is_stylized:
            if ref_candidates:
                positive_prompt = (
                    f"Analyze the reference 2D illustration and strictly preserve the character's exact 2D anime identity, "
                    f"facial proportions, eye shape, iris design and color, nose and mouth geometry, hair silhouette and color, "
                    f"and distinguishing features exactly as they are. Re-render the character as a clean 2D anime character model sheet "
                    f"close-up casting portrait framed from the crown of the head to the upper collarbone. Re-align to a direct frontal, "
                    f"strict eye-level camera angle with head upright and centered, both ears clearly visible, a calm neutral resting "
                    f"expression, naturally closed mouth, and direct eye contact. Strictly preserve authentic {style_name} 2D anime aesthetic: "
                    f"crisp ink lineart, flat and subtle dimensional cel-shading, vibrant animation color palette ({clean_palette}), and zero photographic conversion. "
                    f"Illuminated by pure neutral studio illumination with zero colored light spill on the chin or neck. "
                    f"Isolated cleanly against a solid, uniform, seamless matte neutral gray studio backdrop. "
                    f"Dress the upper shoulders in {wardrobe_collar} with the neck fully visible."
                )
            else:
                positive_prompt = (
                    f"Clean studio animation character model sheet casting portrait of {biometric_profile}. "
                    f"Tight head-and-shoulders close-up framed cleanly from the top of the head down to the base of the neck "
                    f"and upper collarbone. Direct frontal view at exact eye-level, head held upright and centered facing straight ahead "
                    f"with both ears, cheekbones, and jawline equally visible and unobstructed. Completely calm, relaxed neutral "
                    f"resting expression with naturally closed lips and steady, direct eye contact into the lens. "
                    f"Authentic {style_name} animation visual style with crisp ink linework, dimensional cel-shading, and balanced facial proportions ({clean_directives}). "
                    f"Illuminated by pure neutral studio illumination with no colored light spill on the chin or neck, with true neutral white balance ({clean_palette}). "
                    f"Isolated cleanly against a completely uniform, seamless matte neutral gray studio paper backdrop. Wearing {wardrobe_collar} "
                    f"that keeps the entire neck and jawline cleanly visible."
                )
        else:
            if ref_candidates:
                positive_prompt = (
                    f"Analyze the reference photograph and strictly preserve the exact person's biometric identity, "
                    f"bone structure, eye shape, iris color, nose bridge, lip shape, natural skin tone, age, ethnicity, "
                    f"hair texture, and distinguishing facial marks exactly as they are. Re-render the subject as an "
                    f"unretouched RAW photographic studio casting close-up portrait framed from the crown of the head "
                    f"to the upper collarbone. Re-align to a direct frontal, strict eye-level camera angle with head "
                    f"upright and centered, both ears clearly visible, a calm neutral resting expression, naturally "
                    f"closed mouth, and direct eye contact with the lens. Preserve authentic raw human skin texture "
                    f"including visible pores, natural skin grain, subtle tonal variations, fine facial hair, under-eye "
                    f"texture, and natural lip lines with a matte finish. Captured on a 100-megapixel medium-format studio camera "
                    f"with a 100mm macro-portrait prime lens at f/5.6, delivering extreme optical micro-contrast, zero wide-angle "
                    f"distortion, and razor-sharp edge-to-edge focus from the tip of the nose, individual eyelashes, eyebrow hairs, "
                    f"and skin pores all the way to both ears, with hyper-crisp iris detail and clean natural catchlights. Replace all original "
                    f"lighting with pure neutral 5500K studio illumination with no colored light spill on the chin or neck, evenly diffused "
                    f"neutral daylight studio softboxes, and isolate the subject against a solid, uniform, seamless matte light-medium "
                    f"neutral gray studio backdrop. Dress the upper shoulders in {wardrobe_collar} with the neck fully visible. "
                    f"Indistinguishable from an unedited real DSLR casting photograph."
                )
            else:
                positive_prompt = (
                    f"Unretouched RAW photographic studio casting portrait of {biometric_profile}. "
                    f"Tight head-and-shoulders close-up framed cleanly from the top of the head down to the base of the neck "
                    f"and upper collarbone. Direct frontal view at exact eye-level, head held upright and centered facing straight ahead "
                    f"with both ears, cheekbones, and jawline equally visible and unobstructed. Completely calm, relaxed neutral "
                    f"resting expression with naturally closed lips and steady, direct eye contact into the lens. Authentic lived-in "
                    f"human skin with genuine microscopic detail: natural visible pores, subtle skin grain, fine vellus peach fuzz, "
                    f"wispy baby hairs along the hairline, true-to-life tonal variation across forehead and cheeks, natural under-eye "
                    f"texture, subtle fine lines, and realistic lip texture with a natural matte finish and physically accurate subsurface "
                    f"scattering. Captured on a 100-megapixel medium-format studio camera with a 100mm macro-portrait prime lens at f/5.6, "
                    f"delivering extreme optical micro-contrast, zero wide-angle distortion, and razor-sharp edge-to-edge focus from the tip "
                    f"of the nose, individual eyelashes, eyebrow hairs, and skin pores all the way to both ears, with hyper-crisp iris detail "
                    f"and clean natural catchlights. Illuminated by pure neutral 5500K neutral daylight studio softboxes with no colored light spill on the chin or neck, "
                    f"balanced softly diffused gentle frontal fill and subtle dimensional micro-shadows with "
                    f"true neutral white balance. Isolated cleanly against a completely uniform, seamless matte light-medium neutral gray "
                    f"studio paper backdrop. Wearing {wardrobe_collar} that keeps the entire neck and jawline cleanly visible. "
                    f"Indistinguishable from an unedited DSLR casting photograph."
                )

    elif slot_key == "expression":
        card_title = "Card 2: Expression Sheet (3x2 Micro-Expressions Grid)"
        card_aspect = aspect_ratio or "16:9"
        width, height = (1344, 768)  # Sharp 16:9 resolution
        ref_candidates = []
        if getattr(character, "closeup_image_url", None):
            ref_candidates.append(("Card 1 Character Close-Up", character.closeup_image_url))

        if is_stylized:
            if ref_candidates:
                positive_prompt = (
                    f"Animation character expression model sheet contact montage composed of exactly six equal distinct portrait panels "
                    f"arranged in a rigid 3-column by 2-row grid on a single horizontal canvas, featuring {char_name}, {biometric_profile}. "
                    "Capturing the exact same 2D anime character from the reference close-up illustration. "
                    "Strictly preserve 100% character identity, facial proportions, cranial structure, expressive anime eye shape, iris design and pigmentation, "
                    f"ear geometry, hairstyle and silhouette, and consistent wardrobe collar ({wardrobe_collar}) across all six panels. "
                    f"Maintain consistent authentic {style_name} 2D anime aesthetic ({clean_palette}): crisp ink lineart, delicate cel-shading, and clean animated color fills "
                    "exclusively rendered with clean animated 2D flat fills and crisp cel-shaded shadows, completely free of photographic conversion. "
                    "Top row from left to right: calm neutral resting face with relaxed closed lips, "
                    "subtle genuine smile with bright expressive anime eyes and relaxed cheeks, and intense controlled anger with tightened jawline and furrowed brows. "
                    "Bottom row from left to right: quiet sorrow and grief with softened downward gaze, sudden shock and astonishment with widened eyes and slightly parted lips, "
                    "and wary sharp suspicion with narrowed focused eyes. Each individual panel maintains consistent head-and-shoulders framing at eye level "
                    "under pure neutral studio illumination against a seamless matte neutral gray studio backdrop. "
                    "Clean division lines separating panels, pristine animation character model sheet."
                )
            else:
                positive_prompt = (
                    f"Clean studio animation character model sheet expression sheet arranged in a rigid 3-column by 2-row grid "
                    f"(six equal distinct portrait panels) of {char_name}, {biometric_profile}. Authentic {style_name} animation visual style "
                    f"with crisp linework and dimensional cel-shading ({clean_directives}). Strictly preserve character identity, facial proportions, hair, and wardrobe ({wardrobe_collar}) "
                    "across all six panels. Top row from left to right: calm neutral resting face with relaxed closed lips, subtle genuine smile with expressive eyes, "
                    "and intense controlled anger with tightened jawline and furrowed brows. Bottom row from left to right: quiet sorrow and grief with softened downward gaze, "
                    "sudden shock and astonishment with widened eyes and slightly parted lips, and wary sharp suspicion with narrowed focused eyes. "
                    "Each panel maintains consistent head-and-shoulders framing at eye level under pure neutral studio illumination against a seamless matte neutral gray studio backdrop. "
                    "Clean division lines separating panels."
                )
        else:
            if ref_candidates:
                positive_prompt = (
                    f"Photographic character expression contact sheet montage composed of exactly six equal distinct portrait panels "
                    f"arranged in a rigid 3-column by 2-row grid on a single horizontal canvas, featuring {char_name}, {biometric_profile}. "
                    "Capturing the exact same individual from the reference close-up photograph. "
                    "Strictly preserve 100% facial identity, cranial bone structure, eye shape, iris pigmentation, ear geometry, hair texture and hairline, "
                    f"natural skin markings, and consistent wardrobe collar ({wardrobe_collar}) across all six panels with authentic unretouched human skin texture "
                    "(visible pores, micro-wrinkles, natural skin grain, matte finish). Top row from left to right: calm neutral resting face with relaxed closed lips, "
                    "subtle genuine smile with natural eye crinkles and relaxed cheeks, and intense controlled anger with tightened jawline and furrowed brows. "
                    "Bottom row from left to right: quiet sorrow and grief with softened downward gaze, sudden shock and astonishment with widened eyes and slightly parted lips, "
                    "and wary sharp suspicion with narrowed focused eyes. Each individual panel maintains consistent head-and-shoulders framing at eye level, "
                    "captured with a 100mm portrait lens under identical 5500K neutral daylight studio softboxes against a seamless matte neutral gray (#D4D4D4) studio backdrop. "
                    "Clean division lines separating panels, pristine photographic casting sheet realism."
                )
            else:
                positive_prompt = (
                    f"Photographic character expression sheet arranged in a rigid 3-column by 2-row grid (six equal distinct portrait panels) "
                    f"of {char_name}, {biometric_profile}. Authentic casting sheet with lived-in human skin texture, pores, and natural grain. "
                    f"Strictly preserve character identity, facial bone structure, hair, and wardrobe ({wardrobe_collar}) across all six panels. "
                    "Top row from left to right: calm neutral resting face, subtle genuine smile, and intense controlled anger. "
                    "Bottom row from left to right: quiet sorrow and grief, sudden shock and astonishment, and wary sharp suspicion. "
                    "Each panel framed at eye level, captured with a 100mm portrait lens under identical 5500K neutral daylight studio softboxes against a seamless matte neutral gray (#D4D4D4) studio backdrop. "
                    "Clean division lines separating panels."
                )

    elif slot_key == "side":
        card_title = "Card 4: Side Profile 90° (Profile 90° • Silhouette & Proportions)"
        card_aspect = aspect_ratio or "3:4"
        width, height = (768, 1024)
        ref_candidates = []
        if getattr(character, "closeup_image_url", None):
            ref_candidates.append(("Card 1 Character Close-Up", character.closeup_image_url))
        if getattr(character, "front_image_url", None):
            ref_candidates.append(("Card 3 Full Body Front", character.front_image_url))

        if is_stylized:
            if ref_candidates:
                positive_prompt = (
                    f"Full-body studio animation character model sheet 90-degree lateral side profile portrait of {char_name}, {biometric_profile}. "
                    "Capturing the exact same 2D anime character from the reference close-up and full-body front-view illustrations. "
                    "Full-length strict 90-degree lateral side-profile orthogonal view framed cleanly from top of head down to footwear touching the ground. "
                    "Strictly preserves 2D anime facial profile contour, nose slope, chin, cranial geometry, hair silhouette, and lineart styling from reference images with zero photorealistic conversion. "
                    f"Standing upright in a natural neutral profile posture revealing lateral proportions and complete side costume construction matching {full_body_costume}. "
                    f"Rendered in authentic {style_name} animation style with crisp ink lineart, clean 2D cel-shading, and balanced animation proportions ({clean_palette}). "
                    "Illuminated by balanced neutral studio illumination on a seamless matte neutral gray studio backdrop with soft ground contact shadow."
                )
            else:
                positive_prompt = (
                    f"Clean studio animation character model sheet side profile portrait of {char_name}, {biometric_profile}. "
                    f"Authentic {style_name} animation visual style with crisp linework and dimensional cel-shading. Strict 90-degree lateral side-profile view framed cleanly from top of head down to footwear. "
                    f"Standing upright in a neutral profile posture showing lateral proportions and costume construction matching {full_body_costume}. "
                    f"Illuminated by balanced neutral studio illumination on a seamless matte neutral gray studio backdrop with soft ground contact shadow."
                )
        else:
            if ref_candidates:
                positive_prompt = (
                    f"Unretouched RAW photographic full-body studio casting profile portrait of {char_name}, {biometric_profile}. "
                    "Capturing the exact same individual from the reference close-up and full-body front-view casting photographs. "
                    "Full-length strict 90-degree lateral side-profile orthogonal view framed cleanly from the top of the head down to the soles of the footwear touching the ground with comfortable margins above and below. "
                    "Strictly preserves their exact biometric identity, facial profile topography, cranial structure, jawline contour, nose bridge, ear geometry, hair silhouette, and natural skin texture from the reference images. "
                    "Standing upright in a natural, balanced neutral profile standing posture with arms resting naturally at the sides, revealing precise lateral anatomical proportions, natural posture contour, "
                    f"and complete side costume construction matching {full_body_costume}. "
                    "Captured on a medium-format studio camera with an 85mm prime lens at f/8 for zero focal distortion, crisp edge-to-edge optical clarity, and authentic material textures from head to toe. "
                    "Illuminated by balanced, evenly diffused 5500K neutral daylight studio softboxes with delicate lateral separation and true neutral white balance, with zero colored light spill. "
                    "Isolated cleanly against a seamless, solid, uniform matte neutral gray (#D4D4D4) studio sweep cyclorama backdrop with a soft natural ground contact shadow directly beneath the footwear. "
                    "Indistinguishable from an unedited real wardrobe-fitting profile photograph."
                )
            else:
                positive_prompt = (
                    f"Unretouched RAW photographic full-body studio casting profile portrait of {char_name}, {biometric_profile}. "
                    f"Full-length strict 90-degree lateral side-profile view framed cleanly from top of head down to the soles of the footwear touching the ground. "
                    f"Standing upright in a natural neutral profile posture, revealing precise lateral anatomical proportions, posture contour, and costume construction matching {full_body_costume}. "
                    f"Captured on a medium-format studio camera with an 85mm prime lens at f/8 for zero focal distortion and crisp material textures from head to toe. "
                    f"Illuminated by balanced, softly diffused 5500K neutral daylight studio softboxes with subtle lateral separation on a seamless matte neutral gray (#D4D4D4) studio sweep backdrop with soft ground contact shadow. "
                    f"Indistinguishable from an unedited real costume-fitting profile photograph."
                )

    elif slot_key == "three_quarter":
        card_title = "Card 5: 3/4 Hero Angle (Oblique 45° • Hero Perspective)"
        card_aspect = aspect_ratio or "3:4"
        width, height = (768, 1024)
        ref_candidates = []
        if getattr(character, "closeup_image_url", None):
            ref_candidates.append(("Card 1 Character Close-Up", character.closeup_image_url))
        if getattr(character, "front_image_url", None):
            ref_candidates.append(("Card 3 Full Body Front", character.front_image_url))

        if is_stylized:
            if ref_candidates:
                positive_prompt = (
                    f"Full-body studio animation character model sheet 45-degree three-quarter hero angle portrait of {char_name}, {biometric_profile}. "
                    "Capturing the exact same 2D anime character from the reference close-up and front-view illustrations. "
                    "Full-length distinct 45-degree three-quarter oblique standing perspective framed cleanly from top of head down to footwear with comfortable margins. "
                    "Torso and shoulders are distinctly turned 45 degrees away from the optical axis with one shoulder forward toward the camera, breaking frontal symmetry and showing rich three-dimensional depth, side drapery, and dynamic silhouette. The head turns gently toward the viewer while the body maintains a strict 45-degree three-quarter oblique orientation. Strictly avoid flat orthogonal front-facing orientation (0-degree front view) or camera-parallel torso alignment. "
                    "Strictly preserves 2D anime facial identity, expressive anime eyes, hairstyle silhouette, and costume details from reference images with zero conversion to real photography. "
                    f"Standing in a confident, dynamic three-quarter hero stance wearing complete consistent costume design matching {full_body_costume}. "
                    f"Authentic {style_name} animation visual style with crisp ink linework, dimensional cel-shading, and clean animation palette ({clean_palette}). "
                    "Illuminated by balanced neutral studio illumination on a seamless matte neutral gray studio sweep backdrop with soft ground contact shadow."
                )
            else:
                positive_prompt = (
                    f"Clean studio animation character model sheet 3/4 hero angle portrait of {char_name}, {biometric_profile}. "
                    f"Authentic {style_name} animation visual style with dimensional cel-shading. 45-degree three-quarter studio standing view framed from head to toe. "
                    f"Confident stance wearing complete costume design: {full_body_costume}. "
                    "Illuminated by balanced neutral studio illumination on a seamless matte neutral gray studio backdrop."
                )
        else:
            if ref_candidates:
                positive_prompt = (
                    f"Unretouched RAW photographic full-body studio casting portrait of {char_name}, {biometric_profile}. "
                    "Capturing the exact same individual from the reference close-up and front-view photographs. "
                    "Full-length distinct 45-degree three-quarter hero angle standing perspective framed cleanly from the top of the head down to the soles of the footwear touching the ground with comfortable margins. "
                    "The subject's torso and shoulders are distinctly turned 45 degrees away from the optical axis with one shoulder forward toward the camera, breaking frontal symmetry and revealing three-dimensional volumetric depth, side garment drapery, and dynamic body contour. The head turns gently toward the camera lens while the body maintains a strict 45-degree three-quarter oblique orientation. Strictly avoid flat orthogonal front-facing orientation (0-degree front view) or camera-parallel torso alignment. "
                    "Strictly preserves their exact facial identity, bone structure, eye shape and color, hair texture, and distinctive physical features from the reference images. "
                    "Standing in a confident, natural three-quarter stance showing authentic volumetric depth, realistic garment drapery, and natural weight distribution. "
                    f"Wearing complete, consistent wardrobe design matching {full_body_costume}. "
                    "Captured on a medium-format studio camera with an 85mm prime lens at f/8 for distortion-free anatomical perspective, rich dimensional depth, and tactile fabric and material micro-textures from head to toe. "
                    "Evenly illuminated by balanced 5500K neutral daylight studio softboxes with subtle edge separation and true neutral white balance, with zero colored light spill. "
                    "Isolated cleanly against a seamless, solid, uniform matte neutral gray (#D4D4D4) studio sweep cyclorama backdrop with a soft natural ground contact shadow directly beneath the footwear. "
                    "Indistinguishable from an unedited real studio casting photograph."
                )
            else:
                positive_prompt = (
                    f"Unretouched RAW photographic full-body studio casting portrait of {char_name}, {biometric_profile}. "
                    f"Full-length 45-degree three-quarter studio standing view framed cleanly from top of head down to the soles of the footwear. "
                    f"Standing in a confident, natural three-quarter stance showing volumetric depth and dimensional fabric drapery. "
                    f"Wearing complete costume design: {full_body_costume}. Captured on a medium-format studio camera with an 85mm prime lens at f/8. "
                    f"Illuminated by balanced, softly diffused 5500K neutral daylight studio softboxes on a seamless matte neutral gray (#D4D4D4) studio sweep backdrop with soft ground contact shadow."
                )

    elif slot_key == "back":
        card_title = "Card 6: Back View (Orthogonal 180° • Rear Anatomy & Gear)"
        card_aspect = aspect_ratio or "3:4"
        width, height = (768, 1024)
        ref_candidates = []
        if getattr(character, "closeup_image_url", None):
            ref_candidates.append(("Card 1 Character Close-Up", character.closeup_image_url))
        if getattr(character, "front_image_url", None):
            ref_candidates.append(("Card 3 Full Body Front", character.front_image_url))

        if is_stylized:
            if ref_candidates:
                positive_prompt = (
                    f"Full-body studio animation character model sheet 180-degree rear turnaround portrait of {char_name}, {biometric_profile}. "
                    "Capturing the exact same 2D anime character from the reference illustrations in a direct 180-degree rear orthogonal view. "
                    "Full-length head-to-toe framing facing squarely away from the camera, showing rear hair silhouette, shoulder structure, and complete back costume design: "
                    f"{full_body_costume}. "
                    f"Strictly maintain consistent authentic {style_name} 2D anime styling, clean ink contours, and cel-shaded materials matching the reference images, with zero photographic drift. "
                    "Illuminated by balanced neutral studio illumination on a seamless matte neutral gray studio backdrop with soft ground contact shadow."
                )
            else:
                positive_prompt = (
                    f"Clean studio animation character model sheet back view portrait of {char_name}, {biometric_profile}. "
                    f"Authentic {style_name} animation visual style with crisp lineart and cel-shading. Full-length 180-degree rear orthogonal view framed from head to toe facing away. "
                    f"Showing back silhouette and complete rear costume construction: {full_body_costume}. "
                    "Illuminated by balanced neutral studio illumination on a seamless matte neutral gray studio backdrop."
                )
        else:
            if ref_candidates:
                positive_prompt = (
                    f"Unretouched RAW photographic full-body studio turnaround casting portrait of {char_name}, {biometric_profile}. "
                    "Capturing the exact same individual from the reference photographs in a direct 180-degree rear orthogonal view. "
                    "Full-length head-to-toe framing facing squarely and directly away from the lens, capturing the full figure unobstructed from the back of the head down to the soles of the footwear. "
                    "Strictly preserves exact physical proportions, cranial contour, hair shape from behind, neck and shoulder anatomy, and authentic posture matching the reference images. "
                    f"Wearing complete, consistent wardrobe design from the rear matching {full_body_costume}. "
                    "Captured on a medium-format studio camera with an 85mm prime lens at f/8 for zero focal distortion, crisp edge-to-edge optical clarity, and authentic material micro-textures from head to toe. "
                    "Illuminated by clinical, evenly diffused 5500K neutral daylight studio softboxes with subtle rim separation and zero colored light spill. "
                    "Isolated cleanly against a seamless, solid, uniform matte neutral gray (#D4D4D4) studio sweep cyclorama backdrop with a soft natural ground contact shadow directly beneath the footwear. "
                    "Indistinguishable from an unedited real wardrobe-fitting rear-angle photograph."
                )
            else:
                positive_prompt = (
                    f"Unretouched RAW photographic full-body studio turnaround casting portrait of {char_name}, {biometric_profile}. "
                    f"Full-length direct 180-degree rear orthogonal view framed cleanly from the back of the head down to the soles of the footwear touching the ground. "
                    f"Facing directly away from the lens, revealing rear anatomical proportions, back posture contour, and complete rear costume construction matching {full_body_costume}. "
                    f"Captured on a medium-format studio camera with an 85mm prime lens at f/8 for zero focal distortion and crisp material textures from head to toe. "
                    f"Illuminated by balanced, softly diffused 5500K neutral daylight studio softboxes on a seamless matte neutral gray (#D4D4D4) studio sweep backdrop with soft ground contact shadow. "
                    f"Indistinguishable from an unedited real costume-fitting rear photograph."
                )

    elif slot_key == "tpose":
        card_title = "Card 7: Calibration T-Pose (Full Body Frontal • Neutral A/T Calibration)"
        card_aspect = aspect_ratio or "3:4"
        width, height = (768, 1024)
        ref_candidates = []
        if getattr(character, "closeup_image_url", None):
            ref_candidates.append(("Card 1 Character Close-Up", character.closeup_image_url))
        if getattr(character, "front_image_url", None):
            ref_candidates.append(("Card 3 Full Body Front", character.front_image_url))

        if is_stylized:
            if ref_candidates:
                positive_prompt = (
                    f"Studio animation character model sheet technical T-pose calibration sheet of {char_name}, {biometric_profile}. "
                    "Capturing the exact same 2D anime character from the reference illustrations in a strict orthopedic calibration T-pose. "
                    "Full-length direct frontal view framed cleanly from top of head to footwear with comfortable margins. Arms extended horizontally at exactly 90 degrees shoulder height, palms open facing forward, feet planted shoulder-width apart. "
                    f"Strictly preserves 2D anime facial geometry, hair silhouette, and complete costume construction: {full_body_costume}. "
                    f"Authentic {style_name} animation visual style with crisp ink lineart, flat and dimensional cel-shading, and zero photographic conversion. "
                    "Illuminated by balanced neutral studio illumination on a seamless matte neutral gray studio backdrop."
                )
            else:
                positive_prompt = (
                    f"Clean studio animation character model sheet technical T-pose portrait of {char_name}, {biometric_profile}. "
                    f"Authentic {style_name} animation visual style with crisp lineart and cel-shading. Full-length frontal view, arms extended horizontally at 90 degrees, palms facing forward. "
                    f"Complete costume construction: {full_body_costume}. "
                    "Illuminated by balanced neutral studio illumination on a seamless matte neutral gray studio backdrop."
                )
        else:
            if ref_candidates:
                positive_prompt = (
                    f"Unretouched RAW photographic full-body orthopedic calibration T-pose studio casting photograph of {char_name}, {biometric_profile}. "
                    "Capturing the exact same individual from the reference photographs in a strict rigging and orthopedic calibration T-pose. "
                    "Full-length direct frontal view framed cleanly from the top of the head down to the soles of the footwear touching the ground with comfortable margins. "
                    "Standing upright with head level and facing straight forward, arms extended fully horizontally to each side at exact 90-degree shoulder height with palms open and flat facing forward, "
                    "fingers extended naturally, legs straight with feet planted shoulder-width apart pointing straight ahead. "
                    "Strictly preserves identical facial identity, cranial bone structure, eye shape and color, hair silhouette, and skin texture matching the reference images. "
                    f"Wearing complete, consistent wardrobe design matching {full_body_costume}. "
                    "Photographed on a medium-format camera with an 85mm prime lens at f/8 for zero optical distortion, perfectly true anatomical proportions, and edge-to-edge optical clarity from head to toe. "
                    "Illuminated by clinical, evenly diffused shadowless 5500K neutral daylight studio softboxes with true neutral white balance and zero colored spill. "
                    "Isolated cleanly against a seamless, solid, uniform matte neutral gray (#D4D4D4) studio cyclorama sweep backdrop. "
                    "Indistinguishable from an unedited real motion-capture rigging calibration photograph."
                )
            else:
                positive_prompt = (
                    f"Unretouched RAW photographic full-body orthopedic calibration T-pose studio photograph of {char_name}, {biometric_profile}. "
                    f"Full-length direct frontal view, head level, arms extended horizontally to each side at 90-degree shoulder height, palms open and flat facing forward, feet shoulder-width apart. "
                    f"Wearing complete costume design: {full_body_costume}. Captured on a medium-format studio camera with an 85mm prime lens at f/8 for distortion-free true anatomical proportions. "
                    f"Illuminated by clinical, evenly diffused 5500K neutral daylight studio softboxes on a seamless matte neutral gray (#D4D4D4) studio sweep backdrop."
                )

    elif slot_key == "action":
        card_title = "Card 8: Action Pose (Dynamic Stance • Narrative Silhouette)"
        card_aspect = aspect_ratio or "3:4"
        width, height = (768, 1024)
        ref_candidates = []
        if getattr(character, "closeup_image_url", None):
            ref_candidates.append(("Card 1 Character Close-Up", character.closeup_image_url))
        if getattr(character, "front_image_url", None):
            ref_candidates.append(("Card 3 Full Body Front", character.front_image_url))

        if is_stylized:
            if ref_candidates:
                positive_prompt = (
                    f"Full-body studio animation character model sheet dynamic combat/action stance portrait of {char_name}, {biometric_profile}. "
                    "Capturing the exact same 2D anime character from the reference illustrations in a dynamic narrative signature action pose. "
                    "Full-length head-to-toe framing with athletic weight distribution, showing expressive movement, dynamic garment drapery, and signature pose. "
                    f"Strictly preserves 2D anime identity, expressive facial features, hair silhouette, and complete costume design: {full_body_costume}. "
                    f"Dynamic {style_name} animation cel-shading, sharp ink lineart, and vibrant palette with zero photorealistic human texture. "
                    "Illuminated by balanced neutral studio illumination with dynamic contact shadow on a seamless matte neutral gray studio sweep backdrop."
                )
            else:
                positive_prompt = (
                    f"Clean studio animation character model sheet dynamic action pose portrait of {char_name}, {biometric_profile}. "
                    f"Authentic {style_name} animation visual style with crisp lineart and dynamic cel-shading. Full-length dynamic action stance. "
                    f"Complete costume design: {full_body_costume}. "
                    "Illuminated by balanced neutral studio illumination on a seamless matte neutral gray studio backdrop."
                )
        else:
            if ref_candidates:
                positive_prompt = (
                    f"Unretouched RAW photographic full-body dynamic action-stance studio casting photograph of {char_name}, {biometric_profile}. "
                    "Capturing the exact same individual from the reference close-up and front-view photographs in a dynamic narrative action stance. "
                    "Full-length head-to-toe framing capturing the full athletic silhouette, weight distribution, and character-defining dynamic movement with comfortable margins. "
                    "Strictly preserves their exact facial identity, cranial bone structure, eye shape and color, hair silhouette, and skin texture matching the reference images. "
                    f"Wearing complete, consistent wardrobe design under dynamic stress matching {full_body_costume}. "
                    "Captured on a medium-format camera with an 85mm prime lens at f/8 for zero focal distortion, crisp motion-free clarity, and authentic material micro-textures from head to toe. "
                    "Illuminated by balanced, softly diffused 5500K neutral daylight studio softboxes with delicate rim separation and zero colored light spill. "
                    "Isolated cleanly against a seamless, solid, uniform matte neutral gray (#D4D4D4) studio sweep cyclorama backdrop with a realistic dynamic ground contact shadow. "
                    "Indistinguishable from an unedited real studio action-casting photograph."
                )
            else:
                positive_prompt = (
                    f"Unretouched RAW photographic full-body dynamic action-stance studio casting photograph of {char_name}, {biometric_profile}. "
                    f"Full-length head-to-toe framing capturing dynamic athletic silhouette and character-defining action movement. "
                    f"Wearing complete costume design: {full_body_costume}. Captured on a medium-format camera with an 85mm prime lens at f/8. "
                    f"Illuminated by balanced, softly diffused 5500K neutral daylight studio softboxes on a seamless matte neutral gray (#D4D4D4) studio sweep backdrop with ground contact shadow."
                )

    elif slot_key == "state":
        if not target_state:
            target_state = CharacterStateModel(
                character_id=character.id,
                state_code="#State 01",
                state_label="Normal Baseline",
                wardrobe=full_body_costume,
                injuries_and_wear="Immaculate, zero defects, pristine garment condition",
                expression_anchor="Composed, neutral resting gaze with steady emotional discipline",
            )
        card_title = f"{target_state.state_code}: {target_state.state_label}"
        card_aspect = aspect_ratio or "1:1"
        width, height = (1024, 1024)
        ref_candidates = []
        if getattr(character, "closeup_image_url", None):
            ref_candidates.append(("Card 1 Character Close-Up", character.closeup_image_url))
        if getattr(character, "front_image_url", None):
            ref_candidates.append(("Card 3 Full Body Front", character.front_image_url))

        if is_stylized:
            if ref_candidates:
                positive_prompt = (
                    f"Clean studio animation character model sheet state portrait of {char_name}, {biometric_profile}, in state {target_state.state_code}. "
                    "Composed as a single unified character portrait on a single undivided canvas (strictly single frame, zero multi-panel grid, zero collage, zero split screen). "
                    f"Authentic {style_name} animation visual style with crisp linework and dimensional shading. "
                    "Strictly preserving character identity and micro-expression baselines from reference images while applying state progression: "
                    f"Wardrobe: {target_state.wardrobe}. Physical weathering, damage, and wear: {target_state.injuries_and_wear}. "
                    f"Emotional and psychological expression: {target_state.expression_anchor}. "
                    "Strictly preserve 2D anime illustration aesthetic with crisp ink lineart, cel-shading, and zero conversion to photorealism or live-action photography. "
                    "Illuminated by pure neutral studio illumination on a seamless matte neutral gray studio backdrop."
                )
            else:
                positive_prompt = (
                    f"Clean studio animation character model sheet state portrait of {char_name}, {biometric_profile} in state {target_state.state_code}. "
                    "Composed as a single unified character portrait on a single undivided canvas (strictly single frame, zero multi-panel grid, zero collage, zero split screen). "
                    f"Authentic {style_name} animation visual style with crisp linework and dimensional shading. "
                    f"Wardrobe: {target_state.wardrobe}. Physical weathering, damage, and wear: {target_state.injuries_and_wear}. "
                    f"Emotional and psychological expression: {target_state.expression_anchor}. "
                    "Illuminated by pure neutral studio illumination on a seamless matte neutral gray studio backdrop."
                )
        else:
            if ref_candidates:
                positive_prompt = (
                    f"Unretouched RAW photographic studio character state portrait of {char_name}, {biometric_profile}, in state {target_state.state_code}. "
                    "Composed as a single unified full-length/three-quarter photographic studio character portrait on a single undivided canvas (strictly single frame, zero multi-panel grid, zero collage, zero split screen). "
                    "Strictly capturing the exact same individual from the reference photographs while applying realistic state progression: "
                    f"Wardrobe: {target_state.wardrobe}. Physical weathering, damage, and wear: {target_state.injuries_and_wear}. "
                    f"Emotional and psychological expression: {target_state.expression_anchor}. "
                    "Captured on a medium-format studio camera with an 85mm prime lens at f/5.6, revealing authentic fabric wear, realistic wound detail, and skin texture. "
                    "Illuminated by balanced, softly diffused 5500K neutral daylight studio softboxes on a seamless matte neutral gray (#D4D4D4) studio sweep backdrop. "
                    "Indistinguishable from an unedited real production costume test photograph."
                )
            else:
                positive_prompt = (
                    f"Unretouched RAW photographic studio character state portrait of {char_name}, {biometric_profile} in state {target_state.state_code}. "
                    "Composed as a single unified full-length/three-quarter photographic studio character portrait on a single undivided canvas (strictly single frame, zero multi-panel grid, zero collage, zero split screen). "
                    f"Wardrobe: {target_state.wardrobe}. Physical weathering, damage, and wear: {target_state.injuries_and_wear}. "
                    f"Emotional and psychological expression: {target_state.expression_anchor}. "
                    f"Captured on a medium-format studio camera with an 85mm prime lens at f/5.6. "
                    "Illuminated by balanced, softly diffused 5500K neutral daylight studio softboxes on a seamless matte neutral gray (#D4D4D4) studio sweep backdrop."
                )

    else:  # front fallback
        card_title = "Card 3: Full Body (Front View • Orthogonal 0° • Primary Body Anchor)"
        card_aspect = aspect_ratio or "3:4"
        width, height = (768, 1024)
        ref_candidates = []
        if getattr(character, "closeup_image_url", None):
            ref_candidates.append(("Card 1 Character Close-Up", character.closeup_image_url))

        if is_stylized:
            if ref_candidates:
                positive_prompt = (
                    f"Full-length studio animation character model sheet turnaround portrait capturing {char_name}, {biometric_profile}. "
                    "Capturing the exact same 2D anime character from the reference close-up illustration in a complete head-to-toe standing view. "
                    "The camera is pulled back at neutral chest height to capture the full standing figure unobstructed from the crown of the hair down to the soles of the footwear touching the ground, "
                    "with comfortable visible margins above and below. Standing centered upright in a relaxed neutral model sheet A-pose, arms hanging naturally slightly away from the torso, "
                    "hands open and relaxed, feet planted shoulder-width apart, looking straight ahead at orthogonal 0-degree angle. "
                    "Strictly preserve identical 2D anime facial geometry, eye shape and color, hair silhouette, lineart weight, and cel-shading aesthetic matching the reference close-up illustration. "
                    "Strictly 2D anime illustration, zero conversion to photorealism or 3D CGI. "
                    f"Wearing complete, consistent costume design matching the upper collar seen in the reference image: {full_body_costume}. "
                    f"Rendered in authentic {style_name} animation style with clean ink lineart, consistent cel-shaded shadows, and balanced animation proportions ({clean_palette}). "
                    "Evenly illuminated by balanced neutral studio illumination with a soft ground contact shadow directly beneath the footwear on a seamless matte neutral gray studio cyclorama sweep floor. "
                    "Authentic full-body animation model sheet."
                )
            else:
                positive_prompt = (
                    f"Clean studio animation character model sheet full-body turnaround portrait of {char_name}, {biometric_profile}. "
                    f"Authentic {style_name} animation visual style with crisp ink lineart and dimensional cel-shading ({clean_directives}). Full-length direct frontal standing view framed cleanly from top of head to footwear with comfortable margins. "
                    f"Standing upright in a neutral model sheet A-pose, arms resting slightly away from the torso, hands relaxed, feet shoulder-width apart, looking straight ahead at orthogonal 0-degree angle. "
                    f"Wearing complete costume design: {full_body_costume}. Clean ink contours and balanced cel-shading ({clean_palette}). "
                    "Illuminated by balanced neutral studio illumination with soft ground contact shadow on a seamless matte neutral gray studio backdrop."
                )
        else:
            if ref_candidates:
                positive_prompt = (
                    f"Full-length distant-framed studio casting photograph capturing {char_name}, {biometric_profile}. "
                    "Capturing the exact same individual from the reference close-up photograph in a complete head-to-toe standing view. "
                    "The camera is pulled back at neutral chest height to capture the full standing figure unobstructed from the crown of the hair down to the soles of the footwear touching the ground, "
                    "with comfortable visible margins above and below. Standing centered upright in a relaxed neutral studio A-pose, arms hanging naturally slightly away from the torso, "
                    "hands open and relaxed, feet planted shoulder-width apart, looking straight into the lens at orthogonal 0-degree angle. "
                    "Strictly preserve identical facial bone structure, jawline, eye color, hair silhouette, and skin texture matching the reference close-up photograph. "
                    f"Wearing complete, consistent costume design matching the upper collar seen in the reference image: {full_body_costume}. "
                    "Photographed on a medium-format camera with an 85mm prime lens at f/8, delivering distortion-free anatomical proportions and crisp material micro-textures from head to toe. "
                    "Evenly illuminated by balanced 5500K neutral daylight studio softboxes with soft natural ground contact shadow directly beneath the footwear on a seamless matte neutral gray (#D4D4D4) studio cyclorama sweep floor. "
                    "Authentic unretouched full-body wardrobe fitting photograph."
                )
            else:
                positive_prompt = (
                    f"Unretouched RAW photographic full-body studio casting portrait of {char_name}, {biometric_profile}. "
                    f"Full-length direct frontal standing view framed cleanly from the top of the head all the way down to the soles of the footwear with comfortable margin above the head and below the feet. "
                    f"Standing upright in a natural, relaxed neutral A-pose with arms resting slightly away from the torso, hands relaxed, feet shoulder-width apart, looking straight into the lens at chest-to-eye level. "
                    f"Wearing complete costume design: {full_body_costume}. Captured on a medium-format studio camera with an 85mm prime lens at f/8, "
                    f"delivering distortion-free anatomical proportions and crisp fabric, leather, and material micro-textures from head to toe. "
                    f"Illuminated by balanced, softly diffused 5500K neutral daylight studio softboxes with soft natural ground contact shadow on a seamless matte neutral gray (#D4D4D4) studio sweep backdrop. "
                    "Indistinguishable from an unedited real costume-fitting studio photograph."
                )

    if prompt_override and prompt_override.strip():
        positive_prompt = prompt_override.strip()

    if is_stylized:
        inline_guardrail = "[Aesthetic Constraints: Strictly 2D anime cel-shaded illustration. Avoid: photorealism, real human photography, skin pores, realistic wrinkles, 3D CGI render, live-action camera artifacts]"
        if "Aesthetic Constraints: Strictly 2D anime" not in positive_prompt:
            positive_prompt = f"{positive_prompt.rstrip('. ')}. {inline_guardrail}"

    if positive_prompt:
        positive_prompt = positive_prompt.replace(" (#D4D4D4)", "").replace("#D4D4D4", "")

    # Build Strict Production Constraints
    if slot_key == "expression":
        strict_constraints = (
            "[Strict Production Constraints: Single horizontal image composed of a rigid 3x2 grid of exactly six distinct expression panels. "
            "Strictly preserve 100% facial biometric identity, eye geometry, hairstyle silhouette, and wardrobe collar from reference Card 1 across all six panels. "
            "Zero text, zero labels, zero panel numbers, zero typography, zero watermarks, zero borders, zero extra persons.]"
        )
    elif slot_key == "closeup":
        strict_constraints = (
            "[Strict Production Constraints: Single unified close-up portrait frame only. Zero grids, zero collages, zero split frames. "
            "Strictly preserve authentic biometric identity, cranial bone structure, eye shape and color, hair silhouette, and skin texture from visual reference. "
            "Zero text, zero watermarks, zero artifacts.]"
        )
    else:
        # Cards 3-8 and Dynamic States
        costume_lower = full_body_costume.lower()
        if any(g in costume_lower for g in ("gown", "dress", "hanfu", "cheongsam", "qipao", "robe", "skirt")):
            garment_invariance = "Garment type must remain a gown/dress/robe/skirt matching reference Card 3; DO NOT convert into trousers, pants, or shorts"
        elif any(p in costume_lower for p in ("pants", "trouser", "cargo")):
            garment_invariance = "Garment type must remain trousers/pants matching reference Card 3; DO NOT convert into skirt or dress"
        else:
            garment_invariance = "Garment silhouette, structure, and type must strictly match reference Card 3"

        sleeve_match_c = re.search(
            r"\b(sleeveless|short-sleeved|short\s+sleeves?|long-sleeved|long\s+sleeves?|flutter\s+sleeves?|cap\s+sleeves?|rolled-up\s+sleeves?|puffy\s+sleeves?|bell\s+sleeves?|elbow-length\s+sleeves?)\b",
            sanitized_base_prompt,
            re.IGNORECASE,
        )
        if sleeve_match_c:
            sleeve_invariance = f"Sleeve construction must strictly remain {sleeve_match_c.group(1).lower()} matching reference"
        else:
            sleeve_invariance = "Sleeve construction and shoulder coverage must strictly match reference Card 3"

        strict_constraints = (
            f"[Strict Production Constraints: Single unified frame only. Zero grids, zero collages, zero multi-panel splits, zero side-by-side duplicates. "
            f"Strictly preserve character facial identity and cranial structure from reference Card 1. "
            f"Wardrobe invariance from reference Card 3: {garment_invariance}. {sleeve_invariance}. "
            f"Zero text, zero watermarks, zero typography, zero UI overlay, zero extra limbs, zero distorted hands.]"
        )

    if "[Strict Production Constraints:" not in positive_prompt:
        positive_prompt = f"{positive_prompt.rstrip('. ')}.\n\n{strict_constraints}"

    anchors_used = [label for label, u in ref_candidates if u]
    if is_stylized:
        negative_prompt = (
            "photorealism, real human photography, realistic skin texture, skin pores, wrinkles, "
            "3D CGI render, live-action, camera artifacts, "
            "text, numbers, captions, labels, watermarks, panel numbering, typography, subtitles, UI overlay, "
            "colored light spill, colored reflection on chin or neck, blue light spill on chin, blue reflection, "
            "neon collar glow, colored rim lighting, photographic drift, facial morphing, distorted facial anatomy, "
            "asymmetrical eyes, missing fingers, extra limbs, blurry textures, pixelated face, low resolution, "
            "amateur art, inconsistent clothing, plastic skin, 3d doll, oversaturated"
        )
    else:
        negative_prompt = (
            "text, numbers, captions, labels, watermarks, panel numbering, typography, subtitles, UI overlay, "
            "colored light spill, colored reflection on chin or neck, blue light spill on chin, blue reflection, "
            "neon collar glow, colored rim lighting, photographic drift, facial morphing, distorted facial anatomy, "
            "asymmetrical eyes, missing fingers, extra limbs, blurry textures, pixelated face, low resolution, "
            "amateur art, inconsistent clothing, CGI render, plastic skin, 3d doll, oversaturated"
        )

    copy_ready_text = (
        f"{positive_prompt}\n\n"
        f"--negative_prompt: {negative_prompt}\n"
        f"--aspect_ratio: {card_aspect}\n"
        f"--seed: {dna_seed}"
    )

    return {
        "slot": slot_key,
        "card_title": card_title,
        "positive_prompt": positive_prompt,
        "negative_prompt": negative_prompt,
        "copy_ready_text": copy_ready_text,
        "recommended_aspect_ratio": card_aspect,
        "anchors_used": anchors_used,
        "ref_candidates": ref_candidates,
        "dna_seed": dna_seed,
        "width": width,
        "height": height,
    }


@router.get("/characters/{character_id}/sheet-prompts", status_code=status.HTTP_200_OK)
async def get_character_sheet_prompts(
    character_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    c_uuid = _parse_uuid(character_id, "character_id")
    char = (await session.execute(select(CharacterModel).where(CharacterModel.id == c_uuid))).scalar_one_or_none()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    if not char.dna_seed:
        char.dna_seed = int(hashlib.sha256(str(char.id).encode()).hexdigest()[:8], 16) % 900000 + 100000
        await session.commit()

    proj = (await session.execute(select(ProjectModel).where(ProjectModel.id == char.project_id))).scalar_one_or_none()
    mpb_stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == char.project_id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    mpb = (await session.execute(mpb_stmt)).scalar_one_or_none()

    slots = ["closeup", "expression", "front", "side", "three_quarter", "back", "tpose", "action"]
    prompts_map = {}
    for s in slots:
        compiled = compile_sheet_prompt(character=char, project=proj, bible=mpb, slot=s)
        prompts_map[s] = {
            "slot": s,
            "card_title": compiled["card_title"],
            "positive_prompt": compiled["positive_prompt"],
            "negative_prompt": compiled["negative_prompt"],
            "copy_ready_text": compiled["copy_ready_text"],
            "recommended_aspect_ratio": compiled["recommended_aspect_ratio"],
            "anchors_used": compiled["anchors_used"],
            "dna_seed": compiled["dna_seed"],
            "width": compiled["width"],
            "height": compiled["height"],
        }

    # Also compile prompts for character dynamic states (#State 01 - #State 05)
    states_stmt = (
        select(CharacterStateModel)
        .where(CharacterStateModel.character_id == char.id)
        .order_by(CharacterStateModel.state_code)
    )
    char_states = (await session.execute(states_stmt)).scalars().all()
    states_prompts_map = {}
    for st in char_states:
        compiled_st = compile_sheet_prompt(
            character=char,
            project=proj,
            bible=mpb,
            slot="state",
            target_state=st,
        )
        states_prompts_map[st.state_code] = {
            "state_id": str(st.id),
            "state_code": st.state_code,
            "card_title": compiled_st["card_title"],
            "positive_prompt": compiled_st["positive_prompt"],
            "negative_prompt": compiled_st["negative_prompt"],
            "copy_ready_text": compiled_st["copy_ready_text"],
            "recommended_aspect_ratio": compiled_st["recommended_aspect_ratio"],
            "anchors_used": compiled_st["anchors_used"],
            "dna_seed": compiled_st["dna_seed"],
            "width": compiled_st["width"],
            "height": compiled_st["height"],
        }

    return {
        "data": {
            "character_id": str(char.id),
            "character_name": char.name,
            "dna_seed": char.dna_seed,
            "prompts": prompts_map,
            "states_prompts": states_prompts_map,
        }
    }


@router.post("/characters/{character_id}/upload-sheet", status_code=status.HTTP_200_OK)
async def upload_character_sheet(
    character_id: str,
    slot: str = Form(..., description="'closeup', 'front', 'side', 'three_quarter', 'back', 'tpose', 'action', 'expression'"),
    file: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Upload or replace photo for any of the 8 character matrix cards with high-res normalization & anchor sync."""
    c_uuid = _parse_uuid(character_id, "character_id")
    char = (await session.execute(select(CharacterModel).where(CharacterModel.id == c_uuid))).scalar_one_or_none()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    if not char.dna_seed:
        char.dna_seed = int(hashlib.sha256(str(char.id).encode()).hexdigest()[:8], 16) % 900000 + 100000
        await session.commit()

    norm_slot = (slot or "").lower().strip()
    if norm_slot in ("closeup", "close_up", "headshot", "portrait", "master_closeup", "slot_1"):
        slot_key = "closeup"
    elif norm_slot in ("front", "turnaround_front"):
        slot_key = "front"
    elif norm_slot in ("side", "turnaround_side"):
        slot_key = "side"
    elif norm_slot in ("three_quarter", "3/4", "threequarter", "turnaround_three_quarter"):
        slot_key = "three_quarter"
    elif norm_slot in ("back", "turnaround_back"):
        slot_key = "back"
    elif norm_slot in ("tpose", "sheet_tpose", "t_pose"):
        slot_key = "tpose"
    elif norm_slot in ("action", "sheet_action"):
        slot_key = "action"
    elif norm_slot in ("expression", "sheet_expression"):
        slot_key = "expression"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid slot '{slot}'. Must be one of: closeup, front, side, three_quarter, back, tpose, action, expression.",
        )

    # Enforce safe 20MB limit
    MAX_FILE_SIZE = 20 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of 20MB (Received {len(content) / (1024*1024):.1f}MB).",
        )
    if len(content) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    # Process and normalize image (EXIF transpose, RGB conversion, downscale if > 2048px)
    processed_bytes, width, height = process_uploaded_image(content, max_dimension=2048)

    # Save to effective preview storage path
    settings = get_settings()
    storage_dir = settings.effective_preview_storage_path
    storage_dir.mkdir(parents=True, exist_ok=True)

    file_uuid = uuid.uuid4().hex[:8]
    filename = f"char_{str(char.id)[:8]}_{slot_key}_{file_uuid}.png"
    target_path = storage_dir / filename
    target_path.write_bytes(processed_bytes)

    new_url = f"/api/v1/assets/previews/{filename}"

    # Update character column in SQLite
    if slot_key == "closeup":
        char.closeup_image_url = new_url
    elif slot_key == "front":
        char.front_image_url = new_url
    elif slot_key == "side":
        char.side_image_url = new_url
    elif slot_key == "three_quarter":
        char.three_quarter_image_url = new_url
    elif slot_key == "back":
        char.back_image_url = new_url
    elif slot_key == "tpose":
        char.tpose_image_url = new_url
    elif slot_key == "action":
        char.action_image_url = new_url
    elif slot_key == "expression":
        char.expression_image_url = new_url

    # Compile prompt for metadata persistence
    proj = (await session.execute(select(ProjectModel).where(ProjectModel.id == char.project_id))).scalar_one_or_none()
    mpb_stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == char.project_id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    mpb = (await session.execute(mpb_stmt)).scalar_one_or_none()
    compiled = compile_sheet_prompt(character=char, project=proj, bible=mpb, slot=slot_key)

    meta = dict(char.sheet_metadata or {})
    meta[slot_key] = {
        "image_url": new_url,
        "source": "manual_upload",
        "original_filename": file.filename,
        "content_type": file.content_type or "image/png",
        "file_size": len(processed_bytes),
        "width": width,
        "height": height,
        "prompt": compiled["positive_prompt"],
        "negative_prompt": compiled["negative_prompt"],
        "anchors_used": compiled["anchors_used"],
        "seed": char.dna_seed,
        "aspect_ratio": compiled["recommended_aspect_ratio"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
    }
    char.sheet_metadata = meta
    flag_modified(char, "sheet_metadata")

    await session.commit()
    await session.refresh(char)

    return {
        "status": "completed",
        "message": f"Successfully uploaded and synced {slot_key} image",
        "image_url": new_url,
        "slot": slot_key,
        "character_id": str(char.id),
        "width": width,
        "height": height,
        "sheet_metadata": char.sheet_metadata[slot_key],
    }


class CharacterAssetGenerateRequest(BaseModel):
    target_type: str = Field(default="turnaround", description="'turnaround', 'sheet', or 'state'")
    angle: str | None = Field(
        default="closeup",
        description="'closeup', 'front', 'side', 'three_quarter', 'back', 'tpose', 'action', 'expression'",
    )
    state_id: str | None = Field(default=None, description="State ID if target_type is 'state'")
    provider: str | None = Field(default=None, description="'gemini-direct', '9router', 'google-flow', 'qwen-image-3', etc.")
    model: str | None = Field(default=None, description="Model identifier")
    prompt_override: str | None = Field(default=None, description="Optional custom prompt")
    aspect_ratio: str | None = Field(default=None, description="Aspect ratio ('3:4', '16:9', '1:1')")
    character_id: str | None = Field(default=None, description="Optional character ID if called via project-level endpoint")


class CharacterAttachJobRequest(BaseModel):
    job_id: str
    target_type: str = "turnaround"
    angle: str | None = "front"
    state_id: str | None = None


@router.post("/characters/{character_id}/generate-asset", status_code=status.HTTP_200_OK)
@router.post("/characters/{character_id}/generate-character", status_code=status.HTTP_200_OK)
@router.post("/characters/{character_id}/generate-downstream", status_code=status.HTTP_200_OK)
@router.post("/projects/{project_id}/characters/{character_id}/generate-character", status_code=status.HTTP_200_OK)
@router.post("/projects/{project_id}/characters/{character_id}/generate-downstream", status_code=status.HTTP_200_OK)
async def generate_character_asset(
    character_id: str,
    payload: CharacterAssetGenerateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    project_id: str | None = None,
) -> dict[str, Any]:
    """Generate high-resolution visual sheet or state asset with upstream project sync & chained anchoring."""
    c_uuid = _parse_uuid(character_id, "character_id")
    char = (await session.execute(select(CharacterModel).where(CharacterModel.id == c_uuid))).scalar_one_or_none()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    # 1. Deterministic DNA Seed Locking
    if not char.dna_seed:
        char.dna_seed = int(hashlib.sha256(str(char.id).encode()).hexdigest()[:8], 16) % 900000 + 100000
        await session.commit()
    dna_seed = char.dna_seed

    # 2. Upstream Project Database Synchronization
    proj = (await session.execute(select(ProjectModel).where(ProjectModel.id == char.project_id))).scalar_one_or_none()
    mpb_stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == char.project_id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    mpb = (await session.execute(mpb_stmt)).scalar_one_or_none()

    target_state = None
    if payload.target_type == "state":
        if not payload.state_id:
            raise HTTPException(status_code=400, detail="state_id is required when target_type is 'state'")
        s_uuid = _parse_uuid(payload.state_id, "state_id")
        target_state = (
            await session.execute(select(CharacterStateModel).where(CharacterStateModel.id == s_uuid))
        ).scalar_one_or_none()
        if not target_state:
            raise HTTPException(status_code=404, detail="Character state not found")

    slot_to_compile = "state" if payload.target_type == "state" else (payload.angle or "front")
    compiled = compile_sheet_prompt(
        character=char,
        project=proj,
        bible=mpb,
        slot=slot_to_compile,
        target_state=target_state,
        prompt_override=payload.prompt_override,
        aspect_ratio=payload.aspect_ratio,
    )

    angle_key = compiled["slot"]
    card_aspect = compiled["recommended_aspect_ratio"]
    width = compiled["width"]
    height = compiled["height"]
    prompt = compiled["positive_prompt"]
    negative_prompt = compiled["negative_prompt"]
    anchors_used = compiled["anchors_used"]
    ref_candidates = compiled["ref_candidates"]

    ref_urls = [u for label, u in ref_candidates if u]
    valid_ref_paths = [
        p for p in [_url_to_local_path(u) for u in ref_urls]
        if p and os.path.exists(p) and os.path.getsize(p) > 2048
    ][:4]

    render_cfg = get_project_render_config(str(char.project_id))
    active_prov_id = render_cfg.get("active_provider_id") if render_cfg else None
    apply_all = render_cfg.get("apply_to_all_scenes", True) if render_cfg else False

    prov_override = payload.provider if (payload.provider and payload.provider not in ("ag_gemini_flash", "default", None)) else None
    base_url_to_use = None
    api_key_to_use = None

    if prov_override and render_cfg and prov_override in render_cfg.get("configs", {}):
        prov = prov_override
        cfg_override = render_cfg["configs"][prov_override]
        base_url_to_use = cfg_override.get("baseUrl")
        model_to_use = payload.model or cfg_override.get("modelId")
        stored_key = cfg_override.get("apiKey", "")
        api_key_to_use = decrypt_key(stored_key) if stored_key else ""
    elif render_cfg and apply_all and active_prov_id:
        prov = active_prov_id
        model_to_use = payload.model or render_cfg.get("model_id")
        base_url_to_use = render_cfg.get("base_url")
        api_key_to_use = render_cfg.get("api_key")
    else:
        prov = (payload.provider or "9router").lower().strip()
        model_to_use = payload.model or "ag/gemini-3.8-flash"

    # 3. Google Flow Asynchronous Queue
    if prov in ("google_flow", "google-flow"):
        await _assert_socks5_healthy_for_flow(session)
        parsed_state_id = _parse_uuid(payload.state_id, "state_id") if payload.state_id else None
        flow_job = FlowImageJobModel(
            id=uuid.uuid4(),
            project_id=char.project_id,
            character_id=char.id,
            asset_slot=angle_key,
            target_type=payload.target_type,
            state_id=parsed_state_id,
            prompt=prompt,
            aspect_ratio=card_aspect,
            reference_image_paths=valid_ref_paths if valid_ref_paths else None,
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
            "target_type": payload.target_type,
            "angle": angle_key,
            "state_id": payload.state_id,
            "anchors_used": anchors_used,
            "dna_seed": dna_seed,
            "compiled_prompt": prompt,
            "message": "Character render job placed in Google Flow queue",
        }

    # 4. Image Generation Execution
    if render_cfg and (apply_all or prov_override):
        adapter = UniversalImageAdapter()
        req = UniversalImageRequest(
            provider_id=prov,
            model_id=model_to_use,
            prompt=prompt,
            negative_prompt=negative_prompt,
            aspect_ratio=card_aspect,
            width=width,
            height=height,
            seed=dna_seed,
            reference_image_paths=valid_ref_paths,
            base_url_override=base_url_to_use,
            api_key_override=api_key_to_use,
            enable_fallback=True,
        )
        try:
            gen_res = await adapter.generate_image(req)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Image generation failed via {prov}: {str(exc)}",
            )
        gen_res_url = gen_res.local_url
        res_provider = gen_res.provider_id
        res_model = gen_res.model_id or model_to_use
    else:
        model_to_use = payload.model or (
            "ag/gemini-3.8-flash" if prov in ("ag_gemini_flash", "antigravity") else None
        )
        provider_inst = get_image_provider(prov)
        req = ImageGenerationRequest(
            prompt=prompt,
            negative_prompt=negative_prompt,
            seed=dna_seed,
            randomize_seed=False,
            width=width,
            height=height,
            provider="9router" if prov in ("ag_gemini_flash", "antigravity") else prov,
            model=model_to_use,
            enable_fallback=True,
            reference_image_paths=valid_ref_paths,
        )
        try:
            gen_res = await provider_inst.generate(req)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Image generation failed via {prov}: {str(exc)}",
            )
        gen_res_url = gen_res.local_url
        res_provider = gen_res.provider
        res_model = gen_res.model or model_to_use

    # 5. Persistent SQLite Updates
    if payload.target_type == "state" and target_state:
        target_state.image_url = gen_res_url
    else:
        if angle_key == "closeup":
            char.closeup_image_url = gen_res_url
        elif angle_key == "front":
            char.front_image_url = gen_res_url
        elif angle_key == "side":
            char.side_image_url = gen_res_url
        elif angle_key == "three_quarter":
            char.three_quarter_image_url = gen_res_url
        elif angle_key == "back":
            char.back_image_url = gen_res_url
        elif angle_key == "tpose":
            char.tpose_image_url = gen_res_url
        elif angle_key == "action":
            char.action_image_url = gen_res_url
        elif angle_key == "expression":
            char.expression_image_url = gen_res_url

        meta = dict(char.sheet_metadata or {})
        meta[angle_key] = {
            "image_url": gen_res_url,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "anchors_used": anchors_used,
            "provider": res_provider,
            "model": res_model,
            "seed": dna_seed,
            "aspect_ratio": card_aspect,
            "rendered_at": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
        }
        char.sheet_metadata = meta
        flag_modified(char, "sheet_metadata")

    await session.commit()

    return {
        "status": "completed",
        "image_url": gen_res_url,
        "provider": res_provider,
        "model": res_model,
        "target_type": payload.target_type,
        "angle": angle_key,
        "state_id": payload.state_id,
        "anchors_used": anchors_used,
        "dna_seed": dna_seed,
        "compiled_prompt": prompt,
    }


@router.post("/projects/{project_id}/generate-character", status_code=status.HTTP_200_OK)
@router.post("/projects/{project_id}/generate-downstream", status_code=status.HTTP_200_OK)
async def generate_project_character_endpoint(
    project_id: str,
    payload: CharacterAssetGenerateRequest,
    character_id: str | None = None,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    target_cid = character_id or payload.character_id
    if not target_cid:
        p_uuid = _parse_uuid(project_id, "project_id")
        first_char = (await session.execute(select(CharacterModel).where(CharacterModel.project_id == p_uuid))).scalars().first()
        if not first_char:
            raise HTTPException(status_code=404, detail="No character found in this project to generate.")
        target_cid = str(first_char.id)
    return await generate_character_asset(
        character_id=target_cid,
        payload=payload,
        current_user=current_user,
        session=session,
        project_id=project_id,
    )


@router.post("/characters/{character_id}/attach-job-result", status_code=status.HTTP_200_OK)
async def attach_character_job_result(
    character_id: str,
    payload: CharacterAttachJobRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Attach completed Google Flow job result image to character sheet or state matrix."""
    c_uuid = _parse_uuid(character_id, "character_id")
    char = (await session.execute(select(CharacterModel).where(CharacterModel.id == c_uuid))).scalar_one_or_none()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    j_uuid = _parse_uuid(payload.job_id, "job_id")
    job = (await session.execute(select(FlowImageJobModel).where(FlowImageJobModel.id == j_uuid))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != "completed" or not job.image_url:
        raise HTTPException(status_code=400, detail="Job is not completed or missing image_url")

    norm_angle = (payload.angle or "closeup").lower().strip()
    if norm_angle in ("closeup", "close_up", "headshot", "portrait", "master_closeup", "slot_1"):
        angle_key = "closeup"
    elif norm_angle in ("three_quarter", "3/4", "threequarter"):
        angle_key = "three_quarter"
    elif norm_angle in ("tpose", "sheet_tpose", "t_pose"):
        angle_key = "tpose"
    elif norm_angle in ("action", "sheet_action"):
        angle_key = "action"
    elif norm_angle in ("expression", "sheet_expression"):
        angle_key = "expression"
    elif norm_angle in ("back", "turnaround_back"):
        angle_key = "back"
    elif norm_angle == "side":
        angle_key = "side"
    else:
        angle_key = "front"

    if payload.target_type == "state" and payload.state_id:
        s_uuid = _parse_uuid(payload.state_id, "state_id")
        target_state = (
            await session.execute(select(CharacterStateModel).where(CharacterStateModel.id == s_uuid))
        ).scalar_one_or_none()
        if target_state:
            target_state.image_url = job.image_url
    else:
        if angle_key == "closeup":
            char.closeup_image_url = job.image_url
        elif angle_key == "front":
            char.front_image_url = job.image_url
        elif angle_key == "side":
            char.side_image_url = job.image_url
        elif angle_key == "three_quarter":
            char.three_quarter_image_url = job.image_url
        elif angle_key == "back":
            char.back_image_url = job.image_url
        elif angle_key == "tpose":
            char.tpose_image_url = job.image_url
        elif angle_key == "action":
            char.action_image_url = job.image_url
        elif angle_key == "expression":
            char.expression_image_url = job.image_url

        meta = dict(char.sheet_metadata or {})
        meta[angle_key] = {
            "image_url": job.image_url,
            "prompt": job.prompt,
            "anchors_used": job.reference_image_paths or [],
            "provider": "google_flow",
            "seed": char.dna_seed,
            "aspect_ratio": job.aspect_ratio,
            "rendered_at": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
        }
        char.sheet_metadata = meta
        flag_modified(char, "sheet_metadata")

    await session.commit()
    return {
        "status": "success",
        "message": "Image successfully linked and saved to Persistent SQLite Storage",
        "image_url": job.image_url,
        "angle": angle_key,
        "target_type": payload.target_type,
    }


@router.get("/characters/{character_id}/active-jobs", status_code=status.HTTP_200_OK)
async def get_character_active_jobs(
    character_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve in-flight queued or processing Google Flow jobs for a character."""
    c_uuid = _parse_uuid(character_id, "character_id")
    char = (await session.execute(select(CharacterModel).where(CharacterModel.id == c_uuid))).scalar_one_or_none()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    stmt = (
        select(FlowImageJobModel)
        .where(
            FlowImageJobModel.character_id == c_uuid,
            FlowImageJobModel.status.in_(["queued", "processing"]),
        )
        .order_by(FlowImageJobModel.created_at.asc())
    )
    active_jobs = (await session.execute(stmt)).scalars().all()

    def _to_utc_iso(dt: datetime | None) -> str | None:
        if not dt:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    jobs_data = []
    for j in active_jobs:
        jobs_data.append({
            "job_id": str(j.id),
            "character_id": str(j.character_id),
            "asset_slot": j.asset_slot or "front",
            "target_type": j.target_type or "turnaround",
            "state_id": str(j.state_id) if j.state_id else None,
            "status": j.status,
            "started_at": _to_utc_iso(j.started_at),
            "created_at": _to_utc_iso(j.created_at),
        })

    return {
        "status": "success",
        "character_id": str(char.id),
        "count": len(jobs_data),
        "jobs": jobs_data,
    }


# ==============================================================================
# Context-Aware Auto-Generator & Pre-Creation Visual Gatekeeper
# ==============================================================================

def _procedural_character_generator(
    film_title: str,
    synopsis: str,
    genre: str,
    style_name: str,
    draft: CharacterAutoGenerateDraft,
    mode: str,
) -> dict[str, str]:
    """Resilient contextual character concept generator fallback with dynamic naming."""
    base_name = draft.name
    if not base_name or mode in ("all", "name"):
        combined_text = (film_title + " " + genre + " " + synopsis + " " + (style_name or "")).lower()
        h = int(hashlib.sha256((film_title + genre + str(time.time_ns())).encode()).hexdigest()[:8], 16)

        if any(k in combined_text for k in ["jakarta", "nusantara", "indonesia", "jawa", "bali", "melayu"]):
            firsts = ["Baskara", "Aditya", "Dewi", "Bayu", "Laras", "Satria", "Surya", "Kirana", "Dimas", "Tari"]
            lasts = ["Suryanegara", "Pradana", "Kusuma", "Wibowo", "Mahendra", "Saputra", "Wardhana", "Darmawan"]
        elif any(k in combined_text for k in ["tokyo", "japan", "anime", "manga", "neo-tokyo"]):
            firsts = ["Ren", "Kaito", "Haruto", "Aoi", "Yuki", "Daiki", "Sora", "Akira", "Mei", "Kaede"]
            lasts = ["Takahashi", "Murakami", "Kurogane", "Shimizu", "Tanaka", "Fujimoto", "Hayashi", "Morita"]
        elif any(k in combined_text for k in ["cyber", "future", "2099", "sci-fi", "tech", "android", "matrix"]):
            firsts = ["Vector", "Caelum", "Nyx", "Orion", "Zion", "Silas", "Cyrus", "Astra", "Nova", "Echo"]
            lasts = ["Cross", "Kovacs", "Reyes", "Brandt", "Hex", "Varek", "Stratos", "Sterling"]
        elif any(k in combined_text for k in ["noir", "detective", "crime", "mystery", "investigator"]):
            firsts = ["Julian", "Vincent", "Raymond", "Cole", "Evelyn", "Vivian", "Arthur", "Dominic", "Clara"]
            lasts = ["Blackwood", "Callahan", "Davenport", "Monroe", "Holloway", "Sinclair", "Falcone"]
        elif any(k in combined_text for k in ["comedy", "slapstick", "kids", "animation", "cartoon"]):
            firsts = ["Barnaby", "Bloop", "Pippin", "Felix", "Milo", "Toby", "Gizmo", "Bumble", "Ziggy", "Wally"]
            lasts = ["Fidget", "Clatter", "Giggles", "Puddle", "Wobble", "Quirk", "Twist", "Sprout", "Bramble"]
        elif any(k in combined_text for k in ["fantasy", "epic", "myth", "medieval", "sword", "dragon"]):
            firsts = ["Theron", "Alistair", "Rowan", "Evander", "Cassian", "Isolde", "Alden", "Seraphina", "Darian"]
            lasts = ["Stormrider", "Ironwood", "Ravenshadow", "Winterbourne", "Ashford", "Valerius", "Hawthorne"]
        else:
            firsts = ["Gabriel", "Marcus", "Adrian", "Lucas", "Maya", "Darius", "Leona", "Alexander", "Nadia"]
            lasts = ["Novak", "Kallan", "Renner", "Corvus", "Alvarez", "Castellanos", "Deveraux", "Lindqvist"]

        f_idx = (h >> 4) % len(firsts)
        l_idx = (h >> 12) % len(lasts)
        base_name = f"{firsts[f_idx]} {lasts[l_idx]}"

    role_raw = draft.role or draft.role_suggestion or "Protagonist"
    role_sugg = role_raw
    if mode in ("all", "suggestion"):
        if "antagonist" in role_raw.lower():
            role_sugg = "Antagonist"
        elif "mentor" in role_raw.lower():
            role_sugg = "Mentor"
        elif "deuteragonist" in role_raw.lower():
            role_sugg = "Deuteragonist"
        elif "supporting" in role_raw.lower():
            role_sugg = "Supporting"
        else:
            role_sugg = role_raw or "Protagonist"

    bio = draft.archetype_and_bio
    if not bio or mode in ("all", "suggestion"):
        bio = (
            f"{base_name} is a central {role_sugg.lower()} in '{film_title}', navigating high-stakes narrative conflict. "
            f"Driven by unwavering conviction, calculating intellect, and resilient moral complexity. "
            f"Voice profile: Distinct, low-resonance cinematic voice with disciplined articulation."
        )

    vis_prompt = draft.base_visual_prompt
    if not vis_prompt or mode in ("all", "visual_prompt"):
        is_stylized = any(
            k in (style_name or "").lower()
            for k in ("anime", "cartoon", "2d", "comic", "manga", "pixar", "claymation", "illustration")
        )
        if is_stylized:
            std_bg = "isolated on a flat seamless Neutral Matte Light-Medium Studio Gray (#D4D4D4) studio background, neutral studio illumination, zero environment props or color cast"
        else:
            std_bg = "isolated on a flat seamless Neutral Matte Light-Medium Studio Gray (#D4D4D4) studio background, even softbox lighting, zero environment props or color cast"
        vis_prompt = (
            f"Cinematic close biometric character portrait of {base_name}, 33 years old, sharp angular facial bone structure, "
            f"intense gaze, distinct arched brows, a subtle healed vertical scar across the left cheekbone, "
            f"styled textured dark hair, disciplined athletic posture, wearing a tailored dark charcoal tactical blazer "
            f"with reinforced ballistic weave lapels and matte hardware, {std_bg}"
        )

    return {
        "name": base_name,
        "role_suggestion": role_sugg,
        "archetype_and_bio": bio,
        "base_visual_prompt": vis_prompt,
    }


@router.post("/projects/{project_id}/characters/auto-generate", status_code=status.HTTP_200_OK)
async def auto_generate_character_endpoint(
    project_id: str,
    payload: CharacterAutoGenerateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Generate contextual Character Name, Narrative Role/Bio, and Biometric Visual Prompt from active NLE Studio metadata."""
    project = await _resolve_project(project_id, session)

    film_title = project.title
    p_settings = project.settings if isinstance(project.settings, dict) else {}
    treatment = p_settings.get("treatment") or {}
    synopsis = (
        p_settings.get("synopsis")
        or p_settings.get("description")
        or treatment.get("logline")
        or treatment.get("theme")
        or "Epic cinematic narrative feature production."
    )
    genre_tone = p_settings.get("tone") or p_settings.get("genre") or "Cinematic Film"

    mpb_stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == project.id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    bible = (await session.execute(mpb_stmt)).scalar_one_or_none()
    style_code = (
        bible.style_parameters.get("master_style_code")
        if bible and bible.style_parameters
        else None
    ) or project.target_style_code or "#Style 01"

    setting_world = (
        (bible.world_rules.get("setting") or bible.world_rules.get("world_name"))
        if bible and bible.world_rules
        else p_settings.get("setting") or "Cinematic Universe"
    )

    style_def = next((s for s in STYLE_CATALOG if s.get("code") == style_code), None) or STYLE_CATALOG[0]
    style_name = style_def.get("name", "Hollywood Cinematic")

    chars_stmt = select(CharacterModel.name).where(CharacterModel.project_id == project.id)
    existing_names = [row[0] for row in (await session.execute(chars_stmt)).all()]

    mode = (payload.mode or "all").lower().strip()
    draft = payload.current_draft

    settings = get_settings()
    llm_prov = (payload.llm_provider or "9router").lower().strip()
    model_choice = getattr(settings, "llm_model", "ag/gemini-3.8-flash")
    if "gemini" in llm_prov:
        model_choice = "ag/gemini-3.8-flash"
    elif "agy" in llm_prov:
        model_choice = "Agy"

    try:
        proj_ctx: ProjectNarrativeContext | dict[str, Any] = extract_project_narrative_context(project, bible=bible)
    except Exception:
        proj_ctx = {
            "title": film_title,
            "synopsis": synopsis,
            "genre_tone": genre_tone,
            "master_style_code": style_code,
            "style_name": style_name,
            "world_setting": setting_world,
        }

    result_data = None
    try:
        engine = PolyaScreenwriterEngine(model=model_choice, timeout=15.0)
        result_data = await engine.auto_generate_character(
            project_context=proj_ctx,
            existing_names=existing_names,
            mode=mode,
            current_draft=draft.model_dump() if hasattr(draft, "model_dump") else dict(draft),
        )
    except Exception as exc:
        logger.warning(f"PolyaScreenwriterEngine auto-generate failed or timed out: {exc}. Using contextual procedural generator.")

    if not result_data or not isinstance(result_data, dict):
        result_data = _procedural_character_generator(
            film_title=film_title,
            synopsis=synopsis,
            genre=genre_tone,
            style_name=style_name,
            draft=draft,
            mode=mode,
        )

    is_stylized = any(
        k in (style_name or "").lower()
        for k in ("anime", "cartoon", "2d", "comic", "manga", "pixar", "claymation", "illustration")
    )
    if is_stylized:
        std_backdrop = "isolated on a flat seamless Neutral Matte Light-Medium Studio Gray (#D4D4D4) studio background, neutral studio illumination, zero environment props or color cast"
    else:
        std_backdrop = "isolated on a flat seamless Neutral Matte Light-Medium Studio Gray (#D4D4D4) studio background, even softbox lighting, zero environment props or color cast"
    visual_prompt = result_data.get("base_visual_prompt") or draft.base_visual_prompt or (
        f"A cinematic character for {film_title}, 32 years old, striking facial symmetry, sharp gaze, "
        f"tactical bespoke wardrobe reflecting {genre_tone} aesthetic."
    )
    # Sanitize newlines to prevent premature Enter in ProseMirror
    visual_prompt = " ".join(visual_prompt.split())
    if "#D4D4D4" not in visual_prompt:
        visual_prompt = f"{visual_prompt.rstrip('. ')}. {std_backdrop}."

    role_val = result_data.get("role_suggestion") or draft.role or "Protagonist"
    fallback_name = _procedural_character_generator(
        film_title=film_title,
        synopsis=synopsis,
        genre=genre_tone,
        style_name=style_name,
        draft=draft,
        mode="name",
    ).get("name", f"Lead character of {film_title}")
    name_val = result_data.get("name") or draft.name or fallback_name
    bio_val = result_data.get("archetype_and_bio") or draft.archetype_and_bio or (
        f"{name_val} is a resolute character in '{film_title}'. Driven by conviction, speaks with controlled gravitas."
    )
    voice_dna_val = result_data.get("voice_dna_profile") or draft.voice_dna_profile or (
        f"Measured cinematic cadence fitting {genre_tone}; controlled vocal projection with deliberate pauses."
    )

    return {
        "data": {
            "name": name_val,
            "role_suggestion": role_val,
            "archetype_and_bio": bio_val,
            "voice_dna_profile": str(voice_dna_val).strip(),
            "base_visual_prompt": visual_prompt,
        }
    }


@router.post("/projects/{project_id}/characters/preview", status_code=status.HTTP_200_OK)
async def generate_character_preview(
    project_id: str,
    payload: CharacterPreviewRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Generate temporary visual previews for Expression Sheet (3x2) and Full Body without inserting into SQLite."""
    project = await _resolve_project(project_id, session)

    cleanup_stale_temp_previews()

    preview_token = payload.preview_token or uuid.uuid4().hex[:12]
    settings = get_settings()
    temp_dir = settings.effective_preview_storage_path.parent / "temp_previews" / preview_token
    temp_dir.mkdir(parents=True, exist_ok=True)

    dna_seed = payload.dna_seed or (
        int(hashlib.sha256(f"{payload.name}_{preview_token}".encode()).hexdigest()[:8], 16) % 900000 + 100000
    )

    mpb_stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == project.id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    mpb = (await session.execute(mpb_stmt)).scalar_one_or_none()

    # Ephemeral character representation strictly in memory
    dummy_char = CharacterModel(
        id=uuid.uuid4(),
        project_id=project.id,
        name=payload.name,
        role=payload.role,
        base_prompt=payload.base_visual_prompt,
        dna_seed=dna_seed,
        sheet_metadata={},
    )

    render_cfg = get_project_render_config(str(project.id))
    active_prov_id = render_cfg.get("active_provider_id") if render_cfg else None
    apply_all = render_cfg.get("apply_to_all_scenes", True) if render_cfg else False

    prov_override = payload.image_provider if (payload.image_provider and payload.image_provider not in ("ag_gemini_flash", "default", None)) else None
    if prov_override and render_cfg and prov_override in render_cfg.get("configs", {}):
        prov = prov_override
    elif render_cfg and apply_all and active_prov_id:
        prov = active_prov_id
    else:
        prov = (payload.image_provider or "9router").lower().strip()
    target = (payload.target or "closeup").lower().strip()

    closeup_file = temp_dir / "closeup.png"
    expr_file = temp_dir / "expression.png"
    front_file = temp_dir / "front.png"

    closeup_url = (
        f"/api/v1/assets/temp-previews/{preview_token}/closeup.png" if closeup_file.exists() else None
    )
    expression_url = (
        f"/api/v1/assets/temp-previews/{preview_token}/expression.png" if expr_file.exists() else None
    )
    front_url = (
        f"/api/v1/assets/temp-previews/{preview_token}/front.png" if front_file.exists() else None
    )

    # 1. Preview 1: Character Close-Up (Master Anchor) - Slot 1
    if target in ("closeup", "all"):
        aspect_to_use = "3:4" if target in ("closeup", "all") else (payload.aspect_ratio or "3:4")
        compiled_closeup = compile_sheet_prompt(
            character=dummy_char,
            project=project,
            bible=mpb,
            slot="closeup",
            aspect_ratio=aspect_to_use,
        )
        if prov == "google_flow":
            await _assert_socks5_healthy_for_flow(session)
            flow_job = FlowImageJobModel(
                id=uuid.uuid4(),
                project_id=project.id,
                prompt=compiled_closeup["positive_prompt"],
                aspect_ratio=aspect_to_use,
                reference_image_paths=None,
                status="queued",
                retry_count=0,
                max_retries=3,
                created_at=datetime.now(timezone.utc),
            )
            session.add(flow_job)
            await session.commit()
            return {
                "status": "queued",
                "job_id": str(flow_job.id),
                "preview_token": preview_token,
                "slot": "closeup",
                "provider": "google_flow",
                "dna_seed": dna_seed,
                "closeup_url": closeup_url,
                "expression_url": expression_url,
                "front_url": front_url,
                "message": "Character Close-Up render job placed in Google Flow queue",
            }
        else:
            model_to_use = payload.model or (
                "gemini-3.1-flash-image" if prov in ("ag_gemini_flash", "antigravity") else None
            )
            provider_inst = get_image_provider(prov)
            req_closeup = ImageGenerationRequest(
                prompt=compiled_closeup["positive_prompt"],
                negative_prompt=compiled_closeup["negative_prompt"],
                seed=dna_seed,
                randomize_seed=False,
                width=compiled_closeup["width"],
                height=compiled_closeup["height"],
                provider="9router" if prov in ("ag_gemini_flash", "antigravity") else prov,
                model=model_to_use,
                enable_fallback=True,
            )
            try:
                gen_res = await provider_inst.generate(req_closeup)
            except RateLimitExceededError as rle:
                logger.warning("preview_closeup_rate_limited: %s", str(rle))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=str(rle),
                )
            except ImageGenerationError as ige:
                logger.error("preview_closeup_failed: %s", str(ige))
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=str(ige),
                )

            src_path = _url_to_local_path(gen_res.local_url)
            if not src_path or not os.path.exists(src_path):
                if gen_res.local_path and os.path.exists(gen_res.local_path):
                    src_path = gen_res.local_path
                else:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Generated Close-Up file could not be located on disk.",
                    )

            validate_raster_image_file(src_path)
            shutil.copyfile(src_path, closeup_file)
            ts = int(time.time() * 1000)
            closeup_url = f"/api/v1/assets/temp-previews/{preview_token}/closeup.png?v={ts}"

            if target == "closeup":
                return {
                    "status": "completed",
                    "preview_token": preview_token,
                    "closeup_url": closeup_url,
                    "expression_url": expression_url,
                    "front_url": front_url,
                    "dna_seed": dna_seed,
                    "provider": prov,
                    "message": "Character Close-Up preview ready for inspection",
                }

    # 2. Preview 2: Expression Sheet (3x2) - Slot 2
    if target in ("both", "expression", "all"):
        if closeup_url:
            dummy_char.closeup_image_url = closeup_url

        aspect_to_use_expr = "16:9"
        compiled_expr = compile_sheet_prompt(
            character=dummy_char,
            project=project,
            bible=mpb,
            slot="expression",
            aspect_ratio=aspect_to_use_expr,
        )
        ref_paths_expr = []
        if closeup_file.exists() and closeup_file.stat().st_size > 2048:
            ref_paths_expr = [str(closeup_file.resolve())]

        if prov == "google_flow":
            await _assert_socks5_healthy_for_flow(session)
            flow_job = FlowImageJobModel(
                id=uuid.uuid4(),
                project_id=project.id,
                prompt=compiled_expr["positive_prompt"],
                aspect_ratio=aspect_to_use_expr,
                reference_image_paths=ref_paths_expr if ref_paths_expr else None,
                status="queued",
                retry_count=0,
                max_retries=3,
                created_at=datetime.now(timezone.utc),
            )
            session.add(flow_job)
            await session.commit()
            return {
                "status": "queued",
                "job_id": str(flow_job.id),
                "preview_token": preview_token,
                "slot": "expression",
                "provider": "google_flow",
                "dna_seed": dna_seed,
                "closeup_url": closeup_url,
                "expression_url": expression_url,
                "front_url": front_url,
                "message": "Expression Sheet render job placed in Google Flow queue",
            }
        else:
            model_to_use = payload.model or (
                "gemini-3.1-flash-image" if prov in ("ag_gemini_flash", "antigravity") else None
            )
            provider_inst = get_image_provider(prov)
            req_expr = ImageGenerationRequest(
                prompt=compiled_expr["positive_prompt"],
                negative_prompt=compiled_expr["negative_prompt"],
                seed=dna_seed,
                randomize_seed=False,
                width=compiled_expr["width"],
                height=compiled_expr["height"],
                provider="9router" if prov in ("ag_gemini_flash", "antigravity") else prov,
                model=model_to_use,
                enable_fallback=True,
                reference_image_paths=ref_paths_expr,
            )
            try:
                gen_res = await provider_inst.generate(req_expr)
            except RateLimitExceededError as rle:
                logger.warning("preview_expression_rate_limited: %s", str(rle))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=str(rle),
                )
            except ImageGenerationError as ige:
                logger.error("preview_expression_failed: %s", str(ige))
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=str(ige),
                )

            src_path = _url_to_local_path(gen_res.local_url)
            if not src_path or not os.path.exists(src_path):
                if gen_res.local_path and os.path.exists(gen_res.local_path):
                    src_path = gen_res.local_path
                else:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Generated Expression Sheet file could not be located on disk.",
                    )

            # Strict magic bytes raster check before staging
            validate_raster_image_file(src_path)
            shutil.copyfile(src_path, expr_file)
            ts = int(time.time() * 1000)
            expression_url = f"/api/v1/assets/temp-previews/{preview_token}/expression.png?v={ts}"

    # 3. Preview 3: Full Body (Front View) with Chained Biometric Reference - Slot 3
    if target in ("both", "front", "all"):
        if closeup_url:
            dummy_char.closeup_image_url = closeup_url
        if expression_url:
            dummy_char.expression_image_url = expression_url

        aspect_to_use_front = "3:4"
        compiled_front = compile_sheet_prompt(
            character=dummy_char,
            project=project,
            bible=mpb,
            slot="front",
            aspect_ratio=aspect_to_use_front,
        )

        ref_paths = []
        if closeup_file.exists() and closeup_file.stat().st_size > 2048:
            ref_paths.append(str(closeup_file.resolve()))

        if prov == "google_flow":
            await _assert_socks5_healthy_for_flow(session)
            flow_job = FlowImageJobModel(
                id=uuid.uuid4(),
                project_id=project.id,
                prompt=compiled_front["positive_prompt"],
                aspect_ratio=aspect_to_use_front,
                reference_image_paths=ref_paths if ref_paths else None,
                status="queued",
                retry_count=0,
                max_retries=3,
                created_at=datetime.now(timezone.utc),
            )
            session.add(flow_job)
            await session.commit()
            return {
                "status": "queued",
                "job_id": str(flow_job.id),
                "preview_token": preview_token,
                "slot": "front",
                "provider": "google_flow",
                "dna_seed": dna_seed,
                "closeup_url": closeup_url,
                "expression_url": expression_url,
                "front_url": front_url,
                "message": "Full Body render job placed in Google Flow queue",
            }
        else:
            model_to_use = payload.model or (
                "gemini-3.1-flash-image" if prov in ("ag_gemini_flash", "antigravity") else None
            )
            provider_inst = get_image_provider(prov)
            req_front = ImageGenerationRequest(
                prompt=compiled_front["positive_prompt"],
                negative_prompt=compiled_front["negative_prompt"],
                seed=dna_seed,
                randomize_seed=False,
                width=compiled_front["width"],
                height=compiled_front["height"],
                provider="9router" if prov in ("ag_gemini_flash", "antigravity") else prov,
                model=model_to_use,
                enable_fallback=True,
                reference_image_paths=ref_paths,
            )
            try:
                gen_res = await provider_inst.generate(req_front)
            except RateLimitExceededError as rle:
                logger.warning("preview_front_rate_limited: %s", str(rle))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=str(rle),
                )
            except ImageGenerationError as ige:
                logger.error("preview_front_failed: %s", str(ige))
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=str(ige),
                )

            src_path = _url_to_local_path(gen_res.local_url)
            if not src_path or not os.path.exists(src_path):
                if gen_res.local_path and os.path.exists(gen_res.local_path):
                    src_path = gen_res.local_path
                else:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Generated Full Body preview file could not be located on disk.",
                    )

            # Strict magic bytes raster check before staging
            validate_raster_image_file(src_path)
            shutil.copyfile(src_path, front_file)
            ts = int(time.time() * 1000)
            front_url = f"/api/v1/assets/temp-previews/{preview_token}/front.png?v={ts}"

    # Retain and validate existing target if single-target re-roll was performed
    if not closeup_url and closeup_file.exists():
        validate_raster_image_file(closeup_file)
        ts = int(time.time() * 1000)
        closeup_url = f"/api/v1/assets/temp-previews/{preview_token}/closeup.png?v={ts}"

    if not front_url and front_file.exists():
        validate_raster_image_file(front_file)
        ts = int(time.time() * 1000)
        front_url = f"/api/v1/assets/temp-previews/{preview_token}/front.png?v={ts}"

    if not expression_url and expr_file.exists():
        validate_raster_image_file(expr_file)
        ts = int(time.time() * 1000)
        expression_url = f"/api/v1/assets/temp-previews/{preview_token}/expression.png?v={ts}"

    return {
        "status": "completed",
        "preview_token": preview_token,
        "closeup_url": closeup_url,
        "expression_url": expression_url,
        "front_url": front_url,
        "dna_seed": dna_seed,
        "provider": prov,
        "message": "Pre-creation visual previews ready for inspection",
    }


@router.post("/projects/{project_id}/characters/preview/attach", status_code=status.HTTP_200_OK)
async def attach_character_preview_job(
    project_id: str,
    payload: CharacterPreviewAttachRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Attach completed Google Flow job result into character pre-creation staging folder."""
    j_uuid = _parse_uuid(payload.job_id, "job_id")
    job = (await session.execute(select(FlowImageJobModel).where(FlowImageJobModel.id == j_uuid))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Flow job not found")
    if job.status != "completed" or not job.image_url:
        raise HTTPException(status_code=400, detail="Flow job not yet completed or missing image")

    settings = get_settings()
    temp_dir = settings.effective_preview_storage_path.parent / "temp_previews" / payload.preview_token
    temp_dir.mkdir(parents=True, exist_ok=True)

    slot_lower = payload.slot.lower()
    if "closeup" in slot_lower:
        target_slot = "closeup"
    elif "expression" in slot_lower:
        target_slot = "expression"
    else:
        target_slot = "front"
    dest_file = temp_dir / f"{target_slot}.png"

    src_path = _url_to_local_path(job.image_url)
    if not src_path or not os.path.exists(src_path):
        raise HTTPException(status_code=500, detail="Job image file could not be located on disk")

    # Strict raster magic bytes validation before staging
    validate_raster_image_file(src_path)

    shutil.copyfile(src_path, dest_file)
    ts = int(time.time() * 1000)
    new_url = f"/api/v1/assets/temp-previews/{payload.preview_token}/{target_slot}.png?v={ts}"

    return {
        "status": "completed",
        "preview_token": payload.preview_token,
        "slot": target_slot,
        "image_url": new_url,
    }


@router.delete("/projects/{project_id}/characters/preview/{preview_token}", status_code=status.HTTP_200_OK)
@router.post("/projects/{project_id}/characters/preview/{preview_token}/cleanup", status_code=status.HTTP_200_OK)
async def cleanup_character_preview(
    project_id: str,
    preview_token: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Delete staging directory when user cancels or closes modal."""
    clean_token = Path(preview_token).name
    settings = get_settings()
    temp_dir = settings.effective_preview_storage_path.parent / "temp_previews" / clean_token
    if not temp_dir.exists():
        temp_dir = Path("./data/assets/temp_previews") / clean_token
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    cleanup_stale_temp_previews()
    return {"status": "cleaned", "preview_token": clean_token}


@router.get("/assets/temp-previews/{preview_token}/{filename}", status_code=status.HTTP_200_OK)
@router.get("/assets/temp_previews/{preview_token}/{filename}", status_code=status.HTTP_200_OK)
@router.head("/assets/temp-previews/{preview_token}/{filename}", status_code=status.HTTP_200_OK)
@router.head("/assets/temp_previews/{preview_token}/{filename}", status_code=status.HTTP_200_OK)
async def get_temp_preview_asset(preview_token: str, filename: str):
    """Serve staged pre-creation preview images safely with directory traversal protection."""
    clean_token = Path(preview_token).name
    clean_filename = Path(filename).name
    if ".." in clean_token or ".." in clean_filename:
        raise HTTPException(status_code=400, detail="Invalid preview token or filename")

    settings = get_settings()
    file_path = settings.effective_preview_storage_path.parent / "temp_previews" / clean_token / clean_filename
    if not file_path.is_file() or not file_path.exists():
        fallback_path = Path("./data/assets/temp_previews") / clean_token / clean_filename
        if fallback_path.is_file() and fallback_path.exists():
            file_path = fallback_path
        else:
            raise HTTPException(status_code=404, detail="Temporary preview image not found")

    # Detect media_type from magic bytes inspection (fallback to extension)
    media_type = "image/png"
    try:
        header = file_path.read_bytes()[:64]
        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            media_type = "image/png"
        elif header.startswith(b"\xff\xd8\xff"):
            media_type = "image/jpeg"
        elif header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WEBP":
            media_type = "image/webp"
        else:
            ext = file_path.suffix.lower()
            if ext == ".webp":
                media_type = "image/webp"
            elif ext in (".jpg", ".jpeg"):
                media_type = "image/jpeg"
            else:
                media_type = "image/png"
    except Exception:
        pass

    return FileResponse(
        file_path,
        media_type=media_type,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )

