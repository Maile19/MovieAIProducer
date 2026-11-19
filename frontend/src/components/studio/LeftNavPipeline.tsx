"use client";

import React, { useState } from "react";
import {
  CheckCircle2,
  Lock,
  Clock,
  Sparkles,
  ChevronDown,
  ChevronRight,
  Layers,
  ArrowRight,
  ShieldCheck,
  Film,
} from "lucide-react";
import { HOLLYWOOD_16_STAGES, HOLLYWOOD_12_STEPS, StageDefinition } from "@/lib/studio-constants";
import { cn } from "@/lib/utils";

interface LeftNavPipelineProps {
  currentStage: number;
  onSelectStage?: (stage: number) => void;
  isProjectLocked?: boolean;
}

export default function LeftNavPipeline({
  currentStage,
  onSelectStage,
  isProjectLocked = false,
}: LeftNavPipelineProps) {
  const [activeTab, setActiveTab] = useState<"16_stages" | "12_steps">("16_stages");
  const [expandedPhases, setExpandedPhases] = useState<Record<string, boolean>>({
    "Phase 1: Pre-Production & Narrative Blueprint": true,
    "Phase 2: Visual Style & DNA Freeze": true,
    "Phase 3: Generative Inference & Performance": true,
    "Phase 4: Post-Production & Showrunner Delivery": true,
  });

  const togglePhase = (phase: string) => {
    setExpandedPhases((prev) => ({ ...prev, [phase]: !prev[phase] }));
  };

  // Group 16 stages by phase
  const groupedStages = HOLLYWOOD_16_STAGES.reduce<Record<string, StageDefinition[]>>((acc, s) => {
    if (!acc[s.phase]) acc[s.phase] = [];
    acc[s.phase].push(s);
    return acc;
  }, {});

  const getStageStatus = (stageNum: number) => {
    if (stageNum < currentStage) return "COMPLETED";
    if (stageNum === currentStage) return "ACTIVE";
    return "PENDING";
  };

  return (
    <aside className="w-full lg:w-80 shrink-0 flex flex-col bg-panel border border-border rounded-xl overflow-hidden shadow-studio">
      {/* Header with Switcher Tabs */}
      <div className="p-3.5 border-b border-border bg-elevated/40">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
              <Layers className="w-3.5 h-3.5" />
            </div>
            <h2 className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary">
              Pipeline Control
            </h2>
          </div>
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-canvas border border-border text-amber-400">
            Stage {currentStage}/16
          </span>
        </div>

        {/* Tab switch between 16-Stage Pipeline and 12-Step Framework */}
        <div className="grid grid-cols-2 p-0.5 bg-canvas rounded-lg border border-border text-xs">
          <button
            type="button"
            onClick={() => setActiveTab("16_stages")}
            className={cn(
              "py-1.5 px-2 rounded-md font-medium text-[11px] transition-all flex items-center justify-center gap-1.5",
              activeTab === "16_stages"
                ? "bg-elevated text-amber-400 shadow-sm border border-amber-500/30"
                : "text-obsidian-muted hover:text-obsidian-primary"
            )}
          >
            <Film className="w-3 h-3" />
            <span>16 Stages</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("12_steps")}
            className={cn(
              "py-1.5 px-2 rounded-md font-medium text-[11px] transition-all flex items-center justify-center gap-1.5",
              activeTab === "12_steps"
                ? "bg-elevated text-amber-400 shadow-sm border border-amber-500/30"
                : "text-obsidian-muted hover:text-obsidian-primary"
            )}
          >
            <Sparkles className="w-3 h-3" />
            <span>12 Steps</span>
          </button>
        </div>
      </div>

      {/* Main Tree View */}
      <div className="flex-1 overflow-y-auto max-h-[calc(100vh-280px)] p-3 space-y-4 font-sans text-xs">
        {activeTab === "16_stages" ? (
          Object.entries(groupedStages).map(([phaseName, stages]) => {
            const isExpanded = expandedPhases[phaseName] !== false;
            const phaseNumber = phaseName.split(":")[0];
            const phaseTitle = phaseName.split(":")[1]?.trim() || phaseName;

            return (
              <div key={phaseName} className="space-y-1">
                {/* Phase Accordion Header */}
                <button
                  type="button"
                  onClick={() => togglePhase(phaseName)}
                  className="w-full flex items-center justify-between px-2.5 py-1.5 rounded bg-canvas/60 hover:bg-canvas border border-border/60 text-left transition-colors group"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    {isExpanded ? (
                      <ChevronDown className="w-3.5 h-3.5 text-obsidian-muted shrink-0 group-hover:text-amber-400" />
                    ) : (
                      <ChevronRight className="w-3.5 h-3.5 text-obsidian-muted shrink-0 group-hover:text-amber-400" />
                    )}
                    <span className="font-mono text-[10px] text-amber-500 font-semibold uppercase tracking-wider shrink-0">
                      {phaseNumber}
                    </span>
                    <span className="font-medium text-[11px] text-obsidian-secondary truncate group-hover:text-obsidian-primary">
                      {phaseTitle}
                    </span>
                  </div>
                </button>

                {/* Stages in Phase */}
                {isExpanded && (
                  <div className="pl-3 space-y-1 pt-1 border-l border-border/40 ml-2">
                    {stages.map((stage) => {
                      const status = getStageStatus(stage.stage);
                      const isCurrent = stage.stage === currentStage;

                      return (
                        <button
                          key={stage.stage}
                          type="button"
                          onClick={() => onSelectStage?.(stage.stage)}
                          className={cn(
                            "w-full flex items-start gap-2.5 p-2 rounded-lg text-left transition-all border",
                            isCurrent
                              ? "bg-amber-500/10 border-amber-500/50 shadow-glow text-obsidian-primary"
                              : status === "COMPLETED"
                              ? "bg-canvas/40 hover:bg-canvas border-border/60 text-obsidian-secondary"
                              : "bg-transparent hover:bg-canvas/60 border-transparent text-obsidian-muted"
                          )}
                        >
                          {/* Status Icon */}
                          <div className="shrink-0 mt-0.5">
                            {status === "COMPLETED" ? (
                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                            ) : isCurrent ? (
                              <span className="relative flex h-3.5 w-3.5 items-center justify-center">
                                <span className="animate-ping absolute inline-flex h-2.5 w-2.5 rounded-full bg-amber-400 opacity-75" />
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500" />
                              </span>
                            ) : (
                              <Clock className="w-3.5 h-3.5 text-obsidian-muted" />
                            )}
                          </div>

                          {/* Stage Info */}
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center justify-between gap-1 mb-0.5">
                              <span
                                className={cn(
                                  "font-mono text-[10px] font-bold",
                                  isCurrent ? "text-amber-400" : "text-obsidian-muted"
                                )}
                              >
                                S{stage.stage.toString().padStart(2, "0")}
                              </span>
                              {isCurrent && (
                                <span className="text-[9px] font-mono px-1 py-0.2 rounded bg-amber-500/20 text-amber-400 uppercase font-bold">
                                  CURRENT
                                </span>
                              )}
                              {isProjectLocked && stage.stage <= 6 && (
                                <span className="text-[9px] font-mono px-1 py-0.2 rounded bg-rose-500/20 text-rose-400 flex items-center gap-0.5">
                                  <Lock className="w-2.5 h-2.5" /> LOCKED
                                </span>
                              )}
                            </div>
                            <div
                              className={cn(
                                "font-medium text-[11px] leading-tight line-clamp-1",
                                isCurrent
                                  ? "text-obsidian-primary font-semibold"
                                  : "text-obsidian-secondary"
                              )}
                            >
                              {stage.name}
                            </div>
                            <div className="text-[10px] text-obsidian-muted truncate mt-0.5">
                              Gate: {stage.gate}
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })
        ) : (
          /* 12-Step Framework View */
          <div className="space-y-1.5">
            <div className="p-2 rounded bg-canvas border border-border/80 text-[11px] text-obsidian-secondary mb-2 font-mono">
              Deterministic 12-Gate Hollywood Framework sequencing DNA variables.
            </div>
            {HOLLYWOOD_12_STEPS.map((step) => {
              const isActive = step.step <= Math.min(currentStage, 12);
              return (
                <div
                  key={step.step}
                  className={cn(
                    "p-2.5 rounded-lg border transition-all",
                    step.step === Math.min(currentStage, 12)
                      ? "bg-amber-500/10 border-amber-500/40"
                      : isActive
                      ? "bg-canvas/50 border-emerald-500/20"
                      : "bg-transparent border-border/40 text-obsidian-muted"
                  )}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono text-[10px] font-semibold text-amber-500">
                      GATE {step.step.toString().padStart(2, "0")}
                    </span>
                    {isActive ? (
                      <span className="text-[9px] font-mono text-emerald-400 font-bold flex items-center gap-1">
                        <ShieldCheck className="w-3 h-3" /> ACTIVE
                      </span>
                    ) : (
                      <span className="text-[9px] font-mono text-obsidian-muted">QUEUED</span>
                    )}
                  </div>
                  <div className="font-semibold text-obsidian-primary text-xs">{step.name}</div>
                  <div className="text-[10px] text-obsidian-muted mt-0.5">{step.desc}</div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Stage Advance Quick Bar */}
      <div className="p-3 border-t border-border bg-canvas/80 flex items-center justify-between text-xs">
        <span className="text-[11px] font-mono text-obsidian-muted">
          Active: <strong className="text-amber-400 font-semibold">Stage {currentStage}</strong>
        </span>
        <button
          type="button"
          onClick={() => onSelectStage?.(Math.min(currentStage + 1, 16))}
          disabled={currentStage >= 16}
          className="flex items-center gap-1 px-2.5 py-1 rounded bg-elevated hover:bg-border text-obsidian-primary text-[11px] border border-border transition-colors disabled:opacity-50"
        >
          <span>Next</span>
          <ArrowRight className="w-3 h-3" />
        </button>
      </div>
    </aside>
  );
}
