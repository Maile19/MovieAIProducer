"""Staged / Batching Hollywood LLM Screenplay Writer.

Orchestrates 2-tier screenplay generation for 50 to 420 scenes without token limits or timeouts:
- Phase A: Master Story Treatment & Beat Sheet (Logline, Theme, 4-Act Structure, Character Anchors)
- Phase B: Act-by-Act Chunking with Persistent Context Chaining (25 to 105 scenes per batch)
- Procedural Fallback: Deterministic cinematic writer if LLM is offline or times out.
"""

from datetime import datetime, timezone
import json
import logging
import uuid
from typing import Any

import httpx

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)


def get_act_bounds(total_scenes: int) -> list[tuple[int, int]]:
    """Calculate 4-Act scene number bounds [start, end] for any scale target."""
    if total_scenes == 50:
        return [(1, 12), (13, 25), (26, 38), (39, 50)]
    q1 = max(1, int(round(total_scenes * 0.25)))
    q2 = max(q1 + 1, int(round(total_scenes * 0.50)))
    q3 = max(q2 + 1, int(round(total_scenes * 0.75)))
    return [(1, q1), (q1 + 1, q2), (q2 + 1, q3), (q3 + 1, total_scenes)]


class StagedStoryWriter:
    """Orchestrates Phase A & Phase B screenplay generation with persistent context."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str | None = None):
        settings = get_settings()
        self.base_url = base_url or settings.effective_llm_base_url
        self.api_key = api_key or settings.effective_llm_api_key
        self.model = model or settings.llm_model
        self.timeout = settings.llm_timeout_seconds

    async def _call_llm(self, messages: list[dict[str, str]], timeout: float | None = None) -> dict[str, Any] | None:
        """Call LLM completions endpoint with JSON response format."""
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=timeout or self.timeout) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    content_str = data["choices"][0]["message"]["content"]
                    return json.loads(content_str)
                else:
                    logger.warning(
                        "LLM call returned non-200 status: %d body: %s",
                        resp.status_code,
                        resp.text[:200],
                    )
                    return None
        except Exception as exc:
            logger.warning("LLM call exception: %s. Using procedural fallback.", exc)
            return None

    def _procedural_fallback_treatment(
        self,
        title: str,
        total_scenes: int,
        premise: str = "",
        characters: list[dict[str, Any]] | None = None,
        cold_open_30s: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate high-quality procedural cinematic treatment when LLM is unavailable."""
        char_name = characters[0]["name"] if characters else "Arya"
        char_role = characters[0]["role"] if characters else "Disgraced Cyber Operative"

        bounds = get_act_bounds(total_scenes)
        cold_open_enabled = bool(cold_open_30s and cold_open_30s.get("enabled"))
        act1_goal = (
            f"Cold Open (Scenes 01-03): High-energy visual teaser hook montage. "
            f"Linear Ordinary World begins at Scene 04: Establish {char_name}'s ordinary world, trigger inciting incident, force threshold crossing."
            if cold_open_enabled
            else f"Establish {char_name}'s ordinary world, trigger inciting incident, force threshold crossing."
        )
        act1_beat = (
            "Cold Open Visual Hook Montage & Linear Ordinary World Setup (Scene 04)"
            if cold_open_enabled
            else "Plot Point 1: Breach of the Outer Perimeter"
        )

        treatment_dict: dict[str, Any] = {
            "title": title,
            "logline": (
                premise
                or f"In a neo-noir metropolis ruled by algorithmic surveillance, {char_name} ({char_role}) "
                f"uncovers a conspiracy within the city's central mainframe, risking everything to break the loop."
            ),
            "theme": "Free will versus algorithmic determinism in a synthetic world",
            "dramatic_premise": f"{title} follows {char_name}'s descent into the underbelly to reveal truth.",
            "total_scenes": total_scenes,
            "acts": [
                {
                    "act_number": 1,
                    "act_title": "Act I: Setup & The Catalyst",
                    "start_scene": bounds[0][0],
                    "end_scene": bounds[0][1],
                    "dramatic_goal": act1_goal,
                    "key_beat": act1_beat,
                },
                {
                    "act_number": 2,
                    "act_title": "Act II-A: Rising Stakes & Initial Trials",
                    "start_scene": bounds[1][0],
                    "end_scene": bounds[1][1],
                    "dramatic_goal": "Navigate underworld alliances, survive initial counter-measures, build toward the midpoint.",
                    "key_beat": "Midpoint Reversal: False Victory reveals deeper deception",
                },
                {
                    "act_number": 3,
                    "act_title": "Act II-B: Dark Night & The Descent",
                    "start_scene": bounds[2][0],
                    "end_scene": bounds[2][1],
                    "dramatic_goal": "Everything collapses; allies scatter; protagonist faces internal core flaw.",
                    "key_beat": "All Is Lost Crisis: Complete neural quarantine",
                },
                {
                    "act_number": 4,
                    "act_title": "Act III & IV: The Climax & Resolution",
                    "start_scene": bounds[3][0],
                    "end_scene": bounds[3][1],
                    "dramatic_goal": "Final confrontation against the central mainframe, philosophical catharsis, and new reality.",
                    "key_beat": "Final Climax: Decisive reckoning and system rebirth",
                },
            ],
            "act_summaries": {},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        if cold_open_30s:
            treatment_dict["cold_open_30s"] = cold_open_30s

        return treatment_dict

    async def generate_treatment(
        self,
        title: str,
        total_scenes: int,
        premise: str = "",
        characters: list[dict[str, Any]] | None = None,
        cold_open_30s: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Phase A: Generate master story treatment and beat sheet."""
        bounds = get_act_bounds(total_scenes)
        char_desc = ""
        if characters:
            char_desc = "Key Characters:\n" + "\n".join(
                f"- {c.get('name', 'Hero')} ({c.get('role', 'Protagonist')}): {c.get('base_prompt', '')}"
                for c in characters
            )

        cold_open_directive = ""
        if cold_open_30s and cold_open_30s.get("enabled"):
            cold_open_directive = (
                "\nSPECIAL MANDATE - 30-SECOND VISUAL HOOK MONTAGE (COLD OPEN):\n"
                "Act I begins with a 30-Second Visual Hook Montage across Scenes 01-03 before the main story:\n"
                "- Scene 01 (0-10s): In-Media-Res Shock Hook + Hero Prop Reveal\n"
                "- Scene 02 (10-20s): Fast Slapstick Chaos Tease + Main Obstacle/Rival\n"
                "- Scene 03 (20-30s): Peak Climax Preview + Freeze-Frame/Rewind Transition to Scene 04\n"
                "- Scene 04 onwards: The linear narrative (Ordinary World) begins here.\n"
            )

        prompt = f"""You are a master Hollywood script doctor and narrative architect.
Create a comprehensive 4-Act Master Story Treatment and Beat Sheet for a feature film.

Film Title: {title}
Total Screenplay Scale: {total_scenes} Scenes
{f"Director's Premise: {premise}" if premise else ""}
{char_desc}
{cold_open_directive}
Act Ranges:
- Act 1: Scenes {bounds[0][0]} to {bounds[0][1]}
- Act 2: Scenes {bounds[1][0]} to {bounds[1][1]}
- Act 3: Scenes {bounds[2][0]} to {bounds[2][1]}
- Act 4: Scenes {bounds[3][0]} to {bounds[3][1]}

Return a strictly valid JSON object matching this schema:
{{
  "title": "{title}",
  "logline": "Compelling 1-2 sentence cinematic logline with protagonist, inciting incident, antagonist force, and stakes",
  "theme": "Underlying philosophical core or thematic question",
  "dramatic_premise": "Paragraph explaining protagonist arc and central dramatic conflict",
  "total_scenes": {total_scenes},
  "acts": [
    {{
      "act_number": 1,
      "act_title": "Act I: Setup & The Catalyst",
      "start_scene": {bounds[0][0]},
      "end_scene": {bounds[0][1]},
      "dramatic_goal": "Dramatic goal of Act I",
      "key_beat": "Key beat for Act I"
    }},
    {{
      "act_number": 2,
      "act_title": "Act II-A: Rising Stakes",
      "start_scene": {bounds[1][0]},
      "end_scene": {bounds[1][1]},
      "dramatic_goal": "Dramatic goal of Act II-A",
      "key_beat": "Key beat for Act II-A"
    }},
    {{
      "act_number": 3,
      "act_title": "Act II-B: Dark Night",
      "start_scene": {bounds[2][0]},
      "end_scene": {bounds[2][1]},
      "dramatic_goal": "Dramatic goal of Act II-B",
      "key_beat": "Key beat for Act II-B"
    }},
    {{
      "act_number": 4,
      "act_title": "Act III & IV: Climax & Resolution",
      "start_scene": {bounds[3][0]},
      "end_scene": {bounds[3][1]},
      "dramatic_goal": "Dramatic goal of Act III/IV",
      "key_beat": "Key beat for Act III/IV"
    }}
  ]
}}"""

        messages = [
            {"role": "system", "content": "You are a master Hollywood script doctor. Output valid JSON only."},
            {"role": "user", "content": prompt},
        ]

        result = await self._call_llm(messages, timeout=self.timeout)
        if result and isinstance(result, dict) and "acts" in result and len(result.get("acts", [])) == 4:
            result["act_summaries"] = {}
            result["total_scenes"] = total_scenes
            result["used_fallback"] = False
            if cold_open_30s:
                result["cold_open_30s"] = cold_open_30s
                if cold_open_30s.get("enabled"):
                    for act in result.get("acts", []):
                        if act.get("act_number") == 1:
                            goal = act.get("dramatic_goal", "")
                            if "Cold Open (Scenes 01-03)" not in goal:
                                act["dramatic_goal"] = (
                                    f"Cold Open (Scenes 01-03): High-energy visual teaser hook montage. "
                                    f"Linear Ordinary World begins at Scene 04: {goal}"
                                )
                            beat = act.get("key_beat", "")
                            if "Cold Open" not in beat:
                                act["key_beat"] = f"Cold Open Visual Hook Montage & {beat}"
            result["generated_at"] = datetime.now(timezone.utc).isoformat()
            return result

        logger.info("Using procedural treatment fallback for title: %s", title)
        fallback = self._procedural_fallback_treatment(
            title, total_scenes, premise, characters, cold_open_30s=cold_open_30s
        )
        fallback["used_fallback"] = True
        return fallback

    def _procedural_fallback_scene(
        self,
        scene_num: int,
        act_num: int,
        title: str,
        total_scenes: int,
        act_goal: str = "",
        cold_open_30s: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Generate cohesive fallback scene slugline, narrative goal, and dialogue."""
        if act_num == 1 and cold_open_30s and cold_open_30s.get("enabled"):
            if scene_num == 1:
                return {
                    "scene_number": 1,
                    "slugline": "SCENE 01 - INT/EXT. HIGH-VELOCITY CHAOS - DAY (COLD OPEN 0-10S)",
                    "narrative_goal": "In-Media-Res Shock Hook + Hero Prop Reveal: Immediate high-energy visual shock hook in media res, dramatic hero prop reveal, dynamic camera movement.",
                    "dialogue": "[SFX: Instant High-Pitched Comedic Whistle & Dramatic Boing - Protagonist eyes bulge in extreme close-up!]",
                }
            elif scene_num == 2:
                return {
                    "scene_number": 2,
                    "slugline": "SCENE 02 - EXT. RUNAWAY SLAPSTICK OBSTACLE COURSE - CONTINUOUS (COLD OPEN 10-20S)",
                    "narrative_goal": "Fast Slapstick Chaos Tease + Main Obstacle/Rival: Fast-paced comedic chaos tease, introduce antagonist/rival obstacle, rapid slapstick gag escalation.",
                    "dialogue": "[SFX: Rapid Slip, Cartoon Car Horn Honk & Exaggerated Shocked Gasp as Rival Appears]",
                }
            elif scene_num == 3:
                return {
                    "scene_number": 3,
                    "slugline": "SCENE 03 - EXT. PREVIEW OF THE ULTIMATE CLIMAX - CONTINUOUS (COLD OPEN 20-30S)",
                    "narrative_goal": "Peak Climax Preview + Freeze-Frame/Rewind Transition ke Scene 04: Preview of peak catastrophic climax, abrupt comical freeze-frame / VHS rewind sound effect transitioning to linear story at Scene 04 (Ordinary World).",
                    "dialogue": "[SFX: Record Scratch & VHS High-Speed Tape Rewind - 'Yep, that's me... you're probably wondering how I ended up here!']",
                }
            elif scene_num == 4:
                return {
                    "scene_number": 4,
                    "slugline": "SCENE 04 - INT. PROTAGONIST HOME / WORKSPACE - MORNING (ACT I: ORDINARY WORLD BEGINS)",
                    "narrative_goal": "Linear Narrative Setup (Act I: Ordinary World): Introduction of protagonist's routine, desires, and mundane life before the inciting incident.",
                    "dialogue": "[SFX: Gentle Morning Birds Chirping & Yawn - Protagonist stretches before the daily routine starts.]",
                }

        pad = 3 if total_scenes >= 100 else 2
        locations = [
            "EXT. NEO DISTRICT PERIMETER - NIGHT",
            "INT. UNDERGROUND SAFE-HOUSE - DUSK",
            "INT. CENTRAL MAINFRAME VAULT - NIGHT",
            "EXT. INDUSTRIAL RAIN ALLEY - DAWN",
            "INT. HIGH-TOWER PENTHOUSE - NIGHT",
            "EXT. ROOFTOP COMMUNICATIONS ARRAY - DUSK",
            "INT. TACTICAL COMMAND SUB-LEVEL - NIGHT",
            "EXT. ABANDONED MONORAIL STATION - NIGHT",
        ]
        loc = locations[(scene_num * 3 + act_num) % len(locations)]

        dialogues = [
            "Sensor distrik sudah offline. Kita punya waktu tiga menit.",
            "Protokol enkripsi ini bukan buatan manusia, ada AI yang mengendalikannya.",
            "Jika kita masuk sekarang, tidak ada jalan untuk berbalik.",
            "Semua data yang mereka berikan kepadamu hanyalah ilusi terprogram.",
            "Matikan transmisi satelit sekarang juga sebelum mereka melacak posisimu!",
            "Aku tidak peduli siapa yang memerintahkannya, operasi ini harus selesai malam ini.",
            "Lihat log komunikasinya, mereka sudah tahu rencana kita sejak awal.",
            "Sistem pertahanan distrik mulai runtuh, bersiaplah untuk benturan keras.",
        ]
        dlg = dialogues[(scene_num * 7) % len(dialogues)]

        return {
            "scene_number": scene_num,
            "slugline": f"SCENE {str(scene_num).zfill(pad)} - {loc}",
            "narrative_goal": f"Act {act_num} cinematic beat: Advance narrative momentum toward {act_goal or 'mission objective'}.",
            "dialogue": dlg,
        }

    async def generate_act_scenes(
        self,
        act_number: int,
        total_scenes: int,
        treatment: dict[str, Any],
        previous_act_summaries: dict[int, str] | None = None,
        characters: list[dict[str, Any]] | None = None,
        duration_mode: str = "dynamic",
        cold_open_30s: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Phase B: Generate scenes for a single Act with persistent context chaining."""
        bounds = get_act_bounds(total_scenes)
        if not (1 <= act_number <= 4):
            raise ValueError(f"Invalid act number: {act_number}. Must be 1 to 4.")

        start_scene, end_scene = bounds[act_number - 1]
        act_count = end_scene - start_scene + 1

        cold_open_cfg = (
            cold_open_30s
            or treatment.get("cold_open_30s")
            or treatment.get("preset_data", {}).get("storyboard_defaults", {}).get("cold_open_30s")
        )
        cold_open_active = bool(act_number == 1 and cold_open_cfg and cold_open_cfg.get("enabled"))

        # Extract act dramatic goal and title from treatment
        act_info = next((a for a in treatment.get("acts", []) if a.get("act_number") == act_number), None)
        act_title = act_info.get("act_title", f"Act {act_number}") if act_info else f"Act {act_number}"
        act_goal = act_info.get("dramatic_goal", "") if act_info else ""
        key_beat = act_info.get("key_beat", "") if act_info else ""

        # Build persistent context from previous acts
        context_chain = []
        if previous_act_summaries:
            for prev_act in range(1, act_number):
                if prev_act in previous_act_summaries and previous_act_summaries[prev_act]:
                    context_chain.append(f"Summary of Act {prev_act}: {previous_act_summaries[prev_act]}")

        context_str = "\n".join(context_chain) if context_chain else "Beginning of story narrative."

        char_names = [c["name"] for c in characters] if characters else ["Arya", "Kael"]
        char_list_str = ", ".join(char_names)

        # We process in sub-chunks of at most 35 scenes to prevent any token truncation or timeout
        CHUNK_SIZE = 35
        all_generated_scenes: list[dict[str, Any]] = []
        act_summary = ""

        chunks: list[tuple[int, int]] = []
        curr = start_scene
        while curr <= end_scene:
            next_curr = min(curr + CHUNK_SIZE - 1, end_scene)
            chunks.append((curr, next_curr))
            curr = next_curr + 1

        for c_start, c_end in chunks:
            chunk_scenes_needed = c_end - c_start + 1
            cold_open_instruction = ""
            if cold_open_active:
                cold_open_instruction = """
COLD OPEN (30-SECOND VISUAL HOOK MONTAGE) MANDATE:
Scenes 1 through 3 MUST serve as a high-velocity 30-second Cold Open hook montage teasing peak action and slapstick chaos before rewinding:
- Scene 1 (0-10s): In-Media-Res Shock Hook + Hero Prop Reveal
- Scene 2 (10-20s): Fast Slapstick Chaos Tease + Main Obstacle/Rival
- Scene 3 (20-30s): Peak Climax Preview + Freeze-Frame/Rewind Transition ke Scene 04
- Scene 4 onwards: Linear Narrative starts (Act I: Ordinary World Setup).
"""

            prompt = f"""You are a master Hollywood screenwriter writing scenes for a major feature film.

Title: {treatment.get('title', 'Cinema Feature')}
Logline: {treatment.get('logline', '')}
Theme: {treatment.get('theme', '')}

Current Act: {act_title} (Act {act_number} of 4)
Act Dramatic Goal: {act_goal}
Key Dramatic Beat: {key_beat}
Characters Available: {char_list_str}
{cold_open_instruction}
PERSISTENT STORY CONTEXT (Previous Acts):
{context_str}

ASSIGNMENT:
Write exactly {chunk_scenes_needed} scenes from Scene {c_start} to Scene {c_end}.
For each scene provide:
- scene_number (integer from {c_start} to {c_end})
- slugline (standard uppercase screenplay slugline, e.g. 'EXT. SECTOR 4 SPIRE - NIGHT')
- narrative_goal (concise dramatic objective for cinematic storytelling)
- dialogue (realistic, sharp screenplay line in Indonesian or English matching characters)

Return valid JSON in this exact structure:
{{
  "act_summary": "2-3 sentences summarizing the major events and ending situation of these scenes to chain into the next act",
  "scenes": [
    {{
      "scene_number": {c_start},
      "slugline": "EXT. LOCATION - TIME",
      "narrative_goal": "Dramatic goal of the scene",
      "dialogue": "Spoken line or voiceover"
    }}
  ]
}}"""

            messages = [
                {"role": "system", "content": "You are a master screenwriter. Output valid JSON only."},
                {"role": "user", "content": prompt},
            ]

            chunk_res = await self._call_llm(messages, timeout=self.timeout)
            scenes_dict: dict[int, dict[str, Any]] = {}
            chunk_used_fallback = False

            if chunk_res and isinstance(chunk_res, dict) and "scenes" in chunk_res:
                if chunk_res.get("act_summary"):
                    act_summary = chunk_res["act_summary"]

                for sc in chunk_res.get("scenes", []):
                    try:
                        s_num = int(sc.get("scene_number", 0))
                        if c_start <= s_num <= c_end:
                            scenes_dict[s_num] = {
                                "scene_number": s_num,
                                "slugline": str(sc.get("slugline", "")).strip() or f"SCENE {s_num:03d} - INT. SPIRE - NIGHT",
                                "narrative_goal": str(sc.get("narrative_goal", "")).strip(),
                                "dialogue": str(sc.get("dialogue", "")).strip(),
                            }
                    except (ValueError, TypeError):
                        continue
            else:
                chunk_used_fallback = True

            # Ensure all scene numbers in this chunk exist; fill gaps procedurally
            for num in range(c_start, c_end + 1):
                if cold_open_active and num in (1, 2, 3):
                    # Enforce the 30-Second Visual Hook Montage specifications for Scenes 01-03
                    co_sc = self._procedural_fallback_scene(
                        num, act_number, treatment.get("title", ""), total_scenes, act_goal, cold_open_30s=cold_open_cfg
                    )
                    co_sc["is_fallback"] = False
                    all_generated_scenes.append(co_sc)
                elif cold_open_active and num == 4:
                    # Enforce Scene 04 begins the Linear Ordinary World
                    if num in scenes_dict and scenes_dict[num].get("narrative_goal") and not chunk_used_fallback:
                        sc_item = dict(scenes_dict[num])
                        slug = sc_item.get("slugline", "SCENE 04 - INT. PROTAGONIST WORKSPACE - MORNING")
                        if "ORDINARY WORLD BEGINS" not in slug:
                            slug = f"{slug.rstrip()} (ACT I: ORDINARY WORLD BEGINS)"
                        goal = sc_item.get("narrative_goal", "Linear Narrative Setup (Act I: Ordinary World)")
                        if "Ordinary World" not in goal:
                            goal = f"Linear Narrative Setup (Act I: Ordinary World): {goal}"
                        sc_item["slugline"] = slug
                        sc_item["narrative_goal"] = goal
                        sc_item["is_fallback"] = False
                        all_generated_scenes.append(sc_item)
                    else:
                        chunk_used_fallback = True
                        fallback_sc = self._procedural_fallback_scene(
                            4, act_number, treatment.get("title", ""), total_scenes, act_goal, cold_open_30s=cold_open_cfg
                        )
                        fallback_sc["is_fallback"] = True
                        all_generated_scenes.append(fallback_sc)
                elif num in scenes_dict and scenes_dict[num].get("narrative_goal"):
                    sc_item = dict(scenes_dict[num])
                    sc_item["is_fallback"] = False
                    all_generated_scenes.append(sc_item)
                else:
                    chunk_used_fallback = True
                    fallback_sc = self._procedural_fallback_scene(
                        num, act_number, treatment.get("title", ""), total_scenes, act_goal, cold_open_30s=cold_open_cfg
                    )
                    fallback_sc["is_fallback"] = True
                    all_generated_scenes.append(fallback_sc)

        if not act_summary:
            act_summary = (
                f"Act {act_number} reaches its conclusion with {char_names[0]} "
                f"advancing the core dramatic stakes through Scene {end_scene}."
            )

        act_used_fallback = any(s.get("is_fallback", False) for s in all_generated_scenes)

        return {
            "act_number": act_number,
            "start_scene": start_scene,
            "end_scene": end_scene,
            "scenes_count": len(all_generated_scenes),
            "act_summary": act_summary,
            "used_fallback": act_used_fallback,
            "scenes": all_generated_scenes,
        }