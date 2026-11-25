from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, ValidationInfo, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.app.api.deps import get_current_user, get_session
from backend.app.domain.catalog import validate_matrix_code
from backend.app.domain.screenwriter import (
    _STYLE_FAMILY_OPTICS_DEFAULTS,
    PolyaScreenwriterEngine,
    extract_project_narrative_context,
    get_act_bounds,
    get_style_family,
    parse_structured_slugline,
    _determine_scene_duration,
)
from backend.app.domain.story_writer import StagedStoryWriter
from backend.app.infrastructure.database.models.auth import UserModel
from backend.app.infrastructure.database.models.character import (
    CharacterModel,
    CharacterStateModel,
)
from backend.app.infrastructure.database.models.project import MasterProductionBibleModel, ProjectModel
from backend.app.infrastructure.database.models.story import (
    DialogueCalibrationCacheModel,
    SceneModel,
    ShotModel,
)

router = APIRouter(tags=["Scenes & Storyboard"])


class SceneCreateRequest(BaseModel):
    act_number: int = Field(default=1, ge=1, le=5, description="Act 1 to 5")
    scene_number: int = Field(default=1, ge=1, le=1000, description="Scene number 1 to 1000")
    slugline: str = Field(default="INT. LOCATION - DAY", max_length=255)
    narrative_goal: str = Field(default="", description="Dramatic goal of the scene")
    duration_target: float = Field(default=10.0, ge=1.0, le=60.0, description="Target seconds (default 10.0, e.g. 5.0, 10.0, 15.0)")
    status: str = Field(default="PLANNED", description="PLANNED, IN_PROGRESS, APPROVED, LOCKED")
    generate_blueprint: bool = Field(default=False, description="If True, auto-generate standard 4-Act blueprint")
    total_scenes: int = Field(default=50, ge=1, le=500, description="Total scenes for blueprint (50, 100, 200, 300, 400, 420)")
    duration_mode: str = Field(default="dynamic", description="Pacing profile: dynamic | flat_10s | flat_15s | flat_5s")
    auto_split_shots: bool = Field(default=True, description="If True, auto-generate calibrated shots matching target duration")
    clear_existing: bool = Field(default=False, description="If True, clears existing scenes before generating new blueprint")


class SceneUpdateRequest(BaseModel):
    slugline: str | None = None
    narrative_goal: str | None = None
    duration_target: float | None = Field(default=None, ge=1.0, le=60.0)
    status: str | None = None
    dialogue: str | None = None
    camera_code: str | None = None
    lighting_code: str | None = None
    transition_type: str | None = None
    audio_lead_seconds: float | None = None
    auto_split_shots: bool = Field(default=False, description="If True, automatically generate or adjust shots to match target duration")


class DirectorPolishRequest(BaseModel):
    slugline: str | None = None
    narrative_goal: str | None = None
    dialogue: str | None = None
    style_code: str = "#Style 01"
    camera_code: str | None = None
    lighting_code: str | None = None

    @field_validator("style_code", "camera_code", "lighting_code")
    @classmethod
    def _validate_polish_matrix_codes(cls, value: str | None, info: ValidationInfo) -> str | None:
        return validate_matrix_code(info.field_name or "", value)


class SceneAutoSplitRequest(BaseModel):
    target_duration: float | None = Field(default=None, ge=1.0, le=60.0, description="Target duration in seconds (5.0, 10.0, 15.0)")
    coverage_style: str = Field(
        default="classic_coverage",
        description="Coverage strategy: classic_coverage | visceral_oner | rapid_montage | intimate_subtext",
    )


class BlueprintTreatmentRequest(BaseModel):
    total_scenes: int = Field(default=100, ge=1, le=500, description="Total scenes (50, 100, 200, 300, 400, 420, 450)")
    duration_mode: str = Field(default="dynamic", description="dynamic | flat_10s | flat_15s | flat_5s")
    premise: str = Field(default="", description="Story premise / concept from director")
    clear_existing: bool = Field(default=False, description="Clear existing scenes if re-generating")
    structure_type: str = Field(default="4_act", description="3_act | 4_act | youtube_viral | 5_act")
    enable_cold_open: bool | None = Field(
        default=None,
        description="Explicit 30s Cold Open override; defaults to True for youtube_viral or preset cold_open_30s",
    )
    selected_treatment: dict[str, Any] | None = Field(
        default=None,
        description="Optional user-selected pitch variant from /blueprint/treatment-variants to lock directly",
    )


class BlueprintActGenerateRequest(BaseModel):
    act_number: int = Field(ge=1, le=5, description="Act to generate: 1 to 5")
    total_scenes: int = Field(default=100, ge=1, le=500, description="Total scenes planned")
    duration_mode: str = Field(default="dynamic", description="dynamic | flat_10s | flat_15s | flat_5s")
    auto_split_shots: bool = Field(default=True, description="Auto-split shots per scene")
    structure_type: str = Field(default="4_act", description="3_act | 4_act | youtube_viral | 5_act")
    enable_cold_open: bool | None = Field(
        default=None,
        description="Explicit 30s Cold Open override; defaults to True for youtube_viral or preset cold_open_30s",
    )


class BlueprintBatchWriteRequest(BaseModel):
    total_scenes: int = Field(default=100, ge=1, le=500)
    duration_mode: str = Field(default="dynamic")
    premise: str = Field(default="")
    auto_split_shots: bool = Field(default=True)
    clear_existing: bool = Field(default=True)
    structure_type: str = Field(default="4_act")
    enable_cold_open: bool | None = Field(
        default=None,
        description="Explicit 30s Cold Open override; defaults to True for youtube_viral or preset cold_open_30s",
    )


class StructureRecommendationRequest(BaseModel):
    total_scenes: int = Field(default=100, ge=1, le=500, description="Planned total scenes")


class DialogueCalibrationRequest(BaseModel):
    raw_text: str = Field(description="Dialogue or voiceover text line")
    character_name: str = Field(default="Protagonist", description="Speaking character")
    target_language: str = Field(default="id-ID", description="Target locale: id-ID, en-US")
    max_seconds: float = Field(default=5.0, ge=1.0, le=60.0, description="Maximum duration limit")


class SceneAttachPreviewRequest(BaseModel):
    preview_url: str = Field(..., description="Local or remote URL of the preview image")
    preview_provider: str = Field(default="google_flow", description="Provider used, e.g. google_flow, sd35_large_hf, 9router")
    job_id: str | None = Field(default=None, description="Flow or external job ID if applicable")


SHOT_CAMERA_TEMPLATES = [
    {
        "camera_code": "#Cam 01",  # Eye-Level Neutral / Push-In Master
        "lens_code": "#Lens 02",  # 35mm Wide
        "comp_code": "#Comp 01",  # Rule of Thirds
        "light_code": "#Light 01",
        "act_code": "#Act 01",
        "speed_code": "#Speed 03",
    },
    {
        "camera_code": "#Cam 06",  # Over-The-Shoulder / Profile Coverage
        "lens_code": "#Lens 01",  # 2.0x Anamorphic
        "comp_code": "#Comp 02",  # Leading Lines
        "light_code": "#Light 01",
        "act_code": "#Act 04",
        "speed_code": "#Speed 03",
    },
    {
        "camera_code": "#Cam 13",  # Low-Angle Hero Shot / Close-Up
        "lens_code": "#Lens 03",  # 85mm Portrait
        "comp_code": "#Comp 03",  # Center Framing
        "light_code": "#Light 01",
        "act_code": "#Act 06",
        "speed_code": "#Speed 03",
    },
]


async def _perform_auto_split(
    scene: SceneModel,
    target_duration: float,
    session: AsyncSession,
    coverage_style: str = "classic_coverage",
) -> list[ShotModel]:
    """Dual-brain auto-split shots via Screenwriter (8766) + Director (8765), preserving shot IDs cleanly."""
    ctx_info = await _resolve_scene_speaker_and_style(scene=scene, session=session)

    stmt = (
        select(ShotModel)
        .where(ShotModel.scene_id == scene.id)
        .order_by(ShotModel.shot_number.asc())
    )
    existing_shots = list((await session.execute(stmt)).scalars().all())
    existing_dlg = _extract_scene_dialogue(existing_shots)

    writer = PolyaScreenwriterEngine()
    planned = await writer.plan_scene_shot_split(
        scene_number=scene.scene_number,
        slugline=scene.slugline,
        narrative_goal=scene.narrative_goal,
        dialogue=existing_dlg,
        target_duration=target_duration,
        coverage_style=coverage_style,
        style_code=ctx_info["style_code"],
        act_number=scene.act_number,
        voice_dna_profile=ctx_info["voice_dna_profile"],
        active_state=ctx_info["active_state"],
        speaking_character=ctx_info["speaker_name"],
    )

    now = datetime.now(timezone.utc)
    configured_shots: list[ShotModel] = []

    for i, plan in enumerate(planned):
        if i < len(existing_shots):
            shot = existing_shots[i]
            shot.shot_number = plan["shot_number"]
            shot.duration_seconds = plan["duration_seconds"]
            shot.camera_code = plan["camera_code"]
            shot.lens_code = plan["lens_code"]
            shot.comp_code = plan["comp_code"]
            shot.light_code = plan["light_code"]
            shot.act_code = plan["act_code"]
            shot.speed_code = plan["speed_code"]
            if not shot.dialogue and plan.get("dialogue"):
                shot.dialogue = plan["dialogue"]
            shot.transition_type = plan.get("transition_type") or shot.transition_type
            configured_shots.append(shot)
        else:
            new_shot = ShotModel(
                id=uuid.uuid4(),
                scene_id=scene.id,
                shot_number=plan["shot_number"],
                duration_seconds=plan["duration_seconds"],
                camera_code=plan["camera_code"],
                lens_code=plan["lens_code"],
                comp_code=plan["comp_code"],
                light_code=plan["light_code"],
                act_code=plan["act_code"],
                speed_code=plan["speed_code"],
                dialogue=plan.get("dialogue"),
                transition_type=plan.get("transition_type") or "NONE",
                status="PLANNED",
                created_at=now,
            )
            session.add(new_shot)
            configured_shots.append(new_shot)

    # Remove excess shots if switching to a tighter coverage style (e.g. visceral_oner)
    if len(existing_shots) > len(planned):
        for extra in existing_shots[len(planned) :]:
            await session.delete(extra)

    await session.commit()
    for s in configured_shots:
        await session.refresh(s)
    return configured_shots


def _estimate_syllables_and_pacing(text: str) -> tuple[int, int, float]:
    """Calculate word count, syllable approximation, and estimated duration in seconds."""
    words = text.strip().split()
    word_count = len(words)
    if word_count == 0:
        return 0, 0, 0.0

    # Approximate syllable count: 1.5 syllables per word average in English/Indonesian
    # At standard cinematic delivery speed of ~168 words per minute (2.8 words / sec)
    estimated_duration = round(word_count / 2.8, 2)
    estimated_syllables = int(word_count * 1.6)
    return word_count, estimated_syllables, estimated_duration


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


def _extract_scene_dialogue(shots: list[ShotModel]) -> str | None:
    """Extract Screenwriter-generated dialogue text from a scene's ordered shots."""
    lines: list[str] = []
    for sh in shots:
        raw = (sh.dialogue or "").strip()
        if not raw:
            continue
        if raw.startswith("Environmental cue:") and lines:
            continue
        if raw not in lines:
            lines.append(raw)
    if not lines:
        return None
    return "\n".join(lines)


@router.get("/projects/{project_id}/scenes", status_code=status.HTTP_200_OK)
async def list_project_scenes(
    project_id: str,
    act: int | None = Query(default=None, ge=1, le=5, description="Filter by Act 1-5"),
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve scenes for project across 3-Act, 4-Act, 5-Act, or YouTube structures."""
    project = await _resolve_project(project_id, session)

    stmt = select(SceneModel).where(SceneModel.project_id == project.id)
    if act is not None:
        stmt = stmt.where(SceneModel.act_number == act)

    stmt = stmt.order_by(SceneModel.act_number.asc(), SceneModel.scene_number.asc())
    scenes = (await session.execute(stmt)).scalars().all()

    scene_ids = [s.id for s in scenes]
    shots_by_scene: dict[uuid.UUID, list[ShotModel]] = {}
    if scene_ids:
        shots_stmt = select(ShotModel).where(ShotModel.scene_id.in_(scene_ids)).order_by(ShotModel.shot_number.asc())
        all_shots = (await session.execute(shots_stmt)).scalars().all()
        for sh in all_shots:
            shots_by_scene.setdefault(sh.scene_id, []).append(sh)

    data = []
    for s in scenes:
        scene_shots = shots_by_scene.get(s.id, [])
        shot_count = len(scene_shots)
        primary_shot = scene_shots[0] if scene_shots else None

        preview_url = None
        preview_provider = None
        audio_lead_seconds = None
        if primary_shot and isinstance(primary_shot.fg_bg_layers, dict):
            preview_url = primary_shot.fg_bg_layers.get("preview_url")
            preview_provider = primary_shot.fg_bg_layers.get("preview_provider")
            audio_lead_seconds = primary_shot.fg_bg_layers.get("audio_lead_seconds")

        data.append(
            {
                "id": str(s.id),
                "project_id": str(s.project_id),
                "act_number": s.act_number,
                "scene_number": s.scene_number,
                "slugline": s.slugline,
                "narrative_goal": s.narrative_goal,
                "duration_target": s.duration_target,
                "status": s.status,
                "shots_count": shot_count,
                "dialogue": _extract_scene_dialogue(scene_shots),
                "camera_code": primary_shot.camera_code if primary_shot else None,
                "lighting_code": primary_shot.light_code if primary_shot else None,
                "transition_type": primary_shot.transition_type if primary_shot else None,
                "audio_lead_seconds": audio_lead_seconds,
                "preview_url": preview_url,
                "preview_provider": preview_provider,
                "created_at": s.created_at.isoformat(),
            }
        )

    return {"data": data, "total_scenes": len(data)}


def _calculate_act_and_beat(scene_num: int, total_scenes: int, structure_type: str = "4_act") -> tuple[int, str]:
    """Calculate Act number and dramatic beat dynamically based on structure."""
    bounds = get_act_bounds(total_scenes, structure_type=structure_type)
    for act_idx, (b_start, b_end) in enumerate(bounds):
        if b_start <= scene_num <= b_end:
            act = act_idx + 1
            act_len = max(1, b_end - b_start + 1)
            rel_pos = (scene_num - b_start) / act_len
            if rel_pos < 0.33:
                beat = f"Act {act} Setup & Initial Momentum"
            elif rel_pos < 0.67:
                beat = f"Act {act} Mid-Point Escalation"
            else:
                beat = f"Act {act} Climax Transition"
            return act, beat
    return len(bounds), "Final Catharsis & Resolution"


def _determine_scene_duration(act: int, duration_mode: str) -> float:
    """Determine duration based on pacing mode: dynamic Hollywood curve, flat_10s, flat_15s, flat_5s."""
    mode = (duration_mode or "dynamic").lower()
    if mode == "flat_10s":
        return 10.0
    elif mode == "flat_15s":
        return 15.0
    elif mode == "flat_5s":
        return 5.0
    elif mode == "dynamic":
        # Hollywood cinematic pacing curve across acts 1 to 5:
        # Odd acts (1, 3, 5): Exposition, character depth, and emotional descent -> 15.0s
        # Even acts (2, 4): Rising tension, trials, and climactic action -> 10.0s
        return 15.0 if act % 2 == 1 else 10.0
    return 10.0


@router.post("/projects/{project_id}/scenes", status_code=status.HTTP_201_CREATED)
async def create_or_blueprint_scenes(
    project_id: str,
    payload: SceneCreateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Create a single scene. Legacy instant blueprint is deprecated in favor of Polya AI Screenwriter."""
    project = await _resolve_project(project_id, session)
    now = datetime.now(timezone.utc)

    if payload.generate_blueprint:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Legacy instant structural blueprint is deprecated. "
                "Please use the Polya AI Screenplay Writer pipeline via /blueprint/treatment "
                "and /blueprint/generate-act to generate calibrated scenes without mock fallbacks."
            ),
        )

    scene = SceneModel(
        id=uuid.uuid4(),
        project_id=project.id,
        act_number=payload.act_number,
        scene_number=payload.scene_number,
        slugline=payload.slugline,
        narrative_goal=payload.narrative_goal,
        duration_target=payload.duration_target,
        status=payload.status,
        created_at=now,
    )
    session.add(scene)
    await session.commit()
    await session.refresh(scene)

    return {
        "data": {
            "id": str(scene.id),
            "project_id": str(scene.project_id),
            "act_number": scene.act_number,
            "scene_number": scene.scene_number,
            "slugline": scene.slugline,
            "narrative_goal": scene.narrative_goal,
            "duration_target": scene.duration_target,
            "status": scene.status,
            "created_at": scene.created_at.isoformat(),
        }
    }


@router.post("/projects/{project_id}/blueprint/recommend-structure", status_code=status.HTTP_200_OK)
async def recommend_narrative_structure(
    project_id: str,
    payload: StructureRecommendationRequest | None = None,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Polya AI Strategic Advisory: Analyze project narrative and recommend optimal dramatic structure."""
    project = await _resolve_project(project_id, session)
    total_scenes = payload.total_scenes if payload else 100

    bible_stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == project.id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    bible = (await session.execute(bible_stmt)).scalar_one_or_none()

    try:
        project_ctx = extract_project_narrative_context(project, bible=bible)
    except Exception:
        project_ctx = None

    writer = PolyaScreenwriterEngine()
    advisory = await writer.analyze_narrative_structure_hybrid(
        project_context=project_ctx,
        title=project.title,
        total_scenes=total_scenes,
    )
    return {"data": advisory}


async def _load_cast_with_states(
    project_id: uuid.UUID,
    session: AsyncSession,
) -> tuple[list[dict[str, Any]], list[CharacterModel], dict[uuid.UUID, list[CharacterStateModel]]]:
    """Fetch project characters alongside their #State 01-#State 05 progression records."""
    char_stmt = select(CharacterModel).where(CharacterModel.project_id == project_id)
    characters_list = list((await session.execute(char_stmt)).scalars().all())
    char_ids = [c.id for c in characters_list]
    states_by_char: dict[uuid.UUID, list[CharacterStateModel]] = {}
    if char_ids:
        states_stmt = (
            select(CharacterStateModel)
            .where(CharacterStateModel.character_id.in_(char_ids))
            .order_by(CharacterStateModel.state_code.asc())
        )
        for st in (await session.execute(states_stmt)).scalars().all():
            states_by_char.setdefault(st.character_id, []).append(st)

    chars_data = [
        {
            "name": c.name,
            "role": c.role,
            "base_prompt": c.base_prompt,
            "narrative_summary": getattr(c, "narrative_summary", "") or "",
            "voice_dna_profile": getattr(c, "voice_dna_profile", "") or "",
            "states": [
                {
                    "state_code": s.state_code,
                    "state_label": s.state_label or "",
                    "wardrobe": s.wardrobe,
                    "injuries_and_wear": s.injuries_and_wear,
                    "expression_anchor": s.expression_anchor,
                }
                for s in states_by_char.get(c.id, [])
            ],
        }
        for c in characters_list
    ]
    return chars_data, characters_list, states_by_char


def _resolve_cold_open_config(
    project_settings: dict[str, Any] | None,
    structure_type: str,
    enable_cold_open: bool | None,
) -> dict[str, Any] | None:
    """Resolve explicit or default 30s Cold Open configuration cleanly."""
    settings_dict = project_settings if isinstance(project_settings, dict) else {}
    treatment_co = (settings_dict.get("treatment") or {}).get("cold_open_30s")
    preset_co = settings_dict.get("preset_data", {}).get("storyboard_defaults", {}).get("cold_open_30s")
    base_cfg = dict(treatment_co or preset_co or {})

    if enable_cold_open is True:
        base_cfg["enabled"] = True
        return base_cfg
    if enable_cold_open is False:
        base_cfg["enabled"] = False
        return base_cfg
    if base_cfg:
        return base_cfg
    if structure_type == "youtube_viral":
        return {"enabled": True}
    return None


def _build_cold_open_shot_cue(
    scene_num: int,
    shot_idx: int,
    primary_dialogue: str,
    narrative_goal: str,
    slugline: str,
    style_family: str,
) -> tuple[str, str]:
    """Build style-appropriate atmospheric/dramatic cues for 30s Cold Open shots (zero slapstick clichés)."""
    parsed = parse_structured_slugline(slugline)
    loc_cue = (parsed["location"] or "SCENE").lower()
    time_cue = (parsed["time_of_day"] or "ambient").lower()
    beat_snippet = " ".join((narrative_goal or "").split()[:12]).rstrip(".,;:")

    if shot_idx == 0 and primary_dialogue:
        cue = primary_dialogue if "[SFX:" in primary_dialogue else f"[SFX: {style_family} cold-open impulse ({loc_cue}) — {primary_dialogue}]"
        return cue, "NONE"

    if scene_num == 3 and shot_idx > 0:
        if style_family == "anime_2d":
            cue = f"[SFX: Resonant harmonic linger in {loc_cue} cutting sharply to Act I ({beat_snippet})]"
        elif style_family == "stop_motion":
            cue = f"[SFX: Tactile miniature room tone hold bridging into Scene 04 ({beat_snippet})]"
        elif style_family == "stylized_3d":
            cue = f"[SFX: Kinetic prop transient and rhythmic swell bridging into Scene 04 ({beat_snippet})]"
        else:
            cue = f"[SFX: Acoustic decay in {loc_cue} ({time_cue}) carrying directly into Act I]"
        return cue, "L_CUT"

    if style_family == "anime_2d":
        cue = f"[SFX: Atmospheric 'ma' tension in {loc_cue} ({time_cue}) — {beat_snippet or 'sharp focal beat'}]"
    elif style_family == "stop_motion":
        cue = f"[SFX: Tactile prop foley and measured breath in {loc_cue} — {beat_snippet or 'precise visual beat'}]"
    elif style_family == "stylized_3d":
        cue = f"[SFX: Dynamic motion transient in {loc_cue} ({time_cue}) — {beat_snippet or 'kinetic beat'}]"
    else:
        cue = f"[SFX: Grounded {time_cue} room tone in {loc_cue} — {beat_snippet or 'high-stakes visual beat'}]"

    return cue, ("NONE" if shot_idx == 0 else "J_CUT")


@router.post("/projects/{project_id}/blueprint/treatment", status_code=status.HTTP_200_OK)
async def generate_blueprint_treatment(
    project_id: str,
    payload: BlueprintTreatmentRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Phase A: Generate Master Story Treatment and Beat Sheet strictly via Polya AI Screenwriter."""
    project = await _resolve_project(project_id, session)

    if payload.clear_existing:
        await session.execute(delete(SceneModel).where(SceneModel.project_id == project.id))
        await session.commit()

    chars_data, characters_list, states_by_char = await _load_cast_with_states(project.id, session)
    for char_obj in characters_list:
        setattr(char_obj, "_prefetched_states", states_by_char.get(char_obj.id, []))

    bible_stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == project.id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    bible = (await session.execute(bible_stmt)).scalar_one_or_none()

    try:
        project_ctx = extract_project_narrative_context(project, bible=bible, characters=chars_data)
    except Exception:
        project_ctx = None

    cold_open_cfg = _resolve_cold_open_config(project.settings, payload.structure_type, payload.enable_cold_open)

    if isinstance(payload.selected_treatment, dict) and payload.selected_treatment.get("acts"):
        treatment = dict(payload.selected_treatment)
        if cold_open_cfg is not None and (payload.enable_cold_open is not None or "cold_open_30s" not in treatment):
            treatment["cold_open_30s"] = cold_open_cfg
        treatment["used_fallback"] = False
    else:
        writer = PolyaScreenwriterEngine()
        try:
            treatment = await writer.generate_master_treatment(
                project_context=project_ctx,
                title=project.title,
                total_scenes=payload.total_scenes,
                premise=payload.premise,
                characters=chars_data,
                cold_open_30s=cold_open_cfg,
                structure_type=payload.structure_type,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Polya AI Screenplay Treatment generation failed: {exc}",
            )

    if not isinstance(project.settings, dict):
        project.settings = {}
    project.settings["treatment"] = treatment
    project.settings["treatment"]["duration_mode"] = payload.duration_mode
    project.settings["treatment"]["total_scenes"] = payload.total_scenes
    project.settings["treatment"]["structure_type"] = payload.structure_type
    if cold_open_cfg is not None:
        project.settings["treatment"]["cold_open_30s"] = cold_open_cfg
    if "act_summaries" not in project.settings["treatment"]:
        project.settings["treatment"]["act_summaries"] = {}
    flag_modified(project, "settings")
    await session.commit()

    return {"data": treatment}


@router.post("/projects/{project_id}/blueprint/treatment-variants", status_code=status.HTTP_200_OK)
async def generate_blueprint_treatment_variants(
    project_id: str,
    payload: BlueprintTreatmentRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Phase A Multi-Option Engine: Generate 3 contrasting Master Treatment pitches in Strict LLM Mode."""
    project = await _resolve_project(project_id, session)
    chars_data, _, _ = await _load_cast_with_states(project.id, session)

    bible_stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == project.id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    bible = (await session.execute(bible_stmt)).scalar_one_or_none()
    try:
        project_ctx = extract_project_narrative_context(project, bible=bible, characters=chars_data)
    except Exception:
        project_ctx = None

    cold_open_cfg = _resolve_cold_open_config(project.settings, payload.structure_type, payload.enable_cold_open)
    writer = PolyaScreenwriterEngine()
    try:
        variants = await writer.generate_treatment_variants(
            project_context=project_ctx,
            title=project.title,
            total_scenes=payload.total_scenes,
            premise=payload.premise,
            characters=chars_data,
            cold_open_30s=cold_open_cfg,
            structure_type=payload.structure_type,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Polya AI Treatment Variants generation failed: {exc}",
        )

    return {"data": {"variants": variants, "structure_type": payload.structure_type, "total_scenes": payload.total_scenes}}


@router.post("/projects/{project_id}/blueprint/generate-act", status_code=status.HTTP_200_OK)
async def generate_blueprint_act(
    project_id: str,
    payload: BlueprintActGenerateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Phase B: Generate scenes and auto-split shots for a single Act strictly via Polya AI Screenwriter."""
    project = await _resolve_project(project_id, session)
    now = datetime.now(timezone.utc)

    chars_data, _, _ = await _load_cast_with_states(project.id, session)

    bible_stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == project.id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    bible = (await session.execute(bible_stmt)).scalar_one_or_none()

    try:
        project_ctx = extract_project_narrative_context(project, bible=bible, characters=chars_data)
    except Exception:
        project_ctx = None

    treatment = (project.settings or {}).get("treatment")
    structure_type = payload.structure_type or (treatment or {}).get("structure_type", "4_act")
    cold_open_cfg = _resolve_cold_open_config(project.settings, structure_type, payload.enable_cold_open)
    cold_open_active = bool(
        payload.act_number == 1 and cold_open_cfg and cold_open_cfg.get("enabled")
    )
    active_style_code = (
        getattr(project_ctx, "master_style_code", None)
        or (bible.style_parameters.get("master_style_code") if bible and bible.style_parameters else None)
        or project.target_style_code
        or "#Style 01"
    )
    active_style_family = get_style_family(active_style_code)

    writer = PolyaScreenwriterEngine()
    if not treatment:
        try:
            treatment = await writer.generate_master_treatment(
                project_context=project_ctx,
                title=project.title,
                total_scenes=payload.total_scenes,
                characters=chars_data,
                cold_open_30s=cold_open_cfg,
                structure_type=structure_type,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Polya AI Screenplay Treatment generation failed: {exc}",
            )
        if not isinstance(project.settings, dict):
            project.settings = {}
        project.settings["treatment"] = treatment
        project.settings["treatment"]["act_summaries"] = {}
        project.settings["treatment"]["structure_type"] = structure_type
        flag_modified(project, "settings")
        await session.commit()
    elif cold_open_cfg and "cold_open_30s" not in treatment:
        treatment["cold_open_30s"] = cold_open_cfg
        project.settings["treatment"]["cold_open_30s"] = cold_open_cfg
        flag_modified(project, "settings")
        await session.commit()

    act_summaries_raw = (project.settings.get("treatment", {})).get("act_summaries", {})
    prev_summaries = {int(k): v for k, v in act_summaries_raw.items() if k.isdigit()}

    try:
        act_result = await writer.generate_act_scenes(
            act_number=payload.act_number,
            total_scenes=payload.total_scenes,
            treatment=treatment,
            project_context=project_ctx,
            previous_act_summaries=prev_summaries,
            characters=chars_data,
            duration_mode=payload.duration_mode,
            cold_open_30s=cold_open_cfg,
            structure_type=structure_type,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Polya AI Act {payload.act_number} generation failed: {exc}",
        )

    scenes_data = act_result["scenes"]
    act_summary = act_result["act_summary"]

    # Clear existing scenes for this specific act in this project
    await session.execute(
        delete(SceneModel).where(
            SceneModel.project_id == project.id,
            SceneModel.act_number == payload.act_number,
        )
    )

    created_scenes: list[SceneModel] = []
    created_shots: list[ShotModel] = []

    for sc_info in scenes_data:
        s_num = sc_info["scene_number"]
        if cold_open_active and s_num in (1, 2, 3):
            duration_target = 10.0
        else:
            duration_target = _determine_scene_duration(payload.act_number, payload.duration_mode)
        scene_id = uuid.uuid4()
        pad = 3 if payload.total_scenes >= 100 else 2
        scene_status = "FALLBACK" if sc_info.get("is_fallback") else "PLANNED"

        slugline = sc_info.get("slugline") or f"SCENE {str(s_num).zfill(pad)} - INT. LOCATION - NIGHT"
        narrative_goal = sc_info.get("narrative_goal") or f"Act {payload.act_number} dramatic progression."

        if cold_open_active:
            co_struct = (cold_open_cfg or {}).get("structure") or {}
            s2_title = str((co_struct.get("scene_02") or {}).get("title") or "Escalating Kinetic Obstacle").strip()
            if s_num == 1:
                if "COLD OPEN" not in slugline:
                    slugline = f"{slugline} (COLD OPEN 0-10S)"
                if "In-Media-Res Shock Hook" not in narrative_goal:
                    narrative_goal = f"In-Media-Res Shock Hook + Hero Prop Reveal: {narrative_goal}"
            elif s_num == 2:
                if "COLD OPEN" not in slugline:
                    slugline = f"{slugline} (COLD OPEN 10-20S)"
                if s2_title.lower() not in narrative_goal.lower():
                    narrative_goal = f"{s2_title} + Main Threat/Rival: {narrative_goal}"
            elif s_num == 3:
                if "COLD OPEN" not in slugline:
                    slugline = f"{slugline} (COLD OPEN 20-30S)"
                if "Peak Climax Preview" not in narrative_goal:
                    narrative_goal = f"Peak Climax Preview + Time-Cut Transition to Scene 04: {narrative_goal}"
            elif s_num == 4:
                if "ORDINARY WORLD BEGINS" not in slugline:
                    slugline = f"{slugline} (ACT I: ORDINARY WORLD BEGINS)"
                if "Ordinary World" not in narrative_goal:
                    narrative_goal = f"Linear Narrative Setup (Act I: Ordinary World): {narrative_goal}"

        scene = SceneModel(
            id=scene_id,
            project_id=project.id,
            act_number=payload.act_number,
            scene_number=s_num,
            slugline=slugline,
            narrative_goal=narrative_goal,
            duration_target=duration_target,
            status=scene_status,
            created_at=now,
        )
        created_scenes.append(scene)

        if payload.auto_split_shots:
            if duration_target <= 5.0:
                needed_shots = 1
            elif duration_target <= 10.0:
                needed_shots = 2
            else:
                needed_shots = 3

            shot_duration = 5.0
            primary_dialogue = sc_info.get("dialogue", "")

            for i in range(needed_shots):
                if cold_open_active and s_num in (1, 2, 3):
                    if s_num == 1:
                        c_code = "#Cam 19" if i == 0 else "#Cam 23"
                        l_code = "#Lens 04" if i == 0 else "#Lens 02"
                        cp_code = "#Comp 03" if i == 0 else "#Comp 01"
                        sp_code = "#Speed 04"
                    elif s_num == 2:
                        c_code = "#Cam 25" if i == 0 else "#Cam 06"
                        l_code = "#Lens 02" if i == 0 else "#Lens 04"
                        cp_code = "#Comp 01" if i == 0 else "#Comp 02"
                        sp_code = "#Speed 04"
                    else:  # s_num == 3
                        c_code = "#Cam 19" if i == 0 else "#Cam 25"
                        l_code = "#Lens 04" if i == 0 else "#Lens 03"
                        cp_code = "#Comp 03"
                        sp_code = "#Speed 04" if i == 0 else "#Speed 03"

                    dlg, trans = _build_cold_open_shot_cue(
                        scene_num=s_num,
                        shot_idx=i,
                        primary_dialogue=primary_dialogue,
                        narrative_goal=narrative_goal,
                        slugline=slugline,
                        style_family=active_style_family,
                    )
                    new_shot = ShotModel(
                        id=uuid.uuid4(),
                        scene_id=scene_id,
                        shot_number=i + 1,
                        duration_seconds=shot_duration,
                        camera_code=c_code,
                        lens_code=l_code,
                        comp_code=cp_code,
                        light_code="#Light 02",
                        act_code="#Act 01",
                        speed_code=sp_code,
                        dialogue=dlg,
                        transition_type=trans,
                        status="PLANNED",
                        created_at=now,
                    )
                else:
                    template = SHOT_CAMERA_TEMPLATES[min(i, len(SHOT_CAMERA_TEMPLATES) - 1)]
                    family_optics = _STYLE_FAMILY_OPTICS_DEFAULTS.get(
                        active_style_family, _STYLE_FAMILY_OPTICS_DEFAULTS["photorealistic"]
                    )
                    dlg = primary_dialogue if i == 0 else None
                    transition = "J_CUT" if i == 0 and dlg else "NONE"

                    new_shot = ShotModel(
                        id=uuid.uuid4(),
                        scene_id=scene_id,
                        shot_number=i + 1,
                        duration_seconds=shot_duration,
                        camera_code=template["camera_code"],
                        lens_code=template["lens_code"],
                        comp_code=template["comp_code"],
                        light_code=family_optics["light_code"],
                        act_code=family_optics["act_code"],
                        speed_code=family_optics["speed_code"],
                        dialogue=dlg,
                        transition_type=transition,
                        status="PLANNED",
                        created_at=now,
                    )
                created_shots.append(new_shot)

    # Bulk insert
    session.add_all(created_scenes)
    if created_shots:
        session.add_all(created_shots)

    # Update persistent context in project settings
    if "treatment" not in project.settings:
        project.settings["treatment"] = treatment
    if "act_summaries" not in project.settings["treatment"]:
        project.settings["treatment"]["act_summaries"] = {}
    if "act_fallbacks" not in project.settings["treatment"]:
        project.settings["treatment"]["act_fallbacks"] = {}
    project.settings["treatment"]["act_summaries"][str(payload.act_number)] = act_summary
    project.settings["treatment"]["act_fallbacks"][str(payload.act_number)] = act_result["used_fallback"]
    flag_modified(project, "settings")
    await session.commit()

    count_stmt = select(func.count(SceneModel.id)).where(SceneModel.project_id == project.id)
    total_saved = (await session.execute(count_stmt)).scalar() or 0

    return {
        "data": {
            "act_number": payload.act_number,
            "scenes_generated": len(created_scenes),
            "shots_generated": len(created_shots),
            "start_scene": act_result["start_scene"],
            "end_scene": act_result["end_scene"],
            "act_summary": act_summary,
            "total_saved_for_project": total_saved,
            "used_fallback": False,
            "generator_type": "polya_llm_screenwriter",
        }
    }


@router.get("/projects/{project_id}/blueprint/status", status_code=status.HTTP_200_OK)
async def get_blueprint_status(
    project_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve treatment, generated acts, and progress counts."""
    project = await _resolve_project(project_id, session)

    treatment = (project.settings or {}).get("treatment")
    act_summaries = (treatment or {}).get("act_summaries", {})
    act_fallbacks = (treatment or {}).get("act_fallbacks", {})
    structure_type = (treatment or {}).get("structure_type", "4_act")
    total_scenes_val = (treatment or {}).get("total_scenes", 100)
    bounds = get_act_bounds(total_scenes_val, structure_type=structure_type)
    num_acts = len(bounds)

    act_counts: dict[int, int] = {}
    for act in range(1, num_acts + 1):
        st = select(func.count(SceneModel.id)).where(
            SceneModel.project_id == project.id,
            SceneModel.act_number == act,
        )
        act_counts[act] = (await session.execute(st)).scalar() or 0

    total_scenes_stmt = select(func.count(SceneModel.id)).where(SceneModel.project_id == project.id)
    total_scenes = (await session.execute(total_scenes_stmt)).scalar() or 0

    total_shots_stmt = select(func.count(ShotModel.id)).join(
        SceneModel, ShotModel.scene_id == SceneModel.id
    ).where(SceneModel.project_id == project.id)
    total_shots = (await session.execute(total_shots_stmt)).scalar() or 0

    return {
        "data": {
            "project_id": str(project.id),
            "has_treatment": treatment is not None,
            "treatment": treatment,
            "total_scenes": total_scenes,
            "total_shots": total_shots,
            "act_counts": act_counts,
            "act_summaries": act_summaries,
            "act_fallbacks": act_fallbacks,
            "completed_acts": [act for act, cnt in act_counts.items() if cnt > 0],
        }
    }


@router.post("/projects/{project_id}/blueprint/batch-write", status_code=status.HTTP_200_OK)
async def batch_write_blueprint(
    project_id: str,
    payload: BlueprintBatchWriteRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Full end-to-end staged generation: Phase A treatment followed by sequential Phase B Acts."""
    structure_type = payload.structure_type or "4_act"
    bounds = get_act_bounds(payload.total_scenes, structure_type=structure_type)
    num_acts = len(bounds)

    treatment_req = BlueprintTreatmentRequest(
        total_scenes=payload.total_scenes,
        duration_mode=payload.duration_mode,
        premise=payload.premise,
        clear_existing=payload.clear_existing,
        structure_type=structure_type,
        enable_cold_open=payload.enable_cold_open,
    )
    treatment_resp = await generate_blueprint_treatment(project_id, treatment_req, current_user, session)
    treatment_data = treatment_resp["data"]

    results = []
    for act in range(1, num_acts + 1):
        act_req = BlueprintActGenerateRequest(
            act_number=act,
            total_scenes=payload.total_scenes,
            duration_mode=payload.duration_mode,
            auto_split_shots=payload.auto_split_shots,
            structure_type=structure_type,
            enable_cold_open=payload.enable_cold_open,
        )
        act_resp = await generate_blueprint_act(project_id, act_req, current_user, session)
        results.append(act_resp["data"])

    project = await _resolve_project(project_id, session)
    total_scenes_cnt = (
        await session.execute(select(func.count(SceneModel.id)).where(SceneModel.project_id == project.id))
    ).scalar() or 0
    total_shots_cnt = (
        await session.execute(
            select(func.count(ShotModel.id)).join(SceneModel, ShotModel.scene_id == SceneModel.id).where(
                SceneModel.project_id == project.id
            )
        )
    ).scalar() or 0

    return {
        "data": {
            "message": f"Successfully completed {num_acts}-Act staged generation for {total_scenes_cnt} scenes.",
            "total_scenes": total_scenes_cnt,
            "total_shots": total_shots_cnt,
            "treatment": treatment_data,
            "acts": results,
        }
    }


@router.get("/scenes/{scene_id}", status_code=status.HTTP_200_OK)
async def get_scene(
    scene_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve details for a single scene."""
    s_uuid = uuid.UUID(scene_id)
    stmt = select(SceneModel).where(SceneModel.id == s_uuid)
    scene = (await session.execute(stmt)).scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    # Fetch preview_url and preview_provider from shots if generated
    shot_stmt = select(ShotModel).where(ShotModel.scene_id == s_uuid).order_by(ShotModel.shot_number.asc())
    shots = (await session.execute(shot_stmt)).scalars().all()
    preview_url = None
    preview_provider = None
    audio_lead_seconds = None
    primary = shots[0] if shots else None
    if primary and isinstance(primary.fg_bg_layers, dict):
        preview_url = primary.fg_bg_layers.get("preview_url")
        preview_provider = primary.fg_bg_layers.get("preview_provider")
        audio_lead_seconds = primary.fg_bg_layers.get("audio_lead_seconds")

    return {
        "data": {
            "id": str(scene.id),
            "project_id": str(scene.project_id),
            "act_number": scene.act_number,
            "scene_number": scene.scene_number,
            "slugline": scene.slugline,
            "narrative_goal": scene.narrative_goal,
            "duration_target": scene.duration_target,
            "status": scene.status,
            "dialogue": _extract_scene_dialogue(list(shots)),
            "camera_code": primary.camera_code if primary else None,
            "lighting_code": primary.light_code if primary else None,
            "transition_type": primary.transition_type if primary else None,
            "audio_lead_seconds": audio_lead_seconds,
            "preview_url": preview_url,
            "preview_provider": preview_provider,
            "created_at": scene.created_at.isoformat(),
        }
    }


@router.post("/scenes/{scene_id}/attach-preview", status_code=status.HTTP_200_OK)
async def attach_scene_preview(
    scene_id: str,
    payload: SceneAttachPreviewRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Attach generated preview image to shot #1 of the scene via non-destructive JSON merge."""
    try:
        s_uuid = uuid.UUID(scene_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid scene UUID")

    scene_stmt = select(SceneModel).where(SceneModel.id == s_uuid)
    scene = (await session.execute(scene_stmt)).scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene not found")

    shot_stmt = select(ShotModel).where(ShotModel.scene_id == s_uuid).order_by(ShotModel.shot_number.asc())
    shots = (await session.execute(shot_stmt)).scalars().all()
    primary_shot = shots[0] if shots else None

    now_iso = datetime.now(timezone.utc).isoformat()

    if primary_shot:
        current_layers = dict(primary_shot.fg_bg_layers or {}) if isinstance(primary_shot.fg_bg_layers, dict) else {}
        # Non-destructive JSON merge: retain old keys, only add/update preview_url, preview_provider, job_id, updated_at
        current_layers["preview_url"] = payload.preview_url
        current_layers["preview_provider"] = payload.preview_provider
        if payload.job_id:
            current_layers["job_id"] = payload.job_id
        current_layers["updated_at"] = now_iso
        primary_shot.fg_bg_layers = current_layers
        flag_modified(primary_shot, "fg_bg_layers")
    else:
        current_layers = {
            "preview_url": payload.preview_url,
            "preview_provider": payload.preview_provider,
            "job_id": payload.job_id,
            "updated_at": now_iso,
        }
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
            fg_bg_layers=current_layers,
            status="PLANNED",
            created_at=datetime.now(timezone.utc),
        )
        session.add(primary_shot)

    await session.commit()
    await session.refresh(primary_shot)

    return {
        "status": "success",
        "scene_id": str(scene.id),
        "shot_id": str(primary_shot.id),
        "preview_url": payload.preview_url,
        "preview_provider": payload.preview_provider,
        "fg_bg_layers": primary_shot.fg_bg_layers,
    }


@router.put("/scenes/{scene_id}", status_code=status.HTTP_200_OK)
async def update_scene(
    scene_id: str,
    payload: SceneUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Update scene metadata and narrative goal."""
    s_uuid = uuid.UUID(scene_id)
    stmt = select(SceneModel).where(SceneModel.id == s_uuid)
    scene = (await session.execute(stmt)).scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    if payload.slugline is not None:
        scene.slugline = payload.slugline
    if payload.narrative_goal is not None:
        scene.narrative_goal = payload.narrative_goal
    if payload.duration_target is not None:
        scene.duration_target = payload.duration_target
    if payload.status is not None:
        scene.status = payload.status

    shot_stmt = select(ShotModel).where(ShotModel.scene_id == s_uuid).order_by(ShotModel.shot_number.asc())
    existing_shots = list((await session.execute(shot_stmt)).scalars().all())
    has_shot_updates = any(
        val is not None
        for val in (
            payload.dialogue,
            payload.camera_code,
            payload.lighting_code,
            payload.transition_type,
            payload.audio_lead_seconds,
        )
    )
    if has_shot_updates:
        if existing_shots:
            prim = existing_shots[0]
            if payload.dialogue is not None:
                prim.dialogue = payload.dialogue
            if payload.camera_code is not None:
                prim.camera_code = payload.camera_code
            if payload.lighting_code is not None:
                prim.light_code = payload.lighting_code
            if payload.transition_type is not None:
                prim.transition_type = payload.transition_type
            if payload.audio_lead_seconds is not None:
                layers = dict(prim.fg_bg_layers or {})
                layers["audio_lead_seconds"] = float(payload.audio_lead_seconds)
                prim.fg_bg_layers = layers
                flag_modified(prim, "fg_bg_layers")
        else:
            tmpl = SHOT_CAMERA_TEMPLATES[0]
            proj_row = (
                await session.execute(select(ProjectModel).where(ProjectModel.id == scene.project_id))
            ).scalar_one_or_none()
            bible_row = (
                await session.execute(
                    select(MasterProductionBibleModel)
                    .where(MasterProductionBibleModel.project_id == scene.project_id)
                    .order_by(MasterProductionBibleModel.version.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            bible_styles = bible_row.style_parameters if (bible_row and isinstance(bible_row.style_parameters, dict)) else {}
            eff_style = (
                bible_styles.get("master_style_code")
                or (proj_row.target_style_code if proj_row else None)
                or "#Style 01"
            )
            eff_family = get_style_family(eff_style)
            family_optics = _STYLE_FAMILY_OPTICS_DEFAULTS.get(
                eff_family, _STYLE_FAMILY_OPTICS_DEFAULTS["photorealistic"]
            )
            layers: dict[str, Any] = {}
            if payload.audio_lead_seconds is not None:
                layers["audio_lead_seconds"] = float(payload.audio_lead_seconds)
            dlg_val = payload.dialogue or ""
            session.add(
                ShotModel(
                    id=uuid.uuid4(),
                    scene_id=scene.id,
                    shot_number=1,
                    duration_seconds=min(5.0, scene.duration_target or 5.0),
                    camera_code=payload.camera_code or tmpl["camera_code"],
                    lens_code=tmpl["lens_code"],
                    comp_code=tmpl["comp_code"],
                    light_code=payload.lighting_code or family_optics["light_code"],
                    act_code=family_optics["act_code"],
                    speed_code=family_optics["speed_code"],
                    fg_bg_layers=layers,
                    dialogue=payload.dialogue,
                    transition_type=payload.transition_type or ("J_CUT" if dlg_val.strip() else "NONE"),
                    status="PLANNED",
                    created_at=datetime.now(timezone.utc),
                )
            )

    if payload.auto_split_shots and payload.duration_target is not None:
        await _perform_auto_split(scene, payload.duration_target, session)

    await session.commit()
    await session.refresh(scene)

    shot_stmt_out = select(ShotModel).where(ShotModel.scene_id == s_uuid).order_by(ShotModel.shot_number.asc())
    shots_out = list((await session.execute(shot_stmt_out)).scalars().all())
    prim_out = shots_out[0] if shots_out else None

    return {
        "data": {
            "id": str(scene.id),
            "act_number": scene.act_number,
            "scene_number": scene.scene_number,
            "slugline": scene.slugline,
            "narrative_goal": scene.narrative_goal,
            "duration_target": scene.duration_target,
            "status": scene.status,
            "dialogue": _extract_scene_dialogue(shots_out),
            "camera_code": prim_out.camera_code if prim_out else None,
            "lighting_code": prim_out.light_code if prim_out else None,
            "transition_type": prim_out.transition_type if prim_out else None,
        }
    }


@router.post("/scenes/{scene_id}/auto-split", status_code=status.HTTP_200_OK)
async def auto_split_scene(
    scene_id: str,
    payload: SceneAutoSplitRequest | None = None,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Dual-brain auto-split/configure shots with selectable coverage_style."""
    s_uuid = uuid.UUID(scene_id)
    stmt = select(SceneModel).where(SceneModel.id == s_uuid)
    scene = (await session.execute(stmt)).scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    target_duration = (
        payload.target_duration
        if (payload and payload.target_duration is not None)
        else scene.duration_target
    )
    coverage_style = payload.coverage_style if payload and payload.coverage_style else "classic_coverage"
    scene.duration_target = target_duration

    shots = await _perform_auto_split(scene, target_duration, session, coverage_style=coverage_style)
    return {
        "data": {
            "scene_id": str(scene.id),
            "target_duration": target_duration,
            "coverage_style": coverage_style,
            "shots_count": len(shots),
            "message": f"Configured {len(shots)} shots ({coverage_style}) for {target_duration}s scene.",
            "shots": [
                {
                    "id": str(s.id),
                    "scene_id": str(s.scene_id),
                    "shot_number": s.shot_number,
                    "duration_seconds": s.duration_seconds,
                    "camera_code": s.camera_code,
                    "lens_code": s.lens_code,
                    "comp_code": s.comp_code,
                    "light_code": s.light_code,
                    "act_code": s.act_code,
                    "speed_code": s.speed_code,
                    "dialogue": s.dialogue,
                    "transition_type": s.transition_type,
                    "status": s.status,
                }
                for s in shots
            ],
        }
    }


@router.delete("/scenes/{scene_id}", status_code=status.HTTP_200_OK)
async def delete_scene(
    scene_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Delete a scene and associated shots."""
    s_uuid = uuid.UUID(scene_id)
    stmt = select(SceneModel).where(SceneModel.id == s_uuid)
    scene = (await session.execute(stmt)).scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    await session.delete(scene)
    await session.commit()
    return {"data": {"message": f"Scene {scene.scene_number} deleted successfully."}}


async def _resolve_scene_speaker_and_style(
    scene: SceneModel,
    session: AsyncSession,
    character_name: str | None = None,
    requested_style_code: str | None = None,
) -> dict[str, Any]:
    """Load project context, active #Style code, matching speaker Voice DNA, and Act-mapped #State."""
    project = (await session.execute(select(ProjectModel).where(ProjectModel.id == scene.project_id))).scalar_one_or_none()
    bible = None
    if project:
        bible = (
            await session.execute(
                select(MasterProductionBibleModel)
                .where(MasterProductionBibleModel.project_id == project.id)
                .order_by(MasterProductionBibleModel.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    proj_style = (
        (bible.style_parameters.get("master_style_code") if bible and isinstance(bible.style_parameters, dict) else None)
        or (project.target_style_code if project else None)
        or "#Style 01"
    )
    style_code = (
        requested_style_code
        if requested_style_code and (requested_style_code != "#Style 01" or proj_style == "#Style 01")
        else proj_style
    )

    chars_data, _, _ = await _load_cast_with_states(scene.project_id, session)
    total_acts = 4
    if project and isinstance(project.settings, dict):
        tr = project.settings.get("treatment") or {}
        if isinstance(tr.get("acts"), list) and tr["acts"]:
            total_acts = len(tr["acts"])
        elif tr.get("structure_type") == "3_act":
            total_acts = 3
        elif tr.get("structure_type") == "5_act":
            total_acts = 5

    project_ctx = None
    if project:
        try:
            project_ctx = extract_project_narrative_context(project, bible=bible, characters=chars_data)
        except Exception:
            project_ctx = {
                "title": project.title,
                "genre_tone": (project.settings or {}).get("genre") if isinstance(project.settings, dict) else "Cinematic Film",
                "synopsis": (project.settings or {}).get("synopsis") if isinstance(project.settings, dict) else "",
                "master_style_code": style_code,
                "cast_characters": chars_data,
            }

    target_speaker = (character_name or "").strip()
    speaker_entry = None
    if target_speaker:
        speaker_entry = next(
            (c for c in chars_data if c.get("name", "").strip().lower() == target_speaker.lower()),
            None,
        )
    if not speaker_entry and chars_data:
        goal_lower = (scene.narrative_goal or "").lower()
        speaker_entry = next(
            (c for c in chars_data if c.get("name", "").strip().lower() in goal_lower),
            chars_data[0],
        )
        if speaker_entry and not target_speaker:
            target_speaker = speaker_entry.get("name", "")

    voice_dna = speaker_entry.get("voice_dna_profile") if speaker_entry else None
    active_state = None
    if speaker_entry and speaker_entry.get("states"):
        target_state_num = PolyaScreenwriterEngine._resolve_act_to_state_number(scene.act_number, total_acts) or 1
        target_code = f"#State 0{target_state_num}"
        states = sorted(speaker_entry["states"], key=lambda s: str(s.get("state_code", "")))
        active_state = next((s for s in states if str(s.get("state_code", "")).upper() == target_code.upper()), None)
        if not active_state:
            active_state = states[min(len(states) - 1, max(0, target_state_num - 1))]

    return {
        "style_code": style_code,
        "project_ctx": project_ctx,
        "speaker_name": target_speaker or None,
        "voice_dna_profile": voice_dna,
        "active_state": active_state,
    }


@router.post("/scenes/{scene_id}/calibrate-dialogue", status_code=status.HTTP_200_OK)
async def calibrate_scene_dialogue(
    scene_id: str,
    payload: DialogueCalibrationRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Calibrate dialogue pacing with PolyaScreenwriterEngine, style/voice continuity, and DB caching."""
    s_uuid = uuid.UUID(scene_id)
    stmt = select(SceneModel).where(SceneModel.id == s_uuid)
    scene = (await session.execute(stmt)).scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    raw_text = payload.raw_text.strip()
    max_seconds = payload.max_seconds if payload.max_seconds > 0 else 5.0

    ctx_info = await _resolve_scene_speaker_and_style(
        scene=scene,
        session=session,
        character_name=payload.character_name,
    )
    resolved_style = ctx_info["style_code"]

    # Compute cache key incorporating style & speaker identity
    raw_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    cache_key = hashlib.sha256(
        f"{scene_id}:{raw_hash}:{max_seconds:.1f}:{resolved_style}:{(ctx_info['speaker_name'] or '').lower()}".encode("utf-8")
    ).hexdigest()

    # 1. Check DB cache
    cache_stmt = select(DialogueCalibrationCacheModel).where(
        DialogueCalibrationCacheModel.cache_key == cache_key
    )
    cached_entry = (await session.execute(cache_stmt)).scalar_one_or_none()
    if cached_entry:
        try:
            cached_data = json.loads(cached_entry.result_json)
            if isinstance(cached_data, dict) and cached_data.get("alternatives"):
                cached_data["source"] = "db_cache"
                return {"data": cached_data}
        except Exception:
            pass

    # 2. Analyze via PolyaScreenwriterEngine with style_code, Voice DNA & active State
    engine = PolyaScreenwriterEngine()
    calib_res = await engine.calibrate_dialogue_pacing(
        dialogue_text=raw_text,
        max_seconds=max_seconds,
        character_name=payload.character_name,
        context=scene.narrative_goal,
        style_code=resolved_style,
        voice_dna_profile=ctx_info["voice_dna_profile"],
        active_state=ctx_info["active_state"],
    )

    result_data = {
        "scene_id": str(scene.id),
        "character_name": payload.character_name,
        "raw_text": raw_text,
        "word_count": calib_res["word_count"],
        "syllable_count": calib_res["syllable_count"],
        "estimated_duration_seconds": calib_res["estimated_duration_seconds"],
        "passes_duration_limit": calib_res["passes_duration_limit"],
        "passes_5s_limit": calib_res["passes_5s_limit"],
        "max_allowed_words": calib_res["max_allowed_words"],
        "max_seconds": calib_res["max_seconds"],
        "transition_type": calib_res["transition_type"],
        "audio_lead_seconds": calib_res["audio_lead_seconds"],
        "analysis": calib_res["analysis"],
        "trimmed_suggestion": calib_res.get("trimmed_suggestion"),
        "alternatives": calib_res.get("alternatives", []),
        "source": calib_res.get("source", "llm"),
    }

    # 3. Cache result in DB
    try:
      new_cache = DialogueCalibrationCacheModel(
          cache_key=cache_key,
          scene_id=scene.id,
          raw_text_hash=raw_hash,
          max_seconds=max_seconds,
          result_json=json.dumps(result_data),
          created_at=datetime.now(timezone.utc),
      )
      session.add(new_cache)
      await session.commit()
    except Exception as e:
      await session.rollback()

    return {"data": result_data}


@router.post("/scenes/{scene_id}/director-polish", status_code=status.HTTP_200_OK)
@router.post("/projects/{project_id}/scenes/{scene_id}/director-polish", status_code=status.HTTP_200_OK)
async def polish_scene_director(
    scene_id: str,
    payload: DirectorPolishRequest = DirectorPolishRequest(),
    project_id: str | None = None,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Director Polish: Generates polished suggestions for slugline, narrative goal, dialogue, camera, and lighting without overwriting user manual input."""
    s_uuid = uuid.UUID(scene_id)
    scene = (await session.execute(select(SceneModel).where(SceneModel.id == s_uuid))).scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    # Fetch primary shot for existing optical/lighting baselines
    shot_stmt = select(ShotModel).where(ShotModel.scene_id == s_uuid).order_by(ShotModel.shot_number.asc())
    shots = (await session.execute(shot_stmt)).scalars().all()
    prim = shots[0] if shots else None

    current_slugline = payload.slugline or scene.slugline
    current_goal = payload.narrative_goal or scene.narrative_goal
    current_dialogue = payload.dialogue if payload.dialogue is not None else (prim.dialogue if prim else None)
    current_cam = payload.camera_code or (prim.camera_code if prim else "#Cam 01")
    current_light = payload.lighting_code or (prim.light_code if prim else "#Light 01")

    ctx_info = await _resolve_scene_speaker_and_style(
        scene=scene,
        session=session,
        requested_style_code=payload.style_code,
    )

    prev_scene = (
        await session.execute(
            select(SceneModel)
            .where(SceneModel.project_id == scene.project_id, SceneModel.scene_number < scene.scene_number)
            .order_by(SceneModel.scene_number.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    next_scene = (
        await session.execute(
            select(SceneModel)
            .where(SceneModel.project_id == scene.project_id, SceneModel.scene_number > scene.scene_number)
            .order_by(SceneModel.scene_number.asc())
            .limit(1)
        )
    ).scalar_one_or_none()

    adjacent_scenes: dict[str, Any] = {}
    if prev_scene:
        adjacent_scenes["prev"] = {
            "scene_number": prev_scene.scene_number,
            "slugline": prev_scene.slugline,
            "narrative_goal": prev_scene.narrative_goal,
        }
    if next_scene:
        adjacent_scenes["next"] = {
            "scene_number": next_scene.scene_number,
            "slugline": next_scene.slugline,
            "narrative_goal": next_scene.narrative_goal,
        }

    writer = PolyaScreenwriterEngine()
    polished = await writer.polish_scene_director_cut(
        scene_number=scene.scene_number,
        slugline=current_slugline,
        narrative_goal=current_goal,
        dialogue=current_dialogue,
        style_code=ctx_info["style_code"],
        camera_code=current_cam,
        lighting_code=current_light,
        project_context=ctx_info["project_ctx"],
        voice_dna_profile=ctx_info["voice_dna_profile"],
        active_state=ctx_info["active_state"],
        adjacent_scenes=adjacent_scenes or None,
        act_number=scene.act_number,
        speaking_character=ctx_info["speaker_name"],
    )

    # Non-destructive: DB is NOT updated; suggestions returned as preview for user Apply / Discard
    return {
        "status": "success",
        "data": {
            "scene_id": str(scene.id),
            "scene_number": scene.scene_number,
            "original": {
                "slugline": current_slugline,
                "narrative_goal": current_goal,
                "dialogue": current_dialogue,
                "camera_code": current_cam,
                "lighting_code": current_light,
            },
            "suggestions": {
                "slugline": polished["slugline"],
                "narrative_goal": polished["narrative_goal"],
                "dialogue": polished["dialogue"],
                "camera_code": polished["camera_code"],
                "lighting_code": polished["lighting_code"],
                "transition_type": polished.get("transition_type", "L_CUT"),
                "director_notes": polished["director_notes"],
            },
            "options": polished.get("options", []),
            "message": "Director polish takes ready. Select a take and click 'Apply Selected Take' to update your scene & primary shot.",
        },
    }
