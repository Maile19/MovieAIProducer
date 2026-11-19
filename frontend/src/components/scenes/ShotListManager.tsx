"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Film,
  Plus,
  Trash2,
  Loader2,
} from "lucide-react";
import { Shot, api } from "@/lib/api";

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
  const [newDuration] = useState(5.0);
  const [newPromptOverride, setNewPromptOverride] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

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

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <div>
              <label className="text-[10px] text-obsidian-muted">Camera Movement</label>
              <select
                value={newCamCode}
                onChange={(e) => setNewCamCode(e.target.value)}
                className="w-full mt-1 px-2 py-1.5 rounded bg-panel border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none"
              >
                <option value="#Cam 01">#Cam 01 - Push-In</option>
                <option value="#Cam 02">#Cam 02 - Low-Angle Arc</option>
                <option value="#Cam 03">#Cam 03 - Steadicam</option>
                <option value="#Cam 04">#Cam 04 - Whip Pan</option>
              </select>
            </div>

            <div>
              <label className="text-[10px] text-obsidian-muted">Lens Prime</label>
              <select
                value={newLensCode}
                onChange={(e) => setNewLensCode(e.target.value)}
                className="w-full mt-1 px-2 py-1.5 rounded bg-panel border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none"
              >
                <option value="#Lens 01">#Lens 01 - 2.0x Anamorphic</option>
                <option value="#Lens 02">#Lens 02 - 35mm Spherical</option>
                <option value="#Lens 03">#Lens 03 - 85mm Portrait</option>
                <option value="#Lens 04">#Lens 04 - 24mm Wide</option>
              </select>
            </div>

            <div>
              <label className="text-[10px] text-obsidian-muted">Composition</label>
              <select
                value={newCompCode}
                onChange={(e) => setNewCompCode(e.target.value)}
                className="w-full mt-1 px-2 py-1.5 rounded bg-panel border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none"
              >
                <option value="#Comp 01">#Comp 01 - Thirds</option>
                <option value="#Comp 02">#Comp 02 - Spiral</option>
                <option value="#Comp 03">#Comp 03 - Symmetry</option>
                <option value="#Comp 04">#Comp 04 - Deep Focus</option>
              </select>
            </div>

            <div>
              <label className="text-[10px] text-obsidian-muted">Lighting</label>
              <select
                value={newLightCode}
                onChange={(e) => setNewLightCode(e.target.value)}
                className="w-full mt-1 px-2 py-1.5 rounded bg-panel border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none"
              >
                <option value="#Light 01">#Light 01 - Amber Rim</option>
                <option value="#Light 02">#Light 02 - Chiaroscuro</option>
                <option value="#Light 03">#Light 03 - Neon Rain</option>
                <option value="#Light 04">#Light 04 - Sunset</option>
              </select>
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
            className="p-3 rounded-lg bg-canvas border border-border hover:border-amber-500/30 flex items-center justify-between gap-3 text-xs font-mono transition-all group"
          >
            <div className="flex items-center gap-3 min-w-0">
              <span className="w-7 h-7 rounded-lg bg-panel border border-border flex items-center justify-center font-bold text-amber-400 text-xs shrink-0">
                {shot.shot_number || idx + 1}
              </span>

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
        ))}
      </div>
    </div>
  );
}
