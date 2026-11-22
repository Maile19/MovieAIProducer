"use client";

import React, { useState, useEffect } from "react";
import {
  Sparkles,
  Copy,
  Check,
  RefreshCw,
  Cpu,
  Flame,
} from "lucide-react";
import { api, TranspileInput, TranspileResult } from "@/lib/api";
import ObsidianDropdown from "@/components/ui/ObsidianDropdown";

interface PromptTranspilerProps {
  styleCode: string;
  lightCode: string;
  actCode: string;
  camCode: string;
  lensCode: string;
  compCode: string;
  speedCode: string;
  aspectRatio?: string;
  characterDna?: string;
  actionDescription?: string;
  presetRules?: Record<string, any>;
  isNonVerbal?: boolean;
}

export default function PromptTranspiler({
  styleCode,
  lightCode,
  actCode,
  camCode,
  lensCode,
  compCode,
  speedCode,
  aspectRatio = "16:9",
  characterDna = "Protagonist, 35mm cybernetic operative, neon reflections",
  actionDescription = "Slowly turns towards the camera, drawing high-frequency energy blade",
  presetRules,
  isNonVerbal = false,
}: PromptTranspilerProps) {
  const [selectedEngine, setSelectedEngine] = useState<
    "veo" | "kling" | "runway" | "sora" | "comfyui" | "9router" | "sd35"
  >("9router");
  const [transpileResult, setTranspileResult] = useState<TranspileResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const engines = [
    { id: "9router", label: "9Router AI", badge: "Multi-Combo" },
    { id: "sd35", label: "SD 3.5 Large", badge: "HuggingFace" },
    { id: "veo", label: "Google Veo / Flow", badge: "Veo 2.0" },
    { id: "kling", label: "Kling 1.5", badge: "Pro" },
    { id: "runway", label: "Runway Gen-3", badge: "Alpha" },
    { id: "sora", label: "OpenAI Sora", badge: "v1.0" },
    { id: "comfyui", label: "ComfyUI", badge: "Wan 2.1" },
  ] as const;

  // Trigger live transpile whenever parameters change
  useEffect(() => {
    let isCancelled = false;

    const runTranspile = async () => {
      try {
        setIsLoading(true);
        const payload: TranspileInput = {
          provider_target: selectedEngine,
          style_code: styleCode,
          camera_code: camCode,
          lens_code: lensCode,
          comp_code: compCode,
          light_code: lightCode,
          act_code: actCode,
          speed_code: speedCode,
          character_dna: characterDna,
          action_description: actionDescription,
          aspect_ratio: aspectRatio === "2.39:1" ? "16:9" : aspectRatio,
          preset_rules: presetRules,
          is_non_verbal: isNonVerbal,
        };

        const res = await api.transpile.transpilePrompt(payload);
        if (!isCancelled && res?.data) {
          setTranspileResult(res.data);
        }
      } catch {
        // Fallback local compilation if network glitch occurs
        if (!isCancelled) {
          setTranspileResult({
            positive: `[${selectedEngine.toUpperCase()}]: Cinematic film in ${aspectRatio}. ${styleCode}, shot on ${lensCode} with ${camCode}, ${compCode}. ${characterDna}, ${actionDescription}. Lighting: ${lightCode}. Motion: ${speedCode}. Award-winning cinematography, photorealistic 35mm film grain.`,
            negative: "lowres, bad anatomy, bad hands, text, error, blurry, deformed limbs, watermark",
            engine: `${selectedEngine}_cinematic_v2`,
            metadata: {
              prompt_tokens_est: 84,
              aspect_ratio: aspectRatio,
            },
          });
        }
      } finally {
        if (!isCancelled) setIsLoading(false);
      }
    };

    runTranspile();
    return () => {
      isCancelled = true;
    };
  }, [
    selectedEngine,
    styleCode,
    lightCode,
    actCode,
    camCode,
    lensCode,
    compCode,
    speedCode,
    aspectRatio,
    characterDna,
    actionDescription,
    presetRules,
    isNonVerbal,
  ]);

  const handleCopy = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  return (
    <div className="bg-panel border border-border rounded-xl p-3.5 shadow-studio space-y-3 font-sans">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border pb-2.5">
        <div className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-amber-500" />
          <h3 className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary">
            Live Prompt Transpiler
          </h3>
        </div>
        {isLoading ? (
          <div className="flex items-center gap-1.5 text-[10px] font-mono text-amber-400">
            <RefreshCw className="w-3 h-3 animate-spin" />
            <span>Compiling...</span>
          </div>
        ) : (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-canvas border border-border text-emerald-400 font-semibold">
            {transpileResult?.metadata?.prompt_tokens_est || 78} TOKENS
          </span>
        )}
      </div>

      {/* Engine / Provider Selector Dropdown */}
      <ObsidianDropdown
        size="sm"
        label="Generative AI Engine / Provider Target"
        icon={<Cpu className="w-4 h-4 text-amber-500" />}
        options={engines.map((eng) => ({
          value: eng.id,
          title: eng.label,
          description: `Generates cinematic prompt syntax tailored for ${eng.label}`,
          badge: eng.badge,
        }))}
        value={selectedEngine}
        onChange={(val) => setSelectedEngine(val as any)}
      />

      {/* Compiled Positive Prompt Box */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-xs">
          <label className="text-[11px] font-mono font-semibold text-amber-400 flex items-center gap-1.5">
            <Sparkles className="w-3 h-3" />
            <span>Compiled Positive Prompt</span>
          </label>
          <button
            type="button"
            onClick={() => handleCopy(transpileResult?.positive || "", "positive")}
            className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-canvas hover:bg-elevated text-obsidian-secondary hover:text-amber-400 border border-border transition-colors"
          >
            {copiedKey === "positive" ? (
              <>
                <Check className="w-3 h-3 text-emerald-400" />
                <span className="text-emerald-400 font-bold">Copied!</span>
              </>
            ) : (
              <>
                <Copy className="w-3 h-3" />
                <span>1-Click Copy</span>
              </>
            )}
          </button>
        </div>
        <div className="p-3 rounded-lg bg-canvas border border-border text-xs font-mono text-obsidian-primary leading-relaxed max-h-32 overflow-y-auto selection:bg-amber-500/30">
          {transpileResult?.positive || "Compiling prompt across Hollywood matrices..."}
        </div>
      </div>

      {/* Compiled Negative Prompt Box */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-xs">
          <label className="text-[11px] font-mono font-semibold text-rose-400 flex items-center gap-1.5">
            <Flame className="w-3 h-3" />
            <span>Negative Prompt / Exclusions</span>
          </label>
          <button
            type="button"
            onClick={() => handleCopy(transpileResult?.negative || "", "negative")}
            className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-canvas hover:bg-elevated text-obsidian-secondary hover:text-rose-400 border border-border transition-colors"
          >
            {copiedKey === "negative" ? (
              <>
                <Check className="w-3 h-3 text-emerald-400" />
                <span className="text-emerald-400 font-bold">Copied!</span>
              </>
            ) : (
              <>
                <Copy className="w-3 h-3" />
                <span>Copy Negative</span>
              </>
            )}
          </button>
        </div>
        <div className="p-2.5 rounded-lg bg-canvas border border-border/80 text-[11px] font-mono text-obsidian-muted leading-relaxed max-h-20 overflow-y-auto">
          {transpileResult?.negative || "lowres, bad anatomy, blurry, artifacts"}
        </div>
      </div>

      {/* Engine Target Parameters Footer */}
      <div className="pt-2 border-t border-border flex flex-wrap items-center justify-between gap-2 text-[10px] font-mono text-obsidian-muted">
        <div>
          Engine: <strong className="text-obsidian-secondary">{transpileResult?.engine || selectedEngine}</strong>
        </div>
        <div className="flex items-center gap-2">
          <span>Aspect: {aspectRatio}</span>
          <span>&bull;</span>
          <span>CFG: 7.0</span>
          <span>&bull;</span>
          <span>Steps: 30</span>
        </div>
      </div>
    </div>
  );
}
