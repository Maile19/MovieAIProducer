"""Polya AI (Skill: Screenwriter) Character & State Architecture Engine.

Provides cinematic ensemble cast generation, isolated single-character generation,
and isolated per-character re-generation adhering to the Hollywood Screenwriter persona.
Operates strictly text-only with zero automatic image rendering.
"""

from __future__ import annotations

from datetime import datetime, timezone
import asyncio
import hashlib
import json
import logging
import math
import os
import random
import re
import time
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, field_validator

from backend.app.core.config import get_settings
from backend.app.domain.catalog import LIGHTING_MATRIX, STYLE_CATALOG, validate_matrix_code
from backend.app.domain.director_rag import DirectorRAGClient
from backend.app.services.screenwriter_rag import ScreenwriterRAGClient

logger = logging.getLogger("polya.screenwriter")


# ==============================================================================
# Style Taxonomy Families (4-Family Master Matrix for #Style 01 - #Style 18)
# ==============================================================================

STYLE_TAXONOMY_FAMILIES: dict[str, dict[str, Any]] = {
    "photorealistic": {
        "name": "Live Action / Cinematic Photoreal",
        "style_codes": [
            "#Style 01", "#Style 02", "#Style 03", "#Style 04",
            "#Style 05", "#Style 07", "#Style 08", "#Style 12", "#Style 18",
        ],
        "forbidden_negative_tokens": [
            "photorealistic", "photograph", "photography", "35mm film", "cinematic film",
            "hyperrealistic", "lifelike skin", "film grain", "live action", "photo",
            "realistic lighting", "8k uhd", "masterpiece", "award-winning cinematography",
        ],
    },
    "stylized_3d": {
        "name": "Stylized 3D & 2.5D Animation",
        "style_codes": ["#Style 06", "#Style 09", "#Style 10", "#Style 11"],
        "forbidden_negative_tokens": [
            "cartoonish 3d", "cartoonish 3d render", "3d render look", "3d render", "cgi render",
            "stylized 3d", "3d animation", "3d cartoon", "cartoon", "illustration", "anime",
            "pixar", "dreamworks", "arcane", "hextech", "subsurface scattering",
            "cgi", "computer graphics", "3d model", "animation",
        ],
    },
    "stop_motion": {
        "name": "Stop-Motion & Miniature Craft",
        "style_codes": ["#Style 13"],
        "forbidden_negative_tokens": [
            "clay textures", "clay", "plasticine", "stop-motion", "stop motion", "miniature",
            "armature", "fingerprint", "felt", "puppet", "hand-crafted miniature", "stepped motion",
            "cartoon", "illustration", "3d cartoon", "anime", "3d render look",
        ],
    },
    "anime_2d": {
        "name": "2D Animation, Anime & Graphic Novel",
        "style_codes": ["#Style 14", "#Style 15", "#Style 16", "#Style 17"],
        "forbidden_negative_tokens": [
            "anime cel shading", "anime", "cel shading", "cel-shading", "hand-drawn",
            "2d animation", "line art", "manga", "watercolor", "ghibli", "graphic novel",
            "sketch", "comic book art", "2d", "ink wash", "ink line art",
            "cartoon", "illustration",
        ],
    },
}


def get_style_family(style_code: str) -> str:
    """Resolve active style code into one of the 4 canonical Style Taxonomy Families."""
    cleaned = (style_code or "").strip().upper()
    for fam_key, fam_data in STYLE_TAXONOMY_FAMILIES.items():
        if any(cleaned == sc.upper() for sc in fam_data["style_codes"]):
            return fam_key
    return "photorealistic"


def sanitize_negative_prompts_for_style(
    negative_prompts: list[str],
    style_code: str,
) -> list[str]:
    """Deterministically strips style-contradicting tokens from negative prompt clusters
    based on the 4-family Style Taxonomy so that desired style traits are never excluded."""
    family = get_style_family(style_code)
    forbidden = STYLE_TAXONOMY_FAMILIES.get(family, {}).get("forbidden_negative_tokens", [])

    sanitized_clusters: list[str] = []
    for cluster in negative_prompts:
        if not cluster or not isinstance(cluster, str):
            continue
        tokens = [t.strip() for t in cluster.split(",") if t.strip()]
        kept_tokens = []
        for t in tokens:
            t_lower = t.lower()
            has_conflict = False
            for fb in forbidden:
                if fb in t_lower:
                    if family == "anime_2d" and fb == "cartoon" and "3d" in t_lower:
                        continue
                    if family == "photorealistic" and fb == "photo" and t_lower in ("passport photo", "id photo"):
                        continue
                    has_conflict = True
                    break
            if not has_conflict:
                kept_tokens.append(t)

        if kept_tokens:
            sanitized_clusters.append(", ".join(kept_tokens))

    return sanitized_clusters


# ==============================================================================
# Structured Slugline Parser & Style Writing Directives
# ==============================================================================

_SLUG_SETTING_RE = re.compile(
    r"^\s*(?P<setting>(?:INT\.?\s*/\s*EXT\.?|EXT\.?\s*/\s*INT\.?|I\s*/\s*E\.?|INT\.?|EXT\.?))(?=\s|$)(?P<rest>.*)$",
    re.IGNORECASE,
)
_SLUG_TIME_WORD_RE = re.compile(
    r"\b(?:DAY|NIGHT|DAWN|DUSK|TWILIGHT|SUNRISE|SUNSET|MORNING|AFTERNOON|"
    r"EVENING|MIDNIGHT|NOON|LATER|CONTINUOUS|MOMENTS|FLASHBACK|HOUR|"
    r"SAME\s+TIME|PRESENT|DREAM|STORMY|RAINY|OVERCAST)\b",
    re.IGNORECASE,
)

STYLE_FAMILY_WRITING_DIRECTIVES: dict[str, str] = {
    "photorealistic": "Sparse-to-moderate naturalistic restraint (1.8-2.5 wps), 75% unspoken behavioral subtext, sensory foley & J/L-cut bridges.",
    "stylized_3d": "Crisp rhythmic banter (2.2-2.8 wps), pose-to-pose silhouette & prop kineticism, 60% subtext with 3-5s visual shifts.",
    "stop_motion": "Economical deadpan brevity (1.6-2.2 wps), tight miniature diorama materiality, tactile analog foley & stepped holds.",
    "anime_2d": "High-contrast cadence ('ma' atmospheric stillness vs staccato declarations), graphic keyframe beats & L-cut ambient holds.",
}

COVERAGE_STYLE_PRESETS: dict[str, dict[str, Any]] = {
    "classic_coverage": {
        "id": "classic_coverage",
        "label": "Classic Coverage",
        "description": "Establishing Master -> Medium / OTS Dialogue -> Close-Up emotional punch.",
        "shot_blueprints": [
            {"camera_code": "#Cam 04", "lens_code": "#Lens 01", "comp_code": "#Comp 01", "transition_type": "J_CUT"},
            {"camera_code": "#Cam 07", "lens_code": "#Lens 02", "comp_code": "#Comp 05", "transition_type": "L_CUT"},
            {"camera_code": "#Cam 02", "lens_code": "#Lens 03", "comp_code": "#Comp 03", "transition_type": "HARD_CUT"},
        ],
    },
    "visceral_oner": {
        "id": "visceral_oner",
        "label": "Visceral Oner",
        "description": "Unbroken kinetic tracking long take sustaining continuous tension.",
        "single_shot": True,
        "shot_blueprints": [
            {"camera_code": "#Cam 18", "lens_code": "#Lens 04", "comp_code": "#Comp 04", "transition_type": "J_CUT"},
        ],
    },
    "rapid_montage": {
        "id": "rapid_montage",
        "label": "Rapid Montage",
        "description": "High-tempo kinetic micro-cuts for visceral action, prop reveals, or crisis escalation.",
        "shot_blueprints": [
            {"camera_code": "#Cam 19", "lens_code": "#Lens 04", "comp_code": "#Comp 03", "transition_type": "J_CUT"},
            {"camera_code": "#Cam 23", "lens_code": "#Lens 02", "comp_code": "#Comp 02", "transition_type": "HARD_CUT"},
            {"camera_code": "#Cam 01", "lens_code": "#Lens 05", "comp_code": "#Comp 04", "transition_type": "HARD_CUT"},
            {"camera_code": "#Cam 25", "lens_code": "#Lens 03", "comp_code": "#Comp 01", "transition_type": "L_CUT"},
        ],
    },
    "intimate_subtext": {
        "id": "intimate_subtext",
        "label": "Intimate Subtext",
        "description": "Restrained close-ups, reaction holds, and L-Cut silence isolating inner conflict.",
        "shot_blueprints": [
            {"camera_code": "#Cam 03", "lens_code": "#Lens 03", "comp_code": "#Comp 01", "transition_type": "L_CUT"},
            {"camera_code": "#Cam 02", "lens_code": "#Lens 05", "comp_code": "#Comp 02", "transition_type": "L_CUT"},
            {"camera_code": "#Cam 01", "lens_code": "#Lens 03", "comp_code": "#Comp 03", "transition_type": "J_CUT"},
        ],
    },
}

_STYLE_FAMILY_OPTICS_DEFAULTS: dict[str, dict[str, str]] = {
    "photorealistic": {"light_code": "#Light 03", "act_code": "#Act 01", "speed_code": "#Speed 03"},
    "stylized_3d": {"light_code": "#Light 01", "act_code": "#Act 06", "speed_code": "#Speed 04"},
    "stop_motion": {"light_code": "#Light 05", "act_code": "#Act 04", "speed_code": "#Speed 01"},
    "anime_2d": {"light_code": "#Light 06", "act_code": "#Act 02", "speed_code": "#Speed 02"},
}


def parse_structured_slugline(raw: str) -> dict[str, str]:
    """Parse a screenplay slugline into setting, location, time_of_day, and canonical normalized string."""
    cleaned = re.sub(r"\s+", " ", (raw or "").strip())
    if not cleaned:
        return {"setting": "", "location": "", "time_of_day": "", "normalized": ""}

    match = _SLUG_SETTING_RE.match(cleaned)
    if match:
        raw_setting = re.sub(r"\s+", "", match.group("setting").upper())
        if raw_setting.startswith("INT") and "EXT" in raw_setting:
            setting = "EXT./INT." if raw_setting.startswith("EXT") else "INT./EXT."
        elif raw_setting in ("I/E", "I/E."):
            setting = "I/E"
        elif raw_setting.startswith("INT"):
            setting = "INT."
        else:
            setting = "EXT."
        remainder = match.group("rest").strip()
    else:
        setting = ""
        remainder = cleaned

    remainder = re.sub(r"\s*(?:--+|—|–)\s*", " - ", remainder)
    parts = [p.strip().upper() for p in re.split(r"\s+-\s+", remainder) if p.strip()]

    location = ""
    time_of_day = ""
    if len(parts) == 1:
        location = parts[0]
    elif len(parts) >= 2:
        if _SLUG_TIME_WORD_RE.search(parts[-1]):
            location = " - ".join(parts[:-1])
            time_of_day = parts[-1]
        else:
            location = " - ".join(parts)

    prefix_loc = f"{setting} {location}".strip() if (setting or location) else ""
    normalized = f"{prefix_loc} - {time_of_day}" if (prefix_loc and time_of_day) else (prefix_loc or time_of_day)
    return {
        "setting": setting,
        "location": location,
        "time_of_day": time_of_day,
        "normalized": normalized,
    }



# ==============================================================================
# Domain Schemas & Contracts
# ==============================================================================

class SceneBlueprintItem(BaseModel):
    """Individual scene blueprint unit generated by Polya AI Screenwriter."""

    scene_number: int = Field(ge=1, description="Scene sequence number")
    slugline: str = Field(description="Screenplay slugline (e.g. EXT. LOCATION - TIME)")
    narrative_goal: str = Field(description="Dramatic objective and character beat")
    dialogue: str = Field(default="", description="Calibrated dialogue line or SFX cue")
    speaking_character: str = Field(default="", description="Name of character speaking")
    is_fallback: bool = Field(default=False)


class ActBlueprintData(BaseModel):
    """Act-level blueprint with chunked scenes and narrative continuity summary."""

    act_number: int = Field(ge=1, le=5)
    start_scene: int
    end_scene: int
    scenes_count: int
    act_summary: str
    used_fallback: bool = False
    scenes: list[SceneBlueprintItem]


class ActTreatmentItem(BaseModel):
    act_number: int = Field(ge=1, le=5)
    act_title: str
    start_scene: int
    end_scene: int
    dramatic_goal: str
    key_beat: str


class MasterTreatmentData(BaseModel):
    """Phase A Master Story Treatment produced by Polya AI Screenwriter."""

    title: str
    logline: str
    theme: str
    dramatic_premise: str
    total_scenes: int
    structure_type: str = "4_act"
    structure_name: str = "Hollywood 4-Act Structure"
    acts: list[ActTreatmentItem] = Field(min_length=3, max_length=5)
    act_summaries: dict[str, str] = Field(default_factory=dict)
    cold_open_30s: dict[str, Any] | None = None
    used_fallback: bool = False
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


STRUCTURE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "3_act": {
        "structure_type": "3_act",
        "label": "Classic 3-Act Structure",
        "acts_count": 3,
        "description": "Aristotelian dramatic progression: Setup (25%), Confrontation (50%), Resolution (25%). Ideal for character-driven dramas, indie films, and focused narratives.",
        "act_labels": [
            {"act_number": 1, "title": "Act I: Setup & Catalyst", "percentage": "25%"},
            {"act_number": 2, "title": "Act II: Confrontation & Ordeal", "percentage": "50%"},
            {"act_number": 3, "title": "Act III: Climax & Resolution", "percentage": "25%"},
        ],
    },
    "4_act": {
        "structure_type": "4_act",
        "label": "Hollywood 4-Act Structure",
        "acts_count": 4,
        "description": "Industry-standard Save the Cat / Midpoint Split for high-concept blockbusters, action thrillers, and commercial feature films.",
        "act_labels": [
            {"act_number": 1, "title": "Act I: Setup & Catalyst", "percentage": "25%"},
            {"act_number": 2, "title": "Act II-A: Rising Stakes & Trials", "percentage": "25%"},
            {"act_number": 3, "title": "Act II-B: Dark Night & Crisis", "percentage": "25%"},
            {"act_number": 4, "title": "Act III & IV: Climax & Resolution", "percentage": "25%"},
        ],
    },
    "youtube_viral": {
        "structure_type": "youtube_viral",
        "label": "YouTube Viral / High-Retention Structure",
        "acts_count": 4,
        "description": "Fast-paced episodic retention structure: 0-10s Shock Hook, Rapid Chaos Escalation, Climax Twist, and Abrupt Cliffhanger. Ideal for web shorts, kids animation, and viral storytelling.",
        "act_labels": [
            {"act_number": 1, "title": "Part 1: In-Media-Res Teaser & Shock Hook", "percentage": "15%"},
            {"act_number": 2, "title": "Part 2: Escalating Chaos & Obstacles", "percentage": "35%"},
            {"act_number": 3, "title": "Part 3: Climax Confrontation & Twist", "percentage": "35%"},
            {"act_number": 4, "title": "Part 4: Cliffhanger & Call-to-Action", "percentage": "15%"},
        ],
    },
    "5_act": {
        "structure_type": "5_act",
        "label": "5-Act Dramatic Structure (Freytag's Pyramid)",
        "acts_count": 5,
        "description": "Classical theatrical progression: Exposition, Rising Action, Climax, Falling Action, and Catastrophe/Denouement. Ideal for epic fantasy, multi-faction political sagas, and tragedies.",
        "act_labels": [
            {"act_number": 1, "title": "Act I: Exposition & Inciting Incident", "percentage": "20%"},
            {"act_number": 2, "title": "Act II: Rising Action & Complication", "percentage": "20%"},
            {"act_number": 3, "title": "Act III: Climax & Turning Point", "percentage": "20%"},
            {"act_number": 4, "title": "Act IV: Falling Action & Counter-Stroke", "percentage": "20%"},
            {"act_number": 5, "title": "Act V: Catastrophe & Denouement", "percentage": "20%"},
        ],
    },
}


def get_act_bounds(total_scenes: int, structure_type: str = "4_act") -> list[tuple[int, int]]:
    """Calculate scene number bounds [start, end] for arbitrary scale targets (50-500) and structure types."""
    st = (structure_type or "4_act").lower().strip()
    if st == "3_act":
        ratios = [0.25, 0.50, 0.25]
    elif st in ("youtube_viral", "youtube", "viral"):
        ratios = [0.15, 0.35, 0.35, 0.15]
    elif st in ("5_act", "five_act"):
        ratios = [0.20, 0.20, 0.20, 0.20, 0.20]
    else:  # default "4_act"
        if total_scenes == 50:
            return [(1, 12), (13, 25), (26, 38), (39, 50)]
        ratios = [0.25, 0.25, 0.25, 0.25]

    num_acts = len(ratios)
    bounds: list[tuple[int, int]] = []
    cum = 0.0
    prev_end = 0
    for idx, r in enumerate(ratios):
        cum += r
        if idx == num_acts - 1:
            end = total_scenes
        else:
            end = max(prev_end + 1, int(round(total_scenes * cum)))
            remaining_acts = num_acts - 1 - idx
            if end > total_scenes - remaining_acts:
                end = total_scenes - remaining_acts
        bounds.append((prev_end + 1, end))
        prev_end = end
    return bounds


def _determine_scene_duration(act: int, duration_mode: str) -> float:
    """Determine duration based on pacing mode: dynamic Hollywood curve, flat_10s, flat_15s, flat_5s."""
    mode = (duration_mode or "dynamic").lower()
    if mode == "flat_10s":
        return 10.0
    elif mode == "flat_15s":
        return 15.0
    elif mode == "flat_5s":
        return 5.0
    elif mode == "dynamic":
        # Hollywood cinematic pacing curve across acts 1 to 5:
        # Odd acts (1, 3, 5): Exposition, character depth, and emotional descent -> 15.0s
        # Even acts (2, 4): Rising tension, trials, and climactic action -> 10.0s
        return 15.0 if act % 2 == 1 else 10.0
    return 10.0

class ProjectNarrativeContext(BaseModel):
    """Complete narrative and aesthetic context extracted from SQLite."""

    project_id: str
    title: str
    synopsis: str
    genre_tone: str
    master_style_code: str
    style_name: str
    aesthetic_directives: str
    color_grade_emulation: str
    world_setting: str
    continuity_rules: list[str] = Field(default_factory=list)
    visual_dna_parameters: dict[str, Any] = Field(default_factory=dict)
    environments_summary: str = ""
    props_summary: str = ""
    environments: list[dict[str, Any]] = Field(default_factory=list)
    props: list[dict[str, Any]] = Field(default_factory=list)
    # Deep Ingestion Extensions
    aspect_ratio: str = "16:9"
    operational_stage: int = 1
    cast_characters: list[dict[str, Any]] = Field(default_factory=list)
    storyboard_scenes: list[dict[str, Any]] = Field(default_factory=list)
    ranked_locations: list[tuple[str, int]] = Field(default_factory=list)


class CharacterStateData(BaseModel):
    """Dynamic physical state and costume evolution across scenes."""

    state_number: int = Field(ge=1, le=5)
    state_label: str
    wardrobe: str
    physical_damage: str = ""
    emotional_anchor: str = ""

    @field_validator("state_label", mode="before")
    @classmethod
    def sanitize_label(cls, v: Any) -> str:
        s = str(v or "").strip()
        return s or "Baseline State"


class CharacterData(BaseModel):
    """Character identity, narrative function, biometric prompt, and 5-state matrix."""

    name: str
    role: str
    narrative_summary: str = ""
    base_visual_prompt: str
    voice_dna_profile: str = ""
    states: list[CharacterStateData] = Field(min_length=5, max_length=5)

    @field_validator("role", mode="before")
    @classmethod
    def uppercase_role(cls, v: Any) -> str:
        s = str(v or "PROTAGONIST").strip().upper()
        # Clean common prefixes/suffixes
        s = re.sub(r"[^A-Z_]", "", s)
        return s or "SUPPORTING"


class CastEnsembleData(BaseModel):
    """Batch ensemble cast designed by Polya AI Screenwriter (5 to 8 characters)."""

    cast_rationale: str = ""
    characters: list[CharacterData] = Field(min_length=5, max_length=8)


# ==============================================================================
# Context Extractor
# ==============================================================================

def extract_project_narrative_context(
    project: Any,
    bible: Any = None,
    characters: list[Any] | None = None,
    scenes: list[Any] | None = None,
) -> ProjectNarrativeContext:
    """Extract complete narrative context from SQLite models with key-resilient fallbacks."""
    title = (getattr(project, "title", None) or "").strip()

    settings = project.settings if isinstance(getattr(project, "settings", None), dict) else {}
    treatment = settings.get("treatment") if isinstance(settings.get("treatment"), dict) else {}

    # Resilient synopsis extraction: check all known keys
    synopsis = (
        settings.get("synopsis")
        or settings.get("logline")
        or settings.get("description")
        or settings.get("premise")
        or treatment.get("logline")
        or treatment.get("synopsis")
        or treatment.get("theme")
        or ""
    )
    if isinstance(synopsis, dict):
        synopsis = json.dumps(synopsis)
    synopsis = str(synopsis).strip()

    if not title or not synopsis:
        raise ValueError(
            "Judul dan sinopsis proyek wajib diisi sebelum men-generate karakter dengan Polya AI Screenwriter."
        )

    genre_tone = (
        settings.get("genre")
        or settings.get("tone")
        or settings.get("category")
        or "Cinematic Film"
    )

    # Visual DNA parameters from MPB
    mpb_styles = bible.style_parameters if bible and isinstance(getattr(bible, "style_parameters", None), dict) else {}
    visual_dna_params = {
        k: v for k, v in mpb_styles.items()
        if k in ("render_pipeline", "film_stock", "anamorphic_squeeze", "aspect_ratio", "halation_level", "color_palette", "lighting_preset", "lens_code")
        and v is not None
    }
    style_code = (
        mpb_styles.get("master_style_code")
        or getattr(project, "target_style_code", None)
        or "#Style 01"
    )

    # Style catalog lookup
    catalog_entry = next((s for s in STYLE_CATALOG if s.get("code") == style_code), None) or STYLE_CATALOG[0]
    style_name = catalog_entry.get("name", "Hollywood Cinematic")
    aesthetic_directives = catalog_entry.get("aesthetic_directives", "")
    color_grade_emulation = catalog_entry.get("color_grade_emulation", "")

    # World rules lookup
    mpb_rules = bible.world_rules if bible and isinstance(getattr(bible, "world_rules", None), dict) else {}
    world_setting = (
        mpb_rules.get("setting")
        or mpb_rules.get("world_name")
        or mpb_rules.get("world_setting")
        or settings.get("setting")
        or "Cinematic Universe"
    )
    continuity_rules = mpb_rules.get("continuity_rules")
    if continuity_rules is None:
        continuity_rules = mpb_rules.get("continuity_laws", [])
    if not isinstance(continuity_rules, list):
        continuity_rules = [str(continuity_rules)]

    # Environments & props structured and summary
    envs_list = mpb_rules.get("environments", [])
    structured_envs = [e for e in envs_list if isinstance(e, dict)] if isinstance(envs_list, list) else []
    envs_summary = ""
    if structured_envs:
        envs_summary = ", ".join(
            f"{e.get('name', 'Env')}" for e in structured_envs[:5] if e.get("name")
        )

    props_list = mpb_rules.get("props", [])
    structured_props = [p for p in props_list if isinstance(p, dict)] if isinstance(props_list, list) else []
    props_summary = ""
    if structured_props:
        props_summary = ", ".join(
            f"{p.get('name', 'Prop')}" for p in structured_props[:5] if p.get("name")
        )

    # Ingest Characters Cast
    cast_characters: list[dict[str, Any]] = []
    if characters:
        for c in characters:
            if isinstance(c, dict):
                c_name = c.get("name")
                c_role = c.get("role", "PROTAGONIST")
                c_prof = c.get("narrative_profile") or c.get("narrative_summary") or ""
                c_voice = c.get("voice_dna_profile") or ""
                c_prompt = c.get("base_visual_prompt") or c.get("base_prompt") or ""
                c_states = c.get("states") or []
            else:
                c_name = getattr(c, "name", "")
                c_role = getattr(c, "role", "PROTAGONIST")
                meta = getattr(c, "sheet_metadata", {}) or {}
                c_prof = getattr(c, "narrative_summary", None) or meta.get("narrative_summary") or ""
                c_voice = getattr(c, "voice_dna_profile", None) or meta.get("voice_dna_profile") or ""
                c_prompt = getattr(c, "base_prompt", "")
                c_states = getattr(c, "states", [])

            formatted_states = []
            if isinstance(c_states, list):
                for s in c_states:
                    if isinstance(s, dict):
                        formatted_states.append({
                            "code": s.get("state_code") or s.get("code") or "#State 01",
                            "label": s.get("state_label") or s.get("label") or "",
                            "wardrobe": s.get("wardrobe") or "",
                            "wear": s.get("injuries_and_wear") or s.get("wear") or "",
                            "expression": s.get("expression_anchor") or s.get("expression") or s.get("emotional_anchor") or "",
                        })
                    else:
                        formatted_states.append({
                            "code": getattr(s, "state_code", "#State 01"),
                            "label": getattr(s, "state_label", "") or getattr(s, "state_code", ""),
                            "wardrobe": getattr(s, "wardrobe", ""),
                            "wear": getattr(s, "injuries_and_wear", ""),
                            "expression": getattr(s, "expression_anchor", "") or "",
                        })

            if c_name:
                cast_characters.append({
                    "name": c_name,
                    "role": c_role,
                    "narrative_profile": c_prof,
                    "voice_dna_profile": c_voice,
                    "base_visual_prompt": c_prompt,
                    "states": formatted_states,
                })

    # Ingest Storyboard Scenes & Sluglines
    storyboard_scenes: list[dict[str, Any]] = []
    slug_counts: dict[str, int] = {}
    if scenes:
        for sc in scenes:
            if isinstance(sc, dict):
                s_num = sc.get("scene_number", 1)
                a_num = sc.get("act_number", 1)
                slug = sc.get("slugline", "")
                goal = sc.get("narrative_goal", "")
            else:
                s_num = getattr(sc, "scene_number", 1)
                a_num = getattr(sc, "act_number", 1)
                slug = getattr(sc, "slugline", "")
                goal = getattr(sc, "narrative_goal", "")

            storyboard_scenes.append({
                "scene_number": s_num,
                "act_number": a_num,
                "slugline": slug,
                "narrative_goal": goal,
            })
            if slug:
                clean_slug = parse_structured_slugline(slug)["normalized"] or slug.strip().upper()
                slug_counts[clean_slug] = slug_counts.get(clean_slug, 0) + 1

    ranked_locations = sorted(slug_counts.items(), key=lambda x: x[1], reverse=True)

    aspect_ratio = getattr(project, "aspect_ratio", None) or "16:9"
    operational_stage = getattr(project, "operational_stage", 1) or 1

    return ProjectNarrativeContext(
        project_id=str(getattr(project, "id", "")),
        title=title,
        synopsis=synopsis,
        genre_tone=str(genre_tone),
        master_style_code=style_code,
        style_name=style_name,
        aesthetic_directives=aesthetic_directives,
        color_grade_emulation=color_grade_emulation,
        world_setting=str(world_setting),
        continuity_rules=[str(r) for r in continuity_rules if r],
        visual_dna_parameters=visual_dna_params,
        environments_summary=envs_summary,
        props_summary=props_summary,
        environments=structured_envs,
        props=structured_props,
        aspect_ratio=aspect_ratio,
        operational_stage=operational_stage,
        cast_characters=cast_characters,
        storyboard_scenes=storyboard_scenes,
        ranked_locations=ranked_locations,
    )


# ==============================================================================
# Seed Determinism Helper
# ==============================================================================

def generate_unique_deterministic_seed(
    project_id: str,
    name: str,
    existing_seeds: set[int] | None = None,
    salt: str = "",
) -> int:
    """Generate an integer DNA seed (6-digit, 100000-999999) with anti-collision guarantee."""
    used_seeds = existing_seeds if existing_seeds is not None else set()
    base_raw = f"{project_id}_{name}_{salt}_{time.time_ns()}"
    h = int(hashlib.sha256(base_raw.encode("utf-8")).hexdigest()[:8], 16)
    seed = (h % 900000) + 100000

    attempts = 0
    while seed in used_seeds and attempts < 100:
        base_raw += f"_{random.randint(1000, 999999)}"
        h = int(hashlib.sha256(base_raw.encode("utf-8")).hexdigest()[:8], 16)
        seed = (h % 900000) + 100000
        attempts += 1

    used_seeds.add(seed)
    return seed


# ==============================================================================
# Polya AI Screenwriter Engine
# ==============================================================================

POLYA_SCREENWRITER_SYSTEM_PROMPT = """You are Polya AI — Hollywood-Grade Master Screenwriter & Dramatic Story Architect.
You specialize in designing complete, emotionally resonant cinematic feature films, 4-Act screenplay treatments, scene-by-scene blueprints, and biometric character DNA.
Your principles:
1. Deep Narrative Symbiosis: Every scene, dialogue line, dramatic goal, and character action MUST directly serve the project's core dramatic question, world setting, and character arcs. Never invent generic cybernetic or fantasy cliches if they do not fit the universe.
2. Classical Hollywood 4-Act Dramaturgy:
   - Act I: Ordinary World setup, Inciting Incident, and irreversible Plot Point 1 threshold crossing.
   - Act II-A: Trials, rising stakes, and false victory/defeat at the Midpoint Reversal.
   - Act II-B: Descent, betrayal, systemic pressure, and the devastating All Is Lost crisis.
   - Act III/IV: Climax, philosophical reckonings, catharsis, and master resolution.
3. Dialogue Pacing & Calibration:
   - Dialogue must be tight, subtext-rich, and tailored to the scene's target duration.
   - For 5s scenes: maximum 14 words.
   - For 10s scenes: maximum 28 words.
   - For 15s scenes: maximum 42 words.
   - If non-verbal, provide vivid atmospheric sound design in brackets e.g. '[SFX: ...]'.
4. Cast Consistency: In scenes, strictly feature the assigned ensemble cast characters. Do not invent unrelated protagonist names when cast characters exist.
5. Biometric Distinctiveness: Detail precise bone structure, jawline, eye color, skin texture, hairstyle, signature costume, and physical posture so characters can be visually locked for 50+ scenes.
6. Studio Neutral Backdrop: Always end character base_visual_prompts with studio gray background framing: 'isolated on a flat seamless Neutral Matte Light-Medium Studio Gray (#D4D4D4) studio background, neutral studio illumination, zero environment props or color cast'.
7. Strict JSON Only: Output strictly valid JSON conforming to the requested schema. No commentary, markdown prose, or preamble outside the JSON.
8. Authentic & Contextual Naming: Character names, personas, and costumes MUST be 100% unique, freshly conceived, and culturally and aesthetically authentic to the specific universe and synopsis. Strictly avoid repeating generic stock names such as 'Kaelen', 'Thorne', 'Vane', 'Vance', 'Lyra', or 'Cipher'."""


POLYA_AI_DIRECTOR_SYSTEM_PROMPT = """You are Polya AI Director — Chief AI Film Producer & Hollywood Production Designer.
You possess world-class expertise in physical set architecture, cinematic lighting design (Kelvin, contrast ratios, volumetric physics), hero prop craftsmanship, and narrative tactile continuity.

Your core directives:
1. Strict Genre & Aesthetic Lock: You must adhere 100% to the project's Master Visual Style (#Style Code) and Color Grade/Film Emulation directives. Zero cross-genre contamination (e.g. zero sci-fi/cyberpunk artifacts in an Epic High Fantasy or Historical project).
2. DaVinci Obsidian Lighting Matrix Mandate: Every key environment (#Env 01 through #Env 05) MUST explicitly specify an official lighting code (#Light 01 through #Light 14) from the DaVinci Obsidian catalog, incorporating exact Kelvin color temperature, key-to-fill ratio, and volumetric light sources.
3. Audio Bed & Acoustic Bridge Readiness: Every environment MUST define concrete Room Tone & Acoustic Foley (supporting clean SNR >= 32 dB audio bed planning, J-Cut/L-Cut acoustic transitions, and ambient spatial reverbs).
4. Signature Hero Props Anchored to Cast: Every signature hero prop (#Prop 01 through #Prop 05) MUST be anchored to a specific character from the cast (or marked 'Ensemble / World Artifact' if plot-wide). Define concrete physical materials, dimensions, weathering/patina, battle scars, and specular/roughness cues for cross-shot visual continuity (CLIP >= 0.80, LAION >= 8.0/10).
5. Storyboard Slugline Binding: If storyboard scenes/sluglines are provided, environments MUST align with and canonize the primary recurring locations from the storyboard rather than inventing disconnected settings.
6. Strict Valid JSON: Output STRICT valid JSON conforming exactly to the requested schema. No commentary, markdown prose, or preamble outside the JSON."""


class PolyaScreenwriterEngine:
    """Domain service executing Polya AI Screenwriter LLM requests with resilient parsing."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ):
        settings = get_settings()
        self.base_url = base_url or settings.effective_llm_base_url
        self.api_key = api_key or settings.effective_llm_api_key
        self.model = model or settings.llm_model
        env_timeout = os.environ.get("LLM_TIMEOUT_SECONDS")
        if timeout is not None:
            self.timeout = timeout
        elif env_timeout:
            try:
                self.timeout = float(env_timeout)
            except ValueError:
                self.timeout = getattr(settings, "llm_timeout_seconds", 120.0)
        else:
            self.timeout = getattr(settings, "llm_timeout_seconds", 120.0)

    async def _call_llm(
        self,
        messages: list[dict[str, str]],
        retry_on_parse_error: bool = True,
    ) -> dict[str, Any]:
        """Execute chat completion request with JSON format enforcement and 1x auto-retry."""
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.75,
            "stream": False,
        }

        raw_content = ""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    raise RuntimeError(
                        f"Polya AI LLM returned HTTP {resp.status_code}: {resp.text[:300]}"
                    )
                data = resp.json()
                raw_content = data["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.error("Polya AI completion network error: %s", exc)
            raise RuntimeError(f"Polya AI Screenwriter call failed: {exc}") from exc

        parsed = self._clean_and_parse_json(raw_content)
        if parsed is not None:
            return parsed

        # Auto-retry 1x if parse failed
        if retry_on_parse_error:
            logger.warning("Polya AI returned invalid JSON. Attempting 1x structured repair retry.")
            repair_messages = list(messages)
            repair_messages.append({"role": "assistant", "content": raw_content})
            repair_messages.append({
                "role": "user",
                "content": "Your previous output was not valid JSON. Fix formatting immediately and output STRICT valid JSON only with no trailing commas or commentary.",
            })
            return await self._call_llm(repair_messages, retry_on_parse_error=False)

        raise ValueError(f"Could not parse valid JSON from Polya AI response: {raw_content[:400]}")

    def _clean_and_parse_json(self, raw_str: str) -> dict[str, Any] | None:
        """Strip markdown fences, trailing commas, and parse JSON safely."""
        text = raw_str.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        # Direct parse attempt
        try:
            val = json.loads(text)
            if isinstance(val, dict):
                return val
        except Exception:
            pass

        # Regex extract between first { and last }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = text[start : end + 1]
            # Remove trailing commas before closing braces/brackets
            cleaned = re.sub(r",\s*([\]}])", r"\1", snippet)
            try:
                val = json.loads(cleaned)
                if isinstance(val, dict):
                    return val
            except Exception:
                pass

        return None

    async def _fetch_voice_rag_block(
        self,
        context: ProjectNarrativeContext,
        roles: list[str] | str | None = None,
    ) -> str:
        """Fetch Voice DNA & 5-State Arc guidance from Screenwriter RAG (graceful empty fallback)."""
        rag_res = await ScreenwriterRAGClient.retrieve_character_voice(
            style_code=context.master_style_code,
            genre_tone=context.genre_tone,
            roles=roles,
            top_k=3,
        )
        block = str(rag_res.get("prompt_block") or "").strip()
        return f"\n{block}\n" if block else ""

    async def generate_cast_ensemble(
        self,
        context: ProjectNarrativeContext,
        preferred_count: int | None = None,
        additional_notes: str | None = None,
    ) -> CastEnsembleData:
        """Generate a complete ensemble of 5 to 8 characters with 5 dynamic states per character."""
        count_instruction = (
            f"Generate exactly {preferred_count} characters as requested."
            if preferred_count and 5 <= preferred_count <= 8
            else "Determine the most dramatic ensemble size between 5 and 8 characters (inclusive: 5, 6, 7, or 8 characters). Exactly 1 PROTAGONIST, exactly 1 ANTAGONIST, plus 3 to 6 essential supporting roles (e.g. DEUTERAGONIST, MENTOR, ALLY, FOIL, CATALYST)."
        )

        dna_items = []
        if context.visual_dna_parameters:
            for k, v in context.visual_dna_parameters.items():
                dna_items.append(f"{k.replace('_', ' ').title()}: {v}")
        dna_str = f"- Visual DNA Parameters: {', '.join(dna_items)}" if dna_items else ""
        env_str = f"- World Key Environments: {context.environments_summary}" if context.environments_summary else ""
        prop_str = f"- World Hero Props: {context.props_summary}" if context.props_summary else ""
        voice_rag_block = await self._fetch_voice_rag_block(
            context,
            roles=["PROTAGONIST", "ANTAGONIST", "MENTOR/ALLY", "SHADOW/WILDCARD"],
        )

        user_prompt = f"""PROJECT PRODUCTION BIBLE & NARRATIVE CONTEXT:
- Film Title: {context.title}
- Core Synopsis & Premise:
{context.synopsis}
- Master Genre & Tone: {context.genre_tone}
- Master Visual Style Code: {context.master_style_code} ({context.style_name})
- Visual Style Directives: {context.aesthetic_directives}
- Color Palette & Lighting Emulation: {context.color_grade_emulation}
{dna_str}
- World Setting: {context.world_setting}
{env_str}
{prop_str}
- Production Continuity Rules: {', '.join(context.continuity_rules) if context.continuity_rules else 'Standard Cinematic Rules'}
- Additional Showrunner Notes: {additional_notes or 'None'}
{voice_rag_block}
CASTING & CHARACTER DESIGN MANDATE:
1. {count_instruction}
2. Exactly 1 character must have role: "PROTAGONIST" (the primary point-of-view hero).
3. Exactly 1 character must have role: "ANTAGONIST" (primary force of opposition).
4. Remaining characters must have vital dramatic roles: "DEUTERAGONIST", "MENTOR", "ALLY", "FOIL", or "CATALYST".
5. Every character's base_visual_prompt must describe exact age, ethnicity, facial bone structure, distinct eye color, scars/tattoos, hairstyle, and signature costume matching the film's world. Must end with: 'isolated on a flat seamless Neutral Matte Light-Medium Studio Gray (#D4D4D4) studio background, neutral studio illumination, zero environment props or color cast'.
6. Every character must have exactly 5 dynamic state evolution stages (state_number 1 to 5) reflecting their emotional and physical arc in this story:
   - State 1: Normal Baseline
   - State 2: Early Fatigue & Wear
   - State 3: Crisis / Battle Damaged
   - State 4: Severe Psychological Fracture
   - State 5: Climax / Metamorphosis
7. DIVERSE & AUTHENTIC NAMING: Character names must be fresh, creative, and culturally/aesthetically authentic to '{context.title}' and its setting. Do not reuse generic archetype names.

OUTPUT SCHEMA (Return strictly this JSON structure):
{{
  "cast_rationale": "2-3 sentences explaining why this ensemble creates peak narrative tension for this film.",
  "characters": [
    {{
      "name": "Culturally authentic character name matching setting",
      "role": "PROTAGONIST | ANTAGONIST | DEUTERAGONIST | MENTOR | ALLY | FOIL | CATALYST",
      "narrative_summary": "1-2 sentences on their specific narrative function in the synopsis.",
      "base_visual_prompt": "Continuous single paragraph biometric prompt ending with studio gray backdrop.",
      "voice_dna_profile": "Vocal timbre, pitch, cadence, and acoustic texture tailored to this character persona.",
      "states": [
        {{
          "state_number": 1,
          "state_label": "Normal Baseline",
          "wardrobe": "Detailed pristine costume description for opening scenes",
          "physical_damage": "Zero defects, pristine posture",
          "emotional_anchor": "Micro-expression and eye gaze description"
        }},
        {{
          "state_number": 2,
          "state_label": "Contextual state label reflecting story wear",
          "wardrobe": "Costume wear and tear",
          "physical_damage": "Early fatigue, sweat, soot, or light scratches",
          "emotional_anchor": "Vigilant scanning"
        }},
        {{
          "state_number": 3,
          "state_label": "Contextual state label reflecting midpoint crisis",
          "wardrobe": "Torn fabric, damaged accessories",
          "physical_damage": "Visible cuts, contusions, stained clothes",
          "emotional_anchor": "Adrenaline-fueled defiance"
        }},
        {{
          "state_number": 4,
          "state_label": "Contextual state label reflecting psychological strain",
          "wardrobe": "Disheveled, shredded garments",
          "physical_damage": "Severe exhaustion, grimed skin, bloodied brow",
          "emotional_anchor": "Traumatized resolve transitioning to lethal focus"
        }},
        {{
          "state_number": 5,
          "state_label": "Contextual state label reflecting climax / awakening",
          "wardrobe": "Final battle state or transformed wardrobe",
          "physical_damage": "Heroic battle patina, peak wear",
          "emotional_anchor": "Transcendent clarity, absolute catharsis"
        }}
      ]
    }}
  ]
}}"""

        messages = [
            {"role": "system", "content": POLYA_SCREENWRITER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        raw_json = await self._call_llm(messages)
        return self._normalize_cast_ensemble(raw_json, context)

    async def generate_one_character(
        self,
        context: ProjectNarrativeContext,
        sibling_characters: list[dict[str, Any]],
        preferred_role: str | None = None,
        custom_directive: str | None = None,
    ) -> CharacterData:
        """Generate exactly 1 new complementary ensemble character adhering to sibling anti-duplication."""
        siblings_summary = "\n".join(
            f"- {c.get('name')} (Role: {c.get('role')}): {c.get('base_prompt', '')[:120]}..."
            for c in sibling_characters
        ) or "None (First character in project)"

        dna_items = []
        if context.visual_dna_parameters:
            for k, v in context.visual_dna_parameters.items():
                dna_items.append(f"{k.replace('_', ' ').title()}: {v}")
        dna_str = f"\n- Visual DNA Parameters: {', '.join(dna_items)}" if dna_items else ""
        env_str = f"\n- World Key Environments: {context.environments_summary}" if context.environments_summary else ""
        prop_str = f"\n- World Hero Props: {context.props_summary}" if context.props_summary else ""
        voice_rag_block = await self._fetch_voice_rag_block(context, roles=preferred_role or "SUPPORTING")

        user_prompt = f"""PROJECT PRODUCTION BIBLE & NARRATIVE CONTEXT:
- Film Title: {context.title}
- Core Synopsis & Premise:
{context.synopsis}
- Master Genre & Tone: {context.genre_tone}
- Master Visual Style Code: {context.master_style_code} ({context.style_name}){dna_str}
- World Setting: {context.world_setting}{env_str}{prop_str}
{voice_rag_block}
EXISTING SIBLING CAST IN ENSEMBLE (ANTI-DUPLICATION REGISTRY):
{siblings_summary}

MANDATE FOR THIS SINGLE CHARACTER:
1. Create exactly 1 brand new, distinct character that complements the existing cast.
2. STRICT ANTI-DUPLICATION: DO NOT reuse any sibling character names, do not duplicate existing roles, and ensure strong visual contrast (contrasting age, silhouette, face structure, wardrobe palette).
3. Preferred Role: {preferred_role or 'A vital supporting role (DEUTERAGONIST, MENTOR, ALLY, FOIL, or CATALYST) needed by the synopsis'}.
4. Additional Showrunner Directive: {custom_directive or 'None'}.
5. Must include base_visual_prompt ending with '#D4D4D4' studio backdrop directive and exactly 5 dynamic states (#State 01 to #State 05).

OUTPUT SCHEMA (Return strictly this JSON object):
{{
  "name": "Unique Name",
  "role": "PROTAGONIST | ANTAGONIST | DEUTERAGONIST | MENTOR | ALLY | FOIL | CATALYST",
  "narrative_summary": "1-2 sentences on their specific narrative function.",
  "base_visual_prompt": "Continuous single paragraph biometric prompt ending with studio gray backdrop.",
  "voice_dna_profile": "Vocal timbre, pitch, cadence, and acoustic texture.",
  "states": [
    {{
      "state_number": 1,
      "state_label": "Normal Baseline",
      "wardrobe": "Pristine opening wardrobe",
      "physical_damage": "None",
      "emotional_anchor": "Expression anchor"
    }},
    {{ "state_number": 2, "state_label": "Fatigue & Wear", "wardrobe": "...", "physical_damage": "...", "emotional_anchor": "..." }},
    {{ "state_number": 3, "state_label": "Crisis Damage", "wardrobe": "...", "physical_damage": "...", "emotional_anchor": "..." }},
    {{ "state_number": 4, "state_label": "Psychological Fracture", "wardrobe": "...", "physical_damage": "...", "emotional_anchor": "..." }},
    {{ "state_number": 5, "state_label": "Climax / Metamorphosis", "wardrobe": "...", "physical_damage": "...", "emotional_anchor": "..." }}
  ]
}}"""

        messages = [
            {"role": "system", "content": POLYA_SCREENWRITER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        raw_json = await self._call_llm(messages)
        return self._normalize_single_character(raw_json, context, default_role=preferred_role or "SUPPORTING")

    async def regenerate_single_character(
        self,
        context: ProjectNarrativeContext,
        target_character: dict[str, Any],
        sibling_characters: list[dict[str, Any]],
        preserve_role: bool = True,
        custom_directive: str | None = None,
    ) -> CharacterData:
        """Regenerate an existing character with anti-duplication against siblings and avoidance of old version."""
        siblings_summary = "\n".join(
            f"- {c.get('name')} (Role: {c.get('role')}): {c.get('base_prompt', '')[:120]}..."
            for c in sibling_characters
            if str(c.get("id")) != str(target_character.get("id"))
        ) or "None (Isolated character)"

        current_role = target_character.get("role") or "PROTAGONIST"
        current_name = target_character.get("name") or "Character"

        dna_items = []
        if context.visual_dna_parameters:
            for k, v in context.visual_dna_parameters.items():
                dna_items.append(f"{k.replace('_', ' ').title()}: {v}")
        dna_str = f"\n- Visual DNA Parameters: {', '.join(dna_items)}" if dna_items else ""
        env_str = f"\n- World Key Environments: {context.environments_summary}" if context.environments_summary else ""
        prop_str = f"\n- World Hero Props: {context.props_summary}" if context.props_summary else ""
        voice_rag_block = await self._fetch_voice_rag_block(context, roles=current_role)

        user_prompt = f"""PROJECT PRODUCTION BIBLE & NARRATIVE CONTEXT:
- Film Title: {context.title}
- Core Synopsis & Premise:
{context.synopsis}
- Master Genre & Tone: {context.genre_tone}
- Master Visual Style Code: {context.master_style_code} ({context.style_name}){dna_str}
- World Setting: {context.world_setting}{env_str}{prop_str}
{voice_rag_block}
TARGET CHARACTER TO REGENERATE & REPLACE:
- Current Name to Replace: {current_name}
- Current Role: {current_role}
- Preserve Same Role?: {'YES (Must keep role: ' + current_role + ')' if preserve_role else 'NO (Polya AI may redefine role if dramatics require)'}
- Previous Description: {target_character.get('base_prompt', '')[:200]}

SIBLING CHARACTERS IN SAME PROJECT (ANTI-DUPLICATION REGISTRY):
{siblings_summary}

MANDATE FOR REGENERATION:
1. Design a completely fresh, exciting new concept for this character slot.
2. DO NOT simply reuse the previous name '{current_name}' or repeat the exact previous visual concept.
3. STRICT ANTI-DUPLICATION: DO NOT collide with sibling characters in name, role, or biometric traits.
4. Additional Showrunner Directive: {custom_directive or 'None'}.
5. Must include base_visual_prompt ending with '#D4D4D4' studio backdrop directive and exactly 5 dynamic states (#State 01 to #State 05).

OUTPUT SCHEMA (Return strictly this JSON object):
{{
  "name": "New Fresh Name",
  "role": "{current_role if preserve_role else 'PROTAGONIST | ANTAGONIST | DEUTERAGONIST | MENTOR | ALLY | FOIL | CATALYST'}",
  "narrative_summary": "1-2 sentences on their specific narrative function.",
  "base_visual_prompt": "Continuous single paragraph biometric prompt ending with studio gray backdrop.",
  "voice_dna_profile": "Vocal timbre, pitch, cadence, and acoustic texture.",
  "states": [
    {{ "state_number": 1, "state_label": "Normal Baseline", "wardrobe": "...", "physical_damage": "...", "emotional_anchor": "..." }},
    {{ "state_number": 2, "state_label": "Fatigue & Wear", "wardrobe": "...", "physical_damage": "...", "emotional_anchor": "..." }},
    {{ "state_number": 3, "state_label": "Crisis Damage", "wardrobe": "...", "physical_damage": "...", "emotional_anchor": "..." }},
    {{ "state_number": 4, "state_label": "Psychological Fracture", "wardrobe": "...", "physical_damage": "...", "emotional_anchor": "..." }},
    {{ "state_number": 5, "state_label": "Climax / Metamorphosis", "wardrobe": "...", "physical_damage": "...", "emotional_anchor": "..." }}
  ]
}}"""

        messages = [
            {"role": "system", "content": POLYA_SCREENWRITER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        raw_json = await self._call_llm(messages)
        expected_role = current_role if preserve_role else "SUPPORTING"
        return self._normalize_single_character(raw_json, context, default_role=expected_role)

    async def generate_world_prop_variations(
        self,
        context: ProjectNarrativeContext,
        item_type: Literal["environment", "prop"],
        code: str,
        current_item: dict[str, Any] | None = None,
        additional_notes: str | None = None,
    ) -> list[dict[str, Any]]:
        """Generate 3 distinct selectable variations for a single environment or prop.

        Uses the Polya AI Director RAG bridge (8765, strict 1.5s timeout) for cinematic
        grounding, then the Screenwriter LLM for creative divergence. Any RAG/LLM failure
        degrades gracefully to a style-family-aware procedural 3-variation fallback so the
        endpoint always returns exactly 3 selectable options.
        """
        resolved_type: Literal["environment", "prop"] = (
            "prop" if str(item_type).lower().strip() == "prop" else "environment"
        )
        default_code = "#Env 01" if resolved_type == "environment" else "#Prop 01"
        resolved_code = (code or default_code).strip() or default_code
        item = dict(current_item or {})
        item_name = str(item.get("name") or "").strip()

        rag_result = await DirectorRAGClient.retrieve(
            scene_beat=(
                f"{context.title} {resolved_type} variation for {resolved_code}"
                f"{f' ({item_name})' if item_name else ''}: {additional_notes or context.genre_tone}"
            ),
            style_code=context.master_style_code,
            engine="9router",
            top_k=3,
        )
        rag_blocks = [
            str(rag_result.get("director_context") or "").strip()[:700],
            DirectorRAGClient.format_treatment_grammar(rag_result),
            DirectorRAGClient.format_act_context(rag_result),
        ]
        rag_block = "\n".join(b for b in rag_blocks if b).strip()

        fallback = self._procedural_world_prop_variations(
            context=context,
            item_type=resolved_type,
            code=resolved_code,
            current_item=item,
        )

        labels = [
            ("Atmospheric / Moody", "atmospheric_moody"),
            ("Architectural / Grand Scale", "architectural_grand_scale"),
            ("Tactile / Intimate Detail", "tactile_intimate_detail"),
        ]

        if resolved_type == "environment":
            schema_block = """Each variation MUST contain:
- code: the exact provided environment code
- name: evocative, distinct environment name
- lighting_code: canonical '#Light 01'..'#Light 14'
- visual_description: architecture, spatial scale, materials, atmosphere, airborne particles
- ambient_foley: room tone, reverb, spatial Foley bed
- label: the variation label provided
- rationale: one sentence explaining the dramatic intent"""
        else:
            schema_block = """Each variation MUST contain:
- code: the exact provided prop code
- name: distinct, story-critical hero prop name
- dramatic_significance: exact narrative function across the arc
- visual_details: materials, craftsmanship, wear, patina, tactile interaction
- label: the variation label provided
- rationale: one sentence explaining the dramatic intent"""

        user_prompt = f"""SINGLE-ITEM VARIATION BRIEF (Polya AI Director)
- Project: {context.title}
- Synopsis: {context.synopsis[:600]}
- Genre / Tone: {context.genre_tone}
- Master Style: {context.master_style_code} ({context.style_name})
- Aesthetic Directives: {context.aesthetic_directives}
- Color Grade Emulation: {context.color_grade_emulation}
- World Setting: {context.world_setting}
- Item Type: {resolved_type}
- Item Code: {resolved_code}
- Current Saved Item (JSON): {json.dumps(item, ensure_ascii=False)[:900] if item else "None"}
- Showrunner Notes: {additional_notes or "None"}

{rag_block}

Produce exactly THREE distinct selectable variations, each following one creative axis:
1. Atmospheric / Moody — weather, haze, emotional temperature, dramatic shadows.
2. Architectural / Grand Scale — monumental geometry, scale, spatial drama.
3. Tactile / Intimate Detail — materiality, wear, close-up textures, human-scale detail.

{schema_block}

OUTPUT SCHEMA (STRICT valid JSON only):
{{
  "variations": [
    {{"label": "Atmospheric / Moody", "variation_id": "v1", "rationale": "..." }},
    {{"label": "Architectural / Grand Scale", "variation_id": "v2", "rationale": "..." }},
    {{"label": "Tactile / Intimate Detail", "variation_id": "v3", "rationale": "..." }}
  ]
}}"""

        messages = [
            {"role": "system", "content": POLYA_AI_DIRECTOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            raw_json = await self._call_llm(messages)
            raw_variations = raw_json.get("variations") if isinstance(raw_json, dict) else None
            if not isinstance(raw_variations, list):
                raw_variations = []
        except Exception as exc:
            logger.warning(
                "Polya AI Director variation LLM failed (%s). Using style-family procedural fallback.",
                exc,
            )
            raw_variations = []

        normalized: list[dict[str, Any]] = []
        for idx, (label, slug) in enumerate(labels):
            raw_item = raw_variations[idx] if idx < len(raw_variations) and isinstance(raw_variations[idx], dict) else {}
            fallback_item = fallback[idx]
            variation_id = f"{resolved_code.lower().replace(' ', '_').replace('#', '')}_{slug}"

            if resolved_type == "environment":
                raw_light = str(raw_item.get("lighting_code") or "").strip()
                try:
                    valid_light = validate_matrix_code("light", raw_light) or fallback_item["lighting_code"]
                except ValueError:
                    valid_light = fallback_item["lighting_code"]
                normalized.append({
                    "variation_id": variation_id,
                    "label": label,
                    "rationale": str(raw_item.get("rationale") or fallback_item["rationale"]).strip(),
                    "code": resolved_code,
                    "name": str(raw_item.get("name") or fallback_item["name"]).strip(),
                    "lighting_code": valid_light,
                    "visual_description": str(
                        raw_item.get("visual_description") or fallback_item["visual_description"]
                    ).strip(),
                    "ambient_foley": str(raw_item.get("ambient_foley") or fallback_item["ambient_foley"]).strip(),
                })
            else:
                normalized.append({
                    "variation_id": variation_id,
                    "label": label,
                    "rationale": str(raw_item.get("rationale") or fallback_item["rationale"]).strip(),
                    "code": resolved_code,
                    "name": str(raw_item.get("name") or fallback_item["name"]).strip(),
                    "dramatic_significance": str(
                        raw_item.get("dramatic_significance") or fallback_item["dramatic_significance"]
                    ).strip(),
                    "visual_details": str(
                        raw_item.get("visual_details") or fallback_item["visual_details"]
                    ).strip(),
                })

        return normalized

    def _procedural_world_prop_variations(
        self,
        context: ProjectNarrativeContext,
        item_type: Literal["environment", "prop"],
        code: str,
        current_item: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Style-family-aware deterministic 3-variation fallback used when RAG/LLM is unavailable."""
        item = current_item or {}
        family = get_style_family(context.master_style_code)
        base_name = str(item.get("name") or "").strip()
        style_label = context.style_name or context.master_style_code

        family_textures: dict[str, str] = {
            "photorealistic": "practical cinematic materials, physically accurate specular response, authentic set-dressing wear",
            "stylized_3d": "stylized sculpted geometry, ray-traced global illumination, exaggerated tactile material response",
            "stop_motion": "handcrafted miniature materials, visible fingerprint textures, articulated puppet-scale construction",
            "anime_2d": "hand-painted cel textures, graphic line-art contours, layered atmospheric matte painting",
        }
        texture = family_textures.get(family, family_textures["photorealistic"])
        light_codes: dict[str, list[str]] = {
            "photorealistic": ["#Light 01", "#Light 04", "#Light 05"],
            "stylized_3d": ["#Light 06", "#Light 10", "#Light 12"],
            "stop_motion": ["#Light 05", "#Light 13", "#Light 07"],
            "anime_2d": ["#Light 02", "#Light 06", "#Light 04"],
        }
        lights = light_codes.get(family, light_codes["photorealistic"])

        if item_type == "environment":
            architecture = str(item.get("architecture") or "").strip()
            atmosphere = str(item.get("atmosphere") or "").strip()
            audio = str(item.get("audio") or item.get("lighting_and_audio") or "").strip()
            root = base_name or f"{context.world_setting or 'Cinematic'} Location"
            return [
                {
                    "rationale": f"Leans into atmosphere and emotional temperature for {style_label}.",
                    "name": f"{root} — Atmospheric Approach",
                    "lighting_code": lights[0],
                    "visual_description": (
                        f"{atmosphere or 'Dense atmospheric perspective, suspended particulates, shifting weather'} "
                        f"Grounding the location in {texture}."
                    ),
                    "ambient_foley": audio or "Low ambient wind bed, distant spatial reverb, fine particulate hiss.",
                },
                {
                    "rationale": f"Emphasizes monumental architecture and spatial drama for {style_label}.",
                    "name": f"{root} — Grand Architectural Elevation",
                    "lighting_code": lights[1],
                    "visual_description": (
                        f"{architecture or 'Monumental structural geometry, deep forced perspective, imposing vertical scale'} "
                        f"Executed with {texture}."
                    ),
                    "ambient_foley": "Cavernous room tone, long tail reverb, structural creaks and low-frequency rumble.",
                },
                {
                    "rationale": f"Focuses on intimate material detail and tactile close-up texture for {style_label}.",
                    "name": f"{root} — Intimate Tactile Detail",
                    "lighting_code": lights[2],
                    "visual_description": (
                        f"Macro-level surface detail: {texture}, weathered edges, hand-worn contact points and micro-grain."
                    ),
                    "ambient_foley": "Close-perspective Foley, fabric rustle, granular surface contact, intimate breath-level room tone.",
                },
            ]

        material = str(
            item.get("material_and_wear") or item.get("material") or item.get("description") or ""
        ).strip()
        significance = str(
            item.get("narrative_utility") or item.get("weight") or ""
        ).strip()
        action = str(item.get("action") or "").strip()
        root_prop = base_name or f"Signature {code} Artifact"
        return [
            {
                "rationale": f"Frames the prop as an emotionally charged atmospheric relic in {style_label}.",
                "name": f"{root_prop} — Weathered Relic",
                "dramatic_significance": significance or "Carries the emotional history of the world; a quiet witness to loss and resolve.",
                "visual_details": (
                    f"{material or 'Deep patina, oxidized edges, accumulated grime'} "
                    f"with {texture}; {action or 'handled with reverent weight'}."
                ),
            },
            {
                "rationale": f"Elevates the prop into a monumental ceremonial centerpiece for {style_label}.",
                "name": f"{root_prop} — Ceremonial Centerpiece",
                "dramatic_significance": significance or "A public symbol of authority and destiny, displayed before crowds and rivals.",
                "visual_details": (
                    f"Overscaled ceremonial construction, engraved iconography, polished focal surfaces; "
                    f"{material or 'inlaid metal and carved stone'} rendered with {texture}."
                ),
            },
            {
                "rationale": f"Grounds the prop in intimate human tactility and close-up physical detail for {style_label}.",
                "name": f"{root_prop} — Intimate Tactile Detail",
                "dramatic_significance": significance or "Reveals character through touch: grip wear, nervous handling, personal inscription.",
                "visual_details": (
                    f"Macro detail of grip wear, fingerprint polish, repaired fractures and personal inscriptions; "
                    f"{material or 'worn organic and forged surfaces'} finished with {texture}."
                ),
            },
        ]

    # --------------------------------------------------------------------------
    # Normalizers & Guardrails
    # --------------------------------------------------------------------------

    def _normalize_cast_ensemble(
        self,
        raw_json: dict[str, Any],
        context: ProjectNarrativeContext,
    ) -> CastEnsembleData:
        """Validate, sanitize, and enforce 5 to 8 characters with 5 states each."""
        chars_raw = raw_json.get("characters")
        if not isinstance(chars_raw, list) or len(chars_raw) < 5:
            # If root is directly a list
            if isinstance(raw_json, list):
                chars_raw = raw_json
            else:
                for k, v in raw_json.items():
                    if isinstance(v, list) and len(v) >= 5:
                        chars_raw = v
                        break

        if not isinstance(chars_raw, list) or len(chars_raw) < 5:
            raise ValueError(
                f"Polya AI Screenwriter returned insufficient characters ({len(chars_raw) if isinstance(chars_raw, list) else 0}). Minimum 5 required."
            )

        # Clamp to max 8 characters
        if len(chars_raw) > 8:
            chars_raw = chars_raw[:8]

        normalized_chars: list[CharacterData] = []
        has_protagonist = False
        has_antagonist = False

        for idx, item in enumerate(chars_raw):
            if not isinstance(item, dict):
                continue
            char_data = self._normalize_single_character(
                item,
                context,
                default_role="PROTAGONIST" if idx == 0 else "SUPPORTING",
            )
            if char_data.role == "PROTAGONIST":
                has_protagonist = True
            elif char_data.role == "ANTAGONIST":
                has_antagonist = True
            normalized_chars.append(char_data)

        # Enforce exactly 1 protagonist and 1 antagonist
        if not has_protagonist and normalized_chars:
            normalized_chars[0].role = "PROTAGONIST"
        if not has_antagonist and len(normalized_chars) > 1:
            normalized_chars[1].role = "ANTAGONIST"

        # Final bounds check
        if len(normalized_chars) < 5:
            raise ValueError(
                f"Valid characters after normalization is {len(normalized_chars)}, below minimum 5."
            )

        return CastEnsembleData(
            cast_rationale=str(raw_json.get("cast_rationale") or f"Cinematic ensemble designed for {context.title}"),
            characters=normalized_chars,
        )

    def _normalize_single_character(
        self,
        item: dict[str, Any],
        context: ProjectNarrativeContext,
        default_role: str = "SUPPORTING",
    ) -> CharacterData:
        """Sanitize a single character object and guarantee 5 states."""
        name = str(item.get("name") or "").strip()
        if not name or name.lower().startswith("character "):
            ctx_hash = int(hashlib.sha256((context.title + context.genre_tone + str(time.time_ns())).encode()).hexdigest()[:6], 16)
            syllables = ["Cael", "Rian", "Dara", "Zephyr", "Aura", "Kiran", "Talon", "Vesper", "Soran", "Mira", "Ren", "Tariq"]
            surnames = ["Voss", "Sanjaya", "Zhao", "Novak", "Lin", "Darma", "Chen", "Sterling", "Kovacs", "Reyes"]
            name = f"{syllables[ctx_hash % len(syllables)]} {surnames[(ctx_hash >> 3) % len(surnames)]}"

        role = str(item.get("role") or default_role).strip().upper()
        narrative_summary = str(
            item.get("narrative_summary")
            or f"{name} plays a vital dramatic function in '{context.title}'."
        ).strip()

        base_prompt = str(item.get("base_visual_prompt") or "").strip()
        if not base_prompt:
            base_prompt = (
                f"Cinematic close biometric character portrait of {name}, tailored to {context.genre_tone} aesthetic. "
                "Sharp facial features, expressive eyes, authentic signature costume."
            )
        base_prompt = " ".join(base_prompt.split())

        is_stylized = any(
            k in (context.style_name + " " + context.master_style_code).lower()
            for k in ("anime", "cartoon", "2d", "comic", "manga", "pixar", "claymation", "illustration")
        )
        if is_stylized:
            std_bg = "isolated on a flat seamless Neutral Matte Light-Medium Studio Gray (#D4D4D4) studio background, neutral studio illumination, zero environment props or color cast"
        else:
            std_bg = "isolated on a flat seamless Neutral Matte Light-Medium Studio Gray (#D4D4D4) studio background, even softbox lighting, zero environment props or color cast"
        if "#D4D4D4" not in base_prompt:
            base_prompt = f"{base_prompt.rstrip('. ')}. {std_bg}."

        voice_dna = str(
            item.get("voice_dna_profile")
            or "Low-resonance cinematic voice with disciplined emotional articulation"
        ).strip()

        states_raw = item.get("states")
        states_list: list[CharacterStateData] = []
        state_labels_default = [
            "Normal Baseline",
            "Fatigue & Wear",
            "Crisis / Battle Damaged",
            "Psychological Fracture",
            "Climax / Metamorphosis",
        ]

        if isinstance(states_raw, list):
            for s_idx, st in enumerate(states_raw[:5]):
                if isinstance(st, dict):
                    st_num = int(st.get("state_number") or (s_idx + 1))
                    states_list.append(
                        CharacterStateData(
                            state_number=min(max(st_num, 1), 5),
                            state_label=str(st.get("state_label") or state_labels_default[s_idx]),
                            wardrobe=str(st.get("wardrobe") or f"Wardrobe progression stage {s_idx + 1} for {name}"),
                            physical_damage=str(st.get("physical_damage") or ""),
                            emotional_anchor=str(st.get("emotional_anchor") or ""),
                        )
                    )

        # Pad to exactly 5 states if LLM provided fewer
        while len(states_list) < 5:
            curr_idx = len(states_list)
            states_list.append(
                CharacterStateData(
                    state_number=curr_idx + 1,
                    state_label=state_labels_default[curr_idx],
                    wardrobe=f"Wardrobe stage {curr_idx + 1} reflecting progressive wear and story conflict",
                    physical_damage="Progressive atmospheric wear and strain",
                    emotional_anchor="Intense cinematic focus",
                )
            )

        return CharacterData(
            name=name,
            role=role,
            narrative_summary=narrative_summary,
            base_visual_prompt=base_prompt,
            voice_dna_profile=voice_dna,
            states=states_list,
        )

    # ==========================================================================
    # Voice DNA & 5-State Continuity Helpers + Single-Character / State Helpers
    # ==========================================================================

    @staticmethod
    def _resolve_act_to_state_number(act_number: int | None, total_acts: int = 4) -> int | None:
        """Map an Act index (1..total_acts) onto canonical #State 01..05 progression."""
        if act_number is None:
            return None
        safe_total = max(1, int(total_acts or 4))
        safe_act = max(1, min(int(act_number), safe_total))
        if safe_total == 1:
            return 1
        mapped = 1 + round(((safe_act - 1) / (safe_total - 1)) * 4)
        return max(1, min(5, int(mapped)))

    @classmethod
    def _format_cast_continuity_context(
        cls,
        project_context: ProjectNarrativeContext | dict[str, Any] | None = None,
        characters: list[dict[str, Any]] | None = None,
        act_number: int | None = None,
        total_acts: int = 4,
        speaking_character: str | None = None,
    ) -> tuple[str, list[str]]:
        """Build a compact cast block weaving Voice DNA and Act-mapped #State 01-05 continuity."""
        merged_by_name: dict[str, dict[str, Any]] = {}

        def _ingest(raw_list: list[Any] | None) -> None:
            if not raw_list:
                return
            for c in raw_list:
                if not isinstance(c, dict):
                    continue
                name = str(c.get("name") or "").strip()
                if not name:
                    continue
                key = name.lower()
                existing = merged_by_name.get(key, {"name": name, "states": []})
                existing["name"] = name
                existing["role"] = c.get("role") or existing.get("role") or "Cast"
                existing["narrative_summary"] = (
                    c.get("narrative_summary")
                    or c.get("narrative_profile")
                    or existing.get("narrative_summary")
                    or ""
                )
                existing["voice_dna_profile"] = c.get("voice_dna_profile") or existing.get("voice_dna_profile") or ""
                existing["base_prompt"] = c.get("base_prompt") or c.get("base_visual_prompt") or existing.get("base_prompt") or ""
                states = c.get("states") or []
                if states:
                    existing["states"] = list(states)
                merged_by_name[key] = existing

        if isinstance(project_context, ProjectNarrativeContext):
            _ingest(project_context.cast_characters)
        elif isinstance(project_context, dict):
            _ingest(project_context.get("cast_characters"))
        _ingest(characters)

        entries = list(merged_by_name.values())
        if not entries:
            return "- Protagonist (Main Lead)\n- Antagonist (Opposing Force)", ["Protagonist", "Antagonist"]

        sp_lower = (speaking_character or "").strip().lower()
        if sp_lower:
            entries.sort(key=lambda item: (0 if item["name"].lower() == sp_lower else 1))

        target_state_num = cls._resolve_act_to_state_number(act_number, total_acts)
        target_code = f"#State 0{target_state_num}" if target_state_num else None

        lines: list[str] = []
        char_names: list[str] = []
        for entry in entries:
            c_name = entry["name"]
            char_names.append(c_name)
            c_role = entry.get("role", "Cast")
            marker = " [ACTIVE SPEAKER]" if sp_lower and c_name.lower() == sp_lower else ""
            voice_dna = str(entry.get("voice_dna_profile") or "").strip()
            bio = str(entry.get("narrative_summary") or entry.get("base_prompt") or "").strip()

            parts = [f"- {c_name} ({c_role}){marker}:"]
            if bio:
                parts.append(bio[:100])
            if voice_dna:
                parts.append(f"Voice DNA: {voice_dna[:140]}")

            raw_states = entry.get("states") or []
            if raw_states:
                normalized_states: list[tuple[str, str, str, str, str]] = []
                for idx, st in enumerate(raw_states, start=1):
                    if isinstance(st, dict):
                        s_code = str(st.get("state_code") or st.get("code") or f"#State 0{min(idx, 5)}")
                        s_label = str(st.get("state_label") or st.get("label") or "")
                        s_wardrobe = str(st.get("wardrobe") or "")
                        s_wear = str(st.get("injuries_and_wear") or st.get("wear") or st.get("physical_damage") or "")
                        s_expr = str(st.get("expression_anchor") or st.get("expression") or st.get("emotional_anchor") or "")
                    else:
                        s_code = str(getattr(st, "state_code", f"#State 0{min(idx, 5)}"))
                        s_label = str(getattr(st, "state_label", "") or "")
                        s_wardrobe = str(getattr(st, "wardrobe", "") or "")
                        s_wear = str(getattr(st, "injuries_and_wear", "") or "")
                        s_expr = str(getattr(st, "expression_anchor", "") or "")
                    normalized_states.append((s_code, s_label, s_wardrobe, s_wear, s_expr))

                normalized_states.sort(key=lambda tup: tup[0])
                if target_code:
                    chosen = next((t for t in normalized_states if t[0].upper() == target_code.upper()), None)
                    if not chosen:
                        fallback_idx = min(len(normalized_states) - 1, max(0, (target_state_num or 1) - 1))
                        chosen = normalized_states[fallback_idx]
                    st_bits = [b for b in (
                        f"Wardrobe: {chosen[2][:70]}" if chosen[2] else "",
                        f"Wear: {chosen[3][:60]}" if chosen[3] else "",
                        f"Emotion: {chosen[4][:60]}" if chosen[4] else "",
                    ) if b]
                    st_lbl = f" ({chosen[1]})" if chosen[1] else ""
                    if st_bits:
                        parts.append(f"Active {chosen[0]}{st_lbl} [{'; '.join(st_bits)}]")
                else:
                    arc_labels = " -> ".join(f"{t[0]} {t[1] or t[4]}".strip()[:28] for t in normalized_states[:5])
                    if arc_labels:
                        parts.append(f"5-State Arc: {arc_labels}")

            lines.append(" | ".join(parts))

        return "\n".join(lines), char_names

    @staticmethod
    def _format_speaker_continuity_line(
        character_name: str | None = None,
        voice_dna_profile: str | None = None,
        active_state: dict[str, Any] | str | None = None,
    ) -> str:
        """Render concise speaker Voice DNA and active physical/emotional state block for single-scene prompts."""
        bits: list[str] = []
        if voice_dna_profile and str(voice_dna_profile).strip():
            bits.append(f"SPEAKER VOICE DNA ({character_name or 'Active Speaker'}): {str(voice_dna_profile).strip()}")
        if isinstance(active_state, dict) and active_state:
            s_code = active_state.get("state_code") or active_state.get("code") or "#State"
            s_lbl = active_state.get("state_label") or active_state.get("label") or ""
            details = [
                f"Wardrobe: {active_state.get('wardrobe')}" if active_state.get("wardrobe") else "",
                f"Wear/Injuries: {active_state.get('injuries_and_wear') or active_state.get('wear')}" if (active_state.get("injuries_and_wear") or active_state.get("wear")) else "",
                f"Emotional Anchor: {active_state.get('expression_anchor') or active_state.get('expression')}" if (active_state.get("expression_anchor") or active_state.get("expression")) else "",
            ]
            joined = " | ".join(d for d in details if d)
            if joined:
                bits.append(f"ACTIVE STATE ({s_code}{' - ' + s_lbl if s_lbl else ''}): {joined}")
        elif isinstance(active_state, str) and active_state.strip():
            bits.append(f"ACTIVE STATE: {active_state.strip()}")
        return "\n".join(bits)

    async def auto_generate_character(
        self,
        project_context: ProjectNarrativeContext | dict[str, Any] | None = None,
        existing_names: list[str] | None = None,
        mode: str = "all",
        current_draft: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate a single character concept + structured Voice DNA via RAG 8766 & 18-Style taxonomy."""
        if isinstance(project_context, ProjectNarrativeContext):
            film_title = project_context.title
            synopsis = project_context.synopsis
            genre_tone = project_context.genre_tone
            style_code = project_context.master_style_code
            style_name = project_context.style_name
            world_setting = project_context.world_setting
        elif isinstance(project_context, dict):
            film_title = str(project_context.get("title") or "Untitled Production")
            synopsis = str(project_context.get("synopsis") or "Epic cinematic narrative feature production.")
            genre_tone = str(project_context.get("genre_tone") or "Cinematic Film")
            style_code = str(project_context.get("master_style_code") or "#Style 01")
            style_name = str(project_context.get("style_name") or "Hollywood Cinematic")
            world_setting = str(project_context.get("world_setting") or "Cinematic Universe")
        else:
            film_title = "Untitled Production"
            synopsis = "Epic cinematic narrative feature production."
            genre_tone = "Cinematic Film"
            style_code = "#Style 01"
            style_name = "Hollywood Cinematic"
            world_setting = "Cinematic Universe"

        draft = current_draft or {}
        style_family = get_style_family(style_code)
        family_meta = STYLE_TAXONOMY_FAMILIES.get(style_family, {})
        family_label = family_meta.get("name", style_family)
        writing_directive = STYLE_FAMILY_WRITING_DIRECTIVES.get(style_family, "")

        rag_res = await ScreenwriterRAGClient.retrieve_character_voice(
            style_code=style_code,
            genre_tone=genre_tone,
            roles=[str(draft.get("role") or "PROTAGONIST")],
            top_k=2,
        )
        sw_voice_block = str(rag_res.get("prompt_block") or "").strip()

        system_prompt = (
            "You are Polya AI — Hollywood Master Screenwriter, Character Architect, and Biometric Concept Designer.\n"
            "Generate structured JSON strictly adhering to the film universe, Voice DNA discipline, and visual style family.\n"
            "Do NOT reuse generic stock names such as Kaelen, Thorne, Vane, Vance, Lyra, or Cipher.\n"
            "Output strictly valid JSON without markdown or commentary."
        )

        user_prompt = (
            f"Production Title: {film_title}\n"
            f"Synopsis / Core Premise: {synopsis}\n"
            f"Genre & Tone: {genre_tone}\n"
            f"World Setting: {world_setting}\n"
            f"Master Visual Style: {style_name} ({style_code}) — Family: {family_label}\n"
            f"Style Writing Directives: {writing_directive}\n"
            f"Existing Cast Names (do NOT reuse): {', '.join(existing_names) if existing_names else 'None yet'}\n"
            f"Generation Mode: '{mode}'\n"
            f"User Draft Context:\n"
            f"- Current Name: {draft.get('name') or 'None'}\n"
            f"- Current Role: {draft.get('role') or 'None'}\n"
            f"- Current Bio/Archetype: {draft.get('archetype_and_bio') or 'None'}\n"
            f"- Current Base Visual Prompt: {draft.get('base_visual_prompt') or 'None'}\n"
        )
        if sw_voice_block:
            user_prompt += f"\n{sw_voice_block}\n"
        user_prompt += (
            "\nRequirements:\n"
            "1. 'name': Contextually authentic character name fitting the film title and universe.\n"
            "2. 'role_suggestion': One of 'Protagonist', 'Antagonist', 'Deuteragonist', 'Mentor', or 'Supporting'.\n"
            "3. 'archetype_and_bio': 2-3 sentences detailing dramatic role, core flaw/desire, psychological subtext, and narrative function.\n"
            "4. 'voice_dna_profile': Concise vocal & speech fingerprint (speaking tempo/wps, lexical register, emotional tell, verbal tic or silence habit).\n"
            "5. 'base_visual_prompt': Detailed biometric visual prompt (exact age, ethnicity, facial bone structure, eyes, skin texture, hair, posture, signature costume) ending with 'isolated on a flat seamless Neutral Matte Light-Medium Studio Gray (#D4D4D4) studio background, even softbox lighting, zero environment props or color cast' in one continuous paragraph without raw newlines.\n"
            "6. Output strictly valid flat JSON with keys: 'name', 'role_suggestion', 'archetype_and_bio', 'voice_dna_profile', 'base_visual_prompt'."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return await self._call_llm(messages, retry_on_parse_error=True)

    async def suggest_character_state(
        self,
        project_context: ProjectNarrativeContext | dict[str, Any] | None,
        character: Any,
        state_code: str,
        target_field: str = "all",
        current_values: dict[str, str] | None = None,
        previous_value: str | None = None,
        is_regeneration: bool = False,
        scenes_summary: str = "",
        prior_states_text: str = "",
    ) -> dict[str, Any]:
        """Generate progressive #State 01-#State 05 wardrobe/wear/expression grounded in Voice DNA, RAG 8766 & full arc."""
        if isinstance(project_context, ProjectNarrativeContext):
            film_title = project_context.title
            synopsis = project_context.synopsis
            genre_tone = project_context.genre_tone
            style_code = project_context.master_style_code
            style_name = project_context.style_name
            setting_world = project_context.world_setting
        elif isinstance(project_context, dict):
            film_title = str(project_context.get("title") or "Untitled Production")
            synopsis = str(project_context.get("synopsis") or "")
            genre_tone = str(project_context.get("genre_tone") or "Cinematic Film")
            style_code = str(project_context.get("master_style_code") or "#Style 01")
            style_name = str(project_context.get("style_name") or "Hollywood Cinematic")
            setting_world = str(project_context.get("world_setting") or "Cinematic Universe")
        else:
            film_title = "Untitled Production"
            synopsis = ""
            genre_tone = "Cinematic Film"
            style_code = "#Style 01"
            style_name = "Hollywood Cinematic"
            setting_world = "Cinematic Universe"

        char_name = getattr(character, "name", None) or (character.get("name") if isinstance(character, dict) else "Character")
        char_role = getattr(character, "role", None) or (character.get("role") if isinstance(character, dict) else "PROTAGONIST")
        char_base = getattr(character, "base_prompt", None) or (character.get("base_prompt") if isinstance(character, dict) else "")
        char_voice = getattr(character, "voice_dna_profile", None) or (character.get("voice_dna_profile") if isinstance(character, dict) else "") or ""
        char_summary = getattr(character, "narrative_summary", None) or (character.get("narrative_summary") if isinstance(character, dict) else "") or ""

        style_family = get_style_family(style_code)
        writing_directive = STYLE_FAMILY_WRITING_DIRECTIVES.get(style_family, "")

        rag_res = await ScreenwriterRAGClient.retrieve_character_voice(
            style_code=style_code,
            genre_tone=genre_tone,
            roles=[str(char_role)],
            top_k=2,
        )
        sw_voice_block = str(rag_res.get("prompt_block") or "").strip()

        t_field = (target_field or "all").lower().strip()
        curr_vals = current_values or {}
        prev_val = previous_value or "None"

        if t_field == "all":
            expected_keys = '{"wardrobe": "...", "injuries_and_wear": "...", "expression_anchor": "..."}'
            field_instruction = (
                "USER TRIGGERED REGENERATE ALL. Provide fresh, distinct, high-impact alternative descriptions for all 3 fields "
                "('wardrobe', 'injuries_and_wear', 'expression_anchor') differing meaningfully from "
                f"Current Values: {json.dumps(curr_vals)} while preserving costume continuity."
                if is_regeneration
                else f"Generate camera-ready descriptions for all 3 fields ('wardrobe', 'injuries_and_wear', 'expression_anchor') reflecting {state_code}."
            )
        elif t_field == "wardrobe":
            expected_keys = '{"wardrobe": "..."}'
            field_instruction = f"Generate ONLY 'wardrobe' for {state_code}, differing from Previous Rejected Value: '{prev_val}'."
        elif t_field in ("injuries", "injuries_and_wear"):
            expected_keys = '{"injuries_and_wear": "..."}'
            field_instruction = f"Generate ONLY 'injuries_and_wear' for {state_code}, differing from Previous Rejected Value: '{prev_val}'."
        elif t_field in ("expression", "expression_anchor"):
            expected_keys = '{"expression_anchor": "..."}'
            field_instruction = f"Generate ONLY 'expression_anchor' for {state_code}, differing from Previous Rejected Value: '{prev_val}'."
        else:
            expected_keys = '{"wardrobe": "...", "injuries_and_wear": "...", "expression_anchor": "..."}'
            field_instruction = f"Generate camera-ready descriptions for all 3 fields reflecting {state_code}."

        sys_prompt = (
            "You are Polya AI — Hollywood Costume Designer, Continuity Director, and Psychological Performance Architect.\n"
            "Formulate precise, camera-ready visual descriptions for dynamic character state progression (#State 01 to #State 05).\n\n"
            "CRITICAL DIRECTIVES:\n"
            "1. UNIVERSALITY & FIDELITY: Inherit and evolve the specific garments, fabrics, and accessories from Base Visual Prompt.\n"
            "2. PSYCHOLOGICAL & VOCAL COHERENCE: Align facial tension and expression anchor with Character Voice DNA and Dramatic Arc.\n"
            "3. CINEMATIC DESCRIPTORS: Dense visual-first phrasing (15-35 words, 1-2 tight sentences per field). No label prefixes ('Wardrobe:', etc.) or markdown.\n"
            "4. CONTINUITY & ANTI-REPETITION: Build cumulatively on prior recorded states; if regenerating, provide a genuinely distinct alternative.\n"
            "5. JSON OUTPUT ONLY: Strictly valid flat JSON matching requested keys."
        )

        user_prompt = (
            f"=== PRODUCTION CONTEXT ===\n"
            f"Project Title: {film_title}\n"
            f"Synopsis / Premise: {synopsis}\n"
            f"Genre & Tone: {genre_tone}\n"
            f"Master Visual Style: {style_name} ({style_code}) — Family: {style_family}\n"
            f"Style Directives: {writing_directive}\n"
            f"World / Setting: {setting_world}\n"
            f"Full Dramatic Arc Context:\n{scenes_summary}\n\n"
            f"=== ACTIVE CHARACTER PROFILE ===\n"
            f"Name: {char_name}\n"
            f"Role: {char_role}\n"
            f"Narrative Arc Summary: {char_summary or 'N/A'}\n"
            f"Voice DNA Profile: {char_voice or 'Standard cinematic cadence'}\n"
            f"Base Visual Prompt: {char_base}\n\n"
            f"=== PROGRESSION MATRIX REFERENCE ===\n"
            f"- #State 01 - Normal: Pristine baseline appearance; intact attire, zero fresh wounds.\n"
            f"- #State 02 - Wear & Tear: Minor dust, light creasing, loosened collar/accessories, subtle fatigue.\n"
            f"- #State 03 - Battle Damaged: Measured tears, scuffs, fresh cuts, bruises, grime, or burns.\n"
            f"- #State 04 - Psychological Breakdown: Heavily disheveled attire; hollow gaze, trauma, smeared grime/sweat.\n"
            f"- #State 05 - Climax / Catharsis: Peak climactic transformation and physical/emotional resolution.\n\n"
            f"=== CROSS-STATE CONTINUITY ===\n"
            f"Previously Registered States:\n{prior_states_text or 'None registered yet.'}\n"
        )
        if sw_voice_block:
            user_prompt += f"\n{sw_voice_block}\n"
        user_prompt += (
            f"\n=== TARGET GENERATION OBJECTIVE ===\n"
            f"Target State Code: {state_code}\nTarget Field: {t_field}\nIs Regeneration: {is_regeneration}\n"
            f"Current Values: {json.dumps(curr_vals)}\nPrevious Rejected Value: {prev_val}\n\n"
            f"INSTRUCTION:\n{field_instruction}\n"
            f"Output strictly a JSON object with keys: {expected_keys}"
        )

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return await self._call_llm(messages, retry_on_parse_error=True)

    # ==========================================================================
    # ==========================================================================
    # Dynamic World & Signature Props Generator (Polya AI Director Engine)
    # ==========================================================================

    async def generate_world_and_props(
        self,
        context: ProjectNarrativeContext,
        additional_notes: str | None = None,
    ) -> dict[str, Any]:
        """Generate 5 Key Environments (#Env 01 - 05) and 5 Signature Hero Props (#Prop 01 - 05)
        strictly tailored to the project narrative context, cast characters, and storyboard locations
        adhering to Hollywood Production Design & DaVinci Obsidian Matrix standards.
        """
        dna_items = []
        if context.visual_dna_parameters:
            for k, v in context.visual_dna_parameters.items():
                dna_items.append(f"{k.replace('_', ' ').title()}: {v}")
        dna_str = f"- Master Visual DNA Settings: {', '.join(dna_items)}" if dna_items else ""

        # Format cast characters
        cast_lines = []
        for idx, c in enumerate(context.cast_characters):
            states_preview = ""
            if c.get("states"):
                s01 = c["states"][0]
                states_preview = f" | Baseline Wardrobe: {s01.get('wardrobe', '')[:60]}"
            cast_lines.append(
                f"- Character #{idx + 1}: {c.get('name')} (Role: {c.get('role', 'SUPPORTING')}{states_preview}) — Arc: {c.get('narrative_profile', '')[:90]}"
            )
        cast_str = "\n".join(cast_lines) if cast_lines else "No registered cast yet. Anchor props to dramatic roles (PROTAGONIST, ANTAGONIST, ENSEMBLE)."

        # Format storyboard scenes and recurring sluglines
        locations_lines = []
        if context.ranked_locations:
            locations_lines.append(
                "- Storyboard Top Recurring Sluglines: "
                + ", ".join(f"{loc} ({cnt}x)" for loc, cnt in context.ranked_locations[:6])
            )
        if context.storyboard_scenes:
            locations_lines.append(
                "- Storyboard Narrative Progression: "
                + "; ".join(f"Act {sc.get('act_number')} Sc {sc.get('scene_number')} [{sc.get('slugline')}]: {sc.get('narrative_goal', '')[:50]}" for sc in context.storyboard_scenes[:6])
            )
        scenes_str = "\n".join(locations_lines) if locations_lines else "No storyboard scenes created yet. Synthesize 5 core dramatic locations based on premise and genre."

        # Canonical Lighting Matrix from catalog SSOT
        lighting_catalog_summary = "\n".join(
            f"- {l['code']} {l['name']}: {l['technical_specifications']} (Mood: {l['mood_application']})"
            for l in LIGHTING_MATRIX
        )

        # Retrieve Visual Grammar & Lighting Spec
        rag_result = await DirectorRAGClient.retrieve(
            scene_beat=f"{context.title} world-building: {context.synopsis[:100]}",
            style_code=context.master_style_code,
            engine="9router",
            top_k=3
        )
        visual_grammar = DirectorRAGClient.format_treatment_grammar(rag_result)
        lighting_spec = DirectorRAGClient.format_act_context(rag_result)

        user_prompt = f"""PROJECT PRODUCTION BIBLE & NARRATIVE CONTEXT:
- Film Title: {context.title}
- Core Synopsis & Premise:
{context.synopsis}
- Master Genre & Tone: {context.genre_tone}
- Aspect Ratio: {context.aspect_ratio}
- Active Operational Stage: Stage {context.operational_stage}
- Master Visual Style Code: {context.master_style_code} ({context.style_name})
- Visual Style Directives: {context.aesthetic_directives}
- Color Palette & Lighting Emulation: {context.color_grade_emulation}
{dna_str}
- World Setting: {context.world_setting}
- Production Continuity Rules: {', '.join(context.continuity_rules) if context.continuity_rules else 'Standard Cinematic Rules'}
- Additional Showrunner Notes: {additional_notes or 'None'}

{visual_grammar}
{lighting_spec}

REGISTERED CHARACTER CAST ({len(context.cast_characters)} Characters):
{cast_str}

50-SCENE STORYBOARD & RECURRING SLUGLINES ({len(context.storyboard_scenes)} Scenes):
{scenes_str}

CANONICAL DAVINCI OBSIDIAN LIGHTING MATRIX (#Light 01 to #Light 14):
{lighting_catalog_summary}

POLYA AI DIRECTOR MANDATE:
1. Synthesize exactly 5 Key Environments (#Env 01 through #Env 05) that represent the core narrative locations:
   - code: '#Env 01' to '#Env 05'
   - name: Distinct, culturally authentic, and evocative location name (aligned with Storyboard sluglines when present).
   - architecture: Spatial scale, structural silhouettes, construction materials, tactile surface textures consistent with active #Style.
   - atmosphere: Weather physics, airborne particulates (steam/fog/ash/snow/dust), humidity, and atmospheric perspective.
   - lighting_code: Official lighting code ('#Light 01' to '#Light 14' from catalog).
   - lighting_and_audio: Detailed combined directive: '#Light XX [Name] (Kelvin, contrast ratio) • Room Tone: [SNR >= 32 dB acoustic cues, spatial reverb, Foley bed]'.
   - linked_scenes: Associated story arc / acts / sluglines (e.g. 'Act I–II (EXT. ASH WASTES, EXT. RUINED OUTPOST)').
   - lighting: Detailed standalone lighting directive.
   - audio: Detailed standalone room tone and acoustic Foley cues.

2. Synthesize exactly 5 Signature Hero Props (#Prop 01 through #Prop 05) that carry narrative weight and tactile continuity:
   - code: '#Prop 01' to '#Prop 05'
   - name: Unique, story-critical hero prop name matching the film's world.
   - owner_character: Exact character name from the cast above (or 'Ensemble / World Artifact').
   - material_and_wear: Specific physical materiality, dimensions, craftsmanship, weathering, battle scars, specular/roughness cues for cross-shot visual continuity (CLIP >= 0.80, LAION >= 8.0/10).
   - narrative_utility: Exact dramatic function and plot significance across the story arc.
   - description: Concise backward-compatible summary string.
   - material: Backward-compatible material string.
   - weight: Backward-compatible narrative weight string.
   - action: Exact physical tactile manipulation (how characters grip, manipulate, ignite, wear, or activate it).

OUTPUT SCHEMA (Return STRICT valid JSON only):
{{
  "environments": [
    {{
      "code": "#Env 01",
      "name": "Location Name (aligned with Storyboard slugline)",
      "architecture": "Spatial scale and tactile materials",
      "atmosphere": "Atmospheric conditions and airborne particles",
      "lighting_code": "#Light 07",
      "lighting_and_audio": "#Light 07 Overcast Soft (6000K diffused northern sky...) • Room Tone: howling wind, leather footsteps",
      "linked_scenes": "Act I–II (EXT. ASH WASTES, EXT. RUINED OUTPOST)",
      "lighting": "Detailed lighting directive",
      "audio": "Detailed ambient soundscape & Foley"
    }},
    {{ "code": "#Env 02", "name": "...", "architecture": "...", "atmosphere": "...", "lighting_code": "#Light 04", "lighting_and_audio": "...", "linked_scenes": "...", "lighting": "...", "audio": "..." }},
    {{ "code": "#Env 03", "name": "...", "architecture": "...", "atmosphere": "...", "lighting_code": "#Light 01", "lighting_and_audio": "...", "linked_scenes": "...", "lighting": "...", "audio": "..." }},
    {{ "code": "#Env 04", "name": "...", "architecture": "...", "atmosphere": "...", "lighting_code": "#Light 06", "lighting_and_audio": "...", "linked_scenes": "...", "lighting": "...", "audio": "..." }},
    {{ "code": "#Env 05", "name": "...", "architecture": "...", "atmosphere": "...", "lighting_code": "#Light 05", "lighting_and_audio": "...", "linked_scenes": "...", "lighting": "...", "audio": "..." }}
  ],
  "props": [
    {{
      "code": "#Prop 01",
      "name": "Signature Hero Prop Name",
      "owner_character": "Exact Character Name from Cast",
      "material_and_wear": "Concrete physical materials, wear and patina",
      "narrative_utility": "Exact dramatic function across story arc",
      "description": "Concise summary string",
      "material": "Material and wear",
      "weight": "Narrative utility",
      "action": "Tactile manipulation and interaction during pivotal scenes"
    }},
    {{ "code": "#Prop 02", "name": "...", "owner_character": "...", "material_and_wear": "...", "narrative_utility": "...", "description": "...", "material": "...", "weight": "...", "action": "..." }},
    {{ "code": "#Prop 03", "name": "...", "owner_character": "...", "material_and_wear": "...", "narrative_utility": "...", "description": "...", "material": "...", "weight": "...", "action": "..." }},
    {{ "code": "#Prop 04", "name": "...", "owner_character": "...", "material_and_wear": "...", "narrative_utility": "...", "description": "...", "material": "...", "weight": "...", "action": "..." }},
    {{ "code": "#Prop 05", "name": "...", "owner_character": "...", "material_and_wear": "...", "narrative_utility": "...", "description": "...", "material": "...", "weight": "...", "action": "..." }}
  ]
}}"""

        messages = [
            {"role": "system", "content": POLYA_AI_DIRECTOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            raw_json = await self._call_llm(messages)
            normalized = self._normalize_world_and_props(raw_json, context)
            normalized["generation_meta"] = {
                "engine": "polya_ai_director_llm",
                "model": self.model,
                "director_persona": "Polya AI Director",
                "context_ingested": {
                    "style_code": context.master_style_code,
                    "characters_count": len(context.cast_characters),
                    "scenes_count": len(context.storyboard_scenes),
                    "has_synopsis": bool(context.synopsis),
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "fallback_reason": None,
            }
            return normalized
        except Exception as exc:
            logger.warning(
                "Polya AI Director LLM call failed (%s). Activating contextual procedural fallback.",
                exc,
            )
            fallback_data = self._generate_procedural_world_and_props(context)
            fallback_data["generation_meta"] = {
                "engine": "procedural_fallback",
                "model": None,
                "director_persona": "Polya AI Director (Procedural Fallback)",
                "context_ingested": {
                    "style_code": context.master_style_code,
                    "characters_count": len(context.cast_characters),
                    "scenes_count": len(context.storyboard_scenes),
                    "has_synopsis": bool(context.synopsis),
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "fallback_reason": f"LLM execution failed ({type(exc).__name__}: {str(exc)[:150]})",
            }
            return fallback_data

    def _normalize_world_and_props(
        self,
        raw_json: dict[str, Any],
        context: ProjectNarrativeContext,
    ) -> dict[str, Any]:
        """Normalize and enforce 5 environments and 5 props schema with both enriched and backward-compatible fields."""
        procedural_fallback = self._generate_procedural_world_and_props(context)

        raw_envs = raw_json.get("environments", []) if isinstance(raw_json, dict) else []
        raw_props = raw_json.get("props", []) if isinstance(raw_json, dict) else []

        normalized_envs = []
        for i in range(5):
            code = f"#Env {i + 1:02d}"
            item = raw_envs[i] if i < len(raw_envs) and isinstance(raw_envs[i], dict) else {}
            fallback_item = procedural_fallback["environments"][i]

            lighting_code = str(item.get("lighting_code") or fallback_item.get("lighting_code") or f"#Light {((i * 2 + 1) % 14) + 1:02d}").strip()
            lighting = str(item.get("lighting") or fallback_item.get("lighting") or lighting_code).strip()
            audio = str(item.get("audio") or fallback_item.get("audio") or "Balanced ambient room tone with natural foley texture.").strip()
            lighting_and_audio = str(
                item.get("lighting_and_audio")
                or fallback_item.get("lighting_and_audio")
                or f"{lighting} • Room Tone: {audio}"
            ).strip()
            linked_scenes = str(
                item.get("linked_scenes")
                or fallback_item.get("linked_scenes")
                or f"Act {min(i + 1, 4)}"
            ).strip()

            normalized_envs.append({
                "code": code,
                "name": str(item.get("name") or fallback_item["name"]).strip(),
                "architecture": str(item.get("architecture") or fallback_item["architecture"]).strip(),
                "atmosphere": str(item.get("atmosphere") or fallback_item["atmosphere"]).strip(),
                "lighting_code": lighting_code,
                "lighting_and_audio": lighting_and_audio,
                "linked_scenes": linked_scenes,
                "lighting": lighting,
                "audio": audio,
            })

        normalized_props = []
        for i in range(5):
            code = f"#Prop {i + 1:02d}"
            item = raw_props[i] if i < len(raw_props) and isinstance(raw_props[i], dict) else {}
            fallback_item = procedural_fallback["props"][i]

            owner_character = str(
                item.get("owner_character")
                or fallback_item.get("owner_character")
                or (context.cast_characters[i]["name"] if i < len(context.cast_characters) else "Ensemble / World Artifact")
            ).strip()

            material_and_wear = str(
                item.get("material_and_wear")
                or item.get("material")
                or fallback_item.get("material_and_wear")
                or fallback_item.get("material")
                or "Hardened alloy with authentic field wear"
            ).strip()

            narrative_utility = str(
                item.get("narrative_utility")
                or item.get("weight")
                or fallback_item.get("narrative_utility")
                or fallback_item.get("weight")
                or "Narrative anchor in critical story moments"
            ).strip()

            action = str(
                item.get("action")
                or fallback_item.get("action")
                or "Handled firmly during pivotal scenes"
            ).strip()

            desc = str(
                item.get("description")
                or fallback_item.get("description")
                or f"{material_and_wear} - {narrative_utility}"
            ).strip()

            normalized_props.append({
                "code": code,
                "name": str(item.get("name") or fallback_item["name"]).strip(),
                "owner_character": owner_character,
                "material_and_wear": material_and_wear,
                "narrative_utility": narrative_utility,
                "description": desc,
                "material": material_and_wear,
                "weight": narrative_utility,
                "action": action,
            })

        return {
            "environments": normalized_envs,
            "props": normalized_props,
        }

    def _generate_procedural_world_and_props(
        self,
        context: ProjectNarrativeContext,
    ) -> dict[str, Any]:
        """Generate high-fidelity contextual environments and props dynamically synthesized from active project context."""
        title = context.title or "Cinematic Production"
        genre = (context.genre_tone or "Cinematic Drama").split("/")[0].strip()
        setting = context.world_setting or "Epic Universe"

        # Determine cast anchor names
        cast = context.cast_characters
        owner_0 = cast[0]["name"] if len(cast) > 0 else "Protagonist"
        owner_1 = cast[1]["name"] if len(cast) > 1 else (cast[0]["name"] if len(cast) > 0 else "Protagonist")
        owner_2 = cast[2]["name"] if len(cast) > 2 else (cast[1]["name"] if len(cast) > 1 else "Antagonist")
        owner_3 = cast[3]["name"] if len(cast) > 3 else "Supporting Ally"
        owner_4 = "Ensemble / World Artifact"

        # Check if storyboard locations exist
        ranked = [loc for loc, _ in context.ranked_locations] if context.ranked_locations else []
        env_name_0 = ranked[0] if len(ranked) > 0 else None
        env_name_1 = ranked[1] if len(ranked) > 1 else None
        env_name_2 = ranked[2] if len(ranked) > 2 else None
        env_name_3 = ranked[3] if len(ranked) > 3 else None
        env_name_4 = ranked[4] if len(ranked) > 4 else None

        # Contextual templates based on genre keywords & active #Style
        full_text = f"{genre} {title} {context.master_style_code} {context.style_name}".lower()
        is_fantasy = any(w in full_text for w in ["fantasy", "nordic", "myth", "ancient", "magic", "realm", "legend", "disgraced", "#style 04", "#style 07"])
        is_sci_fi = any(w in full_text for w in ["cyber", "sci-fi", "space", "quantum", "machine", "orbit", "future", "stellar", "#style 01", "#style 11"])

        if is_fantasy:
            envs = [
                {
                    "code": "#Env 01",
                    "name": env_name_0 or f"Ancient Stone Sanctuary of {title}",
                    "architecture": "Massive monolithic basalt arches, ancient runic pillars, weathered flagstone floors.",
                    "atmosphere": "Sub-zero mountain mist, drifting woodsmoke, falling snowflakes catching torchlight.",
                    "lighting_code": "#Light 02",
                    "lighting_and_audio": "#Light 02 Volumetric God Rays (4500K beam contrast against 3000K ambient shadows) • Room Tone: howling glacial winds, crackling pine embers, distant thunder echoing through fjords.",
                    "linked_scenes": f"Act I ({env_name_0 or 'EXT. SANCTUARY'})",
                    "lighting": "#Light 02 High-Contrast Chiaroscuro & flickering hearth embers.",
                    "audio": "Howling glacial winds, crackling pine embers, distant thunder echoing through fjords.",
                },
                {
                    "code": "#Env 02",
                    "name": env_name_1 or f"Whispering Pines of {setting}",
                    "architecture": "Dense ancient boreal forest canopy, moss-draped boulders, winding frozen riverbanks.",
                    "atmosphere": "Deep frost, breath condensation vapor, shafts of pale morning sun piercing mist.",
                    "lighting_code": "#Light 04",
                    "lighting_and_audio": "#Light 04 Silvery Blue Moonlight (6500K cool diffused overhead key, soft 2:1 fill) • Room Tone: branches groaning under heavy snowpack, crunching frozen pine needles.",
                    "linked_scenes": f"Act II-A ({env_name_1 or 'EXT. WHISPERING PINES'})",
                    "lighting": "#Light 04 Dawn Softbox with diffuse pale cyan rim illumination.",
                    "audio": "Branches groaning under heavy snowpack, crunching frozen pine needles, distant wolf call.",
                },
                {
                    "code": "#Env 03",
                    "name": env_name_2 or "High Keep Obsidian Throne Room",
                    "architecture": "Vast vaulted timber hall lined with blackened iron shields, towering hearth brazier, frost-rimed glass.",
                    "atmosphere": "Oppressive heavy air, bitter chill battling radiating furnace heat, suspended dust motes.",
                    "lighting_code": "#Light 01",
                    "lighting_and_audio": "#Light 01 Golden Hour Backlit (2800K golden warmth, rim light enveloping subject silhouette) • Room Tone: heavy footsteps on flagstone, low murmur of war council.",
                    "linked_scenes": f"Act II-B ({env_name_2 or 'INT. OBSIDIAN THRONE'})",
                    "lighting": "#Light 01 Volumetric Amber Rim & deep iron shadows.",
                    "audio": "Heavy footsteps on flagstone, low murmur of war council, clatter of forged steel.",
                },
                {
                    "code": "#Env 04",
                    "name": env_name_3 or "Subterranean Runic Crypts",
                    "architecture": "Deep cavernous underground tomb, carved ancestor sarcophagi, subterranean glacial seep.",
                    "atmosphere": "Permafrost condensation, eerie stillness, faint blue luminescence from vein crystals.",
                    "lighting_code": "#Light 06",
                    "lighting_and_audio": "#Light 06 Neon Cyberpunk / Bioluminescent Glow (cyan 480nm specular reflections) • Room Tone: rhythmic glacial water dripping, hollow acoustic resonance.",
                    "linked_scenes": f"Act III ({env_name_3 or 'INT. RUNIC CRYPTS'})",
                    "lighting": "#Light 06 Bioluminescent Cyan Glow reflecting off wet ice walls.",
                    "audio": "Rhythmic glacial water dripping, hollow acoustic resonance, low cavern wind hiss.",
                },
                {
                    "code": "#Env 05",
                    "name": env_name_4 or "The Shattered Ridge / Climax Arena",
                    "architecture": "Exposed mountain pinnacle, jagged slate crags overlooking stormy fjord expanse.",
                    "atmosphere": "Violent blizzard gales, swirling ice crystals, dramatic tempest storm clouds.",
                    "lighting_code": "#Light 05",
                    "lighting_and_audio": "#Light 05 Flickering Torch / Silhouette Against Tempest (1800K dynamic flame luminance, stark lightning bursts) • Room Tone: deafening storm roar, gale-force wind whistling against stone cliffs.",
                    "linked_scenes": f"Act IV ({env_name_4 or 'EXT. SHATTERED RIDGE'})",
                    "lighting": "#Light 05 Dramatic Backlit Silhouette & stark lightning flashes.",
                    "audio": "Deafening storm roar, gale-force wind whistling against stone cliffs, thunder crashes.",
                },
            ]
            props = [
                {
                    "code": "#Prop 01",
                    "name": f"Rune-Etched War Seal of {title}",
                    "owner_character": owner_0,
                    "material_and_wear": "Hand-forged bog iron inlaid with beaten silver runes, worn leather lanyard, specular highlights along battle-notched edges.",
                    "narrative_utility": f"Hero ancestral heirloom carried by {owner_0}; anchors sacred vow of redemption.",
                    "description": f"Ancestral war seal belonging to {owner_0}.",
                    "material": "Hand-forged bog iron inlaid with beaten silver runes and braided leather lanyard.",
                    "weight": f"Hero ancestral heirloom carried by {owner_0}; anchors vow of redemption.",
                    "action": "Held firmly in clenched fist, traced with thumb before entering battle.",
                },
                {
                    "code": "#Prop 02",
                    "name": "Meteoric Steel Broadsword",
                    "owner_character": owner_1,
                    "material_and_wear": "Pattern-welded Damascus steel blade with deep fuller, bronze crossguard, and deer-antler hilt showing sweat stains.",
                    "narrative_utility": f"Signature weapon wielded by {owner_1} across a dozen campaigns.",
                    "description": f"Damascus steel broadsword wielded by {owner_1}.",
                    "material": "Pattern-welded Damascus steel blade with deep fuller, bronze crossguard, and deer-antler hilt.",
                    "weight": f"Signature weapon wielded by {owner_1} carrying battle notches from a dozen campaigns.",
                    "action": "Drawn smoothly from worn leather scabbard with metallic resonance.",
                },
                {
                    "code": "#Prop 03",
                    "name": "Chiseled Obsidian Oath-Stone",
                    "owner_character": owner_2,
                    "material_and_wear": "Fractured volcanic glass inscribed with bloodline covenant vows and gold leaf filler, razor-sharp bevels.",
                    "narrative_utility": f"Binding covenant token used by {owner_2} as a symbol of unyielding authority.",
                    "description": f"Volcanic glass oath-stone carried by {owner_2}.",
                    "material": "Fractured volcanic glass inscribed with ancient bloodline vows and gold leaf filler.",
                    "weight": f"Binding covenant token used by {owner_2} as symbol of tyrannical authority.",
                    "action": "Slammed onto treaty table; pulses with faint thermal shimmer.",
                },
                {
                    "code": "#Prop 04",
                    "name": "Carved Bone Navigation Astrolabe",
                    "owner_character": owner_3,
                    "material_and_wear": "Mammoth ivory rings with brass astronomical dials, cracked quartz lens, weathered tallow wax sealant.",
                    "narrative_utility": f"Guide instrument relied upon by {owner_3} to navigate forbidden northern ice shelves.",
                    "description": f"Navigation astrolabe preserved by {owner_3}.",
                    "material": "Mammoth ivory rings with brass astronomical dials and cracked quartz lens.",
                    "weight": f"Guide instrument relied upon by {owner_3} to navigate the forbidden northern ice shelves.",
                    "action": "Held up against night sky to align constellations through quartz sight.",
                },
                {
                    "code": "#Prop 05",
                    "name": "Ancestral Horn of Awakening",
                    "owner_character": owner_4,
                    "material_and_wear": "Polished Aurochs horn banded in embossed silver and wrapped in dyed crimson sinew, weathered mouthpiece.",
                    "narrative_utility": "Climactic rallying instrument capable of echoing across mountain passes to summon allied factions.",
                    "description": "Rallying horn capable of awakening allied factions.",
                    "material": "Polished Aurochs horn banded in embossed silver and wrapped in dyed crimson sinew.",
                    "weight": "Climactic rallying instrument capable of echoing across mountain passes.",
                    "action": "Raised to lips with deep breath, sounded with low vibrating war blast.",
                },
            ]
        elif is_sci_fi:
            envs = [
                {
                    "code": "#Env 01",
                    "name": env_name_0 or f"Metropolitan Core & Command Deck of {title}",
                    "architecture": "Brutalist composite steel-and-aerogel architecture, towering data displays, modular consoles.",
                    "atmosphere": "Air-scrubbed climate-controlled atmosphere, soft ventilation hum, zero ambient humidity.",
                    "lighting_code": "#Light 01",
                    "lighting_and_audio": "#Light 01 Volumetric Amber Rim (2800K golden warmth, cool console wash) • Room Tone: continuous electronics hum, soft synthesized alerts, muffled magnetic lifts.",
                    "linked_scenes": f"Act I ({env_name_0 or 'INT. COMMAND DECK'})",
                    "lighting": "#Light 01 Volumetric Amber Rim & cool console glow.",
                    "audio": "Continuous electronics hum, soft synthesized alerts, muffled magnetic lifts.",
                },
                {
                    "code": "#Env 02",
                    "name": env_name_1 or f"Perimeter Docking Sector ({setting})",
                    "architecture": "Exposed titanium truss gantries, pressurized magnetic airlocks, reinforced blast doors.",
                    "atmosphere": "Vented nitrogen steam, ozone scent, oil-streaked industrial floor plates.",
                    "lighting_code": "#Light 03",
                    "lighting_and_audio": "#Light 03 Low-Key Chiaroscuro (8:1 Key-to-fill ratio, 3200K single hard key) • Room Tone: pneumatic hiss of depressurization, heavy servo whining, distant industrial klaxon.",
                    "linked_scenes": f"Act II-A ({env_name_1 or 'EXT. DOCKING GANTRIES'})",
                    "lighting": "#Light 03 Neon Sodium Vapor & warning strobe pulses.",
                    "audio": "Pneumatic hiss of depressurization, heavy servo whining, distant industrial klaxon.",
                },
                {
                    "code": "#Env 03",
                    "name": env_name_2 or "Subterranean Reactor Catacombs",
                    "architecture": "Cavernous magnetic containment vaults, supercooled piping arrays, steel catwalks.",
                    "atmosphere": "Cryogenic frost lining conduit joints, thermal haze above vent grates.",
                    "lighting_code": "#Light 06",
                    "lighting_and_audio": "#Light 06 Neon Cyberpunk (cyan 480nm & magenta 650nm) • Room Tone: low-frequency sub-bass generator vibration, periodic liquid-gas discharge.",
                    "linked_scenes": f"Act II-B ({env_name_2 or 'INT. REACTOR CATACOMBS'})",
                    "lighting": "#Light 06 Bioluminescent Cyan Glow & pulsing warning halos.",
                    "audio": "Low-frequency sub-bass generator vibration, periodic liquid-gas discharge.",
                },
                {
                    "code": "#Env 04",
                    "name": env_name_3 or "Abandoned Sensor Observatory",
                    "architecture": "Retro-fitted geodesic dome with peeling electromagnetic shielding, shattered viewport panels.",
                    "atmosphere": "Static charge in the air, swirling airborne dust motes catching celestial light.",
                    "lighting_code": "#Light 02",
                    "lighting_and_audio": "#Light 02 Volumetric God Rays (4500K collimated beam contrast against 3000K shadows) • Room Tone: wind buffeting exterior antenna array, erratic spark discharges.",
                    "linked_scenes": f"Act III ({env_name_3 or 'INT. SENSOR OBSERVATORY'})",
                    "lighting": "#Light 02 High-Contrast Chiaroscuro & starfield wash.",
                    "audio": "Wind buffeting exterior antenna array, erratic spark discharges, hollow echoes.",
                },
                {
                    "code": "#Env 05",
                    "name": env_name_4 or "Orbital Spire Climax Platform",
                    "architecture": "Narrow cantilevered titanium observation spur suspended above planetary cloud deck.",
                    "atmosphere": "Thin stratospheric crosswinds, high-altitude vacuum chill, lightning dancing below.",
                    "lighting_code": "#Light 05",
                    "lighting_and_audio": "#Light 05 Silhouette Against Planetary Curvature (1500K inferno horizon exposure, total silhouette) • Room Tone: screaming wind shear, resonant structural strain, howling slipstream.",
                    "linked_scenes": f"Act IV ({env_name_4 or 'EXT. ORBITAL SPIRE'})",
                    "lighting": "#Light 05 Dramatic Backlit Silhouette against planetary curvature.",
                    "audio": "Screaming wind shear, resonant structural strain, howling slipstream.",
                },
            ]
            props = [
                {
                    "code": "#Prop 01",
                    "name": f"Neural Link Interface Key of {title}",
                    "owner_character": owner_0,
                    "material_and_wear": "Matte carbon-fiber casing with gold-plated micro-pins, hairline scuffs, and status LED diode.",
                    "narrative_utility": f"Protagonist identity authenticator owned by {owner_0}; stores encrypted memories and clearance codes.",
                    "description": f"Neural link authenticator key owned by {owner_0}.",
                    "material": "Matte carbon-fiber casing with gold-plated micro-pins and status LED diode.",
                    "weight": f"Protagonist identity authenticator owned by {owner_0}; stores encrypted memories and clearance codes.",
                    "action": "Inserted into neuro-port with distinct tactile dual-click.",
                },
                {
                    "code": "#Prop 02",
                    "name": "Overcharged Pulse Disruptor",
                    "owner_character": owner_1,
                    "material_and_wear": "Machined tungsten alloy with ceramic heat shield and exposed energy coil showing heat discoloration.",
                    "narrative_utility": f"Compact lethal sidearm calibrated by {owner_1} for close-quarters breach encounters.",
                    "description": f"Pulse disruptor sidearm wielded by {owner_1}.",
                    "material": "Machined tungsten alloy with ceramic heat shield and exposed energy coil.",
                    "weight": f"Compact lethal sidearm calibrated by {owner_1} for close-quarters breach encounters.",
                    "action": "Racked back to arm coil with rising acoustic pitch.",
                },
                {
                    "code": "#Prop 03",
                    "name": "Encrypted Syndicate Core Token",
                    "owner_character": owner_2,
                    "material_and_wear": "Monolithic synthetic black diamond etched with optical quantum lattices, cold to the touch.",
                    "narrative_utility": f"Crucial narrative MacGuffin held by {owner_2} containing decrypted master override.",
                    "description": f"Synthetic diamond core token held by {owner_2}.",
                    "material": "Monolithic synthetic black diamond etched with optical quantum lattices.",
                    "weight": f"Crucial narrative MacGuffin held by {owner_2} containing decrypted master system override.",
                    "action": "Handled with protective thermal gloves; pulses with erratic amber glow.",
                },
                {
                    "code": "#Prop 04",
                    "name": "Atmospheric Scanner Unit",
                    "owner_character": owner_3,
                    "material_and_wear": "Impact-resistant polycarbonate shell with analog dial gauges and sensor probe, silicone grip.",
                    "narrative_utility": f"Field survival tool used by {owner_3} to test toxicity and electromagnetic interference.",
                    "description": f"Atmospheric scanner unit operated by {owner_3}.",
                    "material": "Impact-resistant polycarbonate shell with analog dial gauges and sensor probe.",
                    "weight": f"Field survival tool used by {owner_3} to test toxicity and electromagnetic interference.",
                    "action": "Toggled on with switch click, sweeping across environment to read spikes.",
                },
                {
                    "code": "#Prop 05",
                    "name": "Zero-Point Catalyst Module",
                    "owner_character": owner_4,
                    "material_and_wear": "Stabilized magnetic torus housing a glowing plasma singularity, heavy ceramic seals.",
                    "narrative_utility": "Climax operational key required to overload or restore main station power.",
                    "description": "Magnetic torus catalyst module required for station power.",
                    "material": "Stabilized magnetic torus housing a glowing plasma singularity.",
                    "weight": "Climax operational key required to overload or restore main station power.",
                    "action": "Twisted and locked into primary coupling with hydraulic clamp sound.",
                },
            ]
        else:
            envs = [
                {
                    "code": "#Env 01",
                    "name": env_name_0 or f"Primary Domain & Quarters of {title}",
                    "architecture": "Grounded architectural styling reflecting origins and physical world.",
                    "atmosphere": "Naturalistic atmospheric texture, balanced humidity, organic airborne particles.",
                    "lighting_code": "#Light 01",
                    "lighting_and_audio": "#Light 01 Golden Hour Backlit (2800K golden warmth, rim light enveloping subject silhouette) • Room Tone: grounded environmental room tone, subtle Foley texture, distant external ambience.",
                    "linked_scenes": f"Act I ({env_name_0 or 'EXT. PRIMARY DOMAIN'})",
                    "lighting": "#Light 01 Warm Volumetric Key & natural practical lights.",
                    "audio": "Grounded environmental room tone, subtle Foley texture, distant external ambience.",
                },
                {
                    "code": "#Env 02",
                    "name": env_name_1 or f"Threshold Crossing ({setting})",
                    "architecture": "Expansive transitional terrain marking the shift from safety to conflict.",
                    "atmosphere": "Gathering weather front, shifting crosswinds, changing environmental texture.",
                    "lighting_code": "#Light 04",
                    "lighting_and_audio": "#Light 04 Silvery Blue Moonlight (6500K cool diffused overhead key, soft 2:1 fill) • Room Tone: ambient wind movement, shifting ground debris, atmospheric tension.",
                    "linked_scenes": f"Act II-A ({env_name_1 or 'EXT. THRESHOLD'})",
                    "lighting": "#Light 04 Natural Golden Hour & long dramatic cast shadows.",
                    "audio": "Ambient wind movement, shifting ground debris, atmospheric tension.",
                },
                {
                    "code": "#Env 03",
                    "name": env_name_2 or "The Opposing Citadel / Hostile Sector",
                    "architecture": "Imposing hostile architecture designed to overwhelm scale and establish stakes.",
                    "atmosphere": "Stale oppressive air, dim ambient illumination, cold thermal balance.",
                    "lighting_code": "#Light 03",
                    "lighting_and_audio": "#Light 03 Low-Key Chiaroscuro (8:1 Key-to-fill ratio, 3200K single hard key) • Room Tone: echoing footsteps, mechanical or industrial resonance, heavy silence.",
                    "linked_scenes": f"Act II-B ({env_name_2 or 'INT. CITADEL'})",
                    "lighting": "#Light 02 High-Contrast Chiaroscuro & harsh downward spot illumination.",
                    "audio": "Echoing footsteps, mechanical or industrial resonance, heavy silence.",
                },
                {
                    "code": "#Env 04",
                    "name": env_name_3 or "The Hidden Sanctuary / Lore Vault",
                    "architecture": "Secluded sanctuary preserving history, memories, and forgotten truths.",
                    "atmosphere": "Still, tranquil air with suspended dust particles drifting in light rays.",
                    "lighting_code": "#Light 07",
                    "lighting_and_audio": "#Light 07 Overcast Soft (Fully diffused 6000K skylight through cloud deck) • Room Tone: soft acoustic hush, faint natural breeze, peaceful resonance.",
                    "linked_scenes": f"Act III ({env_name_3 or 'INT. HIDDEN SANCTUARY'})",
                    "lighting": "#Light 06 Gentle Bioluminescent or Diffuse Shafts of natural light.",
                    "audio": "Soft acoustic hush, faint natural breeze, peaceful resonance.",
                },
                {
                    "code": "#Env 05",
                    "name": env_name_4 or "The Climax Crucible / Final Arena",
                    "architecture": "High-stakes confrontation arena where all conflicts culminate.",
                    "atmosphere": "Volatile weather, dramatic environmental shifts, high emotional energy.",
                    "lighting_code": "#Light 05",
                    "lighting_and_audio": "#Light 05 Silhouette Against Climax Fire (1800K dynamic flame luminance, stark lightning flashes) • Room Tone: deafening sonic clash, resonant environmental Foley, peak climactic roar.",
                    "linked_scenes": f"Act IV ({env_name_4 or 'EXT. CLIMAX ARENA'})",
                    "lighting": "#Light 05 Dramatic Backlit Silhouette & tempest lightning.",
                    "audio": "Deafening sonic clash, resonant environmental Foley, peak climactic roar.",
                },
            ]
            props = [
                {
                    "code": "#Prop 01",
                    "name": f"Signature Keepsake of {title}",
                    "owner_character": owner_0,
                    "material_and_wear": "Handcrafted personal artifact bearing tactile scratches, aged patina, and engraved crest.",
                    "narrative_utility": f"Emotional anchor connecting {owner_0} to core dramatic objective.",
                    "description": f"Personal keepsake belonging to {owner_0}.",
                    "material": "Handcrafted personal artifact bearing tactile scratches and aged patina.",
                    "weight": f"Emotional anchor connecting {owner_0} to their core objective.",
                    "action": "Turned over in fingers during moments of doubt or contemplation.",
                },
                {
                    "code": "#Prop 02",
                    "name": "Tactical Master Instrument",
                    "owner_character": owner_1,
                    "material_and_wear": "Hardened alloy craftsmanship with ergonomic grip, functional wear, and matte anti-reflective finish.",
                    "narrative_utility": f"Primary operational tool or weapon relied upon by {owner_1} throughout the story.",
                    "description": f"Tactical instrument wielded by {owner_1}.",
                    "material": "Hardened alloy craftsmanship with ergonomic grip and functional wear.",
                    "weight": f"Primary operational tool or weapon relied upon by {owner_1} throughout the story.",
                    "action": "Gripped firmly and wielded with trained precision.",
                },
                {
                    "code": "#Prop 03",
                    "name": "Antagonist's Emissary Token",
                    "owner_character": owner_2,
                    "material_and_wear": "Distinctive insignia made of cold cast bronze or polished stone with sharp bevels.",
                    "narrative_utility": f"Physical reminder of the antagonistic force and looming deadline carried by {owner_2}.",
                    "description": f"Antagonist insignia token carried by {owner_2}.",
                    "material": "Distinctive insignia made of cold metal or polished stone.",
                    "weight": f"Physical reminder of the antagonistic force and looming deadline carried by {owner_2}.",
                    "action": "Discovered at a critical crime or breach scene.",
                },
                {
                    "code": "#Prop 04",
                    "name": "Decrypted Story Codex",
                    "owner_character": owner_3,
                    "material_and_wear": "Weathered bound parchment or encrypted storage drive with faded markings and thermal tape.",
                    "narrative_utility": f"Reveals the crucial hidden revelation at the narrative midpoint to {owner_3}.",
                    "description": f"Midpoint story codex deciphered by {owner_3}.",
                    "material": "Weathered bound material or encrypted storage drive with faded markings.",
                    "weight": f"Reveals the crucial hidden revelation at the narrative midpoint to {owner_3}.",
                    "action": "Unfolded or accessed with trembling hands to reveal truth.",
                },
                {
                    "code": "#Prop 05",
                    "name": "The Climactic Keystone",
                    "owner_character": owner_4,
                    "material_and_wear": "Pristine or volatile core artifact embodying the story's resolution, pulsing with internal energy.",
                    "narrative_utility": "Decisive object whose destruction or activation resolves the central conflict.",
                    "description": "Climactic resolution keystone artifact.",
                    "material": "Pristine or volatile core artifact embodying the story's resolution.",
                    "weight": "Decisive object whose destruction or activation resolves the central conflict.",
                    "action": "Activated or shattered during the final climax confrontation.",
                },
            ]

        return {"environments": envs, "props": props}

    # ==========================================================================
    # Dynamic Rules & Invariants Engine (Polya AI Director)
    # ==========================================================================

    async def generate_rules_and_invariants(
        self,
        context: ProjectNarrativeContext,
        additional_notes: str | None = None,
    ) -> dict[str, Any]:
        """Generate 5 to 7 Immutable Visual Continuity Laws and 5 to 7 Global Negative Prompts
        strictly anchored to the project narrative context, cast biometric profiles, #Env lighting codes,
        #Prop physical materiality, and active Style Taxonomy family.
        """
        dna_items = []
        if context.visual_dna_parameters:
            for k, v in context.visual_dna_parameters.items():
                dna_items.append(f"{k.replace('_', ' ').title()}: {v}")
        dna_str = f"- Master Visual DNA Settings: {', '.join(dna_items)}" if dna_items else ""

        # Format cast characters
        cast_lines = []
        for idx, c in enumerate(context.cast_characters):
            states_preview = ""
            if c.get("states"):
                s01 = c["states"][0]
                states_preview = f" | Baseline Wardrobe: {s01.get('wardrobe', '')[:60]}"
            cast_lines.append(
                f"- Character #{idx + 1}: {c.get('name')} (Role: {c.get('role', 'SUPPORTING')}{states_preview}) — Arc: {c.get('narrative_profile', '')[:90]}"
            )
        cast_str = "\n".join(cast_lines) if cast_lines else "No registered cast yet. Anchor biometrics to dramatic roles (PROTAGONIST, ANTAGONIST)."

        # Format storyboard scenes
        scenes_lines = []
        if context.storyboard_scenes:
            scenes_lines.append(
                "- Storyboard Narrative Progression: "
                + "; ".join(f"Act {sc.get('act_number')} Sc {sc.get('scene_number')} [{sc.get('slugline')}]: {sc.get('narrative_goal', '')[:50]}" for sc in context.storyboard_scenes[:6])
            )
        scenes_str = "\n".join(scenes_lines) if scenes_lines else "No storyboard scenes created yet. Enforce continuous cinematic framing across a 4-act progression."

        # Format environments
        env_lines = []
        for idx, e in enumerate(context.environments):
            env_lines.append(
                f"- Environment #{idx + 1} ({e.get('code', f'#Env {idx+1:02d}')} - {e.get('name')}): Architecture: {e.get('architecture', '')[:60]} | Lighting: {e.get('lighting_code', '')} {e.get('lighting', '')[:40]}"
            )
        envs_str = "\n".join(env_lines) if env_lines else (f"- Environments Summary: {context.environments_summary}" if context.environments_summary else "No registered environments yet.")

        # Format props
        prop_lines = []
        for idx, p in enumerate(context.props):
            prop_lines.append(
                f"- Hero Prop #{idx + 1} ({p.get('code', f'#Prop {idx+1:02d}')} - {p.get('name')}): Owner: {p.get('owner_character', 'Ensemble')} | Material & Wear: {p.get('material_and_wear', '')[:70]}"
            )
        props_str = "\n".join(prop_lines) if prop_lines else (f"- Hero Props Summary: {context.props_summary}" if context.props_summary else "No registered hero props yet.")

        # Retrieve Visual Grammar & Lighting Spec
        rag_result = await DirectorRAGClient.retrieve(
            scene_beat=f"{context.title} continuity: {context.synopsis[:100]}",
            style_code=context.master_style_code,
            engine="9router",
            top_k=3
        )
        visual_grammar = DirectorRAGClient.format_treatment_grammar(rag_result)
        lighting_spec = DirectorRAGClient.format_act_context(rag_result)

        user_prompt = f"""PROJECT PRODUCTION BIBLE & NARRATIVE CONTEXT:
- Film Title: {context.title}
- Core Synopsis & Premise:
{context.synopsis}
- Master Genre & Tone: {context.genre_tone}
- Aspect Ratio: {context.aspect_ratio}
- Active Operational Stage: Stage {context.operational_stage}
- Master Visual Style Code: {context.master_style_code} ({context.style_name})
- Visual Style Directives: {context.aesthetic_directives}
- Color Palette & Lighting Emulation: {context.color_grade_emulation}
{dna_str}
- World Setting: {context.world_setting}
- Additional Showrunner Notes: {additional_notes or 'None'}

{visual_grammar}
{lighting_spec}

REGISTERED CHARACTER CAST ({len(context.cast_characters)} Characters):
{cast_str}

50-SCENE STORYBOARD & RECURRING SLUGLINES ({len(context.storyboard_scenes)} Scenes):
{scenes_str}

REGISTERED PRODUCTION ENVIRONMENTS ({len(context.environments)} Envs):
{envs_str}

REGISTERED HERO PROPS ({len(context.props)} Props):
{props_str}

POLYA AI DIRECTOR MANDATE:
1. Synthesize 5 to 7 Immutable Visual Continuity Laws ('continuity_rules'):
   - Character biometric & facial invariants (facial structure, eye color, scars, never mirrored).
   - Lighting & atmospheric invariants anchored directly to registered #Env locations and official #Light codes.
   - Physical prop materiality & wear invariants anchored directly to registered #Prop items and their character owners.
   - Cinematic lens, color grade, and wardrobe degradation invariants across narrative acts.

2. Synthesize 5 to 7 Global Negative Prompt Clusters ('negative_prompts'):
   - Universal technical defects (bad anatomy, extra limbs, mutated hands, watermarks, text artifacts).
   - Style-incompatible intrusions strictly respecting the 4-Family Style Taxonomy for {context.master_style_code} ({context.style_name}):
     * CRITICAL RULE: NEVER exclude the core aesthetic or medium of {context.master_style_code}.
       - For Anime / 2D (#Style 14-17): DO NOT exclude anime cel shading, hand-drawn lines, or 2D animation.
       - For Stylized 3D (#Style 06/09/10/11): DO NOT exclude cartoonish 3D render, CGI, or stylized 3D.
       - For Stop-Motion (#Style 13): DO NOT exclude clay textures, plasticine, or stop-motion craft.
       - For Photorealistic (#Style 01-05/07/08/12/18): DO NOT exclude photorealism, photograph, or 35mm film.

OUTPUT SCHEMA (Return STRICT valid JSON only):
{{
  "continuity_rules": [
    "Law 1: Biometric invariant for protagonist...",
    "Law 2: Atmospheric lighting invariant anchored to #Env and #Light code...",
    "Law 3: Hero prop materiality and tactile wear invariant...",
    "Law 4: Style rendering pipeline and optical lens invariant...",
    "Law 5: Wardrobe and physical state sequential progression invariant (#State 01 to #State 05)...",
    "Law 6: Master chromatic color grade and tonal invariant..."
  ],
  "negative_prompts": [
    "lowres, blurry, bad anatomy, bad hands, missing fingers, extra digits, cropped, worst quality",
    "cluster 2: style-contradicting intrusion exclusions...",
    "cluster 3: unnatural physics, geometry morphing, flickering frames...",
    "cluster 4: lighting and chromatic anti-patterns...",
    "cluster 5: watermarks, stock signatures, text overlays, copyright marks"
  ]
}}"""

        messages = [
            {"role": "system", "content": POLYA_AI_DIRECTOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            raw_json = await self._call_llm(messages)
            normalized = self._normalize_rules_and_invariants(raw_json, context)
            normalized["rules_generation_meta"] = {
                "engine": "polya_ai_director_llm",
                "model": self.model,
                "director_persona": "Polya AI Director",
                "context_ingested": {
                    "style_code": context.master_style_code,
                    "characters_count": len(context.cast_characters),
                    "environments_count": len(context.environments),
                    "props_count": len(context.props),
                    "scenes_count": len(context.storyboard_scenes),
                    "has_synopsis": bool(context.synopsis),
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "fallback_reason": None,
            }
            return normalized
        except Exception as exc:
            logger.warning(
                "Polya AI Director LLM call failed (%s). Activating contextual procedural fallback for rules and invariants.",
                exc,
            )
            fallback_data = self._generate_procedural_rules_and_invariants(context)
            fallback_data["rules_generation_meta"] = {
                "engine": "procedural_fallback",
                "model": None,
                "director_persona": "Polya AI Director (Procedural Fallback)",
                "context_ingested": {
                    "style_code": context.master_style_code,
                    "characters_count": len(context.cast_characters),
                    "environments_count": len(context.environments),
                    "props_count": len(context.props),
                    "scenes_count": len(context.storyboard_scenes),
                    "has_synopsis": bool(context.synopsis),
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "fallback_reason": f"LLM execution failed ({type(exc).__name__}: {str(exc)[:150]})",
            }
            return fallback_data

    def _normalize_rules_and_invariants(
        self,
        raw_json: dict[str, Any],
        context: ProjectNarrativeContext,
    ) -> dict[str, Any]:
        """Normalize continuity rules and global prompt negatives with dual-key synchronization
        and deterministic Style-Conflict Sanitization."""
        procedural = self._generate_procedural_rules_and_invariants(context)

        raw_laws = (
            raw_json.get("continuity_rules")
            or raw_json.get("continuity_laws")
            or []
        ) if isinstance(raw_json, dict) else []
        if isinstance(raw_laws, str):
            raw_laws = [raw_laws]
        elif not isinstance(raw_laws, list):
            raw_laws = []

        cleaned_laws = [str(l).strip() for l in raw_laws if str(l).strip()]
        if len(cleaned_laws) < 3:
            for pl in procedural["continuity_rules"]:
                if pl not in cleaned_laws:
                    cleaned_laws.append(pl)
                if len(cleaned_laws) >= 6:
                    break

        raw_negs = (
            raw_json.get("negative_prompts")
            or raw_json.get("prompt_negatives")
            or []
        ) if isinstance(raw_json, dict) else []
        if isinstance(raw_negs, str):
            raw_negs = [raw_negs]
        elif not isinstance(raw_negs, list):
            raw_negs = []

        cleaned_negs = [str(n).strip() for n in raw_negs if str(n).strip()]
        if len(cleaned_negs) < 3:
            for pn in procedural["negative_prompts"]:
                if pn not in cleaned_negs:
                    cleaned_negs.append(pn)
                if len(cleaned_negs) >= 5:
                    break

        # Deterministic style-conflict sanitization
        sanitized_negs = sanitize_negative_prompts_for_style(
            cleaned_negs,
            context.master_style_code,
        )
        if len(sanitized_negs) < 3:
            for pn in procedural["negative_prompts"]:
                if pn not in sanitized_negs:
                    sanitized_negs.append(pn)

        return {
            "continuity_rules": cleaned_laws,
            "continuity_laws": cleaned_laws,
            "negative_prompts": sanitized_negs,
            "prompt_negatives": sanitized_negs,
        }

    def _generate_procedural_rules_and_invariants(
        self,
        context: ProjectNarrativeContext,
    ) -> dict[str, Any]:
        """Generate high-fidelity contextual rules and invariants dynamically synthesized from active project context."""
        title = context.title or "Cinematic Production"
        genre = (context.genre_tone or "Cinematic Drama").split("/")[0].strip()

        # Biometric invariant: anchor to first cast member if available
        cast = context.cast_characters
        if cast and cast[0].get("name"):
            char_name = cast[0]["name"]
            char_law = (
                f"{char_name} signature biometric features, facial bone structure, and eye color "
                f"must remain strictly consistent across all scenes (never inverted or flipped)."
            )
        else:
            char_law = (
                "Protagonist signature biometric features, facial bone structure, and eye color "
                "must remain strictly consistent across all scenes (never inverted or flipped)."
            )

        # Environment & lighting invariant: anchor to registered #Env and #Light code
        envs = context.environments
        if envs and envs[0].get("name"):
            env0 = envs[0]
            env_name = env0.get("name")
            lcode = env0.get("lighting_code") or "#Light 01"
            env_law = (
                f"Atmospheric illumination in {env_name} is strictly anchored to {lcode} specification; "
                f"lighting ratios must preserve spatial depth without flat overexposure."
            )
        else:
            env_law = (
                f"Atmospheric illumination across primary environments must preserve {context.style_name} "
                f"volumetric spatial depth without flat overexposure."
            )

        # Prop invariant: anchor to registered hero prop
        props = context.props
        if props and props[0].get("name"):
            p0 = props[0]
            pname = p0.get("name")
            powner = p0.get("owner_character", "Hero")
            pmaterial = (p0.get("material_and_wear") or p0.get("material") or "tactile physical materials")[:60]
            prop_law = (
                f"{pname} ({powner}) physical materiality ({pmaterial}) must maintain continuous "
                f"tactile patina, wear patterns, and interaction fidelity across all story acts."
            )
        else:
            prop_law = (
                "Signature hero props must maintain continuous tactile patina, wear patterns, "
                "and interaction fidelity across all story acts."
            )

        # Visual style invariant
        style_law = (
            f"Visual rendering pipeline must strictly adhere to {context.master_style_code} ({context.style_name}): "
            f"{context.aesthetic_directives[:90] or 'pristine cinematic framing'}."
        )

        # Character wardrobe / state progression invariant
        state_law = (
            "Character costume degradation, physical damage, and wardrobe wear must advance strictly "
            "sequentially from #State 01 through #State 05 across narrative acts."
        )

        # Color grade invariant
        color_law = (
            f"Color palette timing must faithfully maintain {context.color_grade_emulation or 'master chromatic grade and tonal balance'} "
            f"without color temperature drift."
        )

        # Storyboard sequence invariant
        if context.storyboard_scenes:
            pacing_law = (
                f"Cinematic framing and optical axis must remain strictly continuous across Storyboard sequence "
                f"({len(context.storyboard_scenes)} scenes) with zero phantom geometry morphing."
            )
        else:
            pacing_law = (
                "Cinematic framing and optical axis must remain strictly continuous across all scenes "
                "with zero phantom geometry morphing."
            )

        laws = [char_law, env_law, prop_law, style_law, state_law, color_law, pacing_law]

        # Style-aware negative clusters based on 4 canonical families
        family = get_style_family(context.master_style_code)
        if family == "anime_2d":
            neg_clusters = [
                "lowres, blurry, bad anatomy, bad hands, missing fingers, extra digits, cropped, worst quality",
                "photorealistic live action, 3D CGI gloss, plastic skin texture, lifelike skin pores, real human photo",
                "uncanny valley realistic rendering, 3D polygon mesh, raytraced reflections, digital 3D model",
                "unnatural physics, morphing limbs, flickering line art, stuttering frames, broken inbetweens",
                "watermarks, stock photo signatures, text overlays, copyright markings, logos",
            ]
        elif family == "stylized_3d":
            neg_clusters = [
                "lowres, blurry, bad anatomy, bad hands, missing fingers, extra digits, cropped, worst quality",
                "live-action photograph, realistic film grain, archival film noise, real human pores, 35mm photograph",
                "flat 2D anime cel, hand-drawn paper sketch, pencil drawing, monochrome line art",
                "unnatural physics, broken mesh geometry, clipping textures, morphing limbs, inverted polygons",
                "watermarks, stock photo signatures, text overlays, copyright markings, borders, logos",
            ]
        elif family == "stop_motion":
            neg_clusters = [
                "lowres, blurry, bad anatomy, bad hands, missing fingers, extra digits, cropped, worst quality",
                "smooth digital CGI, hyper-glossy 3D render, vector illustration, flat 2D anime cel",
                "hyper-smooth 60fps interpolation, motion blur, synthetic computer graphics, digital polish",
                "unnatural physics, morphing limbs, disappearing geometry, digital video compression noise",
                "watermarks, stock photo signatures, text overlays, copyright markings, logos",
            ]
        else:  # photorealistic
            neg_clusters = [
                "lowres, blurry, bad anatomy, bad hands, missing fingers, extra digits, cropped, worst quality",
                "cartoonish 3D render, anime cel shading, watercolor artifacts, 2D illustration, sketch, drawing",
                "oversaturated CGI gloss, plastic skin textures, uncanny valley synthetic sheen, video game graphics",
                "unnatural physics, morphing limbs, flickering geometry, frame stutter, ghosting artifacts",
                "watermarks, stock photo signatures, text overlays, copyright markings, borders, logos",
            ]

        sanitized_negs = sanitize_negative_prompts_for_style(neg_clusters, context.master_style_code)

        return {
            "continuity_rules": laws,
            "continuity_laws": laws,
            "negative_prompts": sanitized_negs,
            "prompt_negatives": sanitized_negs,
        }

    # ==========================================================================
    # Strategic Structure Advisory
    # ==========================================================================

    def analyze_narrative_structure(
        self,
        project_context: ProjectNarrativeContext | dict[str, Any] | None = None,
        title: str = "",
        synopsis: str = "",
        genre_tone: str = "",
        master_style_code: str = "",
        total_scenes: int = 100,
    ) -> dict[str, Any]:
        """Polya AI Strategic Advisory: Analyze narrative parameters and recommend optimal dramatic structure."""
        if isinstance(project_context, ProjectNarrativeContext):
            p_title = project_context.title or title
            p_synopsis = project_context.synopsis or synopsis
            p_genre = project_context.genre_tone or genre_tone
            p_style = project_context.master_style_code or master_style_code
        elif isinstance(project_context, dict):
            p_title = project_context.get("title", "") or title
            p_synopsis = project_context.get("synopsis", "") or synopsis
            p_genre = project_context.get("genre_tone", "") or project_context.get("genre", "") or genre_tone
            p_style = project_context.get("master_style_code", "") or master_style_code
        else:
            p_title = title
            p_synopsis = synopsis
            p_genre = genre_tone
            p_style = master_style_code

        full_text = f"{p_title} {p_synopsis} {p_genre}".lower()

        # Strategic recommendation decision matrix
        if any(k in full_text for k in ["youtube", "tiktok", "reels", "viral", "slapstick", "kids", "short", "teaser"]) or (
            total_scenes <= 50 and any(k in full_text for k in ["animation", "cartoon", "comedy"])
        ):
            rec = "youtube_viral"
            rationale = (
                f"Berdasarkan premis '{p_title}' yang mengusung nada dinamis/komedi serta target durasi cepat ({p_genre}), "
                f"struktur YouTube Viral direkomendasikan untuk memaksimalkan retensi audiens di 10 detik pertama (In-Media-Res Teaser) "
                f"dan menjaga eskalasi visual tanpa penurunan ritme dramatik."
            )
        elif any(k in full_text for k in ["epic", "fantasy", "tragedy", "saga", "kingdom", "political", "dynasty", "historical"]) or p_style in ("#Style 04", "#Style 07"):
            rec = "5_act"
            rationale = (
                f"Untuk skala cerita epik '{p_title}' dengan world-building mendalam ({p_genre}), "
                f"struktur 5 Babak (Freytag's Pyramid) direkomendasikan guna memberikan ruang memadai bagi intrik antarfaksi, "
                f"titik balik klimaks di Babak III, serta katarsis konsekuensi tragis/kemenangan di Babak V."
            )
        elif any(k in full_text for k in ["drama", "romance", "biopic", "indie", "intimate", "character study"]):
            rec = "3_act"
            rationale = (
                f"Premis '{p_title}' menitikberatkan pada transformasi karakter internal dan konflik emosional ({p_genre}). "
                f"Struktur Klasik 3 Babak (Aristotelian) memberikan fokus maksimal pada babak konfrontasi panjang (50%) "
                f"tanpa distraksi subplot midpoint ganda."
            )
        else:
            rec = "4_act"
            rationale = (
                f"Sebagai film berformat komersial/sinematik ({p_genre}), struktur Hollywood 4 Babak (Save the Cat Midpoint Split) "
                f"merupakan pilihan standar industri paling solid. Struktur ini membagi babak kedua menjadi Rising Stakes (II-A) "
                f"dan Dark Night Crisis (II-B) yang menjamin momentum ketegangan stabil menuju klimaks."
            )

        rag_struct = ScreenwriterRAGClient.retrieve_structure_rules_sync(
            style_code=p_style,
            structure_type=rec,
            total_scenes=total_scenes,
            query=f"{p_title} {p_genre} {p_synopsis[:240]}".strip(),
            top_k=2,
        )
        rag_items = rag_struct.get("items") or []
        if rag_items:
            top_rule = rag_items[0]
            rule_title = top_rule.get("title") or top_rule.get("rule_code") or "Dramaturgy Invariant"
            rule_text = str(top_rule.get("rule_text") or "").strip()
            if rule_text:
                rationale += f" [Screenwriter Invariant — {rule_title}: {rule_text[:220]}]"

        return {
            "recommended_structure": rec,
            "strategic_rationale": rationale,
            "options": list(STRUCTURE_DEFINITIONS.values()),
        }

    async def analyze_narrative_structure_hybrid(
        self,
        project_context: ProjectNarrativeContext | dict[str, Any] | None = None,
        title: str = "",
        synopsis: str = "",
        genre_tone: str = "",
        master_style_code: str = "",
        total_scenes: int = 100,
    ) -> dict[str, Any]:
        """Hybrid Structure Advisory: combines Screenwriter RAG (8766) + LLM premise reasoning with heuristic fallback."""
        base_advisory = self.analyze_narrative_structure(
            project_context=project_context,
            title=title,
            synopsis=synopsis,
            genre_tone=genre_tone,
            master_style_code=master_style_code,
            total_scenes=total_scenes,
        )
        if isinstance(project_context, ProjectNarrativeContext):
            p_title = project_context.title or title
            p_synopsis = project_context.synopsis or synopsis
            p_genre = project_context.genre_tone or genre_tone
            p_style = project_context.master_style_code or master_style_code
        elif isinstance(project_context, dict):
            p_title = project_context.get("title", "") or title
            p_synopsis = project_context.get("synopsis", "") or synopsis
            p_genre = project_context.get("genre_tone", "") or project_context.get("genre", "") or genre_tone
            p_style = project_context.get("master_style_code", "") or master_style_code
        else:
            p_title, p_synopsis, p_genre, p_style = title, synopsis, genre_tone, master_style_code

        style_family = get_style_family(p_style or "")
        sw_rules = await ScreenwriterRAGClient.retrieve_structure_rules(
            style_code=p_style,
            structure_type=base_advisory["recommended_structure"],
            total_scenes=total_scenes,
            query=f"{p_title} {p_genre} {p_synopsis[:240]}".strip(),
            top_k=3,
        )
        sw_block = str(sw_rules.get("prompt_block") or "").strip()
        style_dir = STYLE_FAMILY_WRITING_DIRECTIVES.get(style_family, "")

        valid_types = {"3_act", "4_act", "youtube_viral", "5_act"}
        base_rec = base_advisory["recommended_structure"]
        prompt = (
            "You are Polya AI — Hollywood Screenwriter & Dramatic Structure Strategist.\n"
            "Analyze the premise, genre, visual style family, and scene budget, then advise on the single strongest dramatic structure among: "
            "'3_act' (intimate/indie/character study/drama), '4_act' (commercial action/thriller), "
            "'youtube_viral' (viral/shorts/high-retention), '5_act' (epic/fantasy/tragedy/saga).\n\n"
            f"Title: {p_title}\nGenre/Tone: {p_genre}\nStyle Code: {p_style or '#Style 01'} (Family: {style_family} — {style_dir})\n"
            f"Scene Scale Target: {total_scenes} scenes\nBaseline Structure Signal: {base_rec}\n"
            f"Synopsis / Premise: {p_synopsis or 'Feature cinematic arc'}\n"
        )
        if sw_block:
            prompt += f"\n[SCREENWRITER STRUCTURE INVARIANTS]\n{sw_block}\n"
        prompt += (
            '\nReturn ONLY valid JSON: {"recommended_structure": "3_act|4_act|youtube_viral|5_act", '
            '"strategic_rationale": "<2-3 concise sentences tying story conflict and #Style cadence to this structure>"}'
        )

        try:
            parsed = await asyncio.wait_for(
                self._call_llm(
                    messages=[
                        {"role": "system", "content": POLYA_SCREENWRITER_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    retry_on_parse_error=False,
                ),
                timeout=8.0,
            )
            if isinstance(parsed, dict) and parsed.get("strategic_rationale"):
                llm_rec = str(parsed.get("recommended_structure") or "").strip()
                # Preserve explicit indie/epic/viral baseline signals while allowing LLM to refine generic 4_act defaults
                final_rec = base_rec if base_rec != "4_act" else (llm_rec if llm_rec in valid_types else base_rec)
                llm_rationale = str(parsed["strategic_rationale"]).strip()
                combined_rationale = f"{base_advisory['strategic_rationale']} [Polya AI Advisory: {llm_rationale}]"
                return {
                    "recommended_structure": final_rec,
                    "strategic_rationale": combined_rationale,
                    "options": base_advisory["options"],
                    "source": "hybrid_llm_rag",
                }
        except Exception as exc:
            logger.info("structure_advisory_heuristic_fallback: %s", exc)

        base_advisory["source"] = "heuristic_rag"
        return base_advisory

    # ==========================================================================
    # Phase A: Master Story Treatment & Beat Sheet (Strict LLM Mode)
    # ==========================================================================

    async def generate_master_treatment(
        self,
        project_context: ProjectNarrativeContext | dict[str, Any] | None = None,
        title: str = "",
        total_scenes: int = 100,
        premise: str = "",
        characters: list[dict[str, Any]] | None = None,
        cold_open_30s: dict[str, Any] | None = None,
        project_title: str | None = None,
        structure_type: str = "4_act",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Phase A: Generate Master Story Treatment and Beat Sheet strictly via LLM without procedural mock fallbacks."""
        if isinstance(project_context, dict):
            genre = project_context.get("genre_tone") or project_context.get("genre", "Cinematic Drama")
            world = project_context.get("world_setting", "Cinematic Universe")
            style = project_context.get("style_name") or project_context.get("visual_tone", "Hollywood Cinematic")
            style_code = (
                project_context.get("master_style_code")
                or project_context.get("target_style_code")
                or project_context.get("style_code")
            )
            film_title = project_title or project_context.get("title") or title or "Cinema Feature"
            film_premise = project_context.get("synopsis") or premise or "A compelling dramatic cinematic journey."
        elif project_context:
            genre = project_context.genre_tone or "Cinematic Drama"
            world = project_context.world_setting or "Cinematic Universe"
            style = project_context.style_name or "Hollywood Cinematic"
            style_code = getattr(project_context, "master_style_code", None)
            film_title = project_title or project_context.title or title or "Cinema Feature"
            film_premise = project_context.synopsis or premise or "A compelling dramatic cinematic journey."
        else:
            genre = "Cinematic Drama"
            world = "Cinematic Universe"
            style = "Hollywood Cinematic"
            style_code = None
            film_title = project_title or title or "Cinema Feature"
            film_premise = premise or "A compelling dramatic cinematic journey."

        bounds = get_act_bounds(total_scenes, structure_type=structure_type)
        num_acts = len(bounds)

        # Format cast context with Voice DNA + 5-State emotional arcs
        cast_str, _ = self._format_cast_continuity_context(
            project_context=project_context,
            characters=characters,
            act_number=None,
            total_acts=num_acts,
        )

        struct_cfg = STRUCTURE_DEFINITIONS.get(structure_type, STRUCTURE_DEFINITIONS["4_act"])
        struct_label = struct_cfg["label"]
        act_labels_list = struct_cfg["act_labels"]

        cold_open_enabled = bool(cold_open_30s and cold_open_30s.get("enabled"))
        cold_open_inst = ""
        if cold_open_enabled:
            cold_open_inst = """
COLD OPEN (30-SECOND VISUAL HOOK MONTAGE) MANDATE:
Act I dramatic goal MUST explicitly mandate:
- Scenes 01-03: High-energy visual teaser hook montage (0-10s in-media-res hook & hero prop reveal, 10-20s escalating obstacle/rival confrontation, 20-30s climax preview & rewind/cut to linear start).
- Scene 04: Linear narrative setup starts.
"""

        acts_boundary_desc = "\n".join(
            f"- Act {idx + 1} ({act_labels_list[idx]['title']}): Scenes {b[0]} to {b[1]}"
            for idx, b in enumerate(bounds)
        )

        acts_json_example = ",\n".join(
            f"""    {{
      "act_number": {idx + 1},
      "act_title": "{act_labels_list[idx]['title']}",
      "start_scene": {b[0]},
      "end_scene": {b[1]},
      "dramatic_goal": "Dramatic goal of Act {idx + 1}",
      "key_beat": "Key turning point or beat for Act {idx + 1}"
    }}"""
            for idx, b in enumerate(bounds)
        )

        prompt = f"""You are Polya AI, Master Screenwriter. Generate a Master Screenplay Story Treatment for a feature film using {struct_label}.

Film Title: {film_title}
Genre/Tone: {genre}
Master Style: {style}
World Setting: {world}
Premise / Logline Concept: {film_premise}
Total Scenes Target: {total_scenes}
Dramatic Structure: {struct_label} ({num_acts} Acts)

Ensemble Cast Available:
{cast_str}

Scene Boundaries ({num_acts} Acts):
{acts_boundary_desc}
{cold_open_inst}"""

        sw_rag_res, rag_result = await asyncio.gather(
            ScreenwriterRAGClient.retrieve_treatment_beats(
                style_code=style_code,
                structure_type=structure_type,
                genre_tone=genre,
                premise=film_premise,
                top_k=3,
            ),
            DirectorRAGClient.retrieve(
                scene_beat=film_premise,
                genre=genre,
                style_code=style_code,
                top_k=2,
            ),
        )
        sw_family = sw_rag_res.get("style_family") or get_style_family(style_code or "")
        sw_directives = sw_rag_res.get("writing_directives") or {}
        sw_prompt_block = str(sw_rag_res.get("prompt_block") or "").strip()
        if sw_prompt_block or sw_directives:
            dir_summary = sw_directives.get("pacing_rules") or STYLE_FAMILY_WRITING_DIRECTIVES.get(sw_family, "")
            prompt += f"\n[SCREENWRITER CRAFT & DRAMATURGY] (style_family={sw_family})\n"
            if dir_summary:
                prompt += f"Style Pacing Directives: {dir_summary}\n"
            if sw_prompt_block:
                prompt += f"{sw_prompt_block}\n"

        rag_block = DirectorRAGClient.format_treatment_grammar(rag_result)
        if rag_block:
            prompt += f"\n[DIRECTOR VISUAL GRAMMAR]\n{rag_block}\n"

        prompt += f"""
Return a strictly valid JSON object matching this schema:
{{
  "title": "{film_title}",
  "logline": "Compelling 1-2 sentence cinematic logline with protagonist, inciting incident, antagonist force, and stakes",
  "theme": "Underlying philosophical core or thematic question",
  "dramatic_premise": "Paragraph explaining protagonist arc and central dramatic conflict",
  "total_scenes": {total_scenes},
  "structure_type": "{structure_type}",
  "structure_name": "{struct_label}",
  "acts": [
{acts_json_example}
  ]
}}"""

        messages = [
            {"role": "system", "content": POLYA_SCREENWRITER_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        try:
            parsed = await self._call_llm(messages, retry_on_parse_error=True)
        except Exception as exc:
            logger.error("Polya AI Master Treatment LLM execution error: %s", exc)
            raise RuntimeError(
                f"Polya AI Screenwriter: Master Story Treatment generation failed due to LLM error: {exc}. "
                f"Strict LLM Mode prevented mock data fallback."
            ) from exc

        if not parsed or not isinstance(parsed, dict) or "acts" not in parsed:
            raise RuntimeError(
                "Polya AI Screenwriter: LLM returned invalid or malformed treatment JSON. "
                "Strict LLM Mode prevented mock data fallback. Please retry."
            )

        parsed_acts = parsed.get("acts", [])
        if len(parsed_acts) != num_acts:
            raise RuntimeError(
                f"Polya AI Screenwriter: LLM returned {len(parsed_acts)} acts but {num_acts} acts were required for {struct_label}. "
                f"Strict LLM Mode prevented mock data fallback. Please retry."
            )

        parsed["act_summaries"] = {}
        parsed["total_scenes"] = total_scenes
        parsed["structure_type"] = structure_type
        parsed["structure_name"] = struct_label
        parsed["used_fallback"] = False

        if cold_open_30s:
            parsed["cold_open_30s"] = cold_open_30s
            if cold_open_30s.get("enabled"):
                for act in parsed.get("acts", []):
                    if act.get("act_number") == 1:
                        goal = act.get("dramatic_goal", "")
                        if "Cold Open (Scenes 01-03)" not in goal:
                            act["dramatic_goal"] = (
                                f"Cold Open (Scenes 01-03): High-energy visual teaser hook montage. "
                                f"Linear narrative begins at Scene 04: {goal}"
                            )

        return parsed

    # Backward-compatible alias
    generate_treatment = generate_master_treatment

    async def generate_treatment_variants(
        self,
        project_context: ProjectNarrativeContext | dict[str, Any] | None = None,
        title: str = "",
        total_scenes: int = 100,
        premise: str = "",
        characters: list[dict[str, Any]] | None = None,
        cold_open_30s: dict[str, Any] | None = None,
        project_title: str | None = None,
        structure_type: str = "4_act",
    ) -> list[dict[str, Any]]:
        """Phase A Multi-Option Pitch Engine (Strict LLM Mode): generate 3 distinct narrative spines."""
        if isinstance(project_context, dict):
            genre = project_context.get("genre_tone") or project_context.get("genre", "Cinematic Drama")
            world = project_context.get("world_setting", "Cinematic Universe")
            style = project_context.get("style_name") or project_context.get("visual_tone", "Hollywood Cinematic")
            style_code = (
                project_context.get("master_style_code")
                or project_context.get("target_style_code")
                or project_context.get("style_code")
            )
            film_title = project_title or project_context.get("title") or title or "Cinema Feature"
            film_premise = project_context.get("synopsis") or premise or "A compelling dramatic cinematic journey."
        elif project_context:
            genre = project_context.genre_tone or "Cinematic Drama"
            world = project_context.world_setting or "Cinematic Universe"
            style = project_context.style_name or "Hollywood Cinematic"
            style_code = getattr(project_context, "master_style_code", None)
            film_title = project_title or project_context.title or title or "Cinema Feature"
            film_premise = project_context.synopsis or premise or "A compelling dramatic cinematic journey."
        else:
            genre, world, style, style_code = "Cinematic Drama", "Cinematic Universe", "Hollywood Cinematic", None
            film_title = project_title or title or "Cinema Feature"
            film_premise = premise or "A compelling dramatic cinematic journey."

        bounds = get_act_bounds(total_scenes, structure_type=structure_type)
        num_acts = len(bounds)
        struct_cfg = STRUCTURE_DEFINITIONS.get(structure_type, STRUCTURE_DEFINITIONS["4_act"])
        struct_label = struct_cfg["label"]
        act_labels_list = struct_cfg["act_labels"]

        cast_str, _ = self._format_cast_continuity_context(
            project_context=project_context,
            characters=characters,
            act_number=None,
            total_acts=num_acts,
        )

        sw_rag_res, dir_rag_res = await asyncio.gather(
            ScreenwriterRAGClient.retrieve_treatment_beats(
                style_code=style_code,
                structure_type=structure_type,
                genre_tone=genre,
                premise=film_premise,
                top_k=3,
            ),
            DirectorRAGClient.retrieve(
                scene_beat=film_premise,
                genre=genre,
                style_code=style_code,
                top_k=2,
            ),
        )
        sw_family = sw_rag_res.get("style_family") or get_style_family(style_code or "")
        sw_directives = sw_rag_res.get("writing_directives") or {}
        sw_block = str(sw_rag_res.get("prompt_block") or "").strip()
        dir_block = DirectorRAGClient.format_treatment_grammar(dir_rag_res)
        pacing_summary = sw_directives.get("pacing_rules") or STYLE_FAMILY_WRITING_DIRECTIVES.get(sw_family, "")

        cold_open_enabled = bool(cold_open_30s and cold_open_30s.get("enabled"))
        cold_open_inst = (
            "\nCOLD OPEN (30s): Each variant MUST specify a 'cold_open_hook' teasing peak Act III/climax tension in Scenes 01-03 before Scene 04's linear opening."
            if cold_open_enabled
            else ""
        )
        acts_boundary_desc = "\n".join(
            f"- Act {idx + 1} ({act_labels_list[idx]['title']}): Scenes {b[0]} to {b[1]}"
            for idx, b in enumerate(bounds)
        )

        prompt = (
            f"You are Polya AI, Master Screenwriter. Generate 3 genuinely DISTINCT Master Treatment pitches for '{film_title}' using {struct_label} ({num_acts} Acts).\n\n"
            f"Genre/Tone: {genre} | Style: {style} ({style_code or 'Default'} / {sw_family})\n"
            f"Style Pacing Directives: {pacing_summary}\n"
            f"World Setting: {world}\n"
            f"Core Premise: {film_premise}\n"
            f"Total Scenes Target: {total_scenes}\n\n"
            f"Ensemble Cast (honor Voice DNA & 5-State arcs):\n{cast_str}\n\n"
            f"Act Boundaries:\n{acts_boundary_desc}\n"
            f"{cold_open_inst}\n"
        )
        if sw_block:
            prompt += f"\n[SCREENWRITER CRAFT & DRAMATURGY]\n{sw_block}\n"
        if dir_block:
            prompt += f"\n[DIRECTOR VISUAL GRAMMAR]\n{dir_block}\n"

        prompt += (
            "\nThe 3 variants MUST represent contrasting dramatic trajectories:\n"
            "1. variant_id='character_tragedy_redemption' (Pitch: 'Character Tragedy / Redemption')\n"
            "2. variant_id='high_stakes_escalation_twist' (Pitch: 'High-Stakes Escalation / Twist')\n"
            "3. variant_id='atmospheric_mythic_arc' (Pitch: 'Atmospheric Mythic Arc')\n\n"
            "Return ONLY valid JSON matching:\n"
            "{\n"
            '  "variants": [\n'
            "    {\n"
            '      "variant_id": "character_tragedy_redemption",\n'
            '      "pitch_label": "Character Tragedy / Redemption",\n'
            '      "pitch_hook": "<1 sentence pitch differentiator>",\n'
            '      "title": "<evocative title>",\n'
            '      "logline": "<compelling 1-2 sentence logline>",\n'
            '      "theme": "<central philosophical question>",\n'
            '      "dramatic_premise": "<protagonist flaw + external conflict + transformation>",\n'
            '      "cold_open_hook": "<optional 30s cold open visual hook>",\n'
            f'      "acts": [{{"act_number": 1, "act_title": "...", "start_scene": 1, "end_scene": {bounds[0][1]}, "dramatic_goal": "...", "key_beat": "..."}} ... exact {num_acts} acts]\n'
            "    }\n"
            "  ]\n"
            "}"
        )

        messages = [
            {"role": "system", "content": POLYA_SCREENWRITER_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        try:
            parsed = await self._call_llm(messages, retry_on_parse_error=True)
        except Exception as exc:
            raise RuntimeError(f"Polya AI Screenwriter: Treatment variants failed due to LLM error: {exc}") from exc

        raw_variants = parsed.get("variants") if isinstance(parsed, dict) else None
        if not isinstance(raw_variants, list) or len(raw_variants) < 3:
            raise RuntimeError("Polya AI Screenwriter: Expected 3 Master Treatment variants; Strict LLM Mode refused mock fallback.")

        normalized_variants: list[dict[str, Any]] = []
        default_specs = [
            ("character_tragedy_redemption", "Character Tragedy / Redemption"),
            ("high_stakes_escalation_twist", "High-Stakes Escalation / Twist"),
            ("atmospheric_mythic_arc", "Atmospheric Mythic Arc"),
        ]
        for idx, raw_v in enumerate(raw_variants[:3]):
            if not isinstance(raw_v, dict):
                continue
            acts_in = raw_v.get("acts") or []
            normalized_acts = []
            for a_idx, bound in enumerate(bounds):
                src_act = acts_in[a_idx] if a_idx < len(acts_in) and isinstance(acts_in[a_idx], dict) else {}
                goal_txt = str(src_act.get("dramatic_goal") or f"Dramatic escalation for Act {a_idx + 1}.").strip()
                if a_idx == 0 and cold_open_enabled and "Cold Open (Scenes 01-03)" not in goal_txt:
                    goal_txt = f"Cold Open (Scenes 01-03): High-stakes visual hook montage. Linear narrative starts at Scene 04: {goal_txt}"
                normalized_acts.append({
                    "act_number": a_idx + 1,
                    "act_title": str(src_act.get("act_title") or act_labels_list[a_idx]["title"]),
                    "start_scene": bound[0],
                    "end_scene": bound[1],
                    "dramatic_goal": goal_txt,
                    "key_beat": str(src_act.get("key_beat") or f"Act {a_idx + 1} Turning Point"),
                })
            vid_fb, lbl_fb = default_specs[idx]
            co_payload = dict(cold_open_30s) if cold_open_30s else None
            if co_payload and raw_v.get("cold_open_hook"):
                co_payload["hook_preview"] = str(raw_v["cold_open_hook"]).strip()
            normalized_variants.append({
                "variant_id": str(raw_v.get("variant_id") or vid_fb),
                "pitch_label": str(raw_v.get("pitch_label") or lbl_fb),
                "pitch_hook": str(raw_v.get("pitch_hook") or raw_v.get("logline") or "").strip(),
                "title": str(raw_v.get("title") or film_title).strip(),
                "logline": str(raw_v.get("logline") or film_premise).strip(),
                "theme": str(raw_v.get("theme") or "Identity vs. Cost").strip(),
                "dramatic_premise": str(raw_v.get("dramatic_premise") or raw_v.get("logline") or film_premise).strip(),
                "total_scenes": total_scenes,
                "structure_type": structure_type,
                "structure_name": struct_label,
                "acts": normalized_acts,
                "act_summaries": {},
                "cold_open_30s": co_payload,
                "used_fallback": False,
            })
        if len(normalized_variants) < 3:
            raise RuntimeError("Polya AI Screenwriter: Could not assemble 3 valid Master Treatment variants.")
        return normalized_variants

    # ==========================================================================
    # Phase B: Act-by-Act Screenplay Generation (Strict LLM Mode)
    # ==========================================================================

    async def generate_act_scenes(
        self,
        act_number: int,
        total_scenes: int,
        treatment: dict[str, Any] | None = None,
        project_context: ProjectNarrativeContext | dict[str, Any] | None = None,
        previous_act_summaries: dict[int, str] | None = None,
        characters: list[dict[str, Any]] | None = None,
        duration_mode: str = "dynamic",
        cold_open_30s: dict[str, Any] | None = None,
        premise: str = "",
        structure_type: str = "4_act",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Phase B: Generate scenes for a single Act strictly via LLM with context chaining and sub-chunking."""
        if treatment is None:
            treatment = {}

        st_type = treatment.get("structure_type") or structure_type or "4_act"
        bounds = get_act_bounds(total_scenes, structure_type=st_type)
        num_acts = len(bounds)
        if not (1 <= act_number <= num_acts):
            raise ValueError(
                f"Invalid act number {act_number} for structure '{st_type}'. Expected 1 to {num_acts}."
            )

        start_scene, end_scene = bounds[act_number - 1]

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

        # Active cast formatting with Voice DNA & Act-mapped #State 01-05 continuity
        cast_str, char_names = self._format_cast_continuity_context(
            project_context=project_context,
            characters=characters,
            act_number=act_number,
            total_acts=num_acts,
        )

        # Intra-act chunking: 18 scenes per chunk to prevent token limits and timeouts
        CHUNK_SIZE = 18
        chunks: list[tuple[int, int]] = []
        curr = start_scene
        while curr <= end_scene:
            next_curr = min(curr + CHUNK_SIZE - 1, end_scene)
            chunks.append((curr, next_curr))
            curr = next_curr + 1

        all_generated_scenes: list[dict[str, Any]] = []
        act_summary = ""
        recent_scenes_handover: list[dict[str, Any]] = []

        # Target duration and word limits
        scene_duration = _determine_scene_duration(act_number, duration_mode)
        max_words = 14 if scene_duration <= 5.0 else (28 if scene_duration <= 10.0 else 42)

        if isinstance(project_context, dict):
            rag_genre = project_context.get("genre_tone") or project_context.get("genre")
            rag_style_code = (
                project_context.get("master_style_code")
                or project_context.get("target_style_code")
                or project_context.get("style_code")
            )
            rag_style_name = project_context.get("style_name") or ""
            rag_aesthetic_directives = project_context.get("aesthetic_directives") or ""
        elif project_context:
            rag_genre = getattr(project_context, "genre_tone", None)
            rag_style_code = getattr(project_context, "master_style_code", None)
            rag_style_name = getattr(project_context, "style_name", "")
            rag_aesthetic_directives = getattr(project_context, "aesthetic_directives", "")
        else:
            rag_genre = treatment.get("genre") if isinstance(treatment, dict) else None
            rag_style_code = treatment.get("style_code") if isinstance(treatment, dict) else None
            rag_style_name = ""
            rag_aesthetic_directives = ""

        if rag_style_code and (not rag_style_name or not rag_aesthetic_directives):
            cat_entry = next((s for s in STYLE_CATALOG if s.get("code") == rag_style_code), None)
            if cat_entry:
                rag_style_name = rag_style_name or cat_entry.get("name", "")
                rag_aesthetic_directives = rag_aesthetic_directives or cat_entry.get("aesthetic_directives", "")

        rag_style_family = get_style_family(rag_style_code or "")
        duration_tier = "5s_max14" if max_words <= 14 else ("10s_max28" if max_words <= 28 else "15s_max42")
        rag_scene_beat = f"{act_title}: {act_goal} {key_beat}".strip() or f"Act {act_number}"

        sw_act_res, rag_act_res = await asyncio.gather(
            ScreenwriterRAGClient.retrieve_scene_craft(
                style_code=rag_style_code,
                act_number=act_number,
                narrative_goal=rag_scene_beat,
                duration_tier=duration_tier,
                top_k=3,
            ),
            DirectorRAGClient.retrieve(
                scene_beat=rag_scene_beat,
                genre=rag_genre,
                style_code=rag_style_code,
                top_k=3,
            ),
        )
        rag_act_block = DirectorRAGClient.format_act_context(rag_act_res)
        sw_directives = sw_act_res.get("writing_directives") or {}
        sw_writing_summary = (
            " | ".join(
                str(sw_directives[k])
                for k in ("dialogue_density", "action_beat_grammar", "preferred_jl_cut_cadence")
                if sw_directives.get(k)
            )
            or STYLE_FAMILY_WRITING_DIRECTIVES.get(rag_style_family, "")
        )
        sw_act_block = str(sw_act_res.get("prompt_block") or "").strip()

        for chunk_idx, (c_start, c_end) in enumerate(chunks):
            chunk_scenes_needed = c_end - c_start + 1

            cold_open_instruction = ""
            if cold_open_active and c_start <= 3:
                cold_open_instruction = """
COLD OPEN (30-SECOND VISUAL HOOK MONTAGE) MANDATE:
Scenes 1 through 3 MUST serve as a high-velocity 30-second Cold Open hook montage teasing peak conflict before transitioning to the linear timeline:
- Scene 1 (0-10s): In-Media-Res Shock Hook + Hero Prop Reveal
- Scene 2 (10-20s): Escalating Kinetic Obstacle + Main Threat/Rival
- Scene 3 (20-30s): Peak Climax Preview + Time-Cut Transition to Scene 04
- Scene 4 onwards: Linear narrative starts (Ordinary World Setup).
"""

            # Intra-act context handover: include last 3 scenes from previous chunk
            handover_str = ""
            if recent_scenes_handover:
                handover_lines = [f"Direct Narrative Handover from previous scenes (Scenes {c_start - len(recent_scenes_handover[-3:])} to {c_start - 1}):"]
                for h_sc in recent_scenes_handover[-3:]:
                    handover_lines.append(
                        f"- Scene {h_sc.get('scene_number')}: {h_sc.get('slugline')} | Goal: {h_sc.get('narrative_goal')} | Dialogue: '{h_sc.get('dialogue', '')}'"
                    )
                handover_str = "\n".join(handover_lines)

            prompt = f"""You are Polya AI — Master Hollywood Screenwriter.
Write scenes for {act_title} (Act {act_number} of {num_acts}) in an ongoing cinematic feature film.

Title: {treatment.get('title', 'Cinema Feature')}
Logline: {treatment.get('logline', '')}
Theme: {treatment.get('theme', '')}
Visual Style: {rag_style_code or 'Default'} ({rag_style_name or 'Hollywood Cinematic'})
Style Family: {rag_style_family}
Aesthetic Directives: {rag_aesthetic_directives or 'Cinematic visual storytelling'}
Style Writing Directives: {sw_writing_summary}

Current Act: {act_title}
Act Dramatic Goal: {act_goal}
Key Dramatic Beat: {key_beat}
Target Scene Duration: {scene_duration} seconds per scene ({duration_tier}).

Active Cast Ensemble & Act Continuity (preserve each speaker's Voice DNA cadence and active #State wear/wardrobe):
{cast_str}
{cold_open_instruction}
PERSISTENT CONTEXT FROM PREVIOUS ACTS:
{context_str}

{handover_str}
"""
            if sw_act_block:
                prompt += f"\n[SCREENWRITER CRAFT & SCENE EXEMPLARS]\n{sw_act_block}\n"
            if rag_act_block:
                prompt += f"\n[DIRECTOR VISUAL GRAMMAR]\n{rag_act_block}\n"

            prompt += f"""
ASSIGNMENT:
Write exactly {chunk_scenes_needed} scenes from Scene {c_start} to Scene {c_end}.
For each scene provide:
- scene_number (integer from {c_start} to {c_end})
- slugline (standard uppercase screenplay slugline, e.g. 'EXT. LOCATION - TIME')
- narrative_goal (dramatic objective advancing the story beat, explicitly naming interacting characters, reflecting active wardrobe/wear state)
- speaking_character (name of character speaking from active cast, or 'None' for non-verbal/SFX)
- dialogue (pacing-calibrated spoken line reflecting speaker's Voice DNA, or [SFX: ...] atmospheric cue)

DRAMATIC CRAFT & DIALOGUE CALIBRATION:
- Scene Value Shift: Every scene MUST turn an observable dramatic value (+ to - or - to +) through behavior and conflict, NOT passive summary.
- Anti-Exposition Rule: Show inner tension via physical action and loaded subtext; never have characters announce plot backstory or feelings on the nose.
- Scene target duration: {scene_duration}s.
- Spoken dialogue line MUST be strictly between 1 and {max_words} words (delivery speed of ~2.8 words/sec).
- For non-verbal or action beats, provide style-authentic atmospheric SFX in brackets e.g. '[SFX: Rain hisses against steel shutter]'.

Return valid JSON in this exact structure:
{{
  "act_summary": "2-3 sentences summarizing the major events and ending situation of this chunk to chain into subsequent scenes",
  "scenes": [
    {{
      "scene_number": {c_start},
      "slugline": "EXT. LOCATION - TIME",
      "narrative_goal": "Dramatic goal featuring character action",
      "speaking_character": "{char_names[0]}",
      "dialogue": "Calibrated spoken dialogue line under {max_words} words"
    }}
  ]
}}"""

            messages = [
                {"role": "system", "content": POLYA_SCREENWRITER_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]

            try:
                chunk_res = await self._call_llm(messages, retry_on_parse_error=True)
            except Exception as exc:
                logger.error("Polya AI chunk LLM error (Scenes %d-%d): %s", c_start, c_end, exc)
                raise RuntimeError(
                    f"Polya AI Screenwriter: Generation failed for Act {act_number} Chunk (Scenes {c_start}-{c_end}) "
                    f"due to LLM error: {exc}. Strict LLM Mode prevented mock data fallback. Please retry this act."
                ) from exc

            if not chunk_res or not isinstance(chunk_res, dict) or "scenes" not in chunk_res:
                raise RuntimeError(
                    f"Polya AI Screenwriter: Act {act_number} Chunk (Scenes {c_start}-{c_end}) returned malformed JSON. "
                    f"Strict LLM Mode prevented mock data fallback. Please retry this act."
                )

            if chunk_res.get("act_summary"):
                act_summary = chunk_res["act_summary"]

            scenes_dict: dict[int, dict[str, Any]] = {}
            for sc in chunk_res.get("scenes", []):
                try:
                    s_num = int(sc.get("scene_number", 0))
                    if c_start <= s_num <= c_end:
                        scenes_dict[s_num] = {
                            "scene_number": s_num,
                            "slugline": str(sc.get("slugline", "")).strip() or f"SCENE {s_num:03d} - INT. LOCATION - NIGHT",
                            "narrative_goal": str(sc.get("narrative_goal", "")).strip() or f"Act {act_number} dramatic beat.",
                            "dialogue": str(sc.get("dialogue", "")).strip(),
                            "speaking_character": str(sc.get("speaking_character", "")).strip() or char_names[0],
                            "is_fallback": False,
                        }
                except (ValueError, TypeError):
                    continue

            # Verify all scenes in chunk were returned by LLM
            missing_scenes = [num for num in range(c_start, c_end + 1) if num not in scenes_dict]
            if missing_scenes:
                raise RuntimeError(
                    f"Polya AI Screenwriter: LLM omitted scene numbers {missing_scenes} in Act {act_number} "
                    f"(Scenes {c_start}-{c_end}). Strict LLM Mode prevented mock fallback injection. Please retry this act."
                )

            chunk_scenes_output = [scenes_dict[num] for num in range(c_start, c_end + 1)]
            all_generated_scenes.extend(chunk_scenes_output)
            recent_scenes_handover = list(chunk_scenes_output)

        if not act_summary:
            act_summary = (
                f"Act {act_number} reaches its narrative progression with {char_names[0]} "
                f"advancing the core dramatic stakes through Scene {end_scene}."
            )

        return {
            "act_number": act_number,
            "start_scene": start_scene,
            "end_scene": end_scene,
            "scenes_count": len(all_generated_scenes),
            "act_summary": act_summary,
            "used_fallback": False,
            "scenes": all_generated_scenes,
        }

    # ==========================================================================
    # Phase C: Dialogue Pacing Calibration & Director Polish
    # ==========================================================================

    @staticmethod
    def _compute_dialogue_pacing_metrics(dialogue_text: str, max_seconds: float) -> dict[str, Any]:
        """Deterministically compute spoken word count, syllables, duration, and pacing pass flags."""
        safe_max_seconds = max_seconds if max_seconds > 0 else 5.0
        max_allowed_words = max(1, int(safe_max_seconds * 2.8))

        # Strip bracketed/parenthetical non-spoken cues like [NON-VERBAL], [SILENT], (beat)
        spoken_only = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", dialogue_text or "").strip()
        words = re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*", spoken_only)
        word_count = len(words)

        if word_count == 0:
            syllable_count = 0
            estimated_duration = 0.0
        else:
            syllable_count = 0
            for w in words:
                cleaned_w = re.sub(r"[^a-z]", "", w.lower())
                if not cleaned_w:
                    syllable_count += 1
                elif len(cleaned_w) <= 3:
                    syllable_count += 1
                else:
                    groups = re.findall(r"[aeiouy]+", cleaned_w)
                    syl = len(groups)
                    if cleaned_w.endswith("e") and not cleaned_w.endswith(("le", "ye", "ee")) and syl > 1:
                        syl -= 1
                    syllable_count += max(1, syl)
            estimated_duration = round(word_count / 2.8, 2)

        passes_duration_limit = word_count <= max_allowed_words
        ratio = estimated_duration / safe_max_seconds if safe_max_seconds > 0 else 0.0
        if ratio > 0.75:
            transition_type = "J_CUT"
            audio_lead_seconds = 1.0
        elif ratio < 0.40:
            transition_type = "HARD_CUT"
            audio_lead_seconds = 0.0
        else:
            transition_type = "L_CUT"
            audio_lead_seconds = 0.5

        return {
            "word_count": word_count,
            "syllable_count": syllable_count,
            "estimated_duration_seconds": estimated_duration,
            "max_allowed_words": max_allowed_words,
            "max_seconds": safe_max_seconds,
            "passes_duration_limit": passes_duration_limit,
            "passes_5s_limit": passes_duration_limit,
            "transition_type": transition_type,
            "audio_lead_seconds": audio_lead_seconds,
        }

    def _finalize_dialogue_alternatives(
        self,
        raw_alternatives: Any,
        dialogue_text: str,
        max_seconds: float,
        style_family: str,
        trimmed_hint: str | None = None,
    ) -> list[dict[str, Any]]:
        """Build 3 voice/style-aware dialogue takes with deterministic 2.8 wps metrics attached to every take."""
        specs = [
            ("subtext_cut", "Subtext-Heavy", "Implies tension beneath calm phrasing; withholds overt exposition."),
            ("urgent_clipped", "Urgent / Clipped", "Staccato rhythm stripped to essentials for kinetic pacing."),
            ("emotional_poetic", "Emotional / Poetic", f"Sensory cadence tailored to {style_family} atmosphere."),
        ]
        by_id: dict[str, dict[str, Any]] = {}
        raw_list = raw_alternatives if isinstance(raw_alternatives, list) else []
        for idx, item in enumerate(raw_list):
            if not isinstance(item, dict):
                continue
            dlg_val = str(item.get("dialogue") or item.get("text") or "").strip()
            if not dlg_val:
                continue
            raw_id = str(item.get("id") or "").strip().lower()
            target_id = raw_id if raw_id in {s[0] for s in specs} else specs[min(idx, len(specs) - 1)][0]
            if target_id not in by_id:
                by_id[target_id] = item

        # Deterministic compression helpers when LLM omits or times out
        words = re.findall(r"\S+", re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", dialogue_text or "").strip())
        max_words = max(1, int((max_seconds if max_seconds > 0 else 5.0) * 2.8))
        trimmed_base = (trimmed_hint or "").strip() or " ".join(words[:max_words]).rstrip(",;:")
        clipped_fallback = " ".join(words[: max(1, min(len(words), max(3, max_words - 4)))]).rstrip(",;:")
        if clipped_fallback and clipped_fallback[-1] not in ".!?":
            clipped_fallback += "."
        subtext_fallback = (trimmed_base + ("" if trimmed_base.endswith((".", "!", "?")) else ".")) if trimmed_base else "[SFX: Heavy silence]"
        poetic_fallback = (
            " ".join(words[: max(1, min(len(words), max_words - 1))]).rstrip(",;:") + "..."
            if words
            else "[SFX: Quiet ambient breath in room tone]"
        )
        fallback_texts = {
            "subtext_cut": subtext_fallback,
            "urgent_clipped": clipped_fallback or subtext_fallback,
            "emotional_poetic": poetic_fallback,
        }

        alternatives: list[dict[str, Any]] = []
        for take_id, default_label, default_note in specs:
            src = by_id.get(take_id, {})
            take_dialogue = str(src.get("dialogue") or src.get("text") or fallback_texts[take_id]).strip()
            det_alt = self._compute_dialogue_pacing_metrics(take_dialogue, max_seconds)
            alternatives.append({
                "id": take_id,
                "label": str(src.get("label") or default_label).strip(),
                "style_note": str(src.get("style_note") or src.get("rationale") or default_note).strip(),
                "dialogue": take_dialogue,
                "word_count": det_alt["word_count"],
                "syllable_count": det_alt["syllable_count"],
                "estimated_duration_seconds": det_alt["estimated_duration_seconds"],
                "passes_duration_limit": det_alt["passes_duration_limit"],
                "max_allowed_words": det_alt["max_allowed_words"],
                "transition_type": det_alt["transition_type"],
                "audio_lead_seconds": det_alt["audio_lead_seconds"],
            })
        return alternatives

    async def calibrate_dialogue_pacing(
        self,
        dialogue_text: str,
        max_seconds: float = 5.0,
        character_name: str | None = None,
        context: str | None = None,
        style_code: str | None = None,
        voice_dna_profile: str | None = None,
        active_state: dict[str, Any] | str | None = None,
    ) -> dict[str, Any]:
        """Analyze acoustic syllable pacing, cut bridge, and 3 voice-aligned alternative spoken takes.
        Uses unified 2.8 words/sec pacing math deterministically across primary line & all alternatives.
        """
        det = self._compute_dialogue_pacing_metrics(dialogue_text, max_seconds)
        safe_max_seconds = det["max_seconds"]
        max_allowed_words = det["max_allowed_words"]

        sw_dlg_res = await ScreenwriterRAGClient.retrieve_dialogue_cut(
            style_code=style_code,
            max_words=max_allowed_words,
            dialogue_text=f"{context or ''} {dialogue_text}".strip(),
            top_k=2,
        )
        sw_dlg_block = str(sw_dlg_res.get("prompt_block") or "").strip()
        resolved_family = sw_dlg_res.get("style_family") or get_style_family(style_code or "")
        style_directive = STYLE_FAMILY_WRITING_DIRECTIVES.get(resolved_family, "")
        speaker_continuity = self._format_speaker_continuity_line(
            character_name=character_name,
            voice_dna_profile=voice_dna_profile,
            active_state=active_state,
        )

        # Attempt LLM analysis + 3 spoken alternatives
        prompt = (
            "You are the Polya AI Hollywood Dialogue & Sound Continuity Director. "
            "Analyze the spoken line for acoustic pacing and sound bridge, AND write 3 distinct spoken rewrites under max_allowed_words honoring the speaker's Voice DNA and active physical/emotional State.\n\n"
            f"CHARACTER: {character_name or 'Unspecified'}\n"
            f"DIALOGUE LINE: \"{dialogue_text}\"\n"
            f"MAX DURATION TARGET: {safe_max_seconds:.1f} seconds (max {max_allowed_words} words @ 2.8 wps)\n"
            f"STYLE: {style_code or 'Default'} ({resolved_family}) — {style_directive}\n"
            f"SCENE CONTEXT: {context or 'Standard dramatic pacing'}\n"
        )
        if speaker_continuity:
            prompt += f"\n[SPEAKER VOICE DNA & ACTIVE STATE]\n{speaker_continuity}\n"
        if sw_dlg_block:
            prompt += f"\n[SCREENWRITER CRAFT & SUBTEXT CUTS]\n{sw_dlg_block}\n"
        prompt += (
            "\nReturn ONLY a JSON object matching this exact schema (each alternative MUST be strictly <= max_allowed_words words):\n"
            "{\n"
            '  "word_count": <int>,\n'
            '  "syllable_count": <int>,\n'
            '  "estimated_duration_seconds": <float>,\n'
            '  "passes_duration_limit": <bool>,\n'
            '  "transition_type": "J_CUT" | "L_CUT" | "HARD_CUT",\n'
            '  "audio_lead_seconds": <float>,\n'
            '  "analysis": "<1-2 sentence directorial acoustic analysis>",\n'
            '  "trimmed_suggestion": "<optional tighter subtext-rich line under max_allowed_words, else null>",\n'
            '  "alternatives": [\n'
            '    {"id": "subtext_cut", "label": "Subtext-Heavy", "style_note": "<1 sentence why>", "dialogue": "<spoken line <= max_allowed_words>"},\n'
            '    {"id": "urgent_clipped", "label": "Urgent / Clipped", "style_note": "<1 sentence why>", "dialogue": "<spoken line <= max_allowed_words>"},\n'
            '    {"id": "emotional_poetic", "label": "Emotional / Poetic", "style_note": "<1 sentence why>", "dialogue": "<spoken line <= max_allowed_words>"}\n'
            "  ]\n"
            "}\n"
        )

        try:
            messages = [
                {"role": "system", "content": "You are an acoustic dialogue consultant and Polya AI sound director."},
                {"role": "user", "content": prompt},
            ]
            raw_resp = await asyncio.wait_for(
                self._call_llm(messages=messages),
                timeout=10.0,
            )
            parsed = raw_resp if isinstance(raw_resp, dict) else self._clean_and_parse_json(str(raw_resp))
            if isinstance(parsed, dict) and ("analysis" in parsed or "estimated_duration_seconds" in parsed):
                llm_lead = parsed.get("audio_lead_seconds")
                lead_val = float(llm_lead) if isinstance(llm_lead, (int, float)) else det["audio_lead_seconds"]
                alternatives = self._finalize_dialogue_alternatives(
                    parsed.get("alternatives"),
                    dialogue_text=dialogue_text,
                    max_seconds=safe_max_seconds,
                    style_family=resolved_family,
                    trimmed_hint=parsed.get("trimmed_suggestion"),
                )
                return {
                    "word_count": det["word_count"],
                    "syllable_count": det["syllable_count"],
                    "estimated_duration_seconds": det["estimated_duration_seconds"],
                    "passes_duration_limit": det["passes_duration_limit"],
                    "passes_5s_limit": det["passes_5s_limit"],
                    "max_allowed_words": det["max_allowed_words"],
                    "max_seconds": safe_max_seconds,
                    "transition_type": det["transition_type"],
                    "audio_lead_seconds": lead_val,
                    "analysis": parsed.get("analysis") or "LLM-verified acoustic pacing.",
                    "trimmed_suggestion": parsed.get("trimmed_suggestion"),
                    "alternatives": alternatives,
                    "source": "llm",
                }
        except Exception as exc:
            logger.warning("llm_dialogue_calibration_fallback: %s. Using deterministic word_count / 2.8s fallback", exc)

        # Deterministic fallback calculation: word_count / 2.8s
        fallback_alts = self._finalize_dialogue_alternatives(
            None,
            dialogue_text=dialogue_text,
            max_seconds=safe_max_seconds,
            style_family=resolved_family,
        )
        return {
            "word_count": det["word_count"],
            "syllable_count": det["syllable_count"],
            "estimated_duration_seconds": det["estimated_duration_seconds"],
            "passes_duration_limit": det["passes_duration_limit"],
            "passes_5s_limit": det["passes_5s_limit"],
            "max_allowed_words": det["max_allowed_words"],
            "max_seconds": safe_max_seconds,
            "transition_type": det["transition_type"],
            "audio_lead_seconds": det["audio_lead_seconds"],
            "analysis": (
                f"Deterministic pacing calculation ({det['word_count']} words @ 2.8 words/sec = {det['estimated_duration_seconds']}s). "
                f"{'Adheres to limit.' if det['passes_duration_limit'] else f'Exceeds {safe_max_seconds}s limit; consider trimming.'}"
            ),
            "trimmed_suggestion": fallback_alts[0]["dialogue"] if not det["passes_duration_limit"] else None,
            "alternatives": fallback_alts,
            "source": "deterministic_fallback",
        }

    def _finalize_polish_options(
        self,
        raw_options: Any,
        slugline: str,
        narrative_goal: str,
        dialogue: str | None,
        camera_code: str,
        lighting_code: str,
        style_family: str,
    ) -> list[dict[str, Any]]:
        """Normalize 3 selectable Polish Takes and attach deterministic pacing metrics to every take."""
        valid_cuts = {"J_CUT", "L_CUT", "HARD_CUT"}
        specs = [
            (
                "subtext_heavy",
                "Subtext-Heavy",
                "Highlights unspoken psychological tension beneath minimal gestures.",
                "#Cam 02",
                "#Light 03",
                "L_CUT",
            ),
            (
                "visceral_kinetic",
                "Visceral / Kinetic",
                "Pushes dynamic camera energy, tactile impact, and prop/environment urgency.",
                "#Cam 07",
                "#Light 01",
                "J_CUT",
            ),
            (
                "minimalist_poetic",
                "Minimalist / Poetic",
                f"Distills framing and stillness tailored to {style_family} atmosphere.",
                "#Cam 13",
                "#Light 04",
                "HARD_CUT",
            ),
        ]
        by_id: dict[str, dict[str, Any]] = {}
        if isinstance(raw_options, list):
            for idx, item in enumerate(raw_options):
                if not isinstance(item, dict) or not item.get("narrative_goal"):
                    continue
                tid = str(item.get("take_id") or "").strip().lower()
                resolved_id = tid if tid in {s[0] for s in specs} else specs[min(idx, len(specs) - 1)][0]
                if resolved_id not in by_id:
                    by_id[resolved_id] = item

        parsed_slug = parse_structured_slugline(slugline)
        if parsed_slug["setting"] and parsed_slug["location"]:
            base_slug = parsed_slug["normalized"]
        else:
            loc_fb = (parsed_slug["location"] or slugline).strip().upper()
            tod_fb = parsed_slug["time_of_day"] or "CONTINUOUS"
            base_slug = f"INT./EXT. {loc_fb} - {tod_fb}"
        base_goal = narrative_goal.strip().rstrip(".")

        options: list[dict[str, Any]] = []
        for idx, (take_id, default_label, default_rat, default_cam, default_light, default_cut) in enumerate(specs):
            src = by_id.get(take_id, {})
            if take_id == "subtext_heavy":
                fb_goal = f"{base_goal}. Charged silence and guarded eye-line reveal unspoken stakes beneath the surface."
                fb_dlg = dialogue or "[SFX: Measured breathing across tense room tone]"
            elif take_id == "visceral_kinetic":
                fb_goal = f"{base_goal}. Kinetic forward push compresses space and forces an immediate reactive turn."
                fb_dlg = dialogue or "[SFX: Sharp prop impact and kinetic footstep surge]"
            else:
                fb_goal = f"{base_goal}. Stark visual framing isolates emotional shift with restrained behavioral detail."
                fb_dlg = dialogue or "[SFX: Distant ambient sustain before decisive stillness]"

            t_dlg = str(src.get("dialogue") if src.get("dialogue") is not None else fb_dlg).strip()
            t_cut = str(src.get("transition_type") or default_cut).strip().upper()
            if t_cut not in valid_cuts:
                t_cut = default_cut
            t_cam = str(src.get("camera_code") or (default_cam if camera_code == "#Cam 01" or idx > 0 else camera_code)).strip()
            t_light = str(src.get("lighting_code") or (default_light if lighting_code == "#Light 01" or idx > 0 else lighting_code)).strip()
            t_slug = str(src.get("slugline") or base_slug).strip()
            t_goal = str(src.get("narrative_goal") or fb_goal).strip()
            t_notes = str(src.get("director_notes") or f"{default_label} polish aligns {t_cam}/{t_light} optics with {t_cut} rhythm.").strip()
            t_rat = str(src.get("angle_rationale") or default_rat).strip()

            det_take = self._compute_dialogue_pacing_metrics(t_dlg, 10.0)
            options.append({
                "take_id": take_id,
                "label": str(src.get("label") or default_label).strip(),
                "angle_rationale": t_rat,
                "slugline": t_slug,
                "narrative_goal": t_goal,
                "dialogue": t_dlg,
                "camera_code": t_cam,
                "lighting_code": t_light,
                "transition_type": t_cut,
                "director_notes": t_notes,
                "word_count": det_take["word_count"],
                "estimated_duration_seconds": det_take["estimated_duration_seconds"],
                "passes_duration_limit": det_take["passes_duration_limit"],
            })
        return options

    async def polish_scene_director_cut(
        self,
        scene_number: int,
        slugline: str,
        narrative_goal: str,
        dialogue: str | None = None,
        style_code: str = "#Style 01",
        camera_code: str = "#Cam 01",
        lighting_code: str = "#Light 01",
        project_context: ProjectNarrativeContext | dict[str, Any] | None = None,
        voice_dna_profile: str | None = None,
        active_state: dict[str, Any] | str | None = None,
        adjacent_scenes: dict[str, Any] | None = None,
        act_number: int | None = None,
        speaking_character: str | None = None,
    ) -> dict[str, Any]:
        """Polya AI Director Polish: Dual RAG (8766 + 8765) generating 3 selectable creative takes + backward-compatible suggestions."""
        sw_scene_res, sw_dlg_res, dir_res = await asyncio.gather(
            ScreenwriterRAGClient.retrieve_scene_craft(
                style_code=style_code,
                act_number=act_number,
                narrative_goal=narrative_goal,
                duration_tier="10s_max28",
                top_k=2,
            ),
            ScreenwriterRAGClient.retrieve_dialogue_cut(
                style_code=style_code,
                max_words=28,
                dialogue_text=dialogue or narrative_goal,
                top_k=2,
            ),
            DirectorRAGClient.retrieve(
                scene_beat=f"{slugline}: {narrative_goal}",
                style_code=style_code,
                top_k=2,
            ),
        )
        sw_scene_block = str(sw_scene_res.get("prompt_block") or "").strip()
        sw_dlg_block = str(sw_dlg_res.get("prompt_block") or "").strip()
        dir_block = DirectorRAGClient.format_act_context(dir_res)
        style_family = sw_scene_res.get("style_family") or get_style_family(style_code)
        style_directive = STYLE_FAMILY_WRITING_DIRECTIVES.get(style_family, "")

        continuity_sections: list[str] = []
        if isinstance(project_context, ProjectNarrativeContext):
            continuity_sections.append(
                f"Project: {project_context.title} ({project_context.genre_tone}) | Style Family: {style_family} ({style_directive})\n"
                f"Premise: {project_context.synopsis[:220]}"
            )
            cast_block, _ = self._format_cast_continuity_context(
                project_context=project_context,
                act_number=act_number,
                speaking_character=speaking_character,
            )
            continuity_sections.append(f"Cast Continuity:\n{cast_block}")
        elif isinstance(project_context, dict) and project_context:
            p_title = project_context.get("title") or "Production"
            p_genre = project_context.get("genre_tone") or project_context.get("genre") or ""
            p_syn = str(project_context.get("synopsis") or "")[:220]
            continuity_sections.append(
                f"Project: {p_title} ({p_genre}) | Style Family: {style_family} ({style_directive})"
                + (f"\nPremise: {p_syn}" if p_syn else "")
            )
            if project_context.get("cast_characters"):
                cast_block, _ = self._format_cast_continuity_context(
                    project_context=project_context,
                    act_number=act_number,
                    speaking_character=speaking_character,
                )
                continuity_sections.append(f"Cast Continuity:\n{cast_block}")

        speaker_line = self._format_speaker_continuity_line(
            character_name=speaking_character,
            voice_dna_profile=voice_dna_profile,
            active_state=active_state,
        )
        if speaker_line:
            continuity_sections.append(speaker_line)

        if adjacent_scenes:
            adj_lines: list[str] = []
            prev_sc = adjacent_scenes.get("prev")
            next_sc = adjacent_scenes.get("next")
            if isinstance(prev_sc, dict):
                adj_lines.append(
                    f"Previous Scene #{prev_sc.get('scene_number')}: {prev_sc.get('slugline')} — {prev_sc.get('narrative_goal', '')[:120]}"
                )
            if isinstance(next_sc, dict):
                adj_lines.append(
                    f"Next Scene #{next_sc.get('scene_number')}: {next_sc.get('slugline')} — {next_sc.get('narrative_goal', '')[:120]}"
                )
            if adj_lines:
                continuity_sections.append("Adjacent Scene Beats:\n" + "\n".join(adj_lines))

        prompt = (
            "You are the Polya AI Hollywood Executive Director & Master Screenwriter. "
            "Produce 3 genuinely distinct creative polish takes for this scene (subtext_heavy, visceral_kinetic, minimalist_poetic), "
            "elevating value shift, Voice DNA fidelity, optical staging (#Cam 01-34, #Light 01-14), and audio bridge cuts.\n\n"
            f"SCENE NUMBER: {scene_number}{f' (Act {act_number})' if act_number else ''}\n"
            f"CURRENT SLUGLINE: {slugline}\n"
            f"CURRENT NARRATIVE GOAL: {narrative_goal}\n"
            f"CURRENT DIALOGUE: {dialogue or 'None / Visual Staging'}\n"
            f"CURRENT CAMERA: {camera_code}\n"
            f"CURRENT LIGHTING: {lighting_code}\n"
            f"STYLE CODE: {style_code} (Family: {style_family})\n\n"
        )
        if continuity_sections:
            prompt += "[PROJECT & SCENE CONTINUITY]\n" + "\n".join(continuity_sections) + "\n\n"
        if sw_scene_block or sw_dlg_block:
            prompt += "[SCREENWRITER CRAFT & SUBTEXT]\n"
            if sw_scene_block:
                prompt += f"{sw_scene_block}\n"
            if sw_dlg_block:
                prompt += f"{sw_dlg_block}\n\n"
        if dir_block:
            prompt += f"[DIRECTOR VISUAL GRAMMAR]\n{dir_block}\n\n"

        prompt += (
            "INSTRUCTIONS:\n"
            "1. Output 3 selectable creative takes in 'options':\n"
            "   - take_id='subtext_heavy' (Label: 'Subtext-Heavy')\n"
            "   - take_id='visceral_kinetic' (Label: 'Visceral / Kinetic')\n"
            "   - take_id='minimalist_poetic' (Label: 'Minimalist / Poetic')\n"
            "2. Keep each dialogue strictly under 24 spoken words (2.8 wps) honoring speaker Voice DNA (or atmospheric [SFX: ...] if non-verbal).\n"
            "3. Assign authentic #Cam 01-#Cam 34, #Light 01-#Light 14, and transition_type ('J_CUT' | 'L_CUT' | 'HARD_CUT') per take.\n\n"
            "Return ONLY a JSON object matching:\n"
            "{\n"
            '  "options": [\n'
            "    {\n"
            '      "take_id": "subtext_heavy",\n'
            '      "label": "Subtext-Heavy",\n'
            '      "angle_rationale": "<1 sentence focus>",\n'
            '      "slugline": "<polished slugline>",\n'
            '      "narrative_goal": "<elevated goal>",\n'
            '      "dialogue": "<calibrated line or [SFX: ...]>",\n'
            '      "camera_code": "#Cam 02",\n'
            '      "lighting_code": "#Light 03",\n'
            '      "transition_type": "L_CUT",\n'
            '      "director_notes": "<2 sentence artistic rationale>"\n'
            "    }\n"
            "  ]\n"
            "}\n"
        )

        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are an award-winning cinematic director and Polya AI screenwriting maestro.",
                },
                {"role": "user", "content": prompt},
            ]
            parsed = await asyncio.wait_for(
                self._call_llm(messages, retry_on_parse_error=True),
                timeout=14.0,
            )
            if isinstance(parsed, dict) and (isinstance(parsed.get("options"), list) or parsed.get("narrative_goal")):
                raw_opts = parsed.get("options")
                if not isinstance(raw_opts, list) and parsed.get("narrative_goal"):
                    raw_opts = [{
                        "take_id": "subtext_heavy",
                        "slugline": parsed.get("slugline", slugline),
                        "narrative_goal": parsed.get("narrative_goal", narrative_goal),
                        "dialogue": parsed.get("dialogue", dialogue),
                        "camera_code": parsed.get("camera_code", camera_code),
                        "lighting_code": parsed.get("lighting_code", lighting_code),
                        "transition_type": parsed.get("transition_type", "L_CUT"),
                        "director_notes": parsed.get("director_notes", "Director polish elevates dramatic stakes and visual clarity."),
                    }]
                options = self._finalize_polish_options(
                    raw_opts,
                    slugline=slugline,
                    narrative_goal=narrative_goal,
                    dialogue=dialogue,
                    camera_code=camera_code,
                    lighting_code=lighting_code,
                    style_family=style_family,
                )
                primary = options[0]
                return {
                    "slugline": primary["slugline"],
                    "narrative_goal": primary["narrative_goal"],
                    "dialogue": primary["dialogue"],
                    "camera_code": primary["camera_code"],
                    "lighting_code": primary["lighting_code"],
                    "transition_type": primary["transition_type"],
                    "director_notes": primary["director_notes"],
                    "options": options,
                }
        except Exception as exc:
            logger.warning("llm_director_polish_procedural_fallback: %s", exc)

        options = self._finalize_polish_options(
            None,
            slugline=slugline,
            narrative_goal=narrative_goal,
            dialogue=dialogue,
            camera_code=camera_code,
            lighting_code=lighting_code,
            style_family=style_family,
        )
        primary = options[0]
        return {
            "slugline": primary["slugline"],
            "narrative_goal": primary["narrative_goal"],
            "dialogue": primary["dialogue"],
            "camera_code": primary["camera_code"],
            "lighting_code": primary["lighting_code"],
            "transition_type": primary["transition_type"],
            "director_notes": primary["director_notes"],
            "options": options,
        }

    # ==========================================================================
    # Dual-Brain Shot Coverage Planner (Screenwriter 8766 + Director 8765)
    # ==========================================================================

    async def plan_scene_shot_split(
        self,
        scene_number: int,
        slugline: str,
        narrative_goal: str,
        dialogue: str | None = None,
        target_duration: float = 10.0,
        coverage_style: str = "classic_coverage",
        style_code: str = "#Style 01",
        act_number: int = 1,
        voice_dna_profile: str | None = None,
        active_state: dict[str, Any] | str | None = None,
        speaking_character: str | None = None,
    ) -> list[dict[str, Any]]:
        """Co-plan multi-shot coverage (8766 beat/dialogue split + 8765 camera/lens/lighting grammar)."""
        preset_key = coverage_style if coverage_style in COVERAGE_STYLE_PRESETS else "classic_coverage"
        preset = COVERAGE_STYLE_PRESETS[preset_key]
        style_family = get_style_family(style_code)
        family_optics = _STYLE_FAMILY_OPTICS_DEFAULTS.get(style_family, _STYLE_FAMILY_OPTICS_DEFAULTS["photorealistic"])

        safe_target = max(1.0, float(target_duration or 5.0))
        if preset.get("single_shot"):
            needed_shots = 1
            shot_durations = [round(safe_target, 1)]
        elif preset_key == "rapid_montage":
            needed_shots = 1 if safe_target <= 5.0 else (3 if safe_target <= 10.0 else 4)
            per = round(safe_target / needed_shots, 1)
            shot_durations = [per] * needed_shots
        else:
            needed_shots = 1 if safe_target <= 5.0 else (2 if safe_target <= 10.0 else 3)
            shot_durations = [5.0] * needed_shots

        sw_res, dir_res = await asyncio.gather(
            ScreenwriterRAGClient.retrieve_scene_craft(
                style_code=style_code,
                act_number=act_number,
                narrative_goal=f"{narrative_goal} ({preset['label']})",
                duration_tier="5s_max14" if needed_shots > 1 else "10s_max28",
                top_k=2,
            ),
            DirectorRAGClient.retrieve(
                scene_beat=f"{preset['label']}: {slugline} — {narrative_goal}",
                style_code=style_code,
                top_k=2,
            ),
        )
        sw_block = str(sw_res.get("prompt_block") or "").strip()
        dir_block = DirectorRAGClient.format_act_context(dir_res)
        speaker_line = self._format_speaker_continuity_line(speaking_character, voice_dna_profile, active_state)

        prompt = (
            f"You are co-directing as Polya Screenwriter & Polya Director. Decompose Scene #{scene_number} ({safe_target:.1f}s) into EXACTLY {needed_shots} shot(s) "
            f"using coverage strategy '{preset['label']}' ({preset['description']}).\n\n"
            f"SLUGLINE: {slugline}\nNARRATIVE GOAL: {narrative_goal}\nDIALOGUE: {dialogue or 'None / Non-Verbal'}\n"
            f"STYLE: {style_code} (Family: {style_family})\n"
        )
        if speaker_line:
            prompt += f"\n{speaker_line}\n"
        if sw_block:
            prompt += f"\n[SCREENWRITER CRAFT]\n{sw_block}\n"
        if dir_block:
            prompt += f"\n[DIRECTOR VISUAL GRAMMAR]\n{dir_block}\n"
        prompt += (
            f"\nReturn ONLY valid JSON with key 'shots' containing EXACTLY {needed_shots} objects. "
            "Each shot MUST include: shot_number (1..N), duration_seconds, camera_code (#Cam 01-#Cam 34), "
            "lens_code (#Lens 01-#Lens 06), comp_code (#Comp 01-#Comp 08), light_code (#Light 01-#Light 14), "
            "act_code (#Act 01-#Act 24), speed_code (#Speed 01-#Speed 05), dialogue (beat-split spoken fragment or atmospheric [SFX: ...]), "
            "transition_type ('J_CUT' | 'L_CUT' | 'HARD_CUT' | 'NONE'). Ensure varied camera_codes across shots."
        )

        parsed_shots: list[dict[str, Any]] | None = None
        try:
            res = await asyncio.wait_for(
                self._call_llm(
                    messages=[
                        {"role": "system", "content": POLYA_SCREENWRITER_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    retry_on_parse_error=False,
                ),
                timeout=12.0,
            )
            if isinstance(res, dict) and isinstance(res.get("shots"), list) and len(res["shots"]) > 0:
                parsed_shots = [s for s in res["shots"] if isinstance(s, dict)]
        except Exception as exc:
            logger.info("plan_scene_shot_split_fallback: %s", exc)

        # Deterministic micro-split helper for dialogue across shots + style-aware optics fallback
        blueprints = preset["shot_blueprints"]
        raw_dlg = (dialogue or "").strip()
        dlg_chunks: list[str] = []
        if raw_dlg and needed_shots > 1:
            clauses = [c.strip() for c in re.split(r"(?<=[.!?;,])\s+", raw_dlg) if c.strip()]
            if len(clauses) >= needed_shots:
                dlg_chunks = clauses[: needed_shots - 1] + [" ".join(clauses[needed_shots - 1 :])]
            else:
                words = raw_dlg.split()
                step = max(1, math.ceil(len(words) / needed_shots))
                dlg_chunks = [" ".join(words[k * step : (k + 1) * step]).strip() for k in range(needed_shots)]
        elif raw_dlg:
            dlg_chunks = [raw_dlg]

        planned: list[dict[str, Any]] = []
        valid_cuts = {"NONE", "J_CUT", "L_CUT", "HARD_CUT"}
        for idx in range(needed_shots):
            bp = blueprints[idx % len(blueprints)]
            llm_shot = parsed_shots[idx] if (parsed_shots and idx < len(parsed_shots)) else {}
            fb_dlg = dlg_chunks[idx] if idx < len(dlg_chunks) and dlg_chunks[idx] else None
            if not fb_dlg and idx == needed_shots - 1 and raw_dlg == "":
                fb_dlg = "[SFX: Beat reaction & room tone hold]"
            cut = str(llm_shot.get("transition_type") or bp["transition_type"]).strip().upper()
            if cut not in valid_cuts:
                cut = bp["transition_type"]
            planned.append({
                "shot_number": idx + 1,
                "duration_seconds": shot_durations[idx],
                "camera_code": str(llm_shot.get("camera_code") or bp["camera_code"]),
                "lens_code": str(llm_shot.get("lens_code") or bp["lens_code"]),
                "comp_code": str(llm_shot.get("comp_code") or bp["comp_code"]),
                "light_code": str(llm_shot.get("light_code") or family_optics["light_code"]),
                "act_code": str(llm_shot.get("act_code") or family_optics["act_code"]),
                "speed_code": str(llm_shot.get("speed_code") or family_optics["speed_code"]),
                "dialogue": llm_shot.get("dialogue") if llm_shot.get("dialogue") is not None else fb_dlg,
                "transition_type": cut,
                "coverage_style": preset_key,
            })
        return planned

    # ==========================================================================
    # Polya AI Director Advisor (Non-Destructive Scene/Shot Optical Guidance)
    # ==========================================================================

    @staticmethod
    def _coerce_matrix_code(layer: str, candidate: Any, fallback: str) -> str:
        """Validate a matrix code against catalog.py, falling back cleanly if invalid."""
        raw = str(candidate or "").strip()
        if not raw:
            return fallback
        try:
            validated = validate_matrix_code(layer, raw)
            return validated or fallback
        except ValueError:
            return fallback

    async def advise_scene_direction(
        self,
        context: ProjectNarrativeContext,
        scene: dict[str, Any],
        shots: list[dict[str, Any]] | None = None,
        target_shot: dict[str, Any] | None = None,
        focus: str = "all",
        intent_notes: str | None = None,
        include_rag: bool = True,
    ) -> dict[str, Any]:
        """Generate 3 style-aligned, Bible-anchored directing recommendations per scene or shot.

        Never mutates DB. All returned #Cam/#Lens/#Comp/#Light/#Act/#Speed codes are
        verified against catalog.py, and RAG/LLM failures degrade cleanly to heuristic_rag.
        """
        style_code = context.master_style_code or "#Style 01"
        style_family = get_style_family(style_code)
        family_optics = _STYLE_FAMILY_OPTICS_DEFAULTS.get(
            style_family, _STYLE_FAMILY_OPTICS_DEFAULTS["photorealistic"]
        )
        slugline = str(scene.get("slugline") or "")
        narrative_goal = str(scene.get("narrative_goal") or "").strip()
        act_number = int(scene.get("act_number") or 1)
        scene_number = int(scene.get("scene_number") or 1)
        shots_list = list(shots or [])
        active_shot = target_shot or (shots_list[0] if shots_list else {})
        parsed_slug = parse_structured_slugline(slugline)

        # Resolve Bible anchors (character, state, environment, props, laws)
        scene_text = " ".join(
            [narrative_goal.lower()]
            + [str(sh.get("dialogue") or "").lower() for sh in shots_list]
        )
        matched_char = None
        for ch in context.cast_characters:
            cname = str(ch.get("name") or "").strip()
            if cname and cname.lower() in scene_text:
                matched_char = ch
                break
        if not matched_char and context.cast_characters:
            matched_char = context.cast_characters[0]

        active_state_code = None
        matched_char_name = None
        if matched_char:
            matched_char_name = matched_char.get("name")
            states = matched_char.get("states") or []
            total_acts = max(4, act_number)
            target_st_num = self._resolve_act_to_state_number(act_number, total_acts) or 1
            target_st_code = f"#State 0{target_st_num}"
            matched_st = next(
                (s for s in states if str(s.get("state_code", "")).upper() == target_st_code.upper()),
                states[0] if states else None,
            )
            active_state_code = matched_st.get("state_code") if matched_st else target_st_code

        matched_env = None
        loc_low = parsed_slug["location"].lower()
        for env in context.environments:
            ename = str(env.get("name") or "").strip().lower()
            if ename and loc_low and (ename in loc_low or loc_low in ename):
                matched_env = env.get("code") or env.get("name")
                break

        matched_props = [
            str(p.get("code") or p.get("name"))
            for p in context.props
            if str(p.get("name") or "").strip().lower() in scene_text
        ][:3]
        applicable_laws = [str(r) for r in context.continuity_rules[:3] if str(r).strip()]

        # Deterministic risk flags on current shots
        shot_risk_flags: list[dict[str, str]] = []
        shots_to_inspect = [active_shot] if target_shot else shots_list
        for sh in shots_to_inspect:
            if not sh:
                continue
            cam = str(sh.get("camera_code") or "").strip()
            spd = str(sh.get("speed_code") or "").strip()
            trans = str(sh.get("transition_type") or "NONE").upper().strip()
            dlg = str(sh.get("dialogue") or "").strip()
            if spd in ("#Speed 04", "#Speed 05") or cam in ("#Cam 22", "#Cam 25", "#Cam 26"):
                shot_risk_flags.append({
                    "code": "TEMPORAL_JITTER_RISK",
                    "severity": "WARNING",
                    "detail": f"Current setup ({cam} / {spd}) carries elevated optical flow temporal jitter.",
                })
            if cam in ("#Cam 08", "#Cam 09", "#Cam 16"):
                shot_risk_flags.append({
                    "code": "FACE_CONSISTENCY_RISK",
                    "severity": "WARNING",
                    "detail": f"Camera {cam} stresses facial landmark stability; ensure Card 1/Card 3 anchors are locked.",
                })
            if dlg and trans == "NONE":
                shot_risk_flags.append({
                    "code": "CUT_BRIDGE_MISSING",
                    "severity": "INFO",
                    "detail": "Dialogue present with transition_type='NONE'; recommend J_CUT or L_CUT audio bridge.",
                })

        # Query Polia AI Director RAG (8765) with graceful fallback
        if include_rag:
            try:
                rag_result = await DirectorRAGClient.retrieve(
                    scene_beat=f"{slugline}: {narrative_goal} {intent_notes or ''}".strip(),
                    style_code=style_code,
                    engine="veo",
                    top_k=3,
                )
            except Exception as exc:
                logger.info("director_advisor_rag_fallback: %s", exc)
                rag_result = {"director_context": "", "shots": [], "grammars": []}
        else:
            rag_result = {"director_context": "", "shots": [], "grammars": []}
        rag_hits = len(rag_result.get("shots") or []) + len(rag_result.get("grammars") or [])
        rag_block = "\n".join(
            b
            for b in (
                DirectorRAGClient.format_act_context(rag_result),
                DirectorRAGClient.format_treatment_grammar(rag_result),
            )
            if b
        ).strip()

        # Style-family heuristic baselines (3 distinct axes)
        env_light = None
        for env in context.environments:
            if (env.get("code") or env.get("name")) == matched_env:
                env_light = env.get("lighting_code")
                break
        base_light = self._coerce_matrix_code(
            "light",
            active_shot.get("light_code") or env_light or family_optics["light_code"],
            family_optics["light_code"],
        )

        heuristics: list[dict[str, Any]] = [
            {
                "recommendation_id": "rec_1",
                "axis": "optics" if focus == "all" else focus,
                "title": f"{context.style_name or style_code} Master Framing & Lens Depth",
                "rationale": (
                    f"Frames {parsed_slug['location'] or 'the scene'} cleanly for {style_family} while locking "
                    f"eyeline and spatial clarity{f' for {matched_char_name}' if matched_char_name else ''}."
                ),
                "camera_code": "#Cam 04" if style_family != "anime_2d" else "#Cam 03",
                "lens_code": "#Lens 01" if style_family == "photorealistic" else "#Lens 02",
                "comp_code": "#Comp 05",
                "light_code": base_light,
                "act_code": family_optics["act_code"],
                "speed_code": family_optics["speed_code"],
                "transition_type": "J_CUT",
                "continuity_warnings": [
                    f"Preserve {active_state_code or '#State 01'} wardrobe & eyeline axis across reverse cuts."
                ],
            },
            {
                "recommendation_id": "rec_2",
                "axis": "staging" if focus == "all" else focus,
                "title": "Character Subtext & Controlled Micro-Motion",
                "rationale": (
                    f"Isolates emotional turn in Scene #{scene_number} without high-jitter camera artifacts, "
                    f"reinforcing {matched_char_name or 'lead'} continuity."
                ),
                "camera_code": "#Cam 02",
                "lens_code": "#Lens 03",
                "comp_code": "#Comp 01",
                "light_code": base_light,
                "act_code": "#Act 04" if style_family == "photorealistic" else family_optics["act_code"],
                "speed_code": "#Speed 02",
                "transition_type": "L_CUT",
                "continuity_warnings": [
                    "Maintain Card 1/Card 3 facial proportions; avoid unmotivated 180-degree axis flips."
                ],
            },
            {
                "recommendation_id": "rec_3",
                "axis": "lighting" if focus == "all" else focus,
                "title": "Atmospheric Depth & Motivated Contrast",
                "rationale": (
                    f"Enhances spatial separation and tactile materiality in {parsed_slug['location'] or 'set'} "
                    f"anchored to {context.color_grade_emulation or style_code}."
                ),
                "camera_code": "#Cam 07",
                "lens_code": "#Lens 04",
                "comp_code": "#Comp 04",
                "light_code": family_optics["light_code"],
                "act_code": family_optics["act_code"],
                "speed_code": "#Speed 03",
                "transition_type": "HARD_CUT",
                "continuity_warnings": [
                    f"Match {parsed_slug['time_of_day'] or 'established'} key light temperature with adjacent scenes."
                ],
            },
        ]

        user_prompt = (
            "POLYA AI DIRECTOR ADVISOR BRIEF (Non-Destructive 7-Layer Optical & Continuity Guidance)\n"
            f"- Project: {context.title} ({context.genre_tone})\n"
            f"- Style: {style_code} ({context.style_name}, family={style_family})\n"
            f"- Scene #{scene_number} (Act {act_number}): {slugline}\n"
            f"- Narrative Goal: {narrative_goal or 'Cinematic progression'}\n"
            f"- Target Shot: {json.dumps(active_shot, ensure_ascii=False)[:500] if active_shot else 'Scene Primary'}\n"
            f"- Focus: {focus}\n"
            f"- Director Intent Notes: {intent_notes or 'None'}\n"
            f"- Bible Anchors: character={matched_char_name}, state={active_state_code}, env={matched_env}, props={matched_props}\n"
            f"- Continuity Laws: {applicable_laws}\n\n"
            f"{rag_block}\n\n"
            "Return STRICT valid JSON with key 'recommendations' (list of exactly 3 objects), each having:\n"
            "axis, title, rationale, camera_code (#Cam 01-#Cam 34), lens_code (#Lens 01-#Lens 06), "
            "comp_code (#Comp 01-#Comp 08), light_code (#Light 01-#Light 14), act_code (#Act 01-#Act 24), "
            "speed_code (#Speed 01-#Speed 05), transition_type ('J_CUT'|'L_CUT'|'HARD_CUT'|'NONE'), "
            "continuity_warnings (list of short strings)."
        )

        source = "heuristic_rag"
        raw_recs: list[dict[str, Any]] = []
        try:
            llm_res = await asyncio.wait_for(
                self._call_llm(
                    messages=[
                        {"role": "system", "content": POLYA_AI_DIRECTOR_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    retry_on_parse_error=False,
                ),
                timeout=10.0,
            )
            if isinstance(llm_res, dict) and isinstance(llm_res.get("recommendations"), list) and llm_res["recommendations"]:
                raw_recs = [r for r in llm_res["recommendations"] if isinstance(r, dict)]
                if raw_recs:
                    source = "llm_rag"
        except Exception as exc:
            logger.info("director_advisor_heuristic_fallback: %s", exc)

        valid_cuts = {"NONE", "J_CUT", "L_CUT", "HARD_CUT"}
        recommendations: list[dict[str, Any]] = []
        for idx, fb in enumerate(heuristics):
            item = raw_recs[idx] if idx < len(raw_recs) else {}
            cut = str(item.get("transition_type") or fb["transition_type"]).upper().strip()
            if cut not in valid_cuts:
                cut = fb["transition_type"]
            raw_warns = item.get("continuity_warnings")
            warns = (
                [str(w).strip() for w in raw_warns if str(w).strip()]
                if isinstance(raw_warns, list) and raw_warns
                else fb["continuity_warnings"]
            )
            recommendations.append({
                "recommendation_id": fb["recommendation_id"],
                "axis": str(item.get("axis") or fb["axis"]).strip() or fb["axis"],
                "title": str(item.get("title") or fb["title"]).strip() or fb["title"],
                "rationale": str(item.get("rationale") or fb["rationale"]).strip() or fb["rationale"],
                "camera_code": self._coerce_matrix_code("cam", item.get("camera_code"), fb["camera_code"]),
                "lens_code": self._coerce_matrix_code("lens", item.get("lens_code"), fb["lens_code"]),
                "comp_code": self._coerce_matrix_code("comp", item.get("comp_code"), fb["comp_code"]),
                "light_code": self._coerce_matrix_code("light", item.get("light_code"), fb["light_code"]),
                "act_code": self._coerce_matrix_code("act", item.get("act_code"), fb["act_code"]),
                "speed_code": self._coerce_matrix_code("speed", item.get("speed_code"), fb["speed_code"]),
                "transition_type": cut,
                "continuity_warnings": warns,
            })

        return {
            "project_id": context.project_id,
            "scene_id": str(scene.get("id") or ""),
            "shot_id": str(target_shot.get("id")) if target_shot and target_shot.get("id") else None,
            "style_code": style_code,
            "style_family": style_family,
            "source": source,
            "director_rag_hits": rag_hits,
            "bible_anchors": {
                "matched_character": matched_char_name,
                "active_state_code": active_state_code,
                "matched_environment": matched_env,
                "matched_props": matched_props,
                "applicable_laws": applicable_laws,
            },
            "recommendations": recommendations,
            "shot_risk_flags": shot_risk_flags,
        }
