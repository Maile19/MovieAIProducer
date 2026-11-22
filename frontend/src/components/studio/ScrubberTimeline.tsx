"use client";

import React from "react";
import { HOLLYWOOD_12_STEPS } from "@/lib/studio-constants";
import { cn } from "@/lib/utils";
import { CheckCircle2, Sparkles } from "lucide-react";

interface ScrubberTimelineProps {
  currentStep: number;
  onSelectStep: (step: number) => void;
  maxCompletedStep?: number;
}

export default function ScrubberTimeline({
  currentStep,
  onSelectStep,
  maxCompletedStep: _maxCompletedStep = 1,
}: ScrubberTimelineProps) {
  return (
    <div className="w-full bg-panel border border-border rounded-xl p-3 shadow-studio">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-amber-500" />
          <span className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary">
            12-Step Cinematic Scrubber
          </span>
        </div>
        <div className="flex items-center gap-3 text-[10px] font-mono">
          <div className="flex items-center gap-1.5 text-emerald-400">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span>Passed Gate</span>
          </div>
          <div className="flex items-center gap-1.5 text-amber-400">
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
            <span>Active Step</span>
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
            className="h-full bg-gradient-to-r from-emerald-500 via-amber-500 to-amber-400 rounded-full transition-all duration-300"
            style={{
              width: `${((Math.max(1, currentStep) - 1) / (HOLLYWOOD_12_STEPS.length - 1)) * 100}%`,
            }}
          />
        </div>

        {/* Steps Grid / Flex */}
        <div className="relative z-10 flex items-center justify-between gap-1 overflow-x-auto pb-2 scrollbar-none">
          {HOLLYWOOD_12_STEPS.map((s) => {
            const isCompleted = s.step < currentStep;
            const isCurrent = s.step === currentStep;

            return (
              <button
                key={s.step}
                type="button"
                onClick={() => onSelectStep(s.step)}
                className="group flex flex-col items-center min-w-[72px] sm:min-w-[84px] text-center focus:outline-none"
              >
                {/* Node Pill */}
                <div
                  className={cn(
                    "w-7 h-7 rounded-full flex items-center justify-center font-mono text-[10px] font-bold transition-all border",
                    isCurrent
                      ? "bg-amber-500 text-canvas border-amber-300 shadow-glow scale-110"
                      : isCompleted
                      ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/50 hover:bg-emerald-500/30"
                      : "bg-canvas text-obsidian-muted border-border hover:border-amber-500/40 hover:text-obsidian-secondary"
                  )}
                >
                  {isCompleted ? (
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  ) : (
                    <span>{s.step.toString().padStart(2, "0")}</span>
                  )}
                </div>

                {/* Step Name */}
                <span
                  className={cn(
                    "text-[10px] font-medium mt-1.5 transition-colors line-clamp-1 w-full",
                    isCurrent
                      ? "text-amber-400 font-bold"
                      : isCompleted
                      ? "text-obsidian-secondary"
                      : "text-obsidian-muted group-hover:text-obsidian-secondary"
                  )}
                >
                  {s.name}
                </span>

                {/* Step Subtitle / Gate */}
                <span className="text-[9px] font-mono text-obsidian-muted/70 scale-90">
                  {s.code}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
