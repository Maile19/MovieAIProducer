"""Deterministic Character Prompt Compiler & Style Gate (CASTING_CLOSEUP_REALISTIC_V1).

Separates creative visual translation (5 dynamic slots supplied by Polia AI Director
or deterministic fallback) from immutable optical, skin-microtexture, studio-lighting,
and negative-prompt constants.

Pure domain module: no framework, database, or infrastructure imports.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.app.domain.screenwriter import sanitize_negative_prompts_for_style

CASTING_CLOSEUP_PRESET_ID = "CASTING_CLOSEUP_REALISTIC_V1"

RoutingMode = Literal["full", "light_override", "strict_bypass"]

# ==============================================================================
# FROZEN MASTER TEMPLATE LAYERS (SINGLE SOURCE OF TRUTH)
# ==============================================================================

LAYER_1_QUALITY_AND_SKIN_DNA = (
    "Completely unretouched raw human skin with extreme micro-detail: visible pores on cheeks, "
    "nose, and forehead, subtle natural imperfections, faint skin redness variations, fine vellus "
    "facial hair, natural dry lip texture with fine lines, crisp iris fibers with circular studio "
    "catchlights, and individual eyebrow hairs. Zero beauty filter, zero airbrushing, zero CGI sheen. "
    "Unedited 16-bit RAW casting photograph look, neutral true-to-life color grading, high "
    "micro-contrast, fine organic sensor grain."
)

LAYER_2_STUDIO_SETUP = (
    "Soft diffused overhead-front octabox key light (butterfly/clamshell studio lighting) with "
    "subtle lower fill bounce, creating soft sculptural shadows beneath the chin, along the neck, "
    "under the cheekbones, and inside the ears. Matte natural skin reflection with zero harsh "
    "highlights. Seamless matte {STUDIO_BACKDROP_TONE} studio backdrop with very subtle natural vignetting."
)

LAYER_3_CLOSEUP_FRAMING_OPTICS = (
    "Hyper-realistic raw studio portrait photograph of {CHARACTER_IDENTITY_AND_FACIAL_FEATURES}, "
    "dead-center symmetrical straight-on frontal close-up headshot from head to upper shoulders, "
    "eye-level camera angle, looking directly into the lens with {FACIAL_EXPRESSION}. "
    "{HAIR_STYLE_AND_COLOR} with natural loose strands and sharp stray flyaway hairs. "
    "Wearing {WARDROBE_AND_ACCESSORIES_TACTILE_DETAILS}. "
    "Shot on medium format digital camera (Hasselblad X2D / Phase One), 85mm portrait lens at f/4.5, "
    "ISO 100. Razor-sharp tack focus across the eyes, nose, lips, and front hair, with gentle natural "
    "depth-of-field falloff on the ears and shoulders. Square 1:1 framing."
)

FROZEN_NEGATIVE_PROMPT = (
    "airbrushed skin, smooth plastic skin, beauty filter, heavy makeup, glossy skin, overly saturated, "
    "HDR overprocessed, CGI, 3D render, Unreal Engine, digital painting, illustration, harsh dramatic "
    "shadows, strong rim light, blown-out highlights, extreme shallow depth of field, blurry eyes, "
    "crooked symmetry, artificial oversharpening, studio gloss, cinematic teal and orange grading"
)

UPSCALE_2K_LOCK_PREFIX = (
    "High-resolution native 2K detail refinement of the exact subject in the reference image. "
    "Preserve 100% of the identical facial bone structure, eye gaze, expression, scars/marks, "
    "hair silhouette, clothing layout, pose, and framing without altering identity or composition. "
    "Reconstruct and sharpen micro-details to crisp 2K clarity:"
)

# Style-specific light override variants for Layer 1
_LAYER_1_STYLE_05_KDrama = (
    "Natural editorial human skin with soft porcelain clarity, subtle natural skin micro-texture, "
    "soft natural lip texture, crisp iris fibers with circular studio catchlights, and individual "
    "eyebrow hairs. Zero artificial beauty filter, zero plastic airbrushing, zero CGI sheen. "
    "Unedited 16-bit RAW editorial casting photograph look, soft pastel-neutral true-to-life color "
    "grading, balanced micro-contrast, fine organic sensor grain."
)

_LAYER_1_STYLE_12_METAHUMAN = (
    "High-fidelity Unreal Engine 5 Metahuman synthetic human skin with extreme micro-detail: natural "
    "pores on cheeks, nose, and forehead, subtle organic skin variations, fine vellus facial hair, "
    "natural lip texture with fine lines, crisp iris fibers with circular studio catchlights, and "
    "individual eyebrow hairs. Zero beauty filter, zero plastic airbrushing. "
    "Physically calibrated digital studio camera look, neutral true-to-life color grading, high "
    "micro-contrast, fine organic sensor grain."
)

_LAYER_1_STYLE_18_VINTAGE_1970S = (
    "Completely unretouched raw human skin with extreme micro-detail: visible pores on cheeks, "
    "nose, and forehead, subtle natural imperfections, faint skin redness variations, fine vellus "
    "facial hair, natural dry lip texture with fine lines, crisp iris fibers with circular studio "
    "catchlights, and individual eyebrow hairs. Zero beauty filter, zero airbrushing, zero CGI sheen. "
    "Authentic 35mm archival Technicolor film stock look (Eastman Color 5247), warm 1970s vintage "
    "film color science, subtle faded dye-coupler balance, high micro-contrast, fine organic celluloid grain."
)

_REFERENCE_LOCK_PREFIX = (
    "Analyze the reference photograph and strictly preserve the exact person's biometric identity, "
    "bone structure, eye shape, iris color, nose bridge, lip shape, natural skin tone, age, ethnicity, "
    "hair texture, and distinguishing facial marks."
)

# ==============================================================================
# DETERMINISTIC STYLE GATE (#Style 01 - #Style 18)
# ==============================================================================

STYLE_GATE_FULL: frozenset[str] = frozenset({
    "#Style 01",
    "#Style 02",
    "#Style 03",
    "#Style 04",
    "#Style 07",
    "#Style 08",
})

STYLE_GATE_LIGHT_OVERRIDE: frozenset[str] = frozenset({
    "#Style 05",
    "#Style 12",
    "#Style 18",
})

STYLE_GATE_STRICT_BYPASS: frozenset[str] = frozenset({
    "#Style 06",
    "#Style 09",
    "#Style 10",
    "#Style 11",
    "#Style 13",
    "#Style 14",
    "#Style 15",
    "#Style 16",
    "#Style 17",
})

_STYLE_CODE_RE = re.compile(r"^#?\s*style[\s_-]*0?(\d{1,2})$", re.IGNORECASE)

# Providers supporting native 2K (2048x2048) square generation vs capped 1K (1024x1024).
NATIVE_2K_SQUARE_PROVIDERS: frozenset[str] = frozenset({
    "seedream-5-5",
    "flux",
    "adobe-firefly-4",
    "midjourney-v8-2",
    "recraft-v4-pro",
    "mai-image-2-6",
    "qwen-image-3",
    "google-flow",
    "google_flow",
    "gemini-direct",
    "nano-banana-2-1",
    "nano-banana-2.1",
})

CAPPED_1K_SQUARE_PROVIDERS: frozenset[str] = frozenset({
    "9router",
    "nine_router",
    "9router_ai",
    "ag_gemini_flash",
    "antigravity",
    "sd35",
    "sd35_large_hf",
    "huggingface",
    "gpt-2-6",
    "openai",
    "grok-imagine-2-0",
    "leonardo-phoenix",
    "comfyui",
    "mock",
})


def normalize_casting_style_code(style_code: str | None) -> str:
    """Normalize any '#Style XX' input into canonical '#Style 01'..'#Style 18'."""
    if not style_code or not isinstance(style_code, str):
        return "#Style 01"
    cleaned = style_code.strip()
    match = _STYLE_CODE_RE.match(cleaned)
    if match:
        num = int(match.group(1))
        if 1 <= num <= 18:
            return f"#Style {num:02d}"
    return cleaned if cleaned in (STYLE_GATE_FULL | STYLE_GATE_LIGHT_OVERRIDE | STYLE_GATE_STRICT_BYPASS) else "#Style 01"


@dataclass(frozen=True)
class StyleGateDecision:
    style_code: str
    routing_mode: RoutingMode
    layer_1_text: str
    layer_2_template: str
    layer_3_template: str
    negative_prompt: str
    reason: str


def _strip_negative_tokens(negative_prompt: str, tokens_to_remove: set[str]) -> str:
    if not tokens_to_remove:
        return negative_prompt
    kept = [
        tok.strip()
        for tok in negative_prompt.split(",")
        if tok.strip() and tok.strip().lower() not in tokens_to_remove
    ]
    return ", ".join(kept)


def resolve_style_gate(style_code: str | None) -> StyleGateDecision:
    """Resolve deterministic Style Gate routing for #Style 01 - #Style 18."""
    norm_code = normalize_casting_style_code(style_code)

    if norm_code in STYLE_GATE_STRICT_BYPASS:
        return StyleGateDecision(
            style_code=norm_code,
            routing_mode="strict_bypass",
            layer_1_text="",
            layer_2_template="",
            layer_3_template="",
            negative_prompt="",
            reason=f"{norm_code} is non-photorealistic; strict bypass to stylized model-sheet pipeline.",
        )

    if norm_code == "#Style 05":
        sanitized = sanitize_negative_prompts_for_style([FROZEN_NEGATIVE_PROMPT], norm_code)
        return StyleGateDecision(
            style_code=norm_code,
            routing_mode="light_override",
            layer_1_text=_LAYER_1_STYLE_05_KDrama,
            layer_2_template=LAYER_2_STUDIO_SETUP,
            layer_3_template=LAYER_3_CLOSEUP_FRAMING_OPTICS,
            negative_prompt=", ".join(sanitized),
            reason="#Style 05 (K-Drama High-End): editorial porcelain skin fidelity without beauty-filter CGI.",
        )

    if norm_code == "#Style 12":
        # Must remove CGI / 3D render / Unreal Engine from negative prompt for UE5 Metahuman
        stripped_neg = _strip_negative_tokens(
            FROZEN_NEGATIVE_PROMPT,
            {"cgi", "3d render", "unreal engine"},
        )
        sanitized = sanitize_negative_prompts_for_style([stripped_neg], norm_code)
        return StyleGateDecision(
            style_code=norm_code,
            routing_mode="light_override",
            layer_1_text=_LAYER_1_STYLE_12_METAHUMAN,
            layer_2_template=LAYER_2_STUDIO_SETUP,
            layer_3_template=LAYER_3_CLOSEUP_FRAMING_OPTICS,
            negative_prompt=", ".join(sanitized),
            reason="#Style 12 (UE5 Metahuman): synthetic metahuman realism allowed; CGI/3D/UE tokens stripped from negative.",
        )

    if norm_code == "#Style 18":
        sanitized = sanitize_negative_prompts_for_style([FROZEN_NEGATIVE_PROMPT], norm_code)
        return StyleGateDecision(
            style_code=norm_code,
            routing_mode="light_override",
            layer_1_text=_LAYER_1_STYLE_18_VINTAGE_1970S,
            layer_2_template=LAYER_2_STUDIO_SETUP,
            layer_3_template=LAYER_3_CLOSEUP_FRAMING_OPTICS,
            negative_prompt=", ".join(sanitized),
            reason="#Style 18 (Vintage 1970s): 35mm archival color science & warm celluloid grain.",
        )

    # Full auto-apply (#Style 01, 02, 03, 04, 07, 08)
    sanitized = sanitize_negative_prompts_for_style([FROZEN_NEGATIVE_PROMPT], norm_code)
    return StyleGateDecision(
        style_code=norm_code,
        routing_mode="full",
        layer_1_text=LAYER_1_QUALITY_AND_SKIN_DNA,
        layer_2_template=LAYER_2_STUDIO_SETUP,
        layer_3_template=LAYER_3_CLOSEUP_FRAMING_OPTICS,
        negative_prompt=", ".join(sanitized),
        reason=f"{norm_code} is photorealistic/live-action; full Layer 1+2+3 frozen casting preset applied.",
    )


resolve_casting_style_gate = resolve_style_gate


def resolve_provider_dimensions(
    provider_id: str | None,
    width: int,
    height: int,
    aspect_ratio: str = "1:1",
) -> tuple[int, int]:
    """Resolve safe pixel dimensions per image provider.

    Preserves 1K (1024x1024) on initial generation to save tokens, allows native 2K
    (up to 2048px) when 2K dimensions are requested on 2K-capable providers, and
    auto-caps safely to 1K on 1K-limited or unknown providers.
    """
    ar = (aspect_ratio or "1:1").strip()
    prov_norm = (provider_id or "").strip().lower()
    wants_2k = max(width, height) >= 1536

    if ar != "1:1" and width != height:
        if not wants_2k:
            return width, height
        if prov_norm in NATIVE_2K_SQUARE_PROVIDERS:
            return width, height
        # Cap non-square 2K requests down to safe 1K dimensions on 1K-limited providers
        if ar == "16:9":
            return 1024, 576
        if ar == "3:4":
            return 768, 1024
        if ar == "9:16":
            return 576, 1024
        return width, height

    if wants_2k and prov_norm in NATIVE_2K_SQUARE_PROVIDERS:
        return min(max(width, 1024), 2048), min(max(height, 1024), 2048)

    if prov_norm in CAPPED_1K_SQUARE_PROVIDERS or prov_norm:
        return min(max(width, 512), 1024), min(max(height, 512), 1024)

    return min(max(width, 512), 1024), min(max(height, 512), 1024)


# ==============================================================================
# POLIA AI DIRECTOR CONTRACT (5 DYNAMIC VARIABLES + ROUTING HINT)
# ==============================================================================

class DirectorCastingVariables(BaseModel):
    """Strict visual translation payload supplied by Polia AI Director (or deterministic fallback)."""

    character_identity_and_facial_features: str = Field(
        min_length=3,
        max_length=500,
        description="Age, ethnicity, bone structure, eye/brow/nose/lip traits, and facial marks/scars.",
    )
    facial_expression: str = Field(
        default="a calm, neutral resting expression and naturally closed lips",
        min_length=3,
        max_length=220,
        description="Restrained resting or narrative facial expression looking into the lens.",
    )
    hair_style_and_color: str = Field(
        default="Natural neatly styled hair",
        min_length=3,
        max_length=220,
        description="Hair cut, texture, length, and color.",
    )
    wardrobe_and_accessories_tactile_details: str = Field(
        default="a simple neutral charcoal-gray crewneck collar",
        min_length=3,
        max_length=320,
        description="Upper-shoulder collar, fabric weave, hardware, and visible accessories.",
    )
    studio_backdrop_tone: str = Field(
        default="neutral medium-grey",
        min_length=3,
        max_length=80,
        description="Matte studio sweep tone (default: 'neutral medium-grey').",
    )
    routing_hint: RoutingMode = Field(
        default="full",
        description="Director routing recommendation: 'full', 'light_override', or 'strict_bypass'.",
    )


DirectorCharacterDynamicSlots = DirectorCastingVariables


class DirectorCastingTranslationRequest(BaseModel):
    """Contract sent from MovieAIProducer to Polia AI Director visual translator."""

    character_name: str = ""
    raw_biometric_text: str = ""
    narrative_summary: str = ""
    style_code: str = "#Style 01"
    slot: str = "closeup"


class DirectorCastingTranslationResponse(BaseModel):
    """Validated response envelope from Polia AI Director."""

    preset_id: str = CASTING_CLOSEUP_PRESET_ID
    style_code: str = "#Style 01"
    slots: DirectorCharacterDynamicSlots
    source: Literal["director_bridge", "deterministic_fallback"] = "deterministic_fallback"


# Patterns forbidden inside dynamic variables so LLM output never collides with frozen optics/lighting.
_OPTICS_LIGHTING_BOILERPLATE_PATTERNS = [
    r"#[0-9a-fA-F]{3,6}",
    r"\[.*?\]",
    r"(?:shot\s+on|captured\s+on|filmed\s+on)\s+[^,.;]*(?:camera|hasselblad|phase\s+one|lens|mm|f/\d)[^,.;]*",
    r"\b\d{2,3}mm\s+(?:portrait|macro|prime|telephoto|wide)?\s*(?:lens)?(?:\s+at\s+f/\d+(?:\.\d+)?)?",
    r"\bf/\d+(?:\.\d+)?\b",
    r"\bISO\s*\d+\b",
    r"(?:displayed|captured|framed|filmed|shot|seen)?\s*(?:in\s+)?(?:a\s+)?(?:cinematic\s+)?(?:wide-angle|wide\s+shot|medium\s+shot|close-up|extreme\s+close-up|full-body|establishing\s+shot|over-the-shoulder|dutch\s+angle|low\s+angle|high\s+angle|isometric|action\s+pose|profile\s+view)\s*(?:shot|view|angle|framing|perspective)?(?:\s+with\s+[^,.;]*(?:contrast|lighting|light))?",
    r"(?:with\s+)?(?:high-octane|cinematic|dramatic|moody|harsh|neon|volumetric|naturalistic|golden\s+hour|sunset|rim|tungsten|shadowy|chiaroscuro|octabox|butterfly|clamshell)\s*(?:lighting|light|contrast|illumination|ambiance|atmosphere|flare|reflections?)",
    r"(?:that|which)?\s*casts?\s+[^,.;]*(?:light|glow|reflection)[^,.;]*(?:onto|on)\s+[^,.;]*",
    r",?\s*isolated\s+(?:on|in|against)\s+a\s+flat\s+(?:seamless|neutral).*",
    r",?\s*(?:even\s+)?softbox\s+lighting.*",
    r",?\s*zero\s+environment\s+props.*",
    r",?\s*(?:clean\s+)?studio\s+background.*",
    r",?\s*uniform\s+(?:non-directional\s+)?illumination.*",
    r",?\s*character\s+model\s+sheet\s+background.*",
    r",?\s*captured\s+with\s+a\s+shallow\s+depth\s+of\s+field.*",
    r"\b(?:standing|isolated)\s*(?:on|in|against)?\s*$",
]


def _sanitize_dynamic_slot_text(
    raw: str | None,
    *,
    char_name: str | None = None,
    default: str = "",
    max_len: int = 450,
) -> str:
    """Deterministically strip name leaks, hex codes, camera/lighting overrides, and newlines."""
    text = " ".join(str(raw or "").replace("•", " ").replace("–", "-").replace("—", "-").split())
    if char_name:
        text = re.sub(
            rf"(?:^|\b)(?:name\s*[:=]\s*)?{re.escape(char_name)}\b[\s,:\-—]*(?:is\s+)?",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip(" ,.")

    text = re.sub(
        r"^(?:cinematic\s+)?(?:close-up\s+|headshot\s+)?portrait\s+of\s+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip(" ,.")

    for pat in _OPTICS_LIGHTING_BOILERPLATE_PATTERNS:
        text = re.sub(pat, "", text, flags=re.IGNORECASE).strip(" ,.")

    text = re.sub(r",\s*\.", ".", text)
    text = re.sub(r",\s*,+", ",", text)
    text = re.sub(r"\s+", " ", text).strip(" ,.")
    if not text:
        return default
    return text[:max_len].strip(" ,.")


def _extract_hair_phrase(text: str) -> str:
    hair_patterns = [
        r"\b((?:short|long|shoulder-length|chin-length|cropped|buzz-cut|shaved|bald|braided|curly|wavy|straight|messy|textured|slicked-back|swept-back|tousled|ponytail|bun|silver|grey|gray|white|black|dark|blonde|brunette|auburn|red|chestnut|salt-and-pepper)(?:\s+[a-zA-Z-]+){0,4}\s+hair(?:style|cut)?)\b",
        r"\b([^,.;]*\bhair(?:style|cut)?\b)",
    ]
    for pat in hair_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            candidate = _sanitize_dynamic_slot_text(m.group(1), max_len=200)
            candidate = re.sub(r"^(?:with|has|having)\s+", "", candidate, flags=re.IGNORECASE).strip(" ,.")
            if candidate:
                return candidate[0].upper() + candidate[1:]
    return "Natural neatly styled hair"


def _extract_wardrobe_collar_phrase(text: str) -> str:
    clothing_patterns = [
        r"(?:he\s+wears|she\s+wears|they\s+wear|the\s+character\s+wears|wearing|dressed in|outfitted in|styled with)\s+([^,.;]+(?:\bcollar\b|jacket|coat|shirt|suit|sweater|hoodie|uniform|vest|turtleneck|crewneck|armor|trenchcoat|tunic|gown|dress|robe|hanfu|cheongsam|qipao|blouse)[^,.;]*)",
        r"([^,.;]*(?:\bcollar\b|jacket|coat|shirt|suit|sweater|hoodie|uniform|vest|turtleneck|crewneck|armor|trenchcoat|tunic|gown|dress|robe|hanfu|cheongsam|qipao|blouse)[^,.;]*)",
    ]
    wardrobe = "a simple neutral charcoal-gray crewneck collar"
    for pat in clothing_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            item = m.group(1).strip()
            item = re.sub(
                r"^(?:he\s+wears|she\s+wears|they\s+wear|the\s+character\s+wears|wearing|dressed in|outfitted in|styled with)\s+",
                "",
                item,
                flags=re.IGNORECASE,
            ).strip()
            item = re.sub(r"^(?:a|an|the)\s+", "", item, flags=re.IGNORECASE).strip()
            if not item:
                continue
            if re.search(r"\bcollar\b", item, re.IGNORECASE):
                wardrobe = f"a {item}"
            elif any(
                k in item.lower()
                for k in (
                    "vest", "gown", "dress", "robe", "hanfu", "cheongsam", "qipao",
                    "jacket", "suit", "armor", "hoodie", "sweater", "tunic", "top",
                    "blouse", "shirt", "crewneck", "turtleneck", "coat", "trenchcoat",
                )
            ):
                wardrobe = f"a {item}"
            else:
                wardrobe = f"a {item} collar"
            break

    wardrobe = re.sub(r"\bglowing\s+", "", wardrobe, flags=re.IGNORECASE).strip(" ,.")
    wardrobe = re.sub(r"^a\s+(?:a|an|the)\s+", "a ", wardrobe, flags=re.IGNORECASE).strip()
    return wardrobe[:300]


def build_deterministic_dynamic_slots(
    *,
    base_prompt: str,
    char_name: str | None = None,
    style_code: str | None = "#Style 01",
    cached_slots: dict[str, Any] | None = None,
    facial_expression_override: str | None = None,
) -> DirectorCharacterDynamicSlots:
    """Build validated 5 dynamic slots from Polia Director cache or deterministic fallback."""
    gate = resolve_style_gate(style_code)

    if isinstance(cached_slots, dict) and cached_slots.get("character_identity_and_facial_features"):
        try:
            return DirectorCharacterDynamicSlots(
                character_identity_and_facial_features=_sanitize_dynamic_slot_text(
                    cached_slots.get("character_identity_and_facial_features"),
                    char_name=char_name,
                    default="an authentic human individual",
                ),
                facial_expression=_sanitize_dynamic_slot_text(
                    facial_expression_override or cached_slots.get("facial_expression"),
                    char_name=char_name,
                    default="a calm, neutral resting expression and naturally closed lips",
                    max_len=200,
                ),
                hair_style_and_color=_sanitize_dynamic_slot_text(
                    cached_slots.get("hair_style_and_color"),
                    char_name=char_name,
                    default="Natural neatly styled hair",
                    max_len=200,
                ),
                wardrobe_and_accessories_tactile_details=_sanitize_dynamic_slot_text(
                    cached_slots.get("wardrobe_and_accessories_tactile_details"),
                    char_name=char_name,
                    default="a simple neutral charcoal-gray crewneck collar",
                    max_len=300,
                ),
                studio_backdrop_tone=_sanitize_dynamic_slot_text(
                    cached_slots.get("studio_backdrop_tone"),
                    default="neutral medium-grey",
                    max_len=60,
                ),
                routing_hint=gate.routing_mode,
            )
        except Exception:
            pass

    cleaned_bio = _sanitize_dynamic_slot_text(
        base_prompt,
        char_name=char_name,
        default="an authentic human individual",
        max_len=480,
    )
    hair = _extract_hair_phrase(cleaned_bio)
    wardrobe = _extract_wardrobe_collar_phrase(cleaned_bio)
    expression = _sanitize_dynamic_slot_text(
        facial_expression_override,
        char_name=char_name,
        default="a calm, neutral resting expression and naturally closed lips",
        max_len=200,
    )

    return DirectorCharacterDynamicSlots(
        character_identity_and_facial_features=cleaned_bio,
        facial_expression=expression,
        hair_style_and_color=hair,
        wardrobe_and_accessories_tactile_details=wardrobe,
        studio_backdrop_tone="neutral medium-grey",
        routing_hint=gate.routing_mode,
    )


# ==============================================================================
# LAYER ASSEMBLY FUNCTIONS (CARD 1 vs CARDS 2-8 vs DYNAMIC STATES)
# ==============================================================================

def compile_casting_closeup_prompt(
    *,
    slots: DirectorCharacterDynamicSlots,
    style_code: str | None,
    has_face_ref: bool = False,
    aspect_ratio: str | None = None,
) -> dict[str, Any]:
    """Compile Card 1 (closeup) using Layer 1 + Layer 2 + Layer 3 when Style Gate allows."""
    gate = resolve_style_gate(style_code)
    if gate.routing_mode == "strict_bypass":
        return {
            "bypassed": True,
            "preset_id": CASTING_CLOSEUP_PRESET_ID,
            "routing_mode": "strict_bypass",
            "style_code": gate.style_code,
            "reason": gate.reason,
        }

    layer_3 = gate.layer_3_template.format(
        CHARACTER_IDENTITY_AND_FACIAL_FEATURES=slots.character_identity_and_facial_features.rstrip(" ."),
        FACIAL_EXPRESSION=slots.facial_expression.rstrip(" ."),
        HAIR_STYLE_AND_COLOR=slots.hair_style_and_color.rstrip(" ."),
        WARDROBE_AND_ACCESSORIES_TACTILE_DETAILS=slots.wardrobe_and_accessories_tactile_details.rstrip(" ."),
    )
    layer_2 = gate.layer_2_template.format(
        STUDIO_BACKDROP_TONE=slots.studio_backdrop_tone or "neutral medium-grey",
    )
    layer_1 = gate.layer_1_text

    parts = []
    if has_face_ref:
        parts.append(_REFERENCE_LOCK_PREFIX)
    parts.extend([layer_3, layer_1, layer_2])

    positive_prompt = " ".join(p.strip() for p in parts if p and p.strip())
    card_aspect = aspect_ratio or "1:1"
    # Initial Card 1 generation strictly defaults to 1K (1024x1024) for token efficiency
    width, height = (1024, 1024) if card_aspect == "1:1" else (768, 1024)

    return {
        "bypassed": False,
        "preset_id": CASTING_CLOSEUP_PRESET_ID,
        "routing_mode": gate.routing_mode,
        "style_code": gate.style_code,
        "reason": gate.reason,
        "positive_prompt": positive_prompt,
        "negative_prompt": gate.negative_prompt,
        "recommended_aspect_ratio": card_aspect,
        "width": width,
        "height": height,
        "layers_applied": ["layer_1", "layer_2", "layer_3"],
        "dynamic_slots": slots.model_dump(),
    }


def get_downstream_frozen_layers(
    *,
    slot_key: str,
    style_code: str | None,
    studio_backdrop_tone: str = "neutral medium-grey",
    has_injuries_or_wear: bool = False,
) -> dict[str, Any]:
    """Return Layer 1 + Layer 2 ONLY (strictly NO Layer 3) for Cards 2-8 & Dynamic States."""
    gate = resolve_style_gate(style_code)
    if gate.routing_mode == "strict_bypass":
        return {
            "bypassed": True,
            "routing_mode": "strict_bypass",
            "style_code": gate.style_code,
            "layers_applied": [],
        }

    layer_1 = gate.layer_1_text
    if slot_key == "state" and has_injuries_or_wear:
        # Preserve Layer 1 micro-detail & RAW look while ensuring state wear/injuries take visual priority
        layer_1 = layer_1.replace(
            "subtle natural imperfections, ",
            "authentic state-specific surface wear and imperfections, ",
        )

    layer_2 = gate.layer_2_template.format(
        STUDIO_BACKDROP_TONE=studio_backdrop_tone or "neutral medium-grey",
    )

    return {
        "bypassed": False,
        "routing_mode": gate.routing_mode,
        "style_code": gate.style_code,
        "layer_1": layer_1,
        "layer_2": layer_2,
        "negative_prompt": gate.negative_prompt,
        "layers_applied": ["layer_1", "layer_2"],
    }


# ==============================================================================
# NATIVE 2K REFERENCE-GUIDED UPSCALE COMPILER
# ==============================================================================

UPSCALE_2K_TARGET_DIMENSIONS: dict[str, tuple[int, int, str]] = {
    "closeup": (2048, 2048, "1:1"),
    "preview_closeup": (2048, 2048, "1:1"),
    "expression": (2048, 1152, "16:9"),
    "front": (1536, 2048, "3:4"),
    "side": (1536, 2048, "3:4"),
    "three_quarter": (1536, 2048, "3:4"),
    "back": (1536, 2048, "3:4"),
    "tpose": (1536, 2048, "3:4"),
    "action": (1536, 2048, "3:4"),
    "state": (2048, 2048, "1:1"),
}

_STYLIZED_2K_QUALITY_DIRECTIVES: dict[str, str] = {
    "stylized_3d": (
        "Crisp native 2K stylized 3D feature-animation surface refinement: sharp sculpted geometry, "
        "clean physically based material shaders, smooth subsurface shading, crisp specular highlights, "
        "and zero photographic noise or raw human skin pores."
    ),
    "stop_motion": (
        "Crisp native 2K handcrafted stop-motion miniature refinement: sharp tactile plasticine and clay "
        "micro-texture, crisp woven miniature fabric fibers, authentic miniature stage lighting clarity, "
        "and zero glossy digital CGI or raw human skin pores."
    ),
    "anime_2d": (
        "Crisp native 2K 2D animation line-art and cel-shading refinement: razor-sharp ink contours, "
        "clean flat and graded cel-shaded fills, crisp expressive eye highlights, zero pixelation, "
        "and zero photorealistic skin pores or 3D CGI artifacts."
    ),
}


def resolve_upscale_2k_target_dimensions(
    slot_key: str,
    aspect_ratio: str | None = None,
) -> tuple[int, int, str]:
    """Return canonical native 2K target (width, height, aspect_ratio) for a character slot."""
    norm = (slot_key or "closeup").lower().strip()
    if norm in UPSCALE_2K_TARGET_DIMENSIONS:
        w, h, default_ar = UPSCALE_2K_TARGET_DIMENSIONS[norm]
        if aspect_ratio and aspect_ratio.strip() != default_ar:
            ar_clean = aspect_ratio.strip()
            if ar_clean == "16:9":
                return 2048, 1152, "16:9"
            if ar_clean == "3:4":
                return 1536, 2048, "3:4"
            if ar_clean == "1:1":
                return 2048, 2048, "1:1"
        return w, h, default_ar

    ar_clean = (aspect_ratio or "3:4").strip()
    if ar_clean == "16:9":
        return 2048, 1152, "16:9"
    if ar_clean == "1:1":
        return 2048, 2048, "1:1"
    return 1536, 2048, "3:4"


def fold_negative_bans_into_positive(
    positive_prompt: str,
    negative_prompt: str | None,
    style_code: str | None = None,
) -> str:
    """Fold core negative constraints into positive prompt for engines lacking negative_prompt."""
    clean_pos = (positive_prompt or "").strip()
    if not negative_prompt or not negative_prompt.strip():
        return clean_pos
    if "Avoid:" in clean_pos or "Strictly avoid:" in clean_pos:
        return clean_pos

    gate = resolve_style_gate(style_code)
    raw_tokens = [t.strip() for t in negative_prompt.split(",") if t.strip()]
    if gate.style_code == "#Style 12":
        raw_tokens = [
            t for t in raw_tokens
            if t.lower() not in {"cgi", "3d render", "unreal engine"}
        ]

    # Pick concise core bans (up to 12 tokens) so we keep positive prompt clean and within limits
    core_tokens = raw_tokens[:12]
    if not core_tokens:
        return clean_pos
    return f"{clean_pos.rstrip('. ')}. Strictly avoid: {', '.join(core_tokens)}."


def compile_upscale_2k_prompt(
    *,
    slot_key: str,
    style_code: str | None,
    base_positive_prompt: str,
    base_negative_prompt: str,
    style_family: str = "photorealistic",
    studio_backdrop_tone: str = "neutral medium-grey",
    has_override: bool = False,
    has_injuries_or_wear: bool = False,
) -> dict[str, Any]:
    """Compile reference-guided native 2K refinement prompt for any slot or dynamic state."""
    gate = resolve_style_gate(style_code)
    norm_slot = (slot_key or "closeup").lower().strip()
    target_w, target_h, target_ar = resolve_upscale_2k_target_dimensions(norm_slot)

    if gate.routing_mode in ("full", "light_override"):
        layer_1 = gate.layer_1_text
        if norm_slot == "state" and has_injuries_or_wear:
            layer_1 = layer_1.replace(
                "subtle natural imperfections, ",
                "authentic state-specific surface wear and imperfections, ",
            )
        layer_2 = gate.layer_2_template.format(
            STUDIO_BACKDROP_TONE=studio_backdrop_tone or "neutral medium-grey",
        )
        parts = [UPSCALE_2K_LOCK_PREFIX, base_positive_prompt.strip()]
        if has_override:
            # User manual override remains primary subject directive while still enforcing frozen 2K micro-detail
            if layer_1 not in base_positive_prompt:
                parts.append(layer_1)
            if layer_2 not in base_positive_prompt:
                parts.append(layer_2)
        positive_prompt = " ".join(p for p in parts if p)
        negative_prompt = base_negative_prompt or gate.negative_prompt
        layers_applied = ["upscale_2k_lock", "layer_1", "layer_2"]
        if norm_slot in ("closeup", "preview_closeup"):
            layers_applied.append("layer_3")
    else:
        fam_directive = _STYLIZED_2K_QUALITY_DIRECTIVES.get(
            style_family,
            _STYLIZED_2K_QUALITY_DIRECTIVES["anime_2d"],
        )
        positive_prompt = f"{UPSCALE_2K_LOCK_PREFIX} {fam_directive} {base_positive_prompt.strip()}".strip()
        negative_prompt = base_negative_prompt
        layers_applied = ["upscale_2k_lock", f"style_family_{style_family}"]

    return {
        "mode": "upscale_2k",
        "slot": norm_slot,
        "routing_mode": gate.routing_mode,
        "style_code": gate.style_code,
        "style_family": style_family,
        "positive_prompt": positive_prompt,
        "negative_prompt": negative_prompt,
        "target_width": target_w,
        "target_height": target_h,
        "aspect_ratio": target_ar,
        "layers_applied": layers_applied,
    }
