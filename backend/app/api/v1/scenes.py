from datetime import datetime, timezone
import math
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user, get_session
from backend.app.infrastructure.database.models.auth import UserModel
from backend.app.infrastructure.database.models.project import ProjectModel
from backend.app.infrastructure.database.models.story import SceneModel, ShotModel

router = APIRouter(tags=["Scenes & Storyboard"])


class SceneCreateRequest(BaseModel):
    act_number: int = Field(default=1, ge=1, le=4, description="Act 1 to 4")
    scene_number: int = Field(default=1, ge=1, le=50, description="Scene number 1 to 50")
    slugline: str = Field(default="INT. LOCATION - DAY", max_length=255)
    narrative_goal: str = Field(default="", description="Dramatic goal of the scene")
    duration_target: float = Field(default=5.0, description="Target seconds (default 5.0)")
    status: str = Field(default="PLANNED", description="PLANNED, IN_PROGRESS, APPROVED, LOCKED")
    generate_blueprint: bool = Field(default=False, description="If True, auto-generate standard 50-Scene 4-Act blueprint")


class SceneUpdateRequest(BaseModel):
    slugline: str | None = None
    narrative_goal: str | None = None
    duration_target: float | None = None
    status: str | None = None


class DialogueCalibrationRequest(BaseModel):
    raw_text: str = Field(description="Dialogue or voiceover text line")
    character_name: str = Field(default="Protagonist", description="Speaking character")
    target_language: str = Field(default="id-ID", description="Target locale: id-ID, en-US")
    max_seconds: float = Field(default=5.0, description="Maximum duration limit")


def _estimate_syllables_and_pacing(text: str) -> tuple[int, int, float]:
    """Calculate word count, syllable approximation, and estimated duration in seconds."""
    words = text.strip().split()
    word_count = len(words)
    if word_count == 0:
        return 0, 0, 0.0

    # Approximate syllable count: 1.5 syllables per word average in English/Indonesian
    # At standard cinematic delivery speed of ~140 words per minute (2.33 words / sec)
    estimated_duration = round(word_count / 2.33, 2)
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


@router.post("/projects/{project_id}/scenes", status_code=status.HTTP_201_CREATED)
async def create_or_blueprint_scenes(
    project_id: str,
    payload: SceneCreateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Create a single scene or auto-generate the complete 50-Scene 4-Act Hollywood blueprint."""
    project = await _resolve_project(project_id, session)
    now = datetime.now(timezone.utc)

    if payload.generate_blueprint:
        # Generate 50 scenes partitioned into 4 Acts:
        # Act I (Setup): Scenes 1–12
        # Act II-A (Rising Action): Scenes 13–25
        # Act II-B (Descent / Dark Night of Soul): Scenes 26–38
        # Act III & IV (Climax & Resolution): Scenes 39–50
        created_scenes = []
        for num in range(1, 51):
            if num <= 12:
                act = 1
                beat = "The Setup & Inciting Incident" if num == 6 else ("Plot Point 1" if num == 12 else "World Ordinary Life")
            elif num <= 25:
                act = 2
                beat = "Midpoint Reversal" if num == 25 else "Rising Stakes & Trials"
            elif num <= 38:
                act = 3
                beat = "All is Lost Crisis" if num == 35 else ("Plot Point 2 Breakthrough" if num == 38 else "Dark Night of Soul")
            else:
                act = 4
                beat = "Climactic Confrontation" if num == 45 else ("Final Catharsis & Resolution" if num == 50 else "Race to the Climax")

            scene = SceneModel(
                id=uuid.uuid4(),
                project_id=project.id,
                act_number=act,
                scene_number=num,
                slugline=f"SCENE {num:02d} - {project.title.upper()} - ACT {act}",
                narrative_goal=f"Beat: {beat}. Scene narrative objective for cinematic progression.",
                duration_target=5.0,
                status="PLANNED",
                created_at=now,
            )
            session.add(scene)
            created_scenes.append(scene)

        await session.commit()
        return {
            "data": {
                "message": "Generated complete 50-Scene 4-Act Hollywood blueprint.",
                "scenes_generated": len(created_scenes),
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
    """Calibrate dialogue pacing, word count, 5.0-second limits, and J/L cuts."""
    s_uuid = uuid.UUID(scene_id)
    stmt = select(SceneModel).where(SceneModel.id == s_uuid)
    scene = (await session.execute(stmt)).scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    word_count, syllables, est_duration = _estimate_syllables_and_pacing(payload.raw_text)
    passes_limit = (word_count <= 14) and (est_duration <= payload.max_seconds)

    # Audio transition calculation: if duration > 3.8s, recommend J-cut with 1.0s audio lead
    if est_duration > 3.8:
        transition = "J_CUT"
        audio_lead = 1.0
    elif est_duration < 2.0:
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
            "passes_5s_limit": passes_limit,
            "max_allowed_words": 14,
            "transition_type": transition,
            "audio_lead_seconds": audio_lead,
        }
    }
