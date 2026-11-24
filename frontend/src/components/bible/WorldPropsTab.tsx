"use client";

import React, { useState } from "react";
import {
  Package,
  MapPin,
  Sparkles,
  Loader2,
  AlertCircle,
  AlertTriangle,
  Compass,
  Lock,
  Clapperboard,
  Users,
  Film,
} from "lucide-react";
import { api, EnvironmentItem, PropItem, GenerationMeta } from "@/lib/api";

interface WorldPropsTabProps {
  worldRules: Record<string, any>;
  isLocked?: boolean;
  onSave?: (rules: Record<string, any>) => void;
  project?: any;
  characters?: any[];
  projectId?: string;
  onRefresh?: () => Promise<void> | void;
}

export default function WorldPropsTab({
  worldRules,
  isLocked = false,
  onSave: _onSave,
  project,
  characters = [],
  projectId,
  onRefresh,
}: WorldPropsTabProps) {
  const [isGenerating, setIsGenerating] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const environments: EnvironmentItem[] = Array.isArray(worldRules?.environments)
    ? worldRules.environments
    : [];
  const propsList: PropItem[] = Array.isArray(worldRules?.props) ? worldRules.props : [];
  const generationMeta: GenerationMeta | undefined = worldRules?.generation_meta;

  const hasData = environments.length > 0 || propsList.length > 0;

  // Derive counts for the Context Linked strip
  const charsCount =
    characters.length ||
    generationMeta?.context_ingested?.characters_count ||
    0;
  const scenesCount =
    project?.stats?.scenes_count ||
    generationMeta?.context_ingested?.scenes_count ||
    0;
  const styleCode =
    project?.target_style_code ||
    generationMeta?.context_ingested?.style_code ||
    "#Style 01";

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
      setErrorMsg(
        err?.message || "Failed to generate world environments and hero props via Polya AI Director."
      );
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="space-y-6 font-sans">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl bg-panel border border-border">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-cinzel text-sm sm:text-base font-bold uppercase tracking-wider text-obsidian-primary flex items-center gap-2">
              <Compass className="w-4 h-4 text-amber-500 shrink-0" />
              <span>Polya AI Director — World &amp; Props Engine</span>
            </h3>

            {hasData && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-panel border border-amber-500/30 text-amber-400 font-semibold shadow-sm">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shrink-0" />
                <span>
                  {environments.length} Envs &bull; {propsList.length} Props
                </span>
              </span>
            )}

            {/* Provenance Badge */}
            {generationMeta && (
              generationMeta.engine === "polya_ai_director_llm" ? (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-semibold shadow-sm">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />
                  <span>Polya AI Director &bull; Live LLM ({generationMeta.model || "geminis"})</span>
                </span>
              ) : (
                <span
                  className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-amber-500/10 border border-amber-500/30 text-amber-400 font-semibold shadow-sm"
                  title={generationMeta.fallback_reason || "Contextual procedural synthesis"}
                >
                  <AlertTriangle className="w-3 h-3 text-amber-400 shrink-0" />
                  <span>Procedural Fallback</span>
                </span>
              )
            )}
          </div>

          <p className="text-xs font-mono text-obsidian-muted mt-1">
            Hollywood Production Design standard: 5 Key Environments (#Env 01–05) and 5 Signature Hero Props (#Prop 01–05) anchored to visual DNA &amp; cast continuity.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2 shrink-0">
          {isLocked ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-panel border border-border text-obsidian-muted font-mono text-xs">
              <Lock className="w-3.5 h-3.5 text-amber-500/70" />
              <span>DNA Frozen</span>
            </span>
          ) : (
            hasData && projectId && (
              <button
                type="button"
                onClick={handleGenerate}
                disabled={isGenerating}
                className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-canvas font-mono font-bold text-xs transition-colors shadow-sm shrink-0"
                title="Re-generate all 5 environments and 5 hero props using Polya AI Director"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Synthesizing...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>✨ Re-generate via Polya AI Director</span>
                  </>
                )}
              </button>
            )
          )}
        </div>
      </div>

      {/* Context Linked Strip */}
      <div className="p-3 rounded-xl bg-canvas border border-border flex flex-wrap items-center justify-between gap-2.5 font-mono text-xs">
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          <span className="text-[10px] text-obsidian-muted uppercase font-bold tracking-wider">
            Context Linked:
          </span>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-panel border border-border text-amber-400 font-semibold text-[11px]">
            <Clapperboard className="w-3 h-3 text-amber-500 shrink-0" />
            <span>Style: {styleCode}</span>
          </span>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-panel border border-border text-obsidian-secondary text-[11px]">
            <Users className="w-3 h-3 text-cyan-400 shrink-0" />
            <span>{charsCount} Cast Characters</span>
          </span>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-panel border border-border text-obsidian-secondary text-[11px]">
            <Film className="w-3 h-3 text-purple-400 shrink-0" />
            <span>{scenesCount > 0 ? `${scenesCount} Storyboard Scenes` : "50-Scene Arc Blueprint"}</span>
          </span>
        </div>

        {generationMeta?.generated_at && (
          <span className="text-[10px] text-obsidian-muted">
            Updated: {new Date(generationMeta.generated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </span>
        )}
      </div>

      {errorMsg && (
        <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2 font-mono">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span className="break-words">{errorMsg}</span>
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
                No World Environments or Hero Props Synthesized
              </h4>
              <p className="text-xs font-mono text-obsidian-muted leading-relaxed">
                Stage 6 of the Hollywood 16-Stage Pipeline requires at least 1 key environment and signature hero prop to establish narrative and tactile continuity.
              </p>
            </div>

            {project && (
              <div className="p-4 rounded-xl bg-canvas border border-border text-left font-mono text-xs space-y-2">
                <div className="flex items-center justify-between border-b border-border/80 pb-1.5">
                  <span className="text-[10px] text-obsidian-muted uppercase">Active Production Context</span>
                  <span className="text-amber-400 font-bold truncate ml-2">{project.title}</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] pt-1">
                  <div>
                    <span className="text-obsidian-muted">Genre/Tone: </span>
                    <span className="text-obsidian-secondary">{project.genre || project.settings?.genre || "Cinematic"}</span>
                  </div>
                  <div>
                    <span className="text-obsidian-muted">Style Code: </span>
                    <span className="text-obsidian-secondary">{styleCode}</span>
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
                    <span>Polya AI Director Synthesizing 5 Envs &amp; 5 Props...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>✨ Generate World &amp; Props (Polya AI Director)</span>
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
            {environments.map((env, idx) => (
              <div
                key={env.code || `env_${idx}`}
                className="p-3.5 rounded-xl bg-canvas border border-border hover:border-amber-500/40 transition-all space-y-2.5 font-mono text-xs"
              >
                <div className="flex items-start justify-between border-b border-border/80 pb-2 gap-2">
                  <div className="flex items-center gap-1.5 shrink-0">
                    <span className="font-bold text-amber-400">{env.code}</span>
                    {env.lighting_code && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-500/10 border border-blue-500/20 text-blue-400 font-bold">
                        {env.lighting_code}
                      </span>
                    )}
                  </div>
                  <span className="text-[11px] font-bold text-obsidian-primary font-sans break-words text-right">
                    {env.name}
                  </span>
                </div>

                {env.linked_scenes && (
                  <div className="text-[10px] text-amber-500/90 bg-amber-500/5 px-2 py-1 rounded border border-amber-500/10">
                    <span className="font-semibold uppercase text-[9px] text-obsidian-muted block">Linked Scenes:</span>
                    <span className="font-sans leading-tight">{env.linked_scenes}</span>
                  </div>
                )}

                <div className="space-y-1">
                  <span className="text-[10px] text-obsidian-muted uppercase">Architecture:</span>
                  <p className="text-[11px] text-obsidian-secondary leading-relaxed font-sans break-words">
                    {env.architecture}
                  </p>
                </div>

                <div className="space-y-1">
                  <span className="text-[10px] text-amber-500 uppercase">Atmosphere:</span>
                  <p className="text-[11px] text-obsidian-secondary leading-relaxed font-sans break-words">
                    {env.atmosphere}
                  </p>
                </div>

                <div className="space-y-1">
                  <span className="text-[10px] text-blue-400 uppercase">Lighting &amp; Audio:</span>
                  <p className="text-[10px] text-obsidian-muted leading-relaxed font-sans break-words">
                    {env.lighting_and_audio || (env.lighting && env.audio ? `${env.lighting} • ${env.audio}` : env.lighting || env.audio || "Standard setup")}
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
            {propsList.map((prp, idx) => (
              <div
                key={prp.code || `prop_${idx}`}
                className="p-3.5 rounded-xl bg-canvas border border-border hover:border-amber-500/40 transition-all space-y-2.5 font-mono text-xs"
              >
                <div className="flex items-start justify-between border-b border-border/80 pb-2 gap-2">
                  <span className="font-bold text-amber-400 shrink-0">{prp.code}</span>
                  <span className="text-[11px] font-bold text-obsidian-primary font-sans break-words text-right">
                    {prp.name}
                  </span>
                </div>

                {prp.owner_character && (
                  <div className="text-[10px] text-cyan-400/90 bg-cyan-500/5 px-2 py-1 rounded border border-cyan-500/10 flex items-center gap-1.5">
                    <span className="text-[9px] uppercase text-obsidian-muted font-bold">Owner:</span>
                    <span className="font-sans font-semibold text-cyan-300 truncate">{prp.owner_character}</span>
                  </div>
                )}

                <div className="space-y-1">
                  <span className="text-[10px] text-obsidian-muted uppercase">Materiality &amp; Wear:</span>
                  <p className="text-[11px] text-obsidian-secondary leading-relaxed font-sans break-words">
                    {prp.material_and_wear || prp.material}
                  </p>
                </div>

                <div className="space-y-1">
                  <span className="text-[10px] text-emerald-400 uppercase">Narrative Utility:</span>
                  <p className="text-[11px] text-obsidian-secondary leading-relaxed font-sans break-words">
                    {prp.narrative_utility || prp.weight}
                  </p>
                </div>

                <div className="space-y-1">
                  <span className="text-[10px] text-amber-500 uppercase">Tactile Interaction:</span>
                  <p className="text-[10px] text-obsidian-muted leading-relaxed font-sans break-words">
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
