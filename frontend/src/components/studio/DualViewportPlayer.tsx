"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Play,
  Pause,
  RotateCcw,
  FastForward,
  Rewind,
  Volume2,
  VolumeX,
  Columns,
  Eye,
  Layers,
  Film,
  Camera,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Character, resolveMediaUrl } from "@/lib/api";

export type AspectRatioType = "2.39:1" | "16:9" | "9:16";
export type ViewportMode = "dual" | "a_roll" | "b_roll";

interface DualViewportPlayerProps {
  aspectRatio: AspectRatioType;
  onChangeAspectRatio: (ratio: AspectRatioType) => void;
  currentSceneTitle?: string;
  styleCode?: string;
  cameraCode?: string;
  lightingCode?: string;
  previewUrl?: string | null;
  previewProvider?: string | null;
  onGeneratePreview?: () => void;
  isLoadingPreview?: boolean;
  characterList?: Character[];
  activeCharacterId?: string | null;
  onSelectCharacter?: (characterId: string) => void;
  projectId?: string;
  previewError?: string | null;
}

function getProviderBadge(provider?: string | null): { label: string; className: string } | null {
  if (!provider) return null;
  const p = provider.toLowerCase();
  if (p.includes("9router") || p.includes("gemini")) {
    return {
      label: "9Router",
      className: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
    };
  }
  if (p.includes("sd35") || p.includes("hf") || p.includes("huggingface")) {
    return {
      label: "SD3.5",
      className: "bg-cyan-500/20 text-cyan-300 border-cyan-500/40",
    };
  }
  if (p.includes("mock") || p.includes("offline") || p.includes("local")) {
    return {
      label: "Offline Fallback",
      className: "bg-amber-500/20 text-amber-300 border-amber-500/40",
    };
  }
  return {
    label: provider,
    className: "bg-purple-500/20 text-purple-300 border-purple-500/40",
  };
}

export default function DualViewportPlayer({
  aspectRatio,
  onChangeAspectRatio,
  currentSceneTitle = "SCENE 01 - CYBERPUNK LAB - INT - NIGHT",
  styleCode = "#Style 01",
  cameraCode = "#Cam 01",
  lightingCode = "#Light 01",
  previewUrl,
  previewProvider,
  onGeneratePreview,
  isLoadingPreview = false,
  characterList,
  activeCharacterId,
  onSelectCharacter,
  projectId,
  previewError,
}: DualViewportPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [viewportMode, setViewportMode] = useState<ViewportMode>("dual");
  const [timecodeSeconds, setTimecodeSeconds] = useState(14.5);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1.0);
  const [isMuted, setIsMuted] = useState(false);
  const [activeFrame, setActiveFrame] = useState(348); // 24 fps
  const [lastTransportKey, setLastTransportKey] = useState<string | null>(null);
  const [charImgError, setCharImgError] = useState(false);

  // Playback loop simulation
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isPlaying) {
      interval = setInterval(() => {
        setTimecodeSeconds((prev) => {
          const next = prev + 0.1 * playbackSpeed;
          return next > 300 ? 0 : next;
        });
        setActiveFrame((prev) => (prev + Math.round(2.4 * playbackSpeed)) % 7200);
      }, 100);
    }
    return () => clearInterval(interval);
  }, [isPlaying, playbackSpeed]);

  // Keyboard Transport Controls (J = Rewind, K = Pause/Play, L = Fast Forward, Space = Toggle)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't intercept if user is typing in input or textarea
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) {
        return;
      }

      const key = e.key.toLowerCase();
      if (key === "k" || e.code === "Space") {
        e.preventDefault();
        setIsPlaying((prev) => !prev);
        setLastTransportKey(isPlaying ? "PAUSE (K)" : "PLAY (K)");
      } else if (key === "j") {
        e.preventDefault();
        setTimecodeSeconds((prev) => Math.max(0, prev - 2.5));
        setActiveFrame((prev) => Math.max(0, prev - 60));
        setLastTransportKey("REWIND -2.5s (J)");
      } else if (key === "l") {
        e.preventDefault();
        setTimecodeSeconds((prev) => prev + 2.5);
        setActiveFrame((prev) => prev + 60);
        setLastTransportKey("FAST-FORWARD +2.5s (L)");
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isPlaying]);

  // Clear key toast
  useEffect(() => {
    if (lastTransportKey) {
      const timer = setTimeout(() => setLastTransportKey(null), 1200);
      return () => clearTimeout(timer);
    }
  }, [lastTransportKey]);

  // Format timecode (HH:MM:SS:FF at 24fps)
  const formatTimecode = (sec: number) => {
    const hours = Math.floor(sec / 3600);
    const minutes = Math.floor((sec % 3600) / 60);
    const seconds = Math.floor(sec % 60);
    const frames = Math.floor((sec % 1) * 24);
    return `${hours.toString().padStart(2, "0")}:${minutes
      .toString()
      .padStart(2, "0")}:${seconds.toString().padStart(2, "0")}:${frames
      .toString()
      .padStart(2, "0")}`;
  };

  // Aspect ratio styling container class:
  // When media is present, enforce strict aspect ratio.
  // In placeholder/empty state on mobile, allow normal flex flow with min-h-[280px] sm:min-h-[320px] to prevent HUD collision.
  const getAspectContainerClass = (hasMedia: boolean) => {
    if (!hasMedia) {
      return "min-h-[280px] sm:min-h-[320px]";
    }
    switch (aspectRatio) {
      case "2.39:1":
        return "aspect-[2.39/1]";
      case "16:9":
        return "aspect-video";
      case "9:16":
        return "aspect-[9/16] max-h-[460px] mx-auto";
      default:
        return "aspect-video";
    }
  };

  return (
    <div className="flex flex-col bg-panel border border-border rounded-xl overflow-hidden shadow-studio">
      {/* Top Header Bar: Modes & Aspect Ratio Presets */}
      <div className="p-3 border-b border-border bg-elevated/40 flex flex-wrap items-center justify-between gap-3 text-xs">
        {/* Left: Viewport Mode Switcher */}
        <div className="flex items-center gap-1.5">
          <div className="flex items-center p-0.5 bg-canvas rounded-lg border border-border">
            <button
              type="button"
              onClick={() => setViewportMode("dual")}
              className={cn(
                "px-2.5 py-1 rounded-md font-medium text-[11px] transition-all flex items-center gap-1.5",
                viewportMode === "dual"
                  ? "bg-elevated text-amber-400 border border-amber-500/30 shadow-sm"
                  : "text-obsidian-muted hover:text-obsidian-primary"
              )}
            >
              <Columns className="w-3.5 h-3.5" />
              <span>Dual-Viewport</span>
            </button>
            <button
              type="button"
              onClick={() => setViewportMode("a_roll")}
              className={cn(
                "px-2.5 py-1 rounded-md font-medium text-[11px] transition-all flex items-center gap-1.5",
                viewportMode === "a_roll"
                  ? "bg-elevated text-amber-400 border border-amber-500/30 shadow-sm"
                  : "text-obsidian-muted hover:text-obsidian-primary"
              )}
            >
              <Eye className="w-3.5 h-3.5" />
              <span>A-Roll Only</span>
            </button>
            <button
              type="button"
              onClick={() => setViewportMode("b_roll")}
              className={cn(
                "px-2.5 py-1 rounded-md font-medium text-[11px] transition-all flex items-center gap-1.5",
                viewportMode === "b_roll"
                  ? "bg-elevated text-amber-400 border border-amber-500/30 shadow-sm"
                  : "text-obsidian-muted hover:text-obsidian-primary"
              )}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Reference Continuity</span>
            </button>
          </div>
        </div>

        {/* Center: Active Scene Slugline */}
        <div className="hidden md:flex items-center gap-2 font-mono text-[11px] text-obsidian-secondary truncate max-w-sm">
          <span className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />
          <span className="truncate">{currentSceneTitle}</span>
        </div>

        {/* Right: Aspect Ratio Presets */}
        <div className="flex items-center gap-1">
          <span className="text-[10px] font-mono text-obsidian-muted uppercase mr-1">Aspect:</span>
          {(["2.39:1", "16:9", "9:16"] as AspectRatioType[]).map((ratio) => (
            <button
              key={ratio}
              type="button"
              onClick={() => onChangeAspectRatio(ratio)}
              className={cn(
                "px-2 py-0.5 rounded text-[11px] font-mono font-semibold transition-all border",
                aspectRatio === ratio
                  ? "bg-amber-500/20 text-amber-400 border-amber-500/40 shadow-sm"
                  : "bg-canvas/60 text-obsidian-muted hover:text-obsidian-primary border-border"
              )}
            >
              {ratio}
            </button>
          ))}
        </div>
      </div>

      {/* Main Viewport Stage Area */}
      <div className="relative bg-canvas p-4 sm:p-6 flex items-center justify-center min-h-[380px] lg:min-h-[440px] overflow-hidden">
        {/* Keypress Transport HUD Overlay */}
        {lastTransportKey && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 z-30 px-3 py-1 rounded-full bg-elevated/90 border border-amber-500/50 text-amber-400 font-mono text-xs shadow-glow animate-in fade-in zoom-in duration-100">
            {lastTransportKey}
          </div>
        )}

        <div
          className={cn(
            "w-full transition-all duration-300",
            viewportMode === "dual"
              ? "grid grid-cols-1 lg:grid-cols-2 gap-4"
              : "flex justify-center"
          )}
        >
          {/* Viewport A: Generative Video Stream (A-Roll) */}
          {(viewportMode === "dual" || viewportMode === "a_roll") && (
            <div
              className={cn(
                "relative rounded-lg overflow-hidden border border-border/80 bg-obsidian-canvas flex flex-col justify-between shadow-2xl group",
                viewportMode === "dual"
                  ? getAspectContainerClass(Boolean(previewUrl))
                  : cn(getAspectContainerClass(Boolean(previewUrl)), "w-full max-w-[800px]")
              )}
            >
              {/* Layer 0: Ambient Background & Media Canvas */}
              <div className="absolute inset-0 bg-gradient-to-tr from-black via-[#0B0F17] to-[#161D26] pointer-events-none z-0 overflow-hidden">
                <div className="absolute inset-0 opacity-[0.07] bg-[radial-gradient(#fff_1px,transparent_1px)] [background-size:16px_16px]" />

                {previewUrl && (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img
                    src={previewUrl}
                    alt="A-Roll 360p Live Preview"
                    className="w-full h-full object-cover pointer-events-auto"
                  />
                )}

                {/* Animated Playback Progress Glow Bar */}
                {isPlaying && (
                  <div className="absolute bottom-0 left-0 right-0 h-1 bg-amber-500 animate-pulse shadow-glow z-10" />
                )}
              </div>

              {/* Layer 1: Normal Document Flow Container */}
              <div className="relative z-10 flex flex-col justify-between min-h-full flex-1 w-full">
                {/* Viewport A Header Bar */}
                {(() => {
                  const providerBadge = getProviderBadge(previewProvider);
                  return (
                    <div className="shrink-0 p-2 sm:p-2.5 flex items-center justify-between gap-1.5 bg-gradient-to-b from-black/80 to-transparent text-[10px] sm:text-[11px] font-mono">
                      <div className="flex items-center gap-1.5 min-w-0 flex-wrap">
                        <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 font-bold border border-amber-500/30 shrink-0">
                          A-ROLL<span className="hidden sm:inline">{" // LIVE GENERATION"}</span>
                        </span>
                        {providerBadge && (
                          <span
                            className={cn(
                              "px-1.5 py-0.5 rounded border text-[9px] sm:text-[10px] font-bold shrink-0",
                              providerBadge.className
                            )}
                          >
                            {providerBadge.label}
                          </span>
                        )}
                        {previewUrl && onGeneratePreview && (
                          <button
                            type="button"
                            onClick={onGeneratePreview}
                            disabled={isLoadingPreview}
                            className="px-1.5 py-0.5 rounded bg-slate-800/80 hover:bg-slate-700 text-amber-400 border border-border flex items-center gap-1 transition-colors text-[9px] sm:text-[10px] shrink-0 disabled:opacity-50 cursor-pointer"
                            title="Regenerate 360p Preview"
                          >
                            <Sparkles className="w-2.5 h-2.5" />
                            <span>Regen</span>
                          </button>
                        )}
                      </div>
                      <span className="px-1.5 py-0.5 rounded bg-black/60 text-obsidian-muted border border-border shrink-0 text-[9px] sm:text-[10px]">
                        360p PREVIEW &bull; {aspectRatio}
                      </span>
                    </div>
                  );
                })()}

                {/* Center Interactive Stage */}
                {previewUrl && isLoadingPreview ? (
                  <div className="flex-1 flex flex-col items-center justify-center p-4 my-auto bg-black/65 backdrop-blur-[2px] rounded-lg mx-2 text-center space-y-2 z-20">
                    <div className="w-9 h-9 border-2 border-amber-500 border-t-transparent rounded-full animate-spin mx-auto shadow-glow" />
                    <div className="font-mono text-xs text-amber-400 font-bold uppercase tracking-wider">
                      Regenerating 360p Preview...
                    </div>
                    <div className="font-mono text-[10px] text-obsidian-muted">
                      Polya AI Preview Engine &bull; {aspectRatio}
                    </div>
                  </div>
                ) : !previewUrl ? (
                  <div className="flex-1 flex flex-col items-center justify-center p-3 sm:p-4 my-auto text-center space-y-2.5">
                    {isLoadingPreview ? (
                      <div className="space-y-2">
                        <div className="w-10 h-10 border-2 border-amber-500 border-t-transparent rounded-full animate-spin mx-auto shadow-glow" />
                        <div className="font-mono text-xs text-amber-400 font-bold uppercase tracking-wider">
                          Rendering 360p Preview...
                        </div>
                        <div className="font-mono text-[10px] text-obsidian-muted">
                          Polya AI Preview Engine &bull; {aspectRatio}
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="w-12 h-12 rounded-xl bg-panel/80 border border-amber-500/30 flex items-center justify-center text-amber-400 shadow-glow">
                          <Film className="w-6 h-6 animate-pulse" />
                        </div>
                        <div>
                          <div className="font-cinzel text-xs sm:text-sm uppercase font-bold tracking-widest text-obsidian-primary">
                            A-Roll Primary Generation
                          </div>
                          <div className="font-mono text-[10px] sm:text-[11px] text-obsidian-muted flex items-center justify-center gap-2 mt-0.5">
                            <span>{styleCode}</span>
                            <span>&bull;</span>
                            <span>{cameraCode}</span>
                            <span>&bull;</span>
                            <span>{lightingCode}</span>
                          </div>
                        </div>

                        {previewError && (
                          <div className="px-3 py-1 rounded bg-rose-500/15 border border-rose-500/30 text-rose-300 font-mono text-[10px] max-w-xs">
                            {previewError}
                          </div>
                        )}

                        {onGeneratePreview && (
                          <button
                            type="button"
                            onClick={onGeneratePreview}
                            disabled={isLoadingPreview}
                            className="mt-1 px-4 py-2 min-h-[38px] rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 font-mono font-bold text-xs flex items-center gap-1.5 shadow-glow transition-all active:scale-95 disabled:opacity-50 cursor-pointer"
                          >
                            <Sparkles className="w-3.5 h-3.5" />
                            <span>Generate 360p Preview</span>
                          </button>
                        )}
                      </>
                    )}
                  </div>
                ) : (
                  <div className="flex-1" />
                )}

                {/* Bottom Footer Bar */}
                <div className="shrink-0 p-2 sm:p-2.5 flex items-center justify-between bg-gradient-to-t from-black/90 to-transparent text-[11px] font-mono text-obsidian-secondary">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                    <span className="text-obsidian-primary font-bold">
                      {formatTimecode(timecodeSeconds)}
                    </span>
                  </div>
                  <span>FRAME {activeFrame.toString().padStart(5, "0")}</span>
                </div>
              </div>
            </div>
          )}

          {/* Viewport B: Reference Continuity Master (B-Roll / DNA Anchor) */}
          {(viewportMode === "dual" || viewportMode === "b_roll") && (() => {
            const activeChar =
              characterList?.find((c) => c.id === activeCharacterId) ||
              characterList?.[0] ||
              null;
            const rawCharImageUrl =
              activeChar?.front_image_url ||
              activeChar?.closeup_image_url ||
              activeChar?.three_quarter_image_url ||
              activeChar?.side_image_url ||
              null;
            const charImageUrl = resolveMediaUrl(rawCharImageUrl);
            const hasCharMedia = Boolean(charImageUrl && !charImgError);

            return (
              <div
                className={cn(
                  "relative rounded-lg overflow-hidden border border-border/80 bg-obsidian-canvas flex flex-col justify-between shadow-2xl group",
                  viewportMode === "dual"
                    ? getAspectContainerClass(hasCharMedia)
                    : cn(getAspectContainerClass(hasCharMedia), "w-full max-w-[800px]")
                )}
              >
                {/* Layer 0: Ambient Background & Character Media */}
                <div className="absolute inset-0 bg-gradient-to-tl from-black via-[#13171F] to-[#1E2530] pointer-events-none z-0 overflow-hidden">
                  <div className="absolute inset-0 opacity-[0.05] bg-[radial-gradient(#38bdf8_1px,transparent_1px)] [background-size:16px_16px]" />

                  {hasCharMedia && (
                    <div className="relative w-full h-full">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={charImageUrl!}
                        alt={activeChar?.name || "Character Continuity Anchor"}
                        onError={() => setCharImgError(true)}
                        className="w-full h-full object-cover object-top pointer-events-auto"
                      />
                      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/30 pointer-events-none z-10" />
                      <div className="absolute inset-0 border border-blue-500/20 pointer-events-none z-10" />
                    </div>
                  )}
                </div>

                {/* Layer 1: Normal Document Flow Container */}
                <div className="relative z-10 flex flex-col justify-between min-h-full flex-1 w-full">
                  {/* Viewport B Header Bar */}
                  <div className="shrink-0 p-2 sm:p-2.5 flex items-center justify-between gap-1.5 bg-gradient-to-b from-black/80 to-transparent text-[10px] sm:text-[11px] font-mono">
                    <div className="flex items-center gap-1.5 min-w-0 flex-wrap">
                      <span className="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 font-bold border border-blue-500/30 shrink-0">
                        B-ROLL<span className="hidden sm:inline">{" // DNA MASTER LOCK"}</span>
                      </span>
                      {characterList && characterList.length > 1 && onSelectCharacter && (
                        <select
                          value={activeChar?.id || ""}
                          onChange={(e) => {
                            setCharImgError(false);
                            onSelectCharacter(e.target.value);
                          }}
                          className="px-1.5 py-0.5 rounded bg-black/80 text-blue-300 border border-blue-500/40 text-[9px] sm:text-[10px] font-mono focus:outline-none focus:ring-1 focus:ring-blue-400 max-w-[110px] sm:max-w-[140px] truncate cursor-pointer"
                          title="Switch Active Continuity Anchor"
                        >
                          {characterList.map((c) => (
                            <option key={c.id} value={c.id} className="bg-slate-900 text-white">
                              {c.name}
                            </option>
                          ))}
                        </select>
                      )}
                      {characterList && characterList.length === 1 && activeChar && (
                        <span className="px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-300 border border-blue-500/20 text-[9px] sm:text-[10px] truncate max-w-[100px]">
                          {activeChar.name}
                        </span>
                      )}
                    </div>
                    {activeChar ? (
                      <span className="px-1.5 py-0.5 rounded bg-black/60 text-emerald-400 border border-emerald-500/30 shrink-0 text-[9px] sm:text-[10px]">
                        QC PASS
                      </span>
                    ) : (
                      <span className="px-1.5 py-0.5 rounded bg-black/60 text-obsidian-muted border border-border shrink-0 text-[9px] sm:text-[10px]">
                        NO ANCHOR
                      </span>
                    )}
                  </div>

                  {/* Center Interactive Stage or Caption */}
                  {hasCharMedia ? (
                    <div className="flex-1 flex flex-col justify-end px-3 pb-1">
                      <div className="space-y-0.5">
                        <div className="font-cinzel text-xs font-bold text-white tracking-wider flex items-center gap-1.5">
                          <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                          <span>{activeChar?.name}</span>
                        </div>
                        <div className="font-mono text-[9px] text-blue-300/80">
                          DNA SEED #{activeChar?.dna_seed || "LOCKED"} &bull; {activeChar?.role || "LEAD"}
                        </div>
                      </div>
                    </div>
                  ) : activeChar ? (
                    <div className="flex-1 flex flex-col items-center justify-center p-3 sm:p-4 my-auto text-center space-y-2.5 max-w-xs mx-auto">
                      <div className="w-12 h-12 rounded-xl bg-panel/80 border border-blue-500/30 flex items-center justify-center mx-auto text-blue-400 shadow-sm">
                        <Camera className="w-6 h-6" />
                      </div>
                      <div className="space-y-1">
                        <div className="font-cinzel text-xs sm:text-sm uppercase font-bold tracking-wider text-obsidian-primary">
                          {activeChar.name}
                        </div>
                        <div className="font-mono text-[10px] sm:text-[11px] text-obsidian-muted">
                          Role: {activeChar.role} &bull; DNA Seed #{activeChar.dna_seed || "Pending"}
                        </div>
                      </div>
                      {projectId && (
                        <Link
                          href={`/projects/${projectId}/bible#characters`}
                          className="inline-flex items-center gap-1 px-3 py-1.5 min-h-[36px] rounded-lg bg-blue-500/20 hover:bg-blue-500/30 border border-blue-500/40 text-blue-300 font-mono text-[11px] font-semibold transition-colors cursor-pointer"
                        >
                          <span>Upload Character Sheet</span>
                        </Link>
                      )}
                    </div>
                  ) : (
                    <div className="flex-1 flex flex-col items-center justify-center p-3 sm:p-4 my-auto text-center space-y-2.5 max-w-xs mx-auto">
                      <div className="w-12 h-12 rounded-xl bg-panel/80 border border-border flex items-center justify-center mx-auto text-obsidian-muted shadow-sm">
                        <Layers className="w-6 h-6" />
                      </div>
                      <div className="space-y-1">
                        <div className="font-cinzel text-xs sm:text-sm uppercase font-bold tracking-wider text-obsidian-primary">
                          No Character Anchor
                        </div>
                        <p className="font-mono text-[10px] sm:text-[11px] text-obsidian-muted">
                          Lock visual continuity across shots with biometric facial DNA.
                        </p>
                      </div>
                      {projectId && (
                        <Link
                          href={`/projects/${projectId}/bible#characters`}
                          className="inline-flex items-center gap-1.5 px-4 py-2 min-h-[38px] rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-mono text-xs font-semibold shadow-md transition-all active:scale-95 cursor-pointer"
                        >
                          <Sparkles className="w-3.5 h-3.5" />
                          <span>Configure DNA Lock</span>
                        </Link>
                      )}
                    </div>
                  )}

                  {/* Viewport B Footer Bar */}
                  <div className="shrink-0 p-2 sm:p-2.5 flex items-center justify-between gap-1 bg-gradient-to-t from-black/90 to-transparent text-[10px] sm:text-[11px] font-mono text-obsidian-secondary">
                    <span className="text-obsidian-muted truncate">
                      {activeChar ? "INSIGHTFACE BIOMETRIC REF" : "CONTINUITY DISABLED"}
                    </span>
                    <span className="text-blue-400 font-semibold shrink-0">
                      {activeChar ? "IMMUTABLE ANCHOR" : "UNLOCKED"}
                    </span>
                  </div>
                </div>
              </div>
            );
          })()}
        </div>
      </div>

      {/* =========================================================================
       * Interactive Transport Controls & Keyboard Shortcuts Bar
       * ========================================================================= */}
      <div className="p-3 bg-panel border-t border-border flex flex-wrap items-center justify-between gap-3 text-xs">
        {/* Left: Transport Buttons (J / K / L) */}
        <div className="flex items-center gap-2">
          {/* Rewind (J) */}
          <button
            type="button"
            title="Rewind 2.5s (Hotkey: J)"
            onClick={() => {
              setTimecodeSeconds((p) => Math.max(0, p - 2.5));
              setActiveFrame((p) => Math.max(0, p - 60));
              setLastTransportKey("REWIND -2.5s (J)");
            }}
            className="p-2 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-secondary hover:text-obsidian-primary transition-colors"
          >
            <Rewind className="w-4 h-4" />
          </button>

          {/* Play / Pause Toggle (K or Space) */}
          <button
            type="button"
            title="Play / Pause (Hotkey: K or Space)"
            onClick={() => {
              setIsPlaying(!isPlaying);
              setLastTransportKey(isPlaying ? "PAUSE (K)" : "PLAY (K)");
            }}
            className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-bold flex items-center gap-2 transition-all shadow-glow"
          >
            {isPlaying ? <Pause className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current" />}
            <span className="font-mono text-xs">{isPlaying ? "PAUSE" : "PLAY"}</span>
          </button>

          {/* Fast Forward (L) */}
          <button
            type="button"
            title="Fast Forward 2.5s (Hotkey: L)"
            onClick={() => {
              setTimecodeSeconds((p) => p + 2.5);
              setActiveFrame((p) => p + 60);
              setLastTransportKey("FAST-FORWARD +2.5s (L)");
            }}
            className="p-2 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-secondary hover:text-obsidian-primary transition-colors"
          >
            <FastForward className="w-4 h-4" />
          </button>

          {/* Reset Frame */}
          <button
            type="button"
            title="Reset to Beginning"
            onClick={() => {
              setTimecodeSeconds(0);
              setActiveFrame(0);
              setIsPlaying(false);
            }}
            className="p-2 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-secondary hover:text-obsidian-primary transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Center: Timecode & Transport Hotkey Tooltip */}
        <div className="flex items-center gap-3 font-mono">
          <div className="px-3 py-1 rounded bg-canvas border border-border text-amber-400 font-bold tracking-wider text-xs">
            {formatTimecode(timecodeSeconds)}
          </div>
          <div className="hidden xl:flex items-center gap-1.5 text-[10px] text-obsidian-muted">
            <span className="px-1 py-0.5 rounded bg-canvas border border-border text-obsidian-secondary">J</span>
            <span>Rewind</span>
            <span className="px-1 py-0.5 rounded bg-canvas border border-border text-obsidian-secondary ml-1">K</span>
            <span>Pause/Play</span>
            <span className="px-1 py-0.5 rounded bg-canvas border border-border text-obsidian-secondary ml-1">L</span>
            <span>Forward</span>
          </div>
        </div>

        {/* Right: Playback Speed & Audio Controls */}
        <div className="flex items-center gap-2">
          {/* Speed Presets */}
          <div className="flex items-center p-0.5 bg-canvas rounded-lg border border-border text-[10px] font-mono">
            {[0.5, 1.0, 2.0].map((spd) => (
              <button
                key={spd}
                type="button"
                onClick={() => setPlaybackSpeed(spd)}
                className={cn(
                  "px-2 py-0.5 rounded font-semibold transition-colors",
                  playbackSpeed === spd
                    ? "bg-elevated text-amber-400 border border-amber-500/30"
                    : "text-obsidian-muted hover:text-obsidian-primary"
                )}
              >
                {spd}x
              </button>
            ))}
          </div>

          {/* Audio Mute Toggle */}
          <button
            type="button"
            onClick={() => setIsMuted(!isMuted)}
            className="p-2 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-secondary hover:text-obsidian-primary transition-colors"
            title={isMuted ? "Unmute" : "Mute"}
          >
            {isMuted ? <VolumeX className="w-3.5 h-3.5 text-rose-400" /> : <Volume2 className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>
    </div>
  );
}
