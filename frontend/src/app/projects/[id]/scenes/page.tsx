"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import AppShell from "@/components/layout/AppShell";
import ActFilterBar, { ActFilterType } from "@/components/scenes/ActFilterBar";
import SceneCard from "@/components/scenes/SceneCard";
import SceneDetailDrawer from "@/components/scenes/SceneDetailDrawer";
import BlueprintModal, { BlueprintConfig } from "@/components/scenes/BlueprintModal";
import { api, Project, Scene } from "@/lib/api";
import {
  Grid,
  Film,
  BookOpen,
  ArrowLeft,
  Loader2,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  Sparkles,
} from "lucide-react";

export default function ScenesStoryboardPage() {
  const params = useParams();
  const projectId = (params?.id as string) || "";

  const [project, setProject] = useState<Project | null>(null);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [selectedScene, setSelectedScene] = useState<Scene | null>(null);
  const [currentFilter, setCurrentFilter] = useState<ActFilterType>("ALL");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isGeneratingBlueprint, setIsGeneratingBlueprint] = useState(false);
  const [isBlueprintModalOpen, setIsBlueprintModalOpen] = useState(false);
  const [currentPage, setCurrentPage] = useState<number>(1);

  // Load project & scenes
  const loadScenesData = useCallback(async (options?: { silent?: boolean }) => {
    try {
      if (!options?.silent) {
        setIsLoading(true);
      }
      setError(null);
      const [projRes, scenesRes] = await Promise.allSettled([
        api.projects.get(projectId),
        api.scenes.list(projectId),
      ]);

      if (projRes.status === "fulfilled" && projRes.value?.data) {
        setProject(projRes.value.data);
      }

      if (scenesRes.status === "fulfilled" && scenesRes.value?.data) {
        const newScenes = scenesRes.value.data;
        setScenes(newScenes);
        setSelectedScene((prev) => {
          if (!prev) return null;
          const found = newScenes.find((s) => s.id === prev.id);
          return found || prev;
        });
      } else if (scenesRes.status === "rejected") {
        throw new Error(scenesRes.reason?.message || "Failed to load scenes from server");
      }
    } catch (err: any) {
      console.error(err);
      setError(err?.message || "Failed to load scenes. Please check your connection and retry.");
    } finally {
      if (!options?.silent) {
        setIsLoading(false);
      }
    }
  }, [projectId]);

  useEffect(() => {
    if (projectId) {
      loadScenesData();
    }
  }, [projectId, loadScenesData]);

  // Handle blueprint modal trigger & generation
  const handleOpenBlueprintModal = () => {
    setIsBlueprintModalOpen(true);
  };

  const handleConfirmBlueprint = async (config: BlueprintConfig) => {
    try {
      setIsGeneratingBlueprint(true);
      setError(null);
      await api.scenes.generateBlueprint(projectId, {
        total_scenes: config.total_scenes,
        duration_mode: config.duration_mode,
        auto_split_shots: config.auto_split_shots,
        clear_existing: config.clear_existing,
      });
      await loadScenesData();
      setIsBlueprintModalOpen(false);
      setCurrentPage(1);
    } catch (err: any) {
      console.error("Blueprint generation error:", err);
      setError(`Blueprint generation failed: ${err?.message || "Unknown error"}. Try resuming or re-generating the Act.`);
    } finally {
      setIsGeneratingBlueprint(false);
    }
  };

  // Export full package
  const handleExportPackage = async (format: "json" | "markdown") => {
    try {
      const res = await api.export.getProjectPackage(projectId, format);
      const content =
        format === "json"
          ? JSON.stringify(res, null, 2)
          : typeof res === "string"
          ? res
          : JSON.stringify(res, null, 2);

      const mimeType = format === "json" ? "application/json" : "text/markdown";
      const blob = new Blob([content], { type: mimeType });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `Hollywood_Storyboard_${projectId}.${format === "json" ? "json" : "md"}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
    }
  };

  const handleFilterChange = (filter: ActFilterType) => {
    setCurrentFilter(filter);
    setCurrentPage(1);
  };

  // Narrative structure metadata from project settings / treatment
  const treatment = (project?.settings as any)?.treatment;
  const structureType: string = treatment?.structure_type || "4_act";
  const structureName: string = treatment?.structure_name || "";
  const treatmentActs: Array<any> | undefined = treatment?.acts;

  // Determine total acts dynamically: treatment acts length, or by structure type, or max scene act
  const maxSceneAct = scenes.reduce((max, s) => Math.max(max, s.act_number || 1), 1);
  const totalActs =
    treatmentActs?.length ||
    (structureType === "3_act"
      ? 3
      : structureType === "5_act"
      ? 5
      : Math.max(4, maxSceneAct));

  // Count scenes dynamically per act (1..totalActs)
  const actCountMap: Record<number, number> = {};
  for (let a = 1; a <= totalActs; a++) {
    actCountMap[a] = scenes.filter((s) => (s.act_number || 1) === a).length;
  }

  // Filter scenes dynamically
  const filteredScenes = scenes.filter((s) => {
    if (currentFilter === "ALL") return true;
    const act = s.act_number || 1;
    if (typeof currentFilter === "number") return act === currentFilter;
    if (currentFilter === "ACT_I") return act === 1;
    if (currentFilter === "ACT_II_A") return act === 2;
    if (currentFilter === "ACT_II_B") return act === 3;
    if (currentFilter === "ACT_III") return act === 4;
    if (currentFilter === "ACT_IV") return act === 4;
    if (currentFilter === "ACT_V") return act === 5;
    const parsedNum = Number(currentFilter);
    if (!isNaN(parsedNum)) return act === parsedNum;
    return true;
  });

  const PAGE_SIZE = 60;
  const totalPages = Math.max(1, Math.ceil(filteredScenes.length / PAGE_SIZE));
  const displayedScenes = filteredScenes.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE
  );

  const totalRuntimeSeconds = scenes.reduce(
    (acc, s) => acc + (s.duration_target || 5.0),
    0
  );
  const runtimeMinutes = Math.floor(totalRuntimeSeconds / 60);
  const runtimeSecs = Math.round(totalRuntimeSeconds % 60);

  if (isLoading) {
    return (
      <AppShell activeProjectId={projectId}>
        <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3">
          <Loader2 className="w-8 h-8 text-amber-500 animate-spin" />
          <p className="font-mono text-xs text-obsidian-secondary tracking-widest uppercase">
            Loading Storyboard Grid...
          </p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell
      activeProjectId={projectId}
      activeProjectTitle={project?.title || "Storyboard"}
      currentStage={project?.operational_stage}
      stageName={project?.stage_name}
    >
      <div className="space-y-5">
        {/* =========================================================================
         * Header: Dynamic Storyboard Title & Metrics
         * ========================================================================= */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/70 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <Link
                href="/dashboard"
                className="text-obsidian-muted hover:text-obsidian-primary transition-colors text-xs flex items-center gap-1 font-mono"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Slate</span>
              </Link>
              <span className="text-obsidian-muted text-xs font-mono">/</span>
              <h1 className="font-cinzel text-lg sm:text-xl font-bold text-obsidian-primary uppercase tracking-wider flex items-center gap-2">
                <Grid className="w-5 h-5 text-amber-500" />
                <span>
                  {scenes.length > 0 ? `${scenes.length}-Scene ` : ""}
                  {structureName || (totalActs === 3 ? "3-Act" : totalActs === 5 ? "5-Act" : "4-Act")} Visual Storyboard
                </span>
              </h1>
            </div>
            <p className="text-xs font-mono text-obsidian-muted mt-1 flex items-center gap-2">
              <span>{scenes.length} Scenes Total</span>
              <span>&bull;</span>
              <span>{totalRuntimeSeconds.toFixed(1)}s Runtime (~{runtimeMinutes}m {runtimeSecs}s)</span>
              <span>&bull;</span>
              <span className="text-emerald-400 font-semibold">QC Continuum: 96%</span>
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href={`/projects/${projectId}/studio`}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-secondary hover:text-amber-400 text-xs font-medium transition-colors"
            >
              <Film className="w-3.5 h-3.5" />
              <span>NLE Studio</span>
            </Link>
            <Link
              href={`/projects/${projectId}/bible`}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-secondary hover:text-amber-400 text-xs font-medium transition-colors"
            >
              <BookOpen className="w-3.5 h-3.5" />
              <span>Production Bible</span>
            </Link>
            <button
              type="button"
              onClick={() => loadScenesData()}
              title="Refresh Storyboard"
              className="p-1.5 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-muted hover:text-obsidian-primary transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* =========================================================================
         * Act Filter Bar & Blueprint Generation
         * ========================================================================= */}
        <ActFilterBar
          currentFilter={currentFilter}
          onChangeFilter={handleFilterChange}
          totalScenes={scenes.length}
          actCounts={actCountMap}
          totalActs={totalActs}
          actsData={treatmentActs}
          structureType={structureType}
          onGenerateBlueprint={handleOpenBlueprintModal}
          isGeneratingBlueprint={isGeneratingBlueprint}
          onExportPackage={handleExportPackage}
        />

        {/* Error Notification Banner */}
        {error && (
          <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-between text-xs text-rose-300">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{error}</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => loadScenesData()}
                className="px-3 py-1 rounded bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 font-bold border border-rose-500/40 transition-colors"
              >
                Retry
              </button>
              <button
                type="button"
                onClick={() => setError(null)}
                className="text-rose-400 hover:text-rose-200 text-sm font-bold px-1"
              >
                &times;
              </button>
            </div>
          </div>
        )}

        {/* =========================================================================
         * 4-Act Visual Storyboard Grid (Virtualized / Paginated)
         * ========================================================================= */}
        {scenes.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 px-4 border border-dashed border-border rounded-2xl bg-panel/50 text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-amber-500/10 flex items-center justify-center text-amber-400">
              <Grid className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <h3 className="font-cinzel text-base font-bold text-obsidian-primary uppercase">No Storyboard Scenes Yet</h3>
              <p className="text-xs text-obsidian-muted max-w-md">
                Launch the Polya AI Screenplay Writer Blueprint generator to create 50 to 450 calibrated scenes with character cast and dramatic beats.
              </p>
            </div>
            <button
              type="button"
              onClick={handleOpenBlueprintModal}
              className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-xs flex items-center gap-2 transition-colors shadow-glow"
            >
              <Sparkles className="w-4 h-4" />
              <span>Generate Blueprint</span>
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3.5">
            {displayedScenes.map((scene) => (
              <SceneCard
                key={scene.id}
                scene={scene}
                isSelected={selectedScene?.id === scene.id}
                onSelect={(s) => setSelectedScene(s)}
              />
            ))}
          </div>
        )}

        {/* Pagination Bar for Large Scene Counts (>60 scenes) */}
        {totalPages > 1 && (
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-3 rounded-xl bg-panel border border-border text-xs font-mono">
            <span className="text-obsidian-muted">
              Showing scenes {(currentPage - 1) * PAGE_SIZE + 1}–{Math.min(currentPage * PAGE_SIZE, filteredScenes.length)} of {filteredScenes.length}
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="px-2.5 py-1.5 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-secondary disabled:opacity-40 transition-colors flex items-center gap-1"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                <span>Prev</span>
              </button>
              <span className="px-2 font-bold text-obsidian-primary">
                Page {currentPage} / {totalPages}
              </span>
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="px-2.5 py-1.5 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-secondary disabled:opacity-40 transition-colors flex items-center gap-1"
              >
                <span>Next</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

        {/* =========================================================================
         * Slide-In Scene Detail Drawer / Sheet
         * ========================================================================= */}
        {selectedScene && (
          <SceneDetailDrawer
            scene={selectedScene}
            onClose={() => setSelectedScene(null)}
            onSceneUpdated={loadScenesData}
            styleCode={project?.target_style_code || "#Style 01"}
            isNonVerbal={
              !!(project?.settings as any)?.preset_data?.bible_blueprint?.world_rules?.visual_non_verbal_mode?.enabled ||
              (project?.settings as any)?.preset_slug === "youtube-global-kids-comedy-non-verbal"
            }
          />
        )}

        {/* =========================================================================
         * Blueprint Configuration Modal
         * ========================================================================= */}
        <BlueprintModal
          isOpen={isBlueprintModalOpen}
          onClose={() => setIsBlueprintModalOpen(false)}
          projectId={projectId}
          onRefreshScenes={loadScenesData}
          onGenerate={handleConfirmBlueprint}
          existingScenesCount={scenes.length}
          presetDefaults={(project?.settings as any)?.preset_data?.storyboard_defaults}
        />
      </div>
    </AppShell>
  );
}
