"use client";

import React from "react";
import { Scene } from "@/lib/api";
import { Film, Clock, ArrowUpRight, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

interface SceneCardProps {
  scene: Scene;
  isSelected: boolean;
  onSelect: (scene: Scene) => void;
}

export default function SceneCard({ scene, isSelected, onSelect }: SceneCardProps) {
  // Determine act number (1, 2, 3, 4)
  const actNum = scene.act_number || (scene.scene_number <= 12 ? 1 : scene.scene_number <= 25 ? 2 : scene.scene_number <= 38 ? 3 : 4);

  // Act color theme mapping
  const getActBadge = () => {
    switch (actNum) {
      case 1:
        return {
          label: "ACT I &bull; SETUP",
          badgeClass: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
          cardAccent: "group-hover:border-emerald-500/50",
          numberColor: "text-emerald-400",
        };
      case 2:
        return {
          label: "ACT II-A &bull; RISING",
          badgeClass: "bg-blue-500/10 text-blue-400 border-blue-500/30",
          cardAccent: "group-hover:border-blue-500/50",
          numberColor: "text-blue-400",
        };
      case 3:
        return {
          label: "ACT II-B &bull; DESCENT",
          badgeClass: "bg-violet-500/10 text-violet-400 border-violet-500/30",
          cardAccent: "group-hover:border-violet-500/50",
          numberColor: "text-violet-400",
        };
      case 4:
      default:
        return {
          label: "ACT III &bull; CLIMAX",
          badgeClass: "bg-rose-500/10 text-rose-400 border-rose-500/30",
          cardAccent: "group-hover:border-rose-500/50",
          numberColor: "text-rose-400",
        };
    }
  };

  const actInfo = getActBadge();

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
            dangerouslySetInnerHTML={{ __html: actInfo.label }}
          />
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

      {/* Middle: Slugline & Narrative Beat Goal */}
      <div className="my-2.5 space-y-1">
        <div className="font-mono text-xs font-bold text-obsidian-primary truncate group-hover:text-amber-400 transition-colors">
          {scene.slugline || `SCENE ${scene.scene_number.toString().padStart(2, "0")}`}
        </div>
        <p className="text-[11px] text-obsidian-secondary line-clamp-2 leading-tight font-sans">
          {scene.narrative_goal || "Dramatic progression beat for Hollywood narrative curve."}
        </p>
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
