"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Film,
  Plus,
  Trash2,
  Loader2,
  Sparkles,
  ExternalLink,
  AlertTriangle,
} from "lucide-react";
import { Shot, api } from "@/lib/api";
import {
  DEFAULT_CAMERAS,
  DEFAULT_LENSES,
  DEFAULT_COMPOSITIONS,
  DEFAULT_LIGHTING,
} from "@/lib/studio-constants";
import ObsidianDropdown from "@/components/ui/ObsidianDropdown";

interface ShotListManagerProps {
  sceneId: string;
  initialShots?: Shot[];
  onShotsUpdated?: () => void;
}

export default function ShotListManager({
  sceneId,
  initialShots,
  onShotsUpdated,
}: ShotListManagerProps) {
  const [shots, setShots] = useState<Shot[]>(initialShots || []);
  const [isAddingShot, setIsAddingShot] = useState(false);

  // New shot form
  const [newCamCode, setNewCamCode] = useState("#Cam 01");
  const [newLensCode, setNewLensCode] = useState("#Lens 01");
  const [newCompCode, setNewCompCode] = useState("#Comp 01");
  const [newLightCode, setNewLightCode] = useState("#Light 01");
  const [newDuration, setNewDuration] = useState(5.0);
  const [newPromptOverride, setNewPromptOverride] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [generatingShotId, setGeneratingShotId] = useState<string | null>(null);
  const [shotErrors, setShotErrors] = useState<Record<string, string>>({});

  const loadShots = useCallback(async () => {
    try {
      const res = await api.scenes.listShots(sceneId);
      if (res?.data && res.data.length > 0) {
        setShots(res.data);
      } else {
        // Fallback default shot
        setShots([
          {
            id: `shot_${sceneId}_1`,
            scene_id: sceneId,
            shot_number: 1,
            composition_code: "#Comp 01",
            camera_code: "#Cam 01",
            lens_code: "#Lens 01",
            lighting_code: "#Light 01",
            action_code: "#Act 01",
            speed_code: "#Speed 01",
            duration_seconds: 5.0,
            status: "PLANNED",
            created_at: new Date().toISOString(),
          },
        ]);
      }
    } catch {
      // Keep default shot
    }
  }, [sceneId]);

  useEffect(() => {
    if (sceneId) {
      loadShots();
    }
  }, [sceneId, loadShots]);

  const handleCreateShot = async () => {
    try {
      setIsSubmitting(true);
      const nextNumber = shots.length + 1;
      await api.scenes.createShot(sceneId, {
        shot_number: nextNumber,
        camera_code: newCamCode,
        lens_code: newLensCode,
        composition_code: newCompCode,
        lighting_code: newLightCode,
        duration_seconds: newDuration,
        prompt_override: newPromptOverride || undefined,
      });

      setIsAddingShot(false);
      setNewPromptOverride("");
      await loadShots();
      onShotsUpdated?.();
    } catch {
      // Ignore submission error
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteShot = async (shotId: string) => {
    try {
      await api.scenes.deleteShot(shotId);
      await loadShots();
      onShotsUpdated?.();
    } catch {
      // Local fallback removal
      setShots((prev) => prev.filter((s) => s.id !== shotId));
    }
  };

  const handleGenerateShotPreview = async (shotId: string) => {
    try {
      setGeneratingShotId(shotId);
      setShotErrors((prev) => ({ ...prev, [shotId]: "" }));
      await api.scenes.generateShotPreview(shotId);
      await loadShots();
      onShotsUpdated?.();
    } catch (err: any) {
      console.error(err);
      const msg = err?.message || "Failed to generate visual preview for shot";
      setShotErrors((prev) => ({ ...prev, [shotId]: msg }));
    } finally {
      setGeneratingShotId(null);
    }
  };

  return (
    <div className="p-4 rounded-xl bg-panel border border-border space-y-4 font-sans text-xs">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Film className="w-4 h-4 text-amber-500" />
          <h4 className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary">
            Shot List &amp; Optical Setup ({shots.length} Shots)
          </h4>
        </div>

        <button
          type="button"
          onClick={() => setIsAddingShot(!isAddingShot)}
          className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-canvas hover:bg-elevated border border-border text-amber-400 font-mono text-[11px] font-bold transition-all"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>{isAddingShot ? "Close Form" : "Add Shot"}</span>
        </button>
      </div>

      {/* Add Shot Inline Form */}
      {isAddingShot && (
        <div className="p-3.5 rounded-xl bg-canvas border border-amber-500/40 space-y-3 font-mono text-xs animate-in fade-in duration-150">
          <div className="text-[10px] text-amber-500 font-bold uppercase">
            Configure Shot #{shots.length + 1}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5">
            <div>
              <ObsidianDropdown
                size="sm"
                label="Camera Movement"
                options={DEFAULT_CAMERAS.map((c) => ({
                  value: c.code,
                  title: `${c.code}: ${c.name}`,
                  description: c.description || c.movement,
                  badge: c.movement,
                }))}
                value={newCamCode}
                onChange={(val) => setNewCamCode(val)}
              />
            </div>

            <div>
              <ObsidianDropdown
                size="sm"
                label="Lens Prime"
                options={DEFAULT_LENSES.map((l) => ({
                  value: l.code,
                  title: `${l.code}: ${l.name}`,
                  description: l.visual_field || l.focal,
                  badge: l.focal,
                }))}
                value={newLensCode}
                onChange={(val) => setNewLensCode(val)}
              />
            </div>

            <div>
              <ObsidianDropdown
                size="sm"
                label="Composition"
                options={DEFAULT_COMPOSITIONS.map((cp) => ({
                  value: cp.code,
                  title: `${cp.code}: ${cp.name}`,
                  description: cp.description || cp.framing,
                  badge: "Framing",
                }))}
                value={newCompCode}
                onChange={(val) => setNewCompCode(val)}
              />
            </div>

            <div>
              <ObsidianDropdown
                size="sm"
                label="Lighting"
                options={DEFAULT_LIGHTING.map((lg) => ({
                  value: lg.code,
                  title: `${lg.code}: ${lg.name}`,
                  description: lg.mood || lg.mood_application,
                  badge: "Illumination",
                }))}
                value={newLightCode}
                onChange={(val) => setNewLightCode(val)}
              />
            </div>

            <div>
              <ObsidianDropdown
                size="sm"
                label="Duration"
                options={[
                  { value: "5", title: "5.0s (Standard)", description: "Standard cinema cut length", badge: "5.0s" },
                  { value: "10", title: "10.0s (Extended)", description: "Extended rising tension length", badge: "10.0s" },
                  { value: "15", title: "15.0s (Long Take)", description: "Dramatic long take unbroken shot", badge: "15.0s" },
                ]}
                value={String(newDuration)}
                onChange={(val) => setNewDuration(parseFloat(val))}
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={() => setIsAddingShot(false)}
              className="px-3 py-1 rounded bg-panel border border-border text-obsidian-secondary"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleCreateShot}
              disabled={isSubmitting}
              className="px-4 py-1 rounded bg-amber-500 hover:bg-amber-600 text-canvas font-bold flex items-center gap-1.5"
            >
              {isSubmitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
              <span>Save Shot</span>
            </button>
          </div>
        </div>
      )}

      {/* Shots Cards List */}
      <div className="space-y-2">
        {shots.map((shot, idx) => (
          <div
            key={shot.id}
            className="p-3 rounded-lg bg-canvas border border-border hover:border-amber-500/30 flex flex-col gap-2 text-xs font-mono transition-all group"
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3 min-w-0">
                {shot.preview_url ? (
                  <div className="relative w-12 h-8 rounded border border-border overflow-hidden shrink-0 group/thumb">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={shot.preview_url}
                      alt={`Shot ${shot.shot_number}`}
                      className="w-full h-full object-cover"
                    />
                    <a
                      href={shot.preview_url}
                      target="_blank"
                      rel="noreferrer"
                      className="absolute inset-0 bg-black/60 opacity-0 group-hover/thumb:opacity-100 flex items-center justify-center text-amber-400"
                    >
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                ) : (
                  <span className="w-7 h-7 rounded-lg bg-panel border border-border flex items-center justify-center font-bold text-amber-400 text-xs shrink-0">
                    {shot.shot_number || idx + 1}
                  </span>
                )}

                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-obsidian-primary">
                      Shot {shot.shot_number || idx + 1}
                    </span>
                    <span className="text-[10px] text-amber-500">
                      {shot.camera_code || "#Cam 01"} &bull; {shot.lens_code || "#Lens 01"} &bull; {shot.lighting_code || "#Light 01"}
                    </span>
                  </div>
                  <div className="text-[10px] text-obsidian-muted mt-0.5 flex items-center gap-2">
                    <span>{shot.duration_seconds || 5.0}s duration</span>
                    <span>&bull;</span>
                    <span>{shot.composition_code || "#Comp 01"}</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={() => handleGenerateShotPreview(shot.id)}
                  disabled={generatingShotId === shot.id}
                  className="flex items-center gap-1 px-2 py-1 rounded bg-panel hover:bg-elevated border border-border text-amber-400 text-[10px] font-bold transition-all disabled:opacity-50"
                  title="Generate Shot Preview via SD 3.5"
                >
                  {generatingShotId === shot.id ? (
                    <>
                      <Loader2 className="w-3 h-3 animate-spin" />
                      <span>Rendering...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3 h-3" />
                      <span>{shot.preview_url ? "Regen" : "Preview"}</span>
                    </>
                  )}
                </button>

                <span className="px-2 py-0.5 rounded text-[9px] font-bold uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                  {shot.status || "PLANNED"}
                </span>

                {shots.length > 1 && (
                  <button
                    type="button"
                    onClick={() => handleDeleteShot(shot.id)}
                    className="text-obsidian-muted hover:text-rose-400 p-1 transition-colors"
                    title="Delete Shot"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>

            {shotErrors[shot.id] && (
              <div className="px-2.5 py-1.5 rounded bg-rose-500/10 border border-rose-500/30 text-rose-400 text-[10px] flex items-center gap-1.5">
                <AlertTriangle className="w-3 h-3 shrink-0" />
                <span className="truncate">{shotErrors[shot.id]}</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
