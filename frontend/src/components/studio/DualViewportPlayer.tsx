"use client";

import React, { useState, useEffect } from "react";
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
} from "lucide-react";
import { cn } from "@/lib/utils";

export type AspectRatioType = "2.39:1" | "16:9" | "9:16";
export type ViewportMode = "dual" | "a_roll" | "b_roll";

interface DualViewportPlayerProps {
  aspectRatio: AspectRatioType;
  onChangeAspectRatio: (ratio: AspectRatioType) => void;
  currentSceneTitle?: string;
  styleCode?: string;
  cameraCode?: string;
  lightingCode?: string;
}

export default function DualViewportPlayer({
  aspectRatio,
  onChangeAspectRatio,
  currentSceneTitle = "SCENE 01 - CYBERPUNK LAB - INT - NIGHT",
  styleCode = "#Style 01",
  cameraCode = "#Cam 01",
  lightingCode = "#Light 01",
}: DualViewportPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [viewportMode, setViewportMode] = useState<ViewportMode>("dual");
  const [timecodeSeconds, setTimecodeSeconds] = useState(14.5);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1.0);
  const [isMuted, setIsMuted] = useState(false);
  const [activeFrame, setActiveFrame] = useState(348); // 24 fps
  const [lastTransportKey, setLastTransportKey] = useState<string | null>(null);

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

  // Aspect ratio styling container class
  const getAspectContainerClass = () => {
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
                viewportMode === "dual" ? getAspectContainerClass() : getAspectContainerClass() + " w-full max-w-[800px]"
              )}
            >
              {/* Cinematic Letterbox Simulation / Canvas */}
              <div className="absolute inset-0 bg-gradient-to-tr from-black via-[#0B0F17] to-[#161D26] flex items-center justify-center overflow-hidden">
                {/* Simulated Film Grain & Scanlines */}
                <div className="absolute inset-0 opacity-[0.07] bg-[radial-gradient(#fff_1px,transparent_1px)] [background-size:16px_16px]" />
                
                {/* Visual Viewport Placeholder Graphic */}
                <div className="text-center p-6 space-y-3 z-10">
                  <div className="w-16 h-16 rounded-2xl bg-panel/80 border border-amber-500/30 flex items-center justify-center mx-auto text-amber-400 shadow-glow">
                    <Film className="w-8 h-8 animate-pulse" />
                  </div>
                  <div className="space-y-1">
                    <div className="font-cinzel text-sm uppercase font-bold tracking-widest text-obsidian-primary">
                      A-Roll Primary Generation
                    </div>
                    <div className="font-mono text-[11px] text-obsidian-muted flex items-center justify-center gap-2">
                      <span>{styleCode}</span>
                      <span>&bull;</span>
                      <span>{cameraCode}</span>
                      <span>&bull;</span>
                      <span>{lightingCode}</span>
                    </div>
                  </div>
                </div>

                {/* Animated Playback Progress Glow Bar */}
                {isPlaying && (
                  <div className="absolute bottom-0 left-0 right-0 h-1 bg-amber-500 animate-pulse shadow-glow" />
                )}
              </div>

              {/* Viewport A Overlay Header */}
              <div className="relative z-20 p-2.5 flex items-center justify-between bg-gradient-to-b from-black/80 to-transparent text-[11px] font-mono">
                <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 font-bold border border-amber-500/30">
                  A-ROLL // LIVE GENERATION
                </span>
                <span className="px-1.5 py-0.5 rounded bg-black/60 text-obsidian-muted border border-border">
                  4K DCI &bull; {aspectRatio}
                </span>
              </div>

              {/* Viewport A Overlay Footer: Timecode & Frame */}
              <div className="relative z-20 p-2.5 flex items-center justify-between bg-gradient-to-t from-black/90 to-transparent text-[11px] font-mono text-obsidian-secondary">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                  <span className="text-obsidian-primary font-bold">
                    {formatTimecode(timecodeSeconds)}
                  </span>
                </div>
                <span>FRAME {activeFrame.toString().padStart(5, "0")}</span>
              </div>
            </div>
          )}

          {/* Viewport B: Reference Continuity Master (B-Roll / DNA Anchor) */}
          {(viewportMode === "dual" || viewportMode === "b_roll") && (
            <div
              className={cn(
                "relative rounded-lg overflow-hidden border border-border/80 bg-obsidian-canvas flex flex-col justify-between shadow-2xl group",
                viewportMode === "dual" ? getAspectContainerClass() : getAspectContainerClass() + " w-full max-w-[800px]"
              )}
            >
              {/* Reference Canvas Simulation */}
              <div className="absolute inset-0 bg-gradient-to-tl from-black via-[#13171F] to-[#1E2530] flex items-center justify-center overflow-hidden">
                <div className="absolute inset-0 opacity-[0.05] bg-[radial-gradient(#38bdf8_1px,transparent_1px)] [background-size:16px_16px]" />
                
                {/* Visual Viewport Placeholder Graphic */}
                <div className="text-center p-6 space-y-3 z-10">
                  <div className="w-16 h-16 rounded-2xl bg-panel/80 border border-blue-500/30 flex items-center justify-center mx-auto text-blue-400 shadow-sm">
                    <Camera className="w-8 h-8" />
                  </div>
                  <div className="space-y-1">
                    <div className="font-cinzel text-sm uppercase font-bold tracking-widest text-obsidian-primary">
                      Reference Continuity Anchor
                    </div>
                    <div className="font-mono text-[11px] text-obsidian-muted flex items-center justify-center gap-2">
                      <span>Face Seed #Protagonist_01</span>
                      <span>&bull;</span>
                      <span>98.4% Match</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Viewport B Overlay Header */}
              <div className="relative z-20 p-2.5 flex items-center justify-between bg-gradient-to-b from-black/80 to-transparent text-[11px] font-mono">
                <span className="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 font-bold border border-blue-500/30">
                  B-ROLL // DNA MASTER LOCK
                </span>
                <span className="px-1.5 py-0.5 rounded bg-black/60 text-emerald-400 border border-emerald-500/30">
                  QC PASS: 94.2
                </span>
              </div>

              {/* Viewport B Overlay Footer */}
              <div className="relative z-20 p-2.5 flex items-center justify-between bg-gradient-to-t from-black/90 to-transparent text-[11px] font-mono text-obsidian-secondary">
                <span className="text-obsidian-muted">INSIGHTFACE BIOMETRIC REF</span>
                <span className="text-blue-400 font-semibold">IMMUTABLE ANCHOR</span>
              </div>
            </div>
          )}
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
