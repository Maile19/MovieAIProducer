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
  onCalibrationComplete?: (result: DialogueCalibrationResult) => void;
}

export default function DialogueCalibrator({
  sceneId,
  initialDialogue = "Cipher, the Syndicate perimeter has collapsed. We have less than forty seconds before neural purge.",
  onCalibrationComplete,
}: DialogueCalibratorProps) {
  const [dialogue, setDialogue] = useState(initialDialogue);
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [calibrationData, setCalibrationData] = useState<DialogueCalibrationResult | null>(null);

  // Client-side real-time estimation
  const words = dialogue.trim().split(/\s+/).filter(Boolean);
  const wordCount = words.length;
  // Estimate ~0.35s per word or 130 words per minute + padding
  const estimatedSeconds = parseFloat((wordCount * 0.34).toFixed(1));
  const isWithinLimit = wordCount <= 14 && estimatedSeconds <= 5.0;

  // J/L Cut calculation
  const recommendedBridge =
    estimatedSeconds > 3.8 ? "J_CUT (1.0s lead)" : estimatedSeconds < 2.0 ? "HARD_CUT" : "L_CUT (0.5s trail)";

  const handleRunCalibration = async () => {
    try {
      setIsCalibrating(true);
      const res = await api.scenes.calibrateDialogue(sceneId, dialogue, 5.0);
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
        passes_5s_limit: isWithinLimit,
        recommended_audio_bridge: estimatedSeconds > 3.8 ? "J_CUT" : "L_CUT",
        audio_lead_seconds: estimatedSeconds > 3.8 ? 1.0 : 0.5,
        analysis: isWithinLimit
          ? "Dialogue pacing adheres to 5.0-second generative inference limit."
          : "Dialogue exceeds 14 words; recommend J-cut lead-in or trim.",
      };
      setCalibrationData(fallback);
      onCalibrationComplete?.(fallback);
    } finally {
      setIsCalibrating(false);
    }
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
            5-Second Dialogue Limiter &amp; J/L-Cut Calibration
          </h4>
        </div>

        <span
          className={cn(
            "px-2 py-0.5 rounded text-[10px] font-mono font-bold flex items-center gap-1",
            isWithinLimit
              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
              : "bg-rose-500/10 text-rose-400 border border-rose-500/30"
          )}
        >
          {isWithinLimit ? (
            <>
              <CheckCircle2 className="w-3 h-3" />
              <span>&le; 5.0s PASS</span>
            </>
          ) : (
            <>
              <AlertTriangle className="w-3 h-3" />
              <span>OVERFLOW WARNING</span>
            </>
          )}
        </span>
      </div>

      {/* Dialogue Textarea */}
      <div className="space-y-1.5 font-mono">
        <div className="flex items-center justify-between text-[11px]">
          <label className="text-obsidian-secondary font-semibold">Scene Dialogue Lines:</label>
          <div className="flex items-center gap-2 text-[10px]">
            <span className={cn(wordCount > 14 ? "text-rose-400 font-bold" : "text-obsidian-muted")}>
              {wordCount}/14 Words
            </span>
            <span>&bull;</span>
            <span className={cn(estimatedSeconds > 5.0 ? "text-rose-400 font-bold" : "text-amber-400")}>
              ~{estimatedSeconds}s / 5.0s max
            </span>
          </div>
        </div>

        <textarea
          value={dialogue}
          onChange={(e) => setDialogue(e.target.value)}
          rows={3}
          placeholder="Enter spoken dialogue lines for this 5-second scene..."
          className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none text-xs resize-none"
        />
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
            const isOverflow = idx > (wordCount / 14) * 25;
            return (
              <div
                key={idx}
                className={cn(
                  "flex-1 rounded-t transition-all",
                  isOverflow
                    ? "bg-border/40"
                    : wordCount > 14
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
          <span>1.5s</span>
          <span>3.0s</span>
          <span>4.5s (L-Cut Trail)</span>
          <span className="text-rose-400">5.0s Max</span>
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
