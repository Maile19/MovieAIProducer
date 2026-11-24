"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import AppShell from "@/components/layout/AppShell";
import LeftNavPipeline from "@/components/studio/LeftNavPipeline";
import DualViewportPlayer, { AspectRatioType } from "@/components/studio/DualViewportPlayer";
import ScrubberTimeline from "@/components/studio/ScrubberTimeline";
import ApprovalGateModal from "@/components/studio/ApprovalGateModal";
import MatrixSelector, { SelectedMatrixState } from "@/components/studio/MatrixSelector";
import PromptTranspiler from "@/components/studio/PromptTranspiler";
import SavePresetModal from "@/components/presets/SavePresetModal";
import { api, Project, Character, PipelineStatusResponse } from "@/lib/api";
import { Loader2, AlertCircle, ArrowLeft, RefreshCw, BookmarkPlus, Sparkles, Film } from "lucide-react";
import Link from "next/link";

export default function StudioPage() {
  const params = useParams();
  const queryClient = useQueryClient();
  const projectId = (params?.id as string) || "";

  const [project, setProject] = useState<Project | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatusResponse | null>(null);
  const [viewingStage, setViewingStage] = useState<number>(1);
  const [catalog, setCatalog] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isSavePresetModalOpen, setIsSavePresetModalOpen] = useState(false);

  // 360p Preview state (Point 8 & Refinement 4)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewProvider, setPreviewProvider] = useState<string | null>(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState<boolean>(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  // Characters for B-Roll DNA Master Lock continuity
  const [characters, setCharacters] = useState<Character[]>([]);
  const [activeCharacterId, setActiveCharacterId] = useState<string | null>(null);

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

  // Fetch project, matrix catalog, and characters
  const loadStudioData = useCallback(async () => {
    try {
      setIsLoading(true);
      setErrorMsg(null);

      // Fetch project, catalog, and character DNA anchors in parallel
      const [projRes, catalogRes, charsRes] = await Promise.allSettled([
        api.projects.get(projectId),
        api.catalog.getMatrix(),
        api.bible.listCharacters(projectId),
      ]);

      if (projRes.status === "fulfilled" && projRes.value?.data) {
        const p = projRes.value.data;
        setProject(p);
        if (p.pipeline_status) {
          setPipelineStatus(p.pipeline_status);
          const currentWorking = p.pipeline_status.header_metrics?.current_working_stage || p.operational_stage || 1;
          setViewingStage((prev) => prev || currentWorking);
        } else {
          setViewingStage((prev) => prev || p.operational_stage || 1);
        }
        if (p.aspect_ratio) {
          if (p.aspect_ratio === "2.39:1" || p.aspect_ratio === "16:9" || p.aspect_ratio === "9:16") {
            setAspectRatio(p.aspect_ratio as AspectRatioType);
          }
        }
        if (p.target_style_code) {
          setSelectedMatrix((prev) => ({ ...prev, styleCode: p.target_style_code }));
        }
        // Restore persistent preview across studio reloads
        if (p.settings && typeof p.settings.preview_url === "string") {
          setPreviewUrl(p.settings.preview_url);
        }
        if (p.settings && typeof p.settings.preview_provider === "string") {
          setPreviewProvider(p.settings.preview_provider);
        }
      } else {
        setErrorMsg("Failed to load project details from server.");
      }

      if (catalogRes.status === "fulfilled" && catalogRes.value?.data) {
        setCatalog(catalogRes.value.data);
      }

      if (charsRes.status === "fulfilled" && charsRes.value?.data) {
        const charList = charsRes.value.data;
        if (Array.isArray(charList)) {
          setCharacters(charList);
          setActiveCharacterId((prev) => prev || charList[0]?.id || null);
        }
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

  const handleStageSelect = (newStage: number) => {
    // Pure viewport navigation: strictly does NOT mutate database operational_stage
    setViewingStage(newStage);
  };

  const handleApproveGate = async (stageNum: number, notes?: string) => {
    try {
      const res = await api.projects.gateSignoff(projectId, {
        stage: stageNum,
        action: "APPROVE",
        notes: notes || `Showrunner Stage ${stageNum} signoff confirmed.`,
      });
      if (res?.data) {
        setPipelineStatus(res.data);
        await queryClient.invalidateQueries({ queryKey: ["projects"] });
        await loadStudioData();
      }
    } catch (err: any) {
      console.error("Failed to approve gate", err);
    }
  };

  const handleRevokeGate = async (stageNum: number, notes?: string) => {
    try {
      const res = await api.projects.gateSignoff(projectId, {
        stage: stageNum,
        action: "REVOKE",
        notes: notes || `Stage ${stageNum} gate revoked for revision.`,
      });
      if (res?.data) {
        setPipelineStatus(res.data);
        await queryClient.invalidateQueries({ queryKey: ["projects"] });
        await loadStudioData();
      }
    } catch (err: any) {
      console.error("Failed to revoke gate", err);
    }
  };

  const handleGeneratePreview = async () => {
    try {
      setIsLoadingPreview(true);
      setPreviewError(null);
      const res = await api.previews.generateProjectPreview(projectId, {
        aspect_ratio: aspectRatio,
        provider: "9router",
        model: "ag/gemini-3.8-flash",
      });
      if (res && res.preview_url) {
        setPreviewUrl(res.preview_url);
        if (res.provider) {
          setPreviewProvider(res.provider);
        }
      }
    } catch (err: any) {
      console.error("Failed to generate 360p preview", err);
      setPreviewError(err?.message || "Preview generation failed. Please try again.");
    } finally {
      setIsLoadingPreview(false);
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

  const currentWorkingStage = pipelineStatus?.header_metrics?.current_working_stage || project?.operational_stage || 1;
  const currentWorkingStep = pipelineStatus?.header_metrics?.current_working_step || 1;
  const activeViewingStage = viewingStage || currentWorkingStage;
  const viewingStageDef = pipelineStatus?.stages?.[`S${activeViewingStage.toString().padStart(2, "0")}`];
  const gateHistory = Array.isArray(project?.settings?.gate_history) ? project.settings.gate_history : [];

  return (
    <AppShell
      activeProjectId={projectId}
      activeProjectTitle={project?.title || "Production Studio"}
      currentStage={currentWorkingStage}
      stageName={project?.stage_name}
    >
      <div className="space-y-4">
        {/* =========================================================================
         * Studio Sub-Header & Quick Navigation (Vertical Hierarchy for Mobile & Desktop)
         * ========================================================================= */}
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 border-b border-border/70 pb-4">
          <div className="space-y-1.5">
            {/* Baris 1: Standalone Slate Navigation */}
            <div>
              <Link
                href="/dashboard"
                className="text-obsidian-muted hover:text-obsidian-primary transition-colors text-xs inline-flex items-center gap-1.5 font-mono"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Slate</span>
              </Link>
            </div>

            {/* Baris 2: Judul Studio Penuh, Rata Kiri, break-words */}
            <h1 className="font-cinzel text-base sm:text-xl font-bold text-obsidian-primary uppercase tracking-wider break-words leading-snug flex items-center gap-2.5">
              <Film className="w-5 h-5 text-amber-500 shrink-0" />
              <span>{project?.title} &bull; NLE Dual-Viewport</span>
            </h1>

            {/* Baris 3: Pipeline & Engine Subtitle */}
            <p className="text-xs font-mono text-obsidian-muted pt-0.5">
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
              viewingStage={activeViewingStage}
              currentWorkingStage={currentWorkingStage}
              stages={pipelineStatus?.stages}
              steps={pipelineStatus?.steps}
              headerMetrics={pipelineStatus?.header_metrics}
              onSelectStage={handleStageSelect}
              onApproveGate={handleApproveGate}
              onRevokeGate={handleRevokeGate}
              isProjectLocked={project?.status === "LOCKED"}
            />
          </div>

          {/* Center Stage: Dual Viewport + 12-Step Scrubber + Approval Gate (Cols 6) */}
          <div className="lg:col-span-6 space-y-4">
            {/* Dual Viewport Player */}
            <DualViewportPlayer
              aspectRatio={aspectRatio}
              onChangeAspectRatio={setAspectRatio}
              currentSceneTitle={`STAGE ${activeViewingStage}: ${viewingStageDef?.name || project?.stage_name || "Hollywood Sequence"}`}
              styleCode={selectedMatrix.styleCode}
              cameraCode={selectedMatrix.camCode}
              lightingCode={selectedMatrix.lightCode}
              previewUrl={previewUrl}
              previewProvider={previewProvider}
              isLoadingPreview={isLoadingPreview}
              onGeneratePreview={handleGeneratePreview}
              characterList={characters}
              activeCharacterId={activeCharacterId}
              onSelectCharacter={setActiveCharacterId}
              projectId={projectId}
              previewError={previewError}
            />

            {/* 12-Step Timeline Scrubber */}
            <ScrubberTimeline
              viewingStep={Math.min(activeViewingStage, 12)}
              currentWorkingStep={currentWorkingStep}
              stepStatuses={pipelineStatus?.steps}
              onSelectStep={(step) => handleStageSelect(step)}
              maxCompletedStep={pipelineStatus?.header_metrics?.completed_steps_count || 1}
            />

            {/* Human Approval Gate Controls */}
            <ApprovalGateModal
              projectId={projectId}
              projectTitle={project?.title || "Production"}
              currentStage={activeViewingStage}
              projectStatus={project?.status}
              gateHistory={gateHistory}
              onGateProcessed={async () => {
                await queryClient.invalidateQueries({ queryKey: ["projects"] });
                await loadStudioData();
              }}
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
