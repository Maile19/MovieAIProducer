import copy
from datetime import datetime, timezone
import re
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.app.api.deps import get_current_user, get_session
from backend.app.infrastructure.database.models.auth import ProjectMemberModel, UserModel
from backend.app.infrastructure.database.models.character import (
    CharacterModel,
    CharacterStateModel,
)
from backend.app.infrastructure.database.models.flow import FlowImageJobModel
from backend.app.infrastructure.database.models.preset import ProductionPresetModel
from backend.app.infrastructure.database.models.project import (
    MasterProductionBibleModel,
    ProjectModel,
)
from backend.app.infrastructure.database.models.story import SceneModel, ShotModel
from backend.app.services.pipeline_status import (
    apply_gate_signoff,
    compute_project_pipeline_status,
)

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
    preset_id: str | None = Field(default=None, description="Optional preset ID or slug to apply")


class ProjectUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    aspect_ratio: str | None = None
    target_style_code: str | None = None
    status: str | None = None
    settings: dict[str, Any] | None = None
    operational_stage: int | None = Field(default=None, ge=1, le=16)


class GateActionRequest(BaseModel):
    action: str = Field(description="Gate action: APPROVE, REVISE, or LOCK")
    notes: str = Field(default="", description="Director / Showrunner notes")
    target_stage: int | None = Field(default=None, description="Optional target stage")


class GateSignoffRequest(BaseModel):
    stage: int = Field(ge=1, le=16, description="Stage number 1 to 16")
    action: str = Field(description="APPROVE or REVOKE")
    notes: str = Field(default="", description="Director / Showrunner notes")


async def verify_project_access(
    project_id: str,
    current_user: UserModel,
    session: AsyncSession,
    require_manage: bool = False,
) -> ProjectModel:
    """Validate project existence and ensure current_user has read or manage access."""
    try:
        p_uuid = uuid.UUID(project_id)
        stmt = select(ProjectModel).where(ProjectModel.id == p_uuid)
    except ValueError:
        stmt = select(ProjectModel).where(ProjectModel.slug == project_id)

    result = await session.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Owner or SUPERADMIN has full access
    if project.owner_id == current_user.id or current_user.role == "SUPERADMIN":
        return project

    # Check project_members association
    member_stmt = select(ProjectMemberModel).where(
        (ProjectMemberModel.project_id == project.id) & (ProjectMemberModel.user_id == current_user.id)
    )
    member = (await session.execute(member_stmt)).scalar_one_or_none()
    if not member:
        # Hide existence from unauthorized users with 404
        raise HTTPException(status_code=404, detail="Project not found")

    if require_manage and member.role not in ("SHOWRUNNER", "OWNER", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to modify or delete this project.",
        )

    return project


@router.get("", status_code=status.HTTP_200_OK)
async def list_projects(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """List film projects accessible to the current user."""
    # Enforce strict user isolation: owner or member of the project
    member_subquery = select(ProjectMemberModel.project_id).where(
        ProjectMemberModel.user_id == current_user.id
    )
    user_filter = (ProjectModel.owner_id == current_user.id) | (ProjectModel.id.in_(member_subquery))

    stmt = select(ProjectModel).where(user_filter)
    count_stmt = select(func.count(ProjectModel.id)).where(user_filter)

    if search:
        search_filter = f"%{search.strip()}%"
        stmt = stmt.where(ProjectModel.title.ilike(search_filter))
        count_stmt = count_stmt.where(ProjectModel.title.ilike(search_filter))

    total_matching = (await session.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(ProjectModel.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    projects = result.scalars().all()

    # Calculate live pipeline metrics across all user projects (independent of search filter)
    metrics_stmt = select(
        func.count(ProjectModel.id).label("total"),
        func.sum(case((ProjectModel.operational_stage <= 5, 1), else_=0)).label("pre_prod"),
        func.sum(case((ProjectModel.operational_stage.between(6, 11), 1), else_=0)).label("prod"),
        func.sum(case((ProjectModel.operational_stage >= 12, 1), else_=0)).label("post"),
    ).where(user_filter)
    metrics_row = (await session.execute(metrics_stmt)).one()
    metrics = {
        "total": int(metrics_row[0] or 0),
        "pre_production": int(metrics_row[1] or 0),
        "generation": int(metrics_row[2] or 0),
        "post_master": int(metrics_row[3] or 0),
    }

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

    return {
        "data": data,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "count": len(data),
            "total": total_matching,
        },
        "metrics": metrics,
    }


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

    # Check and load preset if provided
    preset_data = {}
    preset_obj = None
    if payload.preset_id:
        try:
            p_uuid = uuid.UUID(payload.preset_id)
            preset_stmt = select(ProductionPresetModel).where(ProductionPresetModel.id == p_uuid)
        except ValueError:
            preset_stmt = select(ProductionPresetModel).where(ProductionPresetModel.slug == payload.preset_id)
        preset_obj = (await session.execute(preset_stmt)).scalar_one_or_none()
        if preset_obj:
            preset_data = preset_obj.preset_data or {}

    proj_defaults = preset_data.get("project_defaults", {})
    bible_blueprint = preset_data.get("bible_blueprint", {})

    final_aspect_ratio = payload.aspect_ratio
    if payload.aspect_ratio == "16:9" and "aspect_ratio" in proj_defaults:
        final_aspect_ratio = proj_defaults["aspect_ratio"]

    final_style_code = payload.target_style_code
    if payload.target_style_code == "#Style 01" and "target_style_code" in proj_defaults:
        final_style_code = proj_defaults["target_style_code"]

    final_settings = dict(payload.settings or {})
    if preset_obj:
        final_settings["preset_id"] = str(preset_obj.id)
        final_settings["preset_slug"] = preset_obj.slug
        final_settings["preset_name"] = preset_obj.name
        final_settings["preset_data"] = preset_data

    project = ProjectModel(
        id=project_id,
        title=payload.title,
        slug=final_slug,
        status="PLANNING",
        aspect_ratio=final_aspect_ratio,
        target_style_code=final_style_code,
        operational_stage=1,
        owner_id=current_user.id,
        settings=final_settings,
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

    # Initialize Master Production Bible with preset blueprint if present
    initial_styles = {
        "master_style_code": final_style_code,
        "render_pipeline": "Photorealistic 35mm Film Grain",
        "aspect_ratio": final_aspect_ratio,
    }
    if "style_parameters" in bible_blueprint:
        initial_styles.update(bible_blueprint["style_parameters"])

    initial_rules = {
        "gravity": "earth_standard",
        "atmosphere": "naturalistic",
    }
    if "world_rules" in bible_blueprint:
        initial_rules.update(bible_blueprint["world_rules"])

    bible = MasterProductionBibleModel(
        id=uuid.uuid4(),
        project_id=project_id,
        version=1,
        is_locked=False,
        locked_at=None,
        locked_by_user_id=None,
        style_parameters=initial_styles,
        world_rules=initial_rules,
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


async def derive_project_operational_stage(project: ProjectModel, session: AsyncSession) -> int:
    """Derive minimum operational stage based on existing project artifacts without mutating DB."""
    derived = 1
    # Check scenes (Stage 3: 4-Act Storyboard & 50-Scene Blueprint)
    scene_count_stmt = select(func.count(SceneModel.id)).where(SceneModel.project_id == project.id)
    scene_count = (await session.execute(scene_count_stmt)).scalar() or 0
    if scene_count > 0:
        derived = max(derived, 3)

    # Check characters (Stage 4: Character Profile & Voice DNA)
    char_count_stmt = select(func.count(CharacterModel.id)).where(CharacterModel.project_id == project.id)
    char_count = (await session.execute(char_count_stmt)).scalar() or 0
    if char_count > 0:
        derived = max(derived, 4)

        # Check character states (Stage 5: Dynamic Character Evolution Matrix)
        state_count_stmt = select(func.count(CharacterStateModel.id)).join(
            CharacterModel, CharacterStateModel.character_id == CharacterModel.id
        ).where(CharacterModel.project_id == project.id)
        state_count = (await session.execute(state_count_stmt)).scalar() or 0
        if state_count > 0:
            derived = max(derived, 5)

    # Check environments / props in MPB world_rules (Stage 6: Environment Bible & Hero Prop)
    mpb_stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == project.id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    mpb = (await session.execute(mpb_stmt)).scalar_one_or_none()
    if mpb and isinstance(mpb.world_rules, dict):
        envs = mpb.world_rules.get("environments", [])
        props = mpb.world_rules.get("props", [])
        if (isinstance(envs, list) and len(envs) > 0) or (isinstance(props, list) and len(props) > 0):
            derived = max(derived, 6)

    return derived


@router.get("/{project_id}", status_code=status.HTTP_200_OK)
async def get_project(
    project_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve full project details, stage metrics, bible summary, and dynamic pipeline status."""
    project = await verify_project_access(project_id, current_user, session, require_manage=False)

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

    # Dynamic pipeline status computation (Artifact-First guard & syncing operational_stage)
    pipeline_status = await compute_project_pipeline_status(project, session, sync_operational_stage=True)
    await session.commit()
    await session.refresh(project)

    current_working_stage = pipeline_status["header_metrics"]["current_working_stage"]

    return {
        "data": {
            "id": str(project.id),
            "title": project.title,
            "slug": project.slug,
            "status": project.status,
            "aspect_ratio": project.aspect_ratio,
            "target_style_code": project.target_style_code,
            "operational_stage": current_working_stage,
            "derived_stage": current_working_stage,
            "stage_name": STAGE_NAMES.get(current_working_stage, "Unknown Stage"),
            "owner_id": str(project.owner_id) if project.owner_id else None,
            "settings": project.settings,
            "pipeline_status": pipeline_status,
            "stats": {
                "scenes_count": scene_count,
                "bible_version": active_bible.version if active_bible else 1,
                "bible_locked": active_bible.is_locked if active_bible else False,
            },
            "created_at": project.created_at.isoformat(),
            "updated_at": project.updated_at.isoformat(),
        }
    }


@router.get("/{project_id}/pipeline-status", status_code=status.HTTP_200_OK)
async def get_project_pipeline_status(
    project_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve full dynamic pipeline control status (16 Stages & 12 Steps)."""
    project = await verify_project_access(project_id, current_user, session, require_manage=False)
    pipeline_status = await compute_project_pipeline_status(project, session, sync_operational_stage=True)
    await session.commit()
    return {"data": pipeline_status}


@router.post("/{project_id}/gate-signoff", status_code=status.HTTP_200_OK)
async def execute_gate_signoff(
    project_id: str,
    payload: GateSignoffRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Execute or revoke explicit human gate signoff for a stage."""
    project = await verify_project_access(project_id, current_user, session, require_manage=True)
    pipeline_status = await apply_gate_signoff(
        project=project,
        stage_num=payload.stage,
        action=payload.action,
        notes=payload.notes,
        user_email=current_user.email,
        user_id=current_user.id,
        session=session,
    )
    return {"data": pipeline_status}


@router.put("/{project_id}", status_code=status.HTTP_200_OK)
async def update_project(
    project_id: str,
    payload: ProjectUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Update project configuration parameters."""
    project = await verify_project_access(project_id, current_user, session, require_manage=True)

    if payload.title is not None:
        project.title = payload.title
    if payload.aspect_ratio is not None:
        project.aspect_ratio = payload.aspect_ratio
    if payload.target_style_code is not None:
        project.target_style_code = payload.target_style_code
    if payload.status is not None:
        project.status = payload.status
    if payload.operational_stage is not None:
        project.operational_stage = payload.operational_stage

    if payload.settings is not None:
        new_settings = copy.deepcopy(payload.settings)
        if "stage_manually_set" in new_settings:
            del new_settings["stage_manually_set"]
        project.settings = new_settings
        flag_modified(project, "settings")
    elif isinstance(project.settings, dict) and "stage_manually_set" in project.settings:
        updated_settings = copy.deepcopy(project.settings)
        del updated_settings["stage_manually_set"]
        project.settings = updated_settings
        flag_modified(project, "settings")

    project.updated_at = datetime.now(timezone.utc)
    pipeline_status = await compute_project_pipeline_status(
        project,
        session,
        sync_operational_stage=(payload.operational_stage is None),
    )
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
            "derived_stage": pipeline_status["header_metrics"]["current_working_stage"],
            "stage_name": STAGE_NAMES.get(project.operational_stage, "Unknown Stage"),
            "owner_id": str(project.owner_id) if project.owner_id else None,
            "pipeline_status": pipeline_status,
            "updated_at": project.updated_at.isoformat(),
        }
    }


@router.delete("/{project_id}", status_code=status.HTTP_200_OK)
async def delete_project(
    project_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Delete a film production project and cascade dependencies cleanly."""
    project = await verify_project_access(project_id, current_user, session, require_manage=True)

    # Clean unconstrained flow_image_jobs referencing this project before cascade
    await session.execute(
        delete(FlowImageJobModel).where(FlowImageJobModel.project_id == project.id)
    )

    proj_id_str = str(project.id)
    proj_title = project.title

    await session.delete(project)
    await session.commit()
    return {
        "data": {
            "id": proj_id_str,
            "title": proj_title,
            "message": f"Project '{proj_title}' deleted successfully.",
        }
    }


@router.post("/{project_id}/advance-stage", status_code=status.HTTP_200_OK)
async def advance_project_stage(
    project_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Advance the project's operational stage by 1 step (up to Stage 16)."""
    project = await verify_project_access(project_id, current_user, session, require_manage=True)

    if project.operational_stage < 16:
        project.operational_stage += 1
        curr_settings = copy.deepcopy(project.settings or {})
        if "stage_manually_set" in curr_settings:
            del curr_settings["stage_manually_set"]
        project.settings = curr_settings
        flag_modified(project, "settings")
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
    project = await verify_project_access(project_id, current_user, session, require_manage=True)

    action = payload.action.upper().strip()
    now = datetime.now(timezone.utc)

    # Initialize gate history and gate signoffs using deepcopy
    settings = copy.deepcopy(project.settings or {})
    gate_history = settings.get("gate_history", [])
    gate_signoffs = dict(settings.get("gate_signoffs", {}))

    stage_target = payload.target_stage if payload.target_stage else project.operational_stage

    entry = {
        "action": action,
        "stage": stage_target,
        "notes": payload.notes,
        "decided_by_user_id": str(current_user.id),
        "decided_by_email": current_user.email,
        "timestamp": now.isoformat(),
    }

    key = f"S{stage_target:02d}"

    if action == "APPROVE":
        gate_signoffs[key] = {
            "action": "APPROVE",
            "stage": stage_target,
            "notes": payload.notes,
            "signed_by": current_user.email,
            "signed_by_user_id": str(current_user.id),
            "timestamp": now.isoformat(),
        }
        if payload.target_stage and 1 <= payload.target_stage <= 16:
            project.operational_stage = payload.target_stage
        elif project.operational_stage < 16:
            project.operational_stage += 1
        project.status = "APPROVED" if project.operational_stage >= 16 else "IN_PRODUCTION"

    elif action == "REVISE":
        gate_signoffs[key] = {
            "action": "REVOKE",
            "stage": stage_target,
            "notes": payload.notes,
            "revoked_by": current_user.email,
            "revoked_by_user_id": str(current_user.id),
            "timestamp": now.isoformat(),
        }
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
    settings["gate_signoffs"] = gate_signoffs
    if "stage_manually_set" in settings:
        del settings["stage_manually_set"]
    project.settings = settings
    flag_modified(project, "settings")
    project.updated_at = now

    sync_stage = (payload.target_stage is None)
    pipeline_status = await compute_project_pipeline_status(project, session, sync_operational_stage=sync_stage)
    if sync_stage and action in ("APPROVE", "REVISE"):
        project.operational_stage = pipeline_status["header_metrics"]["current_working_stage"]
    await session.commit()
    await session.refresh(project)

    return {
        "data": {
            "id": str(project.id),
            "operational_stage": project.operational_stage,
            "stage_name": STAGE_NAMES.get(project.operational_stage, "Unknown Stage"),
            "status": project.status,
            "pipeline_status": pipeline_status,
            "latest_decision": entry,
            "updated_at": project.updated_at.isoformat(),
        }
    }
