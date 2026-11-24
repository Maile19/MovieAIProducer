"use client";

import React, { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Search,
  Film,
  BookOpen,
  Grid,
  Sparkles,
  Clapperboard,
  ArrowRight,
  X,
  AlertCircle,
  CheckCircle2,
  Lock,
  FastForward,
  Ratio,
  Palette,
  Filter,
  Bot,
  Trash2,
  Loader2,
} from "lucide-react";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/hooks/useAuth";
import { api, Project, ProjectCreateInput } from "@/lib/api";
import { cn } from "@/lib/utils";
import { DEFAULT_STYLES } from "@/lib/studio-constants";
import ObsidianDropdown from "@/components/ui/ObsidianDropdown";
import HermesNovaDrawer from "@/components/hermes/HermesNovaDrawer";

const ASPECT_RATIOS = [
  { value: "16:9", label: "16:9 Cinema Widescreen", desc: "Standard theatrical & streaming ratio" },
  { value: "2.39:1", label: "2.39:1 Anamorphic Scope", desc: "Ultrawide cinematic Panavision aspect" },
  { value: "9:16", label: "9:16 Vertical Cinema", desc: "Mobile-first immersive cinematic format" },
];

export default function DashboardPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { isAuthenticated } = useAuth({ requireAuth: true });

  const [searchQuery, setSearchQuery] = useState("");
  const [filterStage, setFilterStage] = useState<string>("all");
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [projectToDelete, setProjectToDelete] = useState<Project | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Lock body scroll when create or delete modal is open to prevent background scrolling on mobile
  useEffect(() => {
    if (isCreateModalOpen || projectToDelete) {
      const originalOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      return () => {
        document.body.style.overflow = originalOverflow;
      };
    }
  }, [isCreateModalOpen, projectToDelete]);

  // Form State for Create Production Modal
  const [newTitle, setNewTitle] = useState("");
  const [newSlug, setNewSlug] = useState("");
  const [newAspectRatio, setNewAspectRatio] = useState("16:9");
  const [newStyleCode, setNewStyleCode] = useState("#Style 01");
  const [newLogline, setNewLogline] = useState("");
  const [selectedPresetId, setSelectedPresetId] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [isHermesDrawerOpen, setIsHermesDrawerOpen] = useState(false);

  // Fetch Presets Library
  const { data: presetsData } = useQuery({
    queryKey: ["presets"],
    queryFn: () => api.presets.list(),
    enabled: isAuthenticated,
  });

  // Refinement 5: Safe deduplication without mutating database rows
  // Deduplicate presets by normalized name, prioritizing is_system === true, then most recent
  const presets = React.useMemo(() => {
    const raw = presetsData?.data || [];
    const map = new Map<string, (typeof raw)[0]>();
    for (const p of raw) {
      const normKey = p.name.trim().toLowerCase();
      const existing = map.get(normKey);
      if (!existing) {
        map.set(normKey, p);
      } else if (p.is_system && !existing.is_system) {
        map.set(normKey, p);
      }
    }
    return Array.from(map.values());
  }, [presetsData?.data]);

  // Fetch Projects Slate (identical queryKey and limit to AppShell for cache sharing)
  const {
    data: projectsData,
    isLoading: projectsLoading,
  } = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.projects.list({ limit: 200 }),
    enabled: isAuthenticated,
  });

  // Create Project Mutation
  const createMutation = useMutation({
    mutationFn: (input: ProjectCreateInput) => api.projects.create(input),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setIsCreateModalOpen(false);
      resetForm();
      if (res?.data?.id) {
        router.push(`/projects/${res.data.id}/studio`);
      }
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "Failed to initialize new production";
      setFormError(msg);
    },
  });

  // Delete Project Mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.projects.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setProjectToDelete(null);
      setDeleteError(null);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "Failed to delete production";
      setDeleteError(msg);
    },
  });

  // Quick Advance Stage Mutation
  const advanceMutation = useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) =>
      api.projects.advanceStage(id, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  const resetForm = () => {
    setNewTitle("");
    setNewSlug("");
    setNewAspectRatio("16:9");
    setNewStyleCode("#Style 01");
    setNewLogline("");
    setSelectedPresetId("");
    setFormError(null);
  };

  const handlePresetSelect = (presetId: string) => {
    setSelectedPresetId(presetId);
    if (!presetId) return;

    if (presetId === "polya_ai") {
      // Auto-Launch Event Listener for Polya AI Preset
      setIsHermesDrawerOpen(true);
      return;
    }

    const p = presets.find((item) => item.id === presetId || item.slug === presetId);
    if (p) {
      const projDefaults = p.preset_data?.project_defaults || {};
      if (projDefaults.aspect_ratio) {
        setNewAspectRatio(projDefaults.aspect_ratio);
      }
      if (projDefaults.target_style_code) {
        setNewStyleCode(projDefaults.target_style_code);
      }
      // Cleanly synchronize title and auto-generate kebab slug on preset switch
      setNewTitle(p.name);
      setNewSlug(
        p.name
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "-")
          .replace(/^-|-$/g, "")
      );
      if (p.description) {
        setNewLogline(p.description);
      }
    }
  };

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) {
      setFormError("Production title is required");
      return;
    }

    createMutation.mutate({
      title: newTitle.trim(),
      slug: newSlug.trim() || undefined,
      aspect_ratio: newAspectRatio,
      target_style_code: newStyleCode,
      settings: {
        logline: newLogline.trim(),
      },
      preset_id: selectedPresetId || undefined,
    });
  };

  // User's complete slate of productions
  const allProjects: Project[] = React.useMemo(() => projectsData?.data || [], [projectsData?.data]);

  // Summary Metrics (100% dynamic & real-time across user's complete slate)
  const totalCount = allProjects.length;
  const preProdCount = allProjects.filter((p) => p.operational_stage <= 5).length;
  const prodCount = allProjects.filter((p) => p.operational_stage >= 6 && p.operational_stage <= 11).length;
  const postCount = allProjects.filter((p) => p.operational_stage >= 12).length;

  // Client-side instant & responsive filtering for search and stage category
  const filteredProjects = React.useMemo(() => {
    return allProjects.filter((p) => {
      // Stage category filter
      if (filterStage === "pre-prod" && p.operational_stage > 5) return false;
      if (filterStage === "production" && (p.operational_stage < 6 || p.operational_stage > 11)) return false;
      if (filterStage === "post" && p.operational_stage < 12) return false;

      // Responsive search query filter
      if (searchQuery.trim()) {
        const q = searchQuery.trim().toLowerCase();
        const matchTitle = p.title.toLowerCase().includes(q);
        const matchSlug = p.slug?.toLowerCase().includes(q);
        const matchStyle = p.target_style_code?.toLowerCase().includes(q);
        if (!matchTitle && !matchSlug && !matchStyle) return false;
      }

      return true;
    });
  }, [allProjects, filterStage, searchQuery]);

  return (
    <AppShell>
      <div className="space-y-6">
        {/* =========================================================================
         * Slate Header & Quick Actions
         * ========================================================================= */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-2 border-b border-border/80">
          <div>
            <h1 className="text-2xl sm:text-3xl font-cinzel font-bold text-obsidian-primary tracking-wide">
              Showrunner Production Slate
            </h1>
            <p className="text-xs sm:text-sm text-obsidian-secondary font-mono mt-0.5">
              Multi-Project Hollywood Pipeline Management &bull; 16-Stage Lifecycle
            </p>
          </div>

          <button
            type="button"
            onClick={() => {
              resetForm();
              setIsCreateModalOpen(true);
            }}
            className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-semibold text-xs sm:text-sm shadow-glow transition-all active:scale-95 shrink-0 cursor-pointer"
          >
            <Plus className="w-4 h-4 stroke-[2.5]" />
            <span>Create New Production</span>
          </button>
        </div>

        {/* =========================================================================
         * Pipeline Metrics Summary Cards
         * ========================================================================= */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
          <div className="p-3.5 sm:p-4 rounded-xl bg-panel/80 backdrop-blur-sm border border-border">
            <div className="flex items-center justify-between text-obsidian-muted mb-1 text-[11px] font-mono uppercase">
              <span>Active Slate</span>
              <Clapperboard className="w-4 h-4 text-amber-500" />
            </div>
            <div className="text-2xl sm:text-3xl font-cinzel font-bold text-obsidian-primary">
              {totalCount}
            </div>
            <div className="text-[10px] text-obsidian-muted font-mono mt-1">
              All commissioned films
            </div>
          </div>

          <div className="p-3.5 sm:p-4 rounded-xl bg-panel/80 backdrop-blur-sm border border-border">
            <div className="flex items-center justify-between text-obsidian-muted mb-1 text-[11px] font-mono uppercase">
              <span>Pre-Production</span>
              <BookOpen className="w-4 h-4 text-blue-400" />
            </div>
            <div className="text-2xl sm:text-3xl font-cinzel font-bold text-blue-400">
              {preProdCount}
            </div>
            <div className="text-[10px] text-obsidian-muted font-mono mt-1">
              Stages 1-5 &bull; Bible & Blueprint
            </div>
          </div>

          <div className="p-3.5 sm:p-4 rounded-xl bg-panel/80 backdrop-blur-sm border border-border">
            <div className="flex items-center justify-between text-obsidian-muted mb-1 text-[11px] font-mono uppercase">
              <span>Generation & Inference</span>
              <Sparkles className="w-4 h-4 text-amber-400" />
            </div>
            <div className="text-2xl sm:text-3xl font-cinzel font-bold text-amber-400">
              {prodCount}
            </div>
            <div className="text-[10px] text-obsidian-muted font-mono mt-1">
              Stages 6-11 &bull; Transpiler & Video
            </div>
          </div>

          <div className="p-3.5 sm:p-4 rounded-xl bg-panel/80 backdrop-blur-sm border border-border">
            <div className="flex items-center justify-between text-obsidian-muted mb-1 text-[11px] font-mono uppercase">
              <span>Post & QC Master</span>
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-2xl sm:text-3xl font-cinzel font-bold text-emerald-400">
              {postCount}
            </div>
            <div className="text-[10px] text-obsidian-muted font-mono mt-1">
              Stages 12-16 &bull; QC & Master Cut
            </div>
          </div>
        </div>

        {/* =========================================================================
         * Search & Filter Controls
         * ========================================================================= */}
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 p-3 rounded-2xl bg-panel/70 border border-border">
          {/* Search Box */}
          <div className="relative flex-1">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-obsidian-muted" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search productions by title or keyword..."
              className="w-full bg-canvas border border-border rounded-xl pl-10 pr-4 py-2.5 text-xs sm:text-sm text-obsidian-primary placeholder:text-obsidian-muted focus:outline-none focus:border-amber-500/60 font-sans"
            />
          </div>

          {/* Slate Filter Dropdown */}
          <div className="w-full md:w-72 shrink-0">
            <ObsidianDropdown
              size="sm"
              label="Slate Stage Filter"
              icon={<Filter className="w-3.5 h-3.5 text-amber-500" />}
              options={[
                { value: "all", title: "All Slate Productions", description: `All ${totalCount} film projects`, badge: `${totalCount}` },
                { value: "pre-prod", title: "Pre-Production", description: "Stages 1-5 (Bible, DNA, Script Breakdown)", badge: `${preProdCount}` },
                { value: "production", title: "Active Generation", description: "Stages 6-11 (Act I-III Gen, QC)", badge: `${prodCount}` },
                { value: "post", title: "Post / Master", description: "Stages 12-16 (Assembly, Delivery)", badge: `${postCount}` },
              ]}
              value={filterStage}
              onChange={(val) => setFilterStage(val)}
            />
          </div>
        </div>

        {/* =========================================================================
         * Productions Grid Slate
         * ========================================================================= */}
        {projectsLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-64 rounded-xl bg-panel border border-border animate-pulse p-6 space-y-4"
              >
                <div className="h-6 bg-elevated rounded w-3/4" />
                <div className="h-4 bg-elevated rounded w-1/2" />
                <div className="h-2 bg-elevated rounded w-full mt-6" />
                <div className="h-10 bg-elevated rounded mt-6" />
              </div>
            ))}
          </div>
        ) : filteredProjects.length === 0 ? (
          /* Empty State */
          <div className="text-center py-16 px-4 rounded-xl bg-panel/40 border border-border/80 border-dashed">
            <div className="w-16 h-16 rounded-2xl bg-canvas border border-border mx-auto flex items-center justify-center text-amber-500 mb-4 shadow-inner">
              <Film className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-cinzel font-bold text-obsidian-primary">
              No Productions Found
            </h3>
            <p className="text-xs text-obsidian-secondary font-mono max-w-sm mx-auto mt-1 mb-6">
              {searchQuery
                ? `No film productions matching "${searchQuery}". Try clearing search filter.`
                : "The showrunner slate is currently clear. Commission a new cinematic production to begin."}
            </p>
            <button
              type="button"
              onClick={() => {
                resetForm();
                setIsCreateModalOpen(true);
              }}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-medium text-xs shadow-glow transition-all"
            >
              <Plus className="w-4 h-4" />
              <span>Create First Production</span>
            </button>
          </div>
        ) : (
          /* Active Production Cards */
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filteredProjects.map((project) => {
              const progressPct = Math.round((project.operational_stage / 16) * 100);

              return (
                <div
                  key={project.id}
                  className="rounded-xl bg-panel/80 backdrop-blur-md border border-border hover:border-amber-500/50 transition-all duration-200 flex flex-col justify-between overflow-hidden shadow-studio group"
                >
                  {/* Top Bar / Visual Header */}
                  <div className="p-5 pb-3">
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <div className="min-w-0">
                        <span className="inline-block px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-canvas border border-border text-amber-400 mb-1.5">
                          {project.target_style_code || "#Style 01"}
                        </span>
                        <h2 className="text-lg font-cinzel font-bold text-obsidian-primary group-hover:text-amber-400 transition-colors truncate">
                          {project.title}
                        </h2>
                      </div>
                      <span className="px-2 py-1 rounded text-[10px] font-mono bg-elevated border border-border text-obsidian-secondary shrink-0">
                        {project.aspect_ratio}
                      </span>
                    </div>

                    {/* Operational Stage Badge */}
                    <div className="flex items-center gap-2 mt-3 text-xs font-mono text-obsidian-secondary">
                      <div className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />
                      <span className="text-amber-400 font-semibold">
                        Stage {project.operational_stage}/16:
                      </span>
                      <span className="truncate text-obsidian-primary">
                        {project.stage_name}
                      </span>
                    </div>

                    {/* 16-Stage Progress Bar */}
                    <div className="mt-3">
                      <div className="flex justify-between text-[10px] font-mono text-obsidian-muted mb-1">
                        <span>Pipeline Execution</span>
                        <span>{progressPct}% Complete</span>
                      </div>
                      <div className="h-1.5 w-full bg-canvas rounded-full overflow-hidden border border-border/50">
                        <div
                          className="h-full bg-gradient-to-r from-amber-600 via-amber-500 to-amber-400 rounded-full transition-all duration-500"
                          style={{ width: `${progressPct}%` }}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Production Stats Pill Strip */}
                  <div className="px-5 py-2.5 bg-canvas/60 border-t border-b border-border/60 flex items-center justify-between text-[11px] font-mono text-obsidian-secondary">
                    <span className="flex items-center gap-1.5">
                      <Grid className="w-3.5 h-3.5 text-obsidian-muted" />
                      <span>{project.stats?.scenes_count ?? 50} Scenes</span>
                    </span>
                    <span className="flex items-center gap-1.5">
                      <BookOpen className="w-3.5 h-3.5 text-obsidian-muted" />
                      <span>Bible v{project.stats?.bible_version ?? 1}</span>
                      {project.stats?.bible_locked && (
                        <Lock className="w-3 h-3 text-amber-400" />
                      )}
                    </span>
                    <span className="text-obsidian-muted">
                      {new Date(project.created_at).toLocaleDateString()}
                    </span>
                  </div>

                  {/* Quick Action Navigation Buttons */}
                  <div className="p-4 bg-panel flex items-center justify-between gap-2">
                    {/* Direct Links to Zone 2 Modules */}
                    <div className="flex items-center gap-1.5">
                      <Link
                        href={`/projects/${project.id}/studio`}
                        title="Open NLE Production Studio"
                        className="px-2.5 py-1.5 rounded bg-canvas hover:bg-elevated border border-border text-[11px] font-mono text-obsidian-primary hover:text-amber-400 flex items-center gap-1.5 transition-colors"
                      >
                        <Film className="w-3.5 h-3.5 text-amber-500" />
                        <span>Studio</span>
                      </Link>

                      <Link
                        href={`/projects/${project.id}/bible`}
                        title="Master Production Bible"
                        className="px-2.5 py-1.5 rounded bg-canvas hover:bg-elevated border border-border text-[11px] font-mono text-obsidian-primary hover:text-blue-400 flex items-center gap-1.5 transition-colors"
                      >
                        <BookOpen className="w-3.5 h-3.5 text-blue-400" />
                        <span>Bible</span>
                      </Link>

                      <Link
                        href={`/projects/${project.id}/scenes`}
                        title="50-Scene 4-Act Storyboard"
                        className="px-2.5 py-1.5 rounded bg-canvas hover:bg-elevated border border-border text-[11px] font-mono text-obsidian-primary hover:text-emerald-400 flex items-center gap-1.5 transition-colors"
                      >
                        <Grid className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Scenes</span>
                      </Link>

                      {project.operational_stage < 16 && (
                        <button
                          type="button"
                          onClick={() => advanceMutation.mutate({ id: project.id })}
                          disabled={advanceMutation.isPending}
                          title="Advance to next operational stage"
                          className="px-2.5 py-1.5 rounded bg-canvas hover:bg-elevated border border-border text-[11px] font-mono text-amber-400 hover:border-amber-500/50 flex items-center gap-1.5 transition-colors disabled:opacity-50"
                        >
                          <FastForward className="w-3.5 h-3.5" />
                          <span>Advance</span>
                        </button>
                      )}
                    </div>

                    {/* Quick Action Buttons (Delete & Enter Studio) */}
                    <div className="flex items-center gap-1.5 shrink-0">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          setDeleteError(null);
                          setProjectToDelete(project);
                        }}
                        title={`Delete ${project.title}`}
                        className="p-1.5 rounded-md bg-canvas hover:bg-rose-500/10 border border-border hover:border-rose-500/40 text-obsidian-muted hover:text-rose-400 transition-colors flex items-center justify-center shrink-0 cursor-pointer"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>

                      <Link
                        href={`/projects/${project.id}/studio`}
                        className="p-1.5 rounded-md bg-amber-500 hover:bg-amber-600 text-canvas transition-colors flex items-center justify-center shrink-0"
                        title="Enter Production"
                      >
                        <ArrowRight className="w-4 h-4" />
                      </Link>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* =========================================================================
         * Create New Production Modal (Rendered via Portal to document.body)
         * ========================================================================= */}
        {isCreateModalOpen && mounted && createPortal(
          <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="w-full max-w-lg rounded-xl bg-panel border border-border shadow-studio overflow-hidden flex flex-col max-h-[90dvh] relative">
              {/* Modal Header */}
              <div className="px-5 sm:px-6 py-4 border-b border-border flex items-center justify-between shrink-0 bg-panel">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-7 h-7 rounded bg-canvas border border-border flex items-center justify-center text-amber-500 shrink-0">
                    <Clapperboard className="w-4 h-4" />
                  </div>
                  <h3 className="font-cinzel font-bold text-sm sm:text-base text-obsidian-primary truncate">
                    Commission New Production
                  </h3>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {/* Polya AI Live Status Indicator in Modal Header */}
                  <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-[10px] font-mono text-emerald-400 font-semibold shrink-0 shadow-sm">
                    <span className="relative flex h-1.5 w-1.5 shrink-0">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                      <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500" />
                    </span>
                    <span className="tracking-wide">Polya AI</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsCreateModalOpen(false)}
                    className="p-1 rounded text-obsidian-muted hover:text-obsidian-primary hover:bg-canvas transition-colors"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
              </div>

              {/* Form Content */}
              <form onSubmit={handleCreateSubmit} className="flex flex-col min-h-0 flex-1 overflow-hidden">
                <div className="p-5 sm:p-6 pb-32 sm:pb-12 space-y-4 overflow-y-auto flex-1 overscroll-contain">
                  {formError && (
                    <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
                      <AlertCircle className="w-4 h-4 shrink-0" />
                      <span>{formError}</span>
                    </div>
                  )}

                  {/* Production Preset Template Selector */}
                  <div>
                    <ObsidianDropdown
                      label="Load Production Preset Blueprint (Optional)"
                      placeholder="-- Blank / Custom Production Slate --"
                      icon={<Sparkles className="w-4 h-4 text-amber-500" />}
                      options={[
                        {
                          value: "polya_ai",
                          title: "★ Polya AI Preset",
                          description: "Dynamic YouTube trend & keyword AI ideation assistant",
                          badge: "AI AGENT",
                        },
                        {
                          value: "",
                          title: "-- Blank / Custom Production Slate --",
                          description: "Start from scratch without predefined bible blueprint",
                          badge: "Custom",
                        },
                        ...presets.map((preset) => {
                          const pDef = preset.preset_data?.project_defaults || {};
                          const sDef = preset.preset_data?.storyboard_defaults || {};
                          return {
                            value: preset.id,
                            title: `${preset.is_system ? "★ " : ""}${preset.name}`,
                            description: preset.description || `Style: ${pDef.target_style_code || "#Style 01"} • Ratio: ${pDef.aspect_ratio || "16:9"} • ${sDef.total_scenes || 50} Scenes`,
                            badge: preset.category.toUpperCase(),
                          };
                        }),
                      ]}
                      value={selectedPresetId}
                      onChange={(val) => handlePresetSelect(val)}
                    />

                    {/* Preset Quick Summary Chip */}
                    {selectedPresetId === "polya_ai" ? (
                      <div className="mt-2 p-2.5 rounded-lg bg-amber-500/15 border border-amber-500/40 text-[11px] font-mono text-amber-300 flex items-center justify-between gap-2 animate-in fade-in duration-150">
                        <div className="flex items-center gap-2 min-w-0">
                          <Bot className="w-4 h-4 text-amber-400 shrink-0" />
                          <div className="min-w-0">
                            <span className="font-bold block truncate">★ Polya AI Preset</span>
                            <span className="text-[10px] text-obsidian-secondary truncate block">
                              Dynamic YouTube-trend ideation & 10-variation synopsis engine
                            </span>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => setIsHermesDrawerOpen(true)}
                          className="px-2.5 py-1 rounded bg-amber-500 text-canvas font-bold text-[10px] hover:bg-amber-400 transition-colors shrink-0 shadow-glow"
                        >
                          Open Assistant
                        </button>
                      </div>
                    ) : selectedPresetId && (() => {
                      const activeP = presets.find((p) => p.id === selectedPresetId || p.slug === selectedPresetId);
                      if (!activeP) return null;
                      const pDef = activeP.preset_data?.project_defaults || {};
                      const sDef = activeP.preset_data?.storyboard_defaults || {};
                      return (
                        <div className="mt-2 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-[11px] font-mono text-amber-300 space-y-1">
                          <div className="font-bold flex items-center justify-between">
                            <span>{activeP.name}</span>
                            <span className="text-[10px] uppercase px-1.5 py-0.2 bg-amber-500/20 rounded">
                              {activeP.category}
                            </span>
                          </div>
                          <div className="text-[10px] text-obsidian-secondary">
                            Ratio: {pDef.aspect_ratio || "16:9"} &bull; Style: {pDef.target_style_code || "#Style 01"} &bull; {sDef.total_scenes || 50} Scenes &bull; Pacing: {sDef.pacing?.shot_duration_min || 4.0}-{sDef.pacing?.shot_duration_max || 5.0}s
                          </div>
                        </div>
                      );
                    })()}
                  </div>

                  {/* Project Title */}
                  <div>
                    <label className="block text-xs font-mono uppercase text-obsidian-secondary mb-1">
                      Production Title *
                    </label>
                    <input
                      type="text"
                      required
                      value={newTitle}
                      onChange={(e) => {
                        setNewTitle(e.target.value);
                        if (!newSlug) {
                          setNewSlug(
                            e.target.value
                              .toLowerCase()
                              .replace(/[^a-z0-9]+/g, "-")
                              .replace(/^-|-$/g, "")
                          );
                        }
                      }}
                      placeholder="e.g. Chronicles of Aethelgard: The Red Sun"
                      className="w-full bg-canvas border border-border rounded-lg px-3 py-2 text-sm text-obsidian-primary focus:outline-none focus:border-amber-500"
                    />
                  </div>

                  {/* Slug */}
                  <div>
                    <label className="block text-xs font-mono uppercase text-obsidian-secondary mb-1">
                      URL Slug
                    </label>
                    <input
                      type="text"
                      value={newSlug}
                      onChange={(e) => setNewSlug(e.target.value)}
                      placeholder="chronicles-of-aethelgard"
                      className="w-full bg-canvas border border-border rounded-lg px-3 py-2 text-xs font-mono text-obsidian-secondary focus:outline-none focus:border-amber-500"
                    />
                  </div>

                  {/* Aspect Ratio Presets */}
                  <div>
                    <label className="block text-xs font-mono uppercase text-obsidian-secondary mb-1.5 flex items-center gap-1.5">
                      <Ratio className="w-3.5 h-3.5 text-amber-500" />
                      <span>Aspect Ratio Preset</span>
                    </label>
                    <div className="grid grid-cols-3 gap-2">
                      {ASPECT_RATIOS.map((ar) => (
                        <button
                          key={ar.value}
                          type="button"
                          onClick={() => setNewAspectRatio(ar.value)}
                          className={cn(
                            "p-2.5 rounded-lg border text-left transition-all",
                            newAspectRatio === ar.value
                              ? "bg-amber-500/10 border-amber-500 text-amber-400"
                              : "bg-canvas border-border text-obsidian-secondary hover:border-obsidian-muted"
                          )}
                        >
                          <div className="text-xs font-bold font-mono">{ar.value}</div>
                          <div className="text-[10px] text-obsidian-muted truncate mt-0.5">
                            {ar.label.split(" ")[1] || ar.label}
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Target Visual Style Code */}
                  <div>
                    <ObsidianDropdown
                      label="Hollywood Visual Style (#Style Code)"
                      placeholder="Select Visual Style (#Style 01 - 18)..."
                      icon={<Palette className="w-4 h-4 text-amber-500" />}
                      options={DEFAULT_STYLES.map((style) => ({
                        value: style.code,
                        title: `${style.code} - ${style.name}`,
                        description: style.desc,
                        badge: "Style Code",
                      }))}
                      value={newStyleCode}
                      onChange={(val) => setNewStyleCode(val)}
                    />
                  </div>

                  {/* Logline */}
                  <div>
                    <label className="block text-xs font-mono uppercase text-obsidian-secondary mb-1">
                      Logline / Premise Synopsis
                    </label>
                    <textarea
                      rows={3}
                      value={newLogline}
                      onChange={(e) => setNewLogline(e.target.value)}
                      placeholder="In a cybernetic metropolis under perpetual rain, a rogue synthesis engineer uncovers an anomaly in the planetary atmospheric matrix..."
                      className="w-full bg-canvas border border-border rounded-lg px-3 py-2 text-xs text-obsidian-primary placeholder:text-obsidian-muted focus:outline-none focus:border-amber-500 resize-none font-sans"
                    />
                  </div>
                </div>

                {/* Polya AI Floating Action Button (FAB) */}
                <button
                  type="button"
                  onClick={() => setIsHermesDrawerOpen(true)}
                  className="absolute bottom-16 sm:bottom-20 right-3 sm:right-5 z-40 px-3.5 py-2 rounded-full bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-bold text-xs shadow-glow flex items-center gap-2 transition-all group border border-amber-300/40"
                  title="Open Polya AI Growth Agent"
                >
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-slate-950 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-slate-950"></span>
                  </span>
                  <Bot className="w-3.5 h-3.5 text-slate-950" />
                  <span>Polya AI</span>
                  <span className="px-1.5 py-0.2 rounded bg-slate-950/20 text-[9px] uppercase font-mono tracking-wider">
                    Agent
                  </span>
                </button>

                {/* Modal Footer Buttons */}
                <div className="px-5 sm:px-6 py-3 border-t border-border flex items-center justify-end gap-3 shrink-0 bg-panel/95">
                  <button
                    type="button"
                    onClick={() => setIsCreateModalOpen(false)}
                    className="px-4 py-2 rounded-lg bg-canvas border border-border text-xs text-obsidian-secondary hover:text-obsidian-primary transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={createMutation.isPending}
                    className="px-5 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-canvas font-semibold text-xs shadow-glow transition-all flex items-center gap-2"
                  >
                    {createMutation.isPending ? (
                      <>
                        <span className="w-3.5 h-3.5 border-2 border-canvas border-t-transparent rounded-full animate-spin" />
                        <span>Initializing...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-3.5 h-3.5" />
                        <span>Initialize Production</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>

            {/* Polya AI Glassmorphic Overlay Drawer */}
            <HermesNovaDrawer
              isOpen={isHermesDrawerOpen}
              onClose={() => setIsHermesDrawerOpen(false)}
              activePresetName={
                selectedPresetId === "polya_ai"
                  ? "Polya AI Preset"
                  : presets.find((p) => p.id === selectedPresetId)?.name || ""
              }
              activeCategory={
                selectedPresetId === "polya_ai"
                  ? "anime"
                  : presets.find((p) => p.id === selectedPresetId)?.category || "general"
              }
              activeAspectRatio={newAspectRatio}
              activeStyleCode={newStyleCode}
              activeStyleDesc={DEFAULT_STYLES.find((s) => s.code === newStyleCode)?.desc}
              seedPremise={newLogline}
              onSelectCatalogItem={(item) => {
                setNewAspectRatio(item.aspect_ratio);
                setNewStyleCode(item.target_style_code);
                if (!newLogline) {
                  setNewLogline(item.suggested_premise_seed);
                }
              }}
              onApplyTitleAndSlug={(title, slug) => {
                setNewTitle(title);
                setNewSlug(slug);
              }}
              onApplySynopsis={(synopsis) => {
                setNewLogline(synopsis);
              }}
            />
          </div>,
          document.body
        )}

        {/* =========================================================================
         * Delete Production Confirmation Modal (Rendered via Portal to document.body)
         * ========================================================================= */}
        {projectToDelete && mounted && createPortal(
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200"
            onClick={() => {
              // Block closing backdrop click when delete mutation is in flight
              if (!deleteMutation.isPending) {
                setProjectToDelete(null);
                setDeleteError(null);
              }
            }}
          >
            <div
              className="w-full max-w-md rounded-xl bg-panel border border-border shadow-studio overflow-hidden flex flex-col p-6 space-y-4 animate-in zoom-in-95 duration-150"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-center text-rose-400 shrink-0">
                  <AlertCircle className="w-5 h-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <h3 className="font-cinzel font-bold text-base text-obsidian-primary">
                    Delete Production Slate?
                  </h3>
                  <p className="text-xs text-obsidian-secondary font-mono mt-1">
                    This action is permanent and cannot be undone.
                  </p>
                </div>
              </div>

              <div className="p-3.5 rounded-lg bg-canvas border border-border/80 text-xs font-mono space-y-1">
                <div className="text-obsidian-muted uppercase text-[10px]">Target Production:</div>
                <div className="text-amber-400 font-semibold truncate text-sm">
                  {projectToDelete.title}
                </div>
                <div className="text-obsidian-secondary text-[11px]">
                  Stage {projectToDelete.operational_stage}/16 &bull; {projectToDelete.aspect_ratio} &bull; {projectToDelete.target_style_code}
                </div>
              </div>

              <p className="text-xs text-obsidian-secondary leading-relaxed">
                Deleting this project will permanently remove its 50-Scene Storyboard, Master Production Bible, character matrices, shots, and any generated media assets.
              </p>

              {deleteError && (
                <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 flex items-center gap-2 text-rose-400 text-xs font-mono">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span className="truncate">{deleteError}</span>
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
                <button
                  type="button"
                  disabled={deleteMutation.isPending}
                  onClick={() => {
                    if (!deleteMutation.isPending) {
                      setProjectToDelete(null);
                      setDeleteError(null);
                    }
                  }}
                  className="px-4 py-2 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-secondary hover:text-obsidian-primary text-xs font-medium transition-colors disabled:opacity-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={deleteMutation.isPending}
                  onClick={() => deleteMutation.mutate(projectToDelete.id)}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-700 text-white font-semibold text-xs transition-colors shadow-sm disabled:opacity-50 cursor-pointer"
                >
                  {deleteMutation.isPending ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Deleting Production...</span>
                    </>
                  ) : (
                    <>
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Delete Production</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}
      </div>
    </AppShell>
  );
}
