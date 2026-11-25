import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user, get_session
from backend.app.domain.catalog import STYLE_CATALOG
from backend.app.domain.director_rag import DirectorRAGClient
from backend.app.domain.look_dev import get_look_dev_presets
from backend.app.infrastructure.database.models.auth import ProjectMemberModel, UserModel
from backend.app.infrastructure.database.models.project import (
    MasterProductionBibleModel,
    ProjectModel,
)

router = APIRouter(tags=["Look-Dev"])

_VALID_STYLE_CODES = {item["code"] for item in STYLE_CATALOG}


async def _load_project(
    project_id: str,
    current_user: UserModel,
    session: AsyncSession,
) -> ProjectModel:
    try:
        p_uuid = uuid.UUID(project_id)
        stmt = select(ProjectModel).where(ProjectModel.id == p_uuid)
    except ValueError:
        stmt = select(ProjectModel).where(ProjectModel.slug == project_id)

    project = (await session.execute(stmt)).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.owner_id == current_user.id or current_user.role == "SUPERADMIN":
        return project

    member = (
        await session.execute(
            select(ProjectMemberModel).where(
                (ProjectMemberModel.project_id == project.id)
                & (ProjectMemberModel.user_id == current_user.id)
            )
        )
    ).scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=403, detail="Not authorized for this project")
    return project


async def _resolve_style_code(
    project: ProjectModel,
    style_code: str | None,
    session: AsyncSession,
) -> str:
    if style_code:
        code = style_code.strip()
        if code not in _VALID_STYLE_CODES:
            raise HTTPException(status_code=400, detail=f"Unknown style_code: {style_code}")
        return code

    mpb = (
        await session.execute(
            select(MasterProductionBibleModel)
            .where(MasterProductionBibleModel.project_id == project.id)
            .order_by(MasterProductionBibleModel.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if mpb and isinstance(mpb.style_parameters, dict):
        master = mpb.style_parameters.get("master_style_code")
        if master in _VALID_STYLE_CODES:
            return master
    if project.target_style_code in _VALID_STYLE_CODES:
        return project.target_style_code
    return "#Style 01"


async def _fetch_look_dev_rag_cues(style_code: str, style_label: str) -> str:
    """Best-effort Director RAG cues; 1.5s timeout and empty fallback are enforced client-side."""
    try:
        rag_res = await DirectorRAGClient.retrieve(
            scene_beat=f"{style_code} {style_label} look-dev palette and lighting grammar",
            style_code=style_code,
            engine="flux",
            top_k=2,
        )
        cues_text, _ = DirectorRAGClient.format_transpile_cues(rag_res, max_shots=2)
        return (cues_text or "")[:240].strip()
    except Exception:
        return ""


@router.get("/projects/{project_id}/bible/look-dev-presets", status_code=status.HTTP_200_OK)
async def get_look_dev_presets_endpoint(
    project_id: str,
    style_code: str | None = Query(default=None),
    include_rag_cues: bool = Query(default=True),
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Return the 3 curated Look-Dev presets for the project's style (54 presets across 18 styles)."""
    project = await _load_project(project_id, current_user, session)
    resolved_style = await _resolve_style_code(project, style_code, session)
    presets = get_look_dev_presets(resolved_style)

    style_label = next(
        (item.get("name", "") for item in STYLE_CATALOG if item["code"] == resolved_style),
        "",
    )
    rag_cues = (
        await _fetch_look_dev_rag_cues(resolved_style, style_label)
        if include_rag_cues
        else ""
    )
    for preset in presets:
        preset["director_rag_cues"] = rag_cues

    return {
        "status": "success",
        "project_id": str(project.id),
        "style_code": resolved_style,
        "style_label": style_label,
        "director_rag_cues": rag_cues,
        "count": len(presets),
        "data": presets,
    }
