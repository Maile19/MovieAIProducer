"""Backward-compatible facade for PolyaScreenwriterEngine.

Deprecated: Use `backend.app.domain.screenwriter.PolyaScreenwriterEngine` directly.
"""

from __future__ import annotations

from typing import Any

from backend.app.domain.screenwriter import (
    ActBlueprintData,
    ActTreatmentItem,
    MasterTreatmentData,
    PolyaScreenwriterEngine,
    SceneBlueprintItem,
    _determine_scene_duration,
    get_act_bounds,
)


class StagedStoryWriter(PolyaScreenwriterEngine):
    """Backward-compatible alias for PolyaScreenwriterEngine."""

    async def generate_treatment(
        self,
        title: str,
        total_scenes: int = 100,
        premise: str = "",
        characters: list[dict[str, Any]] | None = None,
        cold_open_30s: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Backward-compatible facade forwarding to generate_master_treatment."""
        return await self.generate_master_treatment(
            title=title,
            total_scenes=total_scenes,
            premise=premise,
            characters=characters,
            cold_open_30s=cold_open_30s,
        )


__all__ = [
    "StagedStoryWriter",
    "PolyaScreenwriterEngine",
    "get_act_bounds",
    "_determine_scene_duration",
    "SceneBlueprintItem",
    "ActBlueprintData",
    "ActTreatmentItem",
    "MasterTreatmentData",
]
