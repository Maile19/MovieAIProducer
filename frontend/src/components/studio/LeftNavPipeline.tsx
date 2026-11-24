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
  ShieldAlert,
  Film,
} from "lucide-react";
import { HOLLYWOOD_16_STAGES, HOLLYWOOD_12_STEPS, StageDefinition } from "@/lib/studio-constants";
import { StageStatusDetail, StepStatusDetail, PipelineHeaderMetrics } from "@/lib/api";
import { cn } from "@/lib/utils";

interface LeftNavPipelineProps {
  currentStage?: number; // Backward compatibility
  viewingStage?: number;
  currentWorkingStage?: number;
  stages?: Record<string, StageStatusDetail>;
  steps?: Record<string, StepStatusDetail>;
  headerMetrics?: PipelineHeaderMetrics;
  onSelectStage?: (stage: number) => void;
  onApproveGate?: (stage: number) => void;
  onRevokeGate?: (stage: number) => void;
  isProjectLocked?: boolean;
}

export default function LeftNavPipeline({
  currentStage,
  viewingStage: propViewingStage,
  currentWorkingStage: propWorkingStage,
  stages,
  steps,
  headerMetrics,
  onSelectStage,
  onApproveGate,
  onRevokeGate: _onRevokeGate,
  isProjectLocked = false,
}: LeftNavPipelineProps) {
  const [activeTab, setActiveTab] = useState<"16_stages" | "12_steps">("16_stages");
  const [expandedPhases, setExpandedPhases] = useState<Record<string, boolean>>({
    "Phase 1: Pre-Production & Narrative Blueprint": true,
    "Phase 2: Visual Style & DNA Freeze": true,
    "Phase 3: Generative Inference & Performance": true,
    "Phase 4: Post-Production & Showrunner Delivery": true,
  });

  const viewingStage = propViewingStage ?? currentStage ?? 1;
  const currentWorkingStage = propWorkingStage ?? headerMetrics?.current_working_stage ?? currentStage ?? 1;
  const currentWorkingStep = headerMetrics?.current_working_step ?? Math.min(currentWorkingStage, 12);

  const completedStagesCount =
    headerMetrics?.completed_stages_count ??
    (stages ? Object.values(stages).filter((s) => s.status === "completed").length : 0);
  const completedStepsCount =
    headerMetrics?.completed_steps_count ??
    (steps ? Object.values(steps).filter((s) => s.status === "completed").length : 0);

  const togglePhase = (phase: string) => {
    setExpandedPhases((prev) => ({ ...prev, [phase]: !prev[phase] }));
  };

  // Group 16 stages by phase
  const groupedStages = HOLLYWOOD_16_STAGES.reduce<Record<string, StageDefinition[]>>((acc, s) => {
    if (!acc[s.phase]) acc[s.phase] = [];
    acc[s.phase].push(s);
    return acc;
  }, {});

  const getStageStatus = (stageNum: number): "completed" | "in_progress" | "awaiting_gate" | "not_started" => {
    const key = `S${stageNum.toString().padStart(2, "0")}`;
    if (stages && stages[key]) {
      return stages[key].status;
    }
    // Fallback if stages map not yet available
    if (stageNum === currentWorkingStage) return "in_progress";
    return "not_started";
  };

  return (
    <aside className="w-full lg:w-80 shrink-0 flex flex-col bg-panel border border-border rounded-xl overflow-hidden shadow-studio">
      {/* Header with Switcher Tabs & Achievement Counter */}
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

          {/* Achievement Counter with Current Working Indicator */}
          <div className="flex flex-col items-end">
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-canvas border border-border text-amber-400">
              {activeTab === "16_stages"
                ? `${completedStagesCount}/16 Completed`
                : `${completedStepsCount}/12 Completed`}
            </span>
            <span className="text-[9px] font-mono text-obsidian-muted mt-0.5">
              {activeTab === "16_stages"
                ? `Current: S${currentWorkingStage.toString().padStart(2, "0")}`
                : `Current: Step ${currentWorkingStep.toString().padStart(2, "0")}`}
            </span>
          </div>
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
          Object.entries(groupedStages).map(([phaseName, phaseStages]) => {
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
                    {phaseStages.map((stage) => {
                      const status = getStageStatus(stage.stage);
                      const isCurrent = stage.stage === currentWorkingStage;
                      const isViewing = stage.stage === viewingStage;
                      const stageKey = `S${stage.stage.toString().padStart(2, "0")}`;
                      const stageDetail = stages ? stages[stageKey] : null;

                      return (
                        <div
                          key={stage.stage}
                          onClick={() => onSelectStage?.(stage.stage)}
                          className={cn(
                            "w-full flex flex-col p-2 rounded-lg text-left transition-all border cursor-pointer",
                            isViewing
                              ? "bg-canvas/90 border-amber-500/80 ring-1 ring-amber-500/50 shadow-md text-obsidian-primary"
                              : isCurrent
                              ? "bg-yellow-400/10 border-yellow-400/50 text-obsidian-primary"
                              : status === "completed"
                              ? "bg-canvas/40 hover:bg-canvas border-emerald-500/20 text-obsidian-secondary"
                              : status === "awaiting_gate"
                              ? "bg-amber-500/10 border-amber-500/40 text-obsidian-primary"
                              : "bg-transparent hover:bg-canvas/60 border-transparent text-obsidian-muted"
                          )}
                        >
                          <div className="flex items-start gap-2.5">
                            {/* Status Icon */}
                            <div className="shrink-0 mt-0.5">
                              {status === "completed" ? (
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                              ) : isCurrent ? (
                                <span className="relative flex h-3.5 w-3.5 items-center justify-center">
                                  <span className="animate-ping absolute inline-flex h-2.5 w-2.5 rounded-full bg-yellow-400 opacity-75" />
                                  <span className="relative inline-flex rounded-full h-2 w-2 bg-yellow-400" />
                                </span>
                              ) : status === "awaiting_gate" ? (
                                <ShieldAlert className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
                              ) : status === "in_progress" ? (
                                <Sparkles className="w-3.5 h-3.5 text-sky-400" />
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
                                    isCurrent
                                      ? "text-yellow-400 font-extrabold"
                                      : isViewing
                                      ? "text-amber-400 font-bold"
                                      : "text-obsidian-muted"
                                  )}
                                >
                                  S{stage.stage.toString().padStart(2, "0")}
                                </span>

                                <div className="flex items-center gap-1">
                                  {isViewing && (
                                    <span className="text-[9px] font-mono px-1 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 font-bold">
                                      VIEWING
                                    </span>
                                  )}
                                  {isCurrent && (
                                    <span className="text-[9px] font-mono px-1 py-0.2 rounded bg-yellow-400/25 text-yellow-300 border border-yellow-400/40 uppercase font-black">
                                      CURRENT
                                    </span>
                                  )}
                                  {status === "completed" && (
                                    <span className="text-[9px] font-mono px-1 py-0.2 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-semibold">
                                      DONE
                                    </span>
                                  )}
                                  {isProjectLocked && stage.stage <= 6 && (
                                    <span className="text-[9px] font-mono px-1 py-0.2 rounded bg-rose-500/20 text-rose-400 flex items-center gap-0.5">
                                      <Lock className="w-2.5 h-2.5" /> LOCKED
                                    </span>
                                  )}
                                </div>
                              </div>

                              <div
                                className={cn(
                                  "font-medium text-[11px] leading-tight line-clamp-1",
                                  isViewing || isCurrent
                                    ? "text-obsidian-primary font-semibold"
                                    : "text-obsidian-secondary"
                                )}
                              >
                                {stage.name}
                              </div>

                              <div className="text-[10px] text-obsidian-muted truncate mt-0.5 flex items-center justify-between">
                                <span>Gate: {stage.gate}</span>
                              </div>
                            </div>
                          </div>

                          {/* Quick Gate Action Control if Awaiting Gate */}
                          {status === "awaiting_gate" && onApproveGate && (
                            <div className="mt-2 pt-1.5 border-t border-amber-500/20 flex items-center justify-between">
                              <span className="text-[9px] font-mono text-amber-400 flex items-center gap-1 font-semibold">
                                <ShieldAlert className="w-3 h-3" /> Gate Ready
                              </span>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onApproveGate(stage.stage);
                                }}
                                className="px-2 py-0.5 rounded bg-amber-500 text-obsidian-primary font-bold text-[10px] hover:bg-amber-400 transition-colors shadow-sm"
                              >
                                Approve Gate
                              </button>
                            </div>
                          )}

                          {status === "completed" && stageDetail?.gate_signoff && (
                            <div className="mt-1 text-[9px] font-mono text-emerald-400/70 truncate">
                              ✓ Approved by {stageDetail.gate_signoff.signed_by || "Showrunner"}
                            </div>
                          )}
                        </div>
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
              const stepKey = step.code;
              const stepDetail = steps ? steps[stepKey] : null;
              const stepStatus = stepDetail ? stepDetail.status : (step.step === currentWorkingStep ? "in_progress" : "not_started");
              const isCurrentStep = step.step === currentWorkingStep;
              const isViewingStep = step.step === Math.min(viewingStage, 12);

              return (
                <div
                  key={step.step}
                  onClick={() => onSelectStage?.(step.step)}
                  className={cn(
                    "p-2.5 rounded-lg border transition-all cursor-pointer",
                    isViewingStep
                      ? "bg-canvas/90 border-amber-500/80 ring-1 ring-amber-500/40"
                      : isCurrentStep
                      ? "bg-yellow-400/10 border-yellow-400/40"
                      : stepStatus === "completed"
                      ? "bg-canvas/50 border-emerald-500/20 hover:border-emerald-500/40"
                      : "bg-transparent border-border/40 text-obsidian-muted hover:bg-canvas/30"
                  )}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono text-[10px] font-semibold text-amber-500">
                      GATE {step.step.toString().padStart(2, "0")}
                    </span>
                    <div className="flex items-center gap-1.5">
                      {isCurrentStep && (
                        <span className="text-[9px] font-mono px-1 py-0.2 rounded bg-yellow-400/25 text-yellow-300 border border-yellow-400/40 uppercase font-black">
                          CURRENT
                        </span>
                      )}
                      {stepStatus === "completed" ? (
                        <span className="text-[9px] font-mono text-emerald-400 font-bold flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" /> PASSED
                        </span>
                      ) : stepStatus === "in_progress" ? (
                        <span className="text-[9px] font-mono text-amber-400 font-bold flex items-center gap-1">
                          <Sparkles className="w-3 h-3" /> IN PROGRESS
                        </span>
                      ) : (
                        <span className="text-[9px] font-mono text-obsidian-muted">QUEUED</span>
                      )}
                    </div>
                  </div>
                  <div className="font-semibold text-obsidian-primary text-xs">{step.name}</div>
                  <div className="text-[10px] text-obsidian-muted mt-0.5">{step.desc}</div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Stage Advance Quick Bar (Non-destructive Viewport Advance) */}
      <div className="p-3 border-t border-border bg-canvas/80 flex items-center justify-between text-xs">
        <div className="flex flex-col">
          <span className="text-[10px] font-mono text-obsidian-muted">
            Viewing: <strong className="text-amber-400 font-semibold">Stage {viewingStage}</strong>
          </span>
          <span className="text-[9px] font-mono text-obsidian-muted/70">
            Current: S{currentWorkingStage.toString().padStart(2, "0")}
          </span>
        </div>
        <button
          type="button"
          onClick={() => onSelectStage?.(Math.min(viewingStage + 1, 16))}
          disabled={viewingStage >= 16}
          className="flex items-center gap-1 px-2.5 py-1 rounded bg-elevated hover:bg-border text-obsidian-primary text-[11px] border border-border transition-colors disabled:opacity-50"
        >
          <span>Next Stage</span>
          <ArrowRight className="w-3 h-3" />
        </button>
      </div>
    </aside>
  );
}
