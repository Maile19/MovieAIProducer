"use client";

import React, { useState, useEffect } from "react";
import {
  Sparkles,
  Clock,
  Layers,
  Film,
  AlertTriangle,
  X,
  CheckCircle2,
  BookOpen,
  ArrowRight,
  Bot,
  Zap,
  RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import ObsidianDropdown from "@/components/ui/ObsidianDropdown";

export type DurationMode = "dynamic" | "flat_10s" | "flat_15s" | "flat_5s";
export type WriterMode = "staged_ai" | "instant_structural";

export interface BlueprintConfig {
  total_scenes: number;
  duration_mode: DurationMode;
  auto_split_shots: boolean;
  clear_existing: boolean;
  premise?: string;
  writer_mode?: WriterMode;
}

interface BlueprintModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  onRefreshScenes: () => Promise<void>;
  existingScenesCount: number;
  onGenerate?: (config: BlueprintConfig) => Promise<void>;
  presetDefaults?: Record<string, any>;
}

const SCENE_OPTIONS = [
  { count: 50, label: "50 Scenes", tier: "Short Form / Teaser", minutes: "~10 min" },
  { count: 100, label: "100 Scenes", tier: "Featurette / Episode", minutes: "~21 min" },
  { count: 200, label: "200 Scenes", tier: "Mid-Length Film", minutes: "~42 min" },
  { count: 300, label: "300 Scenes", tier: "Standard Feature", minutes: "~63 min" },
  { count: 400, label: "400 Scenes", tier: "Epic Feature Film", minutes: "~84 min" },
  { count: 420, label: "420 Scenes", tier: "Extended Feature Cut", minutes: "~88 min" },
];

const DURATION_OPTIONS: Array<{
  id: DurationMode;
  label: string;
  badge: string;
  description: string;
  avgSeconds: number;
}> = [
  {
    id: "dynamic",
    label: "Dynamic Hollywood Pacing",
    badge: "Recommended",
    description: "15s in Acts I & III (breathing room for world-building & emotional depths), 10s in Acts II & IV (accelerated rising action & climactic tension).",
    avgSeconds: 12.5,
  },
  {
    id: "flat_10s",
    label: "Flat 10 Seconds",
    badge: "Balanced Pacing",
    description: "Every scene is locked at 10.0s (2 auto-split 5s shots with alternate camera coverage).",
    avgSeconds: 10.0,
  },
  {
    id: "flat_15s",
    label: "Flat 15 Seconds",
    badge: "Slow Burn / Dramatic",
    description: "Every scene is locked at 15.0s (3 auto-split 5s shots with wide, over-shoulder, and hero close-up angles).",
    avgSeconds: 15.0,
  },
  {
    id: "flat_5s",
    label: "Flat 5 Seconds",
    badge: "Legacy Micro-Shorts",
    description: "Fast-paced single-shot 5.0s pacing matching TikTok/Reels micro-cinematics.",
    avgSeconds: 5.0,
  },
];

interface StageProgress {
  phase: "A" | "B1" | "B2" | "B3" | "B4" | "COMPLETE";
  treatmentGenerated: boolean;
  logline?: string;
  theme?: string;
  actStatuses: {
    1: "pending" | "writing" | "saved" | "error";
    2: "pending" | "writing" | "saved" | "error";
    3: "pending" | "writing" | "saved" | "error";
    4: "pending" | "writing" | "saved" | "error";
  };
  actFallbacks: {
    1: boolean;
    2: boolean;
    3: boolean;
    4: boolean;
  };
  actDetails: {
    1?: { scenes: number; shots: number; summary: string };
    2?: { scenes: number; shots: number; summary: string };
    3?: { scenes: number; shots: number; summary: string };
    4?: { scenes: number; shots: number; summary: string };
  };
  errorMsg?: string;
}

export default function BlueprintModal({
  isOpen,
  onClose,
  projectId,
  onRefreshScenes,
  existingScenesCount,
  onGenerate,
  presetDefaults,
}: BlueprintModalProps) {
  const initialScenes = presetDefaults?.total_scenes || 100;
  const initialMode: DurationMode =
    presetDefaults?.pacing?.pacing_profile === "high_retention_kids"
      ? "flat_5s"
      : (presetDefaults?.duration_mode as DurationMode) || "dynamic";

  const [selectedScenes, setSelectedScenes] = useState<number>(initialScenes);
  const [selectedMode, setSelectedMode] = useState<DurationMode>(initialMode);
  const [writerMode, setWriterMode] = useState<WriterMode>("staged_ai");
  const [premise, setPremise] = useState<string>("");
  const [autoSplitShots, setAutoSplitShots] = useState<boolean>(true);
  const [clearExisting, setClearExisting] = useState<boolean>(existingScenesCount > 0);

  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [stageProgress, setStageProgress] = useState<StageProgress | null>(null);

  // Sync preset defaults on open
  useEffect(() => {
    if (isOpen && presetDefaults) {
      if (presetDefaults.total_scenes) {
        setSelectedScenes(presetDefaults.total_scenes);
      }
      if (presetDefaults.pacing?.pacing_profile === "high_retention_kids") {
        setSelectedMode("flat_5s");
      } else if (presetDefaults.duration_mode) {
        setSelectedMode(presetDefaults.duration_mode);
      }
    }
  }, [isOpen, presetDefaults]);

  // Check existing blueprint status on modal open
  useEffect(() => {
    if (isOpen && projectId) {
      api.blueprint
        .getStatus(projectId)
        .then((res) => {
          const st = res?.data;
          if (st?.has_treatment && st.treatment) {
            const completed = st.completed_acts || [];
            const fallbacks = st.act_fallbacks || {};

            const actStatuses: StageProgress["actStatuses"] = {
              1: completed.includes(1) ? "saved" : "pending",
              2: completed.includes(2) ? "saved" : "pending",
              3: completed.includes(3) ? "saved" : "pending",
              4: completed.includes(4) ? "saved" : "pending",
            };

            const actFallbacks: StageProgress["actFallbacks"] = {
              1: !!fallbacks["1"],
              2: !!fallbacks["2"],
              3: !!fallbacks["3"],
              4: !!fallbacks["4"],
            };

            const actDetails: StageProgress["actDetails"] = {};
            for (let a = 1; a <= 4; a++) {
              if (completed.includes(a)) {
                actDetails[a as 1 | 2 | 3 | 4] = {
                  scenes: st.act_counts?.[a] || 0,
                  shots: 0,
                  summary: st.act_summaries?.[String(a)] || "",
                };
              }
            }

            const isAllComplete = completed.length === 4;
            setStageProgress({
              phase: isAllComplete ? "COMPLETE" : "B1",
              treatmentGenerated: true,
              logline: st.treatment.logline,
              theme: st.treatment.theme,
              actStatuses,
              actFallbacks,
              actDetails,
            });

            if (st.treatment.total_scenes) {
              setSelectedScenes(st.treatment.total_scenes);
            }
            if (st.treatment.duration_mode) {
              setSelectedMode(st.treatment.duration_mode as DurationMode);
            }
          }
        })
        .catch((err) => {
          console.warn("Could not check blueprint status:", err);
        });
    }
  }, [isOpen, projectId]);

  if (!isOpen) return null;

  // Live preview calculations
  const durationConfig = DURATION_OPTIONS.find((d) => d.id === selectedMode) || DURATION_OPTIONS[0];
  const totalSeconds = Math.round(selectedScenes * durationConfig.avgSeconds);
  const estMinutes = Math.floor(totalSeconds / 60);
  const estRemainingSec = totalSeconds % 60;

  let estShots = selectedScenes;
  if (autoSplitShots) {
    if (selectedMode === "dynamic") {
      estShots = Math.round(selectedScenes * 2.5);
    } else if (selectedMode === "flat_10s") {
      estShots = selectedScenes * 2;
    } else if (selectedMode === "flat_15s") {
      estShots = selectedScenes * 3;
    }
  }

  const actQuartile = Math.round(selectedScenes * 0.25);

  const handleStartGeneration = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsGenerating(true);

    if (writerMode === "instant_structural") {
      try {
        if (onGenerate) {
          await onGenerate({
            total_scenes: selectedScenes,
            duration_mode: selectedMode,
            auto_split_shots: autoSplitShots,
            clear_existing: clearExisting,
            premise,
            writer_mode: "instant_structural",
          });
        } else {
          await api.scenes.generateBlueprint(projectId, {
            total_scenes: selectedScenes,
            duration_mode: selectedMode,
            auto_split_shots: autoSplitShots,
            clear_existing: clearExisting,
          });
          await onRefreshScenes();
        }
        onClose();
      } catch (err) {
        console.error("Instant blueprint error:", err);
      } finally {
        setIsGenerating(false);
      }
      return;
    }

    // Staged AI Screenplay Writer Pipeline (Phase A -> Phase B1..B4)
    const initialProgress: StageProgress = {
      phase: "A",
      treatmentGenerated: false,
      actStatuses: {
        1: "pending",
        2: "pending",
        3: "pending",
        4: "pending",
      },
      actFallbacks: {
        1: false,
        2: false,
        3: false,
        4: false,
      },
      actDetails: {},
    };
    setStageProgress(initialProgress);

    try {
      // Step 1: Phase A - Master Story Treatment & Beat Sheet
      const treatRes = await api.blueprint.generateTreatment(projectId, {
        total_scenes: selectedScenes,
        duration_mode: selectedMode,
        premise: premise.trim(),
        clear_existing: clearExisting,
      });

      const treatData = treatRes.data;
      setStageProgress((prev) => ({
        ...(prev || initialProgress),
        treatmentGenerated: true,
        logline: treatData?.logline,
        theme: treatData?.theme,
        phase: "B1",
      }));

      // Step 2: Phase B - Act-by-Act Chunking & Persistent Context
      for (let actNum = 1; actNum <= 4; actNum++) {
        setStageProgress((prev) => {
          if (!prev) return initialProgress;
          return {
            ...prev,
            phase: actNum === 1 ? "B1" : actNum === 2 ? "B2" : actNum === 3 ? "B3" : "B4",
            actStatuses: {
              ...prev.actStatuses,
              [actNum]: "writing",
            },
          };
        });

        const actRes = await api.blueprint.generateAct(projectId, {
          act_number: actNum,
          total_scenes: selectedScenes,
          duration_mode: selectedMode,
          auto_split_shots: autoSplitShots,
        });

        const actData = actRes.data;
        const usedFallback = !!actData.used_fallback;

        setStageProgress((prev) => {
          if (!prev) return initialProgress;
          return {
            ...prev,
            actStatuses: {
              ...prev.actStatuses,
              [actNum]: "saved",
            },
            actFallbacks: {
              ...prev.actFallbacks,
              [actNum]: usedFallback,
            },
            actDetails: {
              ...prev.actDetails,
              [actNum]: {
                scenes: actData.scenes_generated,
                shots: actData.shots_generated,
                summary: actData.act_summary,
              },
            },
          };
        });

        // Incrementally refresh scenes on storyboard page
        await onRefreshScenes();
      }

      setStageProgress((prev) => (prev ? { ...prev, phase: "COMPLETE" } : null));
    } catch (err: any) {
      console.error("Staged generation error:", err);
      setStageProgress((prev) => (prev ? { ...prev, errorMsg: err?.message || "Generation error" } : null));
    } finally {
      setIsGenerating(false);
    }
  };

  // Dedicated Retry handler per Act
  const handleRetryAct = async (actNum: 1 | 2 | 3 | 4) => {
    try {
      setStageProgress((prev) => {
        if (!prev) return null;
        return {
          ...prev,
          actStatuses: {
            ...prev.actStatuses,
            [actNum]: "writing",
          },
        };
      });

      const actRes = await api.blueprint.generateAct(projectId, {
        act_number: actNum,
        total_scenes: selectedScenes,
        duration_mode: selectedMode,
        auto_split_shots: autoSplitShots,
      });

      const actData = actRes.data;
      const usedFallback = !!actData.used_fallback;

      setStageProgress((prev) => {
        if (!prev) return null;
        return {
          ...prev,
          actStatuses: {
            ...prev.actStatuses,
            [actNum]: "saved",
          },
          actFallbacks: {
            ...prev.actFallbacks,
            [actNum]: usedFallback,
          },
          actDetails: {
            ...prev.actDetails,
            [actNum]: {
              scenes: actData.scenes_generated,
              shots: actData.shots_generated,
              summary: actData.act_summary,
            },
          },
        };
      });

      await onRefreshScenes();
    } catch (err: any) {
      console.error(`Retry Act ${actNum} error:`, err);
      setStageProgress((prev) => {
        if (!prev) return null;
        return {
          ...prev,
          actStatuses: {
            ...prev.actStatuses,
            [actNum]: "error",
          },
          errorMsg: `Failed to regenerate Act ${actNum}: ${err?.message || "Error"}`,
        };
      });
    }
  };

  const calculateProgressPercent = () => {
    if (!stageProgress) return 0;
    if (stageProgress.phase === "COMPLETE") return 100;
    let pct = 0;
    if (stageProgress.treatmentGenerated) pct += 20;
    if (stageProgress.actStatuses[1] === "saved") pct += 20;
    if (stageProgress.actStatuses[2] === "saved") pct += 20;
    if (stageProgress.actStatuses[3] === "saved") pct += 20;
    if (stageProgress.actStatuses[4] === "saved") pct += 20;
    return pct;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-2xl bg-panel border border-border rounded-2xl shadow-2xl overflow-hidden max-h-[92vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-border bg-canvas/40">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-cinzel text-base sm:text-lg font-bold text-obsidian-primary uppercase tracking-wide">
                Hollywood 4-Act Storyboard & Screenplay Generator
              </h2>
              <p className="text-xs font-mono text-obsidian-muted">
                Staged 4-Act chunking without token limits or timeouts
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isGenerating}
            className="p-1.5 rounded-lg text-obsidian-muted hover:text-obsidian-primary hover:bg-elevated transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Content */}
        <form onSubmit={handleStartGeneration} className="overflow-y-auto p-5 space-y-6 flex-1 text-xs font-mono">
          {/* Preset Blueprint Banner */}
          {presetDefaults && (
            <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 space-y-2 text-xs font-mono">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-amber-400">
                  <Sparkles className="w-4 h-4 shrink-0" />
                  <span>
                    <strong>Preset Blueprint Active:</strong> {presetDefaults.total_scenes || 50}-Scene 4-Act ({presetDefaults.pacing?.shot_duration_min || 4.0}&ndash;{presetDefaults.pacing?.shot_duration_max || 5.0}s Pacing)
                  </span>
                </div>
                <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 text-[10px] font-bold">
                  AUTO-CALIBRATED
                </span>
              </div>
              {presetDefaults.cold_open_30s?.enabled && (
                <div className="text-[11px] text-amber-300/90 pl-6 border-t border-amber-500/20 pt-1.5 flex items-center justify-between">
                  <span>⚡ <strong>Cold Open Montage (Scenes 01-03):</strong> 30s High-Velocity Hook &amp; Teaser preview &rarr; Linear World at Scene 04</span>
                  <span className="text-[10px] bg-amber-400/20 px-1.5 py-0.5 rounded text-amber-200">6 Shots &times; 5.0s</span>
                </div>
              )}
            </div>
          )}

          {/* Active Generation / Status Dashboard View */}
          {stageProgress ? (
            <div className="space-y-4 animate-fade-in">
              <div className="p-4 rounded-xl bg-canvas border border-border space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-obsidian-primary flex items-center gap-2">
                    <Bot className="w-4 h-4 text-amber-500" />
                    <span>Staged Screenplay Writer Progress</span>
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="text-amber-400 font-bold">{calculateProgressPercent()}%</span>
                  </div>
                </div>

                {/* Progress bar */}
                <div className="w-full h-2 rounded-full bg-panel overflow-hidden border border-border">
                  <div
                    className="h-full bg-gradient-to-r from-amber-500 to-emerald-400 transition-all duration-500"
                    style={{ width: `${calculateProgressPercent()}%` }}
                  />
                </div>

                {/* Phase A: Treatment Status */}
                <div className="p-3 rounded-lg bg-panel/70 border border-border space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-obsidian-primary flex items-center gap-1.5">
                      <BookOpen className="w-3.5 h-3.5 text-blue-400" />
                      <span>Phase A: Master Treatment & Beat Sheet</span>
                    </span>
                    {stageProgress.treatmentGenerated ? (
                      <span className="text-[10px] text-emerald-400 font-bold flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Ready</span>
                      </span>
                    ) : (
                      <span className="text-[10px] text-amber-400 flex items-center gap-1">
                        <div className="w-2.5 h-2.5 border-2 border-amber-400 border-t-transparent rounded-full animate-spin" />
                        <span>Writing Treatment...</span>
                      </span>
                    )}
                  </div>
                  {stageProgress.logline && (
                    <p className="text-[10px] text-obsidian-secondary italic mt-1 border-l-2 border-amber-500/50 pl-2">
                      &quot;{stageProgress.logline}&quot;
                    </p>
                  )}
                </div>

                {/* Phase B: 4 Acts Status Cards with Per-Act Fallback & Retry Buttons */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {[
                    { act: 1, label: "Act I: Setup", desc: "Catalyst & Threshold" },
                    { act: 2, label: "Act II-A: Rising", desc: "Trials & Midpoint" },
                    { act: 3, label: "Act II-B: Dark Night", desc: "Descent & Crisis" },
                    { act: 4, label: "Act III: Climax", desc: "Climax & Resolution" },
                  ].map((item) => {
                    const actStatus = stageProgress.actStatuses[item.act as 1 | 2 | 3 | 4];
                    const isFallback = stageProgress.actFallbacks[item.act as 1 | 2 | 3 | 4];
                    const details = stageProgress.actDetails[item.act as 1 | 2 | 3 | 4];

                    return (
                      <div
                        key={item.act}
                        className={cn(
                          "p-3 rounded-xl border text-left transition-all flex flex-col justify-between",
                          actStatus === "writing"
                            ? "bg-amber-500/10 border-amber-500/50 shadow-sm"
                            : isFallback
                            ? "bg-amber-500/5 border-amber-500/40"
                            : actStatus === "saved"
                            ? "bg-emerald-500/10 border-emerald-500/40"
                            : "bg-panel/40 border-border/80 opacity-60"
                        )}
                      >
                        <div>
                          <div className="flex items-center justify-between gap-1">
                            <span className="font-bold text-xs text-obsidian-primary">{item.label}</span>
                            {actStatus === "saved" && !isFallback && (
                              <span className="text-[9px] text-emerald-400 bg-emerald-500/20 border border-emerald-500/30 px-1.5 py-0.5 rounded font-bold flex items-center gap-1">
                                <CheckCircle2 className="w-2.5 h-2.5" />
                                <span>LLM Saved</span>
                              </span>
                            )}
                            {actStatus === "saved" && isFallback && (
                              <span
                                className="text-[9px] text-amber-300 bg-amber-500/20 border border-amber-500/40 px-1.5 py-0.5 rounded font-bold flex items-center gap-1"
                                title="Babak ini menggunakan Procedural Fallback. Klik Retry untuk men-generate ulang dengan LLM."
                              >
                                <AlertTriangle className="w-2.5 h-2.5" />
                                <span>Fallback Mode</span>
                              </span>
                            )}
                            {actStatus === "writing" && (
                              <span className="text-[9px] text-amber-400 font-bold flex items-center gap-1">
                                <div className="w-2 h-2 border border-amber-400 border-t-transparent rounded-full animate-spin" />
                                <span>Writing...</span>
                              </span>
                            )}
                            {actStatus === "pending" && (
                              <span className="text-[9px] text-obsidian-muted">Pending</span>
                            )}
                            {actStatus === "error" && (
                              <span className="text-[9px] text-rose-400 font-bold">Failed</span>
                            )}
                          </div>
                          <div className="text-[9px] text-obsidian-muted mt-0.5">{item.desc}</div>
                          {details && details.scenes > 0 && (
                            <div className="text-[9px] text-emerald-400/90 mt-1 font-mono">
                              {details.scenes} scenes saved to SQLite
                            </div>
                          )}
                        </div>

                        {/* Retry Per Babak Button */}
                        {(actStatus === "saved" || actStatus === "error" || isFallback) && (
                          <div className="mt-2.5 pt-2 border-t border-border/60 flex items-center justify-between">
                            <span className="text-[9px] text-obsidian-muted truncate">
                              {isFallback ? "Procedural fallback used" : "Act intact in DB"}
                            </span>
                            <button
                              type="button"
                              onClick={() => handleRetryAct(item.act as 1 | 2 | 3 | 4)}
                              disabled={actStatus === "writing" || isGenerating}
                              className={cn(
                                "flex items-center gap-1 px-2 py-1 rounded text-[10px] font-bold font-mono transition-colors disabled:opacity-40",
                                isFallback
                                  ? "bg-amber-500/20 text-amber-300 border border-amber-500/50 hover:bg-amber-500/30"
                                  : "bg-canvas hover:bg-elevated border border-border text-obsidian-secondary hover:text-amber-400"
                              )}
                              title={`Regenerate ${item.label} without altering other acts`}
                            >
                              <RefreshCw className={cn("w-2.5 h-2.5", actStatus === "writing" && "animate-spin")} />
                              <span>{isFallback ? "Retry with LLM" : "Retry Act"}</span>
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {stageProgress.phase === "COMPLETE" && (
                  <div className="p-3 rounded-lg bg-emerald-500/15 border border-emerald-500/40 text-center space-y-1">
                    <div className="text-xs font-bold text-emerald-400 flex items-center justify-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Screenplay Generation Ready!</span>
                    </div>
                    <p className="text-[10px] text-obsidian-secondary">
                      All {selectedScenes} scenes with custom sluglines, narrative goals, and dialogue are committed to SQLite.
                    </p>
                  </div>
                )}

                {stageProgress.errorMsg && (
                  <div className="p-3 rounded-lg bg-rose-500/15 border border-rose-500/40 text-rose-400 text-xs">
                    {stageProgress.errorMsg}
                  </div>
                )}
              </div>

              {/* Actions below dashboard */}
              <div className="flex items-center justify-between pt-2">
                <button
                  type="button"
                  onClick={() => setStageProgress(null)}
                  disabled={isGenerating}
                  className="text-xs text-obsidian-muted hover:text-obsidian-primary transition-colors underline"
                >
                  Configure New Film
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-canvas font-bold text-xs transition-all shadow-glow"
                >
                  <span>View Storyboard</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ) : (
            <>
              {/* Writer Mode Selection */}
              <div className="space-y-2">
                <label className="text-obsidian-primary font-bold uppercase tracking-wider flex items-center gap-2">
                  <Bot className="w-4 h-4 text-amber-500" />
                  <span>Engine Mode</span>
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setWriterMode("staged_ai")}
                    className={cn(
                      "p-3 rounded-xl border text-left transition-all",
                      writerMode === "staged_ai"
                        ? "bg-amber-500/15 border-amber-500/60 shadow-sm"
                        : "bg-canvas border-border hover:bg-elevated/70"
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className={cn("text-xs font-bold", writerMode === "staged_ai" ? "text-amber-400" : "text-obsidian-primary")}>
                        Staged AI Writer (Recommended)
                      </span>
                      {writerMode === "staged_ai" && <CheckCircle2 className="w-3.5 h-3.5 text-amber-400" />}
                    </div>
                    <p className="text-[10px] text-obsidian-muted mt-1 leading-relaxed">
                      Writes full narrative goals, sluglines, and character dialogue act-by-act with persistent context chaining and per-act retry.
                    </p>
                  </button>

                  <button
                    type="button"
                    onClick={() => setWriterMode("instant_structural")}
                    className={cn(
                      "p-3 rounded-xl border text-left transition-all",
                      writerMode === "instant_structural"
                        ? "bg-blue-500/15 border-blue-500/60 shadow-sm"
                        : "bg-canvas border-border hover:bg-elevated/70"
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className={cn("text-xs font-bold", writerMode === "instant_structural" ? "text-blue-400" : "text-obsidian-primary")}>
                        Instant Structural Blueprint
                      </span>
                      {writerMode === "instant_structural" && <CheckCircle2 className="w-3.5 h-3.5 text-blue-400" />}
                    </div>
                    <p className="text-[10px] text-obsidian-muted mt-1 leading-relaxed">
                      Instantly generates the complete 4-Act structure and auto-split camera shots in &lt;100ms.
                    </p>
                  </button>
                </div>
              </div>

              {/* Story Premise / Concept (for AI Writer) */}
              {writerMode === "staged_ai" && (
                <div className="space-y-1.5">
                  <label className="text-obsidian-primary font-bold uppercase tracking-wider flex items-center justify-between">
                    <span>Story Premise / Director&apos;s Concept (Optional)</span>
                    <span className="text-[10px] text-obsidian-muted font-normal">Custom Story Prompt</span>
                  </label>
                  <textarea
                    rows={2}
                    value={premise}
                    onChange={(e) => setPremise(e.target.value)}
                    placeholder="Contoh: Operasi spionase siber di Neo Jakarta di mana Arya berusaha membobol server pusat untuk membebaskan rekannya..."
                    className="w-full p-2.5 rounded-xl bg-canvas border border-border text-obsidian-primary text-xs focus:border-amber-500 focus:outline-none placeholder:text-obsidian-muted/60"
                  />
                </div>
              )}

              {/* Section 1: Total Scene Selection */}
              <div className="space-y-1">
                <ObsidianDropdown
                  label="1. Scene Count (Scale Target)"
                  placeholder="Select Scene Count Target..."
                  icon={<Layers className="w-4 h-4 text-amber-500" />}
                  options={SCENE_OPTIONS.map((opt) => ({
                    value: String(opt.count),
                    title: `${opt.label} (${opt.tier})`,
                    description: `Estimated Runtime: ${opt.minutes} (~${Math.round(opt.count * 0.25)} scenes/act)`,
                    badge: `${opt.count} SCENES`,
                  }))}
                  value={String(selectedScenes)}
                  onChange={(val) => setSelectedScenes(parseInt(val))}
                />
              </div>

              {/* Section 2: Duration Mode Selection */}
              <div className="space-y-1">
                <ObsidianDropdown
                  label="2. Scene Duration & Pacing Profile"
                  placeholder="Select Duration Mode..."
                  icon={<Clock className="w-4 h-4 text-blue-400" />}
                  options={DURATION_OPTIONS.map((mode) => ({
                    value: mode.id,
                    title: `${mode.label} (Avg ${mode.avgSeconds}s)`,
                    description: mode.description,
                    badge: mode.badge,
                  }))}
                  value={selectedMode}
                  onChange={(val) => setSelectedMode(val as DurationMode)}
                />
              </div>

              {/* Section 3: Cinematics & Assembly Config */}
              <div className="space-y-3 p-3.5 rounded-xl bg-canvas border border-border">
                <label className="text-obsidian-primary font-bold uppercase tracking-wider flex items-center gap-2">
                  <Film className="w-4 h-4 text-violet-400" />
                  <span>3. Multi-Shot Assembly Options</span>
                </label>

                <label className="flex items-start gap-2.5 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={autoSplitShots}
                    onChange={(e) => setAutoSplitShots(e.target.checked)}
                    className="mt-0.5 rounded border-border bg-panel text-amber-500 focus:ring-0 focus:ring-offset-0"
                  />
                  <div className="flex-1">
                    <span className="text-xs text-obsidian-primary font-bold">
                      Auto-Split Multi-Shot Assembly (Recommended)
                    </span>
                    <p className="text-[10px] text-obsidian-muted mt-0.5 leading-relaxed">
                      Automatically decomposes 10s scenes into 2 shots and 15s scenes into 3 shots with alternate camera coverage.
                    </p>
                  </div>
                </label>

                {existingScenesCount > 0 && (
                  <label className="flex items-start gap-2.5 cursor-pointer select-none pt-2 border-t border-border/60">
                    <input
                      type="checkbox"
                      checked={clearExisting}
                      onChange={(e) => setClearExisting(e.target.checked)}
                      className="mt-0.5 rounded border-border bg-panel text-rose-500 focus:ring-0 focus:ring-offset-0"
                    />
                    <div className="flex-1">
                      <span className="text-xs text-rose-400 font-bold flex items-center gap-1.5">
                        <AlertTriangle className="w-3.5 h-3.5" />
                        <span>Clear existing {existingScenesCount} scenes before generating</span>
                      </span>
                      <p className="text-[10px] text-obsidian-muted mt-0.5 leading-relaxed">
                        Replaces all current scenes with the newly generated Hollywood 4-Act structure.
                      </p>
                    </div>
                  </label>
                )}
              </div>

              {/* Live Preview Blueprint Stats */}
              <div className="p-3.5 rounded-xl bg-elevated/70 border border-border/80 space-y-2">
                <div className="text-[10px] uppercase text-obsidian-muted tracking-wider font-bold">
                  Generated Blueprint Summary:
                </div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="p-2 rounded-lg bg-panel border border-border">
                    <div className="text-base font-bold text-amber-400">{selectedScenes}</div>
                    <div className="text-[9px] text-obsidian-muted">Scenes Total</div>
                  </div>
                  <div className="p-2 rounded-lg bg-panel border border-border">
                    <div className="text-base font-bold text-blue-400">{estShots}</div>
                    <div className="text-[9px] text-obsidian-muted">Calibrated Shots</div>
                  </div>
                  <div className="p-2 rounded-lg bg-panel border border-border">
                    <div className="text-base font-bold text-emerald-400">
                      {estMinutes}m {estRemainingSec}s
                    </div>
                    <div className="text-[9px] text-obsidian-muted">Est. Runtime ({totalSeconds}s)</div>
                  </div>
                </div>

                <div className="text-[10px] text-obsidian-muted pt-1 flex items-center justify-between border-t border-border/50">
                  <span>Structure: 4 Acts (~{actQuartile} scenes/act)</span>
                  <span>{writerMode === "staged_ai" ? "Staged Act-by-Act Chaining" : "Fast Single-Tx Bulk Insert"}</span>
                </div>
              </div>

              {/* Modal Actions */}
              <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-border">
                <button
                  type="button"
                  onClick={onClose}
                  disabled={isGenerating}
                  className="px-4 py-2 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-secondary text-xs font-bold transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isGenerating}
                  className="flex items-center gap-2 px-5 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas text-xs font-bold transition-all shadow-glow disabled:opacity-50"
                >
                  {writerMode === "staged_ai" ? (
                    <>
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Start Staged AI Writer ({selectedScenes} Scenes)</span>
                    </>
                  ) : (
                    <>
                      <Zap className="w-3.5 h-3.5" />
                      <span>Generate Instant Blueprint</span>
                    </>
                  )}
                </button>
              </div>
            </>
          )}
        </form>
      </div>
    </div>
  );
}