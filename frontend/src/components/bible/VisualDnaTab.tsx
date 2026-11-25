"use client";

import React, { useEffect, useMemo, useState } from "react";
import { Palette, Camera, Sliders, Check, Copy, Sparkles, Save, Loader2 } from "lucide-react";
import { DEFAULT_STYLES } from "@/lib/studio-constants";
import { api, LookDevPreset } from "@/lib/api";
import { cn } from "@/lib/utils";
import ObsidianDropdown from "@/components/ui/ObsidianDropdown";

interface VisualDnaTabProps {
  projectId: string;
  styleParameters: Record<string, any>;
  isLocked: boolean;
  onSave: (params: Record<string, any>) => void;
}

export default function VisualDnaTab({
  projectId,
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
  const [filmStock, setFilmStock] = useState(styleParameters?.film_stock || "");
  const [anamorphicSqueeze, setAnamorphicSqueeze] = useState(
    styleParameters?.anamorphic_squeeze || "2.0x Horizontal"
  );
  const [halationLevel, setHalationLevel] = useState(styleParameters?.halation_level || 0.35);

  const [presets, setPresets] = useState<LookDevPreset[]>([]);
  const [isLoadingPresets, setIsLoadingPresets] = useState(false);
  const [presetsError, setPresetsError] = useState<string | null>(null);
  const [selectedPresetId, setSelectedPresetId] = useState<string | null>(
    styleParameters?.look_dev_preset_id || null
  );
  const [ragCues, setRagCues] = useState<string>("");

  const [copiedHex, setCopiedHex] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoadingPresets(true);
    setPresetsError(null);
    api.bible
      .lookDevPresets(projectId, { style_code: styleCode })
      .then((res) => {
        if (cancelled) return;
        setPresets(res.data || []);
        setRagCues(res.director_rag_cues || "");
        const savedId = styleParameters?.look_dev_preset_id;
        const match = (res.data || []).find((p) => p.preset_id === savedId);
        if (match) {
          setSelectedPresetId(match.preset_id);
        } else if (!styleParameters?.film_stock && (res.data || []).length > 0) {
          setSelectedPresetId(res.data[0].preset_id);
          setFilmStock(res.data[0].film_stock_or_medium);
        }
      })
      .catch((err: any) => {
        if (cancelled) return;
        setPresets([]);
        setPresetsError(err?.message || "Unable to load Look-Dev presets");
      })
      .finally(() => {
        if (!cancelled) setIsLoadingPresets(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, styleCode]);

  const activePreset = useMemo(
    () => presets.find((p) => p.preset_id === selectedPresetId) || presets[0] || null,
    [presets, selectedPresetId]
  );

  const paletteTokens = useMemo(() => {
    if (activePreset?.palette_tokens?.length) return activePreset.palette_tokens;
    if (Array.isArray(styleParameters?.palette_tokens)) return styleParameters.palette_tokens;
    return [];
  }, [activePreset, styleParameters?.palette_tokens]);

  const handleSelectPreset = (preset: LookDevPreset) => {
    setSelectedPresetId(preset.preset_id);
    setFilmStock(preset.film_stock_or_medium);
  };

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
      look_dev_preset_id: activePreset?.preset_id || null,
      palette_tokens: paletteTokens,
      default_lens_code: activePreset?.default_lens_code || null,
      default_light_code: activePreset?.default_light_code || null,
      color_grade_emulation: activePreset?.color_grade_emulation || null,
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

      {/* Look-Dev Preset Selector */}
      <div className="p-4 rounded-xl bg-panel border border-border space-y-3">
        <div className="flex items-center justify-between">
          <label className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary">
            Look-Dev Presets ({styleCode})
          </label>
          {isLoadingPresets ? (
            <span className="text-[10px] font-mono text-obsidian-muted flex items-center gap-1">
              <Loader2 className="w-3 h-3 animate-spin" /> Loading presets
            </span>
          ) : (
            <span className="text-[10px] font-mono text-obsidian-muted">
              {presets.length} curated option{presets.length === 1 ? "" : "s"}
            </span>
          )}
        </div>

        {presetsError && (
          <div className="p-3 rounded-lg bg-canvas border border-border text-xs font-mono text-rose-400">
            {presetsError}
          </div>
        )}

        {!isLoadingPresets && !presetsError && presets.length === 0 && (
          <div className="p-3 rounded-lg bg-canvas border border-border text-xs font-mono text-obsidian-muted">
            No Look-Dev presets available for this style.
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          {presets.map((preset) => {
            const isActive = activePreset?.preset_id === preset.preset_id;
            return (
              <button
                key={preset.preset_id}
                type="button"
                disabled={isLocked}
                onClick={() => handleSelectPreset(preset)}
                className={cn(
                  "text-left p-3 rounded-lg border transition-all space-y-2",
                  isActive
                    ? "bg-amber-500/10 border-amber-500/50 shadow-sm"
                    : "bg-canvas border-border hover:border-amber-500/30",
                  isLocked && "opacity-60 cursor-not-allowed"
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-cinzel text-xs font-bold text-obsidian-primary">
                    {preset.label}
                  </span>
                  {isActive && <Check className="w-3.5 h-3.5 text-amber-400 shrink-0" />}
                </div>
                <div className="flex gap-1">
                  {preset.palette_tokens.map((token) => (
                    <span
                      key={`${preset.preset_id}-${token.role}`}
                      className="h-4 flex-1 rounded-sm border border-white/10"
                      style={{ backgroundColor: token.hex }}
                      title={`${token.role}: ${token.hex}`}
                    />
                  ))}
                </div>
                <p className="text-[10px] font-mono text-obsidian-muted line-clamp-2">
                  {preset.mood_rationale}
                </p>
                <p className="text-[10px] font-mono text-obsidian-secondary line-clamp-1">
                  {preset.film_stock_or_medium}
                </p>
                <div className="flex flex-wrap gap-1 text-[9px] font-mono text-amber-400/80">
                  <span>{preset.default_lens_code}</span>
                  <span>·</span>
                  <span>{preset.default_light_code}</span>
                </div>
              </button>
            );
          })}
        </div>

        {ragCues && (
          <div className="p-2.5 rounded-lg bg-canvas/60 border border-border/80 text-[10px] font-mono text-obsidian-secondary">
            <span className="text-amber-400 font-bold">Director RAG: </span>
            {ragCues}
          </div>
        )}
      </div>

      {/* Color Palette Tokens Section */}
      <div className="p-4 rounded-xl bg-panel border border-border space-y-3">
        <div className="flex items-center justify-between">
          <label className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary">
            Cinematic Palette Tokens
          </label>
          <span className="text-[10px] font-mono text-obsidian-muted">
            Click hex to copy
          </span>
        </div>

        {paletteTokens.length === 0 ? (
          <div className="p-3 rounded-lg bg-canvas border border-border text-xs font-mono text-obsidian-muted">
            Select a Look-Dev preset to load its production palette.
          </div>
        ) : (
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
                <div className="flex items-center justify-between gap-1 text-xs font-mono">
                  <span className="font-bold text-obsidian-primary truncate">{token.role}</span>
                  <span className="text-amber-400 text-[11px] shrink-0">{token.hex}</span>
                </div>
                <p className="text-[10px] text-obsidian-muted mt-1 line-clamp-1">{token.name}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Master Style & Aspect Ratio Selection */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Style Code Selector */}
        <div className="p-4 rounded-xl bg-panel border border-border space-y-3">
          <ObsidianDropdown
            label="Master Style Code (#Style 01-18)"
            icon={<Sparkles className="w-4 h-4 text-amber-500" />}
            options={DEFAULT_STYLES.map((s) => ({
              value: s.code,
              title: `${s.code}: ${s.name}`,
              description: s.desc,
              badge: "Master Style",
            }))}
            value={styleCode}
            disabled={isLocked}
            onChange={(val) => setStyleCode(val)}
          />
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
            <label className="text-obsidian-muted text-[11px]">Film Stock / Medium</label>
            <input
              type="text"
              value={filmStock}
              disabled={isLocked}
              onChange={(e) => setFilmStock(e.target.value)}
              placeholder="Select a Look-Dev preset or type a medium..."
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
