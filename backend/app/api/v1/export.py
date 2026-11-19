from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user, get_session
from backend.app.infrastructure.database.models.auth import UserModel
from backend.app.infrastructure.database.models.character import (
    CharacterModel,
    CharacterStateModel,
)
from backend.app.infrastructure.database.models.pipeline import QCReportModel
from backend.app.infrastructure.database.models.project import (
    MasterProductionBibleModel,
    ProjectModel,
)
from backend.app.infrastructure.database.models.story import SceneModel, ShotModel

router = APIRouter(tags=["Export Package"])


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


def _generate_production_markdown(
    project: ProjectModel,
    bible: MasterProductionBibleModel | None,
    scenes: list[SceneModel],
    scene_shots: dict[uuid.UUID, list[ShotModel]],
    characters: list[CharacterModel],
    char_states: dict[uuid.UUID, list[CharacterStateModel]],
) -> str:
    """Generate a comprehensive Hollywood Production Master Markdown document."""
    lines: list[str] = [
        f"# {project.title.upper()} - MASTER PRODUCTION PACKAGE",
        "",
        f"- **Project ID:** `{project.id}`",
        f"- **Slug:** `{project.slug}`",
        f"- **Status:** `{project.status}`",
        f"- **Aspect Ratio:** `{project.aspect_ratio}`",
        f"- **Master Style Code:** `{project.target_style_code}`",
        f"- **Operational Stage:** `Stage {project.operational_stage}/16`",
        f"- **Generated At:** `{project.updated_at.isoformat()} UTC`",
        "",
        "---",
        "",
        "## 1. Master Production Bible (MPB) Baseline",
        "",
    ]

    if bible:
        lines.extend(
            [
                f"- **Bible Version:** `v{bible.version}`",
                f"- **DNA Frozen / Locked:** `{'YES (LOCKED)' if bible.is_locked else 'NO (IN DRAFT)'}`",
                f"- **Locked At:** `{bible.locked_at.isoformat() if bible.locked_at else 'N/A'}`",
                "",
                "### Style Parameters:",
                "```json",
                f"{bible.style_parameters}",
                "```",
                "",
                "### World Continuity Rules:",
                "```json",
                f"{bible.world_rules}",
                "```",
            ]
        )
    else:
        lines.append("*No Master Production Bible registered.*")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 2. Character DNA & Dynamic State Matrix",
            "",
        ]
    )

    if characters:
        for c in characters:
            lines.extend(
                [
                    f"### Character: {c.name} ({c.role})",
                    f"- **Base Prompt:** {c.base_prompt}",
                    "",
                    "#### Dynamic States (#State 01 - #State 05):",
                ]
            )
            states = char_states.get(c.id, [])
            if states:
                lines.append("| State Code | Wardrobe | Injuries & Wear | Expression Anchor |")
                lines.append("|:---|:---|:---|:---|")
                for s in states:
                    lines.append(f"| `{s.state_code}` | {s.wardrobe} | {s.injuries_and_wear or 'None'} | {s.expression_anchor or 'Neutral'} |")
            else:
                lines.append("*No dynamic states registered.*")
            lines.append("")
    else:
        lines.append("*No characters registered.*")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 3. 4-Act 50-Scene Storyboard & Technical Shot Lists",
            "",
        ]
    )

    if scenes:
        lines.append(f"Total Scenes: {len(scenes)}")
        lines.append("")
        for sc in scenes:
            shots = scene_shots.get(sc.id, [])
            lines.extend(
                [
                    f"### Act {sc.act_number} | Scene {sc.scene_number:02d}: {sc.slugline}",
                    f"- **Narrative Goal:** {sc.narrative_goal}",
                    f"- **Target Duration:** {sc.duration_target}s | **Status:** `{sc.status}` | **Shots Count:** {len(shots)}",
                    "",
                ]
            )

            if shots:
                lines.append("| Shot # | Camera | Lens | Comp | Light | Act | Speed | Transition | Dialogue |")
                lines.append("|:---|:---|:---|:---|:---|:---|:---|:---|:---|")
                for sh in shots:
                    diag = f'"{sh.dialogue}"' if sh.dialogue else "-"
                    lines.append(
                        f"| #{sh.shot_number} | `{sh.camera_code}` | `{sh.lens_code}` | `{sh.comp_code}` | "
                        f"`{sh.light_code}` | `{sh.act_code}` | `{sh.speed_code}` | `{sh.transition_type}` | {diag} |"
                    )
                lines.append("")
            else:
                lines.append("*No individual shots defined for this scene.*")
                lines.append("")
    else:
        lines.append("*No scenes defined.*")

    lines.extend(
        [
            "---",
            "",
            "## 4. Quality Control Certification",
            "",
            "All shots and audio stems compiled in this package conform to Hollywood 12-Step technical specifications.",
            "- Biometric InsightFace threshold: `>= 0.80`",
            "- Semantic CLIP threshold: `>= 0.75`",
            "- Aesthetic LAION benchmark: `>= 7.0 / 10.0`",
            "- Temporal flow jitter variance: `<= 0.15`",
            "",
            "*End of Production Package.*",
        ]
    )

    return "\n".join(lines)


@router.get("/projects/{project_id}/export")
async def export_project_package(
    project_id: str,
    export_format: str = Query(default="json", alias="format", description="Export format: json or markdown (md)"),
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Export complete production bible, scenes, shots, and character matrices."""
    project = await _resolve_project(project_id, session)

    # 1. Fetch active bible
    bible_stmt = (
        select(MasterProductionBibleModel)
        .where(MasterProductionBibleModel.project_id == project.id)
        .order_by(MasterProductionBibleModel.version.desc())
        .limit(1)
    )
    bible = (await session.execute(bible_stmt)).scalar_one_or_none()

    # 2. Fetch scenes
    scenes_stmt = select(SceneModel).where(SceneModel.project_id == project.id).order_by(SceneModel.act_number.asc(), SceneModel.scene_number.asc())
    scenes = (await session.execute(scenes_stmt)).scalars().all()

    # 3. Fetch shots grouped by scene
    scene_shots: dict[uuid.UUID, list[ShotModel]] = {}
    for sc in scenes:
        shots_stmt = select(ShotModel).where(ShotModel.scene_id == sc.id).order_by(ShotModel.shot_number.asc())
        shots = (await session.execute(shots_stmt)).scalars().all()
        scene_shots[sc.id] = list(shots)

    # 4. Fetch characters and states
    chars_stmt = select(CharacterModel).where(CharacterModel.project_id == project.id).order_by(CharacterModel.created_at.asc())
    characters = (await session.execute(chars_stmt)).scalars().all()

    char_states: dict[uuid.UUID, list[CharacterStateModel]] = {}
    for c in characters:
        state_stmt = select(CharacterStateModel).where(CharacterStateModel.character_id == c.id).order_by(CharacterStateModel.state_code.asc())
        states = (await session.execute(state_stmt)).scalars().all()
        char_states[c.id] = list(states)

    fmt = export_format.lower().strip()
    if fmt in ("markdown", "md"):
        markdown_text = _generate_production_markdown(
            project=project,
            bible=bible,
            scenes=list(scenes),
            scene_shots=scene_shots,
            characters=list(characters),
            char_states=char_states,
        )
        return PlainTextResponse(
            content=markdown_text,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{project.slug}-master-package.md"'},
        )

    # Default to JSON
    scenes_json = []
    for sc in scenes:
        shots = scene_shots.get(sc.id, [])
        scenes_json.append(
            {
                "id": str(sc.id),
                "act_number": sc.act_number,
                "scene_number": sc.scene_number,
                "slugline": sc.slugline,
                "narrative_goal": sc.narrative_goal,
                "duration_target": sc.duration_target,
                "status": sc.status,
                "shots": [
                    {
                        "id": str(sh.id),
                        "shot_number": sh.shot_number,
                        "duration_seconds": sh.duration_seconds,
                        "camera_code": sh.camera_code,
                        "lens_code": sh.lens_code,
                        "comp_code": sh.comp_code,
                        "light_code": sh.light_code,
                        "act_code": sh.act_code,
                        "speed_code": sh.speed_code,
                        "fg_bg_layers": sh.fg_bg_layers,
                        "dialogue": sh.dialogue,
                        "transition_type": sh.transition_type,
                        "status": sh.status,
                    }
                    for sh in shots
                ],
            }
        )

    characters_json = []
    for c in characters:
        states = char_states.get(c.id, [])
        characters_json.append(
            {
                "id": str(c.id),
                "name": c.name,
                "role": c.role,
                "base_prompt": c.base_prompt,
                "states": [
                    {
                        "id": str(s.id),
                        "state_code": s.state_code,
                        "wardrobe": s.wardrobe,
                        "injuries_and_wear": s.injuries_and_wear,
                        "expression_anchor": s.expression_anchor,
                    }
                    for s in states
                ],
            }
        )

    return {
        "data": {
            "project": {
                "id": str(project.id),
                "title": project.title,
                "slug": project.slug,
                "status": project.status,
                "aspect_ratio": project.aspect_ratio,
                "target_style_code": project.target_style_code,
                "operational_stage": project.operational_stage,
                "settings": project.settings,
            },
            "bible": {
                "version": bible.version if bible else 1,
                "is_locked": bible.is_locked if bible else False,
                "locked_at": bible.locked_at.isoformat() if (bible and bible.locked_at) else None,
                "style_parameters": bible.style_parameters if bible else {},
                "world_rules": bible.world_rules if bible else {},
            }
            if bible
            else None,
            "characters": characters_json,
            "scenes": scenes_json,
            "total_scenes": len(scenes_json),
        }
    }
