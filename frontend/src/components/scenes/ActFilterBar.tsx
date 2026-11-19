"use client";

import React from "react";
import { Sparkles, Download } from "lucide-react";
import { cn } from "@/lib/utils";

export type ActFilterType = "ALL" | "ACT_I" | "ACT_II_A" | "ACT_II_B" | "ACT_III";

interface ActFilterBarProps {
  currentFilter: ActFilterType;
  onChangeFilter: (filter: ActFilterType) => void;
  totalScenes: number;
  actCounts: {
    act1: number;
    act2a: number;
    act2b: number;
    act3: number;
  };
  onGenerateBlueprint: () => void;
  isGeneratingBlueprint: boolean;
  onExportPackage: (format: "json" | "markdown") => void;
}

export default function ActFilterBar({
  currentFilter,
  onChangeFilter,
  totalScenes,
  actCounts,
  onGenerateBlueprint,
  isGeneratingBlueprint,
  onExportPackage,
}: ActFilterBarProps) {
  const filters: Array<{
    id: ActFilterType;
    label: string;
    sublabel: string;
    count: number;
    color: string;
  }> = [
    {
      id: "ALL",
      label: "All 50 Scenes",
      sublabel: "Scenes 01–50",
      count: totalScenes,
      color: "amber",
    },
    {
      id: "ACT_I",
      label: "Act I: Setup & Catalyst",
      sublabel: "Scenes 01–12",
      count: actCounts.act1,
      color: "emerald",
    },
    {
      id: "ACT_II_A",
      label: "Act II-A: Rising Stakes",
      sublabel: "Scenes 13–25",
      count: actCounts.act2a,
      color: "blue",
    },
    {
      id: "ACT_II_B",
      label: "Act II-B: Dark Night",
      sublabel: "Scenes 26–38",
      count: actCounts.act2b,
      color: "violet",
    },
    {
      id: "ACT_III",
      label: "Act III: Climax & Resolution",
      sublabel: "Scenes 39–50",
      count: actCounts.act3,
      color: "rose",
    },
  ];

  return (
    <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 p-3.5 rounded-xl bg-panel border border-border shadow-studio">
      {/* Act Filter Tabs */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 lg:pb-0 scrollbar-none">
        {filters.map((f) => {
          const isActive = currentFilter === f.id;

          return (
            <button
              key={f.id}
              type="button"
              onClick={() => onChangeFilter(f.id)}
              className={cn(
                "px-3 py-2 rounded-lg text-left text-xs font-mono transition-all border shrink-0",
                isActive
                  ? f.id === "ALL"
                    ? "bg-amber-500/20 text-amber-400 border-amber-500/50 shadow-sm font-bold"
                    : f.id === "ACT_I"
                    ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/50 shadow-sm font-bold"
                    : f.id === "ACT_II_A"
                    ? "bg-blue-500/20 text-blue-400 border-blue-500/50 shadow-sm font-bold"
                    : f.id === "ACT_II_B"
                    ? "bg-violet-500/20 text-violet-400 border-violet-500/50 shadow-sm font-bold"
                    : "bg-rose-500/20 text-rose-400 border-rose-500/50 shadow-sm font-bold"
                  : "bg-canvas text-obsidian-muted hover:text-obsidian-secondary border-border"
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate">{f.label}</span>
                <span className="text-[10px] px-1 py-0.2 rounded bg-black/40 opacity-80">
                  {f.count}
                </span>
              </div>
              <div className="text-[9px] opacity-70 mt-0.5">{f.sublabel}</div>
            </button>
          );
        })}
      </div>

      {/* Action Buttons: Generate Blueprint & Export Package */}
      <div className="flex items-center gap-2 shrink-0">
        {totalScenes === 0 && (
          <button
            type="button"
            onClick={onGenerateBlueprint}
            disabled={isGeneratingBlueprint}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-xs transition-all shadow-glow disabled:opacity-50"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Generate 50-Scene Blueprint</span>
          </button>
        )}

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => onExportPackage("json")}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-secondary hover:text-amber-400 text-xs font-mono transition-colors"
            title="Download Hollywood JSON Package"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export JSON</span>
          </button>
          <button
            type="button"
            onClick={() => onExportPackage("markdown")}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-secondary hover:text-blue-400 text-xs font-mono transition-colors"
            title="Download Hollywood Markdown Script"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Script MD</span>
          </button>
        </div>
      </div>
    </div>
  );
}
