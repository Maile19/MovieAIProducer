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

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
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
from backend.app.domain.character_prompt_compiler import (
    CASTING_CLOSEUP_PRESET_ID,
    DirectorCharacterDynamicSlots,
    UPSCALE_2K_LOCK_PREFIX,
    build_deterministic_dynamic_slots,
    compile_casting_closeup_prompt,
    compile_upscale_2k_prompt,
    get_downstream_frozen_layers,
    resolve_provider_dimensions,
    resolve_style_gate,
    resolve_upscale_2k_target_dimensions,
)
from backend.app.domain.director_rag import DirectorRAGClient
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
    get_style_family,
    sanitize_negative_prompts_for_style,
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
from backend.app.api.v1.render_settings import (
    _lookup_provider_config,
    get_project_render_config,
    decrypt_key,
    resolve_effective_render_provider,
)
from backend.app.infrastructure.universal_image_adapter import (
    AUTO_ROUTE_2K_PRIORITY,
    UniversalImageAdapter,
    UniversalImageRequest,
    supports_native_2k_upscale,
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


class WorldPropVariationRequest(BaseModel):
    item_type: Literal["environment", "prop"] = Field(description="Single item type to vary")
    code: str = Field(description="Exact item code, e.g. '#Env 01' or '#Prop 03'")
    current_item: dict[str, Any] | None = Field(
        default=None,
        description="Current saved item payload; auto-resolved from the Bible when omitted",
    )
    additional_notes: str | None = Field(default=None, description="Optional showrunner steering notes")


class SheetOverrideRequest(BaseModel):
    slot_key: str = Field(description="Canonical sheet slot or dynamic state code")
    prompt_override: str | None = Field(default=None, description="Positive prompt override")
    negative_prompt_override: str | None = Field(default=None, description="Negative prompt override")


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


async def _load_latest_bible(
    project: ProjectModel,
    session: AsyncSession,
) -> MasterProductionBibleModel | None:
    stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == project.id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _build_narrative_context(
    project: ProjectModel,
    session: AsyncSession,
) -> tuple[ProjectNarrativeContext, MasterProductionBibleModel | None]:
    """Assemble a full ProjectNarrativeContext from live cast, states, and storyboard data."""
    bible = await _load_latest_bible(project, session)

    char_stmt = (
        select(CharacterModel)
        .where(CharacterModel.project_id == project.id)
        .order_by(CharacterModel.created_at.asc())
    )
    char_rows = (await session.execute(char_stmt)).scalars().all()
    characters_list: list[dict[str, Any]] = []
    for c in char_rows:
        state_stmt = (
            select(CharacterStateModel)
            .where(CharacterStateModel.character_id == c.id)
            .order_by(CharacterStateModel.state_code.asc())
        )
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
        context = extract_project_narrative_context(
            project,
            bible,
            characters=characters_list,
            scenes=scenes_list,
        )
    except ValueError as exc:
        title = (project.title or "").strip()
        if not title:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
        settings = project.settings if isinstance(project.settings, dict) else {}
        genre_tone = settings.get("genre") or settings.get("tone") or "Cinematic Film"
        context = ProjectNarrativeContext(
            project_id=str(project.id),
            title=title,
            synopsis=(
                f"A cinematic {genre_tone} production titled '{title}' exploring "
                "immersive environments and signature hero props."
            ),
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

    return context, bible


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


@router.post("/projects/{project_id}/bible/world-props/variations", status_code=status.HTTP_200_OK)
async def generate_world_prop_variations_endpoint(
    project_id: str,
    payload: WorldPropVariationRequest | None = None,
    item_type: Literal["environment", "prop"] | None = Query(default=None),
    code: str | None = Query(default=None),
    additional_notes: str | None = Query(default=None),
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Generate exactly 3 distinct selectable variations for ONE environment or prop.

    Accepts a typed JSON body (preferred). Legacy query parameters remain supported for
    backward compatibility. Never mutates any other saved Bible item.
    """
    resolved_type = payload.item_type if payload else item_type
    resolved_code = (payload.code if payload else code) or ""
    resolved_item = payload.current_item if payload else None
    resolved_notes = payload.additional_notes if payload else additional_notes

    if not resolved_type or not resolved_code.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="item_type and code are required (JSON body or query parameters).",
        )

    resolved_code = resolved_code.strip()
    project = await _resolve_project(project_id, session)
    context, bible = await _build_narrative_context(project, session)

    # Auto-resolve the current saved item by code when the client did not supply one.
    if resolved_item is None and bible and isinstance(bible.world_rules, dict):
        collection_key = "environments" if resolved_type == "environment" else "props"
        collection = bible.world_rules.get(collection_key) or []
        if isinstance(collection, list):
            for candidate in collection:
                if not isinstance(candidate, dict):
                    continue
                if str(candidate.get("code", "")).strip().lower() == resolved_code.lower():
                    resolved_item = dict(candidate)
                    break

    engine = PolyaScreenwriterEngine()
    try:
        variations = await engine.generate_world_prop_variations(
            context=context,
            item_type=resolved_type,
            code=resolved_code,
            current_item=resolved_item,
            additional_notes=resolved_notes,
        )
    except Exception as exc:
        logger.error("Polya AI Director world/prop variation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Polya AI Director failed to generate variations: {exc}",
        )

    return {
        "status": "success",
        "project_id": str(project.id),
        "item_type": resolved_type,
        "code": resolved_code,
        "data": variations,
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
                        "resolution_width": (meta.get(f"state_{s.id}") or {}).get("resolution_width"),
                        "resolution_height": (meta.get(f"state_{s.id}") or {}).get("resolution_height"),
                        "is_2k": bool((meta.get(f"state_{s.id}") or {}).get("is_2k", False)),
                        "previous_1k_url": (meta.get(f"state_{s.id}") or {}).get("previous_1k_url"),
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
            manifest: dict[str, Any] = {}
            manifest_path = temp_dir / "preview_manifest.json"
            if manifest_path.exists():
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                except Exception:
                    manifest = {}

            def _promote_preview_slot(slot_name: str) -> tuple[str | None, dict[str, Any] | None]:
                slot_info = manifest.get(slot_name) if isinstance(manifest.get(slot_name), dict) else {}
                active_fname = slot_info.get("active_file") or f"{slot_name}.png"
                src_file = temp_dir / Path(active_fname).name
                if not src_file.exists():
                    src_file = temp_dir / f"{slot_name}.png"
                if not src_file.exists():
                    return None, None

                dest_suffix = "_2k" if slot_info.get("is_2k") else ""
                dest_name = f"char_{str(char_id)[:8]}_{slot_name}_{uuid.uuid4().hex[:8]}{dest_suffix}.png"
                dest_path = perm_storage / dest_name
                shutil.copyfile(src_file, dest_path)
                promoted_url = f"/api/v1/assets/previews/{dest_name}"
                dims = _read_image_dimensions_from_path(dest_path)

                prev_1k_url = None
                prev_fname = slot_info.get("previous_1k_file")
                if prev_fname:
                    prev_src = temp_dir / Path(prev_fname).name
                    if prev_src.exists():
                        prev_dest_name = f"char_{str(char_id)[:8]}_{slot_name}_1k_{uuid.uuid4().hex[:8]}.png"
                        shutil.copyfile(prev_src, perm_storage / prev_dest_name)
                        prev_1k_url = f"/api/v1/assets/previews/{prev_dest_name}"

                slot_meta: dict[str, Any] = {
                    "image_url": promoted_url,
                    "source": "pre_creation_gatekeeper",
                    "status": "completed",
                    "seed": det_seed,
                    "rendered_at": now.isoformat(),
                }
                if dims:
                    slot_meta["width"] = dims[0]
                    slot_meta["height"] = dims[1]
                    slot_meta["resolution_width"] = dims[0]
                    slot_meta["resolution_height"] = dims[1]
                    slot_meta["is_2k"] = max(dims[0], dims[1]) >= 1920
                elif slot_info:
                    slot_meta["resolution_width"] = slot_info.get("resolution_width")
                    slot_meta["resolution_height"] = slot_info.get("resolution_height")
                    slot_meta["is_2k"] = bool(slot_info.get("is_2k", False))
                if prev_1k_url:
                    slot_meta["previous_1k_url"] = prev_1k_url
                return promoted_url, slot_meta

            closeup_url, closeup_meta = _promote_preview_slot("closeup")
            if closeup_meta:
                initial_metadata["closeup"] = closeup_meta

            expression_url, expr_meta = _promote_preview_slot("expression")
            if expr_meta:
                initial_metadata["expression"] = expr_meta

            front_url, front_meta = _promote_preview_slot("front")
            if front_meta:
                initial_metadata["front"] = front_meta

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


@router.put("/projects/{project_id}/characters/{character_id}/sheet-overrides", status_code=status.HTTP_200_OK)
async def update_character_sheet_overrides(
    project_id: str,
    character_id: str,
    payload: SheetOverrideRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Store or clear per-slot positive/negative prompt overrides for a character sheet slot."""
    p_uuid = _parse_uuid(project_id, "project_id")
    c_uuid = _parse_uuid(character_id, "character_id")
    char_stmt = select(CharacterModel).where(CharacterModel.id == c_uuid)
    char = (await session.execute(char_stmt)).scalar_one_or_none()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
    if char.project_id != p_uuid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character does not belong to this project",
        )

    slot_key = (payload.slot_key or "").strip()
    if not slot_key:
        raise HTTPException(status_code=422, detail="slot_key is required")

    prompt_override = (payload.prompt_override or "").strip() or None
    negative_override = (payload.negative_prompt_override or "").strip() or None

    overrides = dict(char.sheet_overrides or {})

    if prompt_override is None and negative_override is None:
        overrides.pop(slot_key, None)
    else:
        overrides[slot_key] = {
            "prompt_override": prompt_override,
            "negative_prompt_override": negative_override,
        }

    char.sheet_overrides = overrides
    flag_modified(char, "sheet_overrides")
    await session.commit()
    await session.refresh(char)

    return {
        "status": "success",
        "character_id": str(char.id),
        "slot_key": slot_key,
        "has_override": slot_key in overrides,
        "overrides": overrides,
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


def _read_image_dimensions_from_path(file_path: str | Path | None) -> tuple[int, int] | None:
    """Read real pixel dimensions (width, height) from disk using PIL.Image."""
    if not file_path:
        return None
    try:
        p = Path(file_path)
        if not p.exists() or not p.is_file():
            return None
        with Image.open(p) as img:
            return img.size
    except Exception:
        return None


def _read_image_dimensions_from_url(url: str | None) -> tuple[int, int] | None:
    """Resolve URL to local path and read real pixel dimensions via PIL.Image."""
    local_path = _url_to_local_path(url)
    return _read_image_dimensions_from_path(local_path)


def _normalize_sheet_slot(slot: str | None, default: str = "front") -> str:
    norm = (slot or default).lower().strip()
    if norm in ("closeup", "close_up", "headshot", "portrait", "master_closeup", "slot_1"):
        return "closeup"
    if norm in ("three_quarter", "3/4", "threequarter", "turnaround_three_quarter"):
        return "three_quarter"
    if norm in ("tpose", "sheet_tpose", "t_pose"):
        return "tpose"
    if norm in ("action", "sheet_action"):
        return "action"
    if norm in ("expression", "sheet_expression"):
        return "expression"
    if norm in ("back", "turnaround_back"):
        return "back"
    if norm in ("side", "turnaround_side"):
        return "side"
    if norm == "state":
        return "state"
    if norm in ("front", "turnaround_front"):
        return "front"
    return default


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


def _clean_style_directives_for_character_sheet(
    text: str,
    is_stylized: bool = False,
    style_family: str | None = None,
) -> str:
    """Strip scenic, environmental, weather, and camera motion overrides from style directives."""
    import re
    family = style_family or ("anime_2d" if is_stylized else "photorealistic")
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
    if family != "photorealistic":
        cleaned = re.sub(r"\bphotorealistic\b", "expressive", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r",\s*,+", ",", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.")
    if cleaned and not cleaned.endswith("."):
        cleaned += "."
    if cleaned:
        return cleaned
    if family == "anime_2d":
        return "Crisp clean linework, dimensional anime cel-shading, vibrant character palette."
    if family == "stylized_3d":
        return "Sculpted stylized 3D geometry, rich PBR surface shading, clean rim-lit form."
    if family == "stop_motion":
        return "Tactile handcrafted plasticine texture, subtle handmade surface relief, physical armature form."
    return "Pristine dynamic range, lifelike skin pores, crisp micro-texture detail."


def _clean_color_grade_for_character_sheet(
    text: str,
    is_stylized: bool = False,
    style_family: str | None = None,
) -> str:
    """Strip environmental and location lighting overrides from color grade emulation."""
    import re
    family = style_family or ("anime_2d" if is_stylized else "photorealistic")
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
    if cleaned:
        return cleaned
    if family == "anime_2d":
        return "Pure neutral white balance, vibrant 2D animation palette emulation."
    if family == "stylized_3d":
        return "Balanced studio global illumination, clean stylized 3D color harmony."
    if family == "stop_motion":
        return "Neutral miniature stage lighting, authentic physical clay color fidelity."
    return "Naturalistic color timing, neutral balanced 65mm sensor reproduction."


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


def _resolve_sheet_family_profile(
    style_code: str,
    style_name: str,
    style_family: str,
    clean_directives: str,
    clean_palette: str,
) -> dict[str, str]:
    """Build style-authentic rendering descriptors for each of the 4 canonical style families."""
    if style_family == "stylized_3d":
        if style_code == "#Style 11":
            medium_desc = (
                f"2.5D painterly brushstroke textures mapped onto sculpted 3D character geometry in {style_name} style, "
                f"graphic novel contour edges, rough oil-paint shader finishes ({clean_directives})"
            )
            ref_noun = "3D/2.5D animated character model"
        elif style_code == "#Style 06":
            medium_desc = (
                f"hyper-detailed stylized 3D Donghua animation character model in {style_name} style, "
                f"clean PBR shaders, expressive sculpted proportions ({clean_directives})"
            )
            ref_noun = "3D animated Donghua character model"
        else:
            medium_desc = (
                f"stylized 3D feature animation character model in {style_name} style, "
                f"expressive sculpted facial geometry, tactile PBR surface shaders, soft studio rim ({clean_directives})"
            )
            ref_noun = "stylized 3D animated character model"
        return {
            "family": "stylized_3d",
            "sheet_header": f"Clean studio stylized 3D animation character model sheet",
            "ref_noun": ref_noun,
            "medium_desc": medium_desc,
            "lighting": "Pure neutral 5500K studio three-point illumination with clean rim separation and true neutral white balance",
            "backdrop": "solid, uniform, seamless matte neutral gray studio cyclorama backdrop",
            "optics": "virtual 85mm distortion-free studio turntable camera",
            "inline_guardrail": "[Aesthetic Constraints: Strictly stylized 3D/2.5D animated CGI character model sheet. Avoid: live-action DSLR photography, raw human skin pores, flat 2D cel sketch]",
            "base_negative": (
                "live-action DSLR photography, raw human skin pores, realistic wrinkles, flat 2D cel sketch, "
                "text, numbers, captions, labels, watermarks, panel numbering, typography, subtitles, UI overlay, "
                "colored light spill, colored reflection on chin or neck, facial morphing, distorted facial anatomy, "
                "asymmetrical eyes, missing fingers, extra limbs, blurry textures, pixelated face, low resolution, "
                "inconsistent clothing, oversaturated"
            ),
        }

    if style_family == "stop_motion":
        return {
            "family": "stop_motion",
            "sheet_header": "Handcrafted stop-motion miniature maquette character model sheet",
            "ref_noun": "handcrafted stop-motion clay/plasticine puppet",
            "medium_desc": (
                f"tactile sculpted plasticine and clay maquette in {style_name} style, subtle authentic fingerprint impressions, "
                f"handmade wool/fabric miniature costume textures, internal armature proportions ({clean_directives})"
            ),
            "lighting": "Balanced neutral miniature stage spotlights with soft overhead fill and zero colored light spill",
            "backdrop": "solid, uniform, seamless matte neutral gray miniature stage cyclorama backdrop",
            "optics": "macro studio stage lens at f/8 with natural miniature depth-of-field clarity",
            "inline_guardrail": "[Aesthetic Constraints: Strictly handcrafted stop-motion clay/plasticine miniature maquette. Avoid: live-action DSLR human skin pores, flat 2D anime cel shading, glossy digital CGI]",
            "base_negative": (
                "live-action human skin pores, glossy digital CGI, flat 2D anime cel shading, "
                "text, numbers, captions, labels, watermarks, panel numbering, typography, subtitles, UI overlay, "
                "colored light spill, colored reflection on chin or neck, facial morphing, distorted anatomy, "
                "asymmetrical eyes, missing fingers, extra limbs, blurry textures, low resolution, inconsistent clothing"
            ),
        }

    if style_family == "anime_2d":
        if style_code == "#Style 16":
            medium_desc = (
                f"Studio Ghibli-inspired hand-drawn 2D animation model sheet in {style_name} style, "
                f"soft organic pencil-and-ink linework, gentle hand-painted watercolor cel washes ({clean_directives})"
            )
            ref_noun = "2D hand-painted anime character illustration"
        elif style_code == "#Style 17":
            medium_desc = (
                f"dark graphic novel character model sheet in {style_name} style, "
                f"heavy chiaroscuro black ink shadows, stark angular contour linework, high-contrast noir ink washes ({clean_directives})"
            )
            ref_noun = "2D graphic novel ink character illustration"
        elif style_code == "#Style 14":
            medium_desc = (
                f"classic 2D cel animation character model sheet in {style_name} style, "
                f"crisp variable-weight ink lineart, clean flat cel color fills ({clean_directives})"
            )
            ref_noun = "2D cel animation character illustration"
        else:
            medium_desc = (
                f"2D anime character model sheet in {style_name} style, "
                f"crisp anime ink lineart, luminous multi-layered expressive eyes, delicate cel-shading ({clean_directives})"
            )
            ref_noun = "2D anime character illustration"
        return {
            "family": "anime_2d",
            "sheet_header": "Clean studio animation character model sheet",
            "ref_noun": ref_noun,
            "medium_desc": medium_desc,
            "lighting": f"Pure neutral studio illumination with zero colored light spill on chin or neck and true neutral white balance ({clean_palette})",
            "backdrop": "solid, uniform, seamless matte neutral gray studio paper backdrop",
            "optics": "flat distortion-free orthographic animation camera",
            "inline_guardrail": "[Aesthetic Constraints: Strictly 2D anime cel-shaded illustration or hand-drawn art. Avoid: photorealism, real human photography, skin pores, realistic wrinkles, 3D CGI render, live-action camera artifacts]",
            "base_negative": (
                "photorealism, real human photography, realistic skin texture, skin pores, wrinkles, "
                "3D CGI render, live-action, camera artifacts, "
                "text, numbers, captions, labels, watermarks, panel numbering, typography, subtitles, UI overlay, "
                "colored light spill, colored reflection on chin or neck, blue light spill on chin, blue reflection, "
                "neon collar glow, colored rim lighting, photographic drift, facial morphing, distorted facial anatomy, "
                "asymmetrical eyes, missing fingers, extra limbs, blurry textures, pixelated face, low resolution, "
                "amateur art, inconsistent clothing, plastic skin, 3d doll, oversaturated"
            ),
        }

    # photorealistic family (#Style 01, 02, 03, 04, 05, 07, 08, 12, 18)
    if style_code == "#Style 12":
        medium_note = f"UE5 Metahuman digital human studio render ({clean_directives}; {clean_palette})"
    elif style_code == "#Style 18":
        medium_note = f"35mm archival film stock texture with organic grain and natural dye balance ({clean_directives}; {clean_palette})"
    else:
        medium_note = f"authentic lived-in human skin with visible pores, natural skin grain, and matte finish ({clean_directives})"

    return {
        "family": "photorealistic",
        "sheet_header": "Unretouched RAW photographic studio casting portrait",
        "ref_noun": "individual from the reference photograph",
        "medium_desc": medium_note,
        "lighting": "balanced, softly diffused 5500K neutral daylight studio softboxes with zero colored light spill",
        "backdrop": "solid, uniform, seamless matte neutral gray studio sweep cyclorama backdrop",
        "optics": "100-megapixel medium-format studio camera with 85mm prime lens at f/8",
        "inline_guardrail": "",
        "base_negative": (
            "text, numbers, captions, labels, watermarks, panel numbering, typography, subtitles, UI overlay, "
            "colored light spill, colored reflection on chin or neck, blue light spill on chin, blue reflection, "
            "neon collar glow, colored rim lighting, photographic drift, facial morphing, distorted facial anatomy, "
            "asymmetrical eyes, missing fingers, extra limbs, blurry textures, pixelated face, low resolution, "
            "amateur art, inconsistent clothing, CGI render, plastic skin, 3d doll, oversaturated"
        ),
    }


def compile_sheet_prompt(
    character: CharacterModel,
    project: ProjectModel | None,
    bible: MasterProductionBibleModel | None,
    slot: str,
    target_state: CharacterStateModel | None = None,
    prompt_override: str | None = None,
    aspect_ratio: str | None = None,
    director_rag_cues: str = "",
    director_slots: DirectorCharacterDynamicSlots | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pure compiler producing project-synced, 4-family style-authentic prompts for Cards 1-8 and dynamic states."""
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
    style_family = str(style_def.get("family") or get_style_family(style_code) or "photorealistic")

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

    clean_directives = _clean_style_directives_for_character_sheet(aesthetic_directives, style_family=style_family)
    clean_palette = _clean_color_grade_for_character_sheet(color_grade_emulation, style_family=style_family)
    fam_spec = _resolve_sheet_family_profile(style_code, style_name, style_family, clean_directives, clean_palette)

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

    # Style Gate & Dynamic Slots (Polia AI Director / deterministic fallback)
    style_gate = resolve_style_gate(style_code)
    is_frozen_active = style_gate.routing_mode in ("full", "light_override")
    cached_slots_dict: dict[str, Any] | None = None
    if isinstance(director_slots, DirectorCharacterDynamicSlots):
        cached_slots_dict = director_slots.model_dump()
    elif isinstance(director_slots, dict):
        cached_slots_dict = director_slots
    elif isinstance(getattr(character, "sheet_metadata", None), dict):
        maybe_cached = character.sheet_metadata.get("director_casting_slots")
        if isinstance(maybe_cached, dict):
            cached_slots_dict = maybe_cached

    dynamic_slots = build_deterministic_dynamic_slots(
        base_prompt=character.base_prompt or "",
        char_name=character.name,
        style_code=style_code,
        cached_slots=cached_slots_dict,
    )
    downstream_layers: dict[str, Any] | None = None
    layers_applied: list[str] = []
    frozen_negative_override: str | None = None

    if is_frozen_active and slot_key != "closeup":
        has_state_wear = False
        if slot_key == "state" and target_state is not None:
            wear_str = (target_state.injuries_and_wear or "").strip().lower()
            has_state_wear = bool(wear_str and wear_str not in ("none", "zero defects", "immaculate, zero defects, pristine garment condition"))
        downstream_layers = get_downstream_frozen_layers(
            slot_key=slot_key,
            style_code=style_code,
            studio_backdrop_tone=dynamic_slots.studio_backdrop_tone,
            has_injuries_or_wear=has_state_wear,
        )
        layers_applied = list(downstream_layers["layers_applied"])
        eff_lighting = downstream_layers["layer_2"]
        eff_backdrop = f"seamless matte {dynamic_slots.studio_backdrop_tone} studio backdrop"
        eff_medium_desc = downstream_layers["layer_1"]
    else:
        eff_lighting = fam_spec["lighting"]
        eff_backdrop = fam_spec["backdrop"]
        eff_medium_desc = fam_spec["medium_desc"]

    # Card Technical Directives & Framing Specifications
    if slot_key == "closeup":
        card_title = "Card 1: Character Close-Up (Master Anchor)"
        card_aspect = aspect_ratio or "1:1"
        ref_candidates = []
        if getattr(character, "face_ref_asset_id", None):
            ref_candidates.append(("Face Reference Asset", str(character.face_ref_asset_id)))

        if is_frozen_active:
            closeup_res = compile_casting_closeup_prompt(
                slots=dynamic_slots,
                style_code=style_code,
                has_face_ref=bool(ref_candidates),
                aspect_ratio=card_aspect,
            )
            positive_prompt = closeup_res["positive_prompt"]
            frozen_negative_override = closeup_res["negative_prompt"]
            width, height = closeup_res["width"], closeup_res["height"]
            layers_applied = list(closeup_res["layers_applied"])
        else:
            width, height = (1024, 1024) if card_aspect == "1:1" else (768, 1024)
            ref_clause = (
                f"Analyze the visual reference and strictly preserve the exact {fam_spec['ref_noun']} identity, "
                f"facial proportions, eye design, hair silhouette, and distinguishing features. "
                if ref_candidates else ""
            )
            positive_prompt = (
                f"{fam_spec['sheet_header']} close-up casting portrait of {biometric_profile}. {ref_clause}"
                f"Tight head-and-shoulders close-up framed cleanly from the crown of the head down to the upper collarbone. "
                f"Direct frontal view at exact eye-level, head held upright and centered facing straight ahead with both ears clearly visible, "
                f"calm neutral resting expression, naturally closed lips, and steady direct eye contact. "
                f"Strictly render in {fam_spec['medium_desc']} ({clean_palette}). "
                f"Illuminated by {fam_spec['lighting']} against a {fam_spec['backdrop']}. "
                f"Dress the upper shoulders in {wardrobe_collar} keeping the neck and jawline cleanly visible."
            )

    elif slot_key == "expression":
        card_title = "Card 2: Expression Sheet (3x2 Micro-Expressions Grid)"
        card_aspect = aspect_ratio or "16:9"
        width, height = (1344, 768)
        ref_candidates = []
        if getattr(character, "closeup_image_url", None):
            ref_candidates.append(("Card 1 Character Close-Up", character.closeup_image_url))

        ref_note = (
            f"Capturing the exact same {fam_spec['ref_noun']} from the reference close-up. "
            if ref_candidates else ""
        )
        grid_lead = (
            f"Photographic character expression contact sheet montage"
            if style_family == "photorealistic"
            else f"{fam_spec['sheet_header']} expression grid"
        )
        lighting_segment = eff_lighting if is_frozen_active else f"illuminated by {eff_lighting} against a {eff_backdrop}"
        positive_prompt = (
            f"{grid_lead} composed of exactly six equal distinct portrait panels arranged in a rigid 3-column by 2-row grid "
            f"on a single horizontal canvas, featuring {char_name}, {biometric_profile}. {ref_note}"
            f"Strictly preserve 100% character identity, facial proportions, eye design, hairstyle silhouette, and consistent wardrobe collar ({wardrobe_collar}) across all six panels. "
            f"Render consistently with {eff_medium_desc} "
            "Top row from left to right: calm neutral resting face with relaxed closed lips, subtle genuine smile with expressive eyes and relaxed cheeks, "
            "and intense controlled anger with tightened jawline and furrowed brows. "
            "Bottom row from left to right: quiet sorrow and grief with softened downward gaze, sudden shock and astonishment with widened eyes and slightly parted lips, "
            "and wary sharp suspicion with narrowed focused eyes. "
            f"Each individual panel maintains consistent head-and-shoulders framing at eye level using {fam_spec['optics']}. "
            f"{lighting_segment} Clean division lines separating panels."
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

        ref_note = f"Capturing the exact same {fam_spec['ref_noun']} from the reference Card 1 close-up and Card 3 front view. " if ref_candidates else ""
        lighting_segment = f"{eff_lighting} with a soft ground contact shadow." if is_frozen_active else f"illuminated by {eff_lighting} against a {eff_backdrop} with a soft ground contact shadow."
        positive_prompt = (
            f"Full-body {fam_spec['sheet_header']} 90-degree lateral side profile portrait of {char_name}, {biometric_profile}. {ref_note}"
            "Full-length strict 90-degree lateral side-profile orthogonal view framed cleanly from top of head down to the soles of the footwear touching the ground with comfortable margins. "
            "Standing upright in a natural, balanced neutral profile standing posture revealing precise lateral proportions and complete side costume construction matching "
            f"{full_body_costume}. {eff_medium_desc} "
            f"Captured via {fam_spec['optics']}. {lighting_segment}"
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

        ref_note = f"Capturing the exact same {fam_spec['ref_noun']} from the reference Card 1 and Card 3 anchors. " if ref_candidates else ""
        lighting_segment = f"{eff_lighting} with soft ground contact shadow." if is_frozen_active else f"illuminated by {eff_lighting} against a {eff_backdrop} with soft ground contact shadow."
        positive_prompt = (
            f"Full-body {fam_spec['sheet_header']} 45-degree three-quarter hero angle portrait of {char_name}, {biometric_profile}. {ref_note}"
            "Full-length distinct 45-degree three-quarter oblique standing perspective framed cleanly from top of head down to the soles of the footwear with comfortable margins. "
            "The subject's torso and shoulders are distinctly turned 45 degrees away from the optical axis with one shoulder forward toward the camera, breaking frontal symmetry and revealing volumetric depth and side garment drapery. "
            "The head turns gently toward the viewer while the body maintains a strict 45-degree three-quarter oblique orientation. Strictly avoid flat orthogonal front-facing orientation (0-degree front view) or camera-parallel torso alignment. "
            f"Standing in a confident three-quarter stance wearing complete consistent costume design matching {full_body_costume}. "
            f"{eff_medium_desc} Captured via {fam_spec['optics']}. {lighting_segment}"
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

        ref_note = f"Capturing the exact same {fam_spec['ref_noun']} from the reference anchors in a direct 180-degree rear orthogonal view. " if ref_candidates else ""
        lighting_segment = f"{eff_lighting} with soft ground contact shadow." if is_frozen_active else f"illuminated by {eff_lighting} against a {eff_backdrop} with soft ground contact shadow."
        positive_prompt = (
            f"Full-body {fam_spec['sheet_header']} 180-degree rear turnaround portrait of {char_name}, {biometric_profile}. {ref_note}"
            "Full-length head-to-toe framing facing squarely away from the camera, capturing rear hair silhouette, shoulder anatomy, and complete back costume construction: "
            f"{full_body_costume}. {eff_medium_desc} Captured via {fam_spec['optics']}. {lighting_segment}"
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

        ref_note = f"Capturing the exact same {fam_spec['ref_noun']} from the reference anchors in a strict orthopedic calibration T-pose. " if ref_candidates else ""
        lighting_segment = eff_lighting if is_frozen_active else f"illuminated by {eff_lighting} against a {eff_backdrop}."
        positive_prompt = (
            f"Full-body {fam_spec['sheet_header']} technical T-pose calibration sheet of {char_name}, {biometric_profile}. {ref_note}"
            "Full-length direct frontal view framed cleanly from top of head down to footwear with comfortable margins. "
            "Standing upright with head level facing straight forward, arms extended horizontally to each side at exact 90-degree shoulder height, palms open facing forward, feet shoulder-width apart. "
            f"Wearing complete consistent costume construction: {full_body_costume}. "
            f"{eff_medium_desc} Captured via {fam_spec['optics']}. {lighting_segment}"
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

        ref_note = f"Capturing the exact same {fam_spec['ref_noun']} from the reference anchors in a dynamic narrative signature action pose. " if ref_candidates else ""
        lighting_segment = f"{eff_lighting} with dynamic ground contact shadow." if is_frozen_active else f"illuminated by {eff_lighting} against a {eff_backdrop} with dynamic ground contact shadow."
        positive_prompt = (
            f"Full-body {fam_spec['sheet_header']} dynamic action-stance portrait of {char_name}, {biometric_profile}. {ref_note}"
            "Full-length head-to-toe framing with athletic weight distribution, expressive silhouette, and dynamic garment drapery. "
            f"Wearing complete consistent costume design under dynamic motion matching {full_body_costume}. "
            f"{eff_medium_desc} Captured via {fam_spec['optics']}. {lighting_segment}"
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

        ref_note = f"Strictly preserving character identity and baseline proportions from the reference {fam_spec['ref_noun']} while applying state progression. " if ref_candidates else ""
        lighting_segment = eff_lighting if is_frozen_active else f"illuminated by {eff_lighting} against a {eff_backdrop}."
        positive_prompt = (
            f"{fam_spec['sheet_header']} state portrait of {char_name}, {biometric_profile}, in state {target_state.state_code}. "
            "Composed as a single unified character portrait on a single undivided canvas (strictly single frame, zero multi-panel grid, zero collage, zero split screen). "
            f"{ref_note}"
            f"Wardrobe: {target_state.wardrobe}. Physical weathering, damage, and wear: {target_state.injuries_and_wear}. "
            f"Emotional and psychological expression: {target_state.expression_anchor}. "
            f"{eff_medium_desc} Captured via {fam_spec['optics']}. {lighting_segment}"
        )

    else:  # front fallback (Card 3)
        card_title = "Card 3: Full Body (Front View • Orthogonal 0° • Primary Body Anchor)"
        card_aspect = aspect_ratio or "3:4"
        width, height = (768, 1024)
        ref_candidates = []
        if getattr(character, "closeup_image_url", None):
            ref_candidates.append(("Card 1 Character Close-Up", character.closeup_image_url))

        ref_note = f"Capturing the exact same {fam_spec['ref_noun']} from the reference close-up in a complete head-to-toe standing view. " if ref_candidates else ""
        pose_phrase = "studio A-pose" if style_family == "photorealistic" else "model sheet A-pose"
        lighting_segment = f"{eff_lighting} with a soft natural ground contact shadow." if is_frozen_active else f"illuminated by {eff_lighting} against a {eff_backdrop} with a soft natural ground contact shadow."
        positive_prompt = (
            f"Full-body {fam_spec['sheet_header']} full-length turnaround portrait of {char_name}, {biometric_profile}. {ref_note}"
            "The camera is pulled back at neutral chest height to capture the full standing figure unobstructed from the crown of the hair down to the soles of the footwear touching the ground, "
            f"with comfortable visible margins above and below. Standing centered upright in a relaxed neutral {pose_phrase}, arms hanging naturally slightly away from the torso, "
            "hands open and relaxed, feet planted shoulder-width apart, looking straight ahead at orthogonal 0-degree angle. "
            f"Wearing complete, consistent costume design: {full_body_costume}. "
            f"{eff_medium_desc} Captured via {fam_spec['optics']}. {lighting_segment}"
        )

    if prompt_override and prompt_override.strip():
        positive_prompt = prompt_override.strip()

    # Never inject scene/shot RAG cues into Card 1 when CASTING_CLOSEUP_REALISTIC_V1 is active
    if director_rag_cues and director_rag_cues.strip() and not (slot_key == "closeup" and is_frozen_active):
        positive_prompt = f"{positive_prompt.rstrip('. ')}. Director look-dev style cues: {director_rag_cues.strip()}."

    if fam_spec["inline_guardrail"] and fam_spec["inline_guardrail"] not in positive_prompt:
        positive_prompt = f"{positive_prompt.rstrip('. ')}. {fam_spec['inline_guardrail']}"

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
            "Strictly preserve authentic biometric identity, cranial bone structure, eye shape and color, hair silhouette, and surface texture from visual reference. "
            "Zero text, zero watermarks, zero artifacts.]"
        )
    else:
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
    if slot_key == "closeup" and frozen_negative_override is not None:
        negative_prompt = frozen_negative_override
    elif downstream_layers is not None:
        downstream_struct_neg = (
            "text, numbers, captions, labels, watermarks, panel numbering, typography, subtitles, "
            "UI overlay, distorted facial anatomy, asymmetrical eyes, missing fingers, extra limbs, "
            "blurry textures, pixelated face, low resolution, inconsistent clothing"
        )
        sanitized_negs = sanitize_negative_prompts_for_style(
            [f"{downstream_layers['negative_prompt']}, {downstream_struct_neg}"],
            style_code,
        )
        negative_prompt = ", ".join(sanitized_negs)
    else:
        sanitized_negs = sanitize_negative_prompts_for_style([fam_spec["base_negative"]], style_code)
        negative_prompt = ", ".join(sanitized_negs)

    copy_ready_text = (
        f"{positive_prompt}\n\n"
        f"--negative_prompt: {negative_prompt}\n"
        f"--aspect_ratio: {card_aspect}\n"
        f"--seed: {dna_seed}"
    )

    return {
        "slot": slot_key,
        "style_family": style_family,
        "style_code": style_gate.style_code,
        "preset_id": CASTING_CLOSEUP_PRESET_ID if is_frozen_active else None,
        "routing_mode": style_gate.routing_mode,
        "layers_applied": layers_applied,
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


def _resolve_sheet_override(
    character: CharacterModel,
    slot_keys: list[str],
) -> dict[str, Any]:
    """Return the first stored per-slot override dict for any of the candidate keys."""
    overrides = character.sheet_overrides if isinstance(character.sheet_overrides, dict) else {}
    for key in slot_keys:
        if not key:
            continue
        candidate = overrides.get(key)
        if isinstance(candidate, dict):
            return candidate
    return {}


def _apply_sheet_overrides(
    compiled: dict[str, Any],
    override: dict[str, Any],
    style_code: str,
) -> dict[str, Any]:
    """Compute compiled vs effective prompts with style-sanitized negative override."""
    compiled_prompt = compiled.get("positive_prompt", "")
    compiled_negative = compiled.get("negative_prompt", "")

    prompt_override = str(override.get("prompt_override") or "").strip()
    negative_override = str(override.get("negative_prompt_override") or "").strip()

    effective_prompt = prompt_override or compiled_prompt
    if negative_override:
        sanitized = sanitize_negative_prompts_for_style([negative_override], style_code)
        effective_negative = ", ".join(sanitized) if sanitized else ""
    else:
        effective_negative = compiled_negative

    return {
        "compiled_prompt": compiled_prompt,
        "prompt_override": prompt_override or None,
        "effective_prompt": effective_prompt,
        "compiled_negative_prompt": compiled_negative,
        "negative_prompt_override": negative_override or None,
        "effective_negative_prompt": effective_negative,
        "has_override": bool(prompt_override or negative_override),
    }


async def _fetch_character_sheet_rag_cues(
    style_code: str,
    character_name: str,
    slot_label: str = "character look-dev portrait",
) -> str:
    """Best-effort async Director RAG lookup (1.5s timeout, empty fallback) for character look-dev cues."""
    try:
        rag_res = await DirectorRAGClient.retrieve(
            scene_beat=f"{style_code} {slot_label} for {character_name}",
            style_code=style_code,
            engine="flux",
            top_k=2,
        )
        cues_text, _ = DirectorRAGClient.format_transpile_cues(rag_res, max_shots=2)
        return cues_text[:240].strip() if cues_text else ""
    except Exception:
        return ""


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

    active_style_code = (
        (mpb.style_parameters.get("master_style_code") if mpb and mpb.style_parameters else None)
        or (proj.target_style_code if proj else None)
        or "#Style 01"
    )
    active_gate = resolve_style_gate(active_style_code)
    rag_cues = await _fetch_character_sheet_rag_cues(
        style_code=active_style_code,
        character_name=char.name or "Character",
        slot_label="character sheet turnaround look-dev",
    )

    slots = ["closeup", "expression", "front", "side", "three_quarter", "back", "tpose", "action"]
    prompts_map = {}
    for s in slots:
        compiled = compile_sheet_prompt(
            character=char,
            project=proj,
            bible=mpb,
            slot=s,
            director_rag_cues="" if (s == "closeup" and active_gate.routing_mode != "strict_bypass") else rag_cues,
        )
        override = _resolve_sheet_override(char, [s])
        effective = _apply_sheet_overrides(compiled, override, active_style_code)
        copy_ready = (
            f"{effective['effective_prompt']}\n\n"
            f"--negative_prompt: {effective['effective_negative_prompt']}\n"
            f"--aspect_ratio: {compiled['recommended_aspect_ratio']}\n"
            f"--seed: {compiled['dna_seed']}"
        )
        prompts_map[s] = {
            "slot": s,
            "card_title": compiled["card_title"],
            "positive_prompt": effective["effective_prompt"],
            "negative_prompt": effective["effective_negative_prompt"],
            "copy_ready_text": copy_ready,
            "recommended_aspect_ratio": compiled["recommended_aspect_ratio"],
            "anchors_used": compiled["anchors_used"],
            "dna_seed": compiled["dna_seed"],
            "width": compiled["width"],
            "height": compiled["height"],
            "preset_id": compiled.get("preset_id"),
            "routing_mode": compiled.get("routing_mode"),
            "layers_applied": compiled.get("layers_applied", []),
            **effective,
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
            director_rag_cues=rag_cues,
        )
        state_override = _resolve_sheet_override(char, [st.state_code, "state"])
        state_effective = _apply_sheet_overrides(compiled_st, state_override, active_style_code)
        state_copy_ready = (
            f"{state_effective['effective_prompt']}\n\n"
            f"--negative_prompt: {state_effective['effective_negative_prompt']}\n"
            f"--aspect_ratio: {compiled_st['recommended_aspect_ratio']}\n"
            f"--seed: {compiled_st['dna_seed']}"
        )
        states_prompts_map[st.state_code] = {
            "state_id": str(st.id),
            "state_code": st.state_code,
            "card_title": compiled_st["card_title"],
            "positive_prompt": state_effective["effective_prompt"],
            "negative_prompt": state_effective["effective_negative_prompt"],
            "copy_ready_text": state_copy_ready,
            "recommended_aspect_ratio": compiled_st["recommended_aspect_ratio"],
            "anchors_used": compiled_st["anchors_used"],
            "dna_seed": compiled_st["dna_seed"],
            "width": compiled_st["width"],
            "height": compiled_st["height"],
            "preset_id": compiled_st.get("preset_id"),
            "routing_mode": compiled_st.get("routing_mode"),
            "layers_applied": compiled_st.get("layers_applied", []),
            **state_effective,
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
        "resolution_width": width,
        "resolution_height": height,
        "is_2k": max(width, height) >= 1920,
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
    active_style_code = (
        (mpb.style_parameters.get("master_style_code") if mpb and mpb.style_parameters else None)
        or (proj.target_style_code if proj else None)
        or "#Style 01"
    )
    override_keys = (
        [target_state.state_code, "state"]
        if target_state is not None
        else [slot_to_compile, payload.angle or "front"]
    )
    stored_override = _resolve_sheet_override(char, override_keys)
    has_prompt_override = bool(
        (payload.prompt_override or "").strip()
        or str(stored_override.get("prompt_override") or "").strip()
    )
    active_gate = resolve_style_gate(active_style_code)
    is_frozen_closeup = slot_to_compile in ("closeup", "close_up", "headshot", "portrait", "master_closeup", "slot_1") and active_gate.routing_mode != "strict_bypass"

    director_slots_dict = None
    if is_frozen_closeup and not has_prompt_override:
        director_slots_dict = await DirectorRAGClient.retrieve_character_casting_slots(
            character_name=char.name or "Character",
            raw_biometric_text=char.base_prompt or "",
            style_code=active_style_code,
            narrative_summary=char.narrative_summary or "",
        )

    rag_cues = (
        await _fetch_character_sheet_rag_cues(
            style_code=active_style_code,
            character_name=char.name or "Character",
            slot_label=f"character {slot_to_compile} look-dev",
        )
        if (not has_prompt_override and not is_frozen_closeup)
        else ""
    )
    compiled = compile_sheet_prompt(
        character=char,
        project=proj,
        bible=mpb,
        slot=slot_to_compile,
        target_state=target_state,
        aspect_ratio=payload.aspect_ratio,
        director_rag_cues=rag_cues,
        director_slots=director_slots_dict,
    )
    effective = _apply_sheet_overrides(compiled, stored_override, active_style_code)

    angle_key = compiled["slot"]
    card_aspect = compiled["recommended_aspect_ratio"]
    width = compiled["width"]
    height = compiled["height"]
    prompt = (payload.prompt_override or "").strip() or effective["effective_prompt"]
    negative_prompt = effective["effective_negative_prompt"]
    anchors_used = compiled["anchors_used"]
    ref_candidates = compiled["ref_candidates"]

    ref_urls = [u for label, u in ref_candidates if u]
    valid_ref_paths = [
        p for p in [_url_to_local_path(u) for u in ref_urls]
        if p and os.path.exists(p) and os.path.getsize(p) > 2048
    ][:4]

    resolved_render = resolve_effective_render_provider(
        project_id=str(char.project_id),
        requested_provider=payload.provider,
        requested_model=payload.model,
        ignored_override_values=("ag_gemini_flash", "default", None),
        default_provider="9router",
        default_model="ag/gemini-3.8-flash",
    )
    prov = resolved_render["provider_id"]
    model_to_use = resolved_render["model_id"]
    base_url_to_use = resolved_render["base_url"]
    api_key_to_use = resolved_render["api_key"]
    use_universal_adapter = resolved_render["use_universal_adapter"]
    width, height = resolve_provider_dimensions(prov, width, height, card_aspect)

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
    if use_universal_adapter:
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
    dims = _read_image_dimensions_from_url(gen_res_url)
    actual_w, actual_h = dims if dims else (width, height)
    is_2k_flag = max(actual_w, actual_h) >= 1920

    meta = dict(char.sheet_metadata or {})
    if payload.target_type == "state" and target_state:
        target_state.image_url = gen_res_url
        meta[f"state_{target_state.id}"] = {
            "image_url": gen_res_url,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "anchors_used": anchors_used,
            "provider": res_provider,
            "model": res_model,
            "seed": dna_seed,
            "aspect_ratio": card_aspect,
            "width": actual_w,
            "height": actual_h,
            "resolution_width": actual_w,
            "resolution_height": actual_h,
            "is_2k": is_2k_flag,
            "rendered_at": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
        }
        char.sheet_metadata = meta
        flag_modified(char, "sheet_metadata")
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

        meta[angle_key] = {
            "image_url": gen_res_url,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "anchors_used": anchors_used,
            "provider": res_provider,
            "model": res_model,
            "seed": dna_seed,
            "aspect_ratio": card_aspect,
            "width": actual_w,
            "height": actual_h,
            "resolution_width": actual_w,
            "resolution_height": actual_h,
            "is_2k": is_2k_flag,
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
        "width": actual_w,
        "height": actual_h,
        "resolution_width": actual_w,
        "resolution_height": actual_h,
        "is_2k": is_2k_flag,
        "compiled_prompt": prompt,
        "effective_prompt": prompt,
        "compiled_negative_prompt": effective["compiled_negative_prompt"],
        "effective_negative_prompt": negative_prompt,
        "has_override": effective["has_override"] or bool((payload.prompt_override or "").strip()),
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

    dims = _read_image_dimensions_from_url(job.image_url)
    actual_w, actual_h = dims if dims else (None, None)
    is_2k_flag = bool(actual_w and actual_h and max(actual_w, actual_h) >= 1920)
    meta = dict(char.sheet_metadata or {})

    if payload.target_type == "state" and payload.state_id:
        s_uuid = _parse_uuid(payload.state_id, "state_id")
        target_state = (
            await session.execute(select(CharacterStateModel).where(CharacterStateModel.id == s_uuid))
        ).scalar_one_or_none()
        if target_state:
            target_state.image_url = job.image_url
            meta[f"state_{target_state.id}"] = {
                "image_url": job.image_url,
                "prompt": job.prompt,
                "anchors_used": job.reference_image_paths or [],
                "provider": "google_flow",
                "seed": char.dna_seed,
                "aspect_ratio": job.aspect_ratio,
                "width": actual_w,
                "height": actual_h,
                "resolution_width": actual_w,
                "resolution_height": actual_h,
                "is_2k": is_2k_flag,
                "rendered_at": datetime.now(timezone.utc).isoformat(),
                "status": "completed",
            }
            char.sheet_metadata = meta
            flag_modified(char, "sheet_metadata")
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

        meta[angle_key] = {
            "image_url": job.image_url,
            "prompt": job.prompt,
            "anchors_used": job.reference_image_paths or [],
            "provider": "google_flow",
            "seed": char.dna_seed,
            "aspect_ratio": job.aspect_ratio,
            "width": actual_w,
            "height": actual_h,
            "resolution_width": actual_w,
            "resolution_height": actual_h,
            "is_2k": is_2k_flag,
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

    resolved_render = resolve_effective_render_provider(
        project_id=str(project.id),
        requested_provider=payload.image_provider,
        requested_model=payload.model,
        ignored_override_values=("ag_gemini_flash", "default", None),
        default_provider="9router",
        default_model="gemini-3.1-flash-image",
    )
    prov = resolved_render["provider_id"]
    resolved_model_id = resolved_render["model_id"]
    resolved_base_url = resolved_render["base_url"]
    resolved_api_key = resolved_render["api_key"]
    use_universal_adapter = resolved_render["use_universal_adapter"]
    target = (payload.target or "closeup").lower().strip()

    async def _run_sync_preview_slot(
        slot_label: str,
        compiled_slot: dict[str, Any],
        aspect_ratio_val: str,
        ref_paths_val: list[str] | None = None,
    ) -> str:
        safe_w, safe_h = resolve_provider_dimensions(
            prov, compiled_slot["width"], compiled_slot["height"], aspect_ratio_val
        )
        if use_universal_adapter:
            adapter = UniversalImageAdapter()
            u_req = UniversalImageRequest(
                provider_id=prov,
                model_id=resolved_model_id,
                prompt=compiled_slot["positive_prompt"],
                negative_prompt=compiled_slot["negative_prompt"],
                aspect_ratio=aspect_ratio_val,
                width=safe_w,
                height=safe_h,
                seed=dna_seed,
                reference_image_paths=ref_paths_val,
                base_url_override=resolved_base_url,
                api_key_override=resolved_api_key,
                enable_fallback=True,
            )
            try:
                u_res = await adapter.generate_image(u_req)
                src = u_res.local_path
                if not src or not os.path.exists(src):
                    src = _url_to_local_path(u_res.local_url)
                if not src or not os.path.exists(src):
                    raise RuntimeError(f"Generated {slot_label} file could not be located on disk.")
                return src
            except RateLimitExceededError as rle:
                logger.warning("preview_%s_rate_limited: %s", slot_label.lower(), str(rle))
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(rle))
            except Exception as exc:
                logger.error("preview_%s_failed: %s", slot_label.lower(), str(exc))
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Image generation failed via {prov}: {str(exc)}",
                )

        model_to_use = payload.model or (
            "gemini-3.1-flash-image" if prov in ("ag_gemini_flash", "antigravity") else None
        )
        provider_inst = get_image_provider(prov)
        req_slot = ImageGenerationRequest(
            prompt=compiled_slot["positive_prompt"],
            negative_prompt=compiled_slot["negative_prompt"],
            seed=dna_seed,
            randomize_seed=False,
            width=safe_w,
            height=safe_h,
            provider="9router" if prov in ("ag_gemini_flash", "antigravity") else prov,
            model=model_to_use,
            enable_fallback=True,
            reference_image_paths=ref_paths_val or [],
        )
        try:
            gen_res = await provider_inst.generate(req_slot)
        except RateLimitExceededError as rle:
            logger.warning("preview_%s_rate_limited: %s", slot_label.lower(), str(rle))
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(rle))
        except ImageGenerationError as ige:
            logger.error("preview_%s_failed: %s", slot_label.lower(), str(ige))
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(ige))

        src = _url_to_local_path(gen_res.local_url)
        if not src or not os.path.exists(src):
            if gen_res.local_path and os.path.exists(gen_res.local_path):
                src = gen_res.local_path
            else:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Generated {slot_label} preview file could not be located on disk.",
                )
        return src

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
        aspect_to_use = "1:1" if target in ("closeup", "all") else (payload.aspect_ratio or "1:1")
        preview_style_code = (
            (mpb.style_parameters.get("master_style_code") if mpb and mpb.style_parameters else None)
            or (project.target_style_code if project else None)
            or "#Style 01"
        )
        preview_gate = resolve_style_gate(preview_style_code)
        preview_director_slots = None
        if preview_gate.routing_mode != "strict_bypass":
            preview_director_slots = await DirectorRAGClient.retrieve_character_casting_slots(
                character_name=payload.name or "Character",
                raw_biometric_text=payload.base_visual_prompt or "",
                style_code=preview_style_code,
            )
        compiled_closeup = compile_sheet_prompt(
            character=dummy_char,
            project=project,
            bible=mpb,
            slot="closeup",
            aspect_ratio=aspect_to_use,
            director_slots=preview_director_slots,
        )
        if prov in ("google_flow", "google-flow"):
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
            src_path = await _run_sync_preview_slot("Close-Up", compiled_closeup, aspect_to_use)
            validate_raster_image_file(src_path)
            shutil.copyfile(src_path, closeup_file)
            c_dims = _read_image_dimensions_from_path(closeup_file)
            _update_preview_manifest(temp_dir, "closeup", closeup_file.name, dims=c_dims)
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
                    "slot_dimensions": {
                        "closeup": {
                            "resolution_width": c_dims[0] if c_dims else 1024,
                            "resolution_height": c_dims[1] if c_dims else 1024,
                            "is_2k": bool(c_dims and max(c_dims) >= 1920),
                        }
                    },
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

        if prov in ("google_flow", "google-flow"):
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
            src_path = await _run_sync_preview_slot(
                "Expression Sheet", compiled_expr, aspect_to_use_expr, ref_paths_expr
            )
            # Strict magic bytes raster check before staging
            validate_raster_image_file(src_path)
            shutil.copyfile(src_path, expr_file)
            _update_preview_manifest(temp_dir, "expression", expr_file.name, dims=_read_image_dimensions_from_path(expr_file))
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

        if prov in ("google_flow", "google-flow"):
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
            src_path = await _run_sync_preview_slot(
                "Full Body", compiled_front, aspect_to_use_front, ref_paths
            )
            # Strict magic bytes raster check before staging
            validate_raster_image_file(src_path)
            shutil.copyfile(src_path, front_file)
            _update_preview_manifest(temp_dir, "front", front_file.name, dims=_read_image_dimensions_from_path(front_file))
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

    slot_dims: dict[str, Any] = {}
    for s_key, f_path in (("closeup", closeup_file), ("expression", expr_file), ("front", front_file)):
        d = _read_image_dimensions_from_path(f_path)
        if d:
            slot_dims[s_key] = {
                "resolution_width": d[0],
                "resolution_height": d[1],
                "is_2k": max(d) >= 1920,
            }

    return {
        "status": "completed",
        "preview_token": preview_token,
        "closeup_url": closeup_url,
        "expression_url": expression_url,
        "front_url": front_url,
        "dna_seed": dna_seed,
        "provider": prov,
        "slot_dimensions": slot_dims,
        "message": "Pre-creation visual previews ready for inspection",
    }


def _update_preview_manifest(
    temp_dir: Path,
    slot_name: str,
    active_file: str,
    *,
    dims: tuple[int, int] | None = None,
    previous_1k_file: str | None = None,
) -> dict[str, Any]:
    manifest_path = temp_dir / "preview_manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}

    w, h = dims if dims else (None, None)
    is_2k_val = bool(w and h and max(w, h) >= 1920)
    entry: dict[str, Any] = {
        "active_file": active_file,
        "resolution_width": w,
        "resolution_height": h,
        "is_2k": is_2k_val,
    }
    if previous_1k_file:
        entry["previous_1k_file"] = previous_1k_file
    manifest[slot_name] = entry
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return entry


def _resolve_upscale_2k_provider(
    project_id: str | None,
    provider_override: str | None = None,
    model_override: str | None = None,
) -> dict[str, Any]:
    """Resolve a 2K-native + reference-capable cloud provider or auto-route if configured."""
    render_cfg = get_project_render_config(str(project_id)) if project_id else None
    configs = (render_cfg.get("configs") or {}) if render_cfg else {}

    active_prov = (
        (provider_override or "").strip()
        or (render_cfg.get("active_provider_id") if render_cfg else None)
        or "9router"
    )
    _, active_cfg = _lookup_provider_config(configs, active_prov)
    active_cfg = active_cfg or {}
    active_model = (model_override or "").strip() or active_cfg.get("modelId")
    active_base_url = active_cfg.get("baseUrl")
    active_key = decrypt_key(active_cfg.get("apiKey", "")) if active_cfg.get("apiKey") else ""

    supported, reason = supports_native_2k_upscale(active_prov, model_id=active_model)
    if supported and active_key:
        return {
            "provider_id": active_prov,
            "model_id": active_model,
            "base_url": active_base_url,
            "api_key": active_key,
            "auto_routed_from": None,
            "route_reason": reason,
        }

    # Capability fallback: auto-route to the highest-priority configured 2K + reference provider
    for cand_pid in AUTO_ROUTE_2K_PRIORITY:
        matched_key, cand_cfg = _lookup_provider_config(configs, cand_pid)
        if not cand_cfg or not matched_key:
            continue
        cand_model = cand_cfg.get("modelId")
        cand_key = decrypt_key(cand_cfg.get("apiKey", "")) if cand_cfg.get("apiKey") else ""
        cand_ok, cand_reason = supports_native_2k_upscale(matched_key, model_id=cand_model)
        if cand_ok and cand_key:
            return {
                "provider_id": matched_key,
                "model_id": cand_model,
                "base_url": cand_cfg.get("baseUrl"),
                "api_key": cand_key,
                "auto_routed_from": active_prov,
                "route_reason": f"Auto-routed from '{active_prov}' to '{matched_key}': {cand_reason}",
            }

    if not supported:
        detail_msg = (
            f"Provider aktif '{active_prov}' tidak mendukung Upscale 2K native + reference image ({reason}). "
            "Konfigurasikan API key untuk Seedream 5.5, FLUX, atau Gemini Direct di Render Settings."
        )
    else:
        detail_msg = (
            f"API key untuk provider 2K '{active_prov}' belum dikonfigurasi. "
            "Tambahkan API key pada Render Settings sebelum melakukan Upscale 2K."
        )
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "error_code": "UPSCALE_2K_PROVIDER_UNSUPPORTED",
            "message": detail_msg,
            "active_provider": active_prov,
        },
    )


class CharacterAssetUpscaleRequest(BaseModel):
    slot_key: str | None = Field(
        default=None,
        description="'closeup', 'expression', 'front', 'side', 'three_quarter', 'back', 'tpose', 'action', or 'state'",
    )
    state_id: str | None = Field(default=None, description="Character state UUID when upscaling a Dynamic State")
    provider_override: str | None = Field(default=None, description="Optional 2K provider override")
    model_override: str | None = Field(default=None, description="Optional model override")


class CharacterAssetRevertRequest(BaseModel):
    slot_key: str | None = Field(default=None, description="Sheet slot key to revert to 1K")
    state_id: str | None = Field(default=None, description="State UUID to revert to 1K")


class CharacterPreviewUpscaleRequest(BaseModel):
    project_id: str | None = Field(default=None, description="Project ID (optional when supplied in path)")
    preview_token: str = Field(description="Active pre-creation staging preview token")
    slot: Literal["closeup", "expression", "front"] = Field(default="closeup")
    name: str = Field(default="Character")
    role: str = Field(default="PROTAGONIST")
    base_visual_prompt: str = Field(default="")
    dna_seed: int | None = Field(default=None)
    provider_override: str | None = Field(default=None)
    model_override: str | None = Field(default=None)


class CharacterPreviewRevertRequest(BaseModel):
    preview_token: str = Field(description="Active pre-creation staging preview token")
    slot: Literal["closeup", "expression", "front"] = Field(default="closeup")


_SLOT_URL_ATTR_MAP: dict[str, str] = {
    "closeup": "closeup_image_url",
    "front": "front_image_url",
    "side": "side_image_url",
    "three_quarter": "three_quarter_image_url",
    "back": "back_image_url",
    "tpose": "tpose_image_url",
    "action": "action_image_url",
    "expression": "expression_image_url",
}


@router.post("/bible/characters/{character_id}/upscale-asset", status_code=status.HTTP_200_OK)
@router.post("/characters/{character_id}/upscale-asset", status_code=status.HTTP_200_OK)
async def upscale_character_asset_2k(
    character_id: str,
    payload: CharacterAssetUpscaleRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Perform reference-guided native 2K refinement via direct cloud HTTP API adapter."""
    c_uuid = _parse_uuid(character_id, "character_id")
    char = (await session.execute(select(CharacterModel).where(CharacterModel.id == c_uuid))).scalar_one_or_none()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    if not char.dna_seed:
        char.dna_seed = int(hashlib.sha256(str(char.id).encode()).hexdigest()[:8], 16) % 900000 + 100000

    proj = (await session.execute(select(ProjectModel).where(ProjectModel.id == char.project_id))).scalar_one_or_none()
    mpb_stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == char.project_id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    mpb = (await session.execute(mpb_stmt)).scalar_one_or_none()

    active_style_code = (
        (mpb.style_parameters.get("master_style_code") if mpb and mpb.style_parameters else None)
        or (proj.target_style_code if proj else None)
        or "#Style 01"
    )

    target_state: CharacterStateModel | None = None
    is_state = bool(payload.state_id) or (payload.slot_key or "").strip().lower() == "state"
    if is_state:
        if not payload.state_id:
            raise HTTPException(status_code=400, detail="state_id is required when upscaling a Dynamic State")
        s_uuid = _parse_uuid(payload.state_id, "state_id")
        target_state = (
            await session.execute(
                select(CharacterStateModel).where(
                    CharacterStateModel.id == s_uuid,
                    CharacterStateModel.character_id == char.id,
                )
            )
        ).scalar_one_or_none()
        if not target_state:
            raise HTTPException(status_code=404, detail="Character state not found")
        slot_key = "state"
        meta_key = f"state_{target_state.id}"
        current_url = target_state.image_url
        override_keys = [target_state.state_code, "state"]
    else:
        slot_key = _normalize_sheet_slot(payload.slot_key, default="closeup")
        if slot_key not in _SLOT_URL_ATTR_MAP:
            raise HTTPException(status_code=400, detail=f"Invalid slot_key '{payload.slot_key}'")
        meta_key = slot_key
        current_url = getattr(char, _SLOT_URL_ATTR_MAP[slot_key], None)
        override_keys = [slot_key]

    if not current_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Slot '{meta_key}' has no generated 1K image yet to upscale.",
        )

    source_local_path = _url_to_local_path(current_url)
    if not source_local_path or not os.path.exists(source_local_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source image file for '{meta_key}' could not be located on disk.",
        )

    # Resolve 2K-native + reference-capable provider (with auto-route if active provider lacks 2K+ref)
    resolved_2k = _resolve_upscale_2k_provider(
        str(char.project_id),
        provider_override=payload.provider_override,
        model_override=payload.model_override,
    )

    stored_override = _resolve_sheet_override(char, override_keys)
    active_gate = resolve_style_gate(active_style_code)
    director_slots_dict = None
    if slot_key == "closeup" and active_gate.routing_mode != "strict_bypass" and not stored_override.get("prompt_override"):
        director_slots_dict = await DirectorRAGClient.retrieve_character_casting_slots(
            character_name=char.name or "Character",
            raw_biometric_text=char.base_prompt or "",
            style_code=active_style_code,
            narrative_summary=char.narrative_summary or "",
        )

    compiled = compile_sheet_prompt(
        character=char,
        project=proj,
        bible=mpb,
        slot=slot_key,
        target_state=target_state,
        director_slots=director_slots_dict,
    )
    effective = _apply_sheet_overrides(compiled, stored_override, active_style_code)

    has_state_wear = False
    if target_state is not None:
        wear_str = (target_state.injuries_and_wear or "").strip().lower()
        has_state_wear = bool(wear_str and wear_str not in ("none", "zero defects"))

    upscale_compiled = compile_upscale_2k_prompt(
        slot_key=slot_key,
        style_code=active_style_code,
        base_positive_prompt=effective["effective_prompt"],
        base_negative_prompt=effective["effective_negative_prompt"],
        style_family=compiled.get("style_family", "photorealistic"),
        has_override=effective["has_override"],
        has_injuries_or_wear=has_state_wear,
    )

    adapter = UniversalImageAdapter()
    req = UniversalImageRequest(
        provider_id=resolved_2k["provider_id"],
        model_id=resolved_2k["model_id"],
        prompt=upscale_compiled["positive_prompt"],
        negative_prompt=upscale_compiled["negative_prompt"],
        aspect_ratio=upscale_compiled["aspect_ratio"],
        width=upscale_compiled["target_width"],
        height=upscale_compiled["target_height"],
        seed=char.dna_seed,
        reference_image_paths=[source_local_path],
        strength=0.35,
        filename_suffix=f"_2k_{int(time.time() * 1000)}",
        style_code=active_style_code,
        base_url_override=resolved_2k["base_url"],
        api_key_override=resolved_2k["api_key"],
        enable_fallback=False,
    )

    try:
        gen_res = await adapter.generate_image(req)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upscale 2K failed via {resolved_2k['provider_id']}: {str(exc)}",
        )

    validate_raster_image_file(gen_res.local_path)
    real_dims = _read_image_dimensions_from_path(gen_res.local_path)
    if not real_dims:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to inspect output pixel dimensions after 2K upscale.",
        )
    actual_w, actual_h = real_dims
    is_2k = max(actual_w, actual_h) >= 1920

    meta = dict(char.sheet_metadata or {})
    prev_entry = meta.get(meta_key) if isinstance(meta.get(meta_key), dict) else {}
    previous_1k_url = prev_entry.get("previous_1k_url")
    if not previous_1k_url and not prev_entry.get("is_2k"):
        previous_1k_url = current_url

    new_url = gen_res.local_url
    if target_state is not None:
        target_state.image_url = new_url
    else:
        setattr(char, _SLOT_URL_ATTR_MAP[slot_key], new_url)

    meta[meta_key] = {
        **prev_entry,
        "image_url": new_url,
        "previous_1k_url": previous_1k_url,
        "resolution_width": actual_w,
        "resolution_height": actual_h,
        "width": actual_w,
        "height": actual_h,
        "is_2k": is_2k,
        "provider": gen_res.provider_id,
        "model": gen_res.model_id or resolved_2k["model_id"],
        "aspect_ratio": upscale_compiled["aspect_ratio"],
        "prompt": upscale_compiled["positive_prompt"],
        "negative_prompt": upscale_compiled["negative_prompt"],
        "upscaled_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
    }
    char.sheet_metadata = meta
    flag_modified(char, "sheet_metadata")
    await session.commit()

    return {
        "status": "completed",
        "character_id": str(char.id),
        "slot_key": slot_key,
        "state_id": payload.state_id,
        "image_url": new_url,
        "previous_1k_url": previous_1k_url,
        "resolution_width": actual_w,
        "resolution_height": actual_h,
        "is_2k": is_2k,
        "provider": gen_res.provider_id,
        "model": gen_res.model_id or resolved_2k["model_id"],
        "auto_routed_from": resolved_2k["auto_routed_from"],
        "message": (
            f"Upscaled to {actual_w}×{actual_h} (2K)"
            if is_2k
            else f"Provider returned {actual_w}×{actual_h} (< 1920px, not labeled as 2K)"
        ),
    }


@router.post("/bible/characters/{character_id}/revert-asset", status_code=status.HTTP_200_OK)
@router.post("/characters/{character_id}/revert-asset", status_code=status.HTTP_200_OK)
async def revert_character_asset_1k(
    character_id: str,
    payload: CharacterAssetRevertRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Revert an upscaled character asset or dynamic state back to its stored 1K image."""
    c_uuid = _parse_uuid(character_id, "character_id")
    char = (await session.execute(select(CharacterModel).where(CharacterModel.id == c_uuid))).scalar_one_or_none()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    meta = dict(char.sheet_metadata or {})
    target_state: CharacterStateModel | None = None
    is_state = bool(payload.state_id) or (payload.slot_key or "").strip().lower() == "state"

    if is_state:
        if not payload.state_id:
            raise HTTPException(status_code=400, detail="state_id is required when reverting a Dynamic State")
        s_uuid = _parse_uuid(payload.state_id, "state_id")
        target_state = (
            await session.execute(
                select(CharacterStateModel).where(
                    CharacterStateModel.id == s_uuid,
                    CharacterStateModel.character_id == char.id,
                )
            )
        ).scalar_one_or_none()
        if not target_state:
            raise HTTPException(status_code=404, detail="Character state not found")
        slot_key = "state"
        meta_key = f"state_{target_state.id}"
    else:
        slot_key = _normalize_sheet_slot(payload.slot_key, default="closeup")
        if slot_key not in _SLOT_URL_ATTR_MAP:
            raise HTTPException(status_code=400, detail=f"Invalid slot_key '{payload.slot_key}'")
        meta_key = slot_key

    slot_entry = dict(meta.get(meta_key) or {})
    prev_1k_url = slot_entry.get("previous_1k_url")
    if not prev_1k_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No previous_1k_url recorded for '{meta_key}'.",
        )

    if target_state is not None:
        target_state.image_url = prev_1k_url
    else:
        setattr(char, _SLOT_URL_ATTR_MAP[slot_key], prev_1k_url)

    dims = _read_image_dimensions_from_url(prev_1k_url)
    actual_w, actual_h = dims if dims else (1024, 1024)
    is_2k = max(actual_w, actual_h) >= 1920

    slot_entry["image_url"] = prev_1k_url
    slot_entry.pop("previous_1k_url", None)
    slot_entry["width"] = actual_w
    slot_entry["height"] = actual_h
    slot_entry["resolution_width"] = actual_w
    slot_entry["resolution_height"] = actual_h
    slot_entry["is_2k"] = is_2k
    slot_entry["reverted_at"] = datetime.now(timezone.utc).isoformat()
    meta[meta_key] = slot_entry

    char.sheet_metadata = meta
    flag_modified(char, "sheet_metadata")
    await session.commit()

    return {
        "status": "reverted",
        "character_id": str(char.id),
        "slot_key": slot_key,
        "state_id": payload.state_id,
        "image_url": prev_1k_url,
        "resolution_width": actual_w,
        "resolution_height": actual_h,
        "is_2k": is_2k,
        "message": f"Reverted {meta_key} back to 1K ({actual_w}×{actual_h})",
    }


@router.post("/projects/{project_id}/characters/preview/upscale", status_code=status.HTTP_200_OK)
@router.post("/bible/projects/{project_id}/characters/preview/upscale", status_code=status.HTTP_200_OK)
@router.post("/bible/characters/preview/upscale", status_code=status.HTTP_200_OK)
async def upscale_character_preview_2k(
    payload: CharacterPreviewUpscaleRequest,
    project_id: str | None = None,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Upscale a staged pre-creation preview (closeup/expression/front) to native 2K."""
    eff_project_id = project_id or payload.project_id
    project = await _resolve_project(eff_project_id, session) if eff_project_id else None
    mpb = await _load_latest_bible(project, session) if project else None

    clean_token = Path(payload.preview_token).name
    settings = get_settings()
    temp_dir = settings.effective_preview_storage_path.parent / "temp_previews" / clean_token
    if not temp_dir.exists():
        temp_dir = Path("./data/assets/temp_previews") / clean_token
    if not temp_dir.exists():
        raise HTTPException(status_code=404, detail="Preview staging directory not found")

    slot_name = payload.slot
    manifest_path = temp_dir / "preview_manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}

    slot_info = manifest.get(slot_name) if isinstance(manifest.get(slot_name), dict) else {}
    active_fname = slot_info.get("active_file") or f"{slot_name}.png"
    src_file = temp_dir / Path(active_fname).name
    if not src_file.exists():
        src_file = temp_dir / f"{slot_name}.png"
    if not src_file.exists():
        raise HTTPException(status_code=400, detail=f"Preview '{slot_name}' image has not been generated yet.")

    resolved_2k = _resolve_upscale_2k_provider(
        str(project.id) if project else None,
        provider_override=payload.provider_override,
        model_override=payload.model_override,
    )

    active_style_code = (
        (mpb.style_parameters.get("master_style_code") if mpb and mpb.style_parameters else None)
        or (project.target_style_code if project else None)
        or "#Style 01"
    )
    dna_seed = payload.dna_seed or (
        int(hashlib.sha256(f"{payload.name}_{clean_token}".encode()).hexdigest()[:8], 16) % 900000 + 100000
    )
    dummy_char = CharacterModel(
        id=uuid.uuid4(),
        project_id=project.id if project else uuid.uuid4(),
        name=payload.name or "Character",
        role=payload.role,
        base_prompt=payload.base_visual_prompt or "an authentic human individual",
        dna_seed=dna_seed,
        sheet_metadata={},
    )
    if (temp_dir / "closeup.png").exists():
        dummy_char.closeup_image_url = f"/api/v1/assets/temp-previews/{clean_token}/closeup.png"

    compiled = compile_sheet_prompt(
        character=dummy_char,
        project=project,
        bible=mpb,
        slot=slot_name,
    )
    upscale_compiled = compile_upscale_2k_prompt(
        slot_key=slot_name,
        style_code=active_style_code,
        base_positive_prompt=compiled["positive_prompt"],
        base_negative_prompt=compiled["negative_prompt"],
        style_family=compiled.get("style_family", "photorealistic"),
    )

    adapter = UniversalImageAdapter()
    req = UniversalImageRequest(
        provider_id=resolved_2k["provider_id"],
        model_id=resolved_2k["model_id"],
        prompt=upscale_compiled["positive_prompt"],
        negative_prompt=upscale_compiled["negative_prompt"],
        aspect_ratio=upscale_compiled["aspect_ratio"],
        width=upscale_compiled["target_width"],
        height=upscale_compiled["target_height"],
        seed=dna_seed,
        reference_image_paths=[str(src_file.resolve())],
        strength=0.35,
        filename_suffix=f"_2k_{int(time.time() * 1000)}",
        style_code=active_style_code,
        base_url_override=resolved_2k["base_url"],
        api_key_override=resolved_2k["api_key"],
        enable_fallback=False,
    )

    try:
        gen_res = await adapter.generate_image(req)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Preview Upscale 2K failed via {resolved_2k['provider_id']}: {str(exc)}",
        )

    validate_raster_image_file(gen_res.local_path)
    real_dims = _read_image_dimensions_from_path(gen_res.local_path)
    if not real_dims:
        raise HTTPException(status_code=502, detail="Failed to inspect upscaled preview dimensions.")
    actual_w, actual_h = real_dims
    is_2k = max(actual_w, actual_h) >= 1920

    prev_1k_fname = slot_info.get("previous_1k_file")
    if not prev_1k_fname and not slot_info.get("is_2k"):
        prev_1k_fname = src_file.name

    ts = int(time.time() * 1000)
    new_fname = f"{slot_name}_2k_{ts}.png"
    dest_2k = temp_dir / new_fname
    shutil.copyfile(gen_res.local_path, dest_2k)

    _update_preview_manifest(
        temp_dir,
        slot_name,
        new_fname,
        dims=(actual_w, actual_h),
        previous_1k_file=prev_1k_fname,
    )
    new_url = f"/api/v1/assets/temp-previews/{clean_token}/{new_fname}?v={ts}"
    prev_1k_url = f"/api/v1/assets/temp-previews/{clean_token}/{prev_1k_fname}" if prev_1k_fname else None

    return {
        "status": "completed",
        "preview_token": clean_token,
        "slot": slot_name,
        "image_url": new_url,
        "previous_1k_url": prev_1k_url,
        "resolution_width": actual_w,
        "resolution_height": actual_h,
        "is_2k": is_2k,
        "provider": gen_res.provider_id,
        "model": gen_res.model_id or resolved_2k["model_id"],
        "message": (
            f"Upscaled to {actual_w}×{actual_h} (2K)"
            if is_2k
            else f"Provider returned {actual_w}×{actual_h} (< 1920px, not labeled as 2K)"
        ),
    }


@router.post("/projects/{project_id}/characters/preview/revert", status_code=status.HTTP_200_OK)
@router.post("/bible/projects/{project_id}/characters/preview/revert", status_code=status.HTTP_200_OK)
@router.post("/bible/characters/preview/revert", status_code=status.HTTP_200_OK)
async def revert_character_preview_1k(
    payload: CharacterPreviewRevertRequest,
    project_id: str | None = None,
    current_user: UserModel = Depends(get_current_user),
) -> dict[str, Any]:
    """Revert a staged pre-creation preview slot back to its 1K image."""
    clean_token = Path(payload.preview_token).name
    settings = get_settings()
    temp_dir = settings.effective_preview_storage_path.parent / "temp_previews" / clean_token
    if not temp_dir.exists():
        temp_dir = Path("./data/assets/temp_previews") / clean_token
    if not temp_dir.exists():
        raise HTTPException(status_code=404, detail="Preview staging directory not found")

    manifest_path = temp_dir / "preview_manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=400, detail="No 1K backup recorded for preview revert.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    slot_info = manifest.get(payload.slot) or {}
    prev_1k_fname = slot_info.get("previous_1k_file")
    if not prev_1k_fname:
        raise HTTPException(status_code=400, detail=f"No previous 1K image recorded for preview slot '{payload.slot}'.")

    prev_path = temp_dir / Path(prev_1k_fname).name
    if not prev_path.exists():
        raise HTTPException(status_code=404, detail="Previous 1K preview file missing on disk.")

    dims = _read_image_dimensions_from_path(prev_path)
    actual_w, actual_h = dims if dims else (1024, 1024)
    _update_preview_manifest(
        temp_dir,
        payload.slot,
        prev_path.name,
        dims=(actual_w, actual_h),
        previous_1k_file=None,
    )
    ts = int(time.time() * 1000)
    return {
        "status": "reverted",
        "preview_token": clean_token,
        "slot": payload.slot,
        "image_url": f"/api/v1/assets/temp-previews/{clean_token}/{prev_path.name}?v={ts}",
        "resolution_width": actual_w,
        "resolution_height": actual_h,
        "is_2k": max(actual_w, actual_h) >= 1920,
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
    dims = _read_image_dimensions_from_path(dest_file)
    _update_preview_manifest(temp_dir, target_slot, dest_file.name, dims=dims)
    ts = int(time.time() * 1000)
    new_url = f"/api/v1/assets/temp-previews/{payload.preview_token}/{target_slot}.png?v={ts}"

    return {
        "status": "completed",
        "preview_token": payload.preview_token,
        "slot": target_slot,
        "image_url": new_url,
        "resolution_width": dims[0] if dims else None,
        "resolution_height": dims[1] if dims else None,
        "is_2k": bool(dims and max(dims) >= 1920),
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

