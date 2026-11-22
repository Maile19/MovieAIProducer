from datetime import datetime, timezone
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user, get_session
from backend.app.infrastructure.database.models.auth import UserModel
from backend.app.infrastructure.database.models.story import SceneModel, ShotModel

router = APIRouter(tags=["Cinematography Shots"])


class ShotCreateRequest(BaseModel):
    shot_number: int = Field(default=1, description="Sequential shot order in scene")
    duration_seconds: float = Field(default=5.0, ge=1.0, le=60.0, description="Duration in seconds (e.g. 5.0, 10.0, 15.0)")
    camera_code: str = Field(default="#Cam 01", description="#Cam 01 to #Cam 34")
    lens_code: str = Field(default="#Lens 01", description="#Lens 01 to #Lens 06")
    comp_code: str = Field(default="#Comp 01", description="#Comp 01 to #Comp 08")
    light_code: str = Field(default="#Light 01", description="#Light 01 to #Light 14")
    act_code: str = Field(default="#Act 01", description="#Act 01 to #Act 24")
    speed_code: str = Field(default="#Speed 01", description="#Speed 01 to #Speed 05")
    fg_bg_layers: dict[str, Any] = Field(default_factory=dict, description="Foreground/Background staging")
    dialogue: str | None = Field(default=None, description="Calibrated dialogue string")
    transition_type: str = Field(default="NONE", description="NONE, J_CUT, L_CUT, HARD_CUT")
    status: str = Field(default="PLANNED", description="PLANNED, COMPILED, GENERATING, APPROVED")


class ShotUpdateRequest(BaseModel):
    shot_number: int | None = None
    duration_seconds: float | None = Field(default=None, ge=1.0, le=60.0)
    camera_code: str | None = None
    lens_code: str | None = None
    comp_code: str | None = None
    light_code: str | None = None
    act_code: str | None = None
    speed_code: str | None = None
    fg_bg_layers: dict[str, Any] | None = None
    dialogue: str | None = None
    transition_type: str | None = None
    status: str | None = None


@router.get("/scenes/{scene_id}/shots", status_code=status.HTTP_200_OK)
@router.get("/projects/{project_id}/scenes/{scene_id}/shots", status_code=status.HTTP_200_OK)
async def list_scene_shots(
    scene_id: str,
    project_id: str | None = None,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve all shots sequenced within a scene."""
    s_uuid = uuid.UUID(scene_id)
    stmt = select(ShotModel).where(ShotModel.scene_id == s_uuid).order_by(ShotModel.shot_number.asc())
    shots = (await session.execute(stmt)).scalars().all()

    data = [
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
            "fg_bg_layers": s.fg_bg_layers,
            "preview_url": s.fg_bg_layers.get("preview_url") if isinstance(s.fg_bg_layers, dict) else None,
            "dialogue": s.dialogue,
            "transition_type": s.transition_type,
            "status": s.status,
            "created_at": s.created_at.isoformat(),
        }
        for s in shots
    ]
    return {"data": data}


@router.post("/scenes/{scene_id}/shots", status_code=status.HTTP_201_CREATED)
async def create_shot(
    scene_id: str,
    payload: ShotCreateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Append a new cinematographic shot to the scene."""
    s_uuid = uuid.UUID(scene_id)
    scene_stmt = select(SceneModel).where(SceneModel.id == s_uuid)
    scene = (await session.execute(scene_stmt)).scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    shot_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    shot = ShotModel(
        id=shot_id,
        scene_id=scene.id,
        shot_number=payload.shot_number,
        duration_seconds=payload.duration_seconds,
        camera_code=payload.camera_code,
        lens_code=payload.lens_code,
        comp_code=payload.comp_code,
        light_code=payload.light_code,
        act_code=payload.act_code,
        speed_code=payload.speed_code,
        fg_bg_layers=payload.fg_bg_layers,
        dialogue=payload.dialogue,
        transition_type=payload.transition_type,
        status=payload.status,
        created_at=now,
    )
    session.add(shot)
    await session.commit()
    await session.refresh(shot)

    return {
        "data": {
            "id": str(shot.id),
            "scene_id": str(shot.scene_id),
            "shot_number": shot.shot_number,
            "duration_seconds": shot.duration_seconds,
            "camera_code": shot.camera_code,
            "lens_code": shot.lens_code,
            "comp_code": shot.comp_code,
            "light_code": shot.light_code,
            "act_code": shot.act_code,
            "speed_code": shot.speed_code,
            "dialogue": shot.dialogue,
            "status": shot.status,
            "created_at": shot.created_at.isoformat(),
        }
    }


@router.get("/shots/{shot_id}", status_code=status.HTTP_200_OK)
async def get_shot(
    shot_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve shot details."""
    s_uuid = uuid.UUID(shot_id)
    stmt = select(ShotModel).where(ShotModel.id == s_uuid)
    shot = (await session.execute(stmt)).scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")

    return {
        "data": {
            "id": str(shot.id),
            "scene_id": str(shot.scene_id),
            "shot_number": shot.shot_number,
            "duration_seconds": shot.duration_seconds,
            "camera_code": shot.camera_code,
            "lens_code": shot.lens_code,
            "comp_code": shot.comp_code,
            "light_code": shot.light_code,
            "act_code": shot.act_code,
            "speed_code": shot.speed_code,
            "fg_bg_layers": shot.fg_bg_layers,
            "preview_url": shot.fg_bg_layers.get("preview_url") if isinstance(shot.fg_bg_layers, dict) else None,
            "dialogue": shot.dialogue,
            "transition_type": shot.transition_type,
            "status": shot.status,
            "created_at": shot.created_at.isoformat(),
        }
    }


@router.put("/shots/{shot_id}", status_code=status.HTTP_200_OK)
async def update_shot(
    shot_id: str,
    payload: ShotUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Update shot matrix codes or dialogue."""
    s_uuid = uuid.UUID(shot_id)
    stmt = select(ShotModel).where(ShotModel.id == s_uuid)
    shot = (await session.execute(stmt)).scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")

    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(shot, field, val)

    await session.commit()
    await session.refresh(shot)
    return {
        "data": {
            "id": str(shot.id),
            "shot_number": shot.shot_number,
            "camera_code": shot.camera_code,
            "lens_code": shot.lens_code,
            "comp_code": shot.comp_code,
            "light_code": shot.light_code,
            "act_code": shot.act_code,
            "speed_code": shot.speed_code,
            "status": shot.status,
        }
    }


@router.delete("/shots/{shot_id}", status_code=status.HTTP_200_OK)
async def delete_shot(
    shot_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Delete a shot."""
    s_uuid = uuid.UUID(shot_id)
    stmt = select(ShotModel).where(ShotModel.id == s_uuid)
    shot = (await session.execute(stmt)).scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")

    await session.delete(shot)
    await session.commit()
    return {"data": {"message": f"Shot {shot.shot_number} deleted successfully."}}
