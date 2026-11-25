"""Async & sync-safe client for the Polia AI Screenwriter Trainer RAG Bridge (127.0.0.1:8766).

Retrieves curated craft rules, treatment beats, scene craft exemplars, dialogue
subtext compression patterns, and character voice DNA / 5-state arcs with a strict
1.5s timeout and graceful empty fallback so MovieAIProducer never crashes or blocks.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.app.core.config import get_settings
from backend.app.domain.director_rag import _InstanceOrClassMethod, resolve_style_filter

logger = logging.getLogger("polia.screenwriter_rag")


def empty_screenwriter_rag_result() -> dict[str, Any]:
    """Return a canonical empty retrieval payload."""
    return {
        "prompt_block": "",
        "writing_directives": {},
        "style_family": "",
        "items": [],
    }


def _normalize_response(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return empty_screenwriter_rag_result()
    items = data.get("items") if isinstance(data.get("items"), list) else []
    directives = data.get("writing_directives") if isinstance(data.get("writing_directives"), dict) else {}
    return {
        "prompt_block": str(data.get("prompt_block") or ""),
        "writing_directives": directives,
        "style_family": str(data.get("style_family") or ""),
        "items": items,
    }


class ScreenwriterRAGClient:
    """HTTP client for querying the Polia AI Screenwriter RAG Bridge (port 8766)."""

    def __init__(
        self,
        enabled: bool | None = None,
        base_url: str | None = None,
        timeout_sec: float | None = None,
    ):
        settings = get_settings()
        self.enabled = settings.screenwriter_rag_enabled if enabled is None else enabled
        self.base_url = (base_url or settings.screenwriter_rag_url or "http://127.0.0.1:8766").rstrip("/")
        self.timeout_sec = settings.screenwriter_rag_timeout if timeout_sec is None else timeout_sec

    async def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            logger.debug("Screenwriter RAG disabled via SCREENWRITER_RAG_ENABLED")
            return empty_screenwriter_rag_result()

        url = f"{self.base_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code != 200:
                    logger.warning("Screenwriter RAG HTTP %s on %s; using empty fallback", resp.status_code, endpoint)
                    return empty_screenwriter_rag_result()
                return _normalize_response(resp.json())
        except httpx.TimeoutException:
            logger.warning("Screenwriter RAG timed out after %.2fs on %s; using empty fallback", self.timeout_sec, endpoint)
            return empty_screenwriter_rag_result()
        except httpx.HTTPError as exc:
            logger.warning("Screenwriter RAG HTTP error (%s) on %s; using empty fallback", type(exc).__name__, endpoint)
            return empty_screenwriter_rag_result()
        except Exception as exc:
            logger.warning("Screenwriter RAG unexpected error (%s) on %s; using empty fallback", type(exc).__name__, endpoint)
            return empty_screenwriter_rag_result()

    def _post_sync(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Sync variant for synchronous callers such as analyze_narrative_structure."""
        if not self.enabled:
            return empty_screenwriter_rag_result()

        url = f"{self.base_url}{endpoint}"
        try:
            with httpx.Client(timeout=self.timeout_sec) as client:
                resp = client.post(url, json=payload)
                if resp.status_code != 200:
                    logger.warning("Screenwriter RAG HTTP %s on %s; using empty fallback", resp.status_code, endpoint)
                    return empty_screenwriter_rag_result()
                return _normalize_response(resp.json())
        except httpx.TimeoutException:
            logger.warning("Screenwriter RAG timed out after %.2fs on %s; using empty fallback", self.timeout_sec, endpoint)
            return empty_screenwriter_rag_result()
        except httpx.HTTPError as exc:
            logger.warning("Screenwriter RAG HTTP error (%s) on %s; using empty fallback", type(exc).__name__, endpoint)
            return empty_screenwriter_rag_result()
        except Exception as exc:
            logger.warning("Screenwriter RAG unexpected error (%s) on %s; using empty fallback", type(exc).__name__, endpoint)
            return empty_screenwriter_rag_result()

    @_InstanceOrClassMethod
    async def retrieve_character_voice(
        self,
        style_code: str | None = None,
        genre_tone: str | None = None,
        roles: list[str] | str | None = None,
        top_k: int = 3,
    ) -> dict[str, Any]:
        resolved_style = resolve_style_filter(style_code=style_code, genre=genre_tone)
        role_str = ", ".join(roles) if isinstance(roles, list) else str(roles or "")
        payload = {
            "query": f"{genre_tone or ''} {role_str}".strip()[:800],
            "style": resolved_style,
            "role_archetype": roles[0] if isinstance(roles, list) and len(roles) == 1 else (role_str if isinstance(roles, str) and roles else None),
            "top_k": max(1, min(int(top_k), 10)),
        }
        return await self._post("/retrieve/character_voice", payload)

    @_InstanceOrClassMethod
    def retrieve_structure_rules_sync(
        self,
        style_code: str | None = None,
        structure_type: str | None = None,
        total_scenes: int = 100,
        query: str = "",
        top_k: int = 3,
    ) -> dict[str, Any]:
        resolved_style = resolve_style_filter(style_code=style_code)
        payload = {
            "query": f"{query} {total_scenes} scenes".strip()[:800],
            "style": resolved_style,
            "structure_type": structure_type,
            "top_k": max(1, min(int(top_k), 10)),
        }
        return self._post_sync("/retrieve/structure_rules", payload)

    @_InstanceOrClassMethod
    async def retrieve_structure_rules(
        self,
        style_code: str | None = None,
        structure_type: str | None = None,
        total_scenes: int = 100,
        query: str = "",
        top_k: int = 3,
    ) -> dict[str, Any]:
        resolved_style = resolve_style_filter(style_code=style_code)
        payload = {
            "query": f"{query} {total_scenes} scenes".strip()[:800],
            "style": resolved_style,
            "structure_type": structure_type,
            "top_k": max(1, min(int(top_k), 10)),
        }
        return await self._post("/retrieve/structure_rules", payload)

    @_InstanceOrClassMethod
    async def retrieve_treatment_beats(
        self,
        style_code: str | None = None,
        structure_type: str | None = None,
        genre_tone: str | None = None,
        premise: str = "",
        top_k: int = 3,
    ) -> dict[str, Any]:
        resolved_style = resolve_style_filter(style_code=style_code, genre=genre_tone)
        payload = {
            "query": f"{genre_tone or ''} {premise}".strip()[:1000],
            "style": resolved_style,
            "structure_type": structure_type,
            "top_k": max(1, min(int(top_k), 10)),
        }
        return await self._post("/retrieve/treatment_beats", payload)

    @_InstanceOrClassMethod
    async def retrieve_scene_craft(
        self,
        style_code: str | None = None,
        act_number: int | None = None,
        narrative_goal: str = "",
        duration_tier: str | None = None,
        top_k: int = 3,
    ) -> dict[str, Any]:
        resolved_style = resolve_style_filter(style_code=style_code)
        payload = {
            "query": (narrative_goal or f"Act {act_number or 1} scene beat")[:1000],
            "style": resolved_style,
            "act_number": act_number,
            "duration_tier": duration_tier,
            "top_k": max(1, min(int(top_k), 10)),
        }
        return await self._post("/retrieve/scene_craft", payload)

    @_InstanceOrClassMethod
    async def retrieve_dialogue_cut(
        self,
        style_code: str | None = None,
        max_words: int | None = None,
        dialogue_text: str = "",
        top_k: int = 2,
    ) -> dict[str, Any]:
        resolved_style = resolve_style_filter(style_code=style_code)
        tier = None
        if max_words is not None:
            tier = "5s_max14" if max_words <= 14 else ("10s_max28" if max_words <= 28 else "15s_max42")
        payload = {
            "query": (dialogue_text or "subtext compression")[:800],
            "style": resolved_style,
            "duration_tier": tier,
            "max_words": max_words,
            "top_k": max(1, min(int(top_k), 10)),
        }
        return await self._post("/retrieve/dialogue_cut", payload)
