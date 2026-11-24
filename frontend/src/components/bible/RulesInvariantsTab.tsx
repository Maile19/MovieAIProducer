"use client";

import React, { useState, useEffect } from "react";
import {
  ShieldCheck,
  Plus,
  Trash2,
  Save,
  Sparkles,
  Flame,
  Loader2,
  AlertCircle,
  AlertTriangle,
  Lock,
  Clapperboard,
  Users,
  Film,
  Layers,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { api, RulesGenerationMeta } from "@/lib/api";

interface RulesInvariantsTabProps {
  worldRules: Record<string, any>;
  isLocked?: boolean;
  onSave?: (rules: Record<string, any>) => void;
  projectId?: string;
  project?: any;
  characters?: any[];
  onRefresh?: () => Promise<void> | void;
}

export default function RulesInvariantsTab({
  worldRules,
  isLocked = false,
  onSave,
  projectId,
  project,
  characters = [],
  onRefresh,
}: RulesInvariantsTabProps) {
  // Read initial rules resiliently from dual keys (continuity_rules / continuity_laws, negative_prompts / prompt_negatives)
  // Purged: 100% of hardcoded Cyberpunk mock laws and static negatives. Defaults to [] to support Empty State.
  const initialLaws: string[] =
    Array.isArray(worldRules?.continuity_rules) && worldRules.continuity_rules.length > 0
      ? worldRules.continuity_rules
      : Array.isArray(worldRules?.continuity_laws) && worldRules.continuity_laws.length > 0
      ? worldRules.continuity_laws
      : [];

  const initialNegatives: string[] =
    Array.isArray(worldRules?.negative_prompts) && worldRules.negative_prompts.length > 0
      ? worldRules.negative_prompts
      : Array.isArray(worldRules?.prompt_negatives) && worldRules.prompt_negatives.length > 0
      ? worldRules.prompt_negatives
      : [];

  const [continuityLaws, setContinuityLaws] = useState<string[]>(initialLaws);
  const [promptNegatives, setPromptNegatives] = useState<string[]>(initialNegatives);
  const [newLaw, setNewLaw] = useState("");
  const [newNegative, setNewNegative] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState(false);
  const [showNotes, setShowNotes] = useState(false);
  const [additionalNotes, setAdditionalNotes] = useState("");

  // Refinement 2: Instant React State Synchronization via useEffect whenever worldRules changes
  useEffect(() => {
    const nextLaws =
      Array.isArray(worldRules?.continuity_rules) && worldRules.continuity_rules.length > 0
        ? worldRules.continuity_rules
        : Array.isArray(worldRules?.continuity_laws) && worldRules.continuity_laws.length > 0
        ? worldRules.continuity_laws
        : [];

    const nextNegatives =
      Array.isArray(worldRules?.negative_prompts) && worldRules.negative_prompts.length > 0
        ? worldRules.negative_prompts
        : Array.isArray(worldRules?.prompt_negatives) && worldRules.prompt_negatives.length > 0
        ? worldRules.prompt_negatives
        : [];

    if (nextLaws.length > 0 || nextNegatives.length > 0) {
      setContinuityLaws(nextLaws);
      setPromptNegatives(nextNegatives);
    }
  }, [
    worldRules?.continuity_rules,
    worldRules?.continuity_laws,
    worldRules?.negative_prompts,
    worldRules?.prompt_negatives,
  ]);

  const rulesGenerationMeta: RulesGenerationMeta | undefined = worldRules?.rules_generation_meta;
  const hasData = continuityLaws.length > 0 || promptNegatives.length > 0;

  // Refinement 4: Unified Context Linked Strip counts matching WorldPropsTab
  const charsCount =
    characters.length || rulesGenerationMeta?.context_ingested?.characters_count || 0;
  const environmentsCount = Array.isArray(worldRules?.environments)
    ? worldRules.environments.length
    : rulesGenerationMeta?.context_ingested?.environments_count || 0;
  const propsCount = Array.isArray(worldRules?.props)
    ? worldRules.props.length
    : rulesGenerationMeta?.context_ingested?.props_count || 0;
  const scenesCount =
    project?.stats?.scenes_count || rulesGenerationMeta?.context_ingested?.scenes_count || 0;
  const styleCode =
    project?.target_style_code ||
    rulesGenerationMeta?.context_ingested?.style_code ||
    "#Style 01";

  // Refinement 1: Non-Destructive Manual Save Rules + Dual-Key Sync
  const handleSaveAll = () => {
    if (!onSave) return;
    onSave({
      ...worldRules,
      continuity_rules: continuityLaws,
      continuity_laws: continuityLaws,
      negative_prompts: promptNegatives,
      prompt_negatives: promptNegatives,
    });
    setSaveSuccessMsg(true);
    setTimeout(() => setSaveSuccessMsg(false), 3000);
  };

  const handleAddLaw = () => {
    if (!newLaw.trim() || isLocked) return;
    setContinuityLaws((prev) => [...prev, newLaw.trim()]);
    setNewLaw("");
  };

  const handleRemoveLaw = (index: number) => {
    if (isLocked) return;
    setContinuityLaws((prev) => prev.filter((_, i) => i !== index));
  };

  const handleAddNegative = () => {
    if (!newNegative.trim() || isLocked) return;
    setPromptNegatives((prev) => [...prev, newNegative.trim()]);
    setNewNegative("");
  };

  const handleRemoveNegative = (index: number) => {
    if (isLocked) return;
    setPromptNegatives((prev) => prev.filter((_, i) => i !== index));
  };

  // Refinement 2: Instant React State Synchronization from POST response
  const handleGenerate = async () => {
    if (!projectId || isLocked || isGenerating) return;

    try {
      setIsGenerating(true);
      setErrorMsg(null);
      const res = await api.bible.generateRulesInvariants(projectId, {
        additional_notes: additionalNotes.trim() || undefined,
      });

      // Immediately update local continuityLaws and promptNegatives state
      const laws = res.continuity_rules || res.continuity_laws || [];
      const negs = res.negative_prompts || res.prompt_negatives || [];
      setContinuityLaws(laws);
      setPromptNegatives(negs);

      if (onRefresh) {
        await onRefresh();
      }
    } catch (err: any) {
      setErrorMsg(
        err?.message ||
          "Failed to generate visual continuity rules and prompt negatives via Polya AI Director."
      );
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="space-y-6 font-sans w-full max-w-full overflow-hidden">
      {/* =========================================================================
       * Header Bar: Polya AI Director + Provenance Badge + Action Controls
       * ========================================================================= */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl bg-panel border border-border">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-cinzel text-sm sm:text-base font-bold uppercase tracking-wider text-obsidian-primary flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-amber-500 shrink-0" />
              <span>Polya AI Director — Rules &amp; Invariants Engine</span>
            </h3>

            {hasData && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-panel border border-amber-500/30 text-amber-400 font-semibold shadow-sm">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shrink-0" />
                <span>
                  {continuityLaws.length} Laws &bull; {promptNegatives.length} Exclusions
                </span>
              </span>
            )}

            {/* Provenance Badge */}
            {rulesGenerationMeta && (
              rulesGenerationMeta.engine === "polya_ai_director_llm" ? (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-semibold shadow-sm">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />
                  <span>
                    Polya AI Director &bull; Live LLM ({rulesGenerationMeta.model || "geminis"})
                  </span>
                </span>
              ) : (
                <span
                  className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-amber-500/10 border border-amber-500/30 text-amber-400 font-semibold shadow-sm"
                  title={rulesGenerationMeta.fallback_reason || "Contextual procedural synthesis"}
                >
                  <AlertTriangle className="w-3 h-3 text-amber-400 shrink-0" />
                  <span>Procedural Fallback</span>
                </span>
              )
            )}
          </div>

          <p className="text-xs font-mono text-obsidian-muted break-words leading-relaxed">
            Hard visual invariants, biometric continuity laws, and algorithmic negative exclusions enforced across all 50 scenes and generative engines.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2 shrink-0 pt-1 sm:pt-0">
          {isLocked ? (
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-panel border border-border text-obsidian-muted font-mono text-xs">
              <Lock className="w-3.5 h-3.5 text-amber-500/70" />
              <span>DNA Frozen</span>
            </span>
          ) : (
            <>
              {hasData && projectId && (
                <button
                  type="button"
                  onClick={handleGenerate}
                  disabled={isGenerating}
                  className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-canvas hover:bg-elevated border border-amber-500/40 text-amber-400 hover:text-amber-300 disabled:opacity-50 font-mono font-bold text-xs transition-colors shadow-sm shrink-0"
                  title="Re-synthesize all visual continuity laws and negative exclusions via Polya AI Director"
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
              )}

              {hasData && (
                <button
                  type="button"
                  onClick={handleSaveAll}
                  className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-xs transition-all shadow-glow shrink-0"
                >
                  <Save className="w-3.5 h-3.5" />
                  <span>Save Rules</span>
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* =========================================================================
       * Context Linked Strip (Full Context Counts matching WorldPropsTab)
       * ========================================================================= */}
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
            <Layers className="w-3 h-3 text-emerald-400 shrink-0" />
            <span>
              {environmentsCount} Envs &bull; {propsCount} Props
            </span>
          </span>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-panel border border-border text-obsidian-secondary text-[11px]">
            <Film className="w-3 h-3 text-purple-400 shrink-0" />
            <span>
              {scenesCount > 0 ? `${scenesCount} Storyboard Scenes` : "50-Scene Arc Blueprint"}
            </span>
          </span>
        </div>

        {rulesGenerationMeta?.generated_at && (
          <span className="text-[10px] text-obsidian-muted">
            Updated:{" "}
            {new Date(rulesGenerationMeta.generated_at).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        )}
      </div>

      {/* Save Success Alert */}
      {saveSuccessMsg && (
        <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2 font-mono">
          <ShieldCheck className="w-4 h-4 shrink-0" />
          <span>Rules and negative prompt exclusions saved and synchronized successfully.</span>
        </div>
      )}

      {/* Error Alert */}
      {errorMsg && (
        <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2 font-mono">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span className="break-words leading-relaxed">{errorMsg}</span>
        </div>
      )}

      {/* Optional Showrunner Directives Toggle */}
      {!isLocked && (
        <div className="rounded-xl bg-panel/70 border border-border p-3 space-y-2">
          <button
            type="button"
            onClick={() => setShowNotes(!showNotes)}
            className="flex items-center justify-between w-full text-xs font-mono text-obsidian-secondary hover:text-amber-400 transition-colors"
          >
            <span className="flex items-center gap-1.5 font-semibold">
              <Sparkles className="w-3.5 h-3.5 text-amber-500" />
              <span>Showrunner Custom Directives (Optional)</span>
            </span>
            {showNotes ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>

          {showNotes && (
            <div className="pt-2">
              <textarea
                value={additionalNotes}
                onChange={(e) => setAdditionalNotes(e.target.value)}
                placeholder="E.g. Strict 35mm anamorphic grain, forbidden modern props, protagonist eye scar must never flip..."
                rows={2}
                className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-xs text-obsidian-primary font-mono placeholder:text-obsidian-muted focus:border-amber-500 focus:outline-none resize-none"
              />
            </div>
          )}
        </div>
      )}

      {/* =========================================================================
       * Interactive Genre-Agnostic Empty State
       * ========================================================================= */}
      {!hasData && (
        <div className="p-6 sm:p-8 rounded-2xl bg-panel border border-dashed border-amber-500/30 text-center space-y-6">
          <div className="max-w-xl mx-auto space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-500 mx-auto">
              <ShieldCheck className="w-6 h-6 animate-pulse" />
            </div>

            <div className="space-y-1.5">
              <h4 className="font-cinzel text-base sm:text-lg font-bold text-obsidian-primary">
                No Visual Continuity Laws or Global Negative Exclusions Synthesized
              </h4>
              <p className="text-xs font-mono text-obsidian-muted leading-relaxed break-words">
                Stage 6 of the Hollywood 16-Stage Pipeline establishes visual invariants, physical continuity boundaries, and negative generative exclusions across all scenes.
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
                    <span className="text-obsidian-secondary">
                      {project.genre || project.settings?.genre || "Cinematic Film"}
                    </span>
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
                    <span>Polya AI Director Synthesizing Rules &amp; Invariants...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>✨ Generate Rules &amp; Invariants (Polya AI Director)</span>
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

      {/* =========================================================================
       * Section 1: Immutable Visual Continuity Laws
       * ========================================================================= */}
      {hasData && (
        <div className="p-4 rounded-xl bg-panel border border-border space-y-4">
          <div className="flex items-center justify-between">
            <label className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-emerald-400" />
              <span>Immutable Visual Continuity Laws</span>
            </label>
            <span className="text-[10px] font-mono text-obsidian-muted">
              {continuityLaws.length} Enforced Laws
            </span>
          </div>

          <div className="space-y-2">
            {continuityLaws.map((law, idx) => (
              <div
                key={idx}
                className="p-3 rounded-lg bg-canvas border border-border/80 flex items-start justify-between gap-3 text-xs font-mono group"
              >
                <div className="flex items-start gap-2.5 min-w-0 flex-1">
                  <span className="w-5 h-5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center justify-center font-bold text-[10px] shrink-0 mt-0.5">
                    {idx + 1}
                  </span>
                  <span className="text-obsidian-primary leading-relaxed font-sans break-words min-w-0">
                    {law}
                  </span>
                </div>

                {!isLocked && (
                  <button
                    type="button"
                    onClick={() => handleRemoveLaw(idx)}
                    className="text-obsidian-muted hover:text-rose-400 opacity-60 sm:opacity-0 group-hover:opacity-100 transition-all p-1 shrink-0"
                    title="Remove Law"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            ))}
          </div>

          {!isLocked && (
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 pt-2">
              <input
                type="text"
                value={newLaw}
                onChange={(e) => setNewLaw(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAddLaw()}
                placeholder="Add new visual continuity invariant law..."
                className="flex-1 px-3 py-2 rounded-lg bg-canvas border border-border text-xs text-obsidian-primary font-mono placeholder:text-obsidian-muted focus:border-amber-500 focus:outline-none"
              />
              <button
                type="button"
                onClick={handleAddLaw}
                disabled={!newLaw.trim()}
                className="px-3.5 py-2 rounded-lg bg-canvas hover:bg-elevated border border-border text-amber-400 text-xs font-bold flex items-center justify-center gap-1 disabled:opacity-50 shrink-0"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Law</span>
              </button>
            </div>
          )}
        </div>
      )}

      {/* =========================================================================
       * Section 2: Global Prompt Negatives & Universal Exclusions
       * ========================================================================= */}
      {hasData && (
        <div className="p-4 rounded-xl bg-panel border border-border space-y-4">
          <div className="flex items-center justify-between">
            <label className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary flex items-center gap-1.5">
              <Flame className="w-4 h-4 text-rose-400" />
              <span>Global Negative Prompts &amp; Universal Exclusions</span>
            </label>
            <span className="text-[10px] font-mono text-obsidian-muted">
              {promptNegatives.length} Negative Clusters
            </span>
          </div>

          <div className="space-y-2">
            {promptNegatives.map((neg, idx) => (
              <div
                key={idx}
                className="p-3 rounded-lg bg-canvas border border-border/80 flex items-start justify-between gap-3 text-xs font-mono group"
              >
                <div className="flex items-start gap-2.5 min-w-0 flex-1">
                  <span className="w-5 h-5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/30 flex items-center justify-center font-bold text-[10px] shrink-0 mt-0.5">
                    &times;
                  </span>
                  <span className="text-obsidian-secondary leading-relaxed font-mono text-[11px] break-words min-w-0">
                    {neg}
                  </span>
                </div>

                {!isLocked && (
                  <button
                    type="button"
                    onClick={() => handleRemoveNegative(idx)}
                    className="text-obsidian-muted hover:text-rose-400 opacity-60 sm:opacity-0 group-hover:opacity-100 transition-all p-1 shrink-0"
                    title="Remove Exclusion"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            ))}
          </div>

          {!isLocked && (
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 pt-2">
              <input
                type="text"
                value={newNegative}
                onChange={(e) => setNewNegative(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAddNegative()}
                placeholder="Add comma-separated negative tokens to universally exclude..."
                className="flex-1 px-3 py-2 rounded-lg bg-canvas border border-border text-xs text-obsidian-primary font-mono placeholder:text-obsidian-muted focus:border-rose-500 focus:outline-none"
              />
              <button
                type="button"
                onClick={handleAddNegative}
                disabled={!newNegative.trim()}
                className="px-3.5 py-2 rounded-lg bg-canvas hover:bg-elevated border border-border text-rose-400 text-xs font-bold flex items-center justify-center gap-1 disabled:opacity-50 shrink-0"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Exclusion</span>
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
