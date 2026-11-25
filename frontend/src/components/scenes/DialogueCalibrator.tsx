"use client";

import React, { useEffect, useState } from "react";
import {
  Mic,
  Volume2,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Sliders,
  Sparkles,
} from "lucide-react";
import { api, DialogueCalibrationResult } from "@/lib/api";
import { cn } from "@/lib/utils";

interface DialogueCalibratorProps {
  sceneId: string;
  initialDialogue?: string | null;
  speakingCharacter?: string | null;
  durationTarget?: number;
  initialTransitionType?: string | null;
  initialAudioLead?: number | null;
  onDialogueChange?: (value: string) => void;
  onCutStrategyChange?: (transitionType: string, audioLeadSeconds: number) => void;
  onCalibrationComplete?: (result: DialogueCalibrationResult) => void;
  isNonVerbal?: boolean;
}

const DEFAULT_NON_VERBAL_TEXT = "[NON-VERBAL]";

function buildDynamicWaveformBars(text: string, wordCount: number, isNonVerbal: boolean): number[] {
  const barCount = 25;
  const trimmed = text.trim();
  if (!trimmed) {
    return Array.from({ length: barCount }, () => 12);
  }
  const baseEnergy = isNonVerbal ? 48 : Math.min(82, 22 + wordCount * 3);
  return Array.from({ length: barCount }, (_, idx) => {
    const chCode = trimmed.charCodeAt(idx % trimmed.length) || 32;
    const wave = Math.sin((idx + 1) * 0.65 + (chCode % 13)) * 22;
    return Math.max(14, Math.min(98, Math.round(baseEnergy + wave)));
  });
}

function countSpokenWords(raw: string): number {
  const spokenOnly = raw.replace(/\[[^\]]*\]|\([^)]*\)/g, " ").trim();
  if (!spokenOnly) return 0;
  return spokenOnly.split(/\s+/).filter(Boolean).length;
}

export default function DialogueCalibrator({
  sceneId,
  initialDialogue = "",
  speakingCharacter,
  durationTarget = 5.0,
  initialTransitionType = null,
  initialAudioLead = null,
  onDialogueChange,
  onCutStrategyChange,
  onCalibrationComplete,
  isNonVerbal = false,
}: DialogueCalibratorProps) {
  const resolvedInitial = isNonVerbal
    ? (initialDialogue && initialDialogue.trim() ? initialDialogue : DEFAULT_NON_VERBAL_TEXT)
    : (initialDialogue || "");
  const [dialogue, setDialogue] = useState(resolvedInitial);
  const [cutStrategy, setCutStrategy] = useState<string>(initialTransitionType || "J_CUT");
  const [audioLead, setAudioLead] = useState<number>(
    typeof initialAudioLead === "number" ? initialAudioLead : 1.0
  );
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [calibrationData, setCalibrationData] = useState<DialogueCalibrationResult | null>(null);

  // Reset calibration alternatives only when switching scenes
  useEffect(() => {
    setCalibrationData(null);
  }, [sceneId]);

  // Sync textarea whenever active scene or external dialogue prop changes
  useEffect(() => {
    const nextVal = isNonVerbal
      ? (initialDialogue && initialDialogue.trim() ? initialDialogue : DEFAULT_NON_VERBAL_TEXT)
      : (initialDialogue || "");
    setDialogue((prev) => (prev === nextVal ? prev : nextVal));
  }, [sceneId, initialDialogue, isNonVerbal]);

  // Sync cut strategy & audio lead from scene/shot state without clearing calibration results
  useEffect(() => {
    if (initialTransitionType && initialTransitionType !== "NONE") {
      setCutStrategy(initialTransitionType);
    } else {
      setCutStrategy("J_CUT");
    }
    if (typeof initialAudioLead === "number") {
      setAudioLead(initialAudioLead);
    } else {
      setAudioLead(1.0);
    }
  }, [sceneId, initialTransitionType, initialAudioLead]);

  const maxSeconds = durationTarget > 0 ? durationTarget : 5.0;
  const maxWords = Math.max(1, Math.floor(maxSeconds * 2.8));

  // Client-side real-time estimation (matches backend spoken-word counter & unified 2.8 wps pacing)
  const wordCount = countSpokenWords(dialogue);
  const estimatedSeconds = wordCount > 0 ? parseFloat((wordCount / 2.8).toFixed(2)) : 0;
  const isWithinLimit = isNonVerbal ? true : wordCount <= maxWords;

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
          transition_type: cutStrategy,
          audio_lead_seconds: 1.2,
          analysis: "Non-Verbal Mode Active: Spoken dialogue rule overridden to pure SFX, vocalization, and J/L-Cut audio bridge.",
        };
        setCalibrationData(nonVerbalResult);
        onCalibrationComplete?.(nonVerbalResult);
        return;
      }
      const res = await api.scenes.calibrateDialogue(sceneId, dialogue, maxSeconds, speakingCharacter);
      if (res?.data) {
        setCalibrationData(res.data);
        const resCut = res.data.transition_type || cutStrategy;
        const resLead = typeof res.data.audio_lead_seconds === "number" ? res.data.audio_lead_seconds : audioLead;
        setCutStrategy(resCut);
        setAudioLead(resLead);
        onCutStrategyChange?.(resCut, resLead);
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

  const updateDialogueValue = (nextValue: string) => {
    setDialogue(nextValue);
    onDialogueChange?.(nextValue);
  };

  const handleInsertSFX = (sfxTag: string) => {
    const nextValue = dialogue ? `${dialogue} ${sfxTag}` : sfxTag;
    updateDialogueValue(nextValue);
  };

  const handleSelectCutStrategy = (nextCut: string, nextLead?: number) => {
    const leadVal =
      nextLead !== undefined
        ? nextLead
        : nextCut === "HARD_CUT"
        ? 0.0
        : nextCut === "L_CUT"
        ? 0.5
        : 1.0;
    setCutStrategy(nextCut);
    setAudioLead(leadVal);
    onCutStrategyChange?.(nextCut, leadVal);
  };

  const handleUseAlternativeTake = (alt: {
    dialogue: string;
    transition_type: string;
    audio_lead_seconds: number;
  }) => {
    updateDialogueValue(alt.dialogue);
    handleSelectCutStrategy(alt.transition_type, alt.audio_lead_seconds);
  };

  // Dynamic SVG waveform bar heights reactive to dialogue/SFX text & density
  const waveformBars = buildDynamicWaveformBars(dialogue, wordCount, isNonVerbal);

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
          <div className="flex items-center gap-2">
            <label className="text-obsidian-secondary font-semibold">
              {isNonVerbal ? "Non-Verbal Audio Bridge & Atmospheric SFX Cues:" : "Scene Dialogue Lines:"}
            </label>
            {speakingCharacter && !isNonVerbal && (
              <span className="px-1.5 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 text-amber-400 text-[9px] font-bold uppercase">
                {speakingCharacter}
              </span>
            )}
          </div>
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
          onChange={(e) => updateDialogueValue(e.target.value)}
          rows={3}
          placeholder={
            isNonVerbal
              ? "Enter atmospheric cues or [NON-VERBAL], e.g. [SFX: Rising ambient tension], [SFX: Sharp breath / heartbeat]..."
              : "No Screenwriter dialogue saved for this scene yet — type dialogue or regenerate scene..."
          }
          className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none text-xs resize-none"
        />

        {/* Quick SFX Inserts for Non-Verbal Mode */}
        {isNonVerbal && (
          <div className="flex items-center gap-1.5 flex-wrap pt-1">
            <span className="text-[10px] text-obsidian-muted">Quick SFX:</span>
            {[
              "[NON-VERBAL]",
              "[SFX: Rising ambient tension]",
              "[SFX: Heavy silence / room tone]",
              "[SFX: Sharp breath / heartbeat]",
              "[SFX: Distant mechanical hum]",
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

      {/* Interactive Cut Strategy Controls (J-Cut / L-Cut / Hard-Cut + Lead Seconds) */}
      <div className="p-3 rounded-lg bg-canvas border border-border/80 flex flex-wrap items-center justify-between gap-2 text-[10px] font-mono">
        <div className="flex items-center gap-1.5">
          <span className="text-obsidian-muted uppercase font-bold">Cut Strategy:</span>
          {(["J_CUT", "L_CUT", "HARD_CUT"] as const).map((cut) => (
            <button
              key={cut}
              type="button"
              onClick={() => handleSelectCutStrategy(cut)}
              className={cn(
                "px-2 py-0.5 rounded font-bold border transition-all",
                cutStrategy === cut
                  ? "bg-amber-500 text-canvas border-amber-500 shadow-sm"
                  : "bg-panel text-obsidian-muted hover:text-obsidian-primary border-border"
              )}
            >
              {cut.replace("_", "-")}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-1.5">
          <span className="text-obsidian-muted uppercase font-bold">Lead/Trail:</span>
          <select
            value={String(audioLead)}
            onChange={(e) => handleSelectCutStrategy(cutStrategy, parseFloat(e.target.value))}
            className="px-2 py-0.5 rounded bg-panel border border-border text-amber-400 font-bold focus:outline-none focus:border-amber-500"
          >
            {[0.0, 0.5, 1.0, 1.2, 1.5].map((sec) => (
              <option key={sec} value={String(sec)}>
                {sec.toFixed(1)}s
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* 3 Selectable Spoken Alternatives from Screenwriter Calibration */}
      {calibrationData?.alternatives && calibrationData.alternatives.length > 0 && (
        <div className="space-y-2 pt-1">
          <div className="text-[10px] font-mono uppercase tracking-wider text-amber-400 font-bold flex items-center gap-1.5">
            <Sparkles className="w-3 h-3" />
            <span>3 Voice-Calibrated Spoken Takes (Click &ldquo;Use Take&rdquo;)</span>
          </div>
          <div className="grid grid-cols-1 gap-2">
            {calibrationData.alternatives.map((alt) => (
              <div
                key={alt.id}
                className="p-2.5 rounded-lg bg-canvas border border-border hover:border-amber-500/40 transition-all space-y-1.5 font-mono text-[11px]"
              >
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div className="flex items-center gap-1.5">
                    <span className="font-bold text-amber-300">{alt.label}</span>
                    <span
                      className={cn(
                        "px-1.5 py-0.2 rounded text-[9px] font-bold border",
                        alt.passes_duration_limit
                          ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                          : "bg-rose-500/15 text-rose-400 border-rose-500/30"
                      )}
                    >
                      {alt.word_count}/{alt.max_allowed_words || maxWords}w &bull; {alt.estimated_duration_seconds}s
                    </span>
                    <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-blue-500/10 text-blue-300 border border-blue-500/20">
                      {alt.transition_type}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleUseAlternativeTake(alt)}
                    className="px-2 py-0.5 rounded bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-[10px] transition-colors cursor-pointer"
                  >
                    Use Take
                  </button>
                </div>
                <p className="text-obsidian-primary font-sans text-xs italic">&ldquo;{alt.dialogue}&rdquo;</p>
                {alt.style_note && <p className="text-[10px] text-obsidian-muted">{alt.style_note}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Calibration Result Details & Run Button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
        <div className="text-[11px] font-mono text-obsidian-secondary space-y-1.5">
          {calibrationData ? (
            <>
              <p className="line-clamp-2">{calibrationData.analysis}</p>
              {calibrationData.trimmed_suggestion && (
                <div className="flex flex-wrap items-center gap-2 pt-0.5">
                  <span className="text-[10px] text-emerald-400">
                    Tighter cut: &ldquo;{calibrationData.trimmed_suggestion}&rdquo;
                  </span>
                  <button
                    type="button"
                    onClick={() => updateDialogueValue(calibrationData.trimmed_suggestion || "")}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/40 text-emerald-300 text-[10px] font-bold transition-colors"
                  >
                    <Sparkles className="w-3 h-3" />
                    <span>Apply Trimmed</span>
                  </button>
                </div>
              )}
            </>
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
