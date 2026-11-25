"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import AppShell from "@/components/layout/AppShell";
import VisualDnaTab from "@/components/bible/VisualDnaTab";
import CharacterMatrixTab from "@/components/bible/CharacterMatrixTab";
import WorldPropsTab from "@/components/bible/WorldPropsTab";
import RulesInvariantsTab from "@/components/bible/RulesInvariantsTab";
import RevisionLockTab from "@/components/bible/RevisionLockTab";
import { api, Project, MasterProductionBible, Character } from "@/lib/api";
import { formatMpbVersion } from "@/lib/versioning";
import {
  BookOpen,
  Palette,
  Users,
  Globe,
  ShieldCheck,
  Lock,
  Unlock,
  ArrowLeft,
  Loader2,
  RefreshCw,
  Film,
  Grid,
  AlertTriangle,
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function ProductionBiblePage() {
  const params = useParams();
  const projectId = (params?.id as string) || "";

  const [activeTab, setActiveTab] = useState<
    "visual_dna" | "character_matrix" | "world_props" | "rules_invariants" | "revision_lock"
  >("visual_dna");

  const [project, setProject] = useState<Project | null>(null);
  const [bible, setBible] = useState<MasterProductionBible | null>(null);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const hasLoadedRef = useRef(false);

  const loadBibleData = useCallback(async (options?: { silent?: boolean }) => {
    try {
      const isInitial = !hasLoadedRef.current;
      if (isInitial && !options?.silent) {
        setIsLoading(true);
      }
      setLoadError(null);
      const [projRes, bibleRes, charRes] = await Promise.allSettled([
        api.projects.get(projectId),
        api.bible.get(projectId),
        api.bible.listCharacters(projectId),
      ]);

      const errors: string[] = [];

      if (projRes.status === "fulfilled" && projRes.value?.data) {
        setProject(projRes.value.data);
      } else {
        const msg = projRes.status === "rejected" ? projRes.reason?.message : "Project response was empty";
        errors.push(`Project load failed: ${msg || "Unknown error"}`);
      }

      if (bibleRes.status === "fulfilled" && bibleRes.value?.data) {
        setBible(bibleRes.value.data);
      } else {
        const msg = bibleRes.status === "rejected" ? bibleRes.reason?.message : "Bible response was empty";
        errors.push(`Master Production Bible load failed: ${msg || "Unknown error"}`);
      }

      if (charRes.status === "fulfilled" && charRes.value?.data) {
        setCharacters(charRes.value.data);
      }

      if (errors.length > 0) {
        setLoadError(errors.join(" | "));
      }
      hasLoadedRef.current = true;
    } catch (err: any) {
      console.error(err);
      setLoadError(err?.message || "Failed to load Master Production Bible from server.");
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  const handlePatchCharacterAsset = useCallback(
    (characterId: string, slot: string, imageUrl: string, metaPatch?: Record<string, any>) => {
      if (slot === "state") return; // Guard: isolate state patches from turnaround cards
      setCharacters((prev) =>
        prev.map((c) => {
          if (c.id !== characterId) return c;

          const colMap: Record<string, keyof Character> = {
            closeup: "closeup_image_url" as any,
            front: "front_image_url",
            side: "side_image_url",
            three_quarter: "three_quarter_image_url",
            back: "back_image_url",
            tpose: "tpose_image_url",
            action: "action_image_url",
            expression: "expression_image_url",
          };
          const targetCol = colMap[slot];
          if (!targetCol) return c;

          const updatedMetadata = {
            ...(c.sheet_metadata || {}),
            [slot]: {
              image_url: imageUrl,
              status: "completed",
              ...(metaPatch || {}),
            },
          };

          return {
            ...c,
            [targetCol]: imageUrl,
            sheet_metadata: updatedMetadata,
          };
        })
      );
    },
    []
  );

  const handlePatchCharacterStateAsset = useCallback(
    (characterId: string, stateId: string, imageUrl: string, metaPatch?: Record<string, any>) => {
      setCharacters((prev) =>
        prev.map((c) => {
          if (c.id !== characterId) return c;
          const updatedStates = (c.states || []).map((s) =>
            s.id === stateId ? { ...s, image_url: imageUrl, ...(metaPatch || {}) } : s
          );
          return {
            ...c,
            states: updatedStates,
          };
        })
      );
    },
    []
  );

  useEffect(() => {
    if (projectId) {
      loadBibleData();
    }
  }, [projectId, loadBibleData]);

  const handleSaveStyleParameters = async (newParams: Record<string, any>) => {
    if (!bible) return;
    try {
      await api.bible.update(projectId, {
        style_parameters: {
          ...bible.style_parameters,
          ...newParams,
        },
      });
      loadBibleData();
    } catch (err) {
      console.error(err);
    }
  };

  const handleSaveWorldRules = async (newRules: Record<string, any>) => {
    if (!bible) return;
    try {
      await api.bible.update(projectId, {
        world_rules: {
          ...bible.world_rules,
          ...newRules,
        },
      });
      loadBibleData();
    } catch (err) {
      console.error(err);
    }
  };

  const tabs = [
    { id: "visual_dna", label: "Visual DNA", icon: Palette },
    { id: "character_matrix", label: "Character DNA & State Matrix", icon: Users },
    { id: "world_props", label: "World & Props", icon: Globe },
    { id: "rules_invariants", label: "Rules & Invariants", icon: ShieldCheck },
    { id: "revision_lock", label: "Revision Lock & Export", icon: bible?.is_locked ? Lock : Unlock },
  ] as const;

  if (isLoading && !bible && characters.length === 0) {
    return (
      <AppShell activeProjectId={projectId}>
        <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3">
          <Loader2 className="w-8 h-8 text-amber-500 animate-spin" />
          <p className="font-mono text-xs text-obsidian-secondary tracking-widest uppercase">
            Loading Master Production Bible (MPB)...
          </p>
        </div>
      </AppShell>
    );
  }

  if (loadError && (!project || !bible)) {
    return (
      <AppShell activeProjectId={projectId}>
        <div className="max-w-lg mx-auto my-16 p-6 rounded-2xl bg-panel border border-rose-500/40 text-center space-y-4">
          <AlertTriangle className="w-10 h-10 text-rose-400 mx-auto" />
          <h2 className="font-cinzel text-lg font-bold text-obsidian-primary uppercase">
            Failed to Load Master Production Bible
          </h2>
          <p className="text-xs font-mono text-rose-300 leading-relaxed">{loadError}</p>
          <div className="flex items-center justify-center gap-2 pt-2">
            <Link
              href="/dashboard"
              className="px-4 py-2 rounded-lg bg-canvas hover:bg-elevated border border-border text-xs font-mono text-obsidian-secondary"
            >
              Return to Slate
            </Link>
            <button
              type="button"
              onClick={() => loadBibleData()}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-xs font-mono cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Retry Load</span>
            </button>
          </div>
        </div>
      </AppShell>
    );
  }

  const isLocked = bible?.is_locked || false;

  return (
    <AppShell
      activeProjectId={projectId}
      activeProjectTitle={project?.title || "Production Bible"}
      currentStage={project?.operational_stage}
      stageName={project?.stage_name}
    >
      <div className="space-y-5">
        {loadError && (
          <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-between gap-3 text-xs font-mono text-rose-300">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{loadError}</span>
            </div>
            <button
              type="button"
              onClick={() => loadBibleData()}
              className="px-3 py-1 rounded bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 text-rose-200 font-bold shrink-0 cursor-pointer"
            >
              Retry Load
            </button>
          </div>
        )}
        {/* =========================================================================
         * Header: Master Production Bible Title & Context
         * ========================================================================= */}
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 border-b border-border/70 pb-4">
          <div className="space-y-1.5">
            <div>
              <Link
                href="/dashboard"
                className="text-obsidian-muted hover:text-obsidian-primary transition-colors text-xs inline-flex items-center gap-1.5 font-mono"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Slate</span>
              </Link>
            </div>
            <h1 className="font-cinzel text-lg sm:text-xl font-bold text-obsidian-primary uppercase tracking-wider flex items-center gap-2.5">
              <BookOpen className="w-5 h-5 text-amber-500 shrink-0" />
              <span>Master Production Bible (MPB)</span>
            </h1>
            <div className="text-xs font-mono text-obsidian-muted flex flex-wrap items-center gap-x-2 gap-y-1 pt-0.5">
              <span className="text-obsidian-secondary font-medium">{project?.title}</span>
              <span>&bull;</span>
              <span className="text-amber-400 font-semibold">{formatMpbVersion(bible?.version, isLocked).label}</span>
              <span>&bull;</span>
              <span
                className={cn(
                  "font-bold uppercase",
                  isLocked ? "text-rose-400" : "text-emerald-400"
                )}
              >
                {isLocked ? "DNA FROZEN (IMMUTABLE)" : "MUTABLE"}
              </span>
            </div>
          </div>

          {/* Quick Studio Links */}
          <div className="flex flex-wrap items-center gap-2 pt-1 sm:pt-0">
            <Link
              href={`/projects/${projectId}/studio`}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-secondary hover:text-amber-400 text-xs font-medium transition-colors"
            >
              <Film className="w-3.5 h-3.5" />
              <span>NLE Studio</span>
            </Link>
            <Link
              href={`/projects/${projectId}/scenes`}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-secondary hover:text-amber-400 text-xs font-medium transition-colors"
            >
              <Grid className="w-3.5 h-3.5" />
              <span>50-Scene Storyboard</span>
            </Link>
            <button
              type="button"
              onClick={() => loadBibleData()}
              title="Refresh Bible State"
              className="p-1.5 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-muted hover:text-obsidian-primary transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* =========================================================================
         * Horizontal Tab Navigation Bar
         * ========================================================================= */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none border-b border-border/80">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id as any)}
                className={cn(
                  "flex items-center gap-2 px-4 py-2.5 rounded-t-lg text-xs font-medium transition-all shrink-0 border-t border-x",
                  isActive
                    ? "bg-panel text-amber-400 border-border border-b-panel font-semibold shadow-sm -mb-[1px]"
                    : "bg-transparent text-obsidian-muted hover:text-obsidian-secondary border-transparent"
                )}
              >
                <Icon className={cn("w-4 h-4", isActive ? "text-amber-500" : "text-obsidian-muted")} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* =========================================================================
         * Tab Content Panels
         * ========================================================================= */}
        <div>
          {activeTab === "visual_dna" && (
            <VisualDnaTab
              projectId={projectId}
              styleParameters={bible?.style_parameters || {}}
              isLocked={isLocked}
              onSave={handleSaveStyleParameters}
            />
          )}

          {activeTab === "character_matrix" && (
            <CharacterMatrixTab
              projectId={projectId}
              project={project}
              characters={characters}
              isLocked={isLocked}
              onRefresh={loadBibleData}
              onSilentRefresh={() => loadBibleData({ silent: true })}
              onPatchCharacterAsset={handlePatchCharacterAsset}
              onPatchCharacterStateAsset={handlePatchCharacterStateAsset}
            />
          )}

          {activeTab === "world_props" && (
            <WorldPropsTab
              projectId={projectId}
              project={project}
              characters={characters}
              worldRules={bible?.world_rules || {}}
              isLocked={isLocked}
              onSave={handleSaveWorldRules}
              onRefresh={loadBibleData}
            />
          )}

          {activeTab === "rules_invariants" && (
            <RulesInvariantsTab
              worldRules={bible?.world_rules || {}}
              isLocked={isLocked}
              onSave={handleSaveWorldRules}
              projectId={projectId}
              project={project}
              characters={characters}
              onRefresh={loadBibleData}
            />
          )}

          {activeTab === "revision_lock" && (
            <RevisionLockTab
              projectId={projectId}
              bible={bible}
              onRefresh={loadBibleData}
            />
          )}
        </div>
      </div>
    </AppShell>
  );
}
