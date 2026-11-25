"""Live Prompt Transpiler for Generative Cinematic Engines.

Translates Hollywood 12-Step creative matrices and MPB DNA variables into
precise, platform-optimized prompt specifications for Google Veo, Kling AI,
Runway Gen-3, OpenAI Sora, and local ComfyUI.
"""

import asyncio
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
from backend.app.domain.director_rag import DirectorRAGClient
from backend.app.services.screenwriter_rag import ScreenwriterRAGClient


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
        audio_lead_seconds: float | None = None,
        character_name: str = "",
        emotional_anchor: str = "",
        physical_damage: str = "",
        aesthetic_directives: str = "",
        color_grade_emulation: str = "",
        slugline: str = "",
        narrative_goal: str = "",
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

        char_label = character_name.strip()
        base_char = character_dna.strip()
        if char_label and base_char:
            char_part = f"{char_label}: {base_char}"
        elif base_char:
            char_part = base_char
        elif char_label:
            char_part = char_label
        else:
            char_part = "Lead subject"
        if wardrobe:
            char_part += f", dressed in {wardrobe}"
        if physical_damage:
            char_part += f", physical wear: {physical_damage}"
        if emotional_anchor:
            char_part += f", expression/emotion: {emotional_anchor}"
        if state_code:
            char_part += f" ({state_code})"

        beat_parts = [p.strip() for p in (slugline, narrative_goal, action_description) if p and p.strip()]
        action_part = "; ".join(beat_parts) if beat_parts else f"performing with {act_name}"
        if non_verbal and "slapstick" not in action_part.lower():
            action_part += " (expressive non-verbal physical staging)"

        env_part = env_dna or (slugline.strip() if slugline.strip() else "cinematic environment")
        style_detail_bits = [b for b in (aesthetic_directives.strip(), color_grade_emulation.strip()) if b]
        style_suffix = f" ({'; '.join(style_detail_bits)})" if style_detail_bits else ""

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
                f"Cinematic movie shot in {aspect_ratio}. "
                f"Camera: {camera_name} ({camera_code}), {lens_name} ({lens_code}), composition: {comp_name} ({comp_code}). "
                f"Subject: {char_part}, {action_part}. "
                f"Environment: {env_part}. "
                f"Lighting: {light_name} ({light_code}). "
                f"Motion dynamics: {speed_name} ({speed_code}), {fg_bg_text}. "
                f"Visual Style: {style_name} ({style_code}){style_suffix}. "
                f"Ultra-high definition, cohesive film grain, 24fps master print."
            )
            negative = (
                "low quality, blurry, distorted hands, extra limbs, watermark, "
                "jerky camera, unrealistic physics, text, compression artifacts"
            )
            engine = "google_flow_veo2" if target in ("google_flow", "flow") else "google_veo_2"

        elif target in ("seedance", "seedance_1.0", "bytedance_seedance"):
            positive = (
                f"Seedance motion sequence ({aspect_ratio}, 24fps): {style_name} ({style_code}){style_suffix}. "
                f"Camera blocking: {camera_name}, {lens_name}, {comp_name}. "
                f"Character continuity: {char_part}. Action beat: {action_part}. "
                f"Setting: {env_part}. Illumination: {light_name}. Tempo: {speed_name}. {fg_bg_text}."
            )
            negative = "flicker, identity drift, warped limbs, blurry motion, watermark, text"
            engine = "seedance_1.0_pro"

        elif target in ("kling", "kling_ai", "kling_1.5", "kling_2.0"):
            # Kling AI: Emphasizes photorealism, physical dynamics, and clear styling
            positive = (
                f"Masterpiece cinematic capture, {style_name} ({style_code}){style_suffix}. "
                f"{camera_name}, {lens_name}, {comp_name}. "
                f"{char_part}, {action_part}. "
                f"Set in {env_part}, lit by {light_name}. "
                f"{speed_name} speed profile. {fg_bg_text}. "
                f"8k resolution, authentic surface textures, raytraced reflections, professional color grading."
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

        norm_transition = (effective_transition or "NONE").upper().strip()
        raw_transition = (transition_type or "NONE").upper().strip()
        if non_verbal and raw_transition == "NONE" and audio_lead_seconds is None:
            j_offset = -1.2
            l_offset = 1.0
        elif norm_transition == "J_CUT":
            j_offset = -abs(float(audio_lead_seconds)) if audio_lead_seconds is not None else (-1.2 if non_verbal else -1.0)
            l_offset = None
        elif norm_transition == "L_CUT":
            j_offset = None
            l_offset = abs(float(audio_lead_seconds)) if audio_lead_seconds is not None else (1.0 if non_verbal else 0.5)
        else:
            j_offset = None
            l_offset = None

        if target in ("comfyui", "sd35", "sd35_large", "huggingface", "sd35_large_hf"):
            engine_params = {"cfg_scale": 5.5 if "sd35" in target else 6.5, "steps": 28, "sampler": "dpmpp_2m"}
        elif target in ("flux", "flux_dev", "flux_schnell"):
            engine_params = {"guidance_scale": 3.5, "steps": 28}
        elif target in ("9router", "nine_router", "9router_ai", "gemini_image", "multimodel"):
            engine_params = {"model": model or "ag/gemini-3.8-flash", "aspect_ratio": aspect_ratio}
        else:
            engine_params = {"fps": 24, "duration_seconds": 5.0, "aspect_ratio": aspect_ratio}

        prompt_tokens_est = max(1, round(len(positive.split()) * 1.35))

        metadata = {
            "target_engine": engine,
            "aspect_ratio": aspect_ratio,
            "model": model,
            "selected_model": model,
            "prompt_tokens_est": prompt_tokens_est,
            "engine_params": engine_params,
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
                "transition_type": norm_transition,
                "audio_lead_seconds": float(audio_lead_seconds) if audio_lead_seconds is not None else (abs(j_offset) if j_offset is not None else l_offset),
                "non_verbal_mode": non_verbal,
                "j_cut_offset_seconds": j_offset,
                "l_cut_offset_seconds": l_offset,
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

    @staticmethod
    async def transpile_with_rag(
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
        genre: str | None = None,
        top_k: int = 3,
        audio_lead_seconds: float | None = None,
        character_name: str = "",
        emotional_anchor: str = "",
        physical_damage: str = "",
        aesthetic_directives: str = "",
        color_grade_emulation: str = "",
        slugline: str = "",
        narrative_goal: str = "",
        act_number: int | None = None,
    ) -> dict[str, Any]:
        """Compile prompt deterministically then enrich with Dual-RAG (8765 Director + 8766 Screenwriter)."""
        base = LivePromptTranspiler.transpile(
            provider_target=provider_target,
            style_code=style_code,
            camera_code=camera_code,
            lens_code=lens_code,
            comp_code=comp_code,
            light_code=light_code,
            act_code=act_code,
            speed_code=speed_code,
            character_dna=character_dna,
            state_code=state_code,
            wardrobe=wardrobe,
            env_dna=env_dna,
            action_description=action_description,
            fg_description=fg_description,
            bg_description=bg_description,
            dialogue=dialogue,
            transition_type=transition_type,
            aspect_ratio=aspect_ratio,
            preset_rules=preset_rules,
            is_non_verbal=is_non_verbal,
            model=model,
            audio_lead_seconds=audio_lead_seconds,
            character_name=character_name,
            emotional_anchor=emotional_anchor,
            physical_damage=physical_damage,
            aesthetic_directives=aesthetic_directives,
            color_grade_emulation=color_grade_emulation,
            slugline=slugline,
            narrative_goal=narrative_goal,
        )

        beat_parts = [p.strip() for p in (slugline, narrative_goal, action_description, env_dna) if p and p.strip()]
        scene_beat = ". ".join(beat_parts) or f"{style_code} {camera_code} {light_code} cinematic shot"

        rag_result, sw_result = await asyncio.gather(
            DirectorRAGClient.retrieve(
                scene_beat=scene_beat,
                genre=genre,
                style_code=style_code,
                engine=provider_target,
                top_k=top_k,
            ),
            ScreenwriterRAGClient.retrieve_scene_craft(
                style_code=style_code,
                act_number=act_number,
                narrative_goal=scene_beat,
                top_k=2,
            ),
        )
        cues_text, rag_refs = DirectorRAGClient.format_transpile_cues(rag_result, max_shots=top_k)

        sw_directives = sw_result.get("writing_directives") or {}
        sw_items = sw_result.get("items") or []
        sw_cue_bits: list[str] = []
        if sw_directives.get("action_beat_grammar"):
            sw_cue_bits.append(str(sw_directives["action_beat_grammar"]))
        if sw_items and isinstance(sw_items[0], dict):
            subtext_cue = sw_items[0].get("subtext_visual_cue") or sw_items[0].get("visual_subtext") or sw_items[0].get("rule_text")
            if subtext_cue:
                sw_cue_bits.append(str(subtext_cue)[:140])
        sw_cues_text = "; ".join(sw_cue_bits).strip()

        enriched_positive = base["positive_prompt"]
        if sw_cues_text:
            enriched_positive = f"{enriched_positive} Screenwriter visual subtext & beat cues: {sw_cues_text}."
        if cues_text:
            enriched_positive = f"{enriched_positive} Director reference cinematography cues: {cues_text}."

        base["positive_prompt"] = enriched_positive
        base["positive"] = enriched_positive
        base["metadata"]["prompt_tokens_est"] = max(1, round(len(enriched_positive.split()) * 1.35))
        base["rag_references"] = rag_refs
        base["metadata"]["rag_references"] = rag_refs
        base["metadata"]["screenwriter_cues"] = sw_cues_text or None
        base["metadata"]["continuity_sources"] = {
            "style_code": style_code,
            "character_name": character_name or None,
            "state_code": state_code,
            "has_character_dna": bool(character_dna.strip()),
            "has_wardrobe_dna": bool(wardrobe.strip()),
            "director_rag_hits": len(rag_refs),
            "screenwriter_rag_hits": len(sw_items),
        }

        compiled_engines: dict[str, dict[str, str]] = {}
        for eng_key in ("google_flow", "veo", "kling", "seedance", "runway", "sora", "comfyui", "9router"):
            eng_res = LivePromptTranspiler.transpile(
                provider_target=eng_key,
                style_code=style_code,
                camera_code=camera_code,
                lens_code=lens_code,
                comp_code=comp_code,
                light_code=light_code,
                act_code=act_code,
                speed_code=speed_code,
                character_dna=character_dna,
                state_code=state_code,
                wardrobe=wardrobe,
                env_dna=env_dna,
                action_description=action_description,
                fg_description=fg_description,
                bg_description=bg_description,
                dialogue=dialogue,
                transition_type=transition_type,
                aspect_ratio=aspect_ratio,
                preset_rules=preset_rules,
                is_non_verbal=is_non_verbal,
                model=model if eng_key == "9router" else None,
                audio_lead_seconds=audio_lead_seconds,
                character_name=character_name,
                emotional_anchor=emotional_anchor,
                physical_damage=physical_damage,
                aesthetic_directives=aesthetic_directives,
                color_grade_emulation=color_grade_emulation,
                slugline=slugline,
                narrative_goal=narrative_goal,
            )
            eng_pos = eng_res["positive_prompt"]
            if sw_cues_text:
                eng_pos = f"{eng_pos} Screenwriter visual subtext & beat cues: {sw_cues_text}."
            if cues_text:
                eng_pos = f"{eng_pos} Director reference cinematography cues: {cues_text}."
            compiled_engines[eng_key] = {
                "engine": eng_res["engine"],
                "positive_prompt": eng_pos,
                "negative_prompt": eng_res["negative_prompt"],
            }
        base["compiled_engines"] = compiled_engines
        return base
