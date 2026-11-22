from datetime import datetime, timezone
import re
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.app.api.deps import get_current_user, get_session
from backend.app.infrastructure.database.models.auth import UserModel
from backend.app.infrastructure.database.models.preset import ProductionPresetModel
from backend.app.infrastructure.database.models.project import (
    MasterProductionBibleModel,
    ProjectModel,
)
from backend.app.infrastructure.database.models.story import SceneModel, ShotModel

router = APIRouter(tags=["Production Presets"])


def slugify(text: str) -> str:
    """Generate a clean URL-safe slug from text."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-") or "preset"


class PresetCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255, description="Preset name")
    slug: str | None = Field(default=None, max_length=255, description="URL-safe slug")
    description: str = Field(default="", description="Detailed description")
    category: str = Field(default="general", max_length=64, description="Category / genre")
    preset_data: dict[str, Any] = Field(description="Holistic preset specification JSON")


class PresetUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    category: str | None = None
    preset_data: dict[str, Any] | None = None


class SaveProjectAsPresetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255, description="Preset name")
    slug: str | None = Field(default=None, max_length=255)
    description: str = Field(default="", description="Preset description")
    category: str = Field(default="custom", max_length=64)


class ApplyPresetRequest(BaseModel):
    preset_id: str = Field(description="UUID or slug of preset to apply")


async def _resolve_preset(preset_id: str, session: AsyncSession) -> ProductionPresetModel:
    try:
        p_uuid = uuid.UUID(preset_id)
        stmt = select(ProductionPresetModel).where(ProductionPresetModel.id == p_uuid)
    except ValueError:
        stmt = select(ProductionPresetModel).where(ProductionPresetModel.slug == preset_id)

    res = await session.execute(stmt)
    preset = res.scalar_one_or_none()
    if not preset:
        raise HTTPException(status_code=404, detail="Production preset not found")
    return preset


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


@router.get("/presets", status_code=status.HTTP_200_OK)
async def list_presets(
    category: str | None = Query(default=None, description="Filter by category"),
    search: str | None = Query(default=None, description="Search by name or description"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """List all available production presets."""
    stmt = select(ProductionPresetModel)

    if category:
        stmt = stmt.where(ProductionPresetModel.category == category)
    if search:
        search_filter = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                ProductionPresetModel.name.ilike(search_filter),
                ProductionPresetModel.description.ilike(search_filter),
            )
        )

    stmt = (
        stmt.order_by(ProductionPresetModel.is_system.desc(), ProductionPresetModel.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    presets = result.scalars().all()

    data = [
        {
            "id": str(p.id),
            "name": p.name,
            "slug": p.slug,
            "description": p.description,
            "category": p.category,
            "is_system": p.is_system,
            "created_by_user_id": str(p.created_by_user_id) if p.created_by_user_id else None,
            "preset_data": p.preset_data,
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat(),
        }
        for p in presets
    ]

    return {"data": data, "pagination": {"limit": limit, "offset": offset, "count": len(data)}}


@router.post("/presets", status_code=status.HTTP_201_CREATED)
async def create_preset(
    payload: PresetCreateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Create a new reusable production preset."""
    base_slug = payload.slug or slugify(payload.name)
    final_slug = base_slug

    check_stmt = select(ProductionPresetModel).where(ProductionPresetModel.slug == final_slug)
    existing = (await session.execute(check_stmt)).scalar_one_or_none()
    if existing:
        final_slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

    now = datetime.now(timezone.utc)
    preset = ProductionPresetModel(
        id=uuid.uuid4(),
        name=payload.name,
        slug=final_slug,
        description=payload.description,
        category=payload.category,
        is_system=False,
        created_by_user_id=current_user.id,
        preset_data=payload.preset_data,
        created_at=now,
        updated_at=now,
    )
    session.add(preset)
    await session.commit()
    await session.refresh(preset)

    return {
        "data": {
            "id": str(preset.id),
            "name": preset.name,
            "slug": preset.slug,
            "description": preset.description,
            "category": preset.category,
            "is_system": preset.is_system,
            "created_by_user_id": str(preset.created_by_user_id) if preset.created_by_user_id else None,
            "preset_data": preset.preset_data,
            "created_at": preset.created_at.isoformat(),
            "updated_at": preset.updated_at.isoformat(),
        }
    }


@router.get("/presets/{preset_id}", status_code=status.HTTP_200_OK)
async def get_preset(
    preset_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve full production preset specification."""
    preset = await _resolve_preset(preset_id, session)
    return {
        "data": {
            "id": str(preset.id),
            "name": preset.name,
            "slug": preset.slug,
            "description": preset.description,
            "category": preset.category,
            "is_system": preset.is_system,
            "created_by_user_id": str(preset.created_by_user_id) if preset.created_by_user_id else None,
            "preset_data": preset.preset_data,
            "created_at": preset.created_at.isoformat(),
            "updated_at": preset.updated_at.isoformat(),
        }
    }


@router.put("/presets/{preset_id}", status_code=status.HTTP_200_OK)
async def update_preset(
    preset_id: str,
    payload: PresetUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Update custom production preset parameters."""
    preset = await _resolve_preset(preset_id, session)

    if preset.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System seed presets cannot be modified.",
        )

    if payload.name is not None:
        preset.name = payload.name
    if payload.description is not None:
        preset.description = payload.description
    if payload.category is not None:
        preset.category = payload.category
    if payload.preset_data is not None:
        preset.preset_data = payload.preset_data

    preset.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(preset)

    return {
        "data": {
            "id": str(preset.id),
            "name": preset.name,
            "slug": preset.slug,
            "description": preset.description,
            "category": preset.category,
            "is_system": preset.is_system,
            "preset_data": preset.preset_data,
            "updated_at": preset.updated_at.isoformat(),
        }
    }


@router.delete("/presets/{preset_id}", status_code=status.HTTP_200_OK)
async def delete_preset(
    preset_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Delete a user-defined production preset."""
    preset = await _resolve_preset(preset_id, session)

    if preset.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System seed presets cannot be deleted.",
        )

    await session.delete(preset)
    await session.commit()
    return {"data": {"message": f"Preset '{preset.name}' deleted successfully."}}


@router.post("/projects/{project_id}/save-as-preset", status_code=status.HTTP_201_CREATED)
async def save_project_as_preset(
    project_id: str,
    payload: SaveProjectAsPresetRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Extract full active project configuration and save as a reusable production preset."""
    project = await _resolve_project(project_id, session)

    # 1. Fetch active Bible
    bible_stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == project.id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    bible = (await session.execute(bible_stmt)).scalar_one_or_none()

    # 2. Fetch scenes count and sample pacing
    scene_stmt = (
        select(SceneModel)
        .where(SceneModel.project_id == project.id)
        .order_by(SceneModel.act_number.asc(), SceneModel.scene_number.asc())
    )
    scenes = list((await session.execute(scene_stmt)).scalars().all())

    # Build holistic preset_data
    preset_data: dict[str, Any] = {
        "project_defaults": {
            "aspect_ratio": project.aspect_ratio,
            "target_style_code": project.target_style_code,
            "operational_stage": 1,
            "settings": project.settings,
        },
        "bible_blueprint": {
            "style_parameters": bible.style_parameters if bible else {"master_style_code": project.target_style_code},
            "world_rules": bible.world_rules if bible else {},
        },
        "storyboard_defaults": {
            "total_scenes": len(scenes) if scenes else 50,
            "default_scene_duration": scenes[0].duration_target if scenes else 5.0,
        },
        "transpiler_rules": {
            "default_matrix_codes": {
                "style_code": project.target_style_code,
            }
        },
        "qc_gate_thresholds": {
            "overall_score": 0.85,
            "face_similarity_insightface": 0.82,
            "aesthetic_score": 8.0,
            "temporal_jitter_variance": 0.15,
        },
    }

    base_slug = payload.slug or slugify(payload.name)
    final_slug = base_slug
    check_stmt = select(ProductionPresetModel).where(ProductionPresetModel.slug == final_slug)
    existing = (await session.execute(check_stmt)).scalar_one_or_none()
    if existing:
        final_slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

    now = datetime.now(timezone.utc)
    preset = ProductionPresetModel(
        id=uuid.uuid4(),
        name=payload.name,
        slug=final_slug,
        description=payload.description or f"Preset generated from project '{project.title}'",
        category=payload.category,
        is_system=False,
        created_by_user_id=current_user.id,
        preset_data=preset_data,
        created_at=now,
        updated_at=now,
    )
    session.add(preset)
    await session.commit()
    await session.refresh(preset)

    return {
        "data": {
            "id": str(preset.id),
            "name": preset.name,
            "slug": preset.slug,
            "description": preset.description,
            "category": preset.category,
            "is_system": preset.is_system,
            "preset_data": preset.preset_data,
            "created_at": preset.created_at.isoformat(),
            "updated_at": preset.updated_at.isoformat(),
        }
    }


@router.post("/projects/{project_id}/apply-preset", status_code=status.HTTP_200_OK)
async def apply_preset_to_project(
    project_id: str,
    payload: ApplyPresetRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Apply a reusable production preset to an existing project.
    
    If Master Production Bible is locked, returns HTTP 409 Conflict.
    """
    project = await _resolve_project(project_id, session)
    preset = await _resolve_preset(payload.preset_id, session)

    # 1. Validation: check if MPB is locked
    bible_stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == project.id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    bible = (await session.execute(bible_stmt)).scalar_one_or_none()

    if bible and bible.is_locked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Master Production Bible is locked. DNA freeze is active; unlock the Bible before applying a new preset.",
        )

    # 2. Extract preset configurations
    preset_data = preset.preset_data or {}
    proj_defaults = preset_data.get("project_defaults", {})
    bible_blueprint = preset_data.get("bible_blueprint", {})

    if "aspect_ratio" in proj_defaults:
        project.aspect_ratio = proj_defaults["aspect_ratio"]
    if "target_style_code" in proj_defaults:
        project.target_style_code = proj_defaults["target_style_code"]

    settings = dict(project.settings or {})
    settings["preset_id"] = str(preset.id)
    settings["preset_slug"] = preset.slug
    settings["preset_name"] = preset.name
    settings["preset_data"] = preset_data
    project.settings = settings
    flag_modified(project, "settings")

    now = datetime.now(timezone.utc)
    project.updated_at = now

    # 3. Update or create MPB
    if bible:
        if "style_parameters" in bible_blueprint:
            merged_styles = dict(bible.style_parameters or {})
            merged_styles.update(bible_blueprint["style_parameters"])
            bible.style_parameters = merged_styles
            flag_modified(bible, "style_parameters")

        if "world_rules" in bible_blueprint:
            merged_rules = dict(bible.world_rules or {})
            merged_rules.update(bible_blueprint["world_rules"])
            bible.world_rules = merged_rules
            flag_modified(bible, "world_rules")

        bible.updated_at = now
    else:
        new_bible = MasterProductionBibleModel(
            id=uuid.uuid4(),
            project_id=project.id,
            version=1,
            is_locked=False,
            style_parameters=bible_blueprint.get("style_parameters", {}),
            world_rules=bible_blueprint.get("world_rules", {}),
            created_at=now,
            updated_at=now,
        )
        session.add(new_bible)

    await session.commit()
    await session.refresh(project)

    return {
        "data": {
            "project_id": str(project.id),
            "preset_applied": {
                "id": str(preset.id),
                "name": preset.name,
                "slug": preset.slug,
            },
            "aspect_ratio": project.aspect_ratio,
            "target_style_code": project.target_style_code,
            "settings": project.settings,
            "message": f"Preset '{preset.name}' successfully applied to project '{project.title}'.",
        }
    }
