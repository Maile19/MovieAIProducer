from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user, get_session
from backend.app.domain.audio_script import AudioScriptCompiler
from backend.app.infrastructure.database.models.auth import UserModel
from backend.app.infrastructure.database.models.character import CharacterModel, CharacterStateModel
from backend.app.infrastructure.database.models.project import ProjectModel
from backend.app.infrastructure.database.models.story import SceneModel, ShotModel

router = APIRouter(tags=["Stage S13-S15 Audio & Subtitles"])


async def _load_project_audio_context(
    project_id: str,
    session: AsyncSession,
) -> tuple[ProjectModel, list[SceneModel], dict[uuid.UUID, list[ShotModel]], list[CharacterModel], dict[uuid.UUID, list[CharacterStateModel]], int]:
    try:
        p_uuid = uuid.UUID(project_id)
        stmt = select(ProjectModel).where(ProjectModel.id == p_uuid)
    except ValueError:
        stmt = select(ProjectModel).where(ProjectModel.slug == project_id)

    project = (await session.execute(stmt)).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    scenes = list(
        (
            await session.execute(
                select(SceneModel)
                .where(SceneModel.project_id == project.id)
                .order_by(SceneModel.act_number.asc(), SceneModel.scene_number.asc())
            )
        ).scalars().all()
    )

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

    characters = list(
        (
            await session.execute(
                select(CharacterModel)
                .where(CharacterModel.project_id == project.id)
                .order_by(CharacterModel.created_at.asc())
            )
        ).scalars().all()
    )
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

    total_acts = 4
    if isinstance(project.settings, dict):
        tr = project.settings.get("treatment") or {}
        if isinstance(tr.get("acts"), list) and tr["acts"]:
            total_acts = len(tr["acts"])
        elif tr.get("structure_type") == "3_act":
            total_acts = 3
        elif tr.get("structure_type") == "5_act":
            total_acts = 5

    return project, scenes, scene_shots, characters, char_states, total_acts


@router.get("/projects/{project_id}/audio-script", status_code=status.HTTP_200_OK)
async def get_project_audio_script(
    project_id: str,
    script_format: str = Query(default="json", alias="format", description="Output format: json | ssml | markdown"),
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Compile Screenwriter TTS/Voiceover Delivery Script with Voice DNA, #State emotion, SSML, and J/L-Cut offsets."""
    project, scenes, scene_shots, characters, char_states, total_acts = await _load_project_audio_context(
        project_id, session
    )
    compiled = AudioScriptCompiler.compile_audio_script(
        project=project,
        scenes=scenes,
        scene_shots=scene_shots,
        characters=characters,
        char_states=char_states,
        total_acts=total_acts,
    )

    fmt = script_format.lower().strip()
    if fmt == "ssml":
        ssml_xml = AudioScriptCompiler.render_full_ssml(compiled)
        return PlainTextResponse(
            content=ssml_xml,
            media_type="application/ssml+xml; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{project.slug}-tts-script.ssml"'},
        )
    if fmt in ("markdown", "md"):
        md_text = AudioScriptCompiler.render_markdown(compiled)
        return PlainTextResponse(
            content=md_text,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{project.slug}-audio-script.md"'},
        )

    return {"data": compiled}


@router.get("/projects/{project_id}/subtitles", status_code=status.HTTP_200_OK)
async def get_project_subtitles(
    project_id: str,
    subtitle_format: str = Query(default="srt", alias="format", description="Subtitle format: srt | vtt"),
    include_sfx: bool = Query(default=False, description="Include [SFX]/[NON-VERBAL] SDH cues"),
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Generate downloadable .srt or .vtt subtitles honoring cumulative shot timing and J/L-Cut offsets."""
    project, scenes, scene_shots, characters, char_states, total_acts = await _load_project_audio_context(
        project_id, session
    )
    compiled = AudioScriptCompiler.compile_audio_script(
        project=project,
        scenes=scenes,
        scene_shots=scene_shots,
        characters=characters,
        char_states=char_states,
        total_acts=total_acts,
    )
    fmt = subtitle_format.lower().strip()
    if fmt not in ("srt", "vtt"):
        raise HTTPException(status_code=400, detail="Unsupported subtitle format. Use 'srt' or 'vtt'.")

    subtitle_text = AudioScriptCompiler.compile_subtitles(compiled, fmt=fmt, include_sfx=include_sfx)
    media_type = "text/vtt; charset=utf-8" if fmt == "vtt" else "application/x-subrip; charset=utf-8"
    return PlainTextResponse(
        content=subtitle_text,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{project.slug}-subtitles.{fmt}"'},
    )
