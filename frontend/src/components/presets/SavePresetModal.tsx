"use client";

import React, { useState } from "react";
import {
  BookmarkPlus,
  X,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Layers,
  Palette,
  ShieldCheck,
} from "lucide-react";
import { api, ProductionPreset } from "@/lib/api";
import ObsidianDropdown from "@/components/ui/ObsidianDropdown";

interface SavePresetModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  defaultTitle?: string;
  onSaved?: (preset: ProductionPreset) => void;
}

export default function SavePresetModal({
  isOpen,
  onClose,
  projectId,
  defaultTitle = "Production",
  onSaved,
}: SavePresetModalProps) {
  const [name, setName] = useState(`${defaultTitle} Preset`);
  const [category, setCategory] = useState("general");
  const [description, setDescription] = useState(
    `Production blueprint exported from project ${defaultTitle}. Includes Master Production Bible, visual styles, cinematography optics, and QC thresholds.`
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setErrorMsg("Preset name is required");
      return;
    }

    try {
      setIsSubmitting(true);
      setErrorMsg(null);
      const res = await api.presets.saveFromProject(projectId, {
        name: name.trim(),
        category: category.trim() || "general",
        description: description.trim(),
      });
      if (res?.data) {
        setSuccessMsg(`Preset '${res.data.name}' saved successfully!`);
        onSaved?.(res.data);
        setTimeout(() => {
          setSuccessMsg(null);
          onClose();
        }, 1200);
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to save project as preset");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-panel border border-border rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden font-sans">
        {/* Header */}
        <div className="px-6 py-4 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-500">
              <BookmarkPlus className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-cinzel font-bold text-base text-obsidian-primary">
                Save as Reusable Preset
              </h3>
              <p className="text-[11px] font-mono text-obsidian-muted">
                Capture entire production DNA for multi-project reuse
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded text-obsidian-muted hover:text-obsidian-primary hover:bg-canvas transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {errorMsg && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {successMsg && (
            <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* Preset Name */}
          <div>
            <label className="block text-xs font-mono uppercase text-obsidian-secondary mb-1">
              Preset Name *
            </label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. YouTube Global Kids Comedy (Non-Verbal)"
              className="w-full bg-canvas border border-border rounded-lg px-3 py-2 text-sm text-obsidian-primary focus:outline-none focus:border-amber-500 font-sans"
            />
          </div>

          {/* Category */}
          <div>
            <ObsidianDropdown
              label="Category / Genre Tag"
              placeholder="Select Category..."
              icon={<Palette className="w-4 h-4 text-amber-500" />}
              options={[
                { value: "general", title: "General / Standard", description: "Default theatrical format", badge: "Standard" },
                { value: "kids_comedy", title: "Kids Comedy / Slapstick Non-Verbal", description: "High retention 4.0-5.0s pacing, expressive 3D animation", badge: "Algorithm" },
                { value: "cyberpunk", title: "Cyberpunk Neo-Noir", description: "Anamorphic flares, neon reflections, wet asphalt", badge: "Noir" },
                { value: "sci_fi", title: "Sci-Fi & Space Opera", description: "Deep space contrast, sterile chrome, orbital scale", badge: "Sci-Fi" },
                { value: "fantasy", title: "High Fantasy & Adventure", description: "Volumetric luminescence, ancient lore, epic vistas", badge: "Fantasy" },
                { value: "documentary", title: "Cinematic Documentary", description: "Visceral handheld, naturalistic grading", badge: "Doc" },
                { value: "anime", title: "Anime / Cel Animation", description: "Vibrant cloudscapes, emotional eyes, radiant flares", badge: "Anime" },
              ]}
              value={category}
              onChange={(val) => setCategory(val)}
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-xs font-mono uppercase text-obsidian-secondary mb-1">
              Description &amp; Director Notes
            </label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Outline the core aesthetic, pacing rules, and intended distribution target..."
              className="w-full bg-canvas border border-border rounded-lg px-3 py-2 text-xs text-obsidian-primary placeholder:text-obsidian-muted focus:outline-none focus:border-amber-500 resize-none font-sans"
            />
          </div>

          {/* Included Components Chips */}
          <div className="pt-2">
            <span className="block text-[11px] font-mono uppercase text-obsidian-muted mb-2">
              Captured Production Blueprint Components:
            </span>
            <div className="grid grid-cols-2 gap-2 text-[11px] font-mono text-obsidian-secondary">
              <div className="flex items-center gap-1.5 p-2 rounded bg-canvas border border-border">
                <Palette className="w-3.5 h-3.5 text-amber-500" />
                <span>Visual DNA (#Style)</span>
              </div>
              <div className="flex items-center gap-1.5 p-2 rounded bg-canvas border border-border">
                <Layers className="w-3.5 h-3.5 text-blue-400" />
                <span>Optics &amp; Framing</span>
              </div>
              <div className="flex items-center gap-1.5 p-2 rounded bg-canvas border border-border">
                <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                <span>Pacing &amp; Audio Bridges</span>
              </div>
              <div className="flex items-center gap-1.5 p-2 rounded bg-canvas border border-border">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                <span>QC Gate Thresholds</span>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="pt-3 border-t border-border flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 rounded-lg bg-canvas border border-border text-xs text-obsidian-secondary hover:text-obsidian-primary transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-5 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-canvas font-semibold text-xs shadow-glow transition-all flex items-center gap-2"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Saving Preset...</span>
                </>
              ) : (
                <>
                  <BookmarkPlus className="w-3.5 h-3.5" />
                  <span>Save to Presets Library</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
