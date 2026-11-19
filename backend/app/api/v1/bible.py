from datetime import datetime, timezone
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user, get_session
from backend.app.infrastructure.database.models.auth import UserModel
from backend.app.infrastructure.database.models.character import (
    CharacterModel,
    CharacterStateModel,
)
from backend.app.infrastructure.database.models.project import (
    MasterProductionBibleModel,
    ProjectModel,
)

router = APIRouter(tags=["Master Production Bible"])


class BibleUpdateRequest(BaseModel):
    style_parameters: dict[str, Any] | None = None
    world_rules: dict[str, Any] | None = None


class BibleLockRequest(BaseModel):
    approval_notes: str = Field(default="Showrunner DNA freeze approval", description="Lock justification")
    confirm_dna_freeze: bool = Field(default=True, description="Explicit confirmation of DNA immutability")


class CharacterCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    role: str = Field(default="PROTAGONIST", description="PROTAGONIST, ANTAGONIST, DEUTERAGONIST, MENTOR, EXTRAS")
    base_prompt: str = Field(description="Base visual and physical prompt description")
    face_ref_asset_id: str | None = None
    voice_ref_asset_id: str | None = None


class CharacterStateCreateRequest(BaseModel):
    scene_id: str | None = None
    state_code: str = Field(default="#State 01", description="#State 01 to #State 05")
    wardrobe: str = Field(description="Costume and attire description")
    injuries_and_wear: str = Field(default="", description="Persistent physical damage, dirt, blood")
    expression_anchor: str = Field(default="", description="Default emotional anchor")


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


@router.get("/projects/{project_id}/bible", status_code=status.HTTP_200_OK)
async def get_project_bible(
    project_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve active Master Production Bible for the project."""
    project = await _resolve_project(project_id, session)

    stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == project.id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    bible = (await session.execute(stmt)).scalar_one_or_none()

    if not bible:
        # Auto-create baseline version 1 if missing
        now = datetime.now(timezone.utc)
        bible = MasterProductionBibleModel(
            id=uuid.uuid4(),
            project_id=project.id,
            version=1,
            is_locked=False,
            style_parameters={"master_style_code": project.target_style_code},
            world_rules={},
            created_at=now,
            updated_at=now,
        )
        session.add(bible)
        await session.commit()
        await session.refresh(bible)

    return {
        "data": {
            "id": str(bible.id),
            "project_id": str(project.id),
            "version": bible.version,
            "is_locked": bible.is_locked,
            "locked_at": bible.locked_at.isoformat() if bible.locked_at else None,
            "locked_by_user_id": str(bible.locked_by_user_id) if bible.locked_by_user_id else None,
            "style_parameters": bible.style_parameters,
            "world_rules": bible.world_rules,
            "created_at": bible.created_at.isoformat(),
            "updated_at": bible.updated_at.isoformat(),
        }
    }


@router.put("/projects/{project_id}/bible", status_code=status.HTTP_200_OK)
async def update_project_bible(
    project_id: str,
    payload: BibleUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Update active MPB parameters. Fails if Bible is locked."""
    project = await _resolve_project(project_id, session)

    stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == project.id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    bible = (await session.execute(stmt)).scalar_one_or_none()
    if not bible:
        raise HTTPException(status_code=404, detail="Bible not found")

    if bible.is_locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Master Production Bible is locked. DNA freeze is active; create a new version to modify.",
        )

    if payload.style_parameters is not None:
        bible.style_parameters = payload.style_parameters
    if payload.world_rules is not None:
        bible.world_rules = payload.world_rules

    bible.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(bible)

    return {
        "data": {
            "id": str(bible.id),
            "project_id": str(project.id),
            "version": bible.version,
            "is_locked": bible.is_locked,
            "style_parameters": bible.style_parameters,
            "world_rules": bible.world_rules,
            "updated_at": bible.updated_at.isoformat(),
        }
    }


@router.post("/projects/{project_id}/bible/lock", status_code=status.HTTP_200_OK)
async def lock_project_bible(
    project_id: str,
    payload: BibleLockRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Freeze Master Production Bible version into immutable baseline."""
    project = await _resolve_project(project_id, session)

    stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == project.id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    bible = (await session.execute(stmt)).scalar_one_or_none()
    if not bible:
        raise HTTPException(status_code=404, detail="Bible not found")

    now = datetime.now(timezone.utc)
    bible.is_locked = True
    bible.locked_at = now
    bible.locked_by_user_id = current_user.id
    bible.updated_at = now

    await session.commit()
    await session.refresh(bible)

    return {
        "data": {
            "id": str(bible.id),
            "project_id": str(project.id),
            "version": bible.version,
            "is_locked": bible.is_locked,
            "locked_at": bible.locked_at.isoformat() if bible.locked_at else None,
            "locked_by_user_id": str(bible.locked_by_user_id) if bible.locked_by_user_id else None,
            "approval_notes": payload.approval_notes,
            "message": "Master Production Bible DNA locked successfully.",
        }
    }


# Character & State Management endpoints


@router.get("/projects/{project_id}/characters", status_code=status.HTTP_200_OK)
async def list_characters(
    project_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """List characters and their registered states for the project."""
    project = await _resolve_project(project_id, session)

    stmt = select(CharacterModel).where(CharacterModel.project_id == project.id).order_by(CharacterModel.created_at.asc())
    characters = (await session.execute(stmt)).scalars().all()

    data = []
    for c in characters:
        state_stmt = select(CharacterStateModel).where(CharacterStateModel.character_id == c.id).order_by(CharacterStateModel.state_code.asc())
        states = (await session.execute(state_stmt)).scalars().all()
        data.append(
            {
                "id": str(c.id),
                "name": c.name,
                "role": c.role,
                "base_prompt": c.base_prompt,
                "face_ref_asset_id": str(c.face_ref_asset_id) if c.face_ref_asset_id else None,
                "voice_ref_asset_id": str(c.voice_ref_asset_id) if c.voice_ref_asset_id else None,
                "states": [
                    {
                        "id": str(s.id),
                        "state_code": s.state_code,
                        "wardrobe": s.wardrobe,
                        "injuries_and_wear": s.injuries_and_wear,
                        "expression_anchor": s.expression_anchor,
                        "scene_id": str(s.scene_id) if s.scene_id else None,
                    }
                    for s in states
                ],
                "created_at": c.created_at.isoformat(),
            }
        )

    return {"data": data}


@router.post("/projects/{project_id}/characters", status_code=status.HTTP_201_CREATED)
async def create_character(
    project_id: str,
    payload: CharacterCreateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Register a new character identity."""
    project = await _resolve_project(project_id, session)

    char_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    face_id = uuid.UUID(payload.face_ref_asset_id) if payload.face_ref_asset_id else None
    voice_id = uuid.UUID(payload.voice_ref_asset_id) if payload.voice_ref_asset_id else None

    char = CharacterModel(
        id=char_id,
        project_id=project.id,
        name=payload.name,
        role=payload.role,
        base_prompt=payload.base_prompt,
        face_ref_asset_id=face_id,
        voice_ref_asset_id=voice_id,
        created_at=now,
    )
    session.add(char)
    await session.commit()
    await session.refresh(char)

    return {
        "data": {
            "id": str(char.id),
            "name": char.name,
            "role": char.role,
            "base_prompt": char.base_prompt,
            "created_at": char.created_at.isoformat(),
        }
    }


@router.post("/characters/{character_id}/states", status_code=status.HTTP_201_CREATED)
async def create_character_state(
    character_id: str,
    payload: CharacterStateCreateRequest,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Register dynamic state evolution (#State 01-05) for character."""
    c_uuid = uuid.UUID(character_id)
    char_stmt = select(CharacterModel).where(CharacterModel.id == c_uuid)
    char = (await session.execute(char_stmt)).scalar_one_or_none()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    scene_uuid = uuid.UUID(payload.scene_id) if payload.scene_id else None
    state_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    state = CharacterStateModel(
        id=state_id,
        character_id=char.id,
        scene_id=scene_uuid,
        state_code=payload.state_code,
        wardrobe=payload.wardrobe,
        injuries_and_wear=payload.injuries_and_wear,
        expression_anchor=payload.expression_anchor,
        created_at=now,
    )
    session.add(state)
    await session.commit()
    await session.refresh(state)

    return {
        "data": {
            "id": str(state.id),
            "character_id": str(char.id),
            "state_code": state.state_code,
            "wardrobe": state.wardrobe,
            "injuries_and_wear": state.injuries_and_wear,
            "expression_anchor": state.expression_anchor,
            "scene_id": str(state.scene_id) if state.scene_id else None,
            "created_at": state.created_at.isoformat(),
        }
    }
