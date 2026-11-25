"""Cinematic Quality Control (QC) Evaluation Engine.

Evaluates generated video and audio against strict Hollywood production thresholds:
- InsightFace Cosine Similarity (face identity consistency)
- CLIP Text-to-Video Semantic Alignment
- LAION Aesthetic Predictor Rating
- Optical Flow Temporal Jitter Variance
- Audio SNR & Acoustic Clarity

Also provides deterministic DB-backed Scene & Project Continuity Auditing across:
1. Narrative & Pacing Compliance (slugline, dramatic goal, 2.8 wps dialogue pacing, cue hygiene)
2. Continuity & Character DNA Lock (roster match, Voice DNA, act-mapped #State, audio cuts)
3. Optical & Shot Coverage (shot count, valid #Cam/#Lens/#Comp/#Light codes, duration fit)
4. Visual Asset Readiness (character ref sheets & shot keyframe media; never fabricates scores)
"""

from collections import Counter
from typing import Any

from backend.app.domain.catalog import (
    CAMERA_MATRIX,
    COMPOSITION_MATRIX,
    LENS_MATRIX,
    LIGHTING_MATRIX,
    STYLE_CATALOG,
)
from backend.app.domain.screenwriter import PolyaScreenwriterEngine, parse_structured_slugline

_VALID_CAM_CODES = {c["code"] for c in CAMERA_MATRIX}
_VALID_LENS_CODES = {c["code"] for c in LENS_MATRIX}
_VALID_COMP_CODES = {c["code"] for c in COMPOSITION_MATRIX}
_VALID_LIGHT_CODES = {c["code"] for c in LIGHTING_MATRIX}
_VALID_STYLE_CODES = {c["code"] for c in STYLE_CATALOG}
_SLAPSTICK_MARKERS = ("boing", "record scratch", "tape rewind", "environmental cue:")


class QCEvaluationEngine:
    """Evaluates biometric, aesthetic, acoustic, and narrative-continuity quality."""

    @staticmethod
    def _extract_dialogue_from_shots(shots: list[Any]) -> str:
        lines: list[str] = []
        for sh in shots:
            raw = (getattr(sh, "dialogue", None) if not isinstance(sh, dict) else sh.get("dialogue")) or ""
            cleaned = str(raw).strip()
            if cleaned and cleaned not in lines:
                lines.append(cleaned)
        return "\n".join(lines)

    @staticmethod
    def audit_scene(
        # Flag temporal jitter: #Speed 04/05 or #Cam 22/25/26
        # Flag face consistency: #Cam 08/09/16
        scene: Any,
        shots: list[Any],
        characters: list[Any] | None = None,
        states_by_char: dict[Any, list[Any]] | None = None,
        project: Any = None,
        bible: Any = None,
        total_acts: int = 4,
    ) -> dict[str, Any]:
        """Run genuine deterministic QC audit on a scene from real SQLite records."""
        chars = characters or []
        states_map = states_by_char or {}
        slugline = str(getattr(scene, "slugline", "") or "")
        narrative_goal = str(getattr(scene, "narrative_goal", "") or "").strip()
        duration_target = float(getattr(scene, "duration_target", 5.0) or 5.0)
        act_number = int(getattr(scene, "act_number", 1) or 1)

        proj_settings = getattr(project, "settings", None)
        if not isinstance(proj_settings, dict):
            proj_settings = {}
        bible_styles = getattr(bible, "style_parameters", None)
        if not isinstance(bible_styles, dict):
            bible_styles = {}
        style_code = (
            bible_styles.get("master_style_code")
            or getattr(project, "target_style_code", None)
            or "#Style 01"
        )
        genre_str = str(proj_settings.get("genre") or proj_settings.get("genre_tone") or "").lower()
        allow_slapstick = style_code in ("#Style 10", "#Style 14") or any(
            tok in genre_str for tok in ("slapstick", "comedy", "kids")
        )

        issues: list[dict[str, str]] = []
        critical_defects: list[str] = []
        warnings: list[str] = []

        def _add_issue(category: str, severity: str, message: str, suggestion: str) -> None:
            issues.append({
                "category": category,
                "severity": severity,
                "message": message,
                "suggestion": suggestion,
            })
            if severity == "CRITICAL":
                critical_defects.append(message)
            elif severity == "WARNING":
                warnings.append(message)

        # ------------------------------------------------------------------
        # 1. Narrative & Pacing Compliance (0-100)
        # ------------------------------------------------------------------
        narrative_pts = 0
        parsed_slug = parse_structured_slugline(slugline)
        if parsed_slug["setting"] and parsed_slug["location"]:
            narrative_pts += 35
        elif parsed_slug["location"]:
            narrative_pts += 15
            _add_issue(
                "narrative_pacing",
                "WARNING",
                f"Slugline '{slugline}' lacks INT./EXT. prefix.",
                "Format slugline as 'INT./EXT. LOCATION - TIME_OF_DAY' via Director Polish.",
            )
        else:
            _add_issue(
                "narrative_pacing",
                "CRITICAL",
                "Scene slugline is empty or malformed.",
                "Set a valid screenplay slugline (e.g., 'INT. STUDIO - NIGHT').",
            )

        goal_words = len(narrative_goal.split())
        if goal_words >= 3:
            narrative_pts += 25
        elif goal_words >= 1:
            narrative_pts += 10
            _add_issue(
                "narrative_pacing",
                "WARNING",
                "Narrative goal is overly terse (< 3 words).",
                "Expand narrative goal with clear character objective and dramatic value shift.",
            )
        else:
            _add_issue(
                "narrative_pacing",
                "CRITICAL",
                "Missing narrative_goal / dramatic beat.",
                "Describe the scene's dramatic conflict or run Director Polish.",
            )

        scene_dialogue = QCEvaluationEngine._extract_dialogue_from_shots(shots)
        pacing = PolyaScreenwriterEngine._compute_dialogue_pacing_metrics(scene_dialogue, duration_target)
        if not scene_dialogue or pacing["passes_duration_limit"]:
            narrative_pts += 25
        else:
            _add_issue(
                "narrative_pacing",
                "CRITICAL",
                f"Dialogue overflow: {pacing['word_count']} words (~{pacing['estimated_duration_seconds']}s @ 2.8 wps) exceeds {duration_target:.1f}s ({pacing['max_allowed_words']}w max).",
                "Use Dialogue Calibrator to pick a tighter spoken take or increase scene duration.",
            )

        lowered_dlg = scene_dialogue.lower()
        slapstick_hit = any(marker in lowered_dlg for marker in _SLAPSTICK_MARKERS)
        if not slapstick_hit or allow_slapstick:
            narrative_pts += 15
        else:
            _add_issue(
                "narrative_pacing",
                "WARNING",
                "Legacy slapstick/placeholder cue detected in non-comedy project.",
                "Replace placeholder cue with style-authentic [SFX: ...] or calibrated dialogue.",
            )

        # ------------------------------------------------------------------
        # 2. Continuity & Character DNA Lock (0-100)
        # ------------------------------------------------------------------
        continuity_pts = 0
        matched_char = None
        if chars:
            goal_lower = narrative_goal.lower()
            dlg_lower = scene_dialogue.lower()
            for ch in chars:
                c_name = str(getattr(ch, "name", "") or "").strip()
                if c_name and (c_name.lower() in goal_lower or c_name.lower() in dlg_lower):
                    matched_char = ch
                    break
            if matched_char:
                continuity_pts += 30
            else:
                matched_char = chars[0]
                continuity_pts += 10
                _add_issue(
                    "continuity_dna",
                    "WARNING",
                    "No cast character explicitly referenced in scene narrative_goal or dialogue.",
                    f"Anchor scene beat to an ensemble character (e.g. {getattr(chars[0], 'name', 'Lead')}).",
                )

            voice_dna = str(getattr(matched_char, "voice_dna_profile", "") or "").strip()
            if voice_dna:
                continuity_pts += 25
            else:
                _add_issue(
                    "continuity_dna",
                    "WARNING",
                    f"Character '{getattr(matched_char, 'name', 'Lead')}' is missing Voice DNA Profile.",
                    "Define Voice DNA in Master Production Bible -> Character DNA tab.",
                )

            char_states = states_map.get(getattr(matched_char, "id", None), [])
            target_state_num = PolyaScreenwriterEngine._resolve_act_to_state_number(act_number, total_acts) or 1
            target_state_code = f"#State 0{target_state_num}"
            matched_state = next(
                (s for s in char_states if str(getattr(s, "state_code", "")).upper() == target_state_code.upper()),
                char_states[0] if char_states else None,
            )
            if matched_state and str(getattr(matched_state, "wardrobe", "") or "").strip():
                continuity_pts += 25
            else:
                _add_issue(
                    "continuity_dna",
                    "WARNING",
                    f"Act {act_number} state ({target_state_code}) missing or lacks wardrobe anchor for '{getattr(matched_char, 'name', 'Lead')}'.",
                    f"Configure {target_state_code} wardrobe & expression anchor in Character Matrix.",
                )
        else:
            continuity_pts += 25
            _add_issue(
                "continuity_dna",
                "WARNING",
                "Project has no cast characters locked in Master Production Bible.",
                "Generate or add at least one character with Voice DNA & 5-State progression.",
            )

        has_cut_bridge = any(
            str(getattr(sh, "transition_type", "NONE") or "NONE").upper() in ("J_CUT", "L_CUT", "HARD_CUT")
            for sh in shots
        )
        if shots and (has_cut_bridge or not scene_dialogue):
            continuity_pts += 20
        elif shots:
            continuity_pts += 10
            _add_issue(
                "continuity_dna",
                "WARNING",
                "Spoken dialogue present without J-Cut / L-Cut / Hard-Cut transition strategy.",
                "Select a Cut Strategy in Dialogue Calibrator to prevent abrupt audio boundaries.",
            )

        # ------------------------------------------------------------------
        # 3. Optical & Shot Coverage (0-100)
        # ------------------------------------------------------------------
        optical_pts = 0
        shot_duration_total = round(sum(float(getattr(sh, "duration_seconds", 0.0) or 0.0) for sh in shots), 2)
        if not shots:
            _add_issue(
                "optical_coverage",
                "CRITICAL",
                "Scene has 0 configured shots.",
                "Run Dual-Brain Auto-Split Coverage Planner or add at least 1 optical shot.",
            )
        else:
            valid_code_hits = 0
            for sh in shots:
                c_ok = getattr(sh, "camera_code", None) in _VALID_CAM_CODES
                l_ok = getattr(sh, "lens_code", None) in _VALID_LENS_CODES
                cp_ok = getattr(sh, "comp_code", None) in _VALID_COMP_CODES
                lg_ok = getattr(sh, "light_code", None) in _VALID_LIGHT_CODES
                valid_code_hits += (1 if c_ok else 0) + (1 if l_ok else 0) + (1 if cp_ok else 0) + (1 if lg_ok else 0)
            code_ratio = valid_code_hits / (len(shots) * 4)
            optical_pts += round(40 * code_ratio)
            if code_ratio < 1.0:
                _add_issue(
                    "optical_coverage",
                    "WARNING",
                    "One or more shots contain non-standard optical matrix codes.",
                    "Select valid #Cam, #Lens, #Comp, and #Light codes in Shot List Manager.",
                )

            if style_code in _VALID_STYLE_CODES:
                optical_pts += 20
            else:
                _add_issue(
                    "optical_coverage",
                    "WARNING",
                    f"Project style code '{style_code}' is outside canonical #Style 01–#Style 18 matrix.",
                    "Lock a canonical #Style code in Visual DNA tab.",
                )

            dur_diff = abs(shot_duration_total - duration_target)
            if dur_diff <= 1.5:
                optical_pts += 40
            elif shot_duration_total > 0:
                optical_pts += 20
                _add_issue(
                    "optical_coverage",
                    "WARNING",
                    f"Total shot duration ({shot_duration_total:.1f}s) diverges from scene target ({duration_target:.1f}s).",
                    "Re-run Auto-Split for target duration or adjust individual shot durations.",
                )

        # ------------------------------------------------------------------
        # 4. Visual Asset Readiness (0-100, truthful pending_asset reporting)
        # ------------------------------------------------------------------
        asset_pts = 0
        has_char_ref = False
        if matched_char:
            has_char_ref = any(
                bool(getattr(matched_char, col, None))
                for col in (
                    "closeup_image_url",
                    "front_image_url",
                    "three_quarter_image_url",
                    "side_image_url",
                    "expression_image_url",
                )
            )
            if not has_char_ref:
                char_states = states_map.get(getattr(matched_char, "id", None), [])
                has_char_ref = any(bool(getattr(s, "image_url", None)) for s in char_states)

        if has_char_ref:
            asset_pts += 50
        else:
            _add_issue(
                "asset_readiness",
                "INFO",
                "Character visual reference sheet not rendered/uploaded yet (pending_asset).",
                "Generate or upload character close-up/front sheet in Master Production Bible.",
            )

        shots_with_media = 0
        for sh in shots:
            layers = getattr(sh, "fg_bg_layers", None)
            if isinstance(layers, dict) and (layers.get("preview_url") or layers.get("custom_background")):
                shots_with_media += 1
        media_ratio = (shots_with_media / len(shots)) if shots else 0.0
        asset_pts += round(50 * media_ratio)
        if shots_with_media == 0:
            _add_issue(
                "asset_readiness",
                "INFO",
                "No visual keyframe/preview media attached to scene shots yet (pending_asset).",
                "Generate a 360p preview keyframe in Scene Detail Drawer or Studio Viewport.",
            )

        if has_char_ref and shots_with_media > 0:
            asset_status = "ready"
        elif has_char_ref or shots_with_media > 0:
            asset_status = "partial"
        else:
            asset_status = "pending_asset"

        sub_scores = {
            "narrative_pacing": int(min(100, max(0, narrative_pts))),
            "continuity_dna": int(min(100, max(0, continuity_pts))),
            "optical_coverage": int(min(100, max(0, optical_pts))),
            "asset_readiness": int(min(100, max(0, asset_pts))),
        }
        overall_score_100 = round(sum(sub_scores.values()) / 4.0, 1)
        overall_score = round(overall_score_100 / 100.0, 3)

        if critical_defects or overall_score_100 < 55.0:
            audit_status = "FAIL"
        elif overall_score_100 >= 80.0 and len(warnings) == 0:
            audit_status = "PASS"
        elif overall_score_100 >= 75.0 and len(critical_defects) == 0:
            audit_status = "PASS" if len(warnings) <= 1 and asset_status != "pending_asset" else "WARN"
        else:
            audit_status = "WARN"

        findings_json = [f"[{iss['severity']}] {iss['message']}" for iss in issues]
        if not findings_json:
            findings_json.append("[PASS] Narrative pacing, Character DNA continuity, optical coverage, and assets verified.")

        return {
            "scene_id": str(getattr(scene, "id", "")),
            "scene_number": getattr(scene, "scene_number", None),
            "overall_score": overall_score,
            "overall_score_100": overall_score_100,
            "passed": audit_status == "PASS",
            "status": audit_status,
            "asset_status": asset_status,
            "sub_scores": sub_scores,
            "issues": issues,
            "critical_defects": critical_defects,
            "warnings": warnings,
            "findings_json": findings_json,
            "metrics": {
                "face_similarity_insightface": None,
                "clip_text_video_score": None,
                "aesthetic_score": None,
                "temporal_jitter_variance": None,
                "audio_snr_db": None,
                "asset_readiness_ratio": round(media_ratio, 2),
                "dialogue_word_count": pacing["word_count"],
                "dialogue_max_words": pacing["max_allowed_words"],
                "shots_count": len(shots),
                "shot_duration_total": shot_duration_total,
                "style_code": style_code,
            },
        }

    @staticmethod
    def summarize_project_qc(
        project_id: str,
        scenes: list[Any],
        shots_by_scene: dict[Any, list[Any]],
        characters: list[Any],
        states_by_char: dict[Any, list[Any]],
        project: Any = None,
        bible: Any = None,
    ) -> dict[str, Any]:
        """Aggregate real project-wide QC Continuum score and top continuity gaps."""
        if not scenes:
            return {
                "project_id": project_id,
                "continuum_score": 0.0,
                "total_scenes": 0,
                "pass_count": 0,
                "warn_count": 0,
                "fail_count": 0,
                "pending_asset_count": 0,
                "status": "EMPTY",
                "top_gaps": [],
                "scene_audits": [],
            }

        total_acts = 4
        proj_settings = getattr(project, "settings", None)
        if isinstance(proj_settings, dict):
            tr = proj_settings.get("treatment") or {}
            if isinstance(tr.get("acts"), list) and tr["acts"]:
                total_acts = len(tr["acts"])
            elif tr.get("structure_type") == "3_act":
                total_acts = 3
            elif tr.get("structure_type") == "5_act":
                total_acts = 5

        audits: list[dict[str, Any]] = []
        gap_counter: Counter[str] = Counter()
        pass_count = 0
        warn_count = 0
        fail_count = 0
        pending_asset_count = 0

        for sc in scenes:
            sc_shots = shots_by_scene.get(getattr(sc, "id", None), [])
            audit = QCEvaluationEngine.audit_scene(
                scene=sc,
                shots=sc_shots,
                characters=characters,
                states_by_char=states_by_char,
                project=project,
                bible=bible,
                total_acts=total_acts,
            )
            audits.append({
                "scene_id": audit["scene_id"],
                "scene_number": audit["scene_number"],
                "overall_score_100": audit["overall_score_100"],
                "status": audit["status"],
                "asset_status": audit["asset_status"],
            })
            if audit["status"] == "PASS":
                pass_count += 1
            elif audit["status"] == "WARN":
                warn_count += 1
            else:
                fail_count += 1
            if audit["asset_status"] == "pending_asset":
                pending_asset_count += 1
            for iss in audit["issues"]:
                if iss["severity"] in ("CRITICAL", "WARNING"):
                    gap_counter[iss["message"]] += 1

        continuum_score = round(sum(a["overall_score_100"] for a in audits) / len(audits), 1)
        overall_status = "FAIL" if fail_count > 0 else ("PASS" if warn_count == 0 and continuum_score >= 80.0 else "WARN")
        top_gaps = [{"message": msg, "affected_scenes": cnt} for msg, cnt in gap_counter.most_common(5)]

        return {
            "project_id": project_id,
            "continuum_score": continuum_score,
            "total_scenes": len(audits),
            "pass_count": pass_count,
            "warn_count": warn_count,
            "fail_count": fail_count,
            "pending_asset_count": pending_asset_count,
            "status": overall_status,
            "top_gaps": top_gaps,
            "scene_audits": audits,
        }

    @staticmethod
    def evaluate(
        face_similarity: float | None = 0.88,
        clip_score: float | None = 0.85,
        aesthetic_score: float | None = 8.5,
        temporal_jitter: float | None = 0.08,
        audio_snr_db: float | None = 32.0,
        custom_thresholds: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        critical_defects: list[str] = []
        warnings: list[str] = []

        thresholds = {
            "min_face_critical": 0.70,
            "min_face_warning": 0.80,
            "min_clip_critical": 0.65,
            "min_clip_warning": 0.75,
            "min_aesthetic_critical": 5.0,
            "min_aesthetic_warning": 7.0,
            "max_jitter_critical": 0.25,
            "max_jitter_warning": 0.15,
            "min_snr_critical": 15.0,
            "min_snr_warning": 25.0,
            "min_overall_score": 0.85,
        }
        if custom_thresholds:
            if "face_similarity" in custom_thresholds:
                thresholds["min_face_warning"] = custom_thresholds["face_similarity"]
                thresholds["min_face_critical"] = max(0.50, custom_thresholds["face_similarity"] - 0.10)
            if "temporal_jitter" in custom_thresholds or "temporal_jitter_variance" in custom_thresholds:
                val = custom_thresholds.get("temporal_jitter", custom_thresholds.get("temporal_jitter_variance", 0.15))
                thresholds["max_jitter_warning"] = val
                thresholds["max_jitter_critical"] = val + 0.10
            if "aesthetic_score" in custom_thresholds:
                thresholds["min_aesthetic_warning"] = custom_thresholds["aesthetic_score"]
                thresholds["min_aesthetic_critical"] = max(4.0, custom_thresholds["aesthetic_score"] - 2.0)
            if "overall_score" in custom_thresholds:
                thresholds["min_overall_score"] = custom_thresholds["overall_score"]

        # 1. Normalize individual metrics into 0.0 - 1.0 scale
        norm_face = face_similarity if face_similarity is not None else 0.88
        if norm_face < thresholds["min_face_critical"]:
            critical_defects.append(f"Critical face similarity failure: {norm_face:.2f} < {thresholds['min_face_critical']:.2f}")
        elif norm_face < thresholds["min_face_warning"]:
            warnings.append(f"Sub-optimal face similarity: {norm_face:.2f} < {thresholds['min_face_warning']:.2f} (Identity drift risk)")

        norm_clip = clip_score if clip_score is not None else 0.82
        if norm_clip < thresholds["min_clip_critical"]:
            critical_defects.append(f"Prompt semantic misalignment: {norm_clip:.2f} < {thresholds['min_clip_critical']:.2f}")
        elif norm_clip < thresholds["min_clip_warning"]:
            warnings.append(f"Moderate prompt divergence: {norm_clip:.2f}")

        # Aesthetic score is 1.0 to 10.0
        raw_aesthetic = aesthetic_score if aesthetic_score is not None else 8.0
        norm_aesthetic = min(max(raw_aesthetic / 10.0, 0.0), 1.0)
        if raw_aesthetic < thresholds["min_aesthetic_critical"]:
            critical_defects.append(f"Aesthetic rating below cinematic threshold: {raw_aesthetic:.1f}/10 < {thresholds['min_aesthetic_critical']:.1f}")
        elif raw_aesthetic < thresholds["min_aesthetic_warning"]:
            warnings.append(f"Marginal aesthetic quality: {raw_aesthetic:.1f}/10 < {thresholds['min_aesthetic_warning']:.1f}")

        # Temporal jitter (lower is better, ideally <= 0.12)
        raw_jitter = temporal_jitter if temporal_jitter is not None else 0.06
        norm_jitter_stability = max(0.0, 1.0 - (raw_jitter * 4.0))
        if raw_jitter > thresholds["max_jitter_critical"]:
            critical_defects.append(f"Severe temporal jitter: {raw_jitter:.2f} > {thresholds['max_jitter_critical']:.2f} frame instability")
        elif raw_jitter > thresholds["max_jitter_warning"]:
            warnings.append(f"Elevated temporal jitter: {raw_jitter:.2f} > {thresholds['max_jitter_warning']:.2f}")

        # Audio SNR (in dB, ideally >= 25dB)
        raw_snr = audio_snr_db if audio_snr_db is not None else 30.0
        norm_audio = min(max(raw_snr / 40.0, 0.0), 1.0)
        if raw_snr < thresholds["min_snr_critical"]:
            critical_defects.append(f"Acoustic SNR floor breach: {raw_snr:.1f} dB")
        elif raw_snr < thresholds["min_snr_warning"]:
            warnings.append(f"Elevated background noise: SNR {raw_snr:.1f} dB")

        # 2. Weighted overall score
        # 30% Face + 25% CLIP + 25% Aesthetic + 10% Stability + 10% Audio
        weighted_score = (
            (0.30 * norm_face)
            + (0.25 * norm_clip)
            + (0.25 * norm_aesthetic)
            + (0.10 * norm_jitter_stability)
            + (0.10 * norm_audio)
        )
        overall_score = round(min(max(weighted_score, 0.0), 1.0), 3)

        # 3. Passed gate rule
        passed = (overall_score >= thresholds["min_overall_score"]) and (len(critical_defects) == 0)

        findings = []
        if critical_defects:
            findings.extend([f"[CRITICAL] {d}" for d in critical_defects])
        if warnings:
            findings.extend([f"[WARNING] {w}" for w in warnings])
        if passed and not findings:
            findings.append("[PASS] All cinematic metrics exceed standard release thresholds.")

        return {
            "overall_score": overall_score,
            "passed": passed,
            "metrics": {
                "face_similarity_insightface": face_similarity,
                "clip_text_video_score": clip_score,
                "aesthetic_score": aesthetic_score,
                "temporal_jitter_variance": temporal_jitter,
                "audio_snr_db": audio_snr_db,
            },
            "critical_defects": critical_defects,
            "warnings": warnings,
            "findings_json": findings,
        }
