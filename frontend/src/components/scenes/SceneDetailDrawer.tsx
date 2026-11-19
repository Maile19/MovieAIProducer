"use client";

import React, { useState, useEffect } from "react";
import {
  X,
  Save,
  Check,
  Cpu,
  ChevronDown,
  ChevronRight,
  Copy,
} from "lucide-react";
import { Scene, api } from "@/lib/api";
import DialogueCalibrator from "./DialogueCalibrator";
import ShotListManager from "./ShotListManager";
import QcScorecard from "./QcScorecard";
import { cn } from "@/lib/utils";

interface SceneDetailDrawerProps {
  scene: Scene | null;
  onClose: () => void;
  onSceneUpdated: () => void;
  styleCode?: string;
}

export default function SceneDetailDrawer({
  scene,
  onClose,
  onSceneUpdated,
  styleCode = "#Style 01",
}: SceneDetailDrawerProps) {
  const [slugline, setSlugline] = useState(scene?.slugline || "");
  const [narrativeGoal, setNarrativeGoal] = useState(scene?.narrative_goal || "");
  const [durationTarget, setDurationTarget] = useState(scene?.duration_target || 5.0);
  const [sceneStatus, setSceneStatus] = useState(scene?.status || "PLANNED");
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Multi-engine live prompt compiler inside drawer
  const [compilerEngine, setCompilerEngine] = useState<
    "veo" | "kling" | "runway" | "sora" | "comfyui"
  >("veo");
  const [compilerAccordionOpen, setCompilerAccordionOpen] = useState(true);
  const [copiedPrompt, setCopiedPrompt] = useState(false);

  useEffect(() => {
    if (scene) {
      setSlugline(scene.slugline || "");
      setNarrativeGoal(scene.narrative_goal || "");
      setDurationTarget(scene.duration_target || 5.0);
      setSceneStatus(scene.status || "PLANNED");
    }
  }, [scene]);

  if (!scene) return null;

  const handleSaveScene = async () => {
    try {
      setIsSaving(true);
      await api.scenes.update(scene.id, {
        slugline,
        narrative_goal: narrativeGoal,
        duration_target: durationTarget,
        status: sceneStatus,
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2000);
      onSceneUpdated();
    } catch (err) {
      console.error(err);
    } finally {
      setIsSaving(false);
    }
  };

  const getEngineCompiledPrompt = () => {
    switch (compilerEngine) {
      case "veo":
        return `[Google Veo Flow]: Cinematic 4K video, 2.39:1 anamorphic. Scene ${scene.scene_number}: ${slugline}. Beat: ${narrativeGoal}. ${styleCode}. Dynamic 5-second camera motion, photorealistic film grain, 24fps motion coherence.`;
      case "kling":
        return `[Kling 1.5 Pro]: High-fidelity cinematic master shot in ${slugline}. ${narrativeGoal}. Stylized on ${styleCode}. Precise physical interaction, seamless 5-second cadence.`;
      case "runway":
        return `[Runway Gen-3 Alpha]: Seamless continuous cinematic motion, ${slugline}. Dramatic lighting, ${narrativeGoal}. Award-winning cinematography, ${styleCode}.`;
      case "sora":
        return `[OpenAI Sora v1]: Hollywood widescreen film scene. ${slugline}. Character narrative objective: ${narrativeGoal}. Art direction strictly adhering to ${styleCode}.`;
      case "comfyui":
      default:
        return `cinematic film shot, ${slugline}, ${narrativeGoal}, ${styleCode}, photorealistic 35mm grain, 8k uhd, masterpiece.`;
    }
  };

  const handleCopyPrompt = () => {
    navigator.clipboard.writeText(getEngineCompiledPrompt());
    setCopiedPrompt(true);
    setTimeout(() => setCopiedPrompt(false), 2000);
  };

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-2xl bg-panel border-l border-border shadow-2xl flex flex-col font-sans animate-in slide-in-from-right duration-300">
      {/* Drawer Header */}
      <div className="p-4 border-b border-border bg-elevated/40 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center font-mono font-bold text-amber-400 text-xs shrink-0">
            #{scene.scene_number.toString().padStart(2, "0")}
          </div>
          <div className="min-w-0">
            <h3 className="font-cinzel text-sm font-bold text-obsidian-primary truncate uppercase tracking-wider">
              {slugline || `Scene ${scene.scene_number}`}
            </h3>
            <p className="text-[10px] font-mono text-obsidian-muted">
              Act {scene.act_number || 1} &bull; Scene Detail Sheet
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleSaveScene}
            disabled={isSaving}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-xs shadow-glow transition-all disabled:opacity-50"
          >
            {saveSuccess ? (
              <>
                <Check className="w-3.5 h-3.5" />
                <span>Saved</span>
              </>
            ) : (
              <>
                <Save className="w-3.5 h-3.5" />
                <span>{isSaving ? "Saving..." : "Save Scene"}</span>
              </>
            )}
          </button>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-obsidian-muted hover:text-obsidian-primary hover:bg-canvas transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Drawer Body Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        {/* Scene Metadata & Beat Goal Editor */}
        <div className="p-4 rounded-xl bg-canvas border border-border space-y-3 font-mono text-xs">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-[10px] text-obsidian-muted uppercase">Slugline / Header</label>
              <input
                type="text"
                value={slugline}
                onChange={(e) => setSlugline(e.target.value)}
                className="w-full px-3 py-1.5 rounded-lg bg-panel border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none text-xs"
              />
            </div>

            <div className="space-y-1">
              <label className="text-[10px] text-obsidian-muted uppercase">Scene Status</label>
              <select
                value={sceneStatus}
                onChange={(e) => setSceneStatus(e.target.value)}
                className="w-full px-3 py-1.5 rounded-lg bg-panel border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none text-xs"
              >
                <option value="PLANNED">Planned</option>
                <option value="GENERATING">Generating</option>
                <option value="QC_PASSED">QC Passed</option>
                <option value="COMPLETED">Completed</option>
              </select>
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-[10px] text-obsidian-muted uppercase">Narrative Goal &amp; Dramatic Beat</label>
            <textarea
              value={narrativeGoal}
              onChange={(e) => setNarrativeGoal(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 rounded-lg bg-panel border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none text-xs resize-none"
            />
          </div>
        </div>

        {/* 5-Second Dialogue Limiter & J/L-Cut Calibration Waveform */}
        <DialogueCalibrator sceneId={scene.id} />

        {/* Shot List Manager */}
        <ShotListManager sceneId={scene.id} onShotsUpdated={onSceneUpdated} />

        {/* Live Multi-Platform Prompt Compiler Drawer */}
        <div className="rounded-xl bg-panel border border-border overflow-hidden">
          <button
            type="button"
            onClick={() => setCompilerAccordionOpen(!compilerAccordionOpen)}
            className="w-full p-3.5 flex items-center justify-between text-left hover:bg-elevated/40 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-amber-500" />
              <h4 className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary">
                Live Multi-Platform Prompt Compiler
              </h4>
            </div>
            {compilerAccordionOpen ? (
              <ChevronDown className="w-4 h-4 text-obsidian-muted" />
            ) : (
              <ChevronRight className="w-4 h-4 text-obsidian-muted" />
            )}
          </button>

          {compilerAccordionOpen && (
            <div className="p-4 border-t border-border space-y-3 font-mono text-xs animate-in fade-in duration-150">
              {/* Engine Switcher */}
              <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
                {[
                  { id: "veo", label: "Google Veo" },
                  { id: "kling", label: "Kling 1.5" },
                  { id: "runway", label: "Runway Gen-3" },
                  { id: "sora", label: "OpenAI Sora" },
                  { id: "comfyui", label: "ComfyUI Wan 2.1" },
                ].map((eng) => (
                  <button
                    key={eng.id}
                    type="button"
                    onClick={() => setCompilerEngine(eng.id as any)}
                    className={cn(
                      "px-2.5 py-1 rounded-md text-[11px] font-semibold transition-all border shrink-0",
                      compilerEngine === eng.id
                        ? "bg-amber-500/20 text-amber-400 border-amber-500/40 shadow-sm"
                        : "bg-canvas text-obsidian-muted hover:text-obsidian-secondary border-border"
                    )}
                  >
                    {eng.label}
                  </button>
                ))}
              </div>

              {/* Compiled Prompt Area */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-obsidian-muted uppercase">Compiled Engine Prompt:</span>
                  <button
                    type="button"
                    onClick={handleCopyPrompt}
                    className="flex items-center gap-1 text-amber-400 hover:text-amber-300"
                  >
                    {copiedPrompt ? (
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
                <div className="p-3 rounded-lg bg-canvas border border-border text-[11px] text-obsidian-primary leading-relaxed selection:bg-amber-500/30">
                  {getEngineCompiledPrompt()}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Automated QC Scorecard */}
        <QcScorecard sceneId={scene.id} />
      </div>
    </div>
  );
}
