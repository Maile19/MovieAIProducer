from datetime import datetime, timezone
import math
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.app.api.deps import get_current_user, get_session
from backend.app.domain.story_writer import StagedStoryWriter, get_act_bounds
from backend.app.infrastructure.database.models.auth import UserModel
from backend.app.infrastructure.database.models.character import CharacterModel
from backend.app.infrastructure.database.models.project import ProjectModel
from backend.app.infrastructure.database.models.story import SceneModel, ShotModel

router = APIRouter(tags=["Scenes & Storyboard"])


class SceneCreateRequest(BaseModel):
    act_number: int = Field(default=1, ge=1, le=4, description="Act 1 to 4")
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
    auto_split_shots: bool = Field(default=False, description="If True, automatically generate or adjust shots to match target duration")


class SceneAutoSplitRequest(BaseModel):
    target_duration: float | None = Field(default=None, ge=1.0, le=60.0, description="Target duration in seconds (5.0, 10.0, 15.0)")


class BlueprintTreatmentRequest(BaseModel):
    total_scenes: int = Field(default=100, ge=1, le=500, description="Total scenes (50, 100, 200, 300, 400, 420)")
    duration_mode: str = Field(default="dynamic", description="dynamic | flat_10s | flat_15s | flat_5s")
    premise: str = Field(default="", description="Story premise / concept from director")
    clear_existing: bool = Field(default=False, description="Clear existing scenes if re-generating")


class BlueprintActGenerateRequest(BaseModel):
    act_number: int = Field(ge=1, le=4, description="Act to generate: 1 to 4")
    total_scenes: int = Field(default=100, ge=1, le=500, description="Total scenes planned")
    duration_mode: str = Field(default="dynamic", description="dynamic | flat_10s | flat_15s | flat_5s")
    auto_split_shots: bool = Field(default=True, description="Auto-split shots per scene")


class BlueprintBatchWriteRequest(BaseModel):
    total_scenes: int = Field(default=100, ge=1, le=500)
    duration_mode: str = Field(default="dynamic")
    premise: str = Field(default="")
    auto_split_shots: bool = Field(default=True)
    clear_existing: bool = Field(default=True)


class DialogueCalibrationRequest(BaseModel):
    raw_text: str = Field(description="Dialogue or voiceover text line")
    character_name: str = Field(default="Protagonist", description="Speaking character")
    target_language: str = Field(default="id-ID", description="Target locale: id-ID, en-US")
    max_seconds: float = Field(default=5.0, ge=1.0, le=60.0, description="Maximum duration limit")


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
) -> list[ShotModel]:
    """Auto-split/configure shots for multi-shot assembly (2 shots for 10s, 3 shots for 15s)."""
    if target_duration <= 5.0:
        needed_shots = 1
    elif target_duration <= 10.0:
        needed_shots = 2
    else:
        needed_shots = 3

    shot_duration = 5.0

    # Query existing shots for this scene
    stmt = (
        select(ShotModel)
        .where(ShotModel.scene_id == scene.id)
        .order_by(ShotModel.shot_number.asc())
    )
    existing_shots = list((await session.execute(stmt)).scalars().all())

    now = datetime.now(timezone.utc)
    configured_shots: list[ShotModel] = []

    for i in range(needed_shots):
        template = SHOT_CAMERA_TEMPLATES[min(i, len(SHOT_CAMERA_TEMPLATES) - 1)]
        if i < len(existing_shots):
            shot = existing_shots[i]
            shot.duration_seconds = shot_duration
            shot.shot_number = i + 1
            configured_shots.append(shot)
        else:
            new_shot = ShotModel(
                id=uuid.uuid4(),
                scene_id=scene.id,
                shot_number=i + 1,
                duration_seconds=shot_duration,
                camera_code=template["camera_code"],
                lens_code=template["lens_code"],
                comp_code=template["comp_code"],
                light_code=template["light_code"],
                act_code=template["act_code"],
                speed_code=template["speed_code"],
                status="PLANNED",
                created_at=now,
            )
            session.add(new_shot)
            configured_shots.append(new_shot)

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


@router.get("/projects/{project_id}/scenes", status_code=status.HTTP_200_OK)
async def list_project_scenes(
    project_id: str,
    act: int | None = Query(default=None, ge=1, le=4, description="Filter by Act 1-4"),
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve scenes for project, organized by 4-Act structure."""
    project = await _resolve_project(project_id, session)

    stmt = select(SceneModel).where(SceneModel.project_id == project.id)
    if act is not None:
        stmt = stmt.where(SceneModel.act_number == act)

    stmt = stmt.order_by(SceneModel.act_number.asc(), SceneModel.scene_number.asc())
    scenes = (await session.execute(stmt)).scalars().all()

    data = []
    for s in scenes:
        # Get shot count for each scene
        shots_count_stmt = select(func.count(ShotModel.id)).where(ShotModel.scene_id == s.id)
        shot_count = (await session.execute(shots_count_stmt)).scalar() or 0

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
                "created_at": s.created_at.isoformat(),
            }
        )

    return {"data": data, "total_scenes": len(data)}


def _calculate_act_and_beat(scene_num: int, total_scenes: int) -> tuple[int, str]:
    """Calculate Act number (1-4) and dramatic beat for arbitrary total scene count."""
    if total_scenes == 50:
        act1_end, act2_end, act3_end = 12, 25, 38
        act1_mid = 6
        act3_mid = 35
        act4_mid = 45
    else:
        act1_end = max(1, int(round(total_scenes * 0.25)))
        act2_end = max(act1_end + 1, int(round(total_scenes * 0.50)))
        act3_end = max(act2_end + 1, int(round(total_scenes * 0.75)))
        act1_mid = max(1, int(round(act1_end * 0.5)))
        act3_mid = act2_end + max(1, int(round((act3_end - act2_end) * 0.5)))
        act4_mid = act3_end + max(1, int(round((total_scenes - act3_end) * 0.5)))

    if scene_num <= act1_end:
        act = 1
        beat = (
            "The Setup & Inciting Incident"
            if scene_num == act1_mid
            else ("Plot Point 1" if scene_num == act1_end else "World Ordinary Life")
        )
    elif scene_num <= act2_end:
        act = 2
        beat = "Midpoint Reversal" if scene_num == act2_end else "Rising Stakes & Trials"
    elif scene_num <= act3_end:
        act = 3
        beat = (
            "All is Lost Crisis"
            if scene_num == act3_mid
            else ("Plot Point 2 Breakthrough" if scene_num == act3_end else "Dark Night of Soul")
        )
    else:
        act = 4
        beat = (
            "Climactic Confrontation"
            if scene_num == act4_mid
            else ("Final Catharsis & Resolution" if scene_num == total_scenes else "Race to the Climax")
        )

    return act, beat


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
        # Hollywood cinematic pacing curve:
        # Act I & III: Exposition, character depth, and emotional descent -> 15.0s
        # Act II & IV: Rising tension, trials, and climactic action -> 10.0s
        return 15.0 if act in (1, 3) else 10.0
    return 10.0


@router.post("/projects/{project_id}/scenes", status_code=status.HTTP_201_CREATED)
async def create_or_blueprint_scenes(
    project_id: str,
    payload: SceneCreateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Create a single scene or auto-generate the complete 50-to-420 Scene 4-Act Hollywood blueprint."""
    project = await _resolve_project(project_id, session)
    now = datetime.now(timezone.utc)

    if payload.generate_blueprint:
        if payload.clear_existing:
            await session.execute(delete(SceneModel).where(SceneModel.project_id == project.id))

        total_scenes = payload.total_scenes
        duration_mode = payload.duration_mode
        auto_split = payload.auto_split_shots

        preset_data = (project.settings or {}).get("preset_data", {})
        cold_open_cfg = preset_data.get("storyboard_defaults", {}).get("cold_open_30s", {})
        cold_open_enabled = bool(cold_open_cfg.get("enabled", False))

        # Bulk construct SceneModel and ShotModel entities in memory
        created_scenes: list[SceneModel] = []
        created_shots: list[ShotModel] = []

        for num in range(1, total_scenes + 1):
            act, beat = _calculate_act_and_beat(num, total_scenes)
            pad_width = 3 if total_scenes >= 100 else 2
            scene_id = uuid.uuid4()

            if cold_open_enabled and act == 1 and num in (1, 2, 3):
                duration_target = 10.0
                if num == 1:
                    slug = "SCENE 01 - INT/EXT. HIGH-VELOCITY CHAOS - DAY (COLD OPEN 0-10S)"
                    goal = "In-Media-Res Shock Hook + Hero Prop Reveal: Immediate high-energy visual shock hook in media res, dramatic hero prop reveal, dynamic camera movement."
                elif num == 2:
                    slug = "SCENE 02 - EXT. RUNAWAY SLAPSTICK OBSTACLE COURSE - CONTINUOUS (COLD OPEN 10-20S)"
                    goal = "Fast Slapstick Chaos Tease + Main Obstacle/Rival: Fast-paced comedic chaos tease, introduce antagonist/rival obstacle, rapid slapstick gag escalation."
                else:  # num == 3
                    slug = "SCENE 03 - EXT. PREVIEW OF THE ULTIMATE CLIMAX - CONTINUOUS (COLD OPEN 20-30S)"
                    goal = "Peak Climax Preview + Freeze-Frame/Rewind Transition ke Scene 04: Preview of peak catastrophic climax, abrupt comical freeze-frame / VHS rewind sound effect transitioning to linear story at Scene 04 (Ordinary World)."
            elif cold_open_enabled and act == 1 and num == 4:
                duration_target = _determine_scene_duration(act, duration_mode)
                slug = "SCENE 04 - INT. PROTAGONIST HOME / WORKSPACE - MORNING (ACT I: ORDINARY WORLD BEGINS)"
                goal = "Linear Narrative Setup (Act I: Ordinary World): Introduction of protagonist's routine, desires, and mundane life before the inciting incident."
            else:
                duration_target = _determine_scene_duration(act, duration_mode)
                slug = f"SCENE {str(num).zfill(pad_width)} - {project.title.upper()} - ACT {act}"
                goal = f"Beat: {beat}. Scene narrative objective for cinematic progression."

            scene = SceneModel(
                id=scene_id,
                project_id=project.id,
                act_number=act,
                scene_number=num,
                slugline=slug,
                narrative_goal=goal,
                duration_target=duration_target,
                status="PLANNED",
                created_at=now,
            )
            created_scenes.append(scene)

            if auto_split:
                if duration_target <= 5.0:
                    needed_shots = 1
                elif duration_target <= 10.0:
                    needed_shots = 2
                else:
                    needed_shots = 3

                shot_duration = 5.0
                for i in range(needed_shots):
                    if cold_open_enabled and act == 1 and num in (1, 2, 3):
                        if num == 1:
                            c_code = "#Cam 19" if i == 0 else "#Cam 23"
                            l_code = "#Lens 04" if i == 0 else "#Lens 02"
                            cp_code = "#Comp 03" if i == 0 else "#Comp 01"
                            sp_code = "#Speed 04"
                            dlg = (
                                "[SFX: Instant High-Pitched Comedic Whistle & Dramatic Boing - Protagonist eyes bulge in extreme close-up!]"
                                if i == 0
                                else "[SFX: Rapid Hero Prop Reveal Whoosh & Shimmering Bell Chime]"
                            )
                            trans = "NONE" if i == 0 else "J_CUT"
                        elif num == 2:
                            c_code = "#Cam 25" if i == 0 else "#Cam 06"
                            l_code = "#Lens 02" if i == 0 else "#Lens 04"
                            cp_code = "#Comp 01" if i == 0 else "#Comp 02"
                            sp_code = "#Speed 04"
                            dlg = (
                                "[SFX: Rapid Slip, Cartoon Car Horn Honk & Exaggerated Shocked Gasp as Rival Appears]"
                                if i == 0
                                else "[SFX: Escalating Anvil Drop Whistle & Frantic Running Sound FX]"
                            )
                            trans = "NONE" if i == 0 else "J_CUT"
                        else:  # num == 3
                            c_code = "#Cam 19" if i == 0 else "#Cam 25"
                            l_code = "#Lens 04" if i == 0 else "#Lens 03"
                            cp_code = "#Comp 03"
                            sp_code = "#Speed 04" if i == 0 else "#Speed 03"
                            dlg = (
                                "[SFX: Dramatic Orchestral Climax Swell Leading Directly to Disaster]"
                                if i == 0
                                else "[SFX: Record Scratch & VHS High-Speed Tape Rewind - 'Yep, that's me... you're probably wondering how I ended up here!']"
                            )
                            trans = "NONE" if i == 0 else "L_CUT"

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
                        new_shot = ShotModel(
                            id=uuid.uuid4(),
                            scene_id=scene_id,
                            shot_number=i + 1,
                            duration_seconds=shot_duration,
                            camera_code=template["camera_code"],
                            lens_code=template["lens_code"],
                            comp_code=template["comp_code"],
                            light_code=template["light_code"],
                            act_code=template["act_code"],
                            speed_code=template["speed_code"],
                            status="PLANNED",
                            created_at=now,
                        )
                    created_shots.append(new_shot)

        # Single bulk transaction for SQLite performance & concurrency safety
        session.add_all(created_scenes)
        if created_shots:
            session.add_all(created_shots)
        await session.commit()

        return {
            "data": {
                "message": f"Generated complete {len(created_scenes)}-Scene 4-Act Hollywood blueprint.",
                "scenes_generated": len(created_scenes),
                "shots_generated": len(created_shots),
                "total_scenes": len(created_scenes),
                "duration_mode": duration_mode,
            }
        }

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


@router.post("/projects/{project_id}/blueprint/treatment", status_code=status.HTTP_200_OK)
async def generate_blueprint_treatment(
    project_id: str,
    payload: BlueprintTreatmentRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Phase A: Generate 4-Act Master Story Treatment and Beat Sheet."""
    project = await _resolve_project(project_id, session)

    if payload.clear_existing:
        await session.execute(delete(SceneModel).where(SceneModel.project_id == project.id))
        await session.commit()

    char_stmt = select(CharacterModel).where(CharacterModel.project_id == project.id)
    characters_list = (await session.execute(char_stmt)).scalars().all()
    chars_data = [
        {"name": c.name, "role": c.role, "base_prompt": c.base_prompt}
        for c in characters_list
    ]

    preset_data = (project.settings or {}).get("preset_data", {})
    cold_open_cfg = preset_data.get("storyboard_defaults", {}).get("cold_open_30s")

    writer = StagedStoryWriter()
    treatment = await writer.generate_treatment(
        title=project.title,
        total_scenes=payload.total_scenes,
        premise=payload.premise,
        characters=chars_data,
        cold_open_30s=cold_open_cfg,
    )

    if not isinstance(project.settings, dict):
        project.settings = {}
    project.settings["treatment"] = treatment
    project.settings["treatment"]["duration_mode"] = payload.duration_mode
    project.settings["treatment"]["total_scenes"] = payload.total_scenes
    if "act_summaries" not in project.settings["treatment"]:
        project.settings["treatment"]["act_summaries"] = {}
    flag_modified(project, "settings")
    await session.commit()

    return {"data": treatment}


@router.post("/projects/{project_id}/blueprint/generate-act", status_code=status.HTTP_200_OK)
async def generate_blueprint_act(
    project_id: str,
    payload: BlueprintActGenerateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Phase B: Generate scenes and auto-split shots for a single Act with persistent context chaining."""
    project = await _resolve_project(project_id, session)
    now = datetime.now(timezone.utc)

    char_stmt = select(CharacterModel).where(CharacterModel.project_id == project.id)
    characters_list = (await session.execute(char_stmt)).scalars().all()
    chars_data = [
        {"name": c.name, "role": c.role, "base_prompt": c.base_prompt}
        for c in characters_list
    ]

    preset_data = (project.settings or {}).get("preset_data", {})
    cold_open_cfg = (
        (project.settings or {}).get("treatment", {}).get("cold_open_30s")
        or preset_data.get("storyboard_defaults", {}).get("cold_open_30s")
    )
    cold_open_active = bool(
        payload.act_number == 1 and cold_open_cfg and cold_open_cfg.get("enabled")
    )

    treatment = (project.settings or {}).get("treatment")
    writer = StagedStoryWriter()
    if not treatment:
        treatment = await writer.generate_treatment(
            title=project.title,
            total_scenes=payload.total_scenes,
            characters=chars_data,
            cold_open_30s=cold_open_cfg,
        )
        if not isinstance(project.settings, dict):
            project.settings = {}
        project.settings["treatment"] = treatment
        project.settings["treatment"]["act_summaries"] = {}
        flag_modified(project, "settings")
        await session.commit()
    elif cold_open_cfg and "cold_open_30s" not in treatment:
        treatment["cold_open_30s"] = cold_open_cfg
        project.settings["treatment"]["cold_open_30s"] = cold_open_cfg
        flag_modified(project, "settings")
        await session.commit()

    act_summaries_raw = (project.settings.get("treatment", {})).get("act_summaries", {})
    prev_summaries = {int(k): v for k, v in act_summaries_raw.items() if k.isdigit()}

    act_result = await writer.generate_act_scenes(
        act_number=payload.act_number,
        total_scenes=payload.total_scenes,
        treatment=treatment,
        previous_act_summaries=prev_summaries,
        characters=chars_data,
        duration_mode=payload.duration_mode,
        cold_open_30s=cold_open_cfg,
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

        scene = SceneModel(
            id=scene_id,
            project_id=project.id,
            act_number=payload.act_number,
            scene_number=s_num,
            slugline=sc_info.get("slugline") or f"SCENE {str(s_num).zfill(pad)} - INT. LOCATION - NIGHT",
            narrative_goal=sc_info.get("narrative_goal") or f"Act {payload.act_number} dramatic progression.",
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
                        dlg = primary_dialogue if (i == 0 and primary_dialogue) else (
                            "[SFX: Instant High-Pitched Comedic Whistle & Dramatic Boing - Protagonist eyes bulge in extreme close-up!]"
                            if i == 0
                            else "[SFX: Rapid Hero Prop Reveal Whoosh & Shimmering Bell Chime]"
                        )
                        trans = "NONE" if i == 0 else "J_CUT"
                    elif s_num == 2:
                        c_code = "#Cam 25" if i == 0 else "#Cam 06"
                        l_code = "#Lens 02" if i == 0 else "#Lens 04"
                        cp_code = "#Comp 01" if i == 0 else "#Comp 02"
                        sp_code = "#Speed 04"
                        dlg = primary_dialogue if (i == 0 and primary_dialogue) else (
                            "[SFX: Rapid Slip, Cartoon Car Horn Honk & Exaggerated Shocked Gasp as Rival Appears]"
                            if i == 0
                            else "[SFX: Escalating Anvil Drop Whistle & Frantic Running Sound FX]"
                        )
                        trans = "NONE" if i == 0 else "J_CUT"
                    else:  # s_num == 3
                        c_code = "#Cam 19" if i == 0 else "#Cam 25"
                        l_code = "#Lens 04" if i == 0 else "#Lens 03"
                        cp_code = "#Comp 03"
                        sp_code = "#Speed 04" if i == 0 else "#Speed 03"
                        dlg = primary_dialogue if (i == 0 and primary_dialogue) else (
                            "[SFX: Dramatic Orchestral Climax Swell Leading Directly to Disaster]"
                            if i == 0
                            else "[SFX: Record Scratch & VHS High-Speed Tape Rewind - 'Yep, that's me... you're probably wondering how I ended up here!']"
                        )
                        trans = "NONE" if i == 0 else "L_CUT"

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
                    dlg = primary_dialogue if i == 0 else (
                        f"Environmental cue: {scene.slugline.split('-')[-1].strip().lower()} ambient tone."
                        if i == 1 and not primary_dialogue else None
                    )
                    transition = "J_CUT" if i == 0 and dlg else "NONE"

                    new_shot = ShotModel(
                        id=uuid.uuid4(),
                        scene_id=scene_id,
                        shot_number=i + 1,
                        duration_seconds=shot_duration,
                        camera_code=template["camera_code"],
                        lens_code=template["lens_code"],
                        comp_code=template["comp_code"],
                        light_code=template["light_code"],
                        act_code=template["act_code"],
                        speed_code=template["speed_code"],
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
            "used_fallback": act_result["used_fallback"],
            "generator_type": "procedural_fallback" if act_result["used_fallback"] else "llm_writer",
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

    act_counts: dict[int, int] = {}
    for act in range(1, 5):
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
    treatment_req = BlueprintTreatmentRequest(
        total_scenes=payload.total_scenes,
        duration_mode=payload.duration_mode,
        premise=payload.premise,
        clear_existing=payload.clear_existing,
    )
    treatment_resp = await generate_blueprint_treatment(project_id, treatment_req, current_user, session)
    treatment_data = treatment_resp["data"]

    results = []
    for act in range(1, 5):
        act_req = BlueprintActGenerateRequest(
            act_number=act,
            total_scenes=payload.total_scenes,
            duration_mode=payload.duration_mode,
            auto_split_shots=payload.auto_split_shots,
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
            "message": f"Successfully completed 4-Act staged generation for {total_scenes_cnt} scenes.",
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

    # Fetch preview_url from shots if generated
    shot_stmt = select(ShotModel).where(ShotModel.scene_id == s_uuid).order_by(ShotModel.shot_number.asc())
    shots = (await session.execute(shot_stmt)).scalars().all()
    preview_url = None
    for sh in shots:
        if isinstance(sh.fg_bg_layers, dict) and sh.fg_bg_layers.get("preview_url"):
            preview_url = sh.fg_bg_layers.get("preview_url")
            break

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
            "preview_url": preview_url,
            "created_at": scene.created_at.isoformat(),
        }
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

    if payload.auto_split_shots and payload.duration_target is not None:
        await _perform_auto_split(scene, payload.duration_target, session)

    await session.commit()
    await session.refresh(scene)

    return {
        "data": {
            "id": str(scene.id),
            "act_number": scene.act_number,
            "scene_number": scene.scene_number,
            "slugline": scene.slugline,
            "narrative_goal": scene.narrative_goal,
            "duration_target": scene.duration_target,
            "status": scene.status,
        }
    }


@router.post("/scenes/{scene_id}/auto-split", status_code=status.HTTP_200_OK)
async def auto_split_scene(
    scene_id: str,
    payload: SceneAutoSplitRequest | None = None,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Auto-split/configure shots for multi-shot assembly (2 shots @ 5s for 10s, 3 shots @ 5s for 15s)."""
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
    scene.duration_target = target_duration

    shots = await _perform_auto_split(scene, target_duration, session)
    return {
        "data": {
            "scene_id": str(scene.id),
            "target_duration": target_duration,
            "shots_count": len(shots),
            "message": f"Configured {len(shots)} shots for {target_duration}s scene.",
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


@router.post("/scenes/{scene_id}/calibrate-dialogue", status_code=status.HTTP_200_OK)
async def calibrate_scene_dialogue(
    scene_id: str,
    payload: DialogueCalibrationRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Calibrate dialogue pacing, dynamic word count, duration limits, and J/L cuts."""
    s_uuid = uuid.UUID(scene_id)
    stmt = select(SceneModel).where(SceneModel.id == s_uuid)
    scene = (await session.execute(stmt)).scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    max_seconds = payload.max_seconds if payload.max_seconds > 0 else 5.0
    max_allowed_words = int(max_seconds * 2.8)

    word_count, syllables, est_duration = _estimate_syllables_and_pacing(payload.raw_text)
    passes_duration_limit = (word_count <= max_allowed_words) and (est_duration <= max_seconds)
    passes_5s_limit = passes_duration_limit  # Backward compatibility alias

    # Dynamic audio transition calculation:
    # Ambang J-Cut / L-Cut / Hard-Cut berbasis persentase durasi (>75% J_CUT, <40% HARD_CUT, sisanya L_CUT)
    duration_ratio = est_duration / max_seconds if max_seconds > 0 else 0.0
    if duration_ratio > 0.75:
        transition = "J_CUT"
        audio_lead = 1.0
    elif duration_ratio < 0.40:
        transition = "HARD_CUT"
        audio_lead = 0.0
    else:
        transition = "L_CUT"
        audio_lead = 0.5

    return {
        "data": {
            "scene_id": str(scene.id),
            "character_name": payload.character_name,
            "raw_text": payload.raw_text,
            "word_count": word_count,
            "syllable_count": syllables,
            "estimated_duration_seconds": est_duration,
            "passes_duration_limit": passes_duration_limit,
            "passes_5s_limit": passes_5s_limit,
            "max_allowed_words": max_allowed_words,
            "max_seconds": max_seconds,
            "transition_type": transition,
            "audio_lead_seconds": audio_lead,
        }
    }
