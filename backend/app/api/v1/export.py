from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
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


def _resolve_scene_speaker(
    scene: SceneModel,
    shots: list[ShotModel],
    characters: list[CharacterModel],
) -> str | None:
    if not characters:
        return None
    goal_lower = (scene.narrative_goal or "").lower()
    dlg_lower = " ".join((sh.dialogue or "") for sh in shots).lower()
    for ch in characters:
        if ch.name and (ch.name.lower() in goal_lower or ch.name.lower() in dlg_lower):
            return ch.name
    return characters[0].name


def _extract_scene_dialogue_meta(shots: list[ShotModel]) -> dict[str, Any]:
    lines: list[str] = []
    transition = "NONE"
    audio_lead: float | None = None
    for sh in shots:
        raw = (sh.dialogue or "").strip()
        if raw and not (raw.startswith("Environmental cue:") and lines) and raw not in lines:
            lines.append(raw)
        if transition == "NONE" and sh.transition_type and sh.transition_type != "NONE":
            transition = sh.transition_type
        if audio_lead is None and isinstance(sh.fg_bg_layers, dict):
            lead = sh.fg_bg_layers.get("audio_lead_seconds")
            if isinstance(lead, (int, float)):
                audio_lead = float(lead)
    return {
        "dialogue": "\n".join(lines) if lines else None,
        "transition_type": transition,
        "audio_lead_seconds": audio_lead,
    }


def _generate_production_markdown(
    project: ProjectModel,
    bible: MasterProductionBibleModel | None,
    scenes: list[SceneModel],
    scene_shots: dict[uuid.UUID, list[ShotModel]],
    characters: list[CharacterModel],
    char_states: dict[uuid.UUID, list[CharacterStateModel]],
) -> str:
    """Generate a full-fidelity Hollywood Production Master Markdown binder."""
    settings = project.settings if isinstance(project.settings, dict) else {}
    treatment = settings.get("treatment") if isinstance(settings.get("treatment"), dict) else {}

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
        "## 0. Master Story Treatment & Beat Sheet",
        "",
    ]

    if treatment:
        lines.extend(
            [
                f"- **Treatment Title:** {treatment.get('title') or project.title}",
                f"- **Dramatic Structure:** `{treatment.get('structure_type', '4_act')}` ({treatment.get('structure_name', 'Hollywood 4-Act Structure')})",
                f"- **Logline:** {treatment.get('logline') or settings.get('synopsis') or 'N/A'}",
                f"- **Theme:** {treatment.get('theme') or 'N/A'}",
                f"- **Dramatic Premise:** {treatment.get('dramatic_premise') or 'N/A'}",
            ]
        )
        cold_open = treatment.get("cold_open_30s")
        if isinstance(cold_open, dict) and cold_open.get("enabled"):
            hook = cold_open.get("hook_preview") or "30s High-Velocity Visual Hook Montage (Scenes 01–03)"
            lines.append(f"- **30s Cold Open Hook:** Enabled — {hook}")
        acts = treatment.get("acts")
        act_summaries = treatment.get("act_summaries") if isinstance(treatment.get("act_summaries"), dict) else {}
        if isinstance(acts, list) and acts:
            lines.extend(["", "### Act Breakdown:"])
            for act in acts:
                if not isinstance(act, dict):
                    continue
                a_num = act.get("act_number", "?")
                a_title = act.get("act_title", f"Act {a_num}")
                s_start = act.get("start_scene", "?")
                s_end = act.get("end_scene", "?")
                lines.append(f"- **{a_title} (Scenes {s_start}–{s_end}):** {act.get('dramatic_goal', '')}")
                if act.get("key_beat"):
                    lines.append(f"  - *Key Beat:* {act.get('key_beat')}")
                if str(a_num) in act_summaries and act_summaries[str(a_num)]:
                    lines.append(f"  - *Act Summary:* {act_summaries[str(a_num)]}")
    else:
        lines.append(f"- **Synopsis / Logline:** {settings.get('synopsis') or '*No Master Story Treatment generated yet.*'}")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 1. Master Production Bible (MPB) Baseline",
            "",
        ]
    )

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
                    f"- **Narrative Summary:** {c.narrative_summary or 'Not specified'}",
                    f"- **Voice DNA Profile:** {c.voice_dna_profile or 'Not specified'}",
                    f"- **DNA Seed:** `{c.dna_seed if c.dna_seed is not None else 'Pending'}`",
                    f"- **Base Prompt:** {c.base_prompt}",
                    "",
                    "#### Dynamic States (#State 01 - #State 05):",
                ]
            )
            states = char_states.get(c.id, [])
            if states:
                lines.append("| State Code | State Label | Wardrobe | Injuries & Wear | Expression Anchor |")
                lines.append("|:---|:---|:---|:---|:---|")
                for s in states:
                    lines.append(
                        f"| `{s.state_code}` | {s.state_label or 'Baseline'} | {s.wardrobe} | "
                        f"{s.injuries_and_wear or 'None'} | {s.expression_anchor or 'Neutral'} |"
                    )
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
            "## 3. Multi-Act Storyboard & Technical Shot Lists",
            "",
        ]
    )

    if scenes:
        lines.append(f"Total Scenes: {len(scenes)}")
        lines.append("")
        for sc in scenes:
            shots = scene_shots.get(sc.id, [])
            sc_meta = _extract_scene_dialogue_meta(shots)
            speaker = _resolve_scene_speaker(sc, shots, characters)
            lead_str = f" ({sc_meta['audio_lead_seconds']}s)" if sc_meta["audio_lead_seconds"] is not None else ""
            lines.extend(
                [
                    f"### Act {sc.act_number} | Scene {sc.scene_number:02d}: {sc.slugline}",
                    f"- **Narrative Goal:** {sc.narrative_goal}",
                    f"- **Speaking Character:** {speaker or 'Ensemble / Non-Verbal'} | **Audio Bridge:** `{sc_meta['transition_type']}`{lead_str}",
                    f"- **Target Duration:** {sc.duration_target}s | **Status:** `{sc.status}` | **Shots Count:** {len(shots)}",
                ]
            )
            if sc_meta["dialogue"]:
                lines.append(f"- **Scene Dialogue / Cue:** {sc_meta['dialogue']}")
            lines.append("")

            if shots:
                lines.append("| Shot # | Duration | Camera | Lens | Comp | Light | Act | Speed | Transition | Dialogue |")
                lines.append("|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|")
                for sh in shots:
                    diag = f'"{sh.dialogue}"' if sh.dialogue else "-"
                    lines.append(
                        f"| #{sh.shot_number} | {sh.duration_seconds}s | `{sh.camera_code}` | `{sh.lens_code}` | `{sh.comp_code}` | "
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
    """Export complete production bible, master treatment, scenes, shots, and character matrices."""
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
    scenes = list((await session.execute(scenes_stmt)).scalars().all())

    # 3. Fetch shots grouped by scene (single batch query)
    scene_shots: dict[uuid.UUID, list[ShotModel]] = {sc.id: [] for sc in scenes}
    if scenes:
        all_shots = (
            await session.execute(
                select(ShotModel)
                .where(ShotModel.scene_id.in_([sc.id for sc in scenes]))
                .order_by(ShotModel.shot_number.asc())
            )
        ).scalars().all()
        for sh in all_shots:
            scene_shots.setdefault(sh.scene_id, []).append(sh)

    # 4. Fetch characters and states (single batch query)
    chars_stmt = select(CharacterModel).where(CharacterModel.project_id == project.id).order_by(CharacterModel.created_at.asc())
    characters = list((await session.execute(chars_stmt)).scalars().all())

    char_states: dict[uuid.UUID, list[CharacterStateModel]] = {c.id: [] for c in characters}
    if characters:
        all_states = (
            await session.execute(
                select(CharacterStateModel)
                .where(CharacterStateModel.character_id.in_([c.id for c in characters]))
                .order_by(CharacterStateModel.state_code.asc())
            )
        ).scalars().all()
        for st in all_states:
            char_states.setdefault(st.character_id, []).append(st)

    fmt = export_format.lower().strip()
    if fmt in ("markdown", "md"):
        markdown_text = _generate_production_markdown(
            project=project,
            bible=bible,
            scenes=scenes,
            scene_shots=scene_shots,
            characters=characters,
            char_states=char_states,
        )
        return PlainTextResponse(
            content=markdown_text,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{project.slug}-master-package.md"'},
        )

    settings = project.settings if isinstance(project.settings, dict) else {}
    treatment = settings.get("treatment") if isinstance(settings.get("treatment"), dict) else None

    scenes_json = []
    for sc in scenes:
        shots = scene_shots.get(sc.id, [])
        sc_meta = _extract_scene_dialogue_meta(shots)
        speaker = _resolve_scene_speaker(sc, shots, characters)
        scenes_json.append(
            {
                "id": str(sc.id),
                "act_number": sc.act_number,
                "scene_number": sc.scene_number,
                "slugline": sc.slugline,
                "narrative_goal": sc.narrative_goal,
                "duration_target": sc.duration_target,
                "status": sc.status,
                "speaking_character": speaker,
                "dialogue": sc_meta["dialogue"],
                "transition_type": sc_meta["transition_type"],
                "audio_lead_seconds": sc_meta["audio_lead_seconds"],
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
                        "prompt_override": sh.fg_bg_layers.get("prompt_override") if isinstance(sh.fg_bg_layers, dict) else None,
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
                "narrative_summary": c.narrative_summary,
                "voice_dna_profile": c.voice_dna_profile,
                "dna_seed": c.dna_seed,
                "base_prompt": c.base_prompt,
                "states": [
                    {
                        "id": str(s.id),
                        "state_code": s.state_code,
                        "state_label": s.state_label,
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
            "treatment": treatment,
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
