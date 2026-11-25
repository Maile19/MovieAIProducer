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
  Wand2,
  Compass,
} from "lucide-react";
import {
  Scene,
  Shot,
  api,
  FlowProxyStatus,
  DirectorPolishResult,
  DirectorPolishTake,
  DirectorAdvisorResult,
  DirectorAdvisorRecommendation,
} from "@/lib/api";
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
  const [sceneDialogue, setSceneDialogue] = useState(scene?.dialogue || "");
  const [durationTarget, setDurationTarget] = useState(scene?.duration_target || 5.0);
  const [sceneStatus, setSceneStatus] = useState(scene?.status || "PLANNED");
  const [cameraCode, setCameraCode] = useState(scene?.camera_code || "#Cam 01");
  const [lightingCode, setLightingCode] = useState(scene?.lighting_code || "#Light 01");
  const [transitionType, setTransitionType] = useState(scene?.transition_type || "J_CUT");
  const [audioLeadSeconds, setAudioLeadSeconds] = useState<number>(scene?.audio_lead_seconds ?? 1.0);
  const [coverageStyle, setCoverageStyle] = useState<string>("classic_coverage");
  const [shotsRefreshKey, setShotsRefreshKey] = useState<number>(0);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [isSplitting, setIsSplitting] = useState(false);
  const [isPolishing, setIsPolishing] = useState(false);
  const [polishResult, setPolishResult] = useState<DirectorPolishResult | null>(null);
  const [selectedTakeIndex, setSelectedTakeIndex] = useState<number>(0);

  // Polya AI Director Advisor state
  const [sceneShots, setSceneShots] = useState<Shot[]>([]);
  const [advisorShotId, setAdvisorShotId] = useState<string>("");
  const [advisorFocus, setAdvisorFocus] = useState<"all" | "optics" | "staging" | "lighting" | "continuity">("all");
  const [isAdvising, setIsAdvising] = useState(false);
  const [advisorResult, setAdvisorResult] = useState<DirectorAdvisorResult | null>(null);
  const [applyingRecId, setApplyingRecId] = useState<string | null>(null);

  // Visual preview state (Dynamic Provider Switching: Google Flow Free / 9Router / Mock)
  const [previewUrl, setPreviewUrl] = useState<string | null>(scene?.preview_url || null);
  const [previewProvider, setPreviewProvider] = useState<string>(scene?.preview_provider || "google_flow");
  const [selectedProvider, setSelectedProvider] = useState<"google_flow" | "9router" | "mock" | string>("google_flow");
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

  // Multi-engine live Dual-RAG prompt compiler inside drawer
  const [compilerEngine, setCompilerEngine] = useState<
    "9router" | "flux" | "sd35" | "google_flow" | "veo" | "kling" | "seedance" | "runway" | "sora" | "comfyui"
  >("veo");
  const [compilerAccordionOpen, setCompilerAccordionOpen] = useState(true);
  const [copiedPrompt, setCopiedPrompt] = useState(false);
  const [compiledPromptText, setCompiledPromptText] = useState<string>("");
  const [isCompilingPrompt, setIsCompilingPrompt] = useState<boolean>(false);
  const [compiledMeta, setCompiledMeta] = useState<{
    tokens?: number;
    characterName?: string | null;
    stateCode?: string;
    dirHits?: number;
    swHits?: number;
  } | null>(null);
  const [compileTrigger, setCompileTrigger] = useState<number>(0);

  useEffect(() => {
    if (scene) {
      setSlugline(scene.slugline || "");
      setNarrativeGoal(scene.narrative_goal || "");
      setSceneDialogue(scene.dialogue || "");
      setDurationTarget(scene.duration_target || 5.0);
      setSceneStatus(scene.status || "PLANNED");
      setCameraCode(scene.camera_code || "#Cam 01");
      setLightingCode(scene.lighting_code || "#Light 01");
      setTransitionType(scene.transition_type || "J_CUT");
      setAudioLeadSeconds(scene.audio_lead_seconds ?? 1.0);
      setPreviewUrl(scene.preview_url || null);
      if (scene.preview_provider) {
        setPreviewProvider(scene.preview_provider);
      }
      setPreviewError(null);
      setPolishResult(null);
      setSelectedTakeIndex(0);
      setAdvisorResult(null);
      setAdvisorShotId("");

      api.scenes
        .listShots(scene.id)
        .then((res) => {
          const shotsList = res?.data || [];
          setSceneShots(shotsList);
          const prim = shotsList[0];
          if (prim) {
            setAdvisorShotId(prim.id);
            if (prim.camera_code) setCameraCode(prim.camera_code);
            if (prim.light_code || prim.lighting_code) {
              setLightingCode(prim.light_code || prim.lighting_code || "#Light 01");
            }
            if (prim.transition_type && prim.transition_type !== "NONE") {
              setTransitionType(prim.transition_type);
            }
            const savedLead = prim.fg_bg_layers?.audio_lead_seconds;
            if (typeof savedLead === "number") {
              setAudioLeadSeconds(savedLead);
            }
          }
        })
        .catch(() => setSceneShots([]));
    }
  }, [scene]);

  useEffect(() => {
    if (!scene?.id || shotsRefreshKey === 0) return;
    api.scenes
      .listShots(scene.id)
      .then((res) => {
        const shotsList = res?.data || [];
        setSceneShots(shotsList);
        if (shotsList.length > 0 && !shotsList.some((s) => s.id === advisorShotId)) {
          setAdvisorShotId(shotsList[0].id);
        }
      })
      .catch(() => {});
  }, [scene?.id, shotsRefreshKey, advisorShotId]);

  useEffect(() => {
    if (!scene?.id || !compilerAccordionOpen) return;
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        setIsCompilingPrompt(true);
        const res = await api.transpile.transpilePrompt({
          provider_target: compilerEngine,
          project_id: scene.project_id,
          scene_id: scene.id,
          style_code: styleCode,
          camera_code: cameraCode,
          light_code: lightingCode,
          slugline,
          narrative_goal: narrativeGoal,
          action_description: narrativeGoal,
          dialogue: sceneDialogue || undefined,
          transition_type: transitionType,
          audio_lead_seconds: audioLeadSeconds,
          is_non_verbal: isNonVerbal,
        });
        if (!cancelled && res?.data) {
          const d = res.data as any;
          setCompiledPromptText(d.positive || d.positive_prompt || "");
          setCompiledMeta({
            tokens: d.metadata?.prompt_tokens_est,
            characterName: d.metadata?.continuity_sources?.character_name,
            stateCode: d.metadata?.continuity_sources?.state_code,
            dirHits: d.metadata?.continuity_sources?.director_rag_hits,
            swHits: d.metadata?.continuity_sources?.screenwriter_rag_hits,
          });
        }
      } catch {
        if (!cancelled) {
          setCompiledPromptText(
            `[${compilerEngine.toUpperCase()}]: ${slugline}. ${narrativeGoal}. ${styleCode}, ${cameraCode}, ${lightingCode}.`
          );
          setCompiledMeta(null);
        }
      } finally {
        if (!cancelled) setIsCompilingPrompt(false);
      }
    }, 280);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [
    scene?.id,
    scene?.project_id,
    compilerAccordionOpen,
    compilerEngine,
    styleCode,
    cameraCode,
    lightingCode,
    slugline,
    narrativeGoal,
    sceneDialogue,
    transitionType,
    audioLeadSeconds,
    isNonVerbal,
    compileTrigger,
  ]);

  if (!scene) return null;

  const handleSaveScene = async () => {
    try {
      setIsSaving(true);
      await api.scenes.update(scene.id, {
        slugline,
        narrative_goal: narrativeGoal,
        duration_target: durationTarget,
        status: sceneStatus,
        dialogue: sceneDialogue,
        camera_code: cameraCode,
        lighting_code: lightingCode,
        transition_type: transitionType,
        audio_lead_seconds: audioLeadSeconds,
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2000);
      setShotsRefreshKey((k) => k + 1);
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
      await api.scenes.autoSplit(scene.id, targetSec, coverageStyle);
      setDurationTarget(targetSec);
      setShotsRefreshKey((k) => k + 1);
      onSceneUpdated({ silent: true });
      showToast("completed", `Shots decomposed via ${coverageStyle.replace("_", " ")} plan.`);
    } catch (err) {
      console.error(err);
    } finally {
      setIsSplitting(false);
    }
  };

  const handleDirectorPolish = async () => {
    if (!scene) return;
    try {
      setIsPolishing(true);
      const res = await api.scenes.directorPolish(scene.id, {
        slugline,
        narrative_goal: narrativeGoal,
        dialogue: sceneDialogue,
        style_code: styleCode,
        camera_code: cameraCode,
        lighting_code: lightingCode,
      });
      if (res?.data) {
        setPolishResult(res.data);
        setSelectedTakeIndex(0);
      }
    } catch (err: any) {
      console.error(err);
      showToast("error", err?.message || "Gagal mendapatkan saran Director Polish.");
    } finally {
      setIsPolishing(false);
    }
  };

  const polishTakes: DirectorPolishTake[] = polishResult?.options?.length
    ? polishResult.options
    : polishResult
    ? [
        {
          take_id: "recommended",
          label: "Recommended Cut",
          slugline: polishResult.suggestions.slugline,
          narrative_goal: polishResult.suggestions.narrative_goal,
          dialogue: polishResult.suggestions.dialogue,
          camera_code: polishResult.suggestions.camera_code || cameraCode,
          lighting_code: polishResult.suggestions.lighting_code || lightingCode,
          transition_type: polishResult.suggestions.transition_type || transitionType,
          director_notes: polishResult.suggestions.director_notes,
        },
      ]
    : [];

  const handleApplyPolish = async (takeOverride?: DirectorPolishTake) => {
    const selectedTake = takeOverride || polishTakes[selectedTakeIndex] || polishTakes[0];
    if (!selectedTake || !scene) return;
    const nextSlug = selectedTake.slugline;
    const nextGoal = selectedTake.narrative_goal;
    const nextDlg = selectedTake.dialogue ?? sceneDialogue;
    const nextCam = selectedTake.camera_code || cameraCode;
    const nextLight = selectedTake.lighting_code || lightingCode;
    const nextCut = selectedTake.transition_type || transitionType;

    setSlugline(nextSlug);
    setNarrativeGoal(nextGoal);
    setSceneDialogue(nextDlg || "");
    setCameraCode(nextCam);
    setLightingCode(nextLight);
    setTransitionType(nextCut);

    try {
      await api.scenes.update(scene.id, {
        slugline: nextSlug,
        narrative_goal: nextGoal,
        dialogue: nextDlg || "",
        camera_code: nextCam,
        lighting_code: nextLight,
        transition_type: nextCut,
      });
      setShotsRefreshKey((k) => k + 1);
      onSceneUpdated({ silent: true });
      showToast("completed", `Take '${selectedTake.label}' diterapkan & disinkronkan ke primary shot (${nextCam} / ${nextLight} / ${nextCut}).`);
    } catch {
      showToast("completed", `Take '${selectedTake.label}' diterapkan ke draft; klik Save Changes untuk menyimpan.`);
    }
    setPolishResult(null);
  };

  const handleAskDirectorAdvisor = async () => {
    if (!scene) return;
    try {
      setIsAdvising(true);
      const res = await api.scenes.directorAdvisor(scene.project_id, scene.id, {
        shot_id: advisorShotId || null,
        focus: advisorFocus,
        include_rag: true,
      });
      if (res?.data) {
        setAdvisorResult(res.data);
      }
    } catch (err: any) {
      showToast("error", err?.message || "Gagal memuat rekomendasi Director Advisor.");
    } finally {
      setIsAdvising(false);
    }
  };

  const handleApplyAdvisorOptics = async (rec: DirectorAdvisorRecommendation) => {
    if (!scene) return;
    setApplyingRecId(rec.recommendation_id);
    const targetShotId = advisorShotId || sceneShots[0]?.id || "";
    try {
      if (targetShotId) {
        await api.scenes.updateShot(targetShotId, {
          camera_code: rec.camera_code,
          lens_code: rec.lens_code,
          comp_code: rec.comp_code,
          light_code: rec.light_code,
          act_code: rec.act_code,
          speed_code: rec.speed_code,
          transition_type: rec.transition_type,
        });
      } else {
        await api.scenes.update(scene.id, {
          camera_code: rec.camera_code,
          lighting_code: rec.light_code,
          transition_type: rec.transition_type,
        });
      }
      if (!targetShotId || targetShotId === sceneShots[0]?.id) {
        setCameraCode(rec.camera_code);
        setLightingCode(rec.light_code);
        setTransitionType(rec.transition_type);
      }
      setShotsRefreshKey((k) => k + 1);
      onSceneUpdated({ silent: true });
      showToast(
        "completed",
        `Optics '${rec.title}' diterapkan (${rec.camera_code} · ${rec.lens_code} · ${rec.light_code}).`
      );
    } catch (err: any) {
      showToast("error", err?.message || "Gagal menerapkan optik Director Advisor.");
    } finally {
      setApplyingRecId(null);
    }
  };

  const handleGeneratePreview = async () => {
    try {
      stopPolling();
      setIsGeneratingPreview(true);
      setPreviewError(null);

      if (selectedProvider === "google_flow") {
        let prompt = previewPromptOverride.trim();
        if (!prompt) {
          try {
            const trRes = await api.transpile.transpilePrompt({
              provider_target: "google_flow",
              project_id: scene.project_id,
              scene_id: scene.id,
              style_code: styleCode,
              camera_code: cameraCode,
              light_code: lightingCode,
              slugline,
              narrative_goal: narrativeGoal,
              action_description: narrativeGoal,
              dialogue: sceneDialogue || undefined,
              transition_type: transitionType,
              audio_lead_seconds: audioLeadSeconds,
              is_non_verbal: isNonVerbal,
            });
            const trData = trRes?.data as any;
            prompt = (trData?.positive || trData?.positive_prompt || "").trim();
          } catch {
            prompt = "";
          }
          if (!prompt) {
            prompt = `${slugline}. ${narrativeGoal}. ${styleCode}, ${cameraCode}, ${lightingCode}.`;
          }
        }

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
    return (
      compiledPromptText ||
      `${slugline}. ${narrativeGoal}. ${styleCode}, ${cameraCode}, ${lightingCode}.`
    );
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
            <div className="flex items-center justify-between">
              <label className="text-[10px] text-obsidian-muted uppercase">Narrative Goal &amp; Dramatic Beat</label>
              <button
                type="button"
                onClick={handleDirectorPolish}
                disabled={isPolishing}
                className="flex items-center gap-1 text-[10px] text-amber-400 hover:text-amber-300 transition-colors disabled:opacity-50 cursor-pointer"
                title="Get AI Director suggestions without overwriting manual inputs"
              >
                {isPolishing ? (
                  <>
                    <Loader2 className="w-3 h-3 animate-spin" />
                    <span>Polishing...</span>
                  </>
                ) : (
                  <>
                    <Wand2 className="w-3 h-3" />
                    <span>Director Polish</span>
                  </>
                )}
              </button>
            </div>
            <textarea
              value={narrativeGoal}
              onChange={(e) => setNarrativeGoal(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 rounded-lg bg-panel border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none text-xs resize-none"
            />
          </div>

          {/* Multi-Option Director Polish Preview Cards (3 Selectable Takes) */}
          {polishResult && polishTakes.length > 0 && (
            <div className="p-3.5 rounded-xl bg-elevated/80 border border-amber-500/40 space-y-3 font-mono text-xs animate-in fade-in duration-200">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div className="flex items-center gap-1.5 text-amber-400 font-bold text-[11px]">
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Director Polish — Select Creative Take ({polishTakes.length} Options)</span>
                </div>
                <span className="text-[9px] text-obsidian-muted">Non-destructive until Apply</span>
              </div>

              {/* 3 Selectable Take Tabs / Cards */}
              <div className="space-y-2">
                {polishTakes.map((take, idx) => {
                  const isActiveTake = idx === selectedTakeIndex;
                  return (
                    <div
                      key={take.take_id || idx}
                      onClick={() => setSelectedTakeIndex(idx)}
                      className={cn(
                        "p-3 rounded-lg border cursor-pointer transition-all space-y-2",
                        isActiveTake
                          ? "bg-amber-500/10 border-amber-500/70 shadow-sm"
                          : "bg-canvas/70 border-border hover:border-amber-500/30"
                      )}
                    >
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <div className="flex items-center gap-1.5">
                          <span className={cn("font-bold text-xs", isActiveTake ? "text-amber-300" : "text-obsidian-primary")}>
                            Take {idx + 1}: {take.label}
                          </span>
                          {take.word_count !== undefined && (
                            <span className="px-1.5 py-0.2 rounded text-[9px] bg-panel border border-border text-obsidian-muted">
                              {take.word_count}w ({take.estimated_duration_seconds}s)
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-1 text-[9px] font-bold">
                          <span className="px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-300 border border-blue-500/30">
                            {take.camera_code}
                          </span>
                          <span className="px-1.5 py-0.5 rounded bg-violet-500/15 text-violet-300 border border-violet-500/30">
                            {take.lighting_code}
                          </span>
                          <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                            {take.transition_type}
                          </span>
                        </div>
                      </div>

                      {take.angle_rationale && (
                        <div className="text-[10px] text-obsidian-muted">{take.angle_rationale}</div>
                      )}
                      <div className="text-[11px] text-emerald-400 font-semibold">{take.slugline}</div>
                      <div className="text-[11px] text-obsidian-primary font-sans">{take.narrative_goal}</div>
                      {take.dialogue && (
                        <div className="text-[11px] text-purple-300 italic">&ldquo;{take.dialogue}&rdquo;</div>
                      )}
                      <div className="text-[10px] text-obsidian-secondary border-t border-border/50 pt-1">
                        <span className="text-amber-400 font-bold">Rationale: </span>
                        {take.director_notes}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Actions */}
              <div className="flex items-center justify-end gap-2 pt-1 border-t border-border/60">
                <button
                  type="button"
                  onClick={() => setPolishResult(null)}
                  className="px-3 py-1 rounded bg-panel hover:bg-elevated border border-border text-obsidian-secondary hover:text-rose-400 transition-colors text-[11px]"
                >
                  Discard
                </button>
                <button
                  type="button"
                  onClick={() => handleApplyPolish()}
                  className="flex items-center gap-1.5 px-3.5 py-1 rounded bg-amber-500 hover:bg-amber-600 text-canvas font-bold transition-all shadow-glow text-[11px]"
                >
                  <Check className="w-3.5 h-3.5" />
                  <span>Apply Selected Take</span>
                </button>
              </div>
            </div>
          )}

          {/* Duration Selector (5s | 10s | 15s) & Dual-Brain Coverage Auto-Split */}
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

            <div className="flex items-center gap-1.5 flex-wrap">
              <select
                value={coverageStyle}
                onChange={(e) => setCoverageStyle(e.target.value)}
                className="px-2 py-1 rounded-lg bg-panel border border-border text-[10px] font-mono text-obsidian-primary focus:outline-none focus:border-amber-500"
                title="Select Screenwriter + Director Shot Coverage Strategy"
              >
                <option value="classic_coverage">Classic Coverage</option>
                <option value="visceral_oner">Visceral Oner</option>
                <option value="rapid_montage">Rapid Montage</option>
                <option value="intimate_subtext">Intimate Subtext</option>
              </select>

              <button
                type="button"
                onClick={() => handleAutoSplit(durationTarget)}
                disabled={isSplitting}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-elevated hover:bg-elevated/80 border border-amber-500/40 text-amber-400 text-[10px] font-semibold transition-all disabled:opacity-50"
                title={`Dual-Brain Auto-Split (${coverageStyle}) for ${durationTarget}s scene`}
              >
                <Layers className="w-3 h-3" />
                <span>
                  {isSplitting
                    ? "Splitting..."
                    : coverageStyle === "visceral_oner"
                    ? `Auto-Split (Oner ${durationTarget}s)`
                    : `Auto-Split (${durationTarget <= 5.0 ? "1" : durationTarget <= 10.0 ? (coverageStyle === "rapid_montage" ? "3" : "2") : (coverageStyle === "rapid_montage" ? "4" : "3")} Shots)`}
                </span>
              </button>
            </div>
          </div>
        </div>

        {/* Visual Preview */}
        <div className="p-4 rounded-xl bg-panel border border-border space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-500" />
              <h4 className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary">
                Visual Concept Preview
              </h4>
            </div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded text-[9px] font-bold uppercase bg-amber-500/10 text-amber-400 border border-amber-500/30">
                Visual AI
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
                {(["google_flow", "9router", "mock"] as const).map((prov) => (
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
                        : "Visual AI"}
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
        <DialogueCalibrator
          sceneId={scene.id}
          initialDialogue={sceneDialogue}
          speakingCharacter={scene.speaking_character}
          durationTarget={durationTarget}
          initialTransitionType={transitionType}
          initialAudioLead={audioLeadSeconds}
          onDialogueChange={setSceneDialogue}
          onCutStrategyChange={(nextCut, nextLead) => {
            setTransitionType(nextCut);
            setAudioLeadSeconds(nextLead);
          }}
          isNonVerbal={isNonVerbal}
        />

        {/* Shot List Manager */}
        <ShotListManager sceneId={scene.id} refreshKey={shotsRefreshKey} onShotsUpdated={onSceneUpdated} />

        {/* Polya AI Director Advisor (Non-Destructive 7-Layer Optical & Continuity Guidance) */}
        <div className="p-4 rounded-xl bg-panel border border-border space-y-3 font-sans text-xs">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Compass className="w-4 h-4 text-amber-500 shrink-0" />
              <h4 className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary">
                Polya Director Advisor
              </h4>
            </div>

            <div className="flex flex-wrap items-center gap-1.5 font-mono">
              {sceneShots.length > 0 && (
                <select
                  value={advisorShotId}
                  onChange={(e) => setAdvisorShotId(e.target.value)}
                  className="px-2 py-1 rounded-lg bg-canvas border border-border text-[10px] text-obsidian-primary focus:outline-none focus:border-amber-500"
                  title="Target shot for optical advisory"
                >
                  {sceneShots.map((sh) => (
                    <option key={sh.id} value={sh.id}>
                      Shot #{sh.shot_number} ({sh.camera_code})
                    </option>
                  ))}
                </select>
              )}

              <select
                value={advisorFocus}
                onChange={(e) => setAdvisorFocus(e.target.value as any)}
                className="px-2 py-1 rounded-lg bg-canvas border border-border text-[10px] text-obsidian-primary focus:outline-none focus:border-amber-500"
              >
                <option value="all">All Axes</option>
                <option value="optics">Optics</option>
                <option value="staging">Staging</option>
                <option value="lighting">Lighting</option>
                <option value="continuity">Continuity</option>
              </select>

              <button
                type="button"
                onClick={handleAskDirectorAdvisor}
                disabled={isAdvising}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-canvas hover:bg-elevated border border-amber-500/40 text-amber-400 text-[10px] font-bold transition-colors disabled:opacity-50"
              >
                {isAdvising ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                <span>{isAdvising ? "Advising..." : "Ask Director Advisor"}</span>
              </button>
            </div>
          </div>

          {advisorResult && (
            <div className="space-y-2.5 font-mono">
              <div className="flex flex-wrap items-center gap-1.5 text-[10px] text-obsidian-muted">
                <span className="px-1.5 py-0.5 rounded bg-canvas border border-border text-amber-400">
                  {advisorResult.source}
                </span>
                <span className="px-1.5 py-0.5 rounded bg-canvas border border-border">
                  RAG Hits: {advisorResult.director_rag_hits}
                </span>
                {advisorResult.bible_anchors?.matched_character && (
                  <span className="px-1.5 py-0.5 rounded bg-canvas border border-border text-cyan-300">
                    {advisorResult.bible_anchors.matched_character} ({advisorResult.bible_anchors.active_state_code || "#State 01"})
                  </span>
                )}
                {advisorResult.bible_anchors?.matched_environment && (
                  <span className="px-1.5 py-0.5 rounded bg-canvas border border-border text-emerald-300">
                    Env: {advisorResult.bible_anchors.matched_environment}
                  </span>
                )}
              </div>

              {advisorResult.shot_risk_flags?.length > 0 && (
                <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/30 space-y-1 text-[10px] text-amber-300">
                  {advisorResult.shot_risk_flags.map((rf, i) => (
                    <div key={i}>
                      <strong>[{rf.code}]</strong> {rf.detail}
                    </div>
                  ))}
                </div>
              )}

              <div className="space-y-2">
                {advisorResult.recommendations.map((rec) => (
                  <div
                    key={rec.recommendation_id}
                    className="p-3 rounded-lg bg-canvas border border-border space-y-2"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span className="text-[9px] uppercase text-amber-400 font-bold">{rec.axis}</span>
                        <div className="text-xs font-bold text-obsidian-primary font-sans">{rec.title}</div>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleApplyAdvisorOptics(rec)}
                        disabled={applyingRecId === rec.recommendation_id}
                        className="px-2.5 py-1 rounded bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-[10px] flex items-center gap-1 shrink-0 disabled:opacity-50"
                      >
                        {applyingRecId === rec.recommendation_id ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <Check className="w-3 h-3" />
                        )}
                        <span>Apply Optics</span>
                      </button>
                    </div>

                    <p className="text-[11px] text-obsidian-secondary font-sans leading-relaxed">{rec.rationale}</p>

                    <div className="flex flex-wrap gap-1 text-[9px]">
                      {[
                        rec.camera_code,
                        rec.lens_code,
                        rec.comp_code,
                        rec.light_code,
                        rec.act_code,
                        rec.speed_code,
                        rec.transition_type,
                      ].map((code, idx) => (
                        <span
                          key={`${rec.recommendation_id}-${idx}`}
                          className="px-1.5 py-0.5 rounded bg-panel border border-border text-obsidian-primary"
                        >
                          {code}
                        </span>
                      ))}
                    </div>

                    {rec.continuity_warnings?.length > 0 && (
                      <div className="text-[10px] text-amber-300/90">
                        Note: {rec.continuity_warnings.join(" ")}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

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
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
                  {[
                    { id: "9router", label: "9Router AI" },
                    { id: "flux", label: "FLUX.1 Dev" },
                    { id: "sd35", label: "SD 3.5 Large" },
                    { id: "google_flow", label: "Google Flow" },
                    { id: "veo", label: "Google Veo" },
                    { id: "kling", label: "Kling 1.5" },
                    { id: "seedance", label: "Seedance" },
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
                <button
                  type="button"
                  onClick={() => setCompileTrigger((n) => n + 1)}
                  disabled={isCompilingPrompt}
                  className="p-1.5 rounded bg-canvas hover:bg-elevated border border-border text-amber-400 shrink-0 disabled:opacity-50"
                  title="Recompile via Dual-RAG /api/v1/transpile"
                >
                  <RefreshCw className={cn("w-3.5 h-3.5", isCompilingPrompt && "animate-spin")} />
                </button>
              </div>

              {compiledMeta && (
                <div className="flex flex-wrap items-center gap-1.5 text-[9px] text-obsidian-muted">
                  {compiledMeta.characterName && (
                    <span className="px-1.5 py-0.5 rounded bg-blue-500/10 border border-blue-500/30 text-blue-300">
                      DNA: {compiledMeta.characterName} ({compiledMeta.stateCode || "#State 01"})
                    </span>
                  )}
                  <span className="px-1.5 py-0.5 rounded bg-canvas border border-border">
                    Dual-RAG 8765:{compiledMeta.dirHits ?? 0} &bull; 8766:{compiledMeta.swHits ?? 0}
                  </span>
                  {compiledMeta.tokens !== undefined && (
                    <span className="px-1.5 py-0.5 rounded bg-canvas border border-border text-emerald-400">
                      {compiledMeta.tokens} tokens
                    </span>
                  )}
                </div>
              )}

              {/* Compiled Prompt Area */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-obsidian-muted uppercase flex items-center gap-1.5">
                    <span>Dual-RAG Compiled Prompt:</span>
                    {isCompilingPrompt && <Loader2 className="w-3 h-3 animate-spin text-amber-400" />}
                  </span>
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
                <div className="p-3 rounded-lg bg-canvas border border-border text-[11px] text-obsidian-primary leading-relaxed selection:bg-amber-500/30 max-h-36 overflow-y-auto">
                  {getEngineCompiledPrompt()}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Automated QC Scorecard */}
        <QcScorecard sceneId={scene.id} keyframeUrl={previewUrl} />
      </div>
    </div>
  );
}
