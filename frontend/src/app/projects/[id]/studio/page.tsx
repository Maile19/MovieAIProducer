"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import AppShell from "@/components/layout/AppShell";
import LeftNavPipeline from "@/components/studio/LeftNavPipeline";
import DualViewportPlayer, { AspectRatioType } from "@/components/studio/DualViewportPlayer";
import ScrubberTimeline from "@/components/studio/ScrubberTimeline";
import ApprovalGateModal from "@/components/studio/ApprovalGateModal";
import MatrixSelector, { SelectedMatrixState } from "@/components/studio/MatrixSelector";
import PromptTranspiler from "@/components/studio/PromptTranspiler";
import SavePresetModal from "@/components/presets/SavePresetModal";
import { api, Project } from "@/lib/api";
import { Loader2, AlertCircle, ArrowLeft, RefreshCw, BookmarkPlus, Sparkles } from "lucide-react";
import Link from "next/link";

export default function StudioPage() {
  const params = useParams();
  const projectId = (params?.id as string) || "";

  const [project, setProject] = useState<Project | null>(null);
  const [catalog, setCatalog] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isSavePresetModalOpen, setIsSavePresetModalOpen] = useState(false);

  // Studio viewport & matrix state
  const [aspectRatio, setAspectRatio] = useState<AspectRatioType>("2.39:1");
  const [selectedMatrix, setSelectedMatrix] = useState<SelectedMatrixState>({
    styleCode: "#Style 01",
    lightCode: "#Light 01",
    actCode: "#Act 01",
    camCode: "#Cam 01",
    lensCode: "#Lens 01",
    compCode: "#Comp 01",
    speedCode: "#Speed 01",
  });

  // Fetch project and matrix catalog
  const loadStudioData = useCallback(async () => {
    try {
      setIsLoading(true);
      setErrorMsg(null);

      // Fetch project
      const [projRes, catalogRes] = await Promise.allSettled([
        api.projects.get(projectId),
        api.catalog.getMatrix(),
      ]);

      if (projRes.status === "fulfilled" && projRes.value?.data) {
        const p = projRes.value.data;
        setProject(p);
        if (p.aspect_ratio) {
          if (p.aspect_ratio === "2.39:1" || p.aspect_ratio === "16:9" || p.aspect_ratio === "9:16") {
            setAspectRatio(p.aspect_ratio as AspectRatioType);
          }
        }
        if (p.target_style_code) {
          setSelectedMatrix((prev) => ({ ...prev, styleCode: p.target_style_code }));
        }
      } else {
        // Fallback for new or mocked project
        setProject({
          id: projectId,
          title: "Cyberpunk Hollywood Master Cut",
          slug: "cyberpunk-master",
          status: "IN_PRODUCTION",
          aspect_ratio: "2.39:1",
          target_style_code: "#Style 01",
          operational_stage: 3,
          stage_name: "4-Act Storyboard & 50-Scene Blueprint",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          settings: {
            gate_history: [
              {
                action: "APPROVE",
                stage: 1,
                notes: "Initial logline approved by showrunner.",
                timestamp: new Date().toISOString(),
              },
              {
                action: "APPROVE",
                stage: 2,
                notes: "Visual style #Style 01 selected.",
                timestamp: new Date().toISOString(),
              },
            ],
          },
        });
      }

      if (catalogRes.status === "fulfilled" && catalogRes.value?.data) {
        setCatalog(catalogRes.value.data);
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to load studio project.");
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (projectId) {
      loadStudioData();
    }
  }, [projectId, loadStudioData]);

  const handleUpdateMatrix = (updates: Partial<SelectedMatrixState>) => {
    setSelectedMatrix((prev) => ({ ...prev, ...updates }));
  };

  const handleStageSelect = async (newStage: number) => {
    if (!project) return;
    try {
      // Optimistic update
      setProject({ ...project, operational_stage: newStage });
      await api.projects.update(projectId, {
        settings: {
          ...project.settings,
          preview_stage: newStage,
        },
      });
    } catch {
      // Non-blocking
    }
  };

  if (isLoading) {
    return (
      <AppShell activeProjectId={projectId}>
        <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3">
          <Loader2 className="w-8 h-8 text-amber-500 animate-spin" />
          <p className="font-mono text-xs text-obsidian-secondary tracking-widest uppercase">
            Initializing Hollywood NLE 3-Pane Viewport...
          </p>
        </div>
      </AppShell>
    );
  }

  if (errorMsg && !project) {
    return (
      <AppShell activeProjectId={projectId}>
        <div className="max-w-md mx-auto my-16 p-6 rounded-2xl bg-panel border border-border text-center space-y-4">
          <AlertCircle className="w-10 h-10 text-rose-500 mx-auto" />
          <h2 className="font-cinzel text-lg font-bold text-obsidian-primary">
            Studio Initialization Error
          </h2>
          <p className="text-xs text-obsidian-secondary font-mono">{errorMsg}</p>
          <div className="pt-2 flex justify-center gap-2">
            <Link
              href="/dashboard"
              className="px-4 py-2 rounded-lg bg-canvas border border-border text-xs text-obsidian-secondary hover:text-obsidian-primary"
            >
              Return to Slate
            </Link>
            <button
              type="button"
              onClick={loadStudioData}
              className="px-4 py-2 rounded-lg bg-amber-500 text-canvas font-bold text-xs"
            >
              Retry
            </button>
          </div>
        </div>
      </AppShell>
    );
  }

  const currentStage = project?.operational_stage || 1;
  const gateHistory = Array.isArray(project?.settings?.gate_history) ? project.settings.gate_history : [];

  return (
    <AppShell
      activeProjectId={projectId}
      activeProjectTitle={project?.title || "Production Studio"}
      currentStage={currentStage}
      stageName={project?.stage_name}
    >
      <div className="space-y-4">
        {/* =========================================================================
         * Studio Sub-Header & Quick Navigation
         * ========================================================================= */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/70 pb-3">
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
              <h1 className="font-cinzel text-base sm:text-lg font-bold text-obsidian-primary uppercase tracking-wider">
                {project?.title} &bull; NLE Dual-Viewport
              </h1>
            </div>
            <p className="text-xs font-mono text-obsidian-muted mt-0.5">
              16-Stage Hollywood Pipeline &bull; 12-Step Framework &bull; DaVinci Obsidian Color Engine
            </p>
          </div>

          <div className="flex items-center gap-2">
            {(project?.settings as any)?.preset_name && (
              <span className="hidden sm:flex px-2.5 py-1 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-mono items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Preset: {(project?.settings as any).preset_name}</span>
              </span>
            )}
            <button
              type="button"
              onClick={() => setIsSavePresetModalOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-400 text-xs font-medium transition-colors"
            >
              <BookmarkPlus className="w-3.5 h-3.5" />
              <span>Save as Preset</span>
            </button>
            <Link
              href={`/projects/${projectId}/bible`}
              className="px-3 py-1.5 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-secondary hover:text-amber-400 text-xs font-medium transition-colors"
            >
              Production Bible
            </Link>
            <Link
              href={`/projects/${projectId}/scenes`}
              className="px-3 py-1.5 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-secondary hover:text-amber-400 text-xs font-medium transition-colors"
            >
              50-Scene Storyboard
            </Link>
            <button
              type="button"
              onClick={loadStudioData}
              title="Refresh Studio State"
              className="p-1.5 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-muted hover:text-obsidian-primary transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* =========================================================================
         * NLE 3-Pane Dual-Viewport Studio Grid (Left Nav | Center Stage | Right Inspector)
         * ========================================================================= */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
          {/* Left Pane: 16-Stage Pipeline & 12-Step Tree (Cols 3) */}
          <div className="lg:col-span-3 space-y-4">
            <LeftNavPipeline
              currentStage={currentStage}
              onSelectStage={handleStageSelect}
              isProjectLocked={project?.status === "LOCKED"}
            />
          </div>

          {/* Center Stage: Dual Viewport + 12-Step Scrubber + Approval Gate (Cols 6) */}
          <div className="lg:col-span-6 space-y-4">
            {/* Dual Viewport Player */}
            <DualViewportPlayer
              aspectRatio={aspectRatio}
              onChangeAspectRatio={setAspectRatio}
              currentSceneTitle={`STAGE ${currentStage}: ${project?.stage_name || "Hollywood Sequence"}`}
              styleCode={selectedMatrix.styleCode}
              cameraCode={selectedMatrix.camCode}
              lightingCode={selectedMatrix.lightCode}
            />

            {/* 12-Step Timeline Scrubber */}
            <ScrubberTimeline
              currentStep={Math.min(currentStage, 12)}
              onSelectStep={(step) => handleStageSelect(step)}
              maxCompletedStep={currentStage}
            />

            {/* Human Approval Gate Controls */}
            <ApprovalGateModal
              projectId={projectId}
              currentStage={currentStage}
              projectStatus={project?.status}
              gateHistory={gateHistory}
              onGateProcessed={loadStudioData}
            />
          </div>

          {/* Right Inspector: Matrix Selector & Live Prompt Transpiler (Cols 3) */}
          <div className="lg:col-span-3 space-y-4">
            {/* Matrix Selector */}
            <MatrixSelector
              selectedMatrix={selectedMatrix}
              onChangeMatrix={handleUpdateMatrix}
              catalogData={catalog}
            />

            {/* Live Prompt Transpiler */}
            <PromptTranspiler
              styleCode={selectedMatrix.styleCode}
              lightCode={selectedMatrix.lightCode}
              actCode={selectedMatrix.actCode}
              camCode={selectedMatrix.camCode}
              lensCode={selectedMatrix.lensCode}
              compCode={selectedMatrix.compCode}
              speedCode={selectedMatrix.speedCode}
              aspectRatio={aspectRatio}
              presetRules={(project?.settings as any)?.preset_data?.transpiler_rules}
              isNonVerbal={
                !!(project?.settings as any)?.preset_data?.bible_blueprint?.world_rules?.visual_non_verbal_mode?.enabled ||
                (project?.settings as any)?.preset_slug === "youtube-global-kids-comedy-non-verbal"
              }
            />
          </div>
        </div>

        {/* Save as Preset Modal */}
        <SavePresetModal
          isOpen={isSavePresetModalOpen}
          onClose={() => setIsSavePresetModalOpen(false)}
          projectId={projectId}
          defaultTitle={project?.title || "Production"}
        />
      </div>
    </AppShell>
  );
}
