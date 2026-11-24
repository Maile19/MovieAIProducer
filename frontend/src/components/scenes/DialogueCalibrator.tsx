"use client";

import React, { useState } from "react";
import {
  Mic,
  Volume2,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Sliders,
} from "lucide-react";
import { api, DialogueCalibrationResult } from "@/lib/api";
import { cn } from "@/lib/utils";

interface DialogueCalibratorProps {
  sceneId: string;
  initialDialogue?: string;
  durationTarget?: number;
  onCalibrationComplete?: (result: DialogueCalibrationResult) => void;
  isNonVerbal?: boolean;
}

export default function DialogueCalibrator({
  sceneId,
  initialDialogue = "",
  durationTarget = 5.0,
  onCalibrationComplete,
  isNonVerbal = false,
}: DialogueCalibratorProps) {
  const defaultNonVerbalText = "[SFX: Comical Boing, Exaggerated Gasp & Slapstick Laughter]";
  const [dialogue, setDialogue] = useState(isNonVerbal ? defaultNonVerbalText : initialDialogue);
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [calibrationData, setCalibrationData] = useState<DialogueCalibrationResult | null>(null);

  const maxSeconds = durationTarget > 0 ? durationTarget : 5.0;
  const maxWords = Math.floor(maxSeconds * 2.8);

  // Client-side real-time estimation
  const words = dialogue.trim().split(/\s+/).filter(Boolean);
  const wordCount = words.length;
  // Estimate ~0.34s per word or 140 words per minute
  const estimatedSeconds = parseFloat((wordCount * 0.34).toFixed(1));
  const isWithinLimit = isNonVerbal ? true : (wordCount <= maxWords && estimatedSeconds <= maxSeconds);

  // J/L Cut calculation (duration-proportional: >75% J_CUT, <40% HARD_CUT, else L_CUT)
  const durationRatio = maxSeconds > 0 ? estimatedSeconds / maxSeconds : 0;
  const recommendedBridge = isNonVerbal
    ? "J-CUT (-1.2s lead) / L-CUT (+1.0s trail)"
    : durationRatio > 0.75
    ? "J_CUT (1.0s lead)"
    : durationRatio < 0.4
    ? "HARD_CUT"
    : "L_CUT (0.5s trail)";

  const handleRunCalibration = async () => {
    try {
      setIsCalibrating(true);
      if (isNonVerbal) {
        const nonVerbalResult: DialogueCalibrationResult = {
          scene_id: sceneId,
          word_count: wordCount,
          syllables_count: 0,
          estimated_duration_seconds: maxSeconds,
          passes_duration_limit: true,
          passes_5s_limit: true,
          max_allowed_words: 999,
          max_seconds: maxSeconds,
          recommended_audio_bridge: "J_CUT (-1.2s) & L_CUT (+1.0s)",
          audio_lead_seconds: 1.2,
          analysis: "Non-Verbal Mode Active: Spoken dialogue rule overridden to pure SFX, vocalization, and J/L-Cut audio bridge.",
        };
        setCalibrationData(nonVerbalResult);
        onCalibrationComplete?.(nonVerbalResult);
        return;
      }
      const res = await api.scenes.calibrateDialogue(sceneId, dialogue, maxSeconds);
      if (res?.data) {
        setCalibrationData(res.data);
        onCalibrationComplete?.(res.data);
      }
    } catch (err) {
      console.error(err);
      // Fallback local calibration
      const fallback: DialogueCalibrationResult = {
        scene_id: sceneId,
        word_count: wordCount,
        syllables_count: Math.round(wordCount * 1.5),
        estimated_duration_seconds: estimatedSeconds,
        passes_duration_limit: isWithinLimit,
        passes_5s_limit: isWithinLimit,
        max_allowed_words: maxWords,
        max_seconds: maxSeconds,
        recommended_audio_bridge: durationRatio > 0.75 ? "J_CUT" : "L_CUT",
        audio_lead_seconds: durationRatio > 0.75 ? 1.0 : 0.5,
        analysis: isWithinLimit
          ? `Dialogue pacing adheres to ${maxSeconds.toFixed(1)}-second generative inference limit.`
          : `Dialogue exceeds ${maxWords} words; recommend J-cut lead-in or trim.`,
      };
      setCalibrationData(fallback);
      onCalibrationComplete?.(fallback);
    } finally {
      setIsCalibrating(false);
    }
  };

  const handleInsertSFX = (sfxTag: string) => {
    setDialogue((prev) => (prev ? `${prev} ${sfxTag}` : sfxTag));
  };

  // Generate SVG waveform bar heights based on words
  const waveformBars = [
    24, 45, 60, 80, 55, 90, 70, 35, 85, 95, 65, 40, 75, 50, 30, 85, 100, 60, 45, 20, 50, 70, 90, 60, 30,
  ];

  return (
    <div className="p-4 rounded-xl bg-panel border border-border space-y-4 font-sans text-xs">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Mic className="w-4 h-4 text-amber-500" />
          <h4 className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary">
            {isNonVerbal ? "Non-Verbal Audio Bridge & SFX Calibrator" : `${maxSeconds.toFixed(0)}-Second Dialogue Limiter & J/L-Cut Calibration`}
          </h4>
        </div>

        <span
          className={cn(
            "px-2 py-0.5 rounded text-[10px] font-mono font-bold flex items-center gap-1",
            isNonVerbal
              ? "bg-purple-500/10 text-purple-400 border border-purple-500/30"
              : isWithinLimit
              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
              : "bg-rose-500/10 text-rose-400 border border-rose-500/30"
          )}
        >
          {isNonVerbal ? (
            <>
              <Volume2 className="w-3 h-3" />
              <span>NON-VERBAL (OVERRIDE 5S RULE)</span>
            </>
          ) : isWithinLimit ? (
            <>
              <CheckCircle2 className="w-3 h-3" />
              <span>&le; {maxSeconds.toFixed(1)}s PASS</span>
            </>
          ) : (
            <>
              <AlertTriangle className="w-3 h-3" />
              <span>OVERFLOW WARNING</span>
            </>
          )}
        </span>
      </div>

      {/* Dialogue / SFX Textarea */}
      <div className="space-y-1.5 font-mono">
        <div className="flex items-center justify-between text-[11px]">
          <label className="text-obsidian-secondary font-semibold">
            {isNonVerbal ? "Slapstick SFX, Laughs & Vocalization Cues:" : "Scene Dialogue Lines:"}
          </label>
          <div className="flex items-center gap-2 text-[10px]">
            {isNonVerbal ? (
              <span className="text-purple-400 font-bold">
                J-Cut: -1.2s &bull; L-Cut: +1.0s
              </span>
            ) : (
              <>
                <span className={cn(wordCount > maxWords ? "text-rose-400 font-bold" : "text-obsidian-muted")}>
                  {wordCount}/{maxWords} Words
                </span>
                <span>&bull;</span>
                <span className={cn(estimatedSeconds > maxSeconds ? "text-rose-400 font-bold" : "text-amber-400")}>
                  ~{estimatedSeconds}s / {maxSeconds.toFixed(1)}s max
                </span>
              </>
            )}
          </div>
        </div>

        <textarea
          value={dialogue}
          onChange={(e) => setDialogue(e.target.value)}
          rows={3}
          placeholder={
            isNonVerbal
              ? "Enter slapstick sound cues, e.g. [SFX: Boing, Whistle, Gasp, Comedic Crash]..."
              : `Enter spoken dialogue lines for this ${maxSeconds.toFixed(0)}-second scene...`
          }
          className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none text-xs resize-none"
        />

        {/* Quick SFX Inserts for Non-Verbal Mode */}
        {isNonVerbal && (
          <div className="flex items-center gap-1.5 flex-wrap pt-1">
            <span className="text-[10px] text-obsidian-muted">Quick SFX:</span>
            {[
              "[SFX: Comical Boing]",
              "[SFX: Banana Slip]",
              "[Reaction: Exaggerated Gasp]",
              "[Laugh: Kids Giggle]",
              "[SFX: Punchy Whistle]",
            ].map((tag) => (
              <button
                key={tag}
                type="button"
                onClick={() => handleInsertSFX(tag)}
                className="px-2 py-0.5 rounded text-[10px] bg-canvas hover:bg-elevated text-purple-300 border border-purple-500/30 transition-colors"
              >
                {tag}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Simulated SVG Audio Waveform Visualizer */}
      <div className="p-3 rounded-lg bg-canvas border border-border/80 space-y-2">
        <div className="flex items-center justify-between text-[10px] font-mono text-obsidian-muted">
          <span className="flex items-center gap-1.5 text-obsidian-secondary">
            <Volume2 className="w-3 h-3 text-amber-500" />
            <span>Acoustic Waveform &amp; Pacing Dynamics</span>
          </span>
          <span className="text-amber-400 font-bold">
            Recommended: {calibrationData?.recommended_audio_bridge || recommendedBridge}
          </span>
        </div>

        {/* SVG Waveform Bars */}
        <div className="h-14 flex items-end justify-between gap-1 px-1 py-1 bg-black/40 rounded border border-border/40">
          {waveformBars.map((h, idx) => {
            const isOverflow = idx > (wordCount / maxWords) * 25;
            return (
              <div
                key={idx}
                className={cn(
                  "flex-1 rounded-t transition-all",
                  isOverflow
                    ? "bg-border/40"
                    : wordCount > maxWords
                    ? "bg-rose-500/80 shadow-sm"
                    : "bg-amber-500/80 shadow-sm"
                )}
                style={{ height: `${h}%` }}
              />
            );
          })}
        </div>

        {/* Timeline Marker Ticks */}
        <div className="flex justify-between text-[9px] font-mono text-obsidian-muted px-0.5">
          <span>0.0s (J-Cut Lead)</span>
          <span>{(maxSeconds * 0.25).toFixed(1)}s</span>
          <span>{(maxSeconds * 0.5).toFixed(1)}s</span>
          <span>{(maxSeconds * 0.75).toFixed(1)}s (L-Cut Trail)</span>
          <span className="text-rose-400">{maxSeconds.toFixed(1)}s Max</span>
        </div>
      </div>

      {/* Calibration Result Details & Run Button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
        <div className="text-[11px] font-mono text-obsidian-secondary">
          {calibrationData ? (
            <p className="line-clamp-1">{calibrationData.analysis}</p>
          ) : (
            <p className="text-obsidian-muted">
              Click calibrate to compute acoustic syllable pacing &amp; audio bridge cuts.
            </p>
          )}
        </div>

        <button
          type="button"
          onClick={handleRunCalibration}
          disabled={isCalibrating || !dialogue.trim()}
          className="flex items-center justify-center gap-2 px-3.5 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-xs transition-all shadow-glow shrink-0 disabled:opacity-50"
        >
          {isCalibrating ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>Calibrating Audio...</span>
            </>
          ) : (
            <>
              <Sliders className="w-3.5 h-3.5" />
              <span>Calibrate Dialogue</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
