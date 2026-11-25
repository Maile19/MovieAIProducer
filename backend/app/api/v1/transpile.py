from typing import Any
import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_session
from backend.app.domain.catalog import STYLE_CATALOG
from backend.app.domain.screenwriter import PolyaScreenwriterEngine
from backend.app.domain.transpiler import LivePromptTranspiler
from backend.app.infrastructure.database.models.character import CharacterModel, CharacterStateModel
from backend.app.infrastructure.database.models.project import MasterProductionBibleModel, ProjectModel
from backend.app.infrastructure.database.models.story import SceneModel, ShotModel

router = APIRouter(tags=["Prompt Transpiler"])


class TranspileRequest(BaseModel):
    provider_target: str = Field(
        default="veo",
        description="Target engine: google_flow, veo, kling, seedance, runway, sora, 9router, comfyui",
    )
    project_id: str | None = Field(default=None, description="Optional project UUID for DB DNA hydration")
    scene_id: str | None = Field(default=None, description="Optional scene UUID for DB DNA hydration")
    shot_id: str | None = Field(default=None, description="Optional shot UUID for DB optical/cut hydration")
    character_id: str | None = Field(default=None, description="Optional character UUID for DB Voice/Visual DNA hydration")
    state_number: int | None = Field(default=None, ge=1, le=5, description="Optional #State 01-05 override")
    style_code: str = Field(default="#Style 01", description="#Style 01 to #Style 18")
    camera_code: str = Field(default="#Cam 01", description="#Cam 01 to #Cam 34")
    lens_code: str = Field(default="#Lens 01", description="#Lens 01 to #Lens 06")
    comp_code: str = Field(default="#Comp 01", description="#Comp 01 to #Comp 08")
    light_code: str = Field(default="#Light 01", description="#Light 01 to #Light 14")
    act_code: str = Field(default="#Act 01", description="#Act 01 to #Act 24")
    speed_code: str = Field(default="#Speed 01", description="#Speed 01 to #Speed 05")
    character_dna: str = Field(default="", description="Character visual descriptors")
    character_name: str = Field(default="", description="Optional character name")
    state_code: str = Field(default="#State 01", description="#State 01 to #State 05")
    wardrobe: str = Field(default="", description="Wardrobe description")
    physical_damage: str = Field(default="", description="Injuries and wear")
    emotional_anchor: str = Field(default="", description="Expression / emotional anchor")
    aesthetic_directives: str = Field(default="", description="Style aesthetic directives")
    color_grade_emulation: str = Field(default="", description="Color grade emulation")
    env_dna: str = Field(default="", description="Environment architecture & atmosphere")
    action_description: str = Field(default="", description="Dynamic performance action")
    slugline: str = Field(default="", description="Optional scene slugline")
    narrative_goal: str = Field(default="", description="Optional scene narrative goal")
    fg_description: str = Field(default="", description="Foreground particulate or depth layer")
    bg_description: str = Field(default="", description="Background atmosphere or moving scenery")
    dialogue: str | None = Field(default=None, description="Spoken dialogue text")
    transition_type: str = Field(default="NONE", description="NONE, J_CUT, L_CUT, HARD_CUT")
    audio_lead_seconds: float | None = Field(default=None, description="Real J/L-Cut audio lead/trail seconds")
    aspect_ratio: str = Field(default="16:9", description="16:9, 9:16, or 2.39:1")
    preset_rules: dict[str, Any] | None = Field(default=None, description="Preset rules dictionary")
    is_non_verbal: bool = Field(default=False, description="Whether non-verbal mode is active")
    model: str | None = Field(default=None, description="Model identifier e.g. ag/gemini-3.8-flash for 9Router")
    genre: str | None = Field(default=None, description="Optional cinematic genre for Director RAG")


def _safe_uuid(raw: str | None) -> uuid.UUID | None:
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


@router.post("/transpile", status_code=status.HTTP_200_OK)
async def transpile_prompt(
    payload: TranspileRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Transpile Hollywood cinematographic matrices + real DB DNA + Dual RAG (8765 + 8766) into generative engine prompt."""
    fields_set = payload.model_fields_set

    shot_uuid = _safe_uuid(payload.shot_id)
    scene_uuid = _safe_uuid(payload.scene_id)
    project_uuid = _safe_uuid(payload.project_id)
    char_uuid = _safe_uuid(payload.character_id)

    shot = (await session.execute(select(ShotModel).where(ShotModel.id == shot_uuid))).scalar_one_or_none() if shot_uuid else None
    if shot and not scene_uuid:
        scene_uuid = shot.scene_id

    scene = (await session.execute(select(SceneModel).where(SceneModel.id == scene_uuid))).scalar_one_or_none() if scene_uuid else None
    if scene and not shot:
        shot = (
            await session.execute(
                select(ShotModel).where(ShotModel.scene_id == scene.id).order_by(ShotModel.shot_number.asc()).limit(1)
            )
        ).scalar_one_or_none()

    if scene and not project_uuid:
        project_uuid = scene.project_id

    project = (await session.execute(select(ProjectModel).where(ProjectModel.id == project_uuid))).scalar_one_or_none() if project_uuid else None
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

    # Resolve Character + act-mapped #State
    char_obj = (await session.execute(select(CharacterModel).where(CharacterModel.id == char_uuid))).scalar_one_or_none() if char_uuid else None
    if not char_obj and project:
        proj_chars = list(
            (
                await session.execute(
                    select(CharacterModel).where(CharacterModel.project_id == project.id).order_by(CharacterModel.created_at.asc())
                )
            ).scalars().all()
        )
        if proj_chars:
            if scene and scene.narrative_goal:
                goal_low = scene.narrative_goal.lower()
                char_obj = next((c for c in proj_chars if c.name and c.name.lower() in goal_low), proj_chars[0])
            else:
                char_obj = proj_chars[0]

    state_obj = None
    if char_obj:
        char_states = list(
            (
                await session.execute(
                    select(CharacterStateModel)
                    .where(CharacterStateModel.character_id == char_obj.id)
                    .order_by(CharacterStateModel.state_code.asc())
                )
            ).scalars().all()
        )
        if char_states:
            total_acts = 4
            if project and isinstance(project.settings, dict):
                tr = project.settings.get("treatment") or {}
                if isinstance(tr.get("acts"), list) and tr["acts"]:
                    total_acts = len(tr["acts"])
                elif tr.get("structure_type") == "3_act":
                    total_acts = 3
                elif tr.get("structure_type") == "5_act":
                    total_acts = 5
            target_st_num = payload.state_number or (
                PolyaScreenwriterEngine._resolve_act_to_state_number(scene.act_number, total_acts) if scene else 1
            ) or 1
            target_st_code = f"#State 0{target_st_num}"
            state_obj = next(
                (s for s in char_states if (s.state_code or "").upper() == target_st_code.upper()),
                char_states[min(len(char_states) - 1, max(0, target_st_num - 1))],
            )

    # Hydrate defaults from DB unless explicitly overridden in request
    bible_styles = bible.style_parameters if (bible and isinstance(bible.style_parameters, dict)) else {}
    bible_world = bible.world_rules if (bible and isinstance(bible.world_rules, dict)) else {}
    proj_settings = project.settings if (project and isinstance(project.settings, dict)) else {}

    style_code = (
        payload.style_code
        if "style_code" in fields_set
        else (bible_styles.get("master_style_code") or (project.target_style_code if project else None) or payload.style_code)
    )
    style_cat = next((s for s in STYLE_CATALOG if s.get("code") == style_code), None)
    aesthetic_directives = payload.aesthetic_directives or str(
        bible_styles.get("aesthetic_directives") or (style_cat.get("aesthetic_directives") if style_cat else "") or ""
    )
    color_grade_emulation = payload.color_grade_emulation or str(
        bible_styles.get("color_grade_emulation") or (style_cat.get("color_grade_emulation") if style_cat else "") or ""
    )

    camera_code = payload.camera_code if "camera_code" in fields_set else (shot.camera_code if shot else payload.camera_code)
    lens_code = payload.lens_code if "lens_code" in fields_set else (shot.lens_code if shot else payload.lens_code)
    comp_code = payload.comp_code if "comp_code" in fields_set else (shot.comp_code if shot else payload.comp_code)
    light_code = payload.light_code if "light_code" in fields_set else (shot.light_code if shot else payload.light_code)
    act_code = payload.act_code if "act_code" in fields_set else (shot.act_code if shot else payload.act_code)
    speed_code = payload.speed_code if "speed_code" in fields_set else (shot.speed_code if shot else payload.speed_code)

    shot_layers = shot.fg_bg_layers if (shot and isinstance(shot.fg_bg_layers, dict)) else {}
    dialogue = payload.dialogue if "dialogue" in fields_set else (shot.dialogue if shot else payload.dialogue)
    transition_type = (
        payload.transition_type
        if "transition_type" in fields_set
        else (shot.transition_type if shot else payload.transition_type)
    )
    audio_lead_seconds = (
        payload.audio_lead_seconds
        if payload.audio_lead_seconds is not None
        else shot_layers.get("audio_lead_seconds")
    )

    character_dna = payload.character_dna or (char_obj.base_prompt if char_obj else "")
    character_name = payload.character_name or (char_obj.name if char_obj else "")
    state_code = (
        payload.state_code
        if "state_code" in fields_set
        else (state_obj.state_code if state_obj else payload.state_code)
    )
    wardrobe = payload.wardrobe or (state_obj.wardrobe if state_obj else "")
    physical_damage = payload.physical_damage or (state_obj.injuries_and_wear if state_obj else "")
    emotional_anchor = payload.emotional_anchor or (state_obj.expression_anchor if state_obj else "")

    slugline = payload.slugline or (scene.slugline if scene else "")
    narrative_goal = payload.narrative_goal or (scene.narrative_goal if scene else "")
    action_description = payload.action_description or (
        str(shot_layers.get("prompt_override") or "").strip() or narrative_goal
    )
    env_dna = payload.env_dna or str(
        bible_world.get("setting") or bible_world.get("world_setting") or slugline or ""
    )
    genre = payload.genre or proj_settings.get("genre") or proj_settings.get("genre_tone")
    aspect_ratio = payload.aspect_ratio if "aspect_ratio" in fields_set else (project.aspect_ratio if project else payload.aspect_ratio)
    preset_rules = payload.preset_rules or proj_settings.get("preset_data", {}).get("transpiler_rules")
    if not preset_rules and bible_world.get("negative_prompts"):
        preset_rules = {"negative_prompts": bible_world.get("negative_prompts")}

    result = await LivePromptTranspiler.transpile_with_rag(
        provider_target=payload.provider_target,
        style_code=style_code,
        camera_code=camera_code,
        lens_code=lens_code,
        comp_code=comp_code,
        light_code=light_code,
        act_code=act_code,
        speed_code=speed_code,
        character_dna=character_dna,
        state_code=state_code,
        wardrobe=wardrobe,
        env_dna=env_dna,
        action_description=action_description,
        fg_description=payload.fg_description,
        bg_description=payload.bg_description,
        dialogue=dialogue,
        transition_type=transition_type,
        aspect_ratio=aspect_ratio,
        preset_rules=preset_rules,
        is_non_verbal=payload.is_non_verbal,
        model=payload.model,
        genre=genre,
        audio_lead_seconds=audio_lead_seconds,
        character_name=character_name,
        emotional_anchor=emotional_anchor,
        physical_damage=physical_damage,
        aesthetic_directives=aesthetic_directives,
        color_grade_emulation=color_grade_emulation,
        slugline=slugline,
        narrative_goal=narrative_goal,
        act_number=scene.act_number if scene else None,
    )
    return {"data": result}
