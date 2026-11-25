from datetime import datetime, timezone
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ValidationInfo, field_validator
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user, get_session
from backend.app.domain.catalog import validate_matrix_code
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
    # Frontend compatibility aliases
    composition_code: str | None = None
    lighting_code: str | None = None
    action_code: str | None = None
    prompt_override: str | None = None
    fg_bg_layers: dict[str, Any] = Field(default_factory=dict, description="Foreground/Background staging")
    dialogue: str | None = Field(default=None, description="Calibrated dialogue string")
    transition_type: str = Field(default="NONE", description="NONE, J_CUT, L_CUT, HARD_CUT")
    status: str = Field(default="PLANNED", description="PLANNED, COMPILED, GENERATING, APPROVED")

    @field_validator(
        "camera_code",
        "lens_code",
        "comp_code",
        "light_code",
        "act_code",
        "speed_code",
        "composition_code",
        "lighting_code",
        "action_code",
    )
    @classmethod
    def _validate_shot_matrix_codes(cls, value: str | None, info: ValidationInfo) -> str | None:
        return validate_matrix_code(info.field_name or "", value)


class ShotUpdateRequest(BaseModel):
    shot_number: int | None = None
    duration_seconds: float | None = Field(default=None, ge=1.0, le=60.0)
    camera_code: str | None = None
    lens_code: str | None = None
    comp_code: str | None = None
    light_code: str | None = None
    act_code: str | None = None
    speed_code: str | None = None
    composition_code: str | None = None
    lighting_code: str | None = None
    action_code: str | None = None
    prompt_override: str | None = None
    fg_bg_layers: dict[str, Any] | None = None
    dialogue: str | None = None
    transition_type: str | None = None
    status: str | None = None
    custom_background: str | None = None
    reset_background_override: bool | None = None

    @field_validator(
        "camera_code",
        "lens_code",
        "comp_code",
        "light_code",
        "act_code",
        "speed_code",
        "composition_code",
        "lighting_code",
        "action_code",
    )
    @classmethod
    def _validate_shot_update_matrix_codes(cls, value: str | None, info: ValidationInfo) -> str | None:
        return validate_matrix_code(info.field_name or "", value)


class SetCustomBackgroundRequest(BaseModel):
    custom_background: str = Field(..., min_length=1, description="URL or local path of custom background")


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

    # Determine Scene-level background preview for auto-inheritance
    scene_stmt = select(SceneModel).where(SceneModel.id == s_uuid)
    scene = (await session.execute(scene_stmt)).scalar_one_or_none()
    scene_preview_url = None
    if shots:
        prim = shots[0]
        if isinstance(prim.fg_bg_layers, dict) and prim.fg_bg_layers.get("preview_url"):
            scene_preview_url = prim.fg_bg_layers.get("preview_url")

    data = []
    for s in shots:
        layers = dict(s.fg_bg_layers) if isinstance(s.fg_bg_layers, dict) else {}
        custom_bg = layers.get("custom_background")
        is_custom = bool(custom_bg and str(custom_bg).strip())
        effective_bg = str(custom_bg).strip() if is_custom else (scene_preview_url or layers.get("preview_url"))
        bg_source = "custom" if is_custom else "inherited"

        data.append(
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
                "prompt_override": layers.get("prompt_override"),
                "preview_url": layers.get("preview_url"),
                "custom_background": custom_bg if is_custom else None,
                "effective_background_url": effective_bg,
                "background_source": bg_source,
                "dialogue": s.dialogue,
                "transition_type": s.transition_type,
                "status": s.status,
                "created_at": s.created_at.isoformat(),
            }
        )
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
    layers = dict(payload.fg_bg_layers or {})
    if payload.prompt_override and payload.prompt_override.strip():
        layers["prompt_override"] = payload.prompt_override.strip()

    shot = ShotModel(
        id=shot_id,
        scene_id=scene.id,
        shot_number=payload.shot_number,
        duration_seconds=payload.duration_seconds,
        camera_code=payload.camera_code,
        lens_code=payload.lens_code,
        comp_code=payload.composition_code or payload.comp_code,
        light_code=payload.lighting_code or payload.light_code,
        act_code=payload.action_code or payload.act_code,
        speed_code=payload.speed_code,
        fg_bg_layers=layers,
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
            "fg_bg_layers": shot.fg_bg_layers,
            "prompt_override": (shot.fg_bg_layers or {}).get("prompt_override"),
            "dialogue": shot.dialogue,
            "transition_type": shot.transition_type,
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

    data_dict = payload.model_dump(exclude_unset=True)
    custom_bg = data_dict.pop("custom_background", None)
    reset_bg = data_dict.pop("reset_background_override", None)
    prompt_ovr = data_dict.pop("prompt_override", None)
    alias_comp = data_dict.pop("composition_code", None)
    alias_light = data_dict.pop("lighting_code", None)
    alias_act = data_dict.pop("action_code", None)
    if alias_comp is not None and "comp_code" not in data_dict:
        data_dict["comp_code"] = alias_comp
    if alias_light is not None and "light_code" not in data_dict:
        data_dict["light_code"] = alias_light
    if alias_act is not None and "act_code" not in data_dict:
        data_dict["act_code"] = alias_act

    for field, val in data_dict.items():
        setattr(shot, field, val)

    layers = dict(shot.fg_bg_layers or {})
    layers_changed = False
    if prompt_ovr is not None:
        if prompt_ovr.strip():
            layers["prompt_override"] = prompt_ovr.strip()
        else:
            layers.pop("prompt_override", None)
        layers_changed = True

    if reset_bg:
        layers.pop("custom_background", None)
        layers_changed = True
    elif custom_bg is not None:
        if custom_bg.strip():
            layers["custom_background"] = custom_bg.strip()
        else:
            layers.pop("custom_background", None)
        layers_changed = True

    if layers_changed:
        shot.fg_bg_layers = layers
        flag_modified(shot, "fg_bg_layers")

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
            "transition_type": shot.transition_type,
            "fg_bg_layers": shot.fg_bg_layers,
            "prompt_override": (shot.fg_bg_layers or {}).get("prompt_override") if isinstance(shot.fg_bg_layers, dict) else None,
            "custom_background": (shot.fg_bg_layers or {}).get("custom_background") if isinstance(shot.fg_bg_layers, dict) else None,
            "status": shot.status,
        }
    }


@router.post("/shots/{shot_id}/reset-background", status_code=status.HTTP_200_OK)
async def reset_shot_background_override(
    shot_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Reset shot background override back to auto-inherit from Scene level."""
    s_uuid = uuid.UUID(shot_id)
    stmt = select(ShotModel).where(ShotModel.id == s_uuid)
    shot = (await session.execute(stmt)).scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")

    layers = dict(shot.fg_bg_layers or {}) if isinstance(shot.fg_bg_layers, dict) else {}
    layers.pop("custom_background", None)
    shot.fg_bg_layers = layers
    flag_modified(shot, "fg_bg_layers")

    await session.commit()
    await session.refresh(shot)
    return {
        "status": "success",
        "shot_id": str(shot.id),
        "background_source": "inherited",
        "custom_background": None,
        "message": "Custom background override removed. Shot now inherits Scene background.",
    }


@router.post("/shots/{shot_id}/custom-background", status_code=status.HTTP_200_OK)
async def set_shot_custom_background(
    shot_id: str,
    payload: SetCustomBackgroundRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Set custom background override for this specific shot."""
    s_uuid = uuid.UUID(shot_id)
    stmt = select(ShotModel).where(ShotModel.id == s_uuid)
    shot = (await session.execute(stmt)).scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")

    layers = dict(shot.fg_bg_layers or {}) if isinstance(shot.fg_bg_layers, dict) else {}
    layers["custom_background"] = payload.custom_background.strip()
    shot.fg_bg_layers = layers
    flag_modified(shot, "fg_bg_layers")

    await session.commit()
    await session.refresh(shot)
    return {
        "status": "success",
        "shot_id": str(shot.id),
        "background_source": "custom",
        "custom_background": payload.custom_background.strip(),
        "message": "Custom background override saved for shot.",
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
