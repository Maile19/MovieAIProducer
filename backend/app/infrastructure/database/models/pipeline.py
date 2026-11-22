from datetime import datetime, timezone
from decimal import Decimal
import uuid

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.database.base import Base
from backend.app.infrastructure.database.types import GUID, UTCDateTime


class AssetModel(Base):
    """Content-Addressable Storage (CAS) media registry."""

    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    shot_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        ForeignKey("shots.id", ondelete="SET NULL"),
        nullable=True,
    )
    asset_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    sha256_checksum: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    duration_seconds: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class PromptSpecificationModel(Base):
    """Compiled, engine-specific generative prompt configuration."""

    __tablename__ = "prompt_specifications"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    shot_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("shots.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    provider_target: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    positive_prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    negative_prompt: Mapped[str] = mapped_column(
        Text,
        default="",
        nullable=False,
    )
    compiled_nodes_json: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    seed: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class ProductionJobModel(Base):
    """Asynchronous video/audio generation job tracking."""

    __tablename__ = "production_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    shot_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("shots.id", ondelete="CASCADE"),
        nullable=False,
    )
    prompt_spec_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        ForeignKey("prompt_specifications.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    external_job_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="QUEUED",
        nullable=False,
    )
    progress_percent: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 4),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime,
        nullable=True,
    )


class QCReportModel(Base):
    """Automated visual and acoustic quality assessment scorecard."""

    __tablename__ = "qc_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    shot_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("shots.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    overall_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    face_similarity: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    clip_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    aesthetic_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    temporal_jitter: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    audio_snr_db: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    findings_json: Mapped[list | dict] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
