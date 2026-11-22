"use client";

import React from "react";
import { Sparkles, Download } from "lucide-react";
import { cn } from "@/lib/utils";
import ObsidianDropdown from "@/components/ui/ObsidianDropdown";

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
  const count = totalScenes || 50;
  const pad = count >= 100 ? 3 : 2;
  const formatNum = (n: number) => n.toString().padStart(pad, "0");

  let act1End = 12;
  let act2End = 25;
  let act3End = 38;

  if (count === 50) {
    act1End = 12;
    act2End = 25;
    act3End = 38;
  } else {
    act1End = Math.max(1, Math.round(count * 0.25));
    act2End = Math.max(act1End + 1, Math.round(count * 0.50));
    act3End = Math.max(act2End + 1, Math.round(count * 0.75));
  }

  const filters: Array<{
    id: ActFilterType;
    label: string;
    sublabel: string;
    count: number;
    color: string;
  }> = [
    {
      id: "ALL",
      label: `All ${count} Scenes`,
      sublabel: `Scenes 01–${formatNum(count)}`,
      count: totalScenes,
      color: "amber",
    },
    {
      id: "ACT_I",
      label: "Act I: Setup & Catalyst",
      sublabel: `Scenes 01–${formatNum(act1End)}`,
      count: actCounts.act1,
      color: "emerald",
    },
    {
      id: "ACT_II_A",
      label: "Act II-A: Rising Stakes",
      sublabel: `Scenes ${formatNum(act1End + 1)}–${formatNum(act2End)}`,
      count: actCounts.act2a,
      color: "blue",
    },
    {
      id: "ACT_II_B",
      label: "Act II-B: Dark Night",
      sublabel: `Scenes ${formatNum(act2End + 1)}–${formatNum(act3End)}`,
      count: actCounts.act2b,
      color: "violet",
    },
    {
      id: "ACT_III",
      label: "Act III: Climax & Resolution",
      sublabel: `Scenes ${formatNum(act3End + 1)}–${formatNum(count)}`,
      count: actCounts.act3,
      color: "rose",
    },
  ];

  return (
    <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 p-3.5 rounded-xl bg-panel border border-border shadow-studio">
      {/* Mobile/Tablet Act Filter Dropdown */}
      <div className="block lg:hidden w-full">
        <ObsidianDropdown
          size="sm"
          label="Filter by Dramatic Act"
          icon={<Sparkles className="w-4 h-4 text-amber-500" />}
          options={filters.map((f) => ({
            value: f.id,
            title: f.label,
            description: `${f.sublabel} • ${f.count} Scenes`,
            badge: `${f.count} SCENES`,
          }))}
          value={currentFilter}
          onChange={(val) => onChangeFilter(val as ActFilterType)}
        />
      </div>

      {/* Desktop Act Filter Tabs */}
      <div className="hidden lg:flex items-center gap-1.5 overflow-x-auto pb-1 lg:pb-0 scrollbar-none">
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
        <button
          type="button"
          onClick={onGenerateBlueprint}
          disabled={isGeneratingBlueprint}
          className={cn(
            "flex items-center gap-1.5 px-3 py-2 rounded-lg font-bold text-xs font-mono transition-all disabled:opacity-50",
            totalScenes === 0
              ? "bg-amber-500 hover:bg-amber-600 text-canvas shadow-glow"
              : "bg-canvas hover:bg-elevated border border-amber-500/40 text-amber-400 hover:border-amber-500"
          )}
          title="Configure & Generate Hollywood 4-Act Blueprint"
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>{totalScenes === 0 ? "Generate Blueprint" : "Blueprint Config"}</span>
        </button>

        <div className="w-36">
          <ObsidianDropdown
            size="sm"
            placeholder="Export..."
            icon={<Download className="w-3.5 h-3.5 text-amber-500" />}
            options={[
              { value: "json", title: "Export JSON", description: "Hollywood JSON Bible & Scenes Package", badge: "JSON" },
              { value: "markdown", title: "Export Script MD", description: "Industry-standard Screenplay Markdown", badge: "MD" },
            ]}
            value=""
            onChange={(format) => onExportPackage(format as "json" | "markdown")}
          />
        </div>
      </div>
    </div>
  );
}
