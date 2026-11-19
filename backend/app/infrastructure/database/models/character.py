from datetime import datetime, timezone
import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.infrastructure.database.base import Base
from backend.app.infrastructure.database.types import GUID, UTCDateTime


class CharacterModel(Base):
    """Character identity, archetype, and facial/voice anchor asset references."""

    __tablename__ = "characters"

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
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    base_prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    face_ref_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    voice_ref_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class CharacterStateModel(Base):
    """Dynamic physical state, damage, and wardrobe continuity across scenes."""

    __tablename__ = "character_states"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    character_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("characters.id", ondelete="CASCADE"),
        nullable=False,
    )
    scene_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        ForeignKey("scenes.id", ondelete="SET NULL"),
        nullable=True,
    )
    state_code: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )
    wardrobe: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    injuries_and_wear: Mapped[str] = mapped_column(
        Text,
        default="",
        nullable=False,
    )
    expression_anchor: Mapped[str] = mapped_column(
        Text,
        default="",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
