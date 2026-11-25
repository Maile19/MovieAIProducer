"""Async client for the Polia AI Director Trainer RAG Bridge (127.0.0.1:8765).

Retrieves curated Sequence Grammars and Shot Templates with strict graceful
fallback so studio generation never blocks or fails if the bridge is offline,
times out, or has an empty knowledge base.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from backend.app.core.config import get_settings
from backend.app.domain.catalog import STYLE_CATALOG

logger = logging.getLogger("polia.director_rag")

_STYLE_CODE_RE = re.compile(r"^#?\s*style[\s_-]*0?(\d{1,2})$", re.IGNORECASE)
_STYLE_NAME_TO_CODE: dict[str, str] = {
    entry["name"].strip().lower(): entry["code"]
    for entry in STYLE_CATALOG
    if entry.get("code") and entry.get("name")
}

# Legacy narrative genres -> canonical Matrix #Style 01..#Style 18 codes
_LEGACY_GENRE_STYLE_MAP: dict[str, str] = {
    "action": "#Style 01",
    "mecha": "#Style 01",
    "blockbuster": "#Style 01",
    "superhero": "#Style 01",
    "sci-fi": "#Style 02",
    "scifi": "#Style 02",
    "science fiction": "#Style 02",
    "cyberpunk": "#Style 02",
    "thriller": "#Style 02",
    "mystery": "#Style 02",
    "cinematic": "#Style 02",
    "cinematic drama": "#Style 02",
    "cinematic film": "#Style 02",
    "imax": "#Style 02",
    "bollywood": "#Style 03",
    "musical": "#Style 03",
    "xianxia": "#Style 04",
    "wuxia": "#Style 04",
    "historical": "#Style 04",
    "k-drama": "#Style 05",
    "kdrama": "#Style 05",
    "romance": "#Style 05",
    "melodrama": "#Style 05",
    "drama": "#Style 05",
    "donghua": "#Style 06",
    "fantasy": "#Style 07",
    "high fantasy": "#Style 07",
    "medieval": "#Style 07",
    "nusantara": "#Style 08",
    "indonesian": "#Style 08",
    "indonesia": "#Style 08",
    "pixar": "#Style 09",
    "disney": "#Style 09",
    "animation": "#Style 09",
    "3d animation": "#Style 09",
    "family": "#Style 09",
    "comedy": "#Style 10",
    "dreamworks": "#Style 10",
    "illumination": "#Style 10",
    "steampunk": "#Style 11",
    "arcane": "#Style 11",
    "metahuman": "#Style 12",
    "unreal": "#Style 12",
    "stop-motion": "#Style 13",
    "stop motion": "#Style 13",
    "cartoon": "#Style 14",
    "2d": "#Style 14",
    "anime": "#Style 15",
    "ghibli": "#Style 16",
    "horror": "#Style 17",
    "noir": "#Style 17",
    "graphic novel": "#Style 17",
    "dark": "#Style 17",
    "crime": "#Style 17",
    "vintage": "#Style 18",
    "retro": "#Style 18",
    "technicolor": "#Style 18",
}


def normalize_style_code(value: str | None) -> str | None:
    """Normalize explicit `#Style 01`..`#Style 18` codes or catalog style names."""
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None

    match = _STYLE_CODE_RE.match(cleaned)
    if match:
        num = int(match.group(1))
        if 1 <= num <= 18:
            return f"#Style {num:02d}"

    return _STYLE_NAME_TO_CODE.get(cleaned.lower())


def resolve_style_filter(style_code: str | None = None, genre: str | None = None) -> str | None:
    """Resolve MovieAIProducer style/genre inputs into canonical `#Style 01`..`#Style 18`."""
    explicit = normalize_style_code(style_code)
    if explicit:
        return explicit

    genre_as_style = normalize_style_code(genre)
    if genre_as_style:
        return genre_as_style

    if isinstance(genre, str) and genre.strip():
        lowered = genre.strip().lower()
        if lowered in _LEGACY_GENRE_STYLE_MAP:
            return _LEGACY_GENRE_STYLE_MAP[lowered]
        for part in re.split(r"[/,&|]+", lowered):
            part_clean = part.strip()
            if part_clean in _LEGACY_GENRE_STYLE_MAP:
                return _LEGACY_GENRE_STYLE_MAP[part_clean]
        for token in re.split(r"[\s/,&|_-]+", lowered):
            if token in _LEGACY_GENRE_STYLE_MAP:
                return _LEGACY_GENRE_STYLE_MAP[token]
        return "#Style 02"

    return None

_ENGINE_MAP: dict[str, str] = {
    "veo": "veo",
    "google_veo": "veo",
    "google_flow": "veo",
    "flow": "veo",
    "runway": "runway",
    "runway_gen3": "runway",
    "gen3": "runway",
    "kling": "kling",
    "kling_ai": "kling",
    "kling_1.5": "kling",
    "kling_2.0": "kling",
    "sora": "sora",
    "openai_sora": "sora",
    "wan2.1": "wan2.1",
    "wan2_1": "wan2.1",
    "comfyui": "wan2.1",
    "comfyui_wan2.1_t2v_14b": "wan2.1",
    "flux": "flux",
    "flux_dev": "flux",
    "flux_schnell": "flux",
    "9router": "flux",
    "nine_router": "flux",
    "9router_ai": "flux",
    "gemini_image": "flux",
    "multimodel": "flux",
    "sd35": "flux",
    "sd35_large": "flux",
    "huggingface": "flux",
    "sd35_large_hf": "flux",
}


class _InstanceOrClassMethod:
    """Descriptor allowing `Client.retrieve(...)` and `Client(...).retrieve(...)`."""

    def __init__(self, func: Any):
        self._func = func

    def __get__(self, instance: Any, owner: type[Any]) -> Any:
        target = instance if instance is not None else owner()
        return self._func.__get__(target, owner)


def empty_rag_result() -> dict[str, Any]:
    """Return a canonical empty retrieval payload."""
    return {
        "director_context": "",
        "shots": [],
        "grammars": [],
    }


def map_target_engine(provider_target: str | None) -> str:
    """Map MovieAIProducer provider targets to trainer engines."""
    cleaned = (provider_target or "veo").lower().strip()
    return _ENGINE_MAP.get(cleaned, "veo")


class DirectorRAGClient:
    """Async HTTP client for querying the Polia AI Director RAG Bridge."""

    def __init__(
        self,
        enabled: bool | None = None,
        base_url: str | None = None,
        token: str | None = None,
        timeout_sec: float | None = None,
    ):
        settings = get_settings()
        self.enabled = settings.polia_rag_enabled if enabled is None else enabled
        self.base_url = (base_url or settings.polia_rag_url or "http://127.0.0.1:8765").rstrip("/")
        self.token = settings.polia_rag_token if token is None else token
        self.timeout_sec = settings.polia_rag_timeout_sec if timeout_sec is None else timeout_sec

    @_InstanceOrClassMethod
    async def retrieve(
        self,
        scene_beat: str,
        genre: str | None = None,
        engine: str = "veo",
        top_k: int = 4,
        style_code: str | None = None,
    ) -> dict[str, Any]:
        """Query `/api/v1/director/retrieve` with strict timeout and empty fallback."""
        if not self.enabled:
            logger.debug("Director RAG disabled via POLIA_RAG_ENABLED")
            return empty_rag_result()

        cleaned_beat = (scene_beat or "").strip()
        if not cleaned_beat:
            return empty_rag_result()

        mapped_engine = map_target_engine(engine)
        clamped_top_k = max(1, min(int(top_k), 20))
        resolved_style = resolve_style_filter(style_code=style_code, genre=genre)
        payload: dict[str, Any] = {
            "scene_beat": cleaned_beat[:1200],
            "genre": resolved_style,
            "engine": mapped_engine,
            "top_k": clamped_top_k,
        }
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["X-Polia-Token"] = self.token

        url = f"{self.base_url}/api/v1/director/retrieve"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code != 200:
                    logger.warning("Director RAG HTTP %s from bridge; using empty fallback", resp.status_code)
                    return empty_rag_result()
                data = resp.json()
                if (
                    isinstance(data, dict)
                    and resolved_style is not None
                    and not (data.get("shots") or data.get("grammars"))
                ):
                    # Safe client fallback if targeted style has no records in Vector DB yet
                    fallback_payload = {**payload, "genre": None}
                    fb_resp = await client.post(url, json=fallback_payload, headers=headers)
                    if fb_resp.status_code == 200 and isinstance(fb_resp.json(), dict):
                        data = fb_resp.json()
        except httpx.TimeoutException:
            logger.warning("Director RAG timed out after %.2fs; using empty fallback", self.timeout_sec)
            return empty_rag_result()
        except httpx.HTTPError as exc:
            logger.warning("Director RAG connection/HTTP error (%s); using empty fallback", type(exc).__name__)
            return empty_rag_result()
        except Exception as exc:
            logger.warning("Director RAG unexpected error (%s); using empty fallback", type(exc).__name__)
            return empty_rag_result()

        if not isinstance(data, dict):
            return empty_rag_result()

        shots = data.get("shots") if isinstance(data.get("shots"), list) else []
        grammars = data.get("grammars") if isinstance(data.get("grammars"), list) else []
        if not shots and not grammars:
            logger.debug("Director RAG returned empty KB results for query")
            return empty_rag_result()

        return {
            "director_context": str(data.get("director_context") or ""),
            "shots": shots,
            "grammars": grammars,
        }

    @staticmethod
    def format_treatment_grammar(rag_result: dict[str, Any]) -> str:
        """Format retrieved Sequence Grammar for Master Treatment prompts."""
        grammars = rag_result.get("grammars") or []
        if not grammars:
            return ""

        g = grammars[0]
        lines = ["DIRECTOR KNOWLEDGE BASE REFERENCE (Optional Cinematography Inspiration):"]
        if g.get("title"):
            lines.append(f"- Reference Sequence: {g['title']}")
        if g.get("director_master_rule"):
            lines.append(f"- Director Master Rule: {g['director_master_rule']}")
        if g.get("pacing_curve"):
            lines.append(f"- Pacing Curve: {g['pacing_curve']}")

        mini_arcs = g.get("dramatic_mini_arcs") or []
        if isinstance(mini_arcs, list) and mini_arcs:
            arc_bits = []
            for arc in mini_arcs[:3]:
                if isinstance(arc, dict):
                    br = arc.get("beat_range", "")
                    intent = arc.get("narrative_intent", "")
                    strat = arc.get("visual_strategy", "")
                    arc_bits.append(f"Beats {br} ({intent}: {strat})".strip())
            if arc_bits:
                lines.append(f"- Dramatic Mini-Arcs: {'; '.join(arc_bits)}")

        return "\n".join(lines) if len(lines) > 1 else ""

    @staticmethod
    def format_act_context(rag_result: dict[str, Any]) -> str:
        """Format retrieved directing grammar/context for Act scene chunk prompts."""
        grammars = rag_result.get("grammars") or []
        shots = rag_result.get("shots") or []
        if not grammars and not shots:
            return ""

        lines = ["DIRECTOR DIRECTING REFERENCE (Adapt pacing & camera flow when helpful):"]
        if grammars:
            g = grammars[0]
            for label, key in (
                ("Pacing Curve", "pacing_curve"),
                ("Lens Progression", "lens_progression"),
                ("Lighting Evolution", "lighting_evolution"),
                ("Audio Bridge Strategy", "audio_bridge_strategy"),
            ):
                val = g.get(key)
                if val:
                    lines.append(f"- {label}: {val}")
        elif shots:
            for s in shots[:2]:
                mc = s.get("matrix_codes") or {}
                codes = " ".join(
                    str(mc.get(k))
                    for k in ("camera_code", "lens_code", "light_code", "speed_code")
                    if mc.get(k)
                )
                if codes:
                    lines.append(f"- Reference Beat ({s.get('shot_id', 'shot')}): {codes}")

        return "\n".join(lines) if len(lines) > 1 else ""

    @staticmethod
    def format_transpile_cues(
        rag_result: dict[str, Any],
        max_shots: int = 3,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Extract compact cinematography cues and lightweight metadata from shot matches."""
        shots = (rag_result.get("shots") or [])[:max_shots]
        if not shots:
            return "", []

        cue_snippets: list[str] = []
        refs: list[dict[str, Any]] = []
        for s in shots:
            if not isinstance(s, dict):
                continue
            mc = s.get("matrix_codes") or {}
            refs.append({
                "shot_id": s.get("shot_id"),
                "similarity": s.get("similarity"),
                "genre": s.get("genre"),
                "engine": s.get("engine"),
                "matrix_codes": mc,
            })
            pos = str(s.get("positive_prompt") or "").strip()
            if pos:
                trimmed = pos[:180].rstrip(" ,.;")
                cue_snippets.append(trimmed)

        cues_text = " | ".join(cue_snippets) if cue_snippets else ""
        return cues_text, refs
