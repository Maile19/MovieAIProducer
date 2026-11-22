"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Bot,
  X,
  ChevronRight,
  Check,
  RotateCcw,
  Zap,
  ArrowRight,
  ArrowLeft,
  Cpu,
  Hash,
  Copy,
} from "lucide-react";
import {
  api,
  HermesCatalogItem,
  HermesTitleItem,
  HermesSynopsisItem,
} from "@/lib/api";
import { cn } from "@/lib/utils";

interface HermesNovaDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  // Main form synchronization bindings
  activePresetName: string;
  activeCategory: string;
  activeAspectRatio: string;
  activeStyleCode: string;
  activeStyleDesc?: string;
  seedPremise: string;
  onSelectCatalogItem: (item: HermesCatalogItem) => void;
  onApplyTitleAndSlug: (title: string, slug: string) => void;
  onApplySynopsis: (synopsis: string) => void;
}

export default function HermesNovaDrawer({
  isOpen,
  onClose,
  activePresetName,
  activeCategory,
  activeAspectRatio,
  activeStyleCode,
  activeStyleDesc,
  seedPremise,
  onSelectCatalogItem,
  onApplyTitleAndSlug,
  onApplySynopsis,
}: HermesNovaDrawerProps) {
  const [activeStep, setActiveStep] = useState<"catalog" | "titles" | "synopses">("catalog");
  const [catalog, setCatalog] = useState<HermesCatalogItem[]>([]);
  const [isLoadingCatalog, setIsLoadingCatalog] = useState(false);

  // Step 1: Titles state
  const [titles, setTitles] = useState<HermesTitleItem[]>([]);
  const [titlesSource, setTitlesSource] = useState<"llm" | "procedural_fallback" | null>(null);
  const [isGeneratingTitles, setIsGeneratingTitles] = useState(false);
  const [titlesError, setTitlesError] = useState<string | null>(null);
  const [lockedTitle, setLockedTitle] = useState<string>("");
  const [seoTags, setSeoTags] = useState<string[]>([]);
  const [copiedSeo, setCopiedSeo] = useState(false);
  const stepBarRef = useRef<HTMLDivElement | null>(null);

  // Step 2: Synopses state
  const [synopses, setSynopses] = useState<HermesSynopsisItem[]>([]);
  const [synopsesSource, setSynopsesSource] = useState<"llm" | "procedural_fallback" | null>(null);
  const [isGeneratingSynopses, setIsGeneratingSynopses] = useState(false);
  const [synopsesError, setSynopsesError] = useState<string | null>(null);
  const [lockedSynopsis, setLockedSynopsis] = useState<string>("");

  // Notification Toast
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Load trend catalog on first open
  useEffect(() => {
    if (isOpen && catalog.length === 0) {
      loadCatalog();
    }
  }, [isOpen, catalog.length]);

  // Horizontal container auto-centering without vertical page jump (Refinement 1)
  useEffect(() => {
    const container = stepBarRef.current;
    if (container) {
      const activeEl = container.querySelector('[data-active="true"]') as HTMLElement | null;
      if (activeEl) {
        container.scrollTo({
          left: activeEl.offsetLeft - container.clientWidth / 2 + activeEl.clientWidth / 2,
          behavior: "smooth",
        });
      }
    }
  }, [activeStep]);

  const loadCatalog = async () => {
    try {
      setIsLoadingCatalog(true);
      const res = await api.hermesNova.getCatalog();
      if (res.data) {
        setCatalog(res.data);
      }
    } catch (err: any) {
      console.error("Failed to load Polya AI catalog", err);
    } finally {
      setIsLoadingCatalog(false);
    }
  };

  const handleCatalogPick = (item: HermesCatalogItem) => {
    onSelectCatalogItem(item);
    setActiveStep("titles");
    // Trigger title ideation for chosen catalog archetype
    generateTitles(item.suggested_premise_seed, item.target_style_code, item.aspect_ratio);
  };

  const generateTitles = async (
    overridePremise?: string,
    overrideStyle?: string,
    overrideRatio?: string
  ) => {
    try {
      setIsGeneratingTitles(true);
      setTitlesError(null);
      const res = await api.hermesNova.ideateTitles({
        preset_name: activePresetName || "Polya AI Preset",
        category: activeCategory || "anime",
        target_style_code: overrideStyle || activeStyleCode || "#Style 06",
        target_style_desc: activeStyleDesc || "",
        aspect_ratio: overrideRatio || activeAspectRatio || "16:9",
        seed_premise: overridePremise !== undefined ? overridePremise : seedPremise,
      });

      if (res.recommendations && res.recommendations.length > 0) {
        setTitles(res.recommendations);
        setTitlesSource(res.source);
      }

      // Capture SEO description tags or fallback to aggregating target keywords
      if (res.seo_description_tags && res.seo_description_tags.length > 0) {
        setSeoTags(res.seo_description_tags);
      } else if (res.recommendations && res.recommendations.length > 0) {
        const allKeywords = res.recommendations.flatMap((r) => r.target_keywords || []);
        const unique = Array.from(new Set(allKeywords.map((k) => k.trim().replace(/^#+/, "")))).filter(Boolean);
        setSeoTags(unique);
      }
    } catch (err: any) {
      setTitlesError(err.message || "Failed to generate title recommendations");
    } finally {
      setIsGeneratingTitles(false);
    }
  };

  const handleConfirmTitle = (item: HermesTitleItem) => {
    setLockedTitle(item.title);
    // Explicit override into parent form
    onApplyTitleAndSlug(item.title, item.slug);
    setToastMessage(`Judul terpilih: "${item.title}"`);
    setTimeout(() => setToastMessage(null), 2500);

    // Automatically transition & chain into Step 2: 10 Synopses
    setActiveStep("synopses");
    generateSynopses(item.title, item.target_keywords);
  };

  const generateSynopses = async (titleToUse: string, keywords?: string[]) => {
    try {
      setIsGeneratingSynopses(true);
      setSynopsesError(null);
      const res = await api.hermesNova.ideateSynopses({
        locked_title: titleToUse,
        preset_name: activePresetName || "Polya AI Preset",
        target_style_code: activeStyleCode || "#Style 06",
        aspect_ratio: activeAspectRatio || "16:9",
        seed_premise: seedPremise,
        trend_keywords: keywords || [],
      });

      if (res.synopses && res.synopses.length > 0) {
        setSynopses(res.synopses);
        setSynopsesSource(res.source);
      }
    } catch (err: any) {
      setSynopsesError(err.message || "Failed to generate synopsis variations");
    } finally {
      setIsGeneratingSynopses(false);
    }
  };

  const handleConfirmSynopsis = (item: HermesSynopsisItem) => {
    setLockedSynopsis(item.synopsis);
    // Explicit override into parent form
    onApplySynopsis(item.synopsis);
    setToastMessage("Sinopsis berhasil diaplikasikan ke form produksi!");
    setTimeout(() => {
      setToastMessage(null);
      onClose(); // Smoothly minimize/close overlay
    }, 1200);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[60] flex flex-col justify-end sm:justify-center items-center p-0 sm:p-4 bg-black/70 backdrop-blur-md animate-in fade-in duration-200">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="absolute top-4 z-[70] px-4 py-2.5 rounded-xl bg-emerald-500/90 border border-emerald-400 text-slate-950 font-semibold text-xs shadow-2xl flex items-center gap-2 animate-in slide-in-from-top duration-200">
          <Check className="w-4 h-4 stroke-[2.5]" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Main Glassmorphic Drawer Card */}
      <div className="w-full max-w-xl bg-slate-950/95 border border-amber-500/30 rounded-t-2xl sm:rounded-2xl shadow-2xl flex flex-col max-h-[92dvh] sm:max-h-[85dvh] overflow-hidden font-sans">
        {/* Drawer Sticky Header */}
        <div className="px-5 py-3.5 border-b border-border/80 flex items-center justify-between shrink-0 bg-slate-900/90">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400 shrink-0 shadow-glow">
              <Bot className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="font-cinzel font-bold text-sm text-obsidian-primary truncate uppercase tracking-wider">
                  Polya AI
                </h3>
                {/* Source status indicator pill */}
                {((activeStep === "titles" && titlesSource) || (activeStep === "synopses" && synopsesSource)) && (
                  <span
                    className={cn(
                      "text-[9px] font-mono px-1.5 py-0.2 rounded border flex items-center gap-1",
                      (activeStep === "titles" ? titlesSource : synopsesSource) === "llm"
                        ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/30"
                        : "bg-amber-500/10 text-amber-400 border-amber-500/30"
                    )}
                  >
                    <Cpu className="w-2.5 h-2.5" />
                    {(activeStep === "titles" ? titlesSource : synopsesSource) === "llm"
                      ? "9Router Gemini"
                      : "Procedural Engine"}
                  </span>
                )}
              </div>
              <p className="text-[10px] text-obsidian-muted font-mono truncate">
                YouTube Algorithmic Ideation & Retention Matrix
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {/* Polya AI Live Status Indicator (Universal Mobile Header) */}
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-[10px] font-mono text-emerald-400 font-semibold shrink-0 shadow-sm">
              <span className="relative flex h-1.5 w-1.5 shrink-0">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500" />
              </span>
              <span className="tracking-wide">Polya AI</span>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg text-obsidian-muted hover:text-obsidian-primary hover:bg-slate-800 transition-colors"
              title="Minimize Assistant"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Live Context Chip Bar */}
        <div className="px-5 py-2 bg-slate-900/60 border-b border-border/50 flex items-center justify-between text-[10px] font-mono shrink-0 overflow-x-auto gap-2">
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-obsidian-muted">Context:</span>
            <span className="px-2 py-0.5 rounded bg-canvas border border-border text-amber-400 font-semibold truncate max-w-[130px]">
              {activePresetName || "Custom Slate"}
            </span>
            <span className="px-2 py-0.5 rounded bg-canvas border border-border text-obsidian-secondary truncate max-w-[110px]">
              {activeStyleCode || "#Style 06"}
            </span>
            <span className="px-1.5 py-0.5 rounded bg-canvas border border-border text-obsidian-secondary">
              {activeAspectRatio || "16:9"}
            </span>
          </div>

          {/* Navigation Pill Steps */}
          <div ref={stepBarRef} className="flex items-center gap-1 shrink-0 overflow-x-auto scrollbar-none py-0.5">
            <button
              type="button"
              data-active={activeStep === "catalog"}
              onClick={() => setActiveStep("catalog")}
              className={cn(
                "px-2.5 py-0.5 rounded transition-all text-[10px] shrink-0",
                activeStep === "catalog"
                  ? "bg-amber-500 text-canvas font-bold ring-1 ring-amber-400 shadow-glow"
                  : "text-obsidian-muted hover:text-obsidian-secondary"
              )}
            >
              Catalog
            </button>
            <span className="text-obsidian-muted">&bull;</span>
            <button
              type="button"
              data-active={activeStep === "titles"}
              onClick={() => setActiveStep("titles")}
              className={cn(
                "px-2.5 py-0.5 rounded transition-all text-[10px] shrink-0",
                activeStep === "titles"
                  ? "bg-amber-500 text-canvas font-bold ring-1 ring-amber-400 shadow-glow"
                  : "text-obsidian-muted hover:text-obsidian-secondary"
              )}
            >
              10 Titles
            </button>
            <span className="text-obsidian-muted">&bull;</span>
            <button
              type="button"
              data-active={activeStep === "synopses"}
              onClick={() => {
                if (lockedTitle) setActiveStep("synopses");
              }}
              disabled={!lockedTitle}
              className={cn(
                "px-2.5 py-0.5 rounded transition-all text-[10px] shrink-0",
                activeStep === "synopses"
                  ? "bg-amber-500 text-canvas font-bold ring-1 ring-amber-400 shadow-glow"
                  : !lockedTitle
                  ? "opacity-40 cursor-not-allowed"
                  : "text-obsidian-muted hover:text-obsidian-secondary"
              )}
            >
              10 Synopses
            </button>
          </div>
        </div>

        {/* Scrollable Content Body */}
        <div className="p-4 sm:p-5 space-y-4 overflow-y-auto flex-1 overscroll-contain">
          {/* ============================================================== */}
          {/* STEP 1: DYNAMIC TREND CATALOG                                   */}
          {/* ============================================================== */}
          {activeStep === "catalog" && (
            <div className="space-y-3 animate-in fade-in duration-150">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold font-cinzel text-obsidian-primary uppercase tracking-wide">
                    YouTube Algorithmic Trend Archetypes
                  </h4>
                  <p className="text-[11px] text-obsidian-muted">
                    Pilih format genre untuk auto-sync rasio, visual style, dan ideasi judul:
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setActiveStep("titles");
                    generateTitles();
                  }}
                  className="text-xs text-amber-400 hover:text-amber-300 font-mono underline flex items-center gap-1 shrink-0"
                >
                  <span>Skip to Ideation</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>

              {isLoadingCatalog ? (
                <div className="py-12 flex flex-col items-center justify-center gap-2 text-obsidian-muted font-mono text-xs">
                  <div className="w-6 h-6 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
                  <span>Scanning YouTube trend patterns...</span>
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-2.5">
                  {catalog.map((item) => (
                    <div
                      key={item.id}
                      onClick={() => handleCatalogPick(item)}
                      className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-amber-500/50 hover:bg-slate-800/80 cursor-pointer transition-all group"
                    >
                      <div className="flex items-start justify-between gap-2 mb-1">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-xs text-obsidian-primary group-hover:text-amber-400 transition-colors">
                            {item.category}
                          </span>
                          <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                            {item.target_style_code}
                          </span>
                          <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-obsidian-secondary">
                            {item.aspect_ratio}
                          </span>
                        </div>
                        <span className="text-[10px] text-emerald-400 font-mono shrink-0">
                          {item.trend_tag}
                        </span>
                      </div>

                      <p className="text-[11px] text-obsidian-muted line-clamp-2 mb-2 font-sans">
                        {item.suggested_premise_seed}
                      </p>

                      <div className="flex items-center justify-between text-[10px] font-mono pt-1 border-t border-slate-800/60">
                        <span className="text-obsidian-secondary">
                          Avg. Cut Pacing: <span className="text-amber-400">{item.avg_retention_pacing}</span>
                        </span>
                        <div className="flex items-center gap-1 text-amber-400 group-hover:translate-x-0.5 transition-transform font-bold">
                          <span>Apply & Ideate</span>
                          <ArrowRight className="w-3 h-3" />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ============================================================== */}
          {/* STEP 2: 10 TITLE RECOMMENDATIONS                                */}
          {/* ============================================================== */}
          {activeStep === "titles" && (
            <div className="space-y-3 animate-in fade-in duration-150">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h4 className="text-xs font-bold font-cinzel text-obsidian-primary uppercase tracking-wide">
                    10 YouTube Title Recommendations
                  </h4>
                  <p className="text-[11px] text-obsidian-muted">
                    Daftar judul beralgoritma tinggi dengan curiosity gap & CTR hook:
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={() => setActiveStep("catalog")}
                    className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-obsidian-secondary hover:text-amber-400 text-xs font-mono flex items-center gap-1.5 transition-colors"
                  >
                    <ArrowLeft className="w-3.5 h-3.5" />
                    <span>← Kembali ke Katalog</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => generateTitles()}
                    disabled={isGeneratingTitles}
                    className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-amber-400 text-xs font-mono flex items-center gap-1.5 transition-colors"
                  >
                    <RotateCcw className={cn("w-3 h-3", isGeneratingTitles && "animate-spin")} />
                    <span>Regenerate</span>
                  </button>
                </div>
              </div>

              {titlesError && (
                <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-mono">
                  {titlesError}
                </div>
              )}

              {/* 1-Click Copy SEO Description Tags Block (Point 6 & Refinement 2) */}
              {seoTags.length > 0 && !isGeneratingTitles && (
                <div className="p-3 rounded-xl bg-slate-900/90 border border-amber-500/30 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5 text-xs font-mono font-semibold text-amber-400">
                      <Hash className="w-3.5 h-3.5" />
                      <span>SEO Description Hashtags & Keywords</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        const normalized = seoTags
                          .map((t) => (t.trim().startsWith("#") ? t.trim() : `#${t.trim()}`))
                          .join(" ");
                        navigator.clipboard.writeText(normalized);
                        setCopiedSeo(true);
                        setTimeout(() => setCopiedSeo(false), 2000);
                      }}
                      className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono bg-canvas hover:bg-slate-800 text-amber-400 border border-amber-500/30 transition-colors shadow-sm"
                    >
                      {copiedSeo ? (
                        <>
                          <Check className="w-3.5 h-3.5 text-emerald-400 stroke-[2.5]" />
                          <span className="text-emerald-400 font-bold">Copied!</span>
                        </>
                      ) : (
                        <>
                          <Copy className="w-3.5 h-3.5" />
                          <span>Salin Tagar SEO (1-Click)</span>
                        </>
                      )}
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto pt-1">
                    {seoTags.map((tag, idx) => {
                      const cleanTag = tag.trim().startsWith("#") ? tag.trim() : `#${tag.trim()}`;
                      return (
                        <span
                          key={idx}
                          className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-canvas/90 text-obsidian-secondary border border-border/80"
                        >
                          {cleanTag}
                        </span>
                      );
                    })}
                  </div>
                </div>
              )}

              {isGeneratingTitles ? (
                <div className="py-14 flex flex-col items-center justify-center gap-2.5 text-obsidian-muted font-mono text-xs">
                  <div className="w-7 h-7 border-2 border-amber-500 border-t-transparent rounded-full animate-spin shadow-glow" />
                  <span>Polya AI synthesizing 10 viral title candidates...</span>
                  <span className="text-[10px] text-obsidian-secondary">Applying YouTube 2026 CTR framework</span>
                </div>
              ) : titles.length === 0 ? (
                <div className="py-10 text-center space-y-2">
                  <p className="text-xs text-obsidian-muted font-mono">Belum ada rekomendasi judul yang dibuat.</p>
                  <button
                    type="button"
                    onClick={() => generateTitles()}
                    className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-semibold text-xs shadow-glow transition-all"
                  >
                    Generate 10 Titles Now
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  {titles.map((item) => {
                    const isSelected = lockedTitle === item.title;
                    return (
                      <div
                        key={item.rank}
                        className={cn(
                          "min-h-[145px] p-4 sm:p-4.5 rounded-xl border transition-all text-left flex flex-col justify-between gap-2.5",
                          isSelected
                            ? "bg-amber-500/10 border-amber-500 ring-1 ring-amber-500/30"
                            : "bg-slate-900/80 border-slate-800 hover:border-slate-700"
                        )}
                      >
                        <div className="space-y-1.5">
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex items-start gap-2.5 min-w-0">
                              <span className="w-5 h-5 rounded bg-canvas border border-border text-[10px] font-mono font-bold text-amber-400 flex items-center justify-center shrink-0">
                                #{item.rank}
                              </span>
                              <div className="min-w-0">
                                <h5 className="font-bold text-xs sm:text-sm text-obsidian-primary leading-snug">
                                  {item.title}
                                </h5>
                                <p className="text-[10px] text-obsidian-muted font-mono mt-0.5">
                                  slug: <span className="text-obsidian-secondary">{item.slug}</span>
                                </p>
                              </div>
                            </div>

                            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shrink-0 font-bold">
                              ★ {item.hook_score}
                            </span>
                          </div>

                          <div className="text-[11px] text-obsidian-muted italic pl-7 font-sans">
                            &ldquo;{item.trend_hook}&rdquo;
                          </div>

                          {/* Keyword tags container with full width wrapping so they are never truncated or obscured */}
                          <div className="flex flex-wrap gap-1.5 pl-7 py-1">
                            {item.target_keywords?.map((kw, i) => (
                              <span
                                key={i}
                                className="text-[9px] font-mono px-2 py-0.5 rounded bg-slate-800/90 text-obsidian-secondary border border-slate-700/50"
                              >
                                #{kw}
                              </span>
                            ))}
                          </div>
                        </div>

                        {/* Action CTA Button at bottom flow (mt-auto) */}
                        <div className="mt-auto pt-2.5 border-t border-slate-800/60 flex items-center justify-end w-full pl-0 sm:pl-7">
                          <button
                            type="button"
                            onClick={() => handleConfirmTitle(item)}
                            className={cn(
                              "px-3.5 py-1.5 rounded-lg text-xs font-semibold font-sans transition-all flex items-center gap-1.5 shrink-0",
                              isSelected
                                ? "bg-amber-500 text-canvas shadow-glow"
                                : "bg-slate-800 hover:bg-amber-500 hover:text-canvas text-amber-400 border border-border"
                            )}
                          >
                            {isSelected ? (
                              <>
                                <Check className="w-3.5 h-3.5 stroke-[2.5]" />
                                <span>Terpilih & Lanjut</span>
                              </>
                            ) : (
                              <>
                                <span>Gunakan Judul Ini</span>
                                <ArrowRight className="w-3.5 h-3.5" />
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* ============================================================== */}
          {/* STEP 3: 10 SYNOPSIS VARIATIONS                                 */}
          {/* ============================================================== */}
          {activeStep === "synopses" && (
            <div className="space-y-3 animate-in fade-in duration-150">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold font-cinzel text-obsidian-primary uppercase tracking-wide">
                    10 Logline & Synopsis Variations
                  </h4>
                  <p className="text-[11px] text-obsidian-muted">
                    Dirancang dengan retention hook 5 detik pertama & cliffhanger dramatis:
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => generateSynopses(lockedTitle)}
                  disabled={isGeneratingSynopses || !lockedTitle}
                  className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-amber-400 text-xs font-mono flex items-center gap-1.5 transition-colors shrink-0"
                >
                  <RotateCcw className={cn("w-3 h-3", isGeneratingSynopses && "animate-spin")} />
                  <span>Regenerate</span>
                </button>
              </div>

              {/* Locked Title Context Card */}
              {lockedTitle && (
                <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-between gap-3 text-xs">
                  <div className="flex items-center gap-2 min-w-0 font-mono">
                    <span className="text-amber-500 font-bold shrink-0">LOCKED TITLE:</span>
                    <span className="font-semibold text-obsidian-primary truncate">{lockedTitle}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setActiveStep("titles")}
                    className="text-[10px] font-mono text-amber-400 hover:text-amber-300 underline shrink-0"
                  >
                    Change Title
                  </button>
                </div>
              )}

              {synopsesError && (
                <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-mono">
                  {synopsesError}
                </div>
              )}

              {isGeneratingSynopses ? (
                <div className="py-14 flex flex-col items-center justify-center gap-2.5 text-obsidian-muted font-mono text-xs">
                  <div className="w-7 h-7 border-2 border-amber-500 border-t-transparent rounded-full animate-spin shadow-glow" />
                  <span>Synthesizing 10 high-retention premise variations...</span>
                  <span className="text-[10px] text-obsidian-secondary">Calibrating cold open stakes</span>
                </div>
              ) : synopses.length === 0 ? (
                <div className="py-10 text-center space-y-2">
                  <p className="text-xs text-obsidian-muted font-mono">Belum ada sinopsis yang dibuat.</p>
                  <button
                    type="button"
                    onClick={() => generateSynopses(lockedTitle)}
                    disabled={!lockedTitle}
                    className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-canvas font-semibold text-xs shadow-glow transition-all"
                  >
                    Generate 10 Synopses Now
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  {synopses.map((item) => {
                    const isSelected = lockedSynopsis === item.synopsis;
                    return (
                      <div
                        key={item.rank}
                        className={cn(
                          "p-3.5 rounded-xl border transition-all text-left flex flex-col gap-2.5",
                          isSelected
                            ? "bg-amber-500/10 border-amber-500 ring-1 ring-amber-500/30"
                            : "bg-slate-900/80 border-slate-800 hover:border-slate-700"
                        )}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="w-5 h-5 rounded bg-canvas border border-border text-[10px] font-mono font-bold text-amber-400 flex items-center justify-center shrink-0">
                              #{item.rank}
                            </span>
                            <span className="font-bold text-xs text-amber-300 font-mono">
                              {item.angle_label}
                            </span>
                          </div>

                          <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-slate-800 text-obsidian-muted truncate max-w-[150px]">
                            Audience: {item.target_audience || "General Audience"}
                          </span>
                        </div>

                        <p className="text-xs text-obsidian-primary leading-relaxed font-sans">
                          {item.synopsis}
                        </p>

                        <div className="p-2 rounded-lg bg-slate-950/70 border border-slate-800 text-[10px] font-mono text-obsidian-secondary flex items-start gap-1.5">
                          <Zap className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                          <div>
                            <span className="text-amber-400 font-bold">5s Hook: </span>
                            <span>{item.retention_hook}</span>
                          </div>
                        </div>

                        <div className="flex items-center justify-end pt-1">
                          <button
                            type="button"
                            onClick={() => handleConfirmSynopsis(item)}
                            className={cn(
                              "px-3.5 py-1.5 rounded-lg text-xs font-semibold font-sans transition-all flex items-center gap-1.5",
                              isSelected
                                ? "bg-emerald-500 text-slate-950 font-bold"
                                : "bg-amber-500 hover:bg-amber-600 text-canvas shadow-glow"
                            )}
                          >
                            {isSelected ? (
                              <>
                                <Check className="w-3.5 h-3.5 stroke-[2.5]" />
                                <span>Terapkan & Selesai</span>
                              </>
                            ) : (
                              <>
                                <Check className="w-3 h-3 stroke-[2]" />
                                <span>Gunakan Sinopsis Ini</span>
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Drawer Sticky Footer */}
        <div className="px-3.5 sm:px-5 py-2.5 sm:py-3 border-t border-border/80 flex items-center justify-between gap-2 text-xs font-mono text-obsidian-muted shrink-0 bg-slate-900/90">
          <div className="flex items-center gap-2 shrink-0 whitespace-nowrap">
            <span className="relative flex h-2 w-2 shrink-0">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
            </span>
            <span className="text-[11px] sm:text-xs font-semibold text-emerald-400 tracking-wide">
              Polya AI Live
            </span>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="px-2.5 sm:px-3 py-1.5 sm:py-1 rounded bg-slate-800 hover:bg-slate-700 text-obsidian-primary transition-colors text-[11px] sm:text-xs shrink-0 whitespace-nowrap"
          >
            Review & Return to Form
          </button>
        </div>
      </div>
    </div>
  );
}
