"""Cross-Scene & Cross-Shot Continuity Audit Engine (ADR-0009).

Evaluates multi-scene and multi-shot production continuity deterministically against:
1. Character DNA & Dynamic States (#State 01-#State 05 progression, Voice DNA, visual anchors)
2. World Props, Environments & Lighting consistency across locations (#Env, #Prop, #Light)
3. Optical Coverage, 180-degree spatial/transition discipline, temporal jitter & face drift risks
4. Master Production Bible Continuity Rules & style-family-safe Negative Prompts
"""

from __future__ import annotations

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
from backend.app.domain.screenwriter import (
    PolyaScreenwriterEngine,
    get_style_family,
    parse_structured_slugline,
    sanitize_negative_prompts_for_style,
)

_VALID_CAM_CODES = {item["code"] for item in CAMERA_MATRIX}
_VALID_LENS_CODES = {item["code"] for item in LENS_MATRIX}
_VALID_COMP_CODES = {item["code"] for item in COMPOSITION_MATRIX}
_VALID_LIGHT_CODES = {item["code"] for item in LIGHTING_MATRIX}
_VALID_ACT_CODES = {item["code"] for item in ACTING_MATRIX}
_VALID_SPEED_CODES = {item["code"] for item in SPEED_MATRIX}
_VALID_STYLE_CODES = {item["code"] for item in STYLE_CATALOG}

_TEMPORAL_JITTER_SPEEDS = {"#Speed 04", "#Speed 05"}
_TEMPORAL_JITTER_CAMS = {"#Cam 22", "#Cam 25", "#Cam 26"}
_FACE_DRIFT_CAMS = {"#Cam 08", "#Cam 09", "#Cam 16"}
_HIGH_CONTRAST_WARM_LIGHTS = {"#Light 05", "#Light 01", "#Light 11"}
_COLD_DIGITAL_LIGHTS = {"#Light 06", "#Light 08", "#Light 10", "#Light 12"}


def _get_attr(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _extract_state_num(code: str | None) -> int | None:
    if not code:
        return None
    cleaned = str(code).strip()
    digits = "".join(ch for ch in cleaned if ch.isdigit())
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _lighting_bucket(light_code: str | None) -> str:
    code = (light_code or "").strip()
    if code in _HIGH_CONTRAST_WARM_LIGHTS:
        return "warm_low_key"
    if code in _COLD_DIGITAL_LIGHTS:
        return "cool_high_key"
    if code:
        return "neutral"
    return "unknown"


class ContinuityAuditEngine:
    """Deterministic cross-scene and cross-shot continuity auditor aligned with ADR-0009."""

    @staticmethod
    def audit_project(
        project_id: str,
        scenes: list[Any],
        shots_by_scene: dict[Any, list[Any]],
        characters: list[Any],
        states_by_char: dict[Any, list[Any]],
        project: Any = None,
        bible: Any = None,
        scene_id_filter: str | None = None,
        act_number_filter: int | None = None,
        strict_mode: bool = False,
    ) -> dict[str, Any]:
        """Run a 4-pillar continuity audit across the project's scenes, shots, and Bible."""
        proj_settings = _get_attr(project, "settings", None)
        if not isinstance(proj_settings, dict):
            proj_settings = {}

        bible_styles = _get_attr(bible, "style_parameters", None)
        if not isinstance(bible_styles, dict):
            bible_styles = {}

        world_rules = _get_attr(bible, "world_rules", None)
        if not isinstance(world_rules, dict):
            world_rules = {}

        style_code = str(
            bible_styles.get("master_style_code")
            or _get_attr(project, "target_style_code", None)
            or "#Style 01"
        ).strip()
        style_family = get_style_family(style_code)

        total_acts = 4
        tr = proj_settings.get("treatment") or {}
        if isinstance(tr, dict):
            if isinstance(tr.get("acts"), list) and tr["acts"]:
                total_acts = len(tr["acts"])
            elif tr.get("structure_type") == "3_act":
                total_acts = 3
            elif tr.get("structure_type") == "5_act":
                total_acts = 5

        findings: list[dict[str, Any]] = []
        pillar_deductions: dict[str, int] = {
            "character_dna_states": 0,
            "world_props_lighting": 0,
            "optical_spatial": 0,
            "rules_invariants": 0,
        }
        deduction_weights = {"CRITICAL": 25, "HIGH": 15, "MEDIUM": 8, "LOW": 3}

        def add_finding(
            pillar: str,
            severity: str,
            title: str,
            detail: str,
            remediation: str,
            scene: Any = None,
            shot: Any = None,
            deduct: bool = True,
        ) -> None:
            sc_id = _get_attr(scene, "id", None)
            sh_id = _get_attr(shot, "id", None)
            findings.append({
                "finding_id": f"cont_{len(findings) + 1:03d}",
                "pillar": pillar,
                "severity": severity,
                "scene_id": str(sc_id) if sc_id else None,
                "scene_number": _get_attr(scene, "scene_number", None),
                "act_number": _get_attr(scene, "act_number", None),
                "shot_id": str(sh_id) if sh_id else None,
                "shot_number": _get_attr(shot, "shot_number", None),
                "title": title,
                "detail": detail,
                "remediation": remediation,
            })
            if deduct:
                pillar_deductions[pillar] = pillar_deductions.get(pillar, 0) + deduction_weights.get(severity, 5)

        # ------------------------------------------------------------------
        # Pillar 1 (Project-level): Character DNA & Dynamic States
        # ------------------------------------------------------------------
        char_has_visual_ref: dict[Any, bool] = {}
        if not characters:
            add_finding(
                "character_dna_states",
                "CRITICAL",
                "Missing Cast DNA Anchors",
                "Project has zero characters registered in the Master Production Bible.",
                "Add or generate at least one cast character with dna_seed, base_prompt, Voice DNA, and #State 01–05.",
            )
        else:
            for ch in characters:
                ch_id = _get_attr(ch, "id", None)
                ch_name = str(_get_attr(ch, "name", "Unnamed Character") or "Unnamed Character")
                base_prompt = str(_get_attr(ch, "base_prompt", "") or "").strip()
                dna_seed = _get_attr(ch, "dna_seed", None)
                voice_dna = str(_get_attr(ch, "voice_dna_profile", "") or "").strip()
                ch_states = states_by_char.get(ch_id, [])

                has_ref = any(
                    bool(_get_attr(ch, col, None))
                    for col in ("closeup_image_url", "front_image_url", "three_quarter_image_url", "side_image_url")
                ) or any(bool(_get_attr(st, "image_url", None)) for st in ch_states)
                char_has_visual_ref[ch_id] = has_ref

                if not base_prompt or not dna_seed:
                    add_finding(
                        "character_dna_states",
                        "CRITICAL",
                        f"Missing Biometric Anchor for '{ch_name}'",
                        f"Character '{ch_name}' lacks {'dna_seed' if not dna_seed else 'base_prompt'} required for cross-shot identity lock.",
                        "Complete base visual prompt and deterministic DNA seed in Character DNA Matrix.",
                    )

                if not voice_dna:
                    add_finding(
                        "character_dna_states",
                        "HIGH",
                        f"Missing Voice DNA Profile for '{ch_name}'",
                        f"Character '{ch_name}' has no Voice DNA cadence profile for dialogue consistency.",
                        "Define voice_dna_profile in Character DNA & State Matrix.",
                    )

                if not ch_states:
                    add_finding(
                        "character_dna_states",
                        "HIGH",
                        f"Missing Dynamic States (#State 01–05) for '{ch_name}'",
                        f"Character '{ch_name}' has 0 progression states; wardrobe and wear continuity cannot be verified across acts.",
                        "Generate or create #State 01 through #State 05 in Character Matrix.",
                    )
                else:
                    empty_wardrobe_states = [
                        str(_get_attr(st, "state_code", "#State"))
                        for st in ch_states
                        if not str(_get_attr(st, "wardrobe", "") or "").strip()
                    ]
                    if empty_wardrobe_states:
                        add_finding(
                            "character_dna_states",
                            "HIGH",
                            f"Incomplete State Wardrobe Anchor for '{ch_name}'",
                            f"States {', '.join(empty_wardrobe_states)} lack wardrobe descriptions.",
                            "Populate wardrobe anchors for every dynamic character state.",
                        )

                if not has_ref:
                    add_finding(
                        "character_dna_states",
                        "LOW",
                        f"Pending Visual Reference Sheet for '{ch_name}'",
                        "No rendered or uploaded close-up/front sheet attached yet (pending_asset).",
                        "Generate or upload Card 1 (Close-Up) and Card 3 (Front) in Character Matrix.",
                    )

        # ------------------------------------------------------------------
        # Pillar 4 (Project-level): Rules, Invariants & Style-Safe Negatives
        # ------------------------------------------------------------------
        if style_code not in _VALID_STYLE_CODES:
            add_finding(
                "rules_invariants",
                "CRITICAL",
                "Invalid Master Style Code",
                f"Active style code '{style_code}' is outside canonical #Style 01–#Style 18 catalog.",
                "Select a canonical #Style code in Master Production Bible -> Visual DNA.",
            )

        rules_list = world_rules.get("continuity_rules")
        if rules_list is None:
            rules_list = world_rules.get("continuity_laws")
        if not isinstance(rules_list, list) or not [r for r in rules_list if str(r).strip()]:
            add_finding(
                "rules_invariants",
                "HIGH" if bible is not None else "MEDIUM",
                "Missing Bible Continuity Laws",
                "Master Production Bible has no active continuity_rules defined.",
                "Generate or add continuity invariants in Bible -> Rules & Invariants.",
            )

        neg_list = world_rules.get("negative_prompts")
        if neg_list is None:
            neg_list = world_rules.get("prompt_negatives")
        if isinstance(neg_list, list):
            for raw_neg in neg_list:
                neg_str = str(raw_neg or "").strip()
                if not neg_str:
                    continue
                sanitized = sanitize_negative_prompts_for_style([neg_str], style_code)
                sanitized_joined = ", ".join(sanitized).strip()
                if sanitized_joined.lower() != ", ".join(t.strip() for t in neg_str.split(",") if t.strip()).lower():
                    is_locked = bool(_get_attr(bible, "is_locked", False))
                    add_finding(
                        "rules_invariants",
                        "CRITICAL" if is_locked else "HIGH",
                        "Style-Contradicting Negative Prompt Exclusion",
                        f"Negative prompt '{neg_str}' excludes core visual traits of {style_code} ({style_family}).",
                        "Remove style-conflicting tokens or re-run Polya Rules & Invariants generator.",
                    )

        # ------------------------------------------------------------------
        # World & Props index
        # ------------------------------------------------------------------
        envs_raw = world_rules.get("environments") if isinstance(world_rules.get("environments"), list) else []
        props_raw = world_rules.get("props") if isinstance(world_rules.get("props"), list) else []
        registered_prop_names = {
            str(p.get("name", "")).strip().lower(): p
            for p in props_raw
            if isinstance(p, dict) and str(p.get("name", "")).strip()
        }
        registered_env_names = [
            str(e.get("name", "")).strip().lower()
            for e in envs_raw
            if isinstance(e, dict) and str(e.get("name", "")).strip()
        ]

        # ------------------------------------------------------------------
        # Cross-Scene & Cross-Shot Timeline Inspection
        # ------------------------------------------------------------------
        ordered_scenes = sorted(
            scenes,
            key=lambda s: (int(_get_attr(s, "scene_number", 0) or 0), int(_get_attr(s, "act_number", 1) or 1)),
        )

        # Filter target scope for findings visibility while evaluating timeline
        target_scenes = ordered_scenes
        if scene_id_filter:
            target_scenes = [s for s in ordered_scenes if str(_get_attr(s, "id", "")) == str(scene_id_filter)]
        elif act_number_filter is not None:
            target_scenes = [s for s in ordered_scenes if int(_get_attr(s, "act_number", 1) or 1) == int(act_number_filter)]

        target_scene_ids = {str(_get_attr(s, "id", "")) for s in target_scenes}

        if not ordered_scenes:
            add_finding(
                "optical_spatial",
                "CRITICAL",
                "Empty Storyboard Timeline",
                "Project has zero scenes to audit for visual or narrative continuity.",
                "Create scenes or run the Blueprint generator before running continuity audit.",
            )

        last_char_state_seen: dict[Any, tuple[int, int]] = {}  # char_id -> (state_num, scene_number)
        last_location_lighting: dict[tuple[str, str], tuple[str, str, int]] = {}  # (loc, tod) -> (bucket, light_code, scene_num)
        audited_shots_count = 0

        for sc in ordered_scenes:
            sc_id = _get_attr(sc, "id", None)
            in_scope = str(sc_id) in target_scene_ids
            sc_num = int(_get_attr(sc, "scene_number", 1) or 1)
            act_num = int(_get_attr(sc, "act_number", 1) or 1)
            slugline = str(_get_attr(sc, "slugline", "") or "")
            goal = str(_get_attr(sc, "narrative_goal", "") or "").strip()
            sc_shots = sorted(
                shots_by_scene.get(sc_id, []),
                key=lambda sh: int(_get_attr(sh, "shot_number", 0) or 0),
            )
            if in_scope:
                audited_shots_count += len(sc_shots)

            parsed_slug = parse_structured_slugline(slugline)
            if in_scope and not parsed_slug["location"]:
                add_finding(
                    "world_props_lighting",
                    "CRITICAL",
                    f"Malformed Slugline in Scene #{sc_num}",
                    f"Scene #{sc_num} slugline '{slugline}' lacks a parseable location.",
                    "Format slugline as 'INT./EXT. LOCATION - TIME_OF_DAY'.",
                    scene=sc,
                )

            scene_text_lower = " ".join(
                [goal.lower()]
                + [str(_get_attr(sh, "dialogue", "") or "").lower() for sh in sc_shots]
            )

            # Match scene speaker / subject character
            matched_char = None
            for ch in characters:
                cname = str(_get_attr(ch, "name", "") or "").strip()
                if cname and cname.lower() in scene_text_lower:
                    matched_char = ch
                    break
            if not matched_char and characters:
                matched_char = characters[0]

            if matched_char is not None:
                ch_id = _get_attr(matched_char, "id", None)
                ch_name = str(_get_attr(matched_char, "name", "Lead") or "Lead")
                ch_states = states_by_char.get(ch_id, [])
                expected_state_num = PolyaScreenwriterEngine._resolve_act_to_state_number(act_num, total_acts) or 1

                # Detect explicit state override/reference in scene text or shot layers, else act-mapped
                explicit_state_num: int | None = None
                for sh in sc_shots:
                    layers = _get_attr(sh, "fg_bg_layers", None)
                    if isinstance(layers, dict) and layers.get("state_code"):
                        explicit_state_num = _extract_state_num(str(layers.get("state_code")))
                        break
                effective_state_num = explicit_state_num or expected_state_num

                prev_entry = last_char_state_seen.get(ch_id)
                if prev_entry is not None:
                    prev_state_num, prev_sc_num = prev_entry
                    if effective_state_num < prev_state_num:
                        if in_scope:
                            add_finding(
                                "character_dna_states",
                                "MEDIUM",
                                f"Character State Regression for '{ch_name}'",
                                (
                                    f"Scene #{sc_num} (Act {act_num}) resolves to #State 0{effective_state_num}, "
                                    f"earlier than #State 0{prev_state_num} established in Scene #{prev_sc_num}."
                                ),
                                "Verify intentional flashback or update shot state_code to maintain chronological progression.",
                                scene=sc,
                            )
                last_char_state_seen[ch_id] = (effective_state_num, sc_num)

                if in_scope and ch_states:
                    target_code = f"#State 0{effective_state_num}"
                    has_target_state = any(
                        str(_get_attr(st, "state_code", "")).upper() == target_code.upper()
                        for st in ch_states
                    )
                    if not has_target_state:
                        add_finding(
                            "character_dna_states",
                            "MEDIUM",
                            f"Missing {target_code} Definition for '{ch_name}'",
                            f"Scene #{sc_num} (Act {act_num}) maps to {target_code}, which is not configured on '{ch_name}'.",
                            f"Add {target_code} with wardrobe & expression anchor in Character Matrix.",
                            scene=sc,
                        )

            # World & Lighting continuity across same location + time_of_day
            loc_key = parsed_slug["location"]
            tod_key = parsed_slug["time_of_day"] or "UNSPECIFIED"
            primary_shot = sc_shots[0] if sc_shots else None
            if loc_key and primary_shot is not None:
                prim_light = str(_get_attr(primary_shot, "light_code", "") or "").strip()
                prim_bucket = _lighting_bucket(prim_light)
                prev_loc = last_location_lighting.get((loc_key, tod_key))
                if prev_loc is not None:
                    prev_bucket, prev_light, prev_sc = prev_loc
                    if (
                        prim_bucket != "unknown"
                        and prev_bucket != "unknown"
                        and prim_bucket != prev_bucket
                        and in_scope
                    ):
                        add_finding(
                            "world_props_lighting",
                            "MEDIUM",
                            f"Lighting Temperature Flip at '{loc_key}'",
                            (
                                f"Scene #{sc_num} uses {prim_light} ({prim_bucket}) at '{loc_key} - {tod_key}', "
                                f"contradicting {prev_light} ({prev_bucket}) in Scene #{prev_sc}."
                            ),
                            f"Align lighting code with {prev_light} or change slugline time-of-day if time elapsed.",
                            scene=sc,
                            shot=primary_shot,
                        )
                last_location_lighting[(loc_key, tod_key)] = (prim_bucket, prim_light, sc_num)

            # Check unregistered env warning if Bible environments are populated
            if in_scope and registered_env_names and loc_key:
                loc_low = loc_key.lower()
                if not any(en in loc_low or loc_low in en for en in registered_env_names):
                    add_finding(
                        "world_props_lighting",
                        "LOW",
                        f"Unanchored Location '{loc_key}' in Scene #{sc_num}",
                        f"Slugline location '{loc_key}' does not match any registered Bible #Env 01–05 location.",
                        "Link or register the environment in Bible -> World & Props for consistent set architecture.",
                        scene=sc,
                    )

            # Prop ownership check if Bible props exist
            if in_scope and registered_prop_names and matched_char is not None:
                ch_name_low = str(_get_attr(matched_char, "name", "") or "").strip().lower()
                for pname_low, prop_obj in registered_prop_names.items():
                    if pname_low in scene_text_lower:
                        owner_low = str(prop_obj.get("owner_character") or "").strip().lower()
                        if owner_low and "ensemble" not in owner_low and "world" not in owner_low and ch_name_low:
                            if ch_name_low not in owner_low and owner_low not in scene_text_lower:
                                add_finding(
                                    "world_props_lighting",
                                    "HIGH",
                                    f"Prop Ownership Handoff Unexplained: '{prop_obj.get('name')}'",
                                    (
                                        f"Scene #{sc_num} references '{prop_obj.get('name')}' (owned by '{prop_obj.get('owner_character')}') "
                                        f"without the owner present in the scene beat."
                                    ),
                                    "Include the prop owner in the scene goal or document a narrative prop transfer.",
                                    scene=sc,
                                )

            # Shot-level optical, jitter, face-drift, transition, and override checks
            if in_scope and not sc_shots:
                add_finding(
                    "optical_spatial",
                    "CRITICAL",
                    f"Scene #{sc_num} Has Zero Shots",
                    f"Scene #{sc_num} ({slugline}) has no optical shot breakdown.",
                    "Run Auto-Split or add at least one configured shot in Scene Detail Drawer.",
                    scene=sc,
                )

            if in_scope:
                prev_shot_light: str | None = None
                for sh in sc_shots:
                    cam = str(_get_attr(sh, "camera_code", "") or "").strip()
                    lens = str(_get_attr(sh, "lens_code", "") or "").strip()
                    comp = str(_get_attr(sh, "comp_code", "") or "").strip()
                    light = str(_get_attr(sh, "light_code", "") or "").strip()
                    act = str(_get_attr(sh, "act_code", "") or "").strip()
                    speed = str(_get_attr(sh, "speed_code", "") or "").strip()
                    transition = str(_get_attr(sh, "transition_type", "NONE") or "NONE").upper().strip()
                    dialogue = str(_get_attr(sh, "dialogue", "") or "").strip()
                    layers = _get_attr(sh, "fg_bg_layers", None)
                    layers = layers if isinstance(layers, dict) else {}

                    invalid_codes = []
                    if cam not in _VALID_CAM_CODES:
                        invalid_codes.append(f"camera_code={cam!r}")
                    if lens not in _VALID_LENS_CODES:
                        invalid_codes.append(f"lens_code={lens!r}")
                    if comp not in _VALID_COMP_CODES:
                        invalid_codes.append(f"comp_code={comp!r}")
                    if light not in _VALID_LIGHT_CODES:
                        invalid_codes.append(f"light_code={light!r}")
                    if act not in _VALID_ACT_CODES:
                        invalid_codes.append(f"act_code={act!r}")
                    if speed not in _VALID_SPEED_CODES:
                        invalid_codes.append(f"speed_code={speed!r}")

                    if invalid_codes:
                        add_finding(
                            "optical_spatial",
                            "CRITICAL",
                            f"Invalid Matrix Code in Scene #{sc_num} Shot #{_get_attr(sh, 'shot_number', '?')}",
                            f"Non-canonical optical code(s): {', '.join(invalid_codes)}.",
                            "Replace with canonical codes from the 7-layer studio catalog.",
                            scene=sc,
                            shot=sh,
                        )

                    if speed in _TEMPORAL_JITTER_SPEEDS or cam in _TEMPORAL_JITTER_CAMS:
                        add_finding(
                            "optical_spatial",
                            "MEDIUM",
                            f"Temporal Jitter Risk ({cam} / {speed})",
                            (
                                f"Scene #{sc_num} Shot #{_get_attr(sh, 'shot_number', '?')} combines high-motion "
                                f"parameters ({cam}, {speed}) which increase optical flow jitter."
                            ),
                            "Stabilize camera movement or anchor with #Speed 02/#Speed 03 unless kinetic action is intentional.",
                            scene=sc,
                            shot=sh,
                        )

                    if cam in _FACE_DRIFT_CAMS and matched_char is not None:
                        ch_id = _get_attr(matched_char, "id", None)
                        if not char_has_visual_ref.get(ch_id, False):
                            add_finding(
                                "character_dna_states",
                                "HIGH",
                                f"Facial Consistency Risk on {cam} Without Ref Anchor",
                                (
                                    f"Scene #{sc_num} Shot #{_get_attr(sh, 'shot_number', '?')} uses {cam} "
                                    f"while lead character lacks rendered/uploaded close-up or front sheet."
                                ),
                                "Attach Character Card 1 (Close-Up) & Card 3 (Front) before video generation.",
                                scene=sc,
                                shot=sh,
                            )

                    if prev_shot_light and light in _VALID_LIGHT_CODES and prev_shot_light != light:
                        if _lighting_bucket(prev_shot_light) != _lighting_bucket(light):
                            add_finding(
                                "world_props_lighting",
                                "MEDIUM",
                                f"Intra-Scene Lighting Jump in Scene #{sc_num}",
                                f"Shot #{_get_attr(sh, 'shot_number', '?')} switches from {prev_shot_light} to {light} mid-scene.",
                                "Keep motivated key lighting consistent across consecutive shots in the same scene.",
                                scene=sc,
                                shot=sh,
                            )
                    if light in _VALID_LIGHT_CODES:
                        prev_shot_light = light

                    if dialogue and transition not in ("J_CUT", "L_CUT", "HARD_CUT"):
                        add_finding(
                            "optical_spatial",
                            "MEDIUM",
                            f"Abrupt Audio Boundary in Scene #{sc_num} Shot #{_get_attr(sh, 'shot_number', '?')}",
                            "Spoken dialogue shot has transition_type='NONE', risking abrupt audio clipping.",
                            "Assign J_CUT, L_CUT, or HARD_CUT via Dialogue Calibrator or Director Advisor.",
                            scene=sc,
                            shot=sh,
                        )

                    neg_ovr = str(layers.get("negative_prompt_override") or "").strip()
                    if neg_ovr:
                        san = sanitize_negative_prompts_for_style([neg_ovr], style_code)
                        if ", ".join(san).strip().lower() != ", ".join(t.strip() for t in neg_ovr.split(",") if t.strip()).lower():
                            add_finding(
                                "rules_invariants",
                                "HIGH",
                                f"Shot Negative Override Conflicts with {style_code}",
                                f"Shot #{_get_attr(sh, 'shot_number', '?')} negative override '{neg_ovr}' conflicts with {style_family}.",
                                "Sanitize or clear style-contradicting tokens on the shot override.",
                                scene=sc,
                                shot=sh,
                            )

        pillar_scores = {
            key: int(max(0, min(100, 100 - deduction)))
            for key, deduction in pillar_deductions.items()
        }
        continuity_score = round(sum(pillar_scores.values()) / 4.0, 1)

        critical_count = sum(1 for f in findings if f["severity"] == "CRITICAL")
        high_count = sum(1 for f in findings if f["severity"] == "HIGH")
        medium_count = sum(1 for f in findings if f["severity"] == "MEDIUM")
        low_count = sum(1 for f in findings if f["severity"] == "LOW")

        if strict_mode:
            if critical_count > 0 or high_count > 0:
                gate_status = "FAIL"
            elif medium_count > 0:
                gate_status = "WARN"
            else:
                gate_status = "PASS"
        else:
            if critical_count > 0:
                gate_status = "FAIL"
            elif high_count > 0:
                gate_status = "WARN"
            else:
                gate_status = "PASS"

        return {
            "project_id": project_id,
            "style_code": style_code,
            "style_family": style_family,
            "strict_mode": strict_mode,
            "continuity_score": continuity_score,
            "gate_status": gate_status,
            "summary": {
                "scenes_audited": len(target_scenes),
                "shots_audited": audited_shots_count,
                "critical_count": critical_count,
                "high_count": high_count,
                "medium_count": medium_count,
                "low_count": low_count,
            },
            "pillar_scores": pillar_scores,
            "findings": findings,
        }
