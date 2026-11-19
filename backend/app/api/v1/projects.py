from datetime import datetime, timezone
import re
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user, get_session
from backend.app.infrastructure.database.models.auth import ProjectMemberModel, UserModel
from backend.app.infrastructure.database.models.project import (
    MasterProductionBibleModel,
    ProjectModel,
)
from backend.app.infrastructure.database.models.story import SceneModel, ShotModel

router = APIRouter(prefix="/projects", tags=["Projects"])

STAGE_NAMES: dict[int, str] = {
    1: "Concept & Logline Specification",
    2: "Genre & Visual Style Catalog (#Style)",
    3: "4-Act Storyboard & 50-Scene Blueprint",
    4: "Character Profile & Voice DNA",
    5: "Dynamic Character Evolution Matrix (#State)",
    6: "Environment Bible & Hero Prop Continuity",
    7: "Dialogue Pacing & Audio Bridge Calibration",
    8: "Cinematography Optics & Framing Matrix (#Cam, #Lens, #Comp)",
    9: "Cinematic Lighting & Performance Matrix (#Light, #Act)",
    10: "Prompt Transpilation & Compiler Freeze",
    11: "Generative Video & Audio Inference Execution",
    12: "Automated Biometric & Aesthetic QC Audit",
    13: "Timeline Multi-Track Assembly (NLE)",
    14: "Cinematic Color Timing & Film Emulation",
    15: "Soundtrack & Foley Acoustic Mastering",
    16: "Final Showrunner Master Cut Delivery",
}


def slugify(text: str) -> str:
    """Generate a clean URL-safe slug from text."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-") or "project"


class ProjectCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255, description="Project title")
    slug: str | None = Field(default=None, max_length=255, description="URL-safe slug")
    aspect_ratio: str = Field(default="16:9", description="16:9 or 9:16")
    target_style_code: str = Field(default="#Style 01", description="#Style 01 to #Style 18")
    settings: dict[str, Any] = Field(default_factory=dict, description="Project settings")


class ProjectUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    aspect_ratio: str | None = None
    target_style_code: str | None = None
    status: str | None = None
    settings: dict[str, Any] | None = None


class GateActionRequest(BaseModel):
    action: str = Field(description="Gate action: APPROVE, REVISE, or LOCK")
    notes: str = Field(default="", description="Director / Showrunner notes")
    target_stage: int | None = Field(default=None, description="Optional target stage")


@router.get("", status_code=status.HTTP_200_OK)
async def list_projects(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """List film projects accessible to the current user."""
    stmt = select(ProjectModel)
    if search:
        search_filter = f"%{search.strip()}%"
        stmt = stmt.where(ProjectModel.title.ilike(search_filter))

    stmt = stmt.order_by(ProjectModel.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    projects = result.scalars().all()

    data = []
    for p in projects:
        data.append(
            {
                "id": str(p.id),
                "title": p.title,
                "slug": p.slug,
                "status": p.status,
                "aspect_ratio": p.aspect_ratio,
                "target_style_code": p.target_style_code,
                "operational_stage": p.operational_stage,
                "stage_name": STAGE_NAMES.get(p.operational_stage, "Unknown Stage"),
                "owner_id": str(p.owner_id) if p.owner_id else None,
                "created_at": p.created_at.isoformat(),
                "updated_at": p.updated_at.isoformat(),
            }
        )

    return {"data": data, "pagination": {"limit": limit, "offset": offset, "count": len(data)}}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Initialize a new cinematic film production project."""
    base_slug = payload.slug or slugify(payload.title)
    final_slug = base_slug

    # Ensure unique slug
    check_stmt = select(ProjectModel).where(ProjectModel.slug == final_slug)
    existing = (await session.execute(check_stmt)).scalar_one_or_none()
    if existing:
        final_slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

    project_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    project = ProjectModel(
        id=project_id,
        title=payload.title,
        slug=final_slug,
        status="PLANNING",
        aspect_ratio=payload.aspect_ratio,
        target_style_code=payload.target_style_code,
        operational_stage=1,
        owner_id=current_user.id,
        settings=payload.settings,
        created_at=now,
        updated_at=now,
    )
    session.add(project)
    await session.flush()

    # Link user as project member
    member = ProjectMemberModel(
        id=uuid.uuid4(),
        project_id=project_id,
        user_id=current_user.id,
        role="SHOWRUNNER",
        created_at=now,
    )
    session.add(member)

    # Initialize default Master Production Bible (version 1)
    bible = MasterProductionBibleModel(
        id=uuid.uuid4(),
        project_id=project_id,
        version=1,
        is_locked=False,
        locked_at=None,
        locked_by_user_id=None,
        style_parameters={
            "master_style_code": payload.target_style_code,
            "render_pipeline": "Photorealistic 35mm Film Grain",
            "aspect_ratio": payload.aspect_ratio,
        },
        world_rules={
            "gravity": "earth_standard",
            "atmosphere": "naturalistic",
        },
        created_at=now,
        updated_at=now,
    )
    session.add(bible)

    await session.commit()
    await session.refresh(project)

    return {
        "data": {
            "id": str(project.id),
            "title": project.title,
            "slug": project.slug,
            "status": project.status,
            "aspect_ratio": project.aspect_ratio,
            "target_style_code": project.target_style_code,
            "operational_stage": project.operational_stage,
            "stage_name": STAGE_NAMES.get(project.operational_stage, "Unknown Stage"),
            "owner_id": str(project.owner_id) if project.owner_id else None,
            "created_at": project.created_at.isoformat(),
            "updated_at": project.updated_at.isoformat(),
        }
    }


@router.get("/{project_id}", status_code=status.HTTP_200_OK)
async def get_project(
    project_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve full project details, stage metrics, and bible summary."""
    try:
        p_uuid = uuid.UUID(project_id)
        stmt = select(ProjectModel).where(ProjectModel.id == p_uuid)
    except ValueError:
        stmt = select(ProjectModel).where(ProjectModel.slug == project_id)

    result = await session.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Counts
    scene_count_stmt = select(func.count(SceneModel.id)).where(SceneModel.project_id == project.id)
    scene_count = (await session.execute(scene_count_stmt)).scalar() or 0

    bible_stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == project.id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    active_bible = (await session.execute(bible_stmt)).scalar_one_or_none()

    return {
        "data": {
            "id": str(project.id),
            "title": project.title,
            "slug": project.slug,
            "status": project.status,
            "aspect_ratio": project.aspect_ratio,
            "target_style_code": project.target_style_code,
            "operational_stage": project.operational_stage,
            "stage_name": STAGE_NAMES.get(project.operational_stage, "Unknown Stage"),
            "owner_id": str(project.owner_id) if project.owner_id else None,
            "settings": project.settings,
            "stats": {
                "scenes_count": scene_count,
                "bible_version": active_bible.version if active_bible else 1,
                "bible_locked": active_bible.is_locked if active_bible else False,
            },
            "created_at": project.created_at.isoformat(),
            "updated_at": project.updated_at.isoformat(),
        }
    }


@router.put("/{project_id}", status_code=status.HTTP_200_OK)
async def update_project(
    project_id: str,
    payload: ProjectUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Update project configuration parameters."""
    try:
        p_uuid = uuid.UUID(project_id)
        stmt = select(ProjectModel).where(ProjectModel.id == p_uuid)
    except ValueError:
        stmt = select(ProjectModel).where(ProjectModel.slug == project_id)

    result = await session.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if payload.title is not None:
        project.title = payload.title
    if payload.aspect_ratio is not None:
        project.aspect_ratio = payload.aspect_ratio
    if payload.target_style_code is not None:
        project.target_style_code = payload.target_style_code
    if payload.status is not None:
        project.status = payload.status
    if payload.settings is not None:
        project.settings = payload.settings

    project.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(project)

    return {
        "data": {
            "id": str(project.id),
            "title": project.title,
            "slug": project.slug,
            "status": project.status,
            "aspect_ratio": project.aspect_ratio,
            "target_style_code": project.target_style_code,
            "operational_stage": project.operational_stage,
            "stage_name": STAGE_NAMES.get(project.operational_stage, "Unknown Stage"),
            "owner_id": str(project.owner_id) if project.owner_id else None,
            "updated_at": project.updated_at.isoformat(),
        }
    }


@router.delete("/{project_id}", status_code=status.HTTP_200_OK)
async def delete_project(
    project_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Delete a film production project and cascade dependencies."""
    try:
        p_uuid = uuid.UUID(project_id)
        stmt = select(ProjectModel).where(ProjectModel.id == p_uuid)
    except ValueError:
        stmt = select(ProjectModel).where(ProjectModel.slug == project_id)

    result = await session.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await session.delete(project)
    await session.commit()
    return {"data": {"message": f"Project '{project.title}' deleted successfully."}}


@router.post("/{project_id}/advance-stage", status_code=status.HTTP_200_OK)
async def advance_project_stage(
    project_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Advance the project's operational stage by 1 step (up to Stage 16)."""
    try:
        p_uuid = uuid.UUID(project_id)
        stmt = select(ProjectModel).where(ProjectModel.id == p_uuid)
    except ValueError:
        stmt = select(ProjectModel).where(ProjectModel.slug == project_id)

    result = await session.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.operational_stage < 16:
        project.operational_stage += 1
        project.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(project)

    return {
        "data": {
            "id": str(project.id),
            "operational_stage": project.operational_stage,
            "stage_name": STAGE_NAMES.get(project.operational_stage, "Final Master Cut Delivery"),
            "status": project.status,
            "updated_at": project.updated_at.isoformat(),
        }
    }


@router.post("/{project_id}/gate", status_code=status.HTTP_200_OK)
async def process_stage_gate(
    project_id: str,
    payload: GateActionRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Execute Stage Approval Gate decision: APPROVE, REVISE, or LOCK."""
    try:
        p_uuid = uuid.UUID(project_id)
        stmt = select(ProjectModel).where(ProjectModel.id == p_uuid)
    except ValueError:
        stmt = select(ProjectModel).where(ProjectModel.slug == project_id)

    result = await session.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    action = payload.action.upper().strip()
    now = datetime.now(timezone.utc)

    # Initialize gate history in project settings
    settings = dict(project.settings or {})
    gate_history = settings.get("gate_history", [])

    entry = {
        "action": action,
        "stage": project.operational_stage,
        "notes": payload.notes,
        "decided_by_user_id": str(current_user.id),
        "decided_by_email": current_user.email,
        "timestamp": now.isoformat(),
    }

    if action == "APPROVE":
        if payload.target_stage and 1 <= payload.target_stage <= 16:
            project.operational_stage = payload.target_stage
        elif project.operational_stage < 16:
            project.operational_stage += 1
        project.status = "APPROVED" if project.operational_stage >= 16 else "IN_PRODUCTION"

    elif action == "REVISE":
        project.status = "REVISION"

    elif action == "LOCK":
        # Lock Bible if on Step 1-6
        bible_stmt = (
            select(MasterProductionBibleModel)
            .where(MasterProductionBibleModel.project_id == project.id)
            .order_by(MasterProductionBibleModel.version.desc())
            .limit(1)
        )
        bible = (await session.execute(bible_stmt)).scalar_one_or_none()
        if bible:
            bible.is_locked = True
            bible.locked_at = now
            bible.locked_by_user_id = current_user.id
            entry["bible_locked"] = True
        project.status = "LOCKED"

    else:
        raise HTTPException(status_code=400, detail="Invalid action. Must be APPROVE, REVISE, or LOCK.")

    gate_history.append(entry)
    settings["gate_history"] = gate_history
    project.settings = settings
    project.updated_at = now

    await session.commit()
    await session.refresh(project)

    return {
        "data": {
            "id": str(project.id),
            "operational_stage": project.operational_stage,
            "stage_name": STAGE_NAMES.get(project.operational_stage, "Unknown Stage"),
            "status": project.status,
            "latest_decision": entry,
            "updated_at": project.updated_at.isoformat(),
        }
    }
