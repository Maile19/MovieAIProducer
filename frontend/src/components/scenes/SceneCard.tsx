"use client";

import React from "react";
import { Scene } from "@/lib/api";
import { Film, Clock, ArrowUpRight, AlertTriangle, MessageSquareText } from "lucide-react";
import { cn } from "@/lib/utils";

interface SceneCardProps {
  scene: Scene;
  isSelected: boolean;
  onSelect: (scene: Scene) => void;
  structureType?: string;
  totalActs?: number;
}

const ACT_COLOR_PALETTE = [
  {
    badgeClass: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    cardAccent: "group-hover:border-emerald-500/50",
    numberColor: "text-emerald-400",
  },
  {
    badgeClass: "bg-blue-500/10 text-blue-400 border-blue-500/30",
    cardAccent: "group-hover:border-blue-500/50",
    numberColor: "text-blue-400",
  },
  {
    badgeClass: "bg-violet-500/10 text-violet-400 border-violet-500/30",
    cardAccent: "group-hover:border-violet-500/50",
    numberColor: "text-violet-400",
  },
  {
    badgeClass: "bg-rose-500/10 text-rose-400 border-rose-500/30",
    cardAccent: "group-hover:border-rose-500/50",
    numberColor: "text-rose-400",
  },
  {
    badgeClass: "bg-amber-500/10 text-amber-400 border-amber-500/30",
    cardAccent: "group-hover:border-amber-500/50",
    numberColor: "text-amber-400",
  },
];

const STRUCTURE_ACT_LABELS: Record<string, string[]> = {
  "3_act": ["ACT I • SETUP", "ACT II • CONFRONTATION", "ACT III • RESOLUTION"],
  "4_act": ["ACT I • SETUP", "ACT II-A • RISING", "ACT II-B • DESCENT", "ACT III • CLIMAX"],
  "5_act": [
    "ACT I • EXPOSITION",
    "ACT II • RISING ACTION",
    "ACT III • CLIMAX",
    "ACT IV • FALLING ACTION",
    "ACT V • DENOUEMENT",
  ],
  "youtube_viral": ["ACT I • HOOK", "ACT II • ESCALATION", "ACT III • REVERSAL", "ACT IV • PAYOFF"],
};

export default function SceneCard({
  scene,
  isSelected,
  onSelect,
  structureType,
  totalActs,
}: SceneCardProps) {
  const actNum = Math.max(
    1,
    Math.min(
      5,
      scene.act_number ||
        (scene.scene_number <= 12 ? 1 : scene.scene_number <= 25 ? 2 : scene.scene_number <= 38 ? 3 : 4)
    )
  );
  const resolvedStructure =
    structureType || (totalActs === 5 || actNum === 5 ? "5_act" : totalActs === 3 ? "3_act" : "4_act");
  const labels = STRUCTURE_ACT_LABELS[resolvedStructure] || STRUCTURE_ACT_LABELS["4_act"];
  const label = labels[actNum - 1] || `ACT ${actNum} • BEAT`;
  const palette = ACT_COLOR_PALETTE[Math.min(actNum - 1, ACT_COLOR_PALETTE.length - 1)];
  const actInfo = { label, ...palette };

  const dialoguePreview = (scene.dialogue || "").trim();

  return (
    <div
      onClick={() => onSelect(scene)}
      className={cn(
        "group cursor-pointer p-3.5 rounded-xl bg-panel border transition-all text-left flex flex-col justify-between min-h-[160px] shadow-sm relative overflow-hidden",
        isSelected
          ? "border-amber-500 bg-panel/90 shadow-glow"
          : cn("border-border hover:bg-elevated/70", actInfo.cardAccent)
      )}
    >
      {/* Top Bar: Scene Number, Act Badge, Status */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <span
            className={cn(
              "font-mono text-xs font-bold px-1.5 py-0.5 rounded bg-canvas border border-border",
              actInfo.numberColor
            )}
          >
            #{scene.scene_number.toString().padStart(scene.scene_number >= 100 ? 3 : 2, "0")}
          </span>
          <span
            className={cn(
              "text-[9px] font-mono px-1.5 py-0.5 rounded border font-semibold",
              actInfo.badgeClass
            )}
          >
            {actInfo.label}
          </span>
        </div>

        <div className="flex items-center gap-1">
          <span
            className={cn(
              "text-[9px] font-mono px-1.5 py-0.2 rounded uppercase font-bold flex items-center gap-1",
              scene.status === "FALLBACK"
                ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                : scene.status === "QC_PASSED" || scene.status === "COMPLETED"
                ? "bg-emerald-500/20 text-emerald-400"
                : scene.status === "GENERATING"
                ? "bg-amber-500/20 text-amber-400"
                : "bg-canvas text-obsidian-muted border border-border/80"
            )}
            title={scene.status === "FALLBACK" ? "Procedural Fallback (Click Blueprint to Retry Act)" : undefined}
          >
            {scene.status === "FALLBACK" && <AlertTriangle className="w-2.5 h-2.5" />}
            <span>{scene.status || "PLANNED"}</span>
          </span>
          <ArrowUpRight className="w-3.5 h-3.5 text-obsidian-muted group-hover:text-amber-400 transition-colors" />
        </div>
      </div>

      {/* Visual Preview Keyframe Thumbnail */}
      {scene.preview_url && (
        <div className="relative w-full aspect-video rounded-lg overflow-hidden border border-border my-2 bg-canvas group/img">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={scene.preview_url}
            alt={`Scene ${scene.scene_number} Preview`}
            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
            loading="lazy"
          />
          {scene.preview_provider && (
            <span className="absolute bottom-1 right-1 px-1.5 py-0.5 rounded bg-black/80 text-[8px] font-mono text-amber-400 font-bold uppercase backdrop-blur-xs border border-white/10">
              {scene.preview_provider === "google_flow" ? "FLOW" : scene.preview_provider}
            </span>
          )}
        </div>
      )}

      {/* Middle: Slugline & Narrative Beat Goal */}
      <div className="my-2.5 space-y-1">
        <div className="font-mono text-xs font-bold text-obsidian-primary truncate group-hover:text-amber-400 transition-colors">
          {scene.slugline || `SCENE ${scene.scene_number.toString().padStart(2, "0")}`}
        </div>
        <p className="text-[11px] text-obsidian-secondary line-clamp-2 leading-tight font-sans">
          {scene.narrative_goal || "Dramatic progression beat for Hollywood narrative curve."}
        </p>
        {dialoguePreview && (
          <div className="flex items-center gap-1 pt-0.5 text-[10px] font-mono text-amber-300/90 truncate">
            <MessageSquareText className="w-3 h-3 text-amber-400 shrink-0" />
            <span className="truncate">{dialoguePreview}</span>
          </div>
        )}
      </div>

      {/* Bottom Footer: Target Duration & Shot Count */}
      <div className="pt-2 border-t border-border/60 flex items-center justify-between text-[10px] font-mono text-obsidian-muted">
        <div className="flex items-center gap-1">
          <Clock className="w-3 h-3 text-amber-500" />
          <span>{scene.duration_target || 5.0}s target</span>
        </div>

        <div className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-canvas border border-border">
          <Film className="w-3 h-3 text-obsidian-secondary" />
          <span>{scene.shots_count || 1} Shots</span>
        </div>
      </div>
    </div>
  );
}
