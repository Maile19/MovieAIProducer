"use client";

import React, { useState } from "react";
import { ShieldCheck, Plus, Trash2, Save, Sparkles, Flame } from "lucide-react";

interface RulesInvariantsTabProps {
  worldRules: Record<string, any>;
  isLocked: boolean;
  onSave: (rules: Record<string, any>) => void;
}

export default function RulesInvariantsTab({
  worldRules,
  isLocked,
  onSave,
}: RulesInvariantsTabProps) {
  const [continuityLaws, setContinuityLaws] = useState<string[]>(
    worldRules?.continuity_laws || [
      "Protagonist Cipher Vance cybernetic optic lens is ALWAYS in the right eye socket (never inverted or flipped).",
      "Night exterior scenes must strictly maintain wet asphalt reflections and anamorphic horizontal lens flare streaks.",
      "High-Frequency Monoblade plasma hue is fixed at 450nm violet; never yellow, red, or green.",
      "No direct natural sunlight in lower-level scenes; illumination is motivated exclusively by neon, sodium vapor, or volumetric spotlights.",
      "The antique brass pocket watch time is perpetually frozen at 03:42 AM.",
      "Costume degradation must strictly advance sequentially from #State 01 to #State 05 across the 4 acts.",
    ]
  );

  const [promptNegatives, setPromptNegatives] = useState<string[]>(
    worldRules?.prompt_negatives || [
      "lowres, blurry, bad anatomy, bad hands, missing fingers, extra digits",
      "oversaturated CGI gloss, plastic skin textures, uncanny valley",
      "cartoonish 3D render, anime cel shading, watercolor artifacts",
      "unnatural physics, morphing limbs, flickering geometry, frame stutter",
      "watermarks, stock photo signatures, text overlays, copyright markings",
    ]
  );

  const [newLaw, setNewLaw] = useState("");
  const [newNegative, setNewNegative] = useState("");

  const handleAddLaw = () => {
    if (!newLaw.trim()) return;
    setContinuityLaws((prev) => [...prev, newLaw.trim()]);
    setNewLaw("");
  };

  const handleRemoveLaw = (index: number) => {
    if (isLocked) return;
    setContinuityLaws((prev) => prev.filter((_, i) => i !== index));
  };

  const handleAddNegative = () => {
    if (!newNegative.trim()) return;
    setPromptNegatives((prev) => [...prev, newNegative.trim()]);
    setNewNegative("");
  };

  const handleRemoveNegative = (index: number) => {
    if (isLocked) return;
    setPromptNegatives((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSaveAll = () => {
    onSave({
      ...worldRules,
      continuity_laws: continuityLaws,
      prompt_negatives: promptNegatives,
    });
  };

  return (
    <div className="space-y-6 font-sans">
      {/* Header Bar */}
      <div className="flex items-center justify-between p-4 rounded-xl bg-panel border border-border">
        <div>
          <h3 className="font-cinzel text-sm font-bold uppercase tracking-wider text-obsidian-primary flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-amber-500" />
            <span>Visual Continuity Laws &amp; Global Prompt Negatives</span>
          </h3>
          <p className="text-xs font-mono text-obsidian-muted mt-0.5">
            Hard invariants and algorithmic exclusions enforced across all 50 scenes and generative engines.
          </p>
        </div>

        {!isLocked && (
          <button
            type="button"
            onClick={handleSaveAll}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-xs transition-all shadow-glow"
          >
            <Save className="w-3.5 h-3.5" />
            <span>Save Rules</span>
          </button>
        )}
      </div>

      {/* Continuity Laws Section */}
      <div className="p-4 rounded-xl bg-panel border border-border space-y-4">
        <div className="flex items-center justify-between">
          <label className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary flex items-center gap-1.5">
            <Sparkles className="w-4 h-4 text-emerald-400" />
            <span>Immutable Visual Continuity Laws</span>
          </label>
          <span className="text-[10px] font-mono text-obsidian-muted">
            {continuityLaws.length} Enforced Laws
          </span>
        </div>

        <div className="space-y-2">
          {continuityLaws.map((law, idx) => (
            <div
              key={idx}
              className="p-3 rounded-lg bg-canvas border border-border/80 flex items-start justify-between gap-3 text-xs font-mono group"
            >
              <div className="flex items-start gap-2.5 min-w-0">
                <span className="w-5 h-5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center justify-center font-bold text-[10px] shrink-0 mt-0.5">
                  {idx + 1}
                </span>
                <span className="text-obsidian-primary leading-relaxed font-sans">{law}</span>
              </div>

              {!isLocked && (
                <button
                  type="button"
                  onClick={() => handleRemoveLaw(idx)}
                  className="text-obsidian-muted hover:text-rose-400 opacity-0 group-hover:opacity-100 transition-all p-1"
                  title="Remove Law"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          ))}
        </div>

        {!isLocked && (
          <div className="flex items-center gap-2 pt-2">
            <input
              type="text"
              value={newLaw}
              onChange={(e) => setNewLaw(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAddLaw()}
              placeholder="Add new visual continuity invariant law..."
              className="flex-1 px-3 py-2 rounded-lg bg-canvas border border-border text-xs text-obsidian-primary font-mono placeholder:text-obsidian-muted focus:border-amber-500 focus:outline-none"
            />
            <button
              type="button"
              onClick={handleAddLaw}
              disabled={!newLaw.trim()}
              className="px-3.5 py-2 rounded-lg bg-canvas hover:bg-elevated border border-border text-amber-400 text-xs font-bold flex items-center gap-1 disabled:opacity-50"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add Law</span>
            </button>
          </div>
        )}
      </div>

      {/* Global Prompt Negatives Section */}
      <div className="p-4 rounded-xl bg-panel border border-border space-y-4">
        <div className="flex items-center justify-between">
          <label className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary flex items-center gap-1.5">
            <Flame className="w-4 h-4 text-rose-400" />
            <span>Global Negative Prompts &amp; Universal Exclusions</span>
          </label>
          <span className="text-[10px] font-mono text-obsidian-muted">
            Engine Exclusions
          </span>
        </div>

        <div className="space-y-2">
          {promptNegatives.map((neg, idx) => (
            <div
              key={idx}
              className="p-3 rounded-lg bg-canvas border border-border/80 flex items-start justify-between gap-3 text-xs font-mono group"
            >
              <div className="flex items-start gap-2.5 min-w-0">
                <span className="w-5 h-5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/30 flex items-center justify-center font-bold text-[10px] shrink-0 mt-0.5">
                  &times;
                </span>
                <span className="text-obsidian-secondary leading-relaxed font-mono text-[11px]">
                  {neg}
                </span>
              </div>

              {!isLocked && (
                <button
                  type="button"
                  onClick={() => handleRemoveNegative(idx)}
                  className="text-obsidian-muted hover:text-rose-400 opacity-0 group-hover:opacity-100 transition-all p-1"
                  title="Remove Exclusion"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          ))}
        </div>

        {!isLocked && (
          <div className="flex items-center gap-2 pt-2">
            <input
              type="text"
              value={newNegative}
              onChange={(e) => setNewNegative(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAddNegative()}
              placeholder="Add comma-separated negative tokens to universally exclude..."
              className="flex-1 px-3 py-2 rounded-lg bg-canvas border border-border text-xs text-obsidian-primary font-mono placeholder:text-obsidian-muted focus:border-rose-500 focus:outline-none"
            />
            <button
              type="button"
              onClick={handleAddNegative}
              disabled={!newNegative.trim()}
              className="px-3.5 py-2 rounded-lg bg-canvas hover:bg-elevated border border-border text-rose-400 text-xs font-bold flex items-center gap-1 disabled:opacity-50"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add Exclusion</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
