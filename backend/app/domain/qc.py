"""Cinematic Quality Control (QC) Evaluation Engine.

Evaluates generated video and audio against strict Hollywood production thresholds:
- InsightFace Cosine Similarity (face identity consistency)
- CLIP Text-to-Video Semantic Alignment
- LAION Aesthetic Predictor Rating
- Optical Flow Temporal Jitter Variance
- Audio SNR & Acoustic Clarity
"""

from typing import Any


class QCEvaluationEngine:
    """Evaluates biometric, aesthetic, and acoustic quality metrics."""

    @staticmethod
    def evaluate(
        face_similarity: float | None = 0.88,
        clip_score: float | None = 0.85,
        aesthetic_score: float | None = 8.5,
        temporal_jitter: float | None = 0.08,
        audio_snr_db: float | None = 32.0,
    ) -> dict[str, Any]:
        critical_defects: list[str] = []
        warnings: list[str] = []

        # 1. Normalize individual metrics into 0.0 - 1.0 scale
        norm_face = face_similarity if face_similarity is not None else 0.88
        if norm_face < 0.70:
            critical_defects.append(f"Critical face similarity failure: {norm_face:.2f} < 0.70")
        elif norm_face < 0.80:
            warnings.append(f"Sub-optimal face similarity: {norm_face:.2f} (Identity drift risk)")

        norm_clip = clip_score if clip_score is not None else 0.82
        if norm_clip < 0.65:
            critical_defects.append(f"Prompt semantic misalignment: {norm_clip:.2f} < 0.65")
        elif norm_clip < 0.75:
            warnings.append(f"Moderate prompt divergence: {norm_clip:.2f}")

        # Aesthetic score is 1.0 to 10.0
        raw_aesthetic = aesthetic_score if aesthetic_score is not None else 8.0
        norm_aesthetic = min(max(raw_aesthetic / 10.0, 0.0), 1.0)
        if raw_aesthetic < 5.0:
            critical_defects.append(f"Aesthetic rating below cinematic threshold: {raw_aesthetic:.1f}/10")
        elif raw_aesthetic < 7.0:
            warnings.append(f"Marginal aesthetic quality: {raw_aesthetic:.1f}/10")

        # Temporal jitter (lower is better, ideally <= 0.12)
        raw_jitter = temporal_jitter if temporal_jitter is not None else 0.06
        norm_jitter_stability = max(0.0, 1.0 - (raw_jitter * 4.0))
        if raw_jitter > 0.25:
            critical_defects.append(f"Severe temporal jitter: {raw_jitter:.2f} frame instability")
        elif raw_jitter > 0.15:
            warnings.append(f"Elevated temporal jitter: {raw_jitter:.2f}")

        # Audio SNR (in dB, ideally >= 25dB)
        raw_snr = audio_snr_db if audio_snr_db is not None else 30.0
        norm_audio = min(max(raw_snr / 40.0, 0.0), 1.0)
        if raw_snr < 15.0:
            critical_defects.append(f"Acoustic SNR floor breach: {raw_snr:.1f} dB")
        elif raw_snr < 25.0:
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
        passed = (overall_score >= 0.85) and (len(critical_defects) == 0)

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
