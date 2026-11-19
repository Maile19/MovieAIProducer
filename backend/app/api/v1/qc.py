from datetime import datetime, timezone
from typing import Any
import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_session
from backend.app.domain.qc import QCEvaluationEngine
from backend.app.infrastructure.database.models.pipeline import QCReportModel

router = APIRouter(prefix="/qc", tags=["Quality Control"])


class QCEvaluateRequest(BaseModel):
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


@router.post("/evaluate", status_code=status.HTTP_200_OK)
async def evaluate_qc(
    payload: QCEvaluateRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Execute automated QC evaluation scorecard against cinematic thresholds."""
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
