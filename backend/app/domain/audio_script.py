"""Stage S13-S15: Pure-Python Screenwriter TTS/SSML Delivery Script & SRT/VTT Subtitle Engine.

Compiles ordered scenes, shots, character Voice DNA profiles, act-mapped #State emotional
anchors, and J-Cut / L-Cut audio bridge offsets into deterministic TTS delivery metadata,
valid XML-escaped SSML, SubRip (.srt), and WebVTT (.vtt) outputs without heavy audio dependencies.
"""

from __future__ import annotations

import re
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from backend.app.domain.screenwriter import PolyaScreenwriterEngine

_SFX_OR_NON_VERBAL_RE = re.compile(r"^\s*(?:\[(?:SFX|NON-VERBAL|SILENT)[^\]]*\]|\([^)]*\))\s*$", re.IGNORECASE)


def _format_srt_timestamp(seconds: float) -> str:
    ms_total = max(0, int(round(seconds * 1000)))
    hours, rem = divmod(ms_total, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _format_vtt_timestamp(seconds: float) -> str:
    ms_total = max(0, int(round(seconds * 1000)))
    hours, rem = divmod(ms_total, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def _is_non_spoken_cue(text: str) -> bool:
    cleaned = (text or "").strip()
    if not cleaned:
        return True
    if _SFX_OR_NON_VERBAL_RE.match(cleaned):
        return True
    # Strip all bracketed/parenthetical tags; if nothing remains, it is pure SFX/non-verbal
    spoken_only = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", cleaned).strip()
    return len(spoken_only) == 0


def _derive_prosody(
    voice_dna_profile: str | None,
    emotional_anchor: str | None,
    transition_type: str,
) -> dict[str, Any]:
    voice_low = (voice_dna_profile or "").lower()
    emo_low = (emotional_anchor or "").lower()
    combined = f"{voice_low} {emo_low}"

    speaking_rate_wps = 2.8
    prosody_rate = "100%"
    prosody_pitch = "0st"
    pause_before_ms = 150
    pause_after_ms = 250

    if any(k in combined for k in ("clipped", "urgent", "staccato", "rapid", "sharp", "tense", "frantic")):
        speaking_rate_wps = 3.0
        prosody_rate = "108%"
        prosody_pitch = "+1st"
        pause_before_ms = 100
        pause_after_ms = 180
    elif any(k in combined for k in ("slow", "measured", "calm", "stoic", "solemn", "whisper", "hollow", "still")):
        speaking_rate_wps = 2.3
        prosody_rate = "88%"
        prosody_pitch = "-2st"
        pause_before_ms = 260
        pause_after_ms = 380

    if any(k in emo_low for k in ("grief", "weary", "broken", "dread", "somber", "exhausted")):
        prosody_pitch = "-2st"
    elif any(k in emo_low for k in ("panic", "fierce", "defiant", "alarm", "shock")):
        prosody_pitch = "+2st"

    if transition_type == "J_CUT":
        pause_before_ms = max(80, pause_before_ms - 60)
    elif transition_type == "L_CUT":
        pause_after_ms = pause_after_ms + 180

    return {
        "speaking_rate_wps": speaking_rate_wps,
        "prosody_rate": prosody_rate,
        "prosody_pitch": prosody_pitch,
        "pause_before_ms": pause_before_ms,
        "pause_after_ms": pause_after_ms,
    }


def _build_ssml_line(text: str, prosody: dict[str, Any]) -> str:
    escaped = xml_escape((text or "").strip())
    return (
        "<speak>"
        f'<prosody rate="{prosody["prosody_rate"]}" pitch="{prosody["prosody_pitch"]}">'
        f'<break time="{prosody["pause_before_ms"]}ms"/>'
        f"{escaped}"
        f'<break time="{prosody["pause_after_ms"]}ms"/>'
        "</prosody>"
        "</speak>"
    )


class AudioScriptCompiler:
    """Deterministic Stage S13-S15 TTS Delivery Script, SSML, and SRT/VTT Compiler."""

    @staticmethod
    def compile_audio_script(
        project: Any,
        scenes: list[Any],
        scene_shots: dict[Any, list[Any]],
        characters: list[Any],
        char_states: dict[Any, list[Any]],
        total_acts: int = 4,
    ) -> dict[str, Any]:
        """Compile ordered scenes/shots with Voice DNA, #State emotion, SSML, and J/L-Cut cumulative timestamps."""
        chars = characters or []
        cues: list[dict[str, Any]] = []
        cumulative_cursor = 0.0
        cue_index = 0

        for sc in scenes:
            shots = scene_shots.get(getattr(sc, "id", None), [])
            sc_duration = float(getattr(sc, "duration_target", 5.0) or 5.0)
            sc_act = int(getattr(sc, "act_number", 1) or 1)
            sc_num = int(getattr(sc, "scene_number", 1) or 1)
            sc_slug = str(getattr(sc, "slugline", "") or f"SCENE {sc_num:02d}")
            sc_goal = str(getattr(sc, "narrative_goal", "") or "")

            units: list[dict[str, Any]]
            if shots:
                units = [
                    {
                        "shot_id": str(getattr(sh, "id", "")),
                        "shot_number": int(getattr(sh, "shot_number", idx + 1) or (idx + 1)),
                        "duration": float(getattr(sh, "duration_seconds", 5.0) or 5.0),
                        "dialogue": getattr(sh, "dialogue", None),
                        "transition_type": str(getattr(sh, "transition_type", "NONE") or "NONE").upper(),
                        "fg_bg_layers": getattr(sh, "fg_bg_layers", {}) if isinstance(getattr(sh, "fg_bg_layers", None), dict) else {},
                    }
                    for idx, sh in enumerate(shots)
                ]
            else:
                units = [
                    {
                        "shot_id": None,
                        "shot_number": 1,
                        "duration": sc_duration,
                        "dialogue": None,
                        "transition_type": "NONE",
                        "fg_bg_layers": {},
                    }
                ]

            for unit in units:
                unit_start = cumulative_cursor
                unit_end = cumulative_cursor + unit["duration"]
                cumulative_cursor = unit_end

                raw_dialogue = str(unit["dialogue"] or "").strip()
                if not raw_dialogue:
                    continue

                cue_index += 1
                is_sfx = _is_non_spoken_cue(raw_dialogue)

                # Match speaking character from roster
                matched_char = None
                if chars:
                    goal_low = sc_goal.lower()
                    dlg_low = raw_dialogue.lower()
                    matched_char = next(
                        (
                            c
                            for c in chars
                            if getattr(c, "name", "")
                            and (c.name.lower() in dlg_low or c.name.lower() in goal_low)
                        ),
                        chars[0],
                    )

                speaker_name = getattr(matched_char, "name", None) or ("SFX / Ambience" if is_sfx else "Narrator")
                voice_dna = str(getattr(matched_char, "voice_dna_profile", "") or "").strip() or None

                emotion_cue = "Neutral"
                active_state_code = "#State 01"
                if matched_char:
                    states = char_states.get(getattr(matched_char, "id", None), [])
                    target_st_num = PolyaScreenwriterEngine._resolve_act_to_state_number(sc_act, total_acts) or 1
                    active_state_code = f"#State 0{target_st_num}"
                    st_obj = next(
                        (s for s in states if str(getattr(s, "state_code", "")).upper() == active_state_code.upper()),
                        states[0] if states else None,
                    )
                    if st_obj:
                        active_state_code = str(getattr(st_obj, "state_code", active_state_code))
                        emotion_cue = str(getattr(st_obj, "expression_anchor", "") or getattr(st_obj, "state_label", "") or "Baseline")

                transition = unit["transition_type"]
                raw_lead = unit["fg_bg_layers"].get("audio_lead_seconds")
                if isinstance(raw_lead, (int, float)):
                    audio_lead = max(0.0, float(raw_lead))
                elif transition == "J_CUT":
                    audio_lead = 1.0
                elif transition == "L_CUT":
                    audio_lead = 0.5
                else:
                    audio_lead = 0.0

                pacing = PolyaScreenwriterEngine._compute_dialogue_pacing_metrics(raw_dialogue, unit["duration"])
                est_dur = float(pacing["estimated_duration_seconds"] or 0.0)

                if transition == "J_CUT":
                    audio_start = max(0.0, round(unit_start - audio_lead, 3))
                    audio_end = round(max(audio_start + max(1.0, est_dur), unit_end), 3)
                elif transition == "L_CUT":
                    audio_start = round(unit_start, 3)
                    audio_end = round(unit_end + audio_lead, 3)
                else:
                    audio_start = round(unit_start, 3)
                    audio_end = round(max(audio_start + 0.5, unit_end), 3)

                prosody = _derive_prosody(voice_dna, emotion_cue, transition)
                ssml = _build_ssml_line(raw_dialogue, prosody)

                cues.append({
                    "cue_number": cue_index,
                    "scene_id": str(getattr(sc, "id", "")),
                    "act_number": sc_act,
                    "scene_number": sc_num,
                    "slugline": sc_slug,
                    "shot_id": unit["shot_id"],
                    "shot_number": unit["shot_number"],
                    "speaker": speaker_name,
                    "voice_profile": voice_dna or "Voice DNA Unset (Default Studio Voice)",
                    "has_voice_dna": bool(voice_dna),
                    "active_state_code": active_state_code,
                    "emotion_cue": emotion_cue,
                    "text": raw_dialogue,
                    "is_sfx": is_sfx,
                    "word_count": pacing["word_count"],
                    "estimated_duration_seconds": est_dur,
                    "passes_duration_limit": pacing["passes_duration_limit"],
                    "transition_type": transition,
                    "audio_lead_seconds": audio_lead,
                    "shot_start_seconds": round(unit_start, 3),
                    "shot_end_seconds": round(unit_end, 3),
                    "start_seconds": audio_start,
                    "end_seconds": audio_end,
                    "speaking_rate_wps": prosody["speaking_rate_wps"],
                    "prosody_rate": prosody["prosody_rate"],
                    "prosody_pitch": prosody["prosody_pitch"],
                    "pause_before_ms": prosody["pause_before_ms"],
                    "pause_after_ms": prosody["pause_after_ms"],
                    "ssml": ssml,
                })

        return {
            "project_id": str(getattr(project, "id", "")),
            "project_title": str(getattr(project, "title", "Production")),
            "total_scenes": len(scenes),
            "total_cues": len(cues),
            "spoken_cues": sum(1 for c in cues if not c["is_sfx"]),
            "sfx_cues": sum(1 for c in cues if c["is_sfx"]),
            "total_runtime_seconds": round(cumulative_cursor, 2),
            "cues": cues,
        }

    @staticmethod
    def render_full_ssml(script_data: dict[str, Any]) -> str:
        """Render complete XML-valid SSML document wrapping all voice cues."""
        title_esc = xml_escape(str(script_data.get("project_title") or "Production"))
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">',
            f"  <!-- {title_esc} — Screenwriter TTS Delivery Script -->",
        ]
        for cue in script_data.get("cues", []):
            speaker_esc = xml_escape(str(cue.get("speaker") or "Speaker"))
            state_esc = xml_escape(str(cue.get("active_state_code") or "#State 01"))
            emo_esc = xml_escape(str(cue.get("emotion_cue") or "Neutral"))
            text_esc = xml_escape(str(cue.get("text") or ""))
            lines.append(
                f'  <!-- Scene {cue["scene_number"]:02d} Shot #{cue["shot_number"]} | '
                f'{speaker_esc} ({state_esc}: {emo_esc}) | {cue["start_seconds"]:.2f}s-{cue["end_seconds"]:.2f}s [{cue["transition_type"]}] -->'
            )
            lines.append(
                f'  <prosody rate="{cue["prosody_rate"]}" pitch="{cue["prosody_pitch"]}">'
                f'<break time="{cue["pause_before_ms"]}ms"/>'
                f"{text_esc}"
                f'<break time="{cue["pause_after_ms"]}ms"/>'
                "</prosody>"
            )
        lines.append("</speak>")
        return "\n".join(lines)

    @staticmethod
    def render_markdown(script_data: dict[str, Any]) -> str:
        """Render human-readable Voiceover & TTS Delivery Binder Markdown."""
        lines = [
            f"# {str(script_data.get('project_title') or 'Production').upper()} — STAGE S13-S15 AUDIO & TTS DELIVERY SCRIPT",
            "",
            f"- **Total Scenes:** {script_data.get('total_scenes', 0)}",
            f"- **Total Audio Cues:** {script_data.get('total_cues', 0)} ({script_data.get('spoken_cues', 0)} spoken, {script_data.get('sfx_cues', 0)} SFX)",
            f"- **Cumulative Timeline Runtime:** {script_data.get('total_runtime_seconds', 0.0)}s",
            "",
            "---",
            "",
        ]
        for cue in script_data.get("cues", []):
            lines.extend(
                [
                    f"### Cue #{cue['cue_number']:03d} — Act {cue['act_number']} | Scene {cue['scene_number']:02d} ({cue['slugline']}) | Shot #{cue['shot_number']}",
                    f"- **Speaker:** **{cue['speaker']}** (`{cue['active_state_code']}` — {cue['emotion_cue']})",
                    f"- **Voice DNA:** {cue['voice_profile']}",
                    f"- **Timeline:** `{cue['start_seconds']:.2f}s -> {cue['end_seconds']:.2f}s` (`{cue['transition_type']}`, lead `{cue['audio_lead_seconds']}s`)",
                    f"- **Delivery:** rate `{cue['prosody_rate']}`, pitch `{cue['prosody_pitch']}`, `{cue['word_count']}w` (~{cue['estimated_duration_seconds']}s @ 2.8 wps)",
                    f"- **Line:** {cue['text']}",
                    f"- **SSML:** `{cue['ssml']}`",
                    "",
                ]
            )
        if not script_data.get("cues"):
            lines.append("*No dialogue or SFX cues found in project shots.*")
        return "\n".join(lines)

    @staticmethod
    def compile_subtitles(
        script_data: dict[str, Any],
        fmt: str = "srt",
        include_sfx: bool = False,
    ) -> str:
        """Format valid SubRip (.srt) or WebVTT (.vtt) subtitles from compiled audio script cues."""
        target_fmt = (fmt or "srt").lower().strip()
        selected_cues = [
            c
            for c in script_data.get("cues", [])
            if include_sfx or not c.get("is_sfx")
        ]

        if target_fmt == "vtt":
            lines = ["WEBVTT", ""]
            for idx, cue in enumerate(selected_cues, start=1):
                start_ts = _format_vtt_timestamp(float(cue["start_seconds"]))
                end_ts = _format_vtt_timestamp(float(cue["end_seconds"]))
                speaker_prefix = f"<v {cue['speaker']}>" if not cue.get("is_sfx") else ""
                lines.append(str(idx))
                lines.append(f"{start_ts} --> {end_ts}")
                lines.append(f"{speaker_prefix}{cue['text']}")
                lines.append("")
            return "\n".join(lines)

        # Default: SubRip (.srt)
        lines = []
        for idx, cue in enumerate(selected_cues, start=1):
            start_ts = _format_srt_timestamp(float(cue["start_seconds"]))
            end_ts = _format_srt_timestamp(float(cue["end_seconds"]))
            text_line = f"{cue['speaker']}: {cue['text']}" if not cue.get("is_sfx") else cue["text"]
            lines.append(str(idx))
            lines.append(f"{start_ts} --> {end_ts}")
            lines.append(text_line)
            lines.append("")
        return "\n".join(lines)
