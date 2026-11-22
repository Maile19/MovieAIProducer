from datetime import datetime, timezone
import uuid

from sqlalchemy import Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.database.base import Base
from backend.app.infrastructure.database.types import GUID, UTCDateTime


class FlowAccountModel(Base):
    """Google Flow Automation Account Profile Registry (6-account pool)."""

    __tablename__ = "flow_accounts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=False,
    )
    label: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="Akun Pro",
    )
    profile_dir: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
    )  # active, busy, cooldown, need_relogin, disabled
    cooldown_until: Mapped[datetime | None] = mapped_column(
        UTCDateTime,
        nullable=True,
    )
    daily_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    last_reset_date: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )
    total_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime,
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class FlowImageJobModel(Base):
    """Google Flow Image Generation Queue and Execution Log."""

    __tablename__ = "flow_image_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        nullable=True,
    )
    scene_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        nullable=True,
    )
    character_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        nullable=True,
        index=True,
    )
    asset_slot: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    target_type: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    state_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        nullable=True,
    )
    prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    aspect_ratio: Mapped[str] = mapped_column(
        String(10),
        default="16:9",
        nullable=False,
    )  # 16:9, 9:16, 1:1
    reference_image_paths: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
    )
    preferred_account_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    assigned_account_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="queued",
        nullable=False,
    )  # queued, processing, completed, failed
    output_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    image_url: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    debug_screenshot_url: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime,
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime,
        nullable=True,
    )


class FlowSettingModel(Base):
    """Dynamic key-value settings for Google Flow worker."""

    __tablename__ = "flow_settings"

    key: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )
    value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
