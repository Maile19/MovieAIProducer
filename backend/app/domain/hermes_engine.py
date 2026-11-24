"""Hermes Nova (Polya AI) YouTube Trend Engine & Ideation Synthesizer.

Incorporates the evidence-backed YouTube growth framework from Nova YouTube Agent:
- High-CTR curiosity gap and algorithmic hook engineering.
- First 5-second viewer retention cliffhangers and pacing directives.
- High-volume search keyword alignment.
- Structured output validation with deterministic procedural fallback on LLM timeout (25.0s).
"""

import json
import logging
import re
from typing import Any
import httpx

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)

# Canonical YouTube Trend Archetypes (100% matched to studio-constants.ts & catalog.py)
YOUTUBE_TREND_CATALOG: list[dict[str, Any]] = [
    {
        "id": "trend_donghua_3d",
        "category": "Donghua 3D & Cultivation",
        "trend_tag": "🔥 High YouTube Search Volume / Xianxia Boom",
        "target_style_code": "#Style 06",
        "target_style_name": "Donghua 3D",
        "aspect_ratio": "16:9",
        "avg_retention_pacing": "4.5s",
        "suggested_premise_seed": "A discarded mortal mechanic in an ancient clockwork sect accidentally fuses with a celestial artificial core, igniting a war across nine planetary realms.",
        "seo_keywords": ["Donghua 3D", "Immortal Core", "Xianxia Anime", "Cultivation 2026"],
    },
    {
        "id": "trend_cyberpunk_mecha",
        "category": "Sci-Fi Mecha & Cyberpunk Anime",
        "trend_tag": "⚡ High CTR Visuals / Fast Paced Action",
        "target_style_code": "#Style 15",
        "target_style_name": "Anime (Shinkai / Ufotable)",
        "aspect_ratio": "16:9",
        "avg_retention_pacing": "3.8s",
        "suggested_premise_seed": "In a rain-drenched Neo-Tokyo, an outlaw pilot steals an experimental biomechanical titan that responds only to neural trauma memories.",
        "seo_keywords": ["Cyberpunk Mecha", "Anime 4K", "Titan Awakening", "Futuristic SciFi"],
    },
    {
        "id": "trend_kids_nonverbal",
        "category": "Global Kids Slapstick Comedy",
        "trend_tag": "🌍 Universal Algorithm Reach (Zero Language Barrier)",
        "target_style_code": "#Style 10",
        "target_style_name": "DreamWorks / Illumination",
        "aspect_ratio": "16:9",
        "avg_retention_pacing": "3.2s",
        "suggested_premise_seed": "A tiny robotic kitchen drone and an eccentric squirrel wage an escalating slapstick war over the last golden acorn in an automated smart home.",
        "seo_keywords": ["Kids Cartoon 3D", "Slapstick Animation", "Funny Robot", "Family Fun"],
    },
    {
        "id": "trend_hollywood_cinema",
        "category": "Cinematic Hollywood Sci-Fi Thriller",
        "trend_tag": "🎬 High Prestige / Long Watch-Time Retention",
        "target_style_code": "#Style 02",
        "target_style_name": "Hollywood IMAX 70mm",
        "aspect_ratio": "2.39:1",
        "avg_retention_pacing": "5.0s",
        "suggested_premise_seed": "A deep-sea oceanographic drilling crew uncovers a subterranean monolith emitting an electromagnetic countdown synchronized with solar eclipses.",
        "seo_keywords": ["SciFi Mystery", "IMAX Cinematic", "Deep Sea Discovery", "Alien Signal"],
    },
    {
        "id": "trend_epic_fantasy",
        "category": "Epic Dark Fantasy & Lore",
        "trend_tag": "⚔️ Deep Worldbuilding / Lore-Explainer Potential",
        "target_style_code": "#Style 07",
        "target_style_name": "Epic High Fantasy",
        "aspect_ratio": "16:9",
        "avg_retention_pacing": "4.8s",
        "suggested_premise_seed": "A wandering rune-weaver and an exiled sun-knight escort a dormant celestial titan through shifting obsidian valleys before eclipse dawn.",
        "seo_keywords": ["Dark Fantasy Lore", "Nordic Myth", "Dragon Curse", "Cinematic Epic"],
    },
    {
        "id": "trend_vertical_shorts_viral",
        "category": "YouTube Shorts Viral Fiction (9:16)",
        "trend_tag": "📱 Mobile Feed Algorithm Surge / 60s High Velocity",
        "target_style_code": "#Style 11",
        "target_style_name": "Arcane (2.5D Steampunk)",
        "aspect_ratio": "9:16",
        "avg_retention_pacing": "2.5s",
        "suggested_premise_seed": "POV: You are an underground hextech surgeon when the city's corrupt enforcer arrives with a cursed ticking mechanical heart that has 60 seconds left.",
        "seo_keywords": ["Shorts Viral", "Hextech POV", "Steampunk Story", "Short Film 9:16"],
    },
    {
        "id": "trend_xianxia_ethereal",
        "category": "Ethereal Xianxia Myth & Legend",
        "trend_tag": "✨ Atmospheric Visuals / Ethereal Aesthetics",
        "target_style_code": "#Style 04",
        "target_style_name": "Xianxia / Chinese Historical",
        "aspect_ratio": "16:9",
        "avg_retention_pacing": "4.2s",
        "suggested_premise_seed": "An immortal sword spirit cursed to wander in mortal disguise must protect the reincarnation of the emperor who betrayed her ten thousand years ago.",
        "seo_keywords": ["Xianxia Fantasy", "Sword God", "Chinese Myth", "Eastern Fantasy"],
    },
]


def slugify_text(text: str) -> str:
    """Generate clean, URL-safe kebab-case slug from text."""
    clean = re.sub(r"[^\w\s-]", "", text.lower())
    clean = re.sub(r"[\s_-]+", "-", clean)
    return clean.strip("-")


class HermesNovaEngine:
    """Orchestrates YouTube-trend aligned title and synopsis ideation with 25s timeout and failover."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 25.0,
    ):
        settings = get_settings()
        self.base_url = base_url or settings.effective_llm_base_url
        self.api_key = api_key or settings.effective_llm_api_key
        self.model = model or settings.llm_model
        self.timeout = timeout

    async def _call_llm(self, messages: list[dict[str, str]]) -> tuple[dict[str, Any] | None, str]:
        """Call LLM completions endpoint with JSON response format.
        
        Returns tuple of (parsed_json_or_none, "llm" | "procedural_fallback").
        """
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.85,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    content_str = data["choices"][0]["message"]["content"]
                    parsed = json.loads(content_str)
                    return parsed, "llm"
                else:
                    logger.warning(
                        "Hermes Nova LLM call returned non-200 (%d): %s. Activating procedural fallback.",
                        resp.status_code,
                        resp.text[:200],
                    )
                    return None, "procedural_fallback"
        except Exception as exc:
            logger.warning(
                "Hermes Nova LLM exception (%s). Activating procedural fallback.",
                str(exc),
            )
            return None, "procedural_fallback"

    def _assemble_fallback_seo_tags(
        self,
        category: str,
        target_style_code: str,
        titles: list[dict[str, Any]],
    ) -> list[str]:
        """Assemble high-volume YouTube SEO tags and hashtags for description."""
        seen = set()
        tags: list[str] = []

        # Find matching archetype keywords
        for arch in YOUTUBE_TREND_CATALOG:
            if arch.get("category", "").lower() == category.lower() or arch.get("target_style_code") == target_style_code:
                for kw in arch.get("seo_keywords", []):
                    clean = kw.strip()
                    if clean and clean.lower() not in seen:
                        seen.add(clean.lower())
                        tags.append(clean)

        # Add target keywords from titles
        for t in titles:
            for kw in t.get("target_keywords", []):
                clean = kw.strip()
                if clean and clean.lower() not in seen:
                    seen.add(clean.lower())
                    tags.append(clean)

        # Baseline universal tags
        for universal in [category, target_style_code, "MovieAI Producer", "YouTube Film", "Trending 2026", "Viral Animation"]:
            clean = universal.strip()
            if clean and clean.lower() not in seen:
                seen.add(clean.lower())
                tags.append(clean)

        return tags[:15]

    async def generate_10_titles(
        self,
        preset_name: str,
        category: str,
        target_style_code: str,
        target_style_desc: str = "",
        aspect_ratio: str = "16:9",
        seed_premise: str = "",
    ) -> dict[str, Any]:
        """Generate exactly 10 high-CTR YouTube title recommendations."""
        system_prompt = (
            "You are Hermes Nova, Principal YouTube Algorithmic Growth & Content Strategy Agent. "
            "Your objective is to generate EXACTLY 10 irresistible, high-CTR YouTube video titles optimized "
            "for algorithmic recommendations, curiosity gap, and search popularity in 2026.\n\n"
            "Rules:\n"
            "1. Output MUST be strictly valid JSON with keys 'recommendations' (array of EXACTLY 10 objects) "
            "and 'seo_description_tags' (array of 12-15 high-volume YouTube hashtags and search keywords formatted for description SEO).\n"
            "2. Each object must have: 'rank' (1-10), 'title' (punchy, high curiosity gap), 'trend_hook' (why it works on YouTube), "
            "'target_keywords' (list of 3-4 search terms), 'hook_score' (float between 8.5 and 9.9).\n"
            "3. Apply proven YouTube title archetypes: 'The X That Broke Y', 'I Uncovered Z', 'Why Nobody Understands X', "
            "'The Last X: Awakening', 'What Happens When You X'. Avoid cheap buzzwords and generic corporate phrasing.\n"
            "4. Align strictly with the visual style and genre context provided."
        )

        user_content = (
            f"Production Context:\n"
            f"- Preset: {preset_name} (Category: {category})\n"
            f"- Visual Style: {target_style_code} ({target_style_desc})\n"
            f"- Aspect Ratio: {aspect_ratio}\n"
            f"- Seed Premise: {seed_premise or 'High stakes conflict with unique aesthetic hook'}\n\n"
            f"Generate 10 standout titles now in JSON format."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        parsed, source = await self._call_llm(messages)

        if parsed and isinstance(parsed.get("recommendations"), list) and len(parsed["recommendations"]) >= 10:
            recs = parsed["recommendations"][:10]
            # Normalize recommendations and ensure slug exists
            for idx, item in enumerate(recs):
                item["rank"] = idx + 1
                if not item.get("slug"):
                    item["slug"] = slugify_text(item.get("title", f"production-title-{idx+1}"))
                if not item.get("target_keywords"):
                    item["target_keywords"] = [target_style_code, category, "YouTube Film"]
                if not item.get("hook_score"):
                    item["hook_score"] = round(9.5 - (idx * 0.1), 1)

            seo_tags = parsed.get("seo_description_tags")
            if not isinstance(seo_tags, list) or len(seo_tags) == 0:
                seo_tags = self._assemble_fallback_seo_tags(category, target_style_code, recs)

            return {
                "source": "llm",
                "context_summary": f"{target_style_code} • {aspect_ratio}",
                "recommendations": recs,
                "seo_description_tags": seo_tags,
            }

        # Fallback to procedural generator
        fallback_recs = self._procedural_fallback_titles(
            preset_name=preset_name,
            category=category,
            target_style_code=target_style_code,
            seed_premise=seed_premise,
        )
        fallback_seo_tags = self._assemble_fallback_seo_tags(category, target_style_code, fallback_recs)
        return {
            "source": "procedural_fallback",
            "context_summary": f"{target_style_code} • {aspect_ratio}",
            "recommendations": fallback_recs,
            "seo_description_tags": fallback_seo_tags,
        }

    async def generate_10_synopses(
        self,
        locked_title: str,
        preset_name: str,
        target_style_code: str,
        aspect_ratio: str = "16:9",
        seed_premise: str = "",
        trend_keywords: list[str] | None = None,
    ) -> dict[str, Any]:
        """Generate exactly 10 YouTube-retention optimized premise synopses."""
        system_prompt = (
            "You are Hermes Nova, Principal YouTube Script Architect & Audience Retention Strategist. "
            "Your objective is to generate EXACTLY 10 distinct, narrative-rich Logline / Premise Synopsis "
            "variations for the locked production title. Each variation must provide an undeniable cold open hook "
            "and emotional cliffhanger that maximizes YouTube viewer retention.\n\n"
            "Rules:\n"
            "1. Output MUST be strictly valid JSON with key 'synopses' containing an array of EXACTLY 10 objects.\n"
            "2. Each object must have:\n"
            "   - 'rank' (1-10)\n"
            "   - 'angle_label' (e.g. 'High-Retention Cold Open', 'Forbidden Discovery', 'Relentless Chase', 'Moral Dilemma')\n"
            "   - 'synopsis' (2-3 cinematic sentences detailing the protagonist, the catalyst, the escalating stakes, and the immediate jeopardy)\n"
            "   - 'retention_hook' (explanation of the first 5-second viewer hook)\n"
            "   - 'target_audience' (MANDATORY: primary community or demographic, e.g. 'Sci-Fi Thriller & Lore Theorists')\n"
            "3. Ensure each of the 10 variations explores a genuinely different dramatic angle or pacing archetype.\n"
            "4. Never output markdown code fences or conversational text outside the JSON."
        )

        user_content = (
            f"Locked Production Data:\n"
            f"- Title: '{locked_title}'\n"
            f"- Preset: {preset_name}\n"
            f"- Visual Style: {target_style_code}\n"
            f"- Aspect Ratio: {aspect_ratio}\n"
            f"- Seed Context: {seed_premise or 'Intense cinematic premise with high stakes'}\n"
            f"- SEO Keywords: {', '.join(trend_keywords or [locked_title, target_style_code])}\n\n"
            f"Generate 10 structured premise synopses now in JSON format."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        parsed, source = await self._call_llm(messages)

        if parsed and isinstance(parsed.get("synopses"), list):
            raw_synopses = parsed["synopses"]
            cleaned_synopses: list[dict[str, Any]] = []

            def _clean_str(val: Any, default: str) -> str:
                if val is None:
                    return default
                if isinstance(val, list):
                    joined = ", ".join(str(x).strip() for x in val if x is not None and str(x).strip())
                    return joined if joined else default
                val_str = str(val).strip()
                return val_str if val_str else default

            def _pick_field(d: dict[str, Any], *keys: str) -> Any:
                for k in keys:
                    if k in d and d[k] is not None and d[k] != "":
                        return d[k]
                return None

            for raw_elem in raw_synopses:
                if isinstance(raw_elem, dict):
                    cleaned_synopses.append(dict(raw_elem))
                elif isinstance(raw_elem, str) and raw_elem.strip():
                    cleaned_synopses.append({"synopsis": raw_elem.strip()})
                # Skip unrepairable non-dict elements

            if len(cleaned_synopses) >= 10:
                synopses = cleaned_synopses[:10]
                for idx, item in enumerate(synopses):
                    item["rank"] = idx + 1

                    raw_angle = _pick_field(item, "angle_label", "angleLabel", "angle", "label")
                    item["angle_label"] = _clean_str(raw_angle, f"Cinematic Variation #{idx+1}")

                    raw_synopsis = _pick_field(item, "synopsis", "premise", "logline", "summary")
                    item["synopsis"] = _clean_str(raw_synopsis, "High-stakes cinematic narrative premise.")

                    raw_hook = _pick_field(item, "retention_hook", "retentionHook", "hook", "retention", "first_5s_hook", "first_5_seconds")
                    item["retention_hook"] = _clean_str(raw_hook, "High stakes cliffhanger within opening seconds")

                    raw_audience = _pick_field(
                        item,
                        "target_audience",
                        "targetAudience",
                        "target_demographic",
                        "targetDemographic",
                        "audience",
                        "demographic",
                        "target",
                    )
                    item["target_audience"] = _clean_str(raw_audience, "General YouTube Audience")

                return {
                    "source": "llm",
                    "locked_title": locked_title,
                    "synopses": synopses,
                }

        # Fallback to procedural generator
        fallback_synopses = self._procedural_fallback_synopses(
            locked_title=locked_title,
            target_style_code=target_style_code,
            seed_premise=seed_premise,
        )
        return {
            "source": "procedural_fallback",
            "locked_title": locked_title,
            "synopses": fallback_synopses,
        }

    def _procedural_fallback_titles(
        self,
        preset_name: str,
        category: str,
        target_style_code: str,
        seed_premise: str = "",
    ) -> list[dict[str, Any]]:
        """Deterministic procedural generator for 10 high-CTR YouTube titles."""
        subject = "Core" if "anime" in category else "Chronicles"
        if seed_premise:
            words = [w.capitalize() for w in re.findall(r"\b[A-Za-z]{4,}\b", seed_premise)]
            if words:
                subject = words[0]

        templates = [
            (f"{subject}: The Last Awakening", "Curiosity Gap + Awakening Archetype", ["Awakening", target_style_code, "YouTube Premiere"], 9.6),
            (f"Why Nobody Expected the {subject} Incident", "Algorithm Intrigue / Explainer Hook", ["Mystery", "Documentary", "Incident"], 9.4),
            (f"{subject} Protocol: Zero Hour", "High Stakes Ticking Clock", ["Action", "SciFi", "Zero Hour"], 9.3),
            (f"I Spent 24 Hours Inside the {subject}", "First-Person Immersion Hook", ["Challenge", "Survival", "POV"], 9.2),
            (f"The Forgotten Architect of {subject}", "Deep Lore / Forbidden Discovery", ["Lore", "Origin Story", "Discovery"], 9.1),
            (f"Rise of {subject}: Beyond the Veil", "Hero's Journey Ascendance", ["Fantasy", "Ascendance", "Epic 4K"], 9.0),
            (f"{subject} vs The Machine Empire", "Conflict & Confrontation", ["Mecha", "War", "Confrontation"], 8.9),
            (f"The Day {subject} Vanished Forever", "Shocking Catalyst / Disappearance", ["Mystery", "Disappearance", "Drama"], 8.8),
            (f"{subject} Origins: Secret of the 9th Realm", "Franchise Origin / Worldbuilding", ["Origins", "Secret", "9th Realm"], 8.7),
            (f"Escape from {subject}: The Final Transmission", "Desperate Survival / Cliffhanger", ["Escape", "Survival", "Final Transmission"], 8.6),
        ]

        results = []
        for rank, (title, hook, keywords, score) in enumerate(templates, start=1):
            results.append({
                "rank": rank,
                "title": title,
                "slug": slugify_text(title),
                "trend_hook": hook,
                "target_keywords": keywords,
                "hook_score": score,
            })
        return results

    def _procedural_fallback_synopses(
        self,
        locked_title: str,
        target_style_code: str,
        seed_premise: str = "",
    ) -> list[dict[str, Any]]:
        """Deterministic procedural generator for 10 premise synopses."""
        base_premise = seed_premise.strip() or "A perilous anomaly threatens to unravel the foundation of the world."

        angles = [
            (
                "High-Retention Cold Open Hook",
                f"When the atmospheric warning sirens blare without warning across the city, a rogue engineer uncovers that '{locked_title}' was triggered from inside their own private terminal. {base_premise} With enforcer gunships descending in under two minutes, they must make a fatal choice before the network collapses.",
                "Immediate life-or-death emergency in the first 5 seconds",
                "High-octane action & thriller viewers",
            ),
            (
                "Mystery & Forbidden Discovery",
                f"Deep within the classified archives beneath the planetary grid, an unmapped chamber opens for the first time in centuries, revealing the truth behind '{locked_title}'. {base_premise} But deciphering the glyphs awakens an ancient synthetic consciousness that demands an unbearable sacrifice.",
                "High curiosity gap with mythological sci-fi lore",
                "Lore theorists and speculative fiction fans",
            ),
            (
                "Underdog Defiance & Zero-to-Hero",
                f"Dismissed as an unqualified apprentice in the lowest tier of the guild, a young tinkerer stumbles upon the prototype that sparked '{locked_title}'. {base_premise} Armed with nothing but makeshift tools and unyielding grit, they stand as the lone barrier between their home and imperial subjugation.",
                "Empathic connection with immediate underdog rooting value",
                "Anime and shonen progression enthusiasts",
            ),
            (
                "Relentless Pursuit & Ticking Clock",
                f"Framed for the catastrophic detonation of the core facility, a courier carries the only biological key to '{locked_title}' across hostile borders. {base_premise} Every surveillance drone and bounty hunter on the continent is tracking their heartbeat.",
                "Constant kinetic motion with visceral stakes",
                "Action and survival game fans",
            ),
            (
                "Psychological Noir & Dual Identity",
                f"Investigating the inexplicable disappearance of a leading scientist, an investigator realizes that all clues in '{locked_title}' point directly to their own erased memories. {base_premise} In a city where synthetic minds can be rented, truth is the most lethal illusion.",
                "Cerebral twists and neon-drenched atmosphere",
                "Neo-noir and Cyberpunk audience",
            ),
            (
                "Epic Faction War & Political Intrigue",
                f"On the eve of peace negotiations between two bitter rival dynasties, the sudden activation of '{locked_title}' threatens to reignite total warfare. {base_premise} A solitary peacekeeper must unravel a conspiracy woven by their own commanding council.",
                "High-stakes political drama and martial showdowns",
                "Grand fantasy and political thriller fans",
            ),
            (
                "Ethereal Spiritual Awakening",
                f"Born without spiritual spiritual roots, an outcast monk meditates beneath the celestial waterfall and absorbs the wandering soul of '{locked_title}'. {base_premise} Now hunted by elder immortals, they must master a forbidden martial path to save the mortal realm.",
                "Mystical aesthetic with awe-inspiring transcendence",
                "Xianxia and Donghua 3D fandom",
            ),
            (
                "Dark Survival & Horror Infiltration",
                f"Trapped inside a quarantine zone where physical laws no longer apply, a reconnaissance squad realizes that '{locked_title}' is not a weapon, but a living ecosystem. {base_premise} Surviving the night requires trusting the entity whispering through their comms.",
                "Tense atmospheric dread and psychological chills",
                "Sci-fi horror and cosmic mystery fans",
            ),
            (
                "Comedic Slapstick & Accidental Catastrophe",
                f"An over-engineered robotic vacuum cleaner accidentally ingests the omnipotent quantum drive behind '{locked_title}' while tidying the villain's secret lair. {base_premise} Chaos erupts as global crime syndicates try to outsmart a machine that just wants a clean floor.",
                "High-energy visual comedy with universal appeal",
                "General audience and animation family viewers",
            ),
            (
                "Poetic Odyssey & Emotional Climax",
                f"After wandering thirty years in deep space exile, a lone navigator returns to an Earth that no longer remembers their name, bringing the final promise of '{locked_title}'. {base_premise} In a bittersweet journey across reclaimed wilderness, they prepare the planet's final goodbye.",
                "Deep emotional resonance and cinematic poetry",
                "Art-house and cinematic drama cinephiles",
            ),
        ]

        results = []
        for rank, (label, synopsis, hook, audience) in enumerate(angles, start=1):
            results.append({
                "rank": rank,
                "angle_label": label,
                "synopsis": synopsis,
                "retention_hook": hook,
                "target_audience": audience,
            })
        return results
