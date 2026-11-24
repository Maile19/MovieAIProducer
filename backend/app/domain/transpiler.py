"""Live Prompt Transpiler for Generative Cinematic Engines.

Translates Hollywood 12-Step creative matrices and MPB DNA variables into
precise, platform-optimized prompt specifications for Google Veo, Kling AI,
Runway Gen-3, OpenAI Sora, and local ComfyUI.
"""

from typing import Any

from backend.app.domain.catalog import (
    ACTING_MATRIX,
    CAMERA_MATRIX,
    COMPOSITION_MATRIX,
    LENS_MATRIX,
    LIGHTING_MATRIX,
    SPEED_MATRIX,
    STYLE_CATALOG,
)


def _lookup_name(catalog: list[dict[str, str]], code: str) -> str:
    """Helper to lookup name or designation from code."""
    for item in catalog:
        if item.get("code") == code:
            return item.get("name") or item.get("cue") or code
    return code


class LivePromptTranspiler:
    """Transpiler engine compiling cinematic parameters to generative models."""

    @staticmethod
    def transpile(
        provider_target: str,
        style_code: str = "#Style 01",
        camera_code: str = "#Cam 01",
        lens_code: str = "#Lens 01",
        comp_code: str = "#Comp 01",
        light_code: str = "#Light 01",
        act_code: str = "#Act 01",
        speed_code: str = "#Speed 01",
        character_dna: str = "",
        state_code: str = "#State 01",
        wardrobe: str = "",
        env_dna: str = "",
        action_description: str = "",
        fg_description: str = "",
        bg_description: str = "",
        dialogue: str | None = None,
        transition_type: str = "NONE",
        aspect_ratio: str = "16:9",
        preset_rules: dict[str, Any] | None = None,
        is_non_verbal: bool = False,
        model: str | None = None,
    ) -> dict[str, Any]:
        target = provider_target.lower().strip()

        preset_cfg = preset_rules or {}
        non_verbal = (
            is_non_verbal
            or preset_cfg.get("is_non_verbal", False)
            or preset_cfg.get("visual_non_verbal_mode", {}).get("enabled", False)
            or preset_cfg.get("world_rules", {}).get("visual_non_verbal_mode", {}).get("enabled", False)
        )

        style_name = _lookup_name(STYLE_CATALOG, style_code)
        camera_name = _lookup_name(CAMERA_MATRIX, camera_code)
        lens_name = _lookup_name(LENS_MATRIX, lens_code)
        comp_name = _lookup_name(COMPOSITION_MATRIX, comp_code)
        light_name = _lookup_name(LIGHTING_MATRIX, light_code)
        act_name = _lookup_name(ACTING_MATRIX, act_code)
        speed_name = _lookup_name(SPEED_MATRIX, speed_code)

        char_part = character_dna or "Protagonist"
        if wardrobe:
            char_part += f", dressed in {wardrobe}"
        if state_code:
            char_part += f" ({state_code})"

        action_part = action_description or f"performing with {act_name}"
        if non_verbal and "slapstick" not in action_part.lower():
            action_part += " (expressive slapstick non-verbal physical comedy)"

        env_part = env_dna or "cinematic environment"

        fg_bg_parts = []
        if fg_description:
            fg_bg_parts.append(f"Foreground: {fg_description}")
        if bg_description:
            fg_bg_parts.append(f"Background: {bg_description}")
        fg_bg_text = "; ".join(fg_bg_parts) if fg_bg_parts else "balanced depth layers"

        if non_verbal:
            effective_dialogue = None
            effective_transition = transition_type if transition_type != "NONE" else "J_CUT"
        else:
            effective_dialogue = dialogue
            effective_transition = transition_type

        if target in ("veo", "google_veo", "google_flow", "flow"):
            # Google Veo / Google Flow: Rich descriptive cinematic phrasing
            positive = (
                f"Photorealistic cinematic movie shot in {aspect_ratio}. "
                f"Camera: {camera_name} ({camera_code}), {lens_name} ({lens_code}), composition: {comp_name} ({comp_code}). "
                f"Subject: {char_part}, {action_part}. "
                f"Environment: {env_part}. "
                f"Lighting: {light_name} ({light_code}). "
                f"Motion dynamics: {speed_name} ({speed_code}), {fg_bg_text}. "
                f"Visual Style: {style_name} ({style_code}). "
                f"Ultra-high definition, 35mm film grain, 24fps master film print."
            )
            negative = (
                "cartoon, low quality, CGI artifacts, plastic skin, distorted hands, "
                "extra limbs, watermark, jerky camera, unrealistic physics, text"
            )
            engine = "google_veo_2"

        elif target in ("kling", "kling_ai", "kling_1.5", "kling_2.0"):
            # Kling AI: Emphasizes photorealism, physical dynamics, and clear styling
            positive = (
                f"Masterpiece cinematic capture, {style_name} ({style_code}). "
                f"{camera_name}, {lens_name}, {comp_name}. "
                f"{char_part}, {action_part}. "
                f"Set in {env_part}, lit by {light_name}. "
                f"{speed_name} speed profile. {fg_bg_text}. "
                f"8k resolution, authentic skin textures, raytraced reflections, professional color grading."
            )
            negative = (
                "deformed, blurry, low resolution, overexposed, bad anatomy, "
                "mutated fingers, floating objects, subtitles, watermark, amateur footage"
            )
            engine = "kling_v1.5_pro"

        elif target in ("runway", "runway_gen3", "gen3"):
            # Runway Gen-3 Alpha: Directorial structured tags
            positive = (
                f"[Camera Movement]: {camera_name}. "
                f"[Lens & Composition]: {lens_name}, {comp_name}. "
                f"[Subject]: {char_part}. "
                f"[Action]: {action_part}. "
                f"[Lighting]: {light_name}. "
                f"[Environment]: {env_part}. "
                f"[Layers & Motion]: {speed_name}, {fg_bg_text}. "
                f"[Aesthetic Style]: {style_name}. "
                f"Seamless continuous motion, cinematic Hollywood grading, award-winning cinematography."
            )
            negative = (
                "distorted, flickering frames, low fidelity, static poses, artificial gloss, "
                "clipping textures, unstable geometry"
            )
            engine = "runway_gen3_alpha"

        elif target in ("sora", "openai_sora"):
            # OpenAI Sora: Literary cinematography and spatial awareness
            positive = (
                f"Cinematic video in {aspect_ratio} widescreen. "
                f"Captured on {lens_name} with {camera_name}, utilizing {comp_name}. "
                f"Inside {env_part}, {char_part} {action_part}. "
                f"Atmospheric illumination created by {light_name}. "
                f"Depth is articulated with {fg_bg_text}, paced at {speed_name}. "
                f"Art direction governed by {style_name} with organic lens flare and tactile world fidelity."
            )
            negative = (
                "blurry, rubbery bodies, morphing architecture, unnatural gravity, "
                "low frame rate, video noise, uncanny valley"
            )
            engine = "openai_sora_v1"

        elif target in ("9router", "nine_router", "9router_ai", "gemini_image", "multimodel"):
            # 9Router Multi-Model Combo Target: High prompt adherence for multimodal and image generation
            positive = (
                f"Cinematic keyframe film still in {aspect_ratio} aspect ratio. "
                f"Visual Style: {style_name} ({style_code}). "
                f"Optics: {lens_name} ({lens_code}) paired with {camera_name} ({camera_code}), framed in {comp_name} ({comp_code}). "
                f"Subject: {char_part}, {action_part}. "
                f"Scene Environment: {env_part}. "
                f"Lighting Setup: {light_name} ({light_code}). "
                f"Spatial Dynamics: {speed_name} ({speed_code}), {fg_bg_text}. "
                f"35mm motion picture film stock, anamorphic bokeh, photorealistic, 8k uhd, master color grade."
            )
            negative = (
                "blurry, low quality, oversaturated, deformed anatomy, extra limbs, bad eyes, "
                "CGI render artifacts, plastic skin, 3d cartoon, text, watermark, signature, cropped"
            )
            if model and model.strip():
                clean_model = model.strip().replace("/", "_").replace("-", "_").replace(".", "_")
                engine = f"9router_{clean_model}"
            else:
                engine = "9router_multimodel_v1"

        elif target in ("sd35", "sd35_large", "huggingface", "sd35_large_hf"):
            # Hugging Face Stable Diffusion 3.5 Large
            positive = (
                f"cinematic film still, {style_name}, shot on {lens_name}, {camera_name}, {comp_name}, "
                f"{char_part}, {action_part}, {env_part}, dramatic {light_name}, "
                f"{fg_bg_text}, 35mm film grain, masterpiece, 8k uhd, photorealistic, cinematic composition"
            )
            negative = (
                "blurry, distorted, oversaturated, deformed, bad anatomy, lowres, text, watermark, "
                "bad proportions, missing fingers, extra limbs, cartoon, illustration"
            )
            engine = "sd35_large_hf"

        elif target in ("flux", "flux_dev", "flux_schnell"):
            # FLUX.1 Flow Transformer
            positive = (
                f"Cinematic photograph, {aspect_ratio}. {style_name}. "
                f"{char_part}, {action_part}. Setting: {env_part}. "
                f"Lighting: {light_name}. Shot on {lens_name}, {camera_name}. "
                f"Composition: {comp_name}. {fg_bg_text}. "
                f"Photorealistic textures, natural skin details, volumetric lighting, award-winning cinematography."
            )
            negative = (
                "ugly, deformed, noisy, blurry, distorted, out of focus, low quality"
            )
            engine = "flux.1_dev"

        else:
            # Default / ComfyUI / Local reference
            positive = (
                f"cinematic shot, {style_name}, {camera_name}, {lens_name}, {comp_name}, "
                f"{char_part}, {action_part}, {env_part}, {light_name}, {speed_name}, "
                f"{fg_bg_text}, masterpiece, 8k uhd, photorealistic, cinematic lighting"
            )
            negative = (
                "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, "
                "fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark"
            )
            engine = "comfyui_wan2.1_t2v_14b"

        # Invalidate/enrich with preset modifiers if provided
        pos_mod = preset_cfg.get("positive_prompt_modifiers", "")
        neg_add = preset_cfg.get("negative_prompt_additions", "")

        if pos_mod and pos_mod not in positive:
            positive = f"{positive} {pos_mod}"
        if neg_add and neg_add not in negative:
            negative = f"{negative}, {neg_add}"

        # Cleanly read project negative_prompts / prompt_negatives if passed
        proj_negs = (
            preset_cfg.get("negative_prompts")
            or preset_cfg.get("prompt_negatives")
            or (preset_cfg.get("world_rules", {}) if isinstance(preset_cfg.get("world_rules"), dict) else {}).get("negative_prompts")
            or (preset_cfg.get("world_rules", {}) if isinstance(preset_cfg.get("world_rules"), dict) else {}).get("prompt_negatives")
        )
        if proj_negs:
            if isinstance(proj_negs, list):
                proj_neg_str = ", ".join(str(p).strip() for p in proj_negs if str(p).strip())
            else:
                proj_neg_str = str(proj_negs).strip()
            if proj_neg_str and proj_neg_str not in negative:
                negative = f"{negative}, {proj_neg_str}" if negative else proj_neg_str

        metadata = {
            "target_engine": engine,
            "aspect_ratio": aspect_ratio,
            "model": model,
            "selected_model": model,
            "codes": {
                "style": style_code,
                "camera": camera_code,
                "lens": lens_code,
                "comp": comp_code,
                "light": light_code,
                "act": act_code,
                "speed": speed_code,
                "state": state_code,
            },
            "audio_bridge": {
                "dialogue": effective_dialogue,
                "transition_type": effective_transition,
                "non_verbal_mode": non_verbal,
                "j_cut_offset_seconds": -1.2 if non_verbal else None,
                "l_cut_offset_seconds": 1.0 if non_verbal else None,
            },
        }

        return {
            "provider_target": target,
            "positive_prompt": positive,
            "negative_prompt": negative,
            "positive": positive,
            "negative": negative,
            "engine": engine,
            "metadata": metadata,
        }
