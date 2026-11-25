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
  projectId?: string;
  sceneId?: string;
  shotId?: string;
  characterId?: string;
  characterDna?: string;
  actionDescription?: string;
  slugline?: string;
  dialogue?: string | null;
  transitionType?: string;
  audioLeadSeconds?: number | null;
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
  projectId,
  sceneId,
  shotId,
  characterId,
  characterDna = "",
  actionDescription = "",
  slugline = "",
  dialogue,
  transitionType = "NONE",
  audioLeadSeconds,
  presetRules,
  isNonVerbal = false,
}: PromptTranspilerProps) {
  const [selectedEngine, setSelectedEngine] = useState<
    "veo" | "kling" | "seedance" | "runway" | "sora" | "comfyui" | "9router"
  >("9router");
  const [selected9RouterModel, setSelected9RouterModel] = useState<string>("ag/gemini-3.8-flash");
  const [transpileResult, setTranspileResult] = useState<TranspileResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const engines = [
    { id: "9router", label: "9Router AI", badge: "Multi-Combo" },
    { id: "veo", label: "Google Veo / Flow", badge: "Veo 2.0" },
    { id: "kling", label: "Kling 1.5", badge: "Pro" },
    { id: "seedance", label: "Seedance 1.0", badge: "Motion" },
    { id: "runway", label: "Runway Gen-3", badge: "Alpha" },
    { id: "sora", label: "OpenAI Sora", badge: "v1.0" },
    { id: "comfyui", label: "ComfyUI", badge: "Wan 2.1" },
  ] as const;

  const NINEROUTER_MODELS = [
    {
      value: "ag/gemini-3.8-flash",
      title: "AG/Gemini 3.8-Flash",
      badge: "Recommended",
      description: "Ultra-fast multimodal prompt synthesis & visual keyframe compiler",
    },
    {
      value: "geminis",
      title: "Multi-Combo Pool",
      badge: "Auto-Failover",
      description: "Dynamic multi-account failover pool across Gemini cluster",
    },
    {
      value: "ag/gemini-4-argon",
      title: "AG/Gemini 4-Argon",
      badge: "Ultra-Res",
      description: "Extreme parameter fidelity for IMAX-grade visual concepts",
    },
    {
      value: "ag/gemini-3.1-pro-high",
      title: "AG/Gemini 3.1-Pro",
      badge: "Deep-Reasoning",
      description: "Advanced cinematic storytelling and subtext calibration",
    },
    {
      value: "gemini/gemini-3.8-flash",
      title: "Gemini 3.8-Flash Direct",
      badge: "Direct",
      description: "Standard direct endpoint routing for Gemini 3.8 Flash",
    },
  ];

  // Trigger live Dual-RAG transpile whenever parameters or active scene/character change
  useEffect(() => {
    let isCancelled = false;

    const runTranspile = async () => {
      try {
        setIsLoading(true);
        const payload: TranspileInput = {
          provider_target: selectedEngine,
          model: selectedEngine === "9router" ? selected9RouterModel : undefined,
          project_id: projectId || undefined,
          scene_id: sceneId || undefined,
          shot_id: shotId || undefined,
          character_id: characterId || undefined,
          style_code: styleCode,
          camera_code: camCode,
          lens_code: lensCode,
          comp_code: compCode,
          light_code: lightCode,
          act_code: actCode,
          speed_code: speedCode,
          character_dna: characterDna || undefined,
          action_description: actionDescription || undefined,
          slugline: slugline || undefined,
          dialogue: dialogue ?? undefined,
          transition_type: transitionType,
          audio_lead_seconds: audioLeadSeconds ?? undefined,
          aspect_ratio: aspectRatio === "2.39:1" ? "16:9" : aspectRatio,
          preset_rules: presetRules,
          is_non_verbal: isNonVerbal,
        };

        const res = await api.transpile.transpilePrompt(payload);
        if (!isCancelled && res?.data) {
          const raw = res.data as any;
          setTranspileResult({
            positive: raw.positive || raw.positive_prompt || "",
            negative: raw.negative || raw.negative_prompt || "",
            engine:
              raw.engine ||
              (selectedEngine === "9router"
                ? `9Router • ${selected9RouterModel}`
                : raw.metadata?.target_engine || selectedEngine),
            compiled_engines: raw.compiled_engines,
            metadata: raw.metadata,
          });
        }
      } catch {
        if (!isCancelled) {
          const subjectFallback = characterDna.trim() || "No character DNA selected yet";
          const actionFallback = actionDescription.trim() || slugline.trim() || "Awaiting scene beat";
          setTranspileResult({
            positive: `[${selectedEngine.toUpperCase()}]: ${styleCode}, ${camCode}, ${lensCode}, ${compCode}, ${lightCode}, ${speedCode}. Subject: ${subjectFallback}. Beat: ${actionFallback}.`,
            negative: "lowres, bad anatomy, bad hands, text, blurry, watermark",
            engine: selectedEngine === "9router" ? `9Router • ${selected9RouterModel}` : selectedEngine,
            metadata: {
              aspect_ratio: aspectRatio,
              engine_params: { aspect_ratio: aspectRatio },
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
    selected9RouterModel,
    projectId,
    sceneId,
    shotId,
    characterId,
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
    slugline,
    dialogue,
    transitionType,
    audioLeadSeconds,
    presetRules,
    isNonVerbal,
  ]);

  const handleCopy = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const engineParams = (transpileResult?.metadata?.engine_params || {}) as Record<string, unknown>;
  const continuitySources = transpileResult?.metadata?.continuity_sources;
  const paramSummaryParts: string[] = [`Aspect: ${aspectRatio}`];
  if (typeof engineParams.cfg_scale === "number") paramSummaryParts.push(`CFG: ${engineParams.cfg_scale}`);
  if (typeof engineParams.guidance_scale === "number") paramSummaryParts.push(`Guidance: ${engineParams.guidance_scale}`);
  if (typeof engineParams.steps === "number") paramSummaryParts.push(`Steps: ${engineParams.steps}`);
  if (typeof engineParams.fps === "number") paramSummaryParts.push(`${engineParams.fps}fps`);
  if (typeof engineParams.duration_seconds === "number") paramSummaryParts.push(`${engineParams.duration_seconds}s`);

  return (
    <div className="bg-panel border border-border rounded-xl p-3.5 shadow-studio space-y-3 font-sans">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border pb-2.5">
        <div className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-amber-500" />
          <h3 className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary">
            Live Dual-RAG Prompt Transpiler
          </h3>
        </div>
        {isLoading ? (
          <div className="flex items-center gap-1.5 text-[10px] font-mono text-amber-400">
            <RefreshCw className="w-3 h-3 animate-spin" />
            <span>Compiling...</span>
          </div>
        ) : (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-canvas border border-border text-emerald-400 font-semibold">
            {transpileResult?.metadata?.prompt_tokens_est || 0} TOKENS
          </span>
        )}
      </div>

      {/* Continuity DNA & Dual-RAG Telemetry */}
      {continuitySources && (
        <div className="flex flex-wrap items-center gap-1.5 text-[9px] font-mono">
          <span className="px-1.5 py-0.5 rounded bg-canvas border border-border text-amber-300">
            {continuitySources.style_code || styleCode}
          </span>
          {continuitySources.character_name && (
            <span className="px-1.5 py-0.5 rounded bg-blue-500/10 border border-blue-500/30 text-blue-300">
              DNA: {continuitySources.character_name} ({continuitySources.state_code || "#State 01"})
            </span>
          )}
          <span className="px-1.5 py-0.5 rounded bg-canvas border border-border text-obsidian-muted">
            RAG 8765:{continuitySources.director_rag_hits ?? 0} &bull; 8766:{continuitySources.screenwriter_rag_hits ?? 0}
          </span>
        </div>
      )}

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

      {/* 9Router Model Selection Dropdown */}
      {selectedEngine === "9router" && (
        <div className="animate-in fade-in duration-150">
          <ObsidianDropdown
            size="sm"
            label="9Router AI Model Selection"
            icon={<Sparkles className="w-4 h-4 text-amber-400" />}
            options={NINEROUTER_MODELS}
            value={selected9RouterModel}
            onChange={(val) => setSelected9RouterModel(val)}
          />
        </div>
      )}

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
        <div className="p-3 rounded-lg bg-canvas border border-border text-xs font-mono text-obsidian-primary leading-relaxed max-h-36 overflow-y-auto selection:bg-amber-500/30">
          {transpileResult?.positive || "Select a scene or configure matrix codes to compile prompt..."}
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
          Engine:{" "}
          <strong className="text-obsidian-secondary">
            {selectedEngine === "9router"
              ? `9Router • ${selected9RouterModel}`
              : transpileResult?.engine || selectedEngine}
          </strong>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {paramSummaryParts.map((part, i) => (
            <React.Fragment key={part}>
              {i > 0 && <span>&bull;</span>}
              <span>{part}</span>
            </React.Fragment>
          ))}
        </div>
      </div>
    </div>
  );
}
