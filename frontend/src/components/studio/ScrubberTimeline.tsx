"use client";

import React from "react";
import { HOLLYWOOD_12_STEPS } from "@/lib/studio-constants";
import { StepStatusDetail } from "@/lib/api";
import { cn } from "@/lib/utils";
import { CheckCircle2, Sparkles } from "lucide-react";

interface ScrubberTimelineProps {
  currentStep?: number; // Backward compatibility
  viewingStep?: number;
  currentWorkingStep?: number;
  stepStatuses?: Record<string, StepStatusDetail>;
  onSelectStep: (step: number) => void;
  maxCompletedStep?: number;
}

export default function ScrubberTimeline({
  currentStep,
  viewingStep: propViewingStep,
  currentWorkingStep: propWorkingStep,
  stepStatuses,
  onSelectStep,
  maxCompletedStep: _maxCompletedStep = 1,
}: ScrubberTimelineProps) {
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const stepRefs = React.useRef<Map<number, HTMLButtonElement>>(new Map());

  const viewing = propViewingStep ?? currentStep ?? 1;
  const workingStep = propWorkingStep ?? currentStep ?? 1;

  const completedCount = stepStatuses
    ? Object.values(stepStatuses).filter((st) => st.status === "completed").length
    : 0;

  // Horizontal container auto-centering without vertical page jump
  React.useEffect(() => {
    const container = containerRef.current;
    const target = stepRefs.current.get(viewing);
    if (container && target) {
      container.scrollTo({
        left: target.offsetLeft - container.clientWidth / 2 + target.clientWidth / 2,
        behavior: "smooth",
      });
    }
  }, [viewing]);

  return (
    <div className="w-full bg-panel border border-border rounded-xl p-3 shadow-studio">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-amber-500" />
          <span className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary">
            12-Step Cinematic Scrubber
          </span>
          <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-canvas border border-border text-amber-400">
            {completedCount}/12 Passed
          </span>
        </div>
        <div className="flex items-center gap-3 text-[10px] font-mono">
          <div className="flex items-center gap-1.5 text-emerald-400">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span>Passed Gate</span>
          </div>
          <div className="flex items-center gap-1.5 text-yellow-400">
            <span className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
            <span>Current Step</span>
          </div>
          <div className="flex items-center gap-1.5 text-obsidian-muted">
            <span className="w-2 h-2 rounded-full bg-border" />
            <span>Queued</span>
          </div>
        </div>
      </div>

      {/* 12-Step Horizontal Timeline Bar */}
      <div className="relative pt-2 pb-1">
        {/* Track Line */}
        <div className="absolute top-[22px] left-3 right-3 h-1 bg-canvas border border-border rounded-full -z-0">
          <div
            className="h-full bg-gradient-to-r from-emerald-500 via-yellow-400 to-amber-400 rounded-full transition-all duration-300"
            style={{
              width: `${Math.min(100, Math.max(0, (completedCount / 12) * 100))}%`,
            }}
          />
        </div>

        {/* Steps Grid / Flex */}
        <div
          ref={containerRef}
          className="relative z-10 flex items-center justify-between gap-1 overflow-x-auto pb-2 scrollbar-none scroll-smooth"
        >
          {HOLLYWOOD_12_STEPS.map((s) => {
            const detail = stepStatuses ? stepStatuses[s.code] : null;
            const isCompleted = detail ? detail.status === "completed" : false;
            const isInProgress = detail ? detail.status === "in_progress" : s.step === workingStep;
            const isCurrent = s.step === workingStep;
            const isViewing = s.step === viewing;

            return (
              <button
                key={s.step}
                ref={(el) => {
                  if (el) stepRefs.current.set(s.step, el);
                  else stepRefs.current.delete(s.step);
                }}
                type="button"
                onClick={() => onSelectStep(s.step)}
                className="group flex flex-col items-center min-w-[72px] sm:min-w-[84px] text-center focus:outline-none shrink-0"
              >
                {/* Node Pill */}
                <div
                  className={cn(
                    "w-7 h-7 rounded-full flex items-center justify-center font-mono text-[10px] font-bold transition-all border",
                    isViewing
                      ? "ring-2 ring-amber-400 border-amber-300 shadow-[0_0_12px_rgba(251,191,36,0.5)] scale-110"
                      : "",
                    isCurrent
                      ? "bg-yellow-400 text-slate-950 border-yellow-300 ring-2 ring-yellow-400/70 shadow-[0_0_15px_rgba(250,204,21,0.7)] font-black"
                      : isCompleted
                      ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/50 hover:bg-emerald-500/30"
                      : isInProgress
                      ? "bg-amber-500/10 text-amber-400 border-amber-500/40"
                      : "bg-canvas text-obsidian-muted border-border hover:border-amber-500/40 hover:text-obsidian-secondary"
                  )}
                >
                  {isCompleted ? (
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  ) : isInProgress ? (
                    <Sparkles className="w-3.5 h-3.5" />
                  ) : (
                    <span>{s.step.toString().padStart(2, "0")}</span>
                  )}
                </div>

                {/* Step Name */}
                <span
                  className={cn(
                    "text-[10px] font-medium mt-1.5 transition-colors line-clamp-1 w-full",
                    isViewing
                      ? "text-amber-400 font-bold"
                      : isCurrent
                      ? "text-yellow-400 font-bold"
                      : isCompleted
                      ? "text-emerald-400/90 font-medium"
                      : "text-obsidian-muted group-hover:text-obsidian-secondary"
                  )}
                >
                  {s.name}
                </span>

                {/* Step Subtitle / Gate */}
                <span
                  className={cn(
                    "text-[9px] font-mono scale-90",
                    isViewing
                      ? "text-amber-400/90 font-bold"
                      : isCurrent
                      ? "text-yellow-400/90 font-bold"
                      : "text-obsidian-muted/70"
                  )}
                >
                  {isCompleted ? "PASSED" : s.code}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
