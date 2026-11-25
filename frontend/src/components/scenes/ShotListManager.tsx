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
  Edit3,
  Check,
  X,
} from "lucide-react";
import { Shot, api } from "@/lib/api";
import {
  DEFAULT_CAMERAS,
  DEFAULT_LENSES,
  DEFAULT_COMPOSITIONS,
  DEFAULT_LIGHTING,
  DEFAULT_ACTING,
  DEFAULT_SPEEDS,
} from "@/lib/studio-constants";
import ObsidianDropdown from "@/components/ui/ObsidianDropdown";
import { cn } from "@/lib/utils";

interface ShotListManagerProps {
  sceneId: string;
  initialShots?: Shot[];
  refreshKey?: number;
  onShotsUpdated?: () => void;
}

export default function ShotListManager({
  sceneId,
  initialShots,
  refreshKey = 0,
  onShotsUpdated,
}: ShotListManagerProps) {
  const [shots, setShots] = useState<Shot[]>(initialShots || []);
  const [isAddingShot, setIsAddingShot] = useState(false);

  // New shot form
  const [newCamCode, setNewCamCode] = useState("#Cam 01");
  const [newLensCode, setNewLensCode] = useState("#Lens 01");
  const [newCompCode, setNewCompCode] = useState("#Comp 01");
  const [newLightCode, setNewLightCode] = useState("#Light 01");
  const [newActCode, setNewActCode] = useState("#Act 01");
  const [newSpeedCode, setNewSpeedCode] = useState("#Speed 01");
  const [newTransitionType, setNewTransitionType] = useState("NONE");
  const [newDialogue, setNewDialogue] = useState("");
  const [newDuration, setNewDuration] = useState(5.0);
  const [newPromptOverride, setNewPromptOverride] = useState("");

  // Inline shot editing state
  const [editingShotId, setEditingShotId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<{
    camera_code: string;
    lens_code: string;
    comp_code: string;
    light_code: string;
    act_code: string;
    speed_code: string;
    duration_seconds: number;
    transition_type: string;
    dialogue: string;
    prompt_override: string;
  } | null>(null);
  const [isSavingEdit, setIsSavingEdit] = useState(false);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [generatingShotId, setGeneratingShotId] = useState<string | null>(null);
  const [resettingBgShotId, setResettingBgShotId] = useState<string | null>(null);
  const [shotErrors, setShotErrors] = useState<Record<string, string>>({});

  const loadShots = useCallback(async () => {
    try {
      const res = await api.scenes.listShots(sceneId);
      if (res?.data) {
        setShots(res.data);
      } else {
        setShots([]);
      }
    } catch {
      // Keep current shots state on transient fetch error
    }
  }, [sceneId]);

  useEffect(() => {
    if (sceneId) {
      loadShots();
    }
  }, [sceneId, refreshKey, loadShots]);

  const handleCreateShot = async () => {
    try {
      setIsSubmitting(true);
      const nextNumber = shots.length + 1;
      await api.scenes.createShot(sceneId, {
        shot_number: nextNumber,
        camera_code: newCamCode,
        lens_code: newLensCode,
        comp_code: newCompCode,
        light_code: newLightCode,
        act_code: newActCode,
        speed_code: newSpeedCode,
        transition_type: newTransitionType,
        dialogue: newDialogue.trim() || undefined,
        duration_seconds: newDuration,
        prompt_override: newPromptOverride.trim() || undefined,
      });

      setIsAddingShot(false);
      setNewPromptOverride("");
      setNewDialogue("");
      await loadShots();
      onShotsUpdated?.();
    } catch {
      // Ignore submission error
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleStartEditShot = (shot: Shot) => {
    setEditingShotId(shot.id);
    setEditForm({
      camera_code: shot.camera_code || "#Cam 01",
      lens_code: shot.lens_code || "#Lens 01",
      comp_code: shot.comp_code || shot.composition_code || "#Comp 01",
      light_code: shot.light_code || shot.lighting_code || "#Light 01",
      act_code: shot.act_code || shot.action_code || "#Act 01",
      speed_code: shot.speed_code || "#Speed 01",
      duration_seconds: shot.duration_seconds || 5.0,
      transition_type: shot.transition_type || "NONE",
      dialogue: shot.dialogue || "",
      prompt_override:
        shot.prompt_override || (shot.fg_bg_layers?.prompt_override as string) || "",
    });
  };

  const handleSaveEditShot = async (shotId: string) => {
    if (!editForm) return;
    try {
      setIsSavingEdit(true);
      await api.scenes.updateShot(shotId, {
        camera_code: editForm.camera_code,
        lens_code: editForm.lens_code,
        comp_code: editForm.comp_code,
        light_code: editForm.light_code,
        act_code: editForm.act_code,
        speed_code: editForm.speed_code,
        duration_seconds: editForm.duration_seconds,
        transition_type: editForm.transition_type,
        dialogue: editForm.dialogue,
        prompt_override: editForm.prompt_override,
      });
      setEditingShotId(null);
      setEditForm(null);
      await loadShots();
      onShotsUpdated?.();
    } catch (err: any) {
      setShotErrors((prev) => ({
        ...prev,
        [shotId]: err?.message || "Failed to update shot",
      }));
    } finally {
      setIsSavingEdit(false);
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

  const handleResetBackground = async (shotId: string) => {
    try {
      setResettingBgShotId(shotId);
      await api.scenes.resetShotBackground(shotId);
      await loadShots();
      onShotsUpdated?.();
    } catch (err) {
      console.error("Failed to reset background override:", err);
    } finally {
      setResettingBgShotId(null);
    }
  };

  const handleSetCustomBackground = async (shotId: string, customBg: string) => {
    try {
      await api.scenes.setShotCustomBackground(shotId, customBg);
      await loadShots();
      onShotsUpdated?.();
    } catch (err) {
      console.error("Failed to set custom background:", err);
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

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
            <div>
              <ObsidianDropdown
                size="sm"
                label="Acting Cue"
                options={DEFAULT_ACTING.map((a) => ({
                  value: a.code,
                  title: `${a.code}: ${a.name || a.cue}`,
                  description: a.micro_expressions,
                  badge: a.category,
                }))}
                value={newActCode}
                onChange={(val) => setNewActCode(val)}
              />
            </div>

            <div>
              <ObsidianDropdown
                size="sm"
                label="Motion Speed"
                options={DEFAULT_SPEEDS.map((sp) => ({
                  value: sp.code,
                  title: `${sp.code}: ${sp.name}`,
                  description: sp.timing,
                  badge: `${sp.fps}fps`,
                }))}
                value={newSpeedCode}
                onChange={(val) => setNewSpeedCode(val)}
              />
            </div>

            <div>
              <ObsidianDropdown
                size="sm"
                label="Audio Cut Bridge"
                options={[
                  { value: "NONE", title: "NONE", description: "Standard cut boundary" },
                  { value: "J_CUT", title: "J_CUT", description: "Audio leads before visual cut" },
                  { value: "L_CUT", title: "L_CUT", description: "Audio trails over next visual" },
                  { value: "HARD_CUT", title: "HARD_CUT", description: "Crisp synchronized cut" },
                ]}
                value={newTransitionType}
                onChange={(val) => setNewTransitionType(val)}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            <div className="space-y-1">
              <label className="text-[10px] text-obsidian-muted uppercase font-bold">Shot Dialogue / SFX Cue</label>
              <input
                type="text"
                value={newDialogue}
                onChange={(e) => setNewDialogue(e.target.value)}
                placeholder="Calibrated line or [SFX: ...] cue for this shot..."
                className="w-full px-2.5 py-1.5 rounded-lg bg-panel border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none text-[11px]"
              />
            </div>

            <div className="space-y-1">
              <label className="text-[10px] text-obsidian-muted uppercase font-bold">Visual Prompt Override (Optional)</label>
              <input
                type="text"
                value={newPromptOverride}
                onChange={(e) => setNewPromptOverride(e.target.value)}
                placeholder="Custom framing or blocking detail override..."
                className="w-full px-2.5 py-1.5 rounded-lg bg-panel border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none text-[11px]"
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

      {/* Shots Cards List / Clean Empty State */}
      <div className="space-y-2">
        {shots.length === 0 ? (
          <div className="p-4 rounded-lg border border-dashed border-border bg-canvas/50 text-center space-y-1 font-mono text-[11px] text-obsidian-muted">
            <p className="text-obsidian-secondary font-semibold">No shots configured yet for this scene.</p>
            <p>Use Auto-Split Coverage Planner above or click &ldquo;Add Shot&rdquo; to assemble optical shots.</p>
          </div>
        ) : shots.map((shot, idx) => (
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
                      {shot.camera_code || "#Cam 01"} &bull; {shot.lens_code || "#Lens 01"} &bull; {shot.light_code || shot.lighting_code || "#Light 01"}
                    </span>
                  </div>
                  <div className="text-[10px] text-obsidian-muted mt-0.5 flex flex-wrap items-center gap-2">
                    <span>{shot.duration_seconds || 5.0}s duration</span>
                    <span>&bull;</span>
                    <span>{shot.composition_code || shot.comp_code || "#Comp 01"}</span>
                    <span>&bull;</span>
                    <span>{shot.act_code || "#Act 01"} &bull; {shot.speed_code || "#Speed 01"}</span>
                    {shot.transition_type && shot.transition_type !== "NONE" && (
                      <>
                        <span>&bull;</span>
                        <span className="text-blue-400 font-bold">{shot.transition_type}</span>
                      </>
                    )}
                  </div>
                  {shot.dialogue && (
                    <div className="text-[10px] text-amber-300/90 italic mt-0.5 truncate max-w-md">
                      &ldquo;{shot.dialogue}&rdquo;
                    </div>
                  )}
                  {(shot.prompt_override || shot.fg_bg_layers?.prompt_override) && (
                    <div className="text-[10px] text-blue-300/90 mt-0.5 truncate max-w-md">
                      Override: {shot.prompt_override || (shot.fg_bg_layers?.prompt_override as string)}
                    </div>
                  )}

                  {/* Fallback Background auto-inheritance row */}
                  <div className="flex items-center gap-2 mt-1 text-[10px]">
                    <span className="text-obsidian-muted">BG:</span>
                    {shot.background_source === "custom" || shot.custom_background ? (
                      <div className="flex items-center gap-1.5">
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase bg-amber-500/10 text-amber-400 border border-amber-500/30">
                          Custom
                        </span>
                        <button
                          type="button"
                          onClick={() => handleResetBackground(shot.id)}
                          disabled={resettingBgShotId === shot.id}
                          className="text-[10px] text-amber-400 hover:text-amber-300 underline font-medium cursor-pointer"
                          title="Reset override to auto-inherit from Scene background"
                        >
                          {resettingBgShotId === shot.id ? "Resetting..." : "Reset Override"}
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1.5">
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase bg-blue-500/10 text-blue-400 border border-blue-500/30">
                          Inherited
                        </span>
                        <button
                          type="button"
                          onClick={() => {
                            const customUrl = window.prompt(
                              "Enter custom background image URL/path for this shot:",
                              shot.effective_background_url || ""
                            );
                            if (customUrl && customUrl.trim()) {
                              handleSetCustomBackground(shot.id, customUrl.trim());
                            }
                          }}
                          className="text-[10px] text-obsidian-muted hover:text-obsidian-primary underline cursor-pointer"
                          title="Set custom background override for this shot"
                        >
                          Override
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={() => handleGenerateShotPreview(shot.id)}
                  disabled={generatingShotId === shot.id}
                  className="flex items-center gap-1 px-2 py-1 rounded bg-panel hover:bg-elevated border border-border text-amber-400 text-[10px] font-bold transition-all disabled:opacity-50"
                  title="Generate Shot Preview"
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

                <button
                  type="button"
                  onClick={() => {
                    if (editingShotId === shot.id) {
                      setEditingShotId(null);
                      setEditForm(null);
                    } else {
                      handleStartEditShot(shot);
                    }
                  }}
                  className={cn(
                    "p-1 transition-colors rounded",
                    editingShotId === shot.id ? "text-amber-400 bg-panel" : "text-obsidian-muted hover:text-amber-400"
                  )}
                  title="Edit Shot Details"
                >
                  <Edit3 className="w-3.5 h-3.5" />
                </button>

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

            {editingShotId === shot.id && editForm && (
              <div className="p-3 rounded-lg bg-panel border border-amber-500/40 space-y-2.5 text-[11px] font-mono">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  <select
                    value={editForm.camera_code}
                    onChange={(e) => setEditForm({ ...editForm, camera_code: e.target.value })}
                    className="px-2 py-1 rounded bg-canvas border border-border text-obsidian-primary"
                  >
                    {DEFAULT_CAMERAS.map((c) => <option key={c.code} value={c.code}>{c.code}: {c.name}</option>)}
                  </select>
                  <select
                    value={editForm.lens_code}
                    onChange={(e) => setEditForm({ ...editForm, lens_code: e.target.value })}
                    className="px-2 py-1 rounded bg-canvas border border-border text-obsidian-primary"
                  >
                    {DEFAULT_LENSES.map((l) => <option key={l.code} value={l.code}>{l.code}: {l.name}</option>)}
                  </select>
                  <select
                    value={editForm.comp_code}
                    onChange={(e) => setEditForm({ ...editForm, comp_code: e.target.value })}
                    className="px-2 py-1 rounded bg-canvas border border-border text-obsidian-primary"
                  >
                    {DEFAULT_COMPOSITIONS.map((cp) => <option key={cp.code} value={cp.code}>{cp.code}: {cp.name}</option>)}
                  </select>
                  <select
                    value={editForm.light_code}
                    onChange={(e) => setEditForm({ ...editForm, light_code: e.target.value })}
                    className="px-2 py-1 rounded bg-canvas border border-border text-obsidian-primary"
                  >
                    {DEFAULT_LIGHTING.map((lg) => <option key={lg.code} value={lg.code}>{lg.code}: {lg.name}</option>)}
                  </select>
                  <select
                    value={editForm.act_code}
                    onChange={(e) => setEditForm({ ...editForm, act_code: e.target.value })}
                    className="px-2 py-1 rounded bg-canvas border border-border text-obsidian-primary"
                  >
                    {DEFAULT_ACTING.map((a) => <option key={a.code} value={a.code}>{a.code}: {a.name || a.cue}</option>)}
                  </select>
                  <select
                    value={editForm.speed_code}
                    onChange={(e) => setEditForm({ ...editForm, speed_code: e.target.value })}
                    className="px-2 py-1 rounded bg-canvas border border-border text-obsidian-primary"
                  >
                    {DEFAULT_SPEEDS.map((sp) => <option key={sp.code} value={sp.code}>{sp.code}: {sp.name}</option>)}
                  </select>
                  <select
                    value={editForm.transition_type}
                    onChange={(e) => setEditForm({ ...editForm, transition_type: e.target.value })}
                    className="px-2 py-1 rounded bg-canvas border border-border text-obsidian-primary"
                  >
                    {["NONE", "J_CUT", "L_CUT", "HARD_CUT"].map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                  <input
                    type="number"
                    min={1}
                    max={60}
                    step={0.5}
                    value={editForm.duration_seconds}
                    onChange={(e) => setEditForm({ ...editForm, duration_seconds: parseFloat(e.target.value) || 5.0 })}
                    className="px-2 py-1 rounded bg-canvas border border-border text-obsidian-primary"
                  />
                </div>
                <input
                  type="text"
                  value={editForm.dialogue}
                  onChange={(e) => setEditForm({ ...editForm, dialogue: e.target.value })}
                  placeholder="Shot dialogue / SFX cue..."
                  className="w-full px-2.5 py-1 rounded bg-canvas border border-border text-obsidian-primary"
                />
                <input
                  type="text"
                  value={editForm.prompt_override}
                  onChange={(e) => setEditForm({ ...editForm, prompt_override: e.target.value })}
                  placeholder="Prompt override (optional)..."
                  className="w-full px-2.5 py-1 rounded bg-canvas border border-border text-obsidian-primary"
                />
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => { setEditingShotId(null); setEditForm(null); }}
                    className="px-2.5 py-1 rounded bg-canvas border border-border text-obsidian-secondary flex items-center gap-1"
                  >
                    <X className="w-3 h-3" />
                    <span>Cancel</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleSaveEditShot(shot.id)}
                    disabled={isSavingEdit}
                    className="px-3 py-1 rounded bg-amber-500 hover:bg-amber-600 text-canvas font-bold flex items-center gap-1 disabled:opacity-50"
                  >
                    {isSavingEdit ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
                    <span>Save Shot</span>
                  </button>
                </div>
              </div>
            )}

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
