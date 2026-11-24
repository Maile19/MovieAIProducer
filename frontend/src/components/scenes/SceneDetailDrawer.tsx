"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  X,
  Save,
  Check,
  Cpu,
  ChevronDown,
  ChevronRight,
  Copy,
  Clock,
  Layers,
  Sparkles,
  Image as ImageIcon,
  Loader2,
  AlertTriangle,
  ExternalLink,
  RefreshCw,
} from "lucide-react";
import { Scene, api, FlowProxyStatus } from "@/lib/api";
import DialogueCalibrator from "./DialogueCalibrator";
import ShotListManager from "./ShotListManager";
import QcScorecard from "./QcScorecard";
import { cn } from "@/lib/utils";
import ObsidianDropdown from "@/components/ui/ObsidianDropdown";

interface SceneDetailDrawerProps {
  scene: Scene | null;
  onClose: () => void;
  onSceneUpdated: (options?: { silent?: boolean }) => void;
  styleCode?: string;
  isNonVerbal?: boolean;
}

export default function SceneDetailDrawer({
  scene,
  onClose,
  onSceneUpdated,
  styleCode = "#Style 01",
  isNonVerbal = false,
}: SceneDetailDrawerProps) {
  const [slugline, setSlugline] = useState(scene?.slugline || "");
  const [narrativeGoal, setNarrativeGoal] = useState(scene?.narrative_goal || "");
  const [durationTarget, setDurationTarget] = useState(scene?.duration_target || 5.0);
  const [sceneStatus, setSceneStatus] = useState(scene?.status || "PLANNED");
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [isSplitting, setIsSplitting] = useState(false);

  // Visual preview state (Dynamic Provider Switching: Google Flow Free / 9Router / SD 3.5 Large)
  const [previewUrl, setPreviewUrl] = useState<string | null>(scene?.preview_url || null);
  const [previewProvider, setPreviewProvider] = useState<string>(scene?.preview_provider || "google_flow");
  const [selectedProvider, setSelectedProvider] = useState<"google_flow" | "9router" | "sd35_large_hf" | "mock">("google_flow");
  const [selectedModel, setSelectedModel] = useState<string>("gemini-3.1-flash-image");
  const [isGeneratingPreview, setIsGeneratingPreview] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewPromptOverride, setPreviewPromptOverride] = useState("");
  const [showPromptOverride, setShowPromptOverride] = useState(false);

  // Polling guard and live progress
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const elapsedIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const toastTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const [elapsedSec, setElapsedSec] = useState<number>(0);
  const [activeJob, setActiveJob] = useState<{
    id: string;
    status: string;
    account_id?: number | null;
  } | null>(null);
  const [toast, setToast] = useState<{
    type: "queued" | "completed" | "error";
    message: string;
  } | null>(null);

  const showToast = (type: "queued" | "completed" | "error", message: string) => {
    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    setToast({ type, message });
    toastTimeoutRef.current = setTimeout(() => {
      setToast(null);
    }, 5000);
  };

  const stopPolling = () => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    if (elapsedIntervalRef.current) {
      clearInterval(elapsedIntervalRef.current);
      elapsedIntervalRef.current = null;
    }
  };

  useEffect(() => {
    return () => {
      stopPolling();
      if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    };
  }, [scene?.id]);

  // SOCKS5 Android Proxy Live Status
  const [proxyStatus, setProxyStatus] = useState<FlowProxyStatus | null>(null);
  const [isCheckingProxy, setIsCheckingProxy] = useState(false);
  const [proxyOfflineAlert, setProxyOfflineAlert] = useState(false);

  const handleCheckProxy = async () => {
    try {
      setIsCheckingProxy(true);
      const res = await api.flow.getProxyStatus();
      setProxyStatus(res);
      if (res.healthy) {
        setProxyOfflineAlert(false);
      }
      return res;
    } catch (err: any) {
      const fallback: FlowProxyStatus = {
        healthy: false,
        status: "offline",
        host: "127.0.0.1",
        port: 10808,
        proxy_url: "socks5://127.0.0.1:10808",
        detail: err?.message || "Gagal menghubungkan ke service proxy",
      };
      setProxyStatus(fallback);
      return fallback;
    } finally {
      setIsCheckingProxy(false);
    }
  };

  useEffect(() => {
    if (selectedProvider === "google_flow") {
      handleCheckProxy();
    }
  }, [selectedProvider]);

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
      setPreviewUrl(scene.preview_url || null);
      if (scene.preview_provider) {
        setPreviewProvider(scene.preview_provider);
      }
      setPreviewError(null);
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

  const handleAutoSplit = async (targetSec: number) => {
    try {
      setIsSplitting(true);
      await api.scenes.autoSplit(scene.id, targetSec);
      setDurationTarget(targetSec);
      onSceneUpdated();
    } catch (err) {
      console.error(err);
    } finally {
      setIsSplitting(false);
    }
  };

  const handleGeneratePreview = async () => {
    try {
      stopPolling();
      setIsGeneratingPreview(true);
      setPreviewError(null);

      if (selectedProvider === "google_flow") {
        const prompt =
          previewPromptOverride.trim() ||
          `${slugline}. ${narrativeGoal}. ${styleCode}. 8k cinematic photorealistic keyframe.`;

        const startTime = Date.now();
        setElapsedSec(0);
        elapsedIntervalRef.current = setInterval(() => {
          setElapsedSec(Math.floor((Date.now() - startTime) / 1000));
        }, 1000);

        try {
          const res = await api.flow.generateImage({
            prompt,
            aspect_ratio: "16:9",
            scene_id: scene.id,
            project_id: scene.project_id,
          });

          const jobId = res.job_id;
          setActiveJob({ id: jobId, status: "queued" });
          showToast("queued", `Job preview #${jobId.slice(0, 8)} berhasil masuk ke antrean Google Flow pool.`);

          let consecutiveErrors = 0;
          pollingIntervalRef.current = setInterval(async () => {
            const currentSec = Math.floor((Date.now() - startTime) / 1000);
            if (currentSec >= 180) {
              stopPolling();
              setIsGeneratingPreview(false);
              setActiveJob(null);
              const timeoutMsg = "Timeout menunggu antrean Google Flow (180 detik).";
              setPreviewError(timeoutMsg);
              showToast("error", timeoutMsg);
              return;
            }

            try {
              const job = await api.flow.getJob(jobId);
              consecutiveErrors = 0;
              setActiveJob({
                id: jobId,
                status: job.status,
                account_id: job.assigned_account_id,
              });

              if (job.status === "completed" && job.image_url) {
                stopPolling();
                try {
                  await api.scenes.attachPreview(scene.id, {
                    preview_url: job.image_url,
                    preview_provider: "google_flow",
                    job_id: jobId,
                  });
                } catch (attachErr) {
                  console.warn("attachPreview warning:", attachErr);
                }
                setPreviewUrl(job.image_url);
                setPreviewProvider("google_flow");
                setIsGeneratingPreview(false);
                setActiveJob(null);
                showToast("completed", "Preview visual scene berhasil di-render dan di-attach!");
                onSceneUpdated({ silent: true });
              } else if (job.status === "failed") {
                stopPolling();
                setIsGeneratingPreview(false);
                setActiveJob(null);
                const errMsg = job.error_message || "Generasi Google Flow gagal.";
                if (errMsg.includes("SOCKS5_PROXY_OFFLINE") || errMsg.includes("ERR_PROXY_")) {
                  setProxyOfflineAlert(true);
                  setPreviewError("Proxy SOCKS5 Android Offline. Pastikan reverse tunnel di HP Android sudah aktif.");
                  showToast("error", "Proxy SOCKS5 Android Offline. Periksa koneksi HP.");
                } else {
                  setPreviewError(errMsg);
                  showToast("error", `Flow render failed: ${errMsg}`);
                }
              }
            } catch (pollErr: any) {
              consecutiveErrors++;
              console.warn(`Polling error (${consecutiveErrors}/5):`, pollErr);
              if (consecutiveErrors >= 5) {
                stopPolling();
                setIsGeneratingPreview(false);
                setActiveJob(null);
                const netMsg = pollErr?.message || "Koneksi terputus saat memeriksa status render Google Flow.";
                setPreviewError(netMsg);
                showToast("error", netMsg);
              }
            }
          }, 3000);
          return;
        } catch (postErr: any) {
          stopPolling();
          setIsGeneratingPreview(false);
          setActiveJob(null);
          const rawErr =
            postErr?.response?.data?.detail ||
            postErr?.response?.data?.error?.message ||
            postErr?.message ||
            postErr;
          const errDetailStr = typeof rawErr === "object" ? (rawErr.message || rawErr.detail || JSON.stringify(rawErr)) : String(rawErr);
          if (
            errDetailStr.includes("SOCKS5_PROXY_OFFLINE") ||
            errDetailStr.includes("ERR_PROXY_") ||
            errDetailStr.includes("Proxy SOCKS5 Android")
          ) {
            setProxyOfflineAlert(true);
            setPreviewError("Proxy SOCKS5 Android Offline. Pastikan reverse tunnel di HP Android sudah aktif.");
            showToast("error", "Proxy SOCKS5 Android Offline.");
          } else {
            setPreviewError(errDetailStr || "Gagal membuat job Google Flow.");
            showToast("error", errDetailStr || "Gagal membuat job Google Flow.");
          }
          return;
        }
      }

      const res = await api.scenes.generatePreview(scene.id, {
        prompt: previewPromptOverride.trim() || undefined,
        aspect_ratio: "16:9",
        provider: selectedProvider,
        model: selectedProvider === "9router" ? selectedModel : undefined,
        enable_fallback: true,
      });
      if (res?.data?.preview_url) {
        setPreviewUrl(res.data.preview_url);
        if (res.data.provider) setPreviewProvider(res.data.provider);
        showToast("completed", `Preview visual berhasil di-generate via ${res.data.provider || selectedProvider}.`);
        onSceneUpdated({ silent: true });
      }
      setIsGeneratingPreview(false);
    } catch (err: any) {
      stopPolling();
      console.error("Preview generation error:", err);
      const msg =
        (typeof err?.message === "string" && err.message !== "[object Object]" ? err.message : null) ||
        (typeof err?.detail === "string" ? err.detail : null) ||
        "Failed to generate visual preview";
      setPreviewError(msg);
      showToast("error", msg);
      setIsGeneratingPreview(false);
    }
  };

  const getEngineCompiledPrompt = () => {
    const durSec = durationTarget || 5.0;
    switch (compilerEngine) {
      case "veo":
        return `[Google Veo Flow]: Cinematic 4K video, 2.39:1 anamorphic. Scene ${scene.scene_number}: ${slugline}. Beat: ${narrativeGoal}. ${styleCode}. Dynamic ${durSec}-second camera motion, photorealistic film grain, 24fps motion coherence.`;
      case "kling":
        return `[Kling 1.5 Pro]: High-fidelity cinematic master shot in ${slugline}. ${narrativeGoal}. Stylized on ${styleCode}. Precise physical interaction, seamless ${durSec}-second cadence.`;
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
              <ObsidianDropdown
                label="Scene Status"
                size="sm"
                options={[
                  { value: "PLANNED", title: "Planned", description: "Scene structured and queued", badge: "Stage 01" },
                  { value: "GENERATING", title: "Generating", description: "Inference actively rendering", badge: "Stage 02" },
                  { value: "QC_PASSED", title: "QC Passed", description: "Biometric and continuity passed", badge: "Stage 03" },
                  { value: "COMPLETED", title: "Completed", description: "Approved and ready for timeline", badge: "Stage 04" },
                ]}
                value={sceneStatus}
                onChange={(val) => setSceneStatus(val)}
              />
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

          {/* Duration Selector (5s | 10s | 15s) & Multi-Shot Assembly Trigger */}
          <div className="pt-2 border-t border-border flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-amber-500" />
              <label className="text-[10px] text-obsidian-muted uppercase font-bold">
                Scene Duration:
              </label>
              <div className="flex items-center p-0.5 bg-panel rounded-lg border border-border">
                {[5.0, 10.0, 15.0].map((sec) => (
                  <button
                    key={sec}
                    type="button"
                    onClick={() => setDurationTarget(sec)}
                    className={cn(
                      "px-2.5 py-1 rounded-md text-[11px] font-semibold transition-all",
                      durationTarget === sec
                        ? "bg-amber-500 text-canvas font-bold shadow-sm"
                        : "text-obsidian-muted hover:text-obsidian-primary"
                    )}
                  >
                    {sec}s
                  </button>
                ))}
              </div>
            </div>

            {durationTarget > 5.0 && (
              <button
                type="button"
                onClick={() => handleAutoSplit(durationTarget)}
                disabled={isSplitting}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-elevated hover:bg-elevated/80 border border-amber-500/40 text-amber-400 text-[10px] font-semibold transition-all disabled:opacity-50"
                title={`Auto-split into ${durationTarget === 10.0 ? "2" : "3"} shots @ 5.0s`}
              >
                <Layers className="w-3 h-3" />
                <span>
                  {isSplitting
                    ? "Splitting..."
                    : `Auto-Split (${durationTarget === 10.0 ? "2x5s" : "3x5s"})`}
                </span>
              </button>
            )}
          </div>
        </div>

        {/* Visual Preview (Stable Diffusion 3.5 Large) */}
        <div className="p-4 rounded-xl bg-panel border border-border space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-500" />
              <h4 className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary">
                Visual Concept Preview (SD 3.5 Large)
              </h4>
            </div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded text-[9px] font-bold uppercase bg-amber-500/10 text-amber-400 border border-amber-500/30">
                HF Space
              </span>
              <button
                type="button"
                onClick={() => setShowPromptOverride(!showPromptOverride)}
                className="text-[10px] text-obsidian-muted hover:text-amber-400 transition-colors underline"
              >
                {showPromptOverride ? "Hide Prompt" : "Edit Prompt"}
              </button>
            </div>
          </div>

          {showPromptOverride && (
            <div className="space-y-1 animate-in fade-in duration-150">
              <label className="text-[10px] text-obsidian-muted uppercase">Prompt Override (Optional)</label>
              <textarea
                value={previewPromptOverride}
                onChange={(e) => setPreviewPromptOverride(e.target.value)}
                placeholder="Leave blank to use auto-compiled Hollywood cinematic prompt..."
                rows={2}
                className="w-full px-3 py-1.5 rounded-lg bg-canvas border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none text-xs resize-none"
              />
            </div>
          )}

          {/* Provider Selection Matrix for Dynamic Switching */}
          <div className="flex flex-wrap items-center justify-between gap-2 p-2 rounded-lg bg-canvas border border-border">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] uppercase font-bold text-obsidian-muted">Provider:</span>
              <div className="flex items-center gap-1">
                {(["google_flow", "9router", "sd35_large_hf", "mock"] as const).map((prov) => (
                  <button
                    key={prov}
                    type="button"
                    onClick={() => setSelectedProvider(prov)}
                    className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold transition-all ${
                      selectedProvider === prov
                        ? "bg-amber-500 text-canvas shadow-sm"
                        : "bg-panel text-obsidian-muted hover:text-obsidian-primary"
                    }`}
                  >
                    {prov === "google_flow"
                      ? "Google Flow (Free)"
                      : prov === "9router"
                      ? "9Router (Combos)"
                      : prov === "sd35_large_hf"
                      ? "SD 3.5 HF"
                      : "Local Mock"}
                  </button>
                ))}
              </div>
            </div>

            {selectedProvider === "9router" && (
              <div className="flex items-center gap-1">
                <span className="text-[10px] text-obsidian-muted">Model:</span>
                <select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  className="px-2 py-0.5 rounded bg-panel border border-border text-obsidian-primary text-[10px] font-mono focus:outline-none focus:border-amber-500"
                >
                  <option value="gemini-3.1-flash-image">gemini-3.1-flash-image (Tier 1)</option>
                  <option value="geminis">geminis (Multi-Model Combo)</option>
                  <option value="Agy">Agy (Antigravity Pool)</option>
                  <option value="ag/gemini-3.8-flash">ag/gemini-3.8-flash</option>
                </select>
              </div>
            )}
          </div>

          {/* Live SOCKS5 Android Status Bar inside Drawer */}
          {selectedProvider === "google_flow" && (
            <div className="flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-lg bg-panel border border-border text-[11px] font-mono">
              <div className="flex items-center gap-1.5">
                <span
                  className={cn(
                    "w-2 h-2 rounded-full",
                    proxyStatus?.healthy
                      ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.7)]"
                      : "bg-rose-500 animate-pulse"
                  )}
                />
                <span className="text-obsidian-secondary">SOCKS5 Android:</span>
                <strong className={proxyStatus?.healthy ? "text-emerald-400" : "text-rose-400"}>
                  {proxyStatus?.healthy ? "ONLINE" : "OFFLINE"}
                </strong>
                {proxyStatus?.healthy && proxyStatus.latency_ms && (
                  <span className="text-[10px] text-obsidian-muted font-mono">
                    ({proxyStatus.latency_ms}ms)
                  </span>
                )}
              </div>
              <button
                type="button"
                onClick={handleCheckProxy}
                disabled={isCheckingProxy}
                className="px-2 py-0.5 rounded text-[10px] font-semibold bg-canvas hover:bg-panel text-obsidian-primary border border-border transition disabled:opacity-50"
                title={proxyStatus?.detail || "Cek koneksi SOCKS5 Android"}
              >
                {isCheckingProxy ? "Checking..." : "[Check Connection]"}
              </button>
            </div>
          )}

          {/* SOCKS5 Proxy Offline Alert Banner */}
          {proxyOfflineAlert && (
            <div className="p-3 rounded-lg bg-rose-500/15 border border-rose-500/40 text-xs font-mono text-rose-300 space-y-2 animate-in fade-in">
              <div className="flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <div className="flex-1 space-y-1">
                  <p className="font-bold">⚠️ SOCKS5 Proxy Android Offline</p>
                  <p className="text-[11px] text-obsidian-secondary leading-relaxed">
                    Koneksi tunnel HP Android (127.0.0.1:10808) tidak aktif. Pastikan aplikasi SOCKS5 / reverse tunnel di HP Android sudah dinyalakan.
                  </p>
                  <div className="pt-1 flex items-center gap-2">
                    <button
                      type="button"
                      onClick={async () => {
                        const s = await handleCheckProxy();
                        if (s.healthy) setProxyOfflineAlert(false);
                      }}
                      disabled={isCheckingProxy}
                      className="px-2.5 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-canvas font-bold text-[10px] flex items-center gap-1 transition"
                    >
                      {isCheckingProxy ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                      <span>Check Connection</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setProxyOfflineAlert(false)}
                      className="px-2.5 py-1 rounded bg-panel hover:bg-canvas text-obsidian-muted hover:text-obsidian-primary text-[10px] border border-border transition"
                    >
                      Tutup
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Toast Notification for Google Flow / Preview status */}
          {toast && (
            <div
              className={cn(
                "p-3 rounded-lg border text-xs font-mono flex items-center justify-between gap-2 transition-all",
                toast.type === "completed"
                  ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300"
                  : toast.type === "error"
                  ? "bg-rose-500/15 border-rose-500/40 text-rose-300"
                  : "bg-amber-500/15 border-amber-500/40 text-amber-300"
              )}
            >
              <div className="flex items-center gap-2">
                {toast.type === "completed" ? (
                  <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                ) : toast.type === "error" ? (
                  <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                ) : (
                  <Sparkles className="w-4 h-4 text-amber-400 shrink-0 animate-pulse" />
                )}
                <span>{toast.message}</span>
              </div>
              <button
                type="button"
                onClick={() => setToast(null)}
                className="text-[10px] opacity-70 hover:opacity-100 p-0.5 text-obsidian-muted hover:text-obsidian-primary"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Active Flow Progress Box */}
          {isGeneratingPreview && (
            <div className="p-3.5 rounded-xl bg-panel/90 border-2 border-amber-500/60 shadow-[0_0_15px_rgba(245,158,11,0.2)] animate-pulse space-y-3 font-mono">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Loader2 className="w-4 h-4 text-amber-400 animate-spin" />
                  <span className="text-xs font-bold text-amber-300 uppercase tracking-wide">
                    Active Flow Generation
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      "px-2 py-0.5 rounded text-[10px] font-bold border",
                      proxyStatus?.healthy
                        ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                        : "bg-rose-500/20 text-rose-400 border-rose-500/30"
                    )}
                  >
                    SOCKS5: {proxyStatus?.healthy ? "ONLINE" : "OFFLINE"}
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      stopPolling();
                      setIsGeneratingPreview(false);
                      setActiveJob(null);
                      showToast("error", "Generasi Flow dibatalkan oleh pengguna.");
                    }}
                    className="text-[10px] text-obsidian-muted hover:text-rose-400 px-1.5 py-0.5 rounded bg-canvas border border-border transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>

              {/* Status Pool */}
              <div className="text-[11px] text-obsidian-secondary flex items-center justify-between">
                <span>
                  Status Pool:{" "}
                  <strong className="text-obsidian-primary">
                    {activeJob?.status === "processing"
                      ? `Sedang Render di Playwright (Akun #${activeJob.account_id || 1})`
                      : "Menunggu Antrean Worker Pool (Round-Robin 6 Akun)..."}
                  </strong>
                </span>
                <span className="text-[10px] text-amber-400 font-bold">
                  ⏱️ {elapsedSec}s / 180s
                </span>
              </div>

              {/* Live Elapsed Progress Bar */}
              <div className="w-full h-1.5 bg-canvas rounded-full overflow-hidden border border-border">
                <div
                  className="h-full bg-gradient-to-r from-amber-500 to-amber-300 transition-all duration-1000 ease-linear rounded-full"
                  style={{ width: `${Math.min(100, Math.max(5, (elapsedSec / 180) * 100))}%` }}
                />
              </div>

              {activeJob?.id && (
                <div className="text-[9px] text-obsidian-muted truncate">
                  Job ID: <span className="font-mono text-obsidian-secondary">{activeJob.id}</span>
                </div>
              )}
            </div>
          )}

          {/* Preview Image or Placeholder */}
          {previewUrl ? (
            <div className="space-y-2">
              <div className="relative rounded-lg overflow-hidden border border-border bg-canvas aspect-video group">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={previewUrl}
                  alt={`Preview Scene ${scene.scene_number}`}
                  className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-end justify-between p-3">
                  <div className="flex items-center gap-1.5 truncate max-w-[70%]">
                    <span className="text-[10px] text-white/90 font-mono">
                      Scene #{scene.scene_number.toString().padStart(2, "0")} Keyframe
                    </span>
                    <span className="px-1.5 py-0.2 rounded bg-amber-500/80 text-black font-mono font-bold text-[9px] uppercase">
                      {previewProvider}
                    </span>
                  </div>
                  <a
                    href={previewUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 text-[10px] text-amber-400 hover:text-amber-300 bg-black/60 px-2 py-1 rounded backdrop-blur-sm"
                  >
                    <ExternalLink className="w-3 h-3" />
                    <span>Full Resolution</span>
                  </a>
                </div>
              </div>

              <div className="flex items-center justify-between pt-1">
                <span className="text-[10px] text-obsidian-muted">
                  Engine: {selectedProvider === "google_flow" ? "GOOGLE FLOW (FREE)" : selectedProvider.toUpperCase()} &bull; 16:9 Cinema &bull; Dynamic Switching Active
                </span>
                <button
                  type="button"
                  onClick={handleGeneratePreview}
                  disabled={isGeneratingPreview}
                  className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-canvas hover:bg-elevated border border-border text-amber-400 font-bold text-[11px] transition-all disabled:opacity-50"
                >
                  {isGeneratingPreview ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Generating...</span>
                    </>
                  ) : (
                    <>
                      <RefreshCw className="w-3.5 h-3.5" />
                      <span>
                        Regenerate (
                        {selectedProvider === "google_flow"
                          ? "Flow (Free)"
                          : selectedProvider === "9router"
                          ? "9Router"
                          : selectedProvider === "sd35_large_hf"
                          ? "SD 3.5"
                          : "Mock"}
                        )
                      </span>
                    </>
                  )}
                </button>
              </div>
            </div>
          ) : (
            <div className="p-5 rounded-lg border border-dashed border-border bg-canvas/40 flex flex-col items-center justify-center text-center space-y-2.5">
              <div className="w-9 h-9 rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
                <ImageIcon className="w-4 h-4" />
              </div>
              <div className="space-y-0.5">
                <p className="text-obsidian-primary font-semibold text-xs">Belum ada preview visual scene</p>
                <p className="text-obsidian-muted text-[10px] max-w-sm">
                  Generate concept visual keyframe berbasis Hollywood camera, lighting, dan beat cerita scene ini menggunakan{" "}
                  {selectedProvider === "google_flow"
                    ? "Google Flow (Free 6-Account Round-Robin Pool)"
                    : selectedProvider === "9router"
                    ? "9Router Multi-Model Combo"
                    : selectedProvider === "sd35_large_hf"
                    ? "Stable Diffusion 3.5 Large"
                    : "Local Mock Engine"}
                  .
                </p>
              </div>
              <button
                type="button"
                onClick={handleGeneratePreview}
                disabled={isGeneratingPreview}
                className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-xs shadow-glow transition-all disabled:opacity-50"
              >
                {isGeneratingPreview ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>
                      Generating via{" "}
                      {selectedProvider === "google_flow"
                        ? "Google Flow"
                        : selectedProvider === "9router"
                        ? "9Router"
                        : "SD 3.5"}
                      ...
                    </span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>
                      Generate Preview (
                      {selectedProvider === "google_flow"
                        ? "Google Flow Free"
                        : selectedProvider === "9router"
                        ? "9Router"
                        : selectedProvider === "sd35_large_hf"
                        ? "SD 3.5"
                        : "Mock"}
                      )
                    </span>
                  </>
                )}
              </button>
            </div>
          )}

          {/* Error Banner */}
          {previewError && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 flex items-start gap-2.5 text-rose-400 animate-in fade-in duration-150">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="text-[11px] leading-relaxed">
                <div className="font-bold">Gagal Generate Visual Preview</div>
                <div className="text-rose-300/90">{previewError}</div>
              </div>
            </div>
          )}
        </div>

        {/* Dynamic Dialogue Limiter & J/L-Cut Calibration Waveform */}
        <DialogueCalibrator sceneId={scene.id} durationTarget={durationTarget} isNonVerbal={isNonVerbal} />

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
