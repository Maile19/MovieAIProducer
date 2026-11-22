"use client";

import React, { useState } from "react";
import {
  Palette,
  Sun,
  Smile,
  Video,
  Eye,
  LayoutGrid,
  Zap,
  Search,
  Check,
  Filter,
} from "lucide-react";
import {
  DEFAULT_STYLES,
  DEFAULT_LIGHTING,
  DEFAULT_ACTING,
  DEFAULT_CAMERAS,
  DEFAULT_LENSES,
  DEFAULT_COMPOSITIONS,
  DEFAULT_SPEEDS,
} from "@/lib/studio-constants";
import { cn } from "@/lib/utils";
import ObsidianDropdown from "@/components/ui/ObsidianDropdown";

export interface SelectedMatrixState {
  styleCode: string;
  lightCode: string;
  actCode: string;
  camCode: string;
  lensCode: string;
  compCode: string;
  speedCode: string;
}

interface MatrixSelectorProps {
  selectedMatrix: SelectedMatrixState;
  onChangeMatrix: (updates: Partial<SelectedMatrixState>) => void;
  catalogData?: any;
}

export default function MatrixSelector({
  selectedMatrix,
  onChangeMatrix,
  catalogData,
}: MatrixSelectorProps) {
  const [activeCategory, setActiveCategory] = useState<
    "style" | "light" | "act" | "cam" | "lens" | "comp" | "speed"
  >("style");
  const [searchQuery, setSearchQuery] = useState("");

  const styles = catalogData?.styles || DEFAULT_STYLES;
  const lighting = catalogData?.lighting || DEFAULT_LIGHTING;
  const acting = catalogData?.acting || DEFAULT_ACTING;
  const cameras = catalogData?.cameras || DEFAULT_CAMERAS;
  const lenses = catalogData?.lenses || DEFAULT_LENSES;
  const compositions = catalogData?.compositions || DEFAULT_COMPOSITIONS;
  const speeds = catalogData?.speeds || DEFAULT_SPEEDS;

  const categories = [
    { id: "style", label: "#Style", icon: Palette, current: selectedMatrix.styleCode, count: styles.length },
    { id: "light", label: "#Light", icon: Sun, current: selectedMatrix.lightCode, count: lighting.length },
    { id: "act", label: "#Act", icon: Smile, current: selectedMatrix.actCode, count: acting.length },
    { id: "cam", label: "#Cam", icon: Video, current: selectedMatrix.camCode, count: cameras.length },
    { id: "lens", label: "#Lens", icon: Eye, current: selectedMatrix.lensCode, count: lenses.length },
    { id: "comp", label: "#Comp", icon: LayoutGrid, current: selectedMatrix.compCode, count: compositions.length },
    { id: "speed", label: "#Speed", icon: Zap, current: selectedMatrix.speedCode, count: speeds.length },
  ] as const;

  // Filter items based on search query
  const getFilteredItems = () => {
    const q = searchQuery.toLowerCase().trim();
    switch (activeCategory) {
      case "style":
        return styles.filter((s: any) =>
          !q || s.code.toLowerCase().includes(q) || s.name.toLowerCase().includes(q)
        );
      case "light":
        return lighting.filter((l: any) =>
          !q || l.code.toLowerCase().includes(q) || l.name.toLowerCase().includes(q)
        );
      case "act":
        return acting.filter((a: any) =>
          !q || a.code.toLowerCase().includes(q) || (a.name || a.cue || "").toLowerCase().includes(q)
        );
      case "cam":
        return cameras.filter((c: any) =>
          !q || c.code.toLowerCase().includes(q) || c.name.toLowerCase().includes(q)
        );
      case "lens":
        return lenses.filter((ln: any) =>
          !q || ln.code.toLowerCase().includes(q) || ln.name.toLowerCase().includes(q)
        );
      case "comp":
        return compositions.filter((cp: any) =>
          !q || cp.code.toLowerCase().includes(q) || cp.name.toLowerCase().includes(q)
        );
      case "speed":
        return speeds.filter((sp: any) =>
          !q || sp.code.toLowerCase().includes(q) || sp.name.toLowerCase().includes(q)
        );
      default:
        return [];
    }
  };

  const handleSelectItem = (code: string) => {
    switch (activeCategory) {
      case "style":
        onChangeMatrix({ styleCode: code });
        break;
      case "light":
        onChangeMatrix({ lightCode: code });
        break;
      case "act":
        onChangeMatrix({ actCode: code });
        break;
      case "cam":
        onChangeMatrix({ camCode: code });
        break;
      case "lens":
        onChangeMatrix({ lensCode: code });
        break;
      case "comp":
        onChangeMatrix({ compCode: code });
        break;
      case "speed":
        onChangeMatrix({ speedCode: code });
        break;
    }
  };

  const currentSelectedCode = () => {
    switch (activeCategory) {
      case "style":
        return selectedMatrix.styleCode;
      case "light":
        return selectedMatrix.lightCode;
      case "act":
        return selectedMatrix.actCode;
      case "cam":
        return selectedMatrix.camCode;
      case "lens":
        return selectedMatrix.lensCode;
      case "comp":
        return selectedMatrix.compCode;
      case "speed":
        return selectedMatrix.speedCode;
    }
  };

  return (
    <div className="bg-panel border border-border rounded-xl p-3.5 shadow-studio space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border pb-2.5">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-amber-500" />
          <h3 className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary">
            Hollywood Matrix Selector
          </h3>
        </div>
        <span className="text-[10px] font-mono text-obsidian-muted">
          7-Variable Matrix
        </span>
      </div>

      {/* Matrix Dimension & Active Value Obsidian Dropdowns */}
      <div className="space-y-2.5">
        <ObsidianDropdown
          size="sm"
          label="Active Matrix Dimension"
          options={categories.map((cat) => ({
            value: cat.id,
            title: `${cat.label} Matrix (${cat.count} Hollywood Standards)`,
            description: `Active Selection: ${cat.current}`,
            badge: cat.current,
          }))}
          value={activeCategory}
          onChange={(val) => {
            setActiveCategory(val as any);
            setSearchQuery("");
          }}
        />

        <ObsidianDropdown
          label={`Hollywood ${categories.find(c => c.id === activeCategory)?.label} Catalog`}
          placeholder={`Choose ${activeCategory} specification...`}
          options={getFilteredItems().map((item: any) => ({
            value: item.code,
            title: `${item.code}: ${item.name || item.cue || "Specification"}`,
            description: item.desc || item.aesthetic_directives || item.mood || item.movement || item.framing || item.visual_field || item.description,
            badge: activeCategory.toUpperCase(),
          }))}
          value={currentSelectedCode() || ""}
          onChange={(code) => handleSelectItem(code)}
        />
      </div>

      {/* Active Matrix Summary Badges */}
      <div className="p-2 rounded-lg bg-canvas border border-border/80 flex flex-wrap gap-1.5 text-[10px] font-mono">
        <span className="text-obsidian-muted mr-1">Active:</span>
        <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
          {selectedMatrix.styleCode}
        </span>
        <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
          {selectedMatrix.lightCode}
        </span>
        <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
          {selectedMatrix.actCode}
        </span>
        <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
          {selectedMatrix.camCode}
        </span>
        <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
          {selectedMatrix.lensCode}
        </span>
        <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
          {selectedMatrix.compCode}
        </span>
        <span className="px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
          {selectedMatrix.speedCode}
        </span>
      </div>

      {/* Search Filter Input */}
      <div className="relative">
        <Search className="w-3.5 h-3.5 text-obsidian-muted absolute left-2.5 top-1/2 -translate-y-1/2" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder={`Search ${activeCategory} catalog (e.g. Neo-Noir, Volumetric)...`}
          className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-canvas border border-border text-xs text-obsidian-primary font-mono placeholder:text-obsidian-muted focus:border-amber-500 focus:outline-none"
        />
      </div>

      {/* Item List */}
      <div className="max-h-52 overflow-y-auto space-y-1.5 pr-1">
        {getFilteredItems().map((item: any) => {
          const isSelected = item.code === currentSelectedCode();

          return (
            <button
              key={item.code}
              type="button"
              onClick={() => handleSelectItem(item.code)}
              className={cn(
                "w-full flex items-start justify-between gap-2 p-2 rounded-lg text-left transition-all border",
                isSelected
                  ? "bg-amber-500/15 border-amber-500/50 shadow-sm text-obsidian-primary"
                  : "bg-canvas/60 hover:bg-canvas border-border/60 text-obsidian-secondary hover:text-obsidian-primary"
              )}
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <span
                    className={cn(
                      "font-mono text-[10px] font-bold",
                      isSelected ? "text-amber-400" : "text-amber-500/80"
                    )}
                  >
                    {item.code}
                  </span>
                  <span className="font-semibold text-xs truncate">
                    {item.name || item.cue || "Unnamed"}
                  </span>
                </div>
                {(item.description || item.aesthetic_directives || item.mood || item.movement || item.framing) && (
                  <p className="text-[10px] text-obsidian-muted mt-0.5 line-clamp-1">
                    {item.description || item.aesthetic_directives || item.mood || item.movement || item.framing}
                  </p>
                )}
              </div>

              {isSelected && (
                <div className="w-4 h-4 rounded-full bg-amber-500 text-canvas flex items-center justify-center shrink-0 mt-0.5">
                  <Check className="w-2.5 h-2.5 stroke-[3]" />
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
