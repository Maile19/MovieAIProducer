"use client";

import React from "react";
import { Sparkles, Download } from "lucide-react";
import { cn } from "@/lib/utils";
import ObsidianDropdown from "@/components/ui/ObsidianDropdown";

export type ActFilterType =
  | "ALL"
  | number
  | "ACT_I"
  | "ACT_II_A"
  | "ACT_II_B"
  | "ACT_III"
  | "ACT_IV"
  | "ACT_V";

interface ActFilterBarProps {
  currentFilter: ActFilterType;
  onChangeFilter: (filter: ActFilterType) => void;
  totalScenes: number;
  actCounts?: Record<number, number> | {
    act1?: number;
    act2a?: number;
    act2b?: number;
    act3?: number;
    [key: string]: number | undefined;
  };
  totalActs?: number;
  actsData?: Array<{
    act_number: number;
    act_title?: string;
    start_scene?: number;
    end_scene?: number;
  }>;
  structureType?: string;
  onGenerateBlueprint: () => void;
  isGeneratingBlueprint: boolean;
  onExportPackage: (format: "json" | "markdown") => void;
}

export default function ActFilterBar({
  currentFilter,
  onChangeFilter,
  totalScenes,
  actCounts,
  totalActs,
  actsData,
  structureType,
  onGenerateBlueprint,
  isGeneratingBlueprint,
  onExportPackage,
}: ActFilterBarProps) {
  const count = totalScenes || 50;
  const pad = count >= 100 ? 3 : 2;
  const formatNum = (n: number) => n.toString().padStart(pad, "0");

  // Normalized act counts map: 1 -> count, 2 -> count, etc.
  const countMap: Record<number, number> = {};
  if (actCounts) {
    if ("act1" in actCounts || "act2a" in actCounts) {
      const legacy = actCounts as { act1?: number; act2a?: number; act2b?: number; act3?: number };
      countMap[1] = legacy.act1 || 0;
      countMap[2] = legacy.act2a || 0;
      countMap[3] = legacy.act2b || 0;
      countMap[4] = legacy.act3 || 0;
    } else {
      Object.entries(actCounts).forEach(([k, v]) => {
        const num = Number(k);
        if (!isNaN(num) && typeof v === "number") {
          countMap[num] = v;
        }
      });
    }
  }

  // Determine number of acts (3, 4, or 5)
  const numActs =
    totalActs ||
    actsData?.length ||
    (structureType === "3_act" ? 3 : structureType === "5_act" ? 5 : 4);

  const DEFAULT_LABELS: Record<string, Record<number, string>> = {
    "3_act": {
      1: "Act I: Setup & Catalyst",
      2: "Act II: Confrontation & Ordeal",
      3: "Act III: Climax & Resolution",
    },
    "4_act": {
      1: "Act I: Setup & Catalyst",
      2: "Act II-A: Rising Stakes",
      3: "Act II-B: Dark Night",
      4: "Act III: Climax & Resolution",
    },
    "youtube_viral": {
      1: "Part 1: Shock Hook",
      2: "Part 2: Rapid Chaos",
      3: "Part 3: Climax Twist",
      4: "Part 4: Cliffhanger",
    },
    "5_act": {
      1: "Act I: Exposition & Inciting",
      2: "Act II: Rising Action",
      3: "Act III: Climax & Turning Point",
      4: "Act IV: Falling Action",
      5: "Act V: Catastrophe & Denouement",
    },
  };

  const getActColor = (actNum: number, maxActs: number) => {
    if (actNum === 1) return "emerald";
    if (actNum === 2) return "blue";
    if (actNum === 3) return maxActs === 3 ? "rose" : "violet";
    if (actNum === 4) return maxActs === 5 ? "fuchsia" : "rose";
    return "rose";
  };

  // Build bounds dynamically if actsData not provided
  const bounds: Array<{ start: number; end: number }> = [];
  if (actsData && actsData.length > 0) {
    actsData.forEach((ad) => {
      bounds.push({
        start: ad.start_scene || 1,
        end: ad.end_scene || count,
      });
    });
  } else {
    if (numActs === 3) {
      const b1 = Math.max(1, Math.round(count * 0.25));
      const b2 = Math.max(b1 + 1, Math.round(count * 0.75));
      bounds.push({ start: 1, end: b1 });
      bounds.push({ start: b1 + 1, end: b2 });
      bounds.push({ start: b2 + 1, end: count });
    } else if (numActs === 5) {
      const b1 = Math.max(1, Math.round(count * 0.20));
      const b2 = Math.max(b1 + 1, Math.round(count * 0.40));
      const b3 = Math.max(b2 + 1, Math.round(count * 0.60));
      const b4 = Math.max(b3 + 1, Math.round(count * 0.80));
      bounds.push({ start: 1, end: b1 });
      bounds.push({ start: b1 + 1, end: b2 });
      bounds.push({ start: b2 + 1, end: b3 });
      bounds.push({ start: b3 + 1, end: b4 });
      bounds.push({ start: b4 + 1, end: count });
    } else {
      const b1 = count === 50 ? 12 : Math.max(1, Math.round(count * 0.25));
      const b2 = count === 50 ? 25 : Math.max(b1 + 1, Math.round(count * 0.50));
      const b3 = count === 50 ? 38 : Math.max(b2 + 1, Math.round(count * 0.75));
      bounds.push({ start: 1, end: b1 });
      bounds.push({ start: b1 + 1, end: b2 });
      bounds.push({ start: b2 + 1, end: b3 });
      bounds.push({ start: b3 + 1, end: count });
    }
  }

  const structureKey = structureType || (numActs === 3 ? "3_act" : numActs === 5 ? "5_act" : "4_act");
  const labelMap = DEFAULT_LABELS[structureKey] || DEFAULT_LABELS["4_act"];

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
  ];

  for (let a = 1; a <= numActs; a++) {
    const actData = actsData?.find((item) => item.act_number === a);
    const label = actData?.act_title || labelMap[a] || `Act ${a}`;
    const bound = bounds[a - 1] || { start: 1, end: count };
    const actCount = countMap[a] ?? 0;
    const color = getActColor(a, numActs);

    filters.push({
      id: a as ActFilterType,
      label,
      sublabel: `Scenes ${formatNum(bound.start)}–${formatNum(bound.end)}`,
      count: actCount,
      color,
    });
  }

  const isItemActive = (filterId: ActFilterType) => {
    if (filterId === "ALL" && currentFilter === "ALL") return true;
    if (filterId === currentFilter) return true;
    if (typeof filterId === "number") {
      if (currentFilter === "ACT_I" && filterId === 1) return true;
      if (currentFilter === "ACT_II_A" && filterId === 2) return true;
      if (currentFilter === "ACT_II_B" && filterId === 3) return true;
      if (currentFilter === "ACT_III" && filterId === 4) return true;
      if (Number(currentFilter) === filterId) return true;
    }
    return false;
  };

  const getColorClass = (color: string, isActive: boolean) => {
    if (!isActive) return "bg-canvas text-obsidian-muted hover:text-obsidian-secondary border-border";
    switch (color) {
      case "amber":
        return "bg-amber-500/20 text-amber-400 border-amber-500/50 shadow-sm font-bold";
      case "emerald":
        return "bg-emerald-500/20 text-emerald-400 border-emerald-500/50 shadow-sm font-bold";
      case "blue":
        return "bg-blue-500/20 text-blue-400 border-blue-500/50 shadow-sm font-bold";
      case "violet":
        return "bg-violet-500/20 text-violet-400 border-violet-500/50 shadow-sm font-bold";
      case "fuchsia":
        return "bg-fuchsia-500/20 text-fuchsia-400 border-fuchsia-500/50 shadow-sm font-bold";
      case "rose":
      default:
        return "bg-rose-500/20 text-rose-400 border-rose-500/50 shadow-sm font-bold";
    }
  };

  return (
    <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 p-3.5 rounded-xl bg-panel border border-border shadow-studio">
      {/* Mobile/Tablet Act Filter Dropdown */}
      <div className="block lg:hidden w-full">
        <ObsidianDropdown
          size="sm"
          label="Filter by Dramatic Act"
          icon={<Sparkles className="w-4 h-4 text-amber-500" />}
          options={filters.map((f) => ({
            value: String(f.id),
            title: f.label,
            description: `${f.sublabel} • ${f.count} Scenes`,
            badge: `${f.count} SCENES`,
          }))}
          value={String(currentFilter)}
          onChange={(val) => onChangeFilter(val === "ALL" ? "ALL" : Number(val))}
        />
      </div>

      {/* Desktop Act Filter Tabs */}
      <div className="hidden lg:flex items-center gap-1.5 overflow-x-auto pb-1 lg:pb-0 scrollbar-none">
        {filters.map((f) => {
          const isActive = isItemActive(f.id);

          return (
            <button
              key={String(f.id)}
              type="button"
              onClick={() => onChangeFilter(f.id)}
              className={cn(
                "px-3 py-2 rounded-lg text-left text-xs font-mono transition-all border shrink-0",
                getColorClass(f.color, isActive)
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
          title="Configure & Generate Storyboard Blueprint with Polya AI"
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
