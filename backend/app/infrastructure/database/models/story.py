from datetime import datetime, timezone
import uuid

from sqlalchemy import Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.database.base import Base
from backend.app.infrastructure.database.types import GUID, UTCDateTime


class SceneModel(Base):
    """50-Scene Storyboard blueprint node organized into 4 Acts."""

    __tablename__ = "scenes"

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
    act_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    scene_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    slugline: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    narrative_goal: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    duration_target: Mapped[float] = mapped_column(
        Float,
        default=5.0,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="PLANNED",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class ShotModel(Base):
    """Cinematographic shot with optical, lighting, and performance matrices."""

    __tablename__ = "shots"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    scene_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("scenes.id", ondelete="CASCADE"),
        nullable=False,
    )
    shot_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    duration_seconds: Mapped[float] = mapped_column(
        Float,
        default=5.0,
        nullable=False,
    )
    camera_code: Mapped[str] = mapped_column(
        String(16),
        default="#Cam 01",
        nullable=False,
    )
    lens_code: Mapped[str] = mapped_column(
        String(16),
        default="#Lens 01",
        nullable=False,
    )
    comp_code: Mapped[str] = mapped_column(
        String(16),
        default="#Comp 01",
        nullable=False,
    )
    light_code: Mapped[str] = mapped_column(
        String(16),
        default="#Light 01",
        nullable=False,
    )
    act_code: Mapped[str] = mapped_column(
        String(16),
        default="#Act 01",
        nullable=False,
    )
    speed_code: Mapped[str] = mapped_column(
        String(16),
        default="#Speed 01",
        nullable=False,
    )
    fg_bg_layers: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    dialogue: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    transition_type: Mapped[str] = mapped_column(
        String(16),
        default="NONE",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="PLANNED",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class DialogueCalibrationCacheModel(Base):
    """Cache for PolyaScreenwriterEngine dialogue calibration & pacing analysis."""

    __tablename__ = "dialogue_calibration_cache"

    cache_key: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    scene_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        nullable=True,
        index=True,
    )
    raw_text_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    max_seconds: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    result_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

