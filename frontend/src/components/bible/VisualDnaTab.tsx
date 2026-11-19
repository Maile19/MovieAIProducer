"use client";

import React, { useState } from "react";
import { Palette, Camera, Sliders, Check, Copy, Sparkles, Save } from "lucide-react";
import { DEFAULT_STYLES } from "@/lib/studio-constants";
import { cn } from "@/lib/utils";

interface VisualDnaTabProps {
  styleParameters: Record<string, any>;
  isLocked: boolean;
  onSave: (params: Record<string, any>) => void;
}

export default function VisualDnaTab({
  styleParameters,
  isLocked,
  onSave,
}: VisualDnaTabProps) {
  const [styleCode, setStyleCode] = useState(
    styleParameters?.master_style_code || styleParameters?.style_code || "#Style 01"
  );
  const [aspectRatio, setAspectRatio] = useState(styleParameters?.aspect_ratio || "2.39:1");
  const [renderPipeline, setRenderPipeline] = useState(
    styleParameters?.render_pipeline || "Photorealistic 35mm Film Grain"
  );
  const [filmStock, setFilmStock] = useState(
    styleParameters?.film_stock || "Kodak Vision3 5219 500T"
  );
  const [anamorphicSqueeze, setAnamorphicSqueeze] = useState(
    styleParameters?.anamorphic_squeeze || "2.0x Horizontal"
  );
  const [halationLevel, setHalationLevel] = useState(styleParameters?.halation_level || 0.35);

  const [copiedHex, setCopiedHex] = useState<string | null>(null);

  // Default DaVinci Obsidian Color Palette Tokens
  const paletteTokens = [
    { role: "Canvas Base", hex: "#090B0E", desc: "Ultra-dark obsidian baseline for letterboxing" },
    { role: "Panel Surface", hex: "#12161D", desc: "Rich charcoal container and background tone" },
    { role: "Cinema Amber", hex: "#F59E0B", desc: "Primary showrunner key illumination accent" },
    { role: "Emerald Continuity", hex: "#10B981", desc: "QC approval and biometric verification pass" },
    { role: "Rose Defect", hex: "#F43F5E", desc: "Continuity defect and revision alert indicator" },
  ];

  const handleCopy = (hex: string) => {
    navigator.clipboard.writeText(hex);
    setCopiedHex(hex);
    setTimeout(() => setCopiedHex(null), 1500);
  };

  const handleSaveAll = () => {
    onSave({
      master_style_code: styleCode,
      aspect_ratio: aspectRatio,
      render_pipeline: renderPipeline,
      film_stock: filmStock,
      anamorphic_squeeze: anamorphicSqueeze,
      halation_level: halationLevel,
    });
  };

  return (
    <div className="space-y-6 font-sans">
      {/* Header / Save Bar */}
      <div className="flex items-center justify-between p-4 rounded-xl bg-panel border border-border">
        <div>
          <h3 className="font-cinzel text-sm font-bold uppercase tracking-wider text-obsidian-primary flex items-center gap-2">
            <Palette className="w-4 h-4 text-amber-500" />
            <span>Master Visual DNA Specification</span>
          </h3>
          <p className="text-xs font-mono text-obsidian-muted mt-0.5">
            Governs color science, optical physics, camera baseline, and generative render targets.
          </p>
        </div>

        {!isLocked && (
          <button
            type="button"
            onClick={handleSaveAll}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-xs transition-all shadow-glow"
          >
            <Save className="w-3.5 h-3.5" />
            <span>Save Visual DNA</span>
          </button>
        )}
      </div>

      {/* Color Palette Tokens Section */}
      <div className="p-4 rounded-xl bg-panel border border-border space-y-3">
        <div className="flex items-center justify-between">
          <label className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary">
            DaVinci Obsidian Color Palette Tokens
          </label>
          <span className="text-[10px] font-mono text-obsidian-muted">
            Click hex to copy
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-5 gap-3">
          {paletteTokens.map((token) => (
            <div
              key={token.role}
              onClick={() => handleCopy(token.hex)}
              className="p-3 rounded-lg bg-canvas border border-border hover:border-amber-500/50 cursor-pointer transition-all group"
            >
              <div
                className="w-full h-12 rounded-md mb-2 border border-white/10 shadow-inner flex items-center justify-center"
                style={{ backgroundColor: token.hex }}
              >
                {copiedHex === token.hex ? (
                  <Check className="w-4 h-4 text-white drop-shadow" />
                ) : (
                  <Copy className="w-3.5 h-3.5 text-white/50 opacity-0 group-hover:opacity-100 transition-opacity" />
                )}
              </div>
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="font-bold text-obsidian-primary truncate">{token.role}</span>
                <span className="text-amber-400 text-[11px]">{token.hex}</span>
              </div>
              <p className="text-[10px] text-obsidian-muted mt-1 line-clamp-1">{token.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Master Style & Aspect Ratio Selection */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Style Code Selector */}
        <div className="p-4 rounded-xl bg-panel border border-border space-y-3">
          <label className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary flex items-center gap-1.5">
            <Sparkles className="w-4 h-4 text-amber-500" />
            <span>Master Style Code (#Style 01-18)</span>
          </label>
          <select
            value={styleCode}
            disabled={isLocked}
            onChange={(e) => setStyleCode(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-xs text-obsidian-primary font-mono focus:border-amber-500 focus:outline-none disabled:opacity-50"
          >
            {DEFAULT_STYLES.map((s) => (
              <option key={s.code} value={s.code}>
                {s.code}: {s.name}
              </option>
            ))}
          </select>
          <div className="p-3 rounded-lg bg-canvas/60 border border-border/80 text-xs text-obsidian-secondary font-mono">
            Directives: {DEFAULT_STYLES.find((s) => s.code === styleCode)?.desc || "Cinematic Hollywood aesthetic"}
          </div>
        </div>

        {/* Aspect Ratio & Render Pipeline */}
        <div className="p-4 rounded-xl bg-panel border border-border space-y-3">
          <label className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary flex items-center gap-1.5">
            <Camera className="w-4 h-4 text-amber-500" />
            <span>Aspect Ratio &amp; Render Pipeline</span>
          </label>
          <div className="grid grid-cols-3 gap-2">
            {["2.39:1", "16:9", "9:16"].map((ratio) => (
              <button
                key={ratio}
                type="button"
                disabled={isLocked}
                onClick={() => setAspectRatio(ratio)}
                className={cn(
                  "py-2 px-3 rounded-lg text-xs font-mono font-bold transition-all border",
                  aspectRatio === ratio
                    ? "bg-amber-500/20 text-amber-400 border-amber-500/50 shadow-sm"
                    : "bg-canvas text-obsidian-muted hover:text-obsidian-secondary border-border"
                )}
              >
                {ratio}
              </button>
            ))}
          </div>
          <div className="pt-1">
            <input
              type="text"
              value={renderPipeline}
              disabled={isLocked}
              onChange={(e) => setRenderPipeline(e.target.value)}
              placeholder="Render Pipeline description..."
              className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-xs text-obsidian-primary font-mono focus:border-amber-500 focus:outline-none disabled:opacity-50"
            />
          </div>
        </div>
      </div>

      {/* Camera Baseline & Optical Emulation */}
      <div className="p-4 rounded-xl bg-panel border border-border space-y-4">
        <h4 className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary flex items-center gap-2">
          <Sliders className="w-4 h-4 text-amber-500" />
          <span>Camera Baseline &amp; Emulation Physics</span>
        </h4>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs font-mono">
          <div className="space-y-1.5">
            <label className="text-obsidian-muted text-[11px]">Film Stock Emulation</label>
            <input
              type="text"
              value={filmStock}
              disabled={isLocked}
              onChange={(e) => setFilmStock(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none disabled:opacity-50"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-obsidian-muted text-[11px]">Anamorphic Squeeze Factor</label>
            <input
              type="text"
              value={anamorphicSqueeze}
              disabled={isLocked}
              onChange={(e) => setAnamorphicSqueeze(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none disabled:opacity-50"
            />
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-[11px]">
              <label className="text-obsidian-muted">Halation &amp; Grain Level</label>
              <span className="text-amber-400 font-bold">{halationLevel}</span>
            </div>
            <input
              type="range"
              min="0.0"
              max="1.0"
              step="0.05"
              value={halationLevel}
              disabled={isLocked}
              onChange={(e) => setHalationLevel(parseFloat(e.target.value))}
              className="w-full accent-amber-500 mt-2"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
