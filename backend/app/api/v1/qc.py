from datetime import datetime, timezone
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user, get_session
from backend.app.domain.qc import QCEvaluationEngine
from backend.app.infrastructure.database.models.auth import UserModel
from backend.app.infrastructure.database.models.character import CharacterModel, CharacterStateModel
from backend.app.infrastructure.database.models.pipeline import QCReportModel
from backend.app.infrastructure.database.models.project import MasterProductionBibleModel, ProjectModel
from backend.app.infrastructure.database.models.story import SceneModel, ShotModel

router = APIRouter(tags=["Quality Control"])


class QCEvaluateRequest(BaseModel):
    scene_id: str | None = Field(default=None, description="Optional scene UUID for real DB-backed audit")
    shot_id: str | None = Field(default=None, description="Target shot UUID")
    asset_id: str | None = Field(default=None, description="Evaluated asset UUID")
    face_similarity: float | None = Field(
        default=0.88,
        ge=0.0,
        le=1.0,
        description="InsightFace similarity (0.0 - 1.0)",
    )
    clip_score: float | None = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="CLIP semantic alignment score (0.0 - 1.0)",
    )
    aesthetic_score: float | None = Field(
        default=8.5,
        ge=1.0,
        le=10.0,
        description="LAION aesthetic predictor score (1.0 - 10.0)",
    )
    temporal_jitter: float | None = Field(
        default=0.08,
        ge=0.0,
        description="Optical flow temporal jitter variance",
    )
    audio_snr_db: float | None = Field(
        default=32.0,
        description="Audio Signal-to-Noise Ratio (dB)",
    )


async def _load_project_qc_context(project_id: uuid.UUID, session: AsyncSession) -> tuple[Any, Any, list[Any], dict[Any, list[Any]]]:
    project = (await session.execute(select(ProjectModel).where(ProjectModel.id == project_id))).scalar_one_or_none()
    bible = (
        await session.execute(
            select(MasterProductionBibleModel)
            .where(MasterProductionBibleModel.project_id == project_id)
            .order_by(MasterProductionBibleModel.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    chars = list(
        (
            await session.execute(
                select(CharacterModel).where(CharacterModel.project_id == project_id).order_by(CharacterModel.created_at.asc())
            )
        ).scalars().all()
    )
    char_ids = [c.id for c in chars]
    states_by_char: dict[Any, list[Any]] = {}
    if char_ids:
        all_states = (
            await session.execute(
                select(CharacterStateModel)
                .where(CharacterStateModel.character_id.in_(char_ids))
                .order_by(CharacterStateModel.state_code.asc())
            )
        ).scalars().all()
        for st in all_states:
            states_by_char.setdefault(st.character_id, []).append(st)
    return project, bible, chars, states_by_char


async def _execute_scene_audit(scene_id: str, session: AsyncSession) -> dict[str, Any]:
    try:
        s_uuid = uuid.UUID(scene_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid scene UUID")

    scene = (await session.execute(select(SceneModel).where(SceneModel.id == s_uuid))).scalar_one_or_none()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    shots = list(
        (
            await session.execute(
                select(ShotModel).where(ShotModel.scene_id == scene.id).order_by(ShotModel.shot_number.asc())
            )
        ).scalars().all()
    )
    project, bible, chars, states_by_char = await _load_project_qc_context(scene.project_id, session)

    total_acts = 4
    if project and isinstance(project.settings, dict):
        tr = project.settings.get("treatment") or {}
        if isinstance(tr.get("acts"), list) and tr["acts"]:
            total_acts = len(tr["acts"])
        elif tr.get("structure_type") == "3_act":
            total_acts = 3
        elif tr.get("structure_type") == "5_act":
            total_acts = 5

    return QCEvaluationEngine.audit_scene(
        scene=scene,
        shots=shots,
        characters=chars,
        states_by_char=states_by_char,
        project=project,
        bible=bible,
        total_acts=total_acts,
    )


@router.post("/qc/audit-scene/{scene_id}", status_code=status.HTTP_200_OK)
async def audit_scene_qc(
    scene_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Execute deterministic narrative, continuity, optical, and asset-readiness QC audit for a scene."""
    audit_result = await _execute_scene_audit(scene_id, session)
    return {"data": audit_result}


@router.get("/projects/{project_id}/qc/summary", status_code=status.HTTP_200_OK)
async def get_project_qc_summary(
    project_id: str,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Compute real project-wide QC Continuum aggregate score and top continuity gaps."""
    try:
        p_uuid = uuid.UUID(project_id)
        project = (await session.execute(select(ProjectModel).where(ProjectModel.id == p_uuid))).scalar_one_or_none()
    except ValueError:
        project = (await session.execute(select(ProjectModel).where(ProjectModel.slug == project_id))).scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    _, bible, chars, states_by_char = await _load_project_qc_context(project.id, session)
    scenes = list(
        (
            await session.execute(
                select(SceneModel)
                .where(SceneModel.project_id == project.id)
                .order_by(SceneModel.act_number.asc(), SceneModel.scene_number.asc())
            )
        ).scalars().all()
    )
    shots_by_scene: dict[Any, list[Any]] = {}
    if scenes:
        scene_ids = [s.id for s in scenes]
        all_shots = (
            await session.execute(
                select(ShotModel).where(ShotModel.scene_id.in_(scene_ids)).order_by(ShotModel.shot_number.asc())
            )
        ).scalars().all()
        for sh in all_shots:
            shots_by_scene.setdefault(sh.scene_id, []).append(sh)

    summary = QCEvaluationEngine.summarize_project_qc(
        project_id=str(project.id),
        scenes=scenes,
        shots_by_scene=shots_by_scene,
        characters=chars,
        states_by_char=states_by_char,
        project=project,
        bible=bible,
    )
    return {"data": summary}


@router.post("/qc/evaluate", status_code=status.HTTP_200_OK)
async def evaluate_qc(
    payload: QCEvaluateRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Execute automated QC evaluation scorecard against cinematic thresholds (or scene audit when scene_id supplied without numeric overrides)."""
    explicit_numeric = bool(
        payload.model_fields_set
        & {"face_similarity", "clip_score", "aesthetic_score", "temporal_jitter", "audio_snr_db"}
    )
    if payload.scene_id and not explicit_numeric:
        return {"data": await _execute_scene_audit(payload.scene_id, session)}

    result = QCEvaluationEngine.evaluate(
        face_similarity=payload.face_similarity,
        clip_score=payload.clip_score,
        aesthetic_score=payload.aesthetic_score,
        temporal_jitter=payload.temporal_jitter,
        audio_snr_db=payload.audio_snr_db,
    )

    shot_uuid: uuid.UUID | None = None
    if payload.shot_id:
        try:
            shot_uuid = uuid.UUID(payload.shot_id)
        except ValueError:
            shot_uuid = None

    asset_uuid: uuid.UUID | None = None
    if payload.asset_id:
        try:
            asset_uuid = uuid.UUID(payload.asset_id)
        except ValueError:
            asset_uuid = None

    # Save to database if shot_id is provided
    if shot_uuid:
        qc_record = QCReportModel(
            id=uuid.uuid4(),
            shot_id=shot_uuid,
            asset_id=asset_uuid,
            overall_score=result["overall_score"],
            passed=result["passed"],
            face_similarity=payload.face_similarity,
            clip_score=payload.clip_score,
            aesthetic_score=payload.aesthetic_score,
            temporal_jitter=payload.temporal_jitter,
            audio_snr_db=payload.audio_snr_db,
            findings_json=result["findings_json"],
            created_at=datetime.now(timezone.utc),
        )
        session.add(qc_record)
        try:
            await session.commit()
            await session.refresh(qc_record)
            result["report_id"] = str(qc_record.id)
        except Exception:
            await session.rollback()

    return {"data": result}
