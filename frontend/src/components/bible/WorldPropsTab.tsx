"use client";

import React, { useState } from "react";
import { Globe, Package, MapPin, Sparkles, Loader2, AlertCircle, Compass } from "lucide-react";
import { api } from "@/lib/api";

interface WorldPropsTabProps {
  worldRules: Record<string, any>;
  isLocked?: boolean;
  onSave?: (rules: Record<string, any>) => void;
  project?: any;
  projectId?: string;
  onRefresh?: () => Promise<void> | void;
}

export default function WorldPropsTab({
  worldRules,
  isLocked = false,
  onSave: _onSave,
  project,
  projectId,
  onRefresh,
}: WorldPropsTabProps) {
  const [isGenerating, setIsGenerating] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const environments: any[] = Array.isArray(worldRules?.environments) ? worldRules.environments : [];
  const propsList: any[] = Array.isArray(worldRules?.props) ? worldRules.props : [];
  const hasData = environments.length > 0 || propsList.length > 0;

  const handleGenerate = async () => {
    if (!projectId || isLocked || isGenerating) return;

    try {
      setIsGenerating(true);
      setErrorMsg(null);
      await api.bible.generateWorldProps(projectId);
      if (onRefresh) {
        await onRefresh();
      }
    } catch (err: any) {
      setErrorMsg(err?.message || "Failed to generate world environments and hero props via Polya AI.");
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="space-y-6 font-sans">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl bg-panel border border-border">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-cinzel text-sm sm:text-base font-bold uppercase tracking-wider text-obsidian-primary flex items-center gap-2">
              <Globe className="w-4 h-4 text-amber-500" />
              <span>World Environments &amp; Signature Hero Props</span>
            </h3>
            {hasData && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-panel border border-amber-500/30 text-amber-400 font-semibold shadow-sm">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shrink-0" />
                <span>{environments.length} Envs &bull; {propsList.length} Props</span>
              </span>
            )}
          </div>
          <p className="text-xs font-mono text-obsidian-muted mt-0.5">
            Maintains visual architecture, lighting anchors, and signature tactile continuity across scenes.
          </p>
        </div>

        {hasData && !isLocked && projectId && (
          <button
            type="button"
            onClick={handleGenerate}
            disabled={isGenerating}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-canvas font-mono font-bold text-xs transition-colors shadow-sm shrink-0"
            title="Re-generate all 5 environments and 5 hero props using Polya AI Screenwriter"
          >
            {isGenerating ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Generating...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5" />
                <span>✨ Re-generate World &amp; Props</span>
              </>
            )}
          </button>
        )}
      </div>

      {errorMsg && (
        <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2 font-mono">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Interactive Empty State */}
      {!hasData && (
        <div className="p-6 sm:p-8 rounded-2xl bg-panel border border-dashed border-amber-500/30 text-center space-y-6">
          <div className="max-w-xl mx-auto space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-500 mx-auto">
              <Compass className="w-6 h-6 animate-pulse" />
            </div>

            <div className="space-y-1.5">
              <h4 className="font-cinzel text-base sm:text-lg font-bold text-obsidian-primary">
                No World Environments or Hero Props Defined
              </h4>
              <p className="text-xs font-mono text-obsidian-muted leading-relaxed">
                Stage 6 of the Hollywood 16-Stage Pipeline requires at least 1 key environment and signature hero prop to establish narrative and tactile continuity.
              </p>
            </div>

            {project && (
              <div className="p-4 rounded-xl bg-canvas border border-border text-left font-mono text-xs space-y-2">
                <div className="flex items-center justify-between border-b border-border/80 pb-1.5">
                  <span className="text-[10px] text-obsidian-muted uppercase">Active Production Context</span>
                  <span className="text-amber-400 font-bold">{project.title}</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] pt-1">
                  <div>
                    <span className="text-obsidian-muted">Genre/Tone: </span>
                    <span className="text-obsidian-secondary">{project.genre || project.settings?.genre || "Cinematic"}</span>
                  </div>
                  <div>
                    <span className="text-obsidian-muted">Style Code: </span>
                    <span className="text-obsidian-secondary">{project.target_style_code || "STYLE_01"}</span>
                  </div>
                </div>
                {project.synopsis && (
                  <p className="text-[11px] text-obsidian-secondary italic line-clamp-2 pt-1 border-t border-border/40">
                    &ldquo;{project.synopsis}&rdquo;
                  </p>
                )}
              </div>
            )}

            <div>
              <button
                type="button"
                onClick={handleGenerate}
                disabled={isGenerating || isLocked || !projectId}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-canvas font-mono font-bold text-xs sm:text-sm transition-all shadow-glow hover:scale-[1.02] active:scale-[0.98]"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Polya AI Generating 5 Envs &amp; 5 Props...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>✨ Generate World Environments &amp; Hero Props (Polya AI)</span>
                  </>
                )}
              </button>
              {isLocked && (
                <p className="text-[10px] font-mono text-rose-400 mt-2">
                  Master Production Bible is locked (DNA Frozen). Unlock or create a new revision to generate.
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Environments Section (#Env 01 - 05) */}
      {environments.length > 0 && (
        <div className="p-4 rounded-xl bg-panel border border-border space-y-4">
          <div className="flex items-center justify-between">
            <label className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary flex items-center gap-1.5">
              <MapPin className="w-4 h-4 text-amber-500" />
              <span>Key Environments (#Env 01 - #Env 05)</span>
            </label>
            <span className="text-[10px] font-mono text-obsidian-muted">
              {environments.length} Core Narrative Locations
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {environments.map((env) => (
              <div
                key={env.code || env.name}
                className="p-3.5 rounded-xl bg-canvas border border-border hover:border-amber-500/40 transition-all space-y-2.5 font-mono text-xs"
              >
                <div className="flex items-center justify-between border-b border-border/80 pb-2">
                  <span className="font-bold text-amber-400">{env.code}</span>
                  <span className="text-[11px] font-bold text-obsidian-primary font-sans truncate ml-2">
                    {env.name}
                  </span>
                </div>

                <div className="space-y-1">
                  <span className="text-[10px] text-obsidian-muted uppercase">Architecture:</span>
                  <p className="text-[11px] text-obsidian-secondary leading-tight font-sans">
                    {env.architecture}
                  </p>
                </div>

                <div className="space-y-1">
                  <span className="text-[10px] text-amber-500 uppercase">Atmosphere:</span>
                  <p className="text-[11px] text-obsidian-secondary leading-tight font-sans">
                    {env.atmosphere}
                  </p>
                </div>

                <div className="space-y-1">
                  <span className="text-[10px] text-blue-400 uppercase">Lighting &amp; Audio:</span>
                  <p className="text-[10px] text-obsidian-muted leading-tight font-sans">
                    {env.lighting} &bull; {env.audio}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Signature Props Section (#Prop 01 - 05) */}
      {propsList.length > 0 && (
        <div className="p-4 rounded-xl bg-panel border border-border space-y-4">
          <div className="flex items-center justify-between">
            <label className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary flex items-center gap-1.5">
              <Package className="w-4 h-4 text-amber-500" />
              <span>Signature Hero Props (#Prop 01 - #Prop 05)</span>
            </label>
            <span className="text-[10px] font-mono text-obsidian-muted">
              {propsList.length} Tactile Materiality Items
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {propsList.map((prp) => (
              <div
                key={prp.code || prp.name}
                className="p-3.5 rounded-xl bg-canvas border border-border hover:border-amber-500/40 transition-all space-y-2.5 font-mono text-xs"
              >
                <div className="flex items-center justify-between border-b border-border/80 pb-2">
                  <span className="font-bold text-amber-400">{prp.code}</span>
                  <span className="text-[11px] font-bold text-obsidian-primary font-sans truncate ml-2">
                    {prp.name}
                  </span>
                </div>

                <div className="space-y-1">
                  <span className="text-[10px] text-obsidian-muted uppercase">Materiality:</span>
                  <p className="text-[11px] text-obsidian-secondary leading-tight font-sans">
                    {prp.material}
                  </p>
                </div>

                <div className="space-y-1">
                  <span className="text-[10px] text-emerald-400 uppercase">Narrative Function:</span>
                  <p className="text-[11px] text-obsidian-secondary leading-tight font-sans">
                    {prp.weight}
                  </p>
                </div>

                <div className="space-y-1">
                  <span className="text-[10px] text-amber-500 uppercase">Tactile Interaction:</span>
                  <p className="text-[10px] text-obsidian-muted leading-tight font-sans">
                    {prp.action}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
