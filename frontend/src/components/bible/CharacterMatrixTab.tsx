"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Users,
  Plus,
  Layers,
  Mic,
  Camera,
  X,
  Loader2,
  Sparkles,
  ExternalLink,
  RefreshCw,
  CheckCircle2,
  Copy,
  Check,
  Info,
  Lock,
  Upload,
  Eye,
  Film,
  Dices,
  ZoomIn,
  AlertTriangle,
  Edit,
  Trash2,
  ArrowRight,
  XCircle,
  ShieldCheck,
  ShieldAlert,
  RotateCcw,
  AlertCircle,
} from "lucide-react";
import { Character, SheetPromptItem, Project, api, FlowProxyStatus } from "@/lib/api";
import { cn } from "@/lib/utils";
import ObsidianDropdown from "@/components/ui/ObsidianDropdown";
import AIRenderProviderCard from "@/components/AIRenderProviderCard";
import { AI_RENDER_PROVIDERS, UserProviderConfig } from "@/config/aiProviders";

const GLOBAL_PROVIDER_STORAGE_KEY = "movieai_global_render_provider_v2";

function normalizeProviderId(providerId?: string | null): string {
  if (!providerId) return "google-flow";
  const clean = providerId.trim();
  if (clean === "google_flow") return "google-flow";
  return clean;
}

function isGoogleFlowProvider(providerId?: string | null): boolean {
  const norm = (providerId || "").trim().toLowerCase();
  return norm === "google_flow" || norm === "google-flow";
}

const STRICT_BYPASS_STYLE_CODES = new Set([
  "#Style 06",
  "#Style 09",
  "#Style 10",
  "#Style 11",
  "#Style 13",
  "#Style 14",
  "#Style 15",
  "#Style 16",
  "#Style 17",
]);

function isPhotorealisticCastingStyle(styleCode?: string | null): boolean {
  const clean = (styleCode || "#Style 01").trim();
  return !STRICT_BYPASS_STYLE_CODES.has(clean);
}

function resolveProviderDisplayInfo(providerId: string, modelId?: string) {
  const norm = normalizeProviderId(providerId);
  const spec = AI_RENDER_PROVIDERS.find((p) => p.id === norm);
  if (spec) {
    return {
      spec,
      label: modelId ? `${spec.name} (${modelId})` : spec.name,
      supportsVisualAnchor: spec.supportsVisualAnchor,
    };
  }
  if (norm === "ag_gemini_flash") {
    return {
      spec: undefined,
      label: modelId ? `AG/Gemini (${modelId})` : "AG/Gemini 3.8 Flash",
      supportsVisualAnchor: false,
    };
  }
  return {
    spec: undefined,
    label: modelId ? `${providerId} (${modelId})` : providerId,
    supportsVisualAnchor: false,
  };
}

interface CharacterMatrixTabProps {
  projectId: string;
  project?: Project | null;
  characters: Character[];
  isLocked: boolean;
  onRefresh: (options?: { silent?: boolean }) => void | Promise<void>;
  onSilentRefresh?: () => void | Promise<void>;
  onPatchCharacterAsset?: (characterId: string, slot: string, imageUrl: string, metaPatch?: Record<string, any>) => void;
  onPatchCharacterStateAsset?: (characterId: string, stateId: string, imageUrl: string, metaPatch?: Record<string, any>) => void;
}

export default function CharacterMatrixTab({
  projectId,
  project,
  characters,
  isLocked,
  onRefresh,
  onSilentRefresh,
  onPatchCharacterAsset,
  onPatchCharacterStateAsset,
}: CharacterMatrixTabProps) {
  const [selectedCharId, setSelectedCharId] = useState<string>(() => {
    if (typeof window !== "undefined") {
      try {
        const urlParams = new URLSearchParams(window.location.search);
        const fromUrl = urlParams.get("characterId");
        if (fromUrl) return fromUrl;

        const fromStorage = localStorage.getItem(`movieai_active_character_${projectId}`);
        if (fromStorage) return fromStorage;
      } catch {
        // Fallback below
      }
    }
    return characters[0]?.id || "";
  });

  const handleSelectCharacter = useCallback(
    (charId: string) => {
      setSelectedCharId(charId);
      if (typeof window !== "undefined") {
        try {
          localStorage.setItem(`movieai_active_character_${projectId}`, charId);
          const url = new URL(window.location.href);
          url.searchParams.set("characterId", charId);
          window.history.replaceState({}, "", url.toString());
        } catch {
          // ignore
        }
      }
    },
    [projectId]
  );

  // Active poller interval registry to prevent detached zombie loops
  const activePollersRef = useRef<Map<string, NodeJS.Timeout>>(new Map());

  const parseUtcTimestampMs = useCallback((dateStr: string | null | undefined): number => {
    if (!dateStr) return Date.now();
    const normalized = dateStr.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(dateStr)
      ? dateStr
      : `${dateStr}Z`;
    const ms = Date.parse(normalized);
    return isNaN(ms) ? Date.now() : ms;
  }, []);

  useEffect(() => {
    const pollers = activePollersRef.current;
    return () => {
      pollers.forEach((t) => clearInterval(t));
      pollers.clear();
    };
  }, []);
  const [addCharModalOpen, setAddCharModalOpen] = useState(false);
  const [addStateModalOpen, setAddStateModalOpen] = useState(false);

  // Add Character form & Context-Aware Auto-Generator state
  const [newCharName, setNewCharName] = useState("");
  const [newCharRole, setNewCharRole] = useState("PROTAGONIST");
  const [newCharBio, setNewCharBio] = useState("");
  const [newCharVoiceDna, setNewCharVoiceDna] = useState("");
  const [newCharPrompt, setNewCharPrompt] = useState("");
  const [newCharSeed, setNewCharSeed] = useState<number>(() => Math.floor(100000 + Math.random() * 900000));
  const [isSubmittingChar, setIsSubmittingChar] = useState(false);

  // Dual AI Provider Selector for Add Character Modal (Synced with Global Acuan)
  const [addCharLLMProvider, setAddCharLLMProvider] = useState<"9router" | "gemini" | "agy">("9router");
  const [addCharImageProvider, setAddCharImageProvider] = useState<string>("google-flow");

  // Auto-generation loading states
  const [isAutoGeneratingAll, setIsAutoGeneratingAll] = useState(false);
  const [isGeneratingField, setIsGeneratingField] = useState<Record<string, boolean>>({});

  // Pre-Creation Visual Gatekeeper staging state (Slot 1 Close-Up Master Anchor)
  const [previewToken, setPreviewToken] = useState<string | null>(null);
  const [previewCloseupUrl, setPreviewCloseupUrl] = useState<string | null>(null);
  const [previewExpressionUrl, setPreviewExpressionUrl] = useState<string | null>(null);
  const [previewFrontUrl, setPreviewFrontUrl] = useState<string | null>(null);
  const [isPreviewGenerating, setIsPreviewGenerating] = useState(false);
  const [previewStatusText, setPreviewStatusText] = useState("");
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewErrorMsg, setPreviewErrorMsg] = useState<string | null>(null);
  const [isRollingCloseup, setIsRollingCloseup] = useState(false);
  const [isRollingExpression, setIsRollingExpression] = useState(false);
  const [isRollingFront, setIsRollingFront] = useState(false);
  const [isExprOutdated, setIsExprOutdated] = useState(false);
  const [isFrontOutdated, setIsFrontOutdated] = useState(false);
  const [isRegeneratingAllDownstream, setIsRegeneratingAllDownstream] = useState(false);
  const [isStoppingDownstream, setIsStoppingDownstream] = useState(false);
  const [downstreamProgressText, setDownstreamProgressText] = useState<string | null>(null);
  const abortDownstreamRef = useRef<boolean>(false);

  // Global Batch Downstream Generation States (Cards 2–8 + Dynamic States for all characters)
  const [isBatchGenerating, setIsBatchGenerating] = useState(false);
  const [isStoppingBatch, setIsStoppingBatch] = useState(false);
  const abortBatchRef = useRef<boolean>(false);
  const wakeLockRef = useRef<any>(null);
  const [batchResumeMode, setBatchResumeMode] = useState<boolean>(true);
  const [batchPreflightModalOpen, setBatchPreflightModalOpen] = useState(false);
  const [batchProgress, setBatchProgress] = useState<{
    currentCharIdx: number;
    totalReady: number;
    charName: string;
    currentStep: number;
    totalSteps: number;
    stepText: string;
  } | null>(null);
  const [batchSummaryModalOpen, setBatchSummaryModalOpen] = useState(false);

  // Batch Active Guard (Generate All Downstream / Regenerate All Downstream)
  const isBatchActive = isBatchGenerating || isRegeneratingAllDownstream;
  const [batchLockToast, setBatchLockToast] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
  } | null>(null);
  const batchLockToastTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const showBatchLockNotification = useCallback((actionName: string) => {
    if (batchLockToastTimeoutRef.current) {
      clearTimeout(batchLockToastTimeoutRef.current);
    }
    const processName = isBatchGenerating
      ? "Generate All Downstream for All Characters"
      : isRegeneratingAllDownstream
      ? "Regenerate All Downstream"
      : "Batch Downstream";
    setBatchLockToast({
      isOpen: true,
      title: "Aksi Terkunci oleh Proses Batch",
      message: `Proses '${processName}' sedang berlangsung sekuensial. Tunggu selesai atau hentikan batch (Stop) sebelum melakukan ${actionName}.`,
    });
    batchLockToastTimeoutRef.current = setTimeout(() => {
      setBatchLockToast(null);
    }, 5000);
  }, [isBatchGenerating, isRegeneratingAllDownstream]);
  const [batchSummaryData, setBatchSummaryData] = useState<{
    total: number;
    readyCount: number;
    successCount: number;
    skippedChars: { name: string; role: string; reason: string }[];
    failedChars: { name: string; role: string; error: string }[];
    wasCancelled?: boolean;
  } | null>(null);

  // Mobile Screen Wake Lock to prevent screen sleep / Chrome background throttling
  const requestWakeLock = useCallback(async () => {
    try {
      if (typeof navigator !== "undefined" && "wakeLock" in navigator && (navigator as any).wakeLock?.request) {
        wakeLockRef.current = await (navigator as any).wakeLock.request("screen");
        console.log("Screen Wake Lock active for batch generation.");
      }
    } catch (err) {
      console.warn("Screen Wake Lock could not be acquired:", err);
    }
  }, []);

  const releaseWakeLock = useCallback(async () => {
    try {
      if (wakeLockRef.current) {
        await wakeLockRef.current.release();
        wakeLockRef.current = null;
        console.log("Screen Wake Lock released.");
      }
    } catch (err) {
      console.warn("Screen Wake Lock release failed:", err);
    }
  }, []);

  useEffect(() => {
    return () => {
      releaseWakeLock();
    };
  }, [releaseWakeLock]);

  // Real DOM verification states for staged preview images
  const [closeupImgLoaded, setCloseupImgLoaded] = useState(false);
  const [closeupImgError, setCloseupImgError] = useState(false);
  const [exprImgLoaded, setExprImgLoaded] = useState(false);
  const [exprImgError, setExprImgError] = useState(false);
  const [frontImgLoaded, setFrontImgLoaded] = useState(false);
  const [frontImgError, setFrontImgError] = useState(false);

  // Lightbox zoom modal state
  const [lightboxImageUrl, setLightboxImageUrl] = useState<string | null>(null);
  const [lightboxTitle, setLightboxTitle] = useState<string | null>(null);

  // Add State form
  const [newStateCode, setNewStateCode] = useState("#State 01");
  const [newStateLabel, setNewStateLabel] = useState("");
  const [newWardrobe, setNewWardrobe] = useState("");
  const [newInjuries, setNewInjuries] = useState("");
  const [newExpression, setNewExpression] = useState("");
  const [isSubmittingState, setIsSubmittingState] = useState(false);
  const [isDeletingChar, setIsDeletingChar] = useState(false);

  // Dynamic State Progression Matrix UI & AI Auto-Suggestion States
  const [editingStateId, setEditingStateId] = useState<string | null>(null);
  const [isSuggestingAll, setIsSuggestingAll] = useState(false);
  const [isSuggestingField, setIsSuggestingField] = useState<{
    wardrobe?: boolean;
    injuries?: boolean;
    expression?: boolean;
  }>({});
  const [suggestionError, setSuggestionError] = useState<string | null>(null);
  const suggestAbortControllerRef = useRef<AbortController | null>(null);
  const [deletingStateId, setDeletingStateId] = useState<string | null>(null);

  // AI Generation Provider & Model Configuration (Synced with Global Acuan SQLite)
  const [selectedProvider, setSelectedProvider] = useState<string>(() => {
    if (typeof window !== "undefined") {
      try {
        const raw = localStorage.getItem(`${GLOBAL_PROVIDER_STORAGE_KEY}_${projectId}`);
        if (raw) {
          const parsed = JSON.parse(raw);
          if (parsed?.activeProviderId) {
            return normalizeProviderId(parsed.activeProviderId);
          }
        }
      } catch {
        // ignore invalid JSON
      }
    }
    return "google-flow";
  });
  const [selectedModel, setSelectedModel] = useState<string>(() => {
    if (typeof window !== "undefined") {
      try {
        const raw = localStorage.getItem(`${GLOBAL_PROVIDER_STORAGE_KEY}_${projectId}`);
        if (raw) {
          const parsed = JSON.parse(raw);
          const pid = normalizeProviderId(parsed?.activeProviderId || "google-flow");
          const cfgModel = parsed?.configs?.[pid]?.modelId;
          if (cfgModel) return cfgModel;
          const spec = AI_RENDER_PROVIDERS.find((p) => p.id === pid);
          if (spec?.defaultModelId) return spec.defaultModelId;
        }
      } catch {
        // ignore
      }
    }
    return "flow-imagen-anchor-pro";
  });
  const [applyToAllScenes, setApplyToAllScenes] = useState<boolean>(true);
  const [globalProviderConfigs, setGlobalProviderConfigs] = useState<Record<string, UserProviderConfig>>({});

  const applyGlobalProviderState = useCallback(
    (payload: {
      activeProviderId?: string;
      applyToAllScenes?: boolean;
      configs?: Record<string, UserProviderConfig>;
    }) => {
      if (!payload?.activeProviderId) return;
      const normId = normalizeProviderId(payload.activeProviderId);
      const nextConfigs = payload.configs || {};
      const spec = AI_RENDER_PROVIDERS.find((p) => p.id === normId);
      const nextModel =
        nextConfigs[payload.activeProviderId]?.modelId ||
        nextConfigs[normId]?.modelId ||
        spec?.defaultModelId ||
        "";

      setSelectedProvider(normId);
      setSelectedModel(nextModel);
      if (typeof payload.applyToAllScenes === "boolean") {
        setApplyToAllScenes(payload.applyToAllScenes);
      }
      if (payload.configs) {
        setGlobalProviderConfigs(payload.configs);
      }
      setAddCharImageProvider(normId);
    },
    []
  );

  // Sync Character Matrix provider state directly from backend SQLite (Source of Truth)
  useEffect(() => {
    let isMounted = true;
    async function syncGlobalProvider() {
      try {
        const res = await fetch(`/api/v1/projects/${projectId}/render-provider`, {
          headers: { Accept: "application/json" },
        });
        if (res.ok) {
          const data = await res.json();
          if (data?.configured && data?.activeProviderId && isMounted) {
            applyGlobalProviderState({
              activeProviderId: data.activeProviderId,
              applyToAllScenes: data.applyToAllScenes,
              configs: data.configs,
            });
            return;
          }
        }
      } catch {
        // Fallback to global localStorage cache below
      }
      try {
        const raw = localStorage.getItem(`${GLOBAL_PROVIDER_STORAGE_KEY}_${projectId}`);
        if (!raw || !isMounted) return;
        const parsed = JSON.parse(raw);
        if (parsed?.activeProviderId) {
          applyGlobalProviderState({
            activeProviderId: parsed.activeProviderId,
            applyToAllScenes: parsed.applyToAllScenes,
            configs: parsed.configs,
          });
        }
      } catch {
        // ignore
      }
    }
    syncGlobalProvider();
    return () => {
      isMounted = false;
    };
  }, [projectId, applyGlobalProviderState]);

  // SOCKS5 Android Proxy Live Indicator & Fail-Fast State
  const [proxyStatus, setProxyStatus] = useState<FlowProxyStatus | null>(null);
  const [isCheckingProxy, setIsCheckingProxy] = useState(false);
  const consecutiveProxyFailures = useRef(0);
  const [proxyOfflineAlert, setProxyOfflineAlert] = useState<{
    isOpen: boolean;
    message?: string;
    detail?: string;
  } | null>(null);

  const handleCheckProxy = useCallback(async () => {
    try {
      setIsCheckingProxy(true);
      const status = await api.flow.getProxyStatus();
      if (status.healthy) {
        consecutiveProxyFailures.current = 0;
        setProxyStatus(status);
        setProxyOfflineAlert(null);
      } else {
        consecutiveProxyFailures.current += 1;
        if (consecutiveProxyFailures.current >= 2) {
          setProxyStatus(status);
        }
      }
      return status;
    } catch (err: any) {
      consecutiveProxyFailures.current += 1;
      const fallback: FlowProxyStatus = {
        healthy: false,
        status: "offline",
        host: "127.0.0.1",
        port: 10808,
        proxy_url: "socks5://127.0.0.1:10808",
        detail: err?.message || "Tidak dapat menghubungi server health check",
      };
      if (consecutiveProxyFailures.current >= 2) {
        setProxyStatus(fallback);
      }
      return fallback;
    } finally {
      setIsCheckingProxy(false);
    }
  }, []);

  useEffect(() => {
    handleCheckProxy();
    const interval = setInterval(handleCheckProxy, 20000);
    return () => clearInterval(interval);
  }, [handleCheckProxy]);

  const isProxyOfflineError = (errOrMsg: any): boolean => {
    if (!errOrMsg) return false;
    let str = "";
    if (typeof errOrMsg === "string") {
      str = errOrMsg;
    } else {
      const msgStr = typeof errOrMsg?.message === "string" ? errOrMsg.message : JSON.stringify(errOrMsg?.message || "");
      const detailStr = typeof errOrMsg?.detail === "string" ? errOrMsg.detail : JSON.stringify(errOrMsg?.detail || "");
      str = `${errOrMsg?.code || ""} ${errOrMsg?.error_code || ""} ${msgStr} ${detailStr} ${JSON.stringify(errOrMsg || {})}`;
    }
    return (
      str.includes("SOCKS5_PROXY_OFFLINE") ||
      str.includes("ERR_PROXY_CONNECTION_FAILED") ||
      str.includes("ERR_SOCKS_CONNECTION_FAILED") ||
      str.includes("ERR_TUNNEL_CONNECTION_FAILED") ||
      str.includes("Proxy SOCKS5 Android")
    );
  };

  // Per-target render loading, polling progress & error states
  const [renderingTargets, setRenderingTargets] = useState<Record<string, boolean>>({});
  const [pollStatus, setPollStatus] = useState<Record<string, string>>({});
  const [targetErrors, setTargetErrors] = useState<Record<string, string | null>>({});

  // 7-Card Per-Slot Prompts, Uploads, and Modals
  const [sheetPrompts, setSheetPrompts] = useState<Record<string, SheetPromptItem>>({});
  const [isLoadingPrompts, setIsLoadingPrompts] = useState(false);
  const [activePromptModalSlot, setActivePromptModalSlot] = useState<string | null>(null);
  const [copiedPromptSlot, setCopiedPromptSlot] = useState<string | null>(null);
  const [copiedModalField, setCopiedModalField] = useState<string | null>(null);

  // Editable per-slot prompt overrides
  const [isEditingSlotPrompt, setIsEditingSlotPrompt] = useState(false);
  const [promptDraft, setPromptDraft] = useState<{ positive: string; negative: string }>({
    positive: "",
    negative: "",
  });
  const [isSavingPromptOverride, setIsSavingPromptOverride] = useState(false);
  const [promptOverrideError, setPromptOverrideError] = useState<string | null>(null);

  // Per-slot upload states
  const [uploadingSlots, setUploadingSlots] = useState<Record<string, boolean>>({});
  const [uploadErrors, setUploadErrors] = useState<Record<string, string | null>>({});

  // Per-card Upscale 2K locking, preview dimensions, and toast feedback
  const [upscalingSlots, setUpscalingSlots] = useState<Record<string, boolean>>({});
  const [upscaleErrors, setUpscaleErrors] = useState<Record<string, string | null>>({});
  const [previewSlotMeta, setPreviewSlotMeta] = useState<
    Record<
      "closeup" | "expression" | "front",
      { resolution_width?: number | null; resolution_height?: number | null; is_2k?: boolean; previous_1k_url?: string | null }
    >
  >({
    closeup: {},
    expression: {},
    front: {},
  });
  const [upscaleToast, setUpscaleToast] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    isError?: boolean;
  } | null>(null);
  const upscaleToastTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const showUpscaleToast = useCallback((title: string, message: string, isError = false) => {
    if (upscaleToastTimeoutRef.current) {
      clearTimeout(upscaleToastTimeoutRef.current);
    }
    setUpscaleToast({ isOpen: true, title, message, isError });
    upscaleToastTimeoutRef.current = setTimeout(() => {
      setUpscaleToast(null);
    }, 5500);
  }, []);

  // Zero Static Fallback: Active characters derived purely from persistent database
  const activeCharacters: Character[] = characters;
  const selectedChar: Character | null =
    activeCharacters.find((c) => c.id === selectedCharId) || activeCharacters[0] || null;

  // Polya AI Screenwriter Generation States
  const [generateCastModalOpen, setGenerateCastModalOpen] = useState(false);
  const [addOneModalOpen, setAddOneModalOpen] = useState(false);
  const [regenModalOpen, setRegenModalOpen] = useState(false);
  const [isGeneratingCast, setIsGeneratingCast] = useState(false);
  const [isGeneratingOneChar, setIsGeneratingOneChar] = useState(false);
  const [isRegeneratingChar, setIsRegeneratingChar] = useState(false);
  const [polyaLoadingText, setPolyaLoadingText] = useState<string | null>(null);

  // Cast Generation Options
  const [preferredCastCount, setPreferredCastCount] = useState<number | null>(null);
  const [castAdditionalNotes, setCastAdditionalNotes] = useState("");

  // Add 1 Character Options
  const [addOnePreferredRole, setAddOnePreferredRole] = useState("DEUTERAGONIST");
  const [addOneCustomDirective, setAddOneCustomDirective] = useState("");

  // Re-generate Character Options
  const [regenPreserveRole, setRegenPreserveRole] = useState(true);
  const [regenCustomDirective, setRegenCustomDirective] = useState("");

  // Inline Edit States for Character Name, Role, Narrative Summary, Voice DNA & Prompt
  const [isEditingCharIdentity, setIsEditingCharIdentity] = useState(false);
  const [editCharName, setEditCharName] = useState("");
  const [editCharRole, setEditCharRole] = useState("PROTAGONIST");
  const [editCharNarrativeSummary, setEditCharNarrativeSummary] = useState("");
  const [editCharVoiceDna, setEditCharVoiceDna] = useState("");
  const [isSavingCharIdentity, setIsSavingCharIdentity] = useState(false);

  const [isEditingPrompt, setIsEditingPrompt] = useState(false);
  const [editBasePrompt, setEditBasePrompt] = useState("");
  const [isSavingPrompt, setIsSavingPrompt] = useState(false);

  const handleGenerateCast = async () => {
    try {
      setIsGeneratingCast(true);
      setPolyaLoadingText("Polya AI (Screenwriter) sedang merancang ensemble 5–8 karakter lengkap...");
      await api.bible.generateCast(projectId, {
        preferred_count: preferredCastCount || undefined,
        additional_notes: castAdditionalNotes.trim() || undefined,
        replace_existing: true,
      });
      setGenerateCastModalOpen(false);
      setCastAdditionalNotes("");
      await onRefresh();
    } catch (err: any) {
      console.error("Generate cast error:", err);
      alert(err?.message || "Gagal generate cast ensemble dari Polya AI.");
    } finally {
      setIsGeneratingCast(false);
      setPolyaLoadingText(null);
    }
  };

  const handleGenerateOneCharacter = async () => {
    try {
      setIsGeneratingOneChar(true);
      setPolyaLoadingText(`Polya AI (Screenwriter) sedang merancang 1 karakter baru (${addOnePreferredRole})...`);
      const res = await api.bible.generateOneCharacter(projectId, {
        preferred_role: addOnePreferredRole,
        custom_directive: addOneCustomDirective.trim() || undefined,
      });
      setAddOneModalOpen(false);
      setAddOneCustomDirective("");
      await onRefresh();
      if (res?.data?.id) {
        handleSelectCharacter(res.data.id);
      }
    } catch (err: any) {
      console.error("Generate 1 character error:", err);
      alert(err?.message || "Gagal membuat karakter baru via Polya AI.");
    } finally {
      setIsGeneratingOneChar(false);
      setPolyaLoadingText(null);
    }
  };

  const handleRegenerateCharacter = async () => {
    if (!selectedChar?.id) return;
    try {
      setIsRegeneratingChar(true);
      setPolyaLoadingText(`Polya AI (Screenwriter) sedang meregenerasi identitas & 5 states ${selectedChar.name}...`);
      await api.bible.regenerateCharacter(projectId, selectedChar.id, {
        custom_directive: regenCustomDirective.trim() || undefined,
        preserve_role: regenPreserveRole,
      });
      setRegenModalOpen(false);
      setRegenCustomDirective("");
      await onRefresh();
      fetchPrompts(selectedChar.id);
    } catch (err: any) {
      console.error("Regenerate character error:", err);
      alert(err?.message || "Gagal re-generate karakter via Polya AI.");
    } finally {
      setIsRegeneratingChar(false);
      setPolyaLoadingText(null);
    }
  };

  const handleStartEditIdentity = () => {
    if (!selectedChar) return;
    setEditCharName(selectedChar.name);
    setEditCharRole(selectedChar.role);
    setEditCharNarrativeSummary(selectedChar.narrative_summary || "");
    setEditCharVoiceDna(selectedChar.voice_dna_profile || "");
    setIsEditingCharIdentity(true);
  };

  const handleSaveCharacterIdentity = async () => {
    if (!selectedChar || !editCharName.trim()) return;
    try {
      setIsSavingCharIdentity(true);
      await api.bible.updateCharacter(projectId, selectedChar.id, {
        name: editCharName.trim(),
        role: editCharRole,
        narrative_summary: editCharNarrativeSummary.trim(),
        voice_dna_profile: editCharVoiceDna.trim(),
      });
      setIsEditingCharIdentity(false);
      await onRefresh();
    } catch (err: any) {
      console.error("Save identity error:", err);
      alert(err?.message || "Gagal menyimpan identitas karakter.");
    } finally {
      setIsSavingCharIdentity(false);
    }
  };

  const handleStartEditPrompt = () => {
    if (!selectedChar) return;
    setEditBasePrompt(selectedChar.base_prompt);
    setIsEditingPrompt(true);
  };

  const handleSaveBasePrompt = async () => {
    if (!selectedChar || !editBasePrompt.trim()) return;
    try {
      setIsSavingPrompt(true);
      await api.bible.updateCharacter(projectId, selectedChar.id, {
        base_prompt: editBasePrompt.trim(),
      });
      setIsEditingPrompt(false);
      await onRefresh();
      fetchPrompts(selectedChar.id);
    } catch (err: any) {
      console.error("Save base prompt error:", err);
      alert(err?.message || "Gagal menyimpan base visual prompt.");
    } finally {
      setIsSavingPrompt(false);
    }
  };

  const handleDeleteCharacter = async (charId: string, charName: string) => {
    if (!confirm(`Hapus karakter "${charName}" dan seluruh dynamic state matrix-nya secara permanen?`)) return;
    try {
      setIsDeletingChar(true);
      await api.bible.deleteCharacter(projectId, charId);
      await onRefresh();
    } catch (err: any) {
      console.error("Delete character error:", err);
      alert(err?.message || "Gagal menghapus karakter.");
    } finally {
      setIsDeletingChar(false);
    }
  };

  // Context-Aware Auto-Generator Handler (pulls NLE Studio context from backend)
  const handleAutoGenerate = async (mode: "all" | "name" | "suggestion" | "visual_prompt") => {
    try {
      if (mode === "all") {
        setIsAutoGeneratingAll(true);
      } else {
        setIsGeneratingField((prev) => ({ ...prev, [mode]: true }));
      }
      const res = await api.bible.autoGenerateCharacter(projectId, {
        llm_provider: addCharLLMProvider,
        mode,
        current_draft: {
          name: newCharName,
          role: newCharRole,
          archetype_and_bio: newCharBio,
          voice_dna_profile: newCharVoiceDna,
          base_visual_prompt: newCharPrompt,
          dna_seed: newCharSeed,
        },
      });

      if (res?.data) {
        if (mode === "all" || mode === "name") {
          if (res.data.name) setNewCharName(res.data.name);
        }
        if (mode === "all" || mode === "suggestion") {
          if (res.data.role_suggestion) {
            const upperRole = res.data.role_suggestion.toUpperCase();
            if (["PROTAGONIST", "ANTAGONIST", "DEUTERAGONIST", "MENTOR", "EXTRAS"].includes(upperRole)) {
              setNewCharRole(upperRole);
            } else {
              setNewCharRole("PROTAGONIST");
            }
          }
          if (res.data.archetype_and_bio) setNewCharBio(res.data.archetype_and_bio);
          if (res.data.voice_dna_profile) setNewCharVoiceDna(res.data.voice_dna_profile);
        }
        if (mode === "all" || mode === "visual_prompt") {
          if (res.data.base_visual_prompt) setNewCharPrompt(res.data.base_visual_prompt);
        }
      }
    } catch (err: any) {
      console.error("Auto-generate error:", err);
      setPreviewError(err?.message || "Gagal auto-generate dari konteks NLE Studio.");
    } finally {
      setIsAutoGeneratingAll(false);
      setIsGeneratingField((prev) => ({ ...prev, [mode]: false }));
    }
  };

  const handleRerollSeed = () => {
    setNewCharSeed(Math.floor(100000 + Math.random() * 900000));
    if (previewExpressionUrl) setIsExprOutdated(true);
    if (previewFrontUrl) setIsFrontOutdated(true);
  };

  // Pre-Creation Visual Gatekeeper: Generate Preview (Closeup Master Anchor, Expression, Front)
  const handleGeneratePreview = async (
    target: "closeup" | "expression" | "front" | "both" | "all" = "closeup"
  ) => {
    if (!newCharName.trim()) {
      setPreviewError("Nama karakter wajib diisi terlebih dahulu.");
      setPreviewErrorMsg("Nama karakter wajib diisi terlebih dahulu.");
      return;
    }
    const effectivePrompt =
      newCharPrompt.trim() ||
      `${newCharName}, ${newCharRole} cinematic character, isolated on a flat seamless Neutral Matte Light-Medium Studio Gray (#D4D4D4) studio background, even softbox lighting, zero environment props or color cast.`;

    setIsPreviewGenerating(true);
    setPreviewError(null);
    setPreviewErrorMsg(null);

    if (target === "closeup") {
      setCloseupImgLoaded(false);
      setCloseupImgError(false);
      setIsRollingCloseup(true);
      if (previewExpressionUrl) setIsExprOutdated(true);
      if (previewFrontUrl) setIsFrontOutdated(true);
    } else if (target === "expression") {
      setExprImgLoaded(false);
      setExprImgError(false);
      setIsRollingExpression(true);
      setIsExprOutdated(false);
    } else if (target === "front") {
      setFrontImgLoaded(false);
      setFrontImgError(false);
      setIsRollingFront(true);
      setIsFrontOutdated(false);
    } else if (target === "both") {
      // Downstream generation only (Slot 2 & 3): Do NOT reset Slot 1 Close-Up states!
      // Card 1 Close-Up remains static and displayed without spinner
      setExprImgLoaded(false);
      setExprImgError(false);
      setFrontImgLoaded(false);
      setFrontImgError(false);
      setIsRollingExpression(true);
      setIsRollingFront(true);
      setIsExprOutdated(false);
      setIsFrontOutdated(false);
    } else {
      // target === "all": reset everything
      setCloseupImgLoaded(false);
      setCloseupImgError(false);
      setExprImgLoaded(false);
      setExprImgError(false);
      setFrontImgLoaded(false);
      setFrontImgError(false);
      setIsRollingCloseup(true);
      setIsRollingExpression(true);
      setIsRollingFront(true);
      setIsExprOutdated(false);
      setIsFrontOutdated(false);
    }

    setPreviewStatusText(
      isGoogleFlowProvider(addCharImageProvider)
        ? `Mengirim ${target === "closeup" ? "Slot 1: Close-Up Master Anchor" : target === "expression" ? "Expression Sheet" : "Full Body"} ke antrean Google Flow PRO...`
        : `Merender ${target === "closeup" ? "Card 1: Character Close-Up (Master Anchor)" : target === "expression" ? "Card 2: Expression Sheet" : "Card 3: Full Body"}...`
    );

    const normModalProvider = normalizeProviderId(addCharImageProvider);
    const modalSpec = AI_RENDER_PROVIDERS.find((p) => p.id === normModalProvider);
    const modalModel =
      globalProviderConfigs[addCharImageProvider]?.modelId ||
      globalProviderConfigs[normModalProvider]?.modelId ||
      (normModalProvider === selectedProvider ? selectedModel : undefined) ||
      modalSpec?.defaultModelId ||
      undefined;

    try {
      const res = await api.bible.previewCharacter(projectId, {
        name: newCharName.trim(),
        role: newCharRole,
        base_visual_prompt: effectivePrompt,
        dna_seed: newCharSeed,
        image_provider: addCharImageProvider,
        model: modalModel,
        target,
        aspect_ratio: (target === "expression" || target === "both") ? "16:9" : target === "closeup" ? "1:1" : "3:4",
        preview_token: previewToken || undefined,
      });

      if (res.preview_token) {
        setPreviewToken(res.preview_token);
      }

      // Synchronous completion (AG/Gemini Flash, 9Router, SD 3.5 Large)
      if (res.status === "completed") {
        if (res.closeup_url) setPreviewCloseupUrl(res.closeup_url);
        if (res.expression_url) setPreviewExpressionUrl(res.expression_url);
        if (res.front_url) setPreviewFrontUrl(res.front_url);
        setPreviewSlotMeta((prev) => ({
          closeup: res.slot_dimensions?.closeup
            ? { ...res.slot_dimensions.closeup, previous_1k_url: null }
            : target === "closeup" || target === "all"
            ? { resolution_width: 1024, resolution_height: 1024, is_2k: false, previous_1k_url: null }
            : prev.closeup,
          expression: res.slot_dimensions?.expression
            ? { ...res.slot_dimensions.expression, previous_1k_url: null }
            : target === "expression" || target === "both" || target === "all"
            ? { resolution_width: 1344, resolution_height: 768, is_2k: false, previous_1k_url: null }
            : prev.expression,
          front: res.slot_dimensions?.front
            ? { ...res.slot_dimensions.front, previous_1k_url: null }
            : target === "front" || target === "both" || target === "all"
            ? { resolution_width: 768, resolution_height: 1024, is_2k: false, previous_1k_url: null }
            : prev.front,
        }));
        setPreviewStatusText("");
        setIsPreviewGenerating(false);
        setIsRollingCloseup(false);
        setIsRollingExpression(false);
        setIsRollingFront(false);
        return;
      }

      // Google Flow Async Job Handling
      if (res.status === "queued" && res.job_id) {
        const currentToken = res.preview_token;
        const jobId = res.job_id;
        const slot = res.slot || (target === "closeup" ? "closeup" : target === "front" ? "front" : "expression");
        let pollCount = 0;
        const previewStartTime = Date.now();

        const pollInterval = setInterval(async () => {
          pollCount++;
          const elapsedSec = Math.round((Date.now() - previewStartTime) / 1000);
          try {
            const job = await api.flow.getJob(jobId);
            if (job.status === "completed" && job.image_url) {
              clearInterval(pollInterval);
              const attachRes = await api.bible.attachCharacterPreviewJob(projectId, {
                preview_token: currentToken,
                job_id: jobId,
                slot: slot as "closeup" | "expression" | "front",
              });
              if (slot === "closeup") {
                setPreviewCloseupUrl(attachRes.image_url);
              } else if (slot === "expression") {
                setPreviewExpressionUrl(attachRes.image_url);
              } else {
                setPreviewFrontUrl(attachRes.image_url);
              }
              setPreviewSlotMeta((prev) => ({
                ...prev,
                [slot]: {
                  resolution_width: attachRes.resolution_width ?? (slot === "expression" ? 1344 : slot === "closeup" ? 1024 : 768),
                  resolution_height: attachRes.resolution_height ?? (slot === "expression" ? 768 : 1024),
                  is_2k: !!attachRes.is_2k,
                  previous_1k_url: null,
                },
              }));

              setPreviewStatusText("");
              setIsPreviewGenerating(false);
              setIsRollingCloseup(false);
              setIsRollingExpression(false);
              setIsRollingFront(false);

              // Auto-chain second downstream anchor (Slot 3: Full Body Front) if "both" was triggered via Google Flow
              if (target === "both" && slot === "expression") {
                setTimeout(() => {
                  handleGeneratePreview("front");
                }, 150);
              }
            } else if (job.status === "failed") {
              clearInterval(pollInterval);
              const jErr = job.error_message || "Generasi preview Flow gagal.";
              if (isProxyOfflineError(jErr)) {
                setProxyOfflineAlert({
                  isOpen: true,
                  message: `SOCKS5 Proxy Android Offline saat generate Slot ${slot}`,
                  detail: "Tunnel SOCKS5 (127.0.0.1:10808) terputus saat merender di Google Flow.",
                });
                setPreviewError("Proxy SOCKS5 Android Offline. Pastikan reverse tunnel di HP Android sudah aktif.");
                setPreviewErrorMsg("Proxy SOCKS5 Android Offline. Pastikan reverse tunnel di HP Android sudah aktif.");
              } else {
                setPreviewError(jErr);
                setPreviewErrorMsg(jErr);
              }
              setIsPreviewGenerating(false);
              setIsRollingCloseup(false);
              setIsRollingExpression(false);
              setIsRollingFront(false);
            } else {
              setPreviewStatusText(
                `Google Flow sedang memproses ${slot === "closeup" ? "Slot 1 Close-Up" : slot === "expression" ? "Expression Sheet" : "Full Body"} (${elapsedSec}s)...`
              );
              if (elapsedSec > 240 || pollCount > 80) {
                clearInterval(pollInterval);
                const timeoutMsg = "Waktu tunggu antrean Google Flow habis (240s).";
                setPreviewError(timeoutMsg);
                setPreviewErrorMsg(timeoutMsg);
                setIsPreviewGenerating(false);
                setIsRollingCloseup(false);
                setIsRollingExpression(false);
                setIsRollingFront(false);
              }
            }
          } catch (pollErr: any) {
            clearInterval(pollInterval);
            const pErrMsg = pollErr?.response?.data?.detail || pollErr?.message || "Gagal memeriksa status job Flow.";
            setPreviewError(pErrMsg);
            setPreviewErrorMsg(pErrMsg);
            setIsPreviewGenerating(false);
            setIsRollingCloseup(false);
            setIsRollingExpression(false);
            setIsRollingFront(false);
          }
        }, 3000);
      }
    } catch (err: any) {
      console.error("Preview error:", err);
      if (isProxyOfflineError(err)) {
        const detailStr =
          typeof err?.message === "string" && err.message !== "[object Object]"
            ? err.message
            : (typeof err?.detail === "string"
                ? err.detail
                : (typeof err?.detail?.message === "string"
                    ? err.detail.message
                    : "Koneksi tunnel SOCKS5 (127.0.0.1:10808) offline."));
        setProxyOfflineAlert({
          isOpen: true,
          message: "Proxy SOCKS5 Android Offline saat mengirim job ke Google Flow",
          detail: detailStr,
        });
        setPreviewError("Proxy SOCKS5 Android Offline. Pastikan reverse tunnel di HP Android sudah aktif.");
        setPreviewErrorMsg("Proxy SOCKS5 Android Offline. Pastikan reverse tunnel di HP Android sudah aktif.");
      } else {
        const rawErr = err?.response?.data?.detail || err?.response?.data?.error?.message || err?.message || err;
        const errMsg =
          typeof rawErr === "string" && rawErr !== "[object Object]"
            ? rawErr
            : (typeof rawErr?.message === "string" && rawErr.message !== "[object Object]"
                ? rawErr.message
                : (typeof rawErr?.detail === "string"
                    ? rawErr.detail
                    : JSON.stringify(rawErr)));
        setPreviewError(errMsg);
        setPreviewErrorMsg(errMsg);
      }
      setIsPreviewGenerating(false);
      setIsRollingCloseup(false);
      setIsRollingExpression(false);
      setIsRollingFront(false);
    }
  };

  const handleCloseAddModal = () => {
    if (previewToken) {
      api.bible.cleanupCharacterPreview(projectId, previewToken).catch(() => {});
    }
    setAddCharModalOpen(false);
    setPreviewToken(null);
    setPreviewCloseupUrl(null);
    setPreviewExpressionUrl(null);
    setPreviewFrontUrl(null);
    setCloseupImgLoaded(false);
    setCloseupImgError(false);
    setExprImgLoaded(false);
    setExprImgError(false);
    setFrontImgLoaded(false);
    setFrontImgError(false);
    setIsRollingCloseup(false);
    setIsRollingExpression(false);
    setIsRollingFront(false);
    setPreviewSlotMeta({ closeup: {}, expression: {}, front: {} });
    setIsExprOutdated(false);
    setIsFrontOutdated(false);
    setPreviewError(null);
    setPreviewErrorMsg(null);
    setPreviewStatusText("");
    setNewCharName("");
    setNewCharPrompt("");
    setNewCharBio("");
    setNewCharVoiceDna("");
  };

  const isVisualVerified = Boolean(
    !isPreviewGenerating &&
    (
      (previewCloseupUrl && !closeupImgError) ||
      (previewExpressionUrl && !exprImgError) ||
      (previewFrontUrl && !frontImgError)
    )
  );

  const handleCommitCharacter = async () => {
    if (!newCharName.trim()) return;
    if (!isVisualVerified) {
      const vMsg = "Generate & verifikasi preview Slot 1 Close-Up terlebih dahulu sebelum membuat karakter.";
      setPreviewError(vMsg);
      setPreviewErrorMsg(vMsg);
      return;
    }
    try {
      setIsSubmittingChar(true);
      const res = await api.bible.createCharacter(projectId, {
        name: newCharName.trim(),
        role: newCharRole,
        base_prompt: newCharPrompt || `${newCharName}, Hollywood cinematic character.`,
        narrative_summary: newCharBio.trim() || undefined,
        voice_dna_profile: newCharVoiceDna.trim() || undefined,
        dna_seed: newCharSeed,
        preview_token: previewToken || undefined,
      });
      setAddCharModalOpen(false);
      setPreviewToken(null);
      setPreviewCloseupUrl(null);
      setPreviewExpressionUrl(null);
      setPreviewFrontUrl(null);
      setCloseupImgLoaded(false);
      setCloseupImgError(false);
      setExprImgLoaded(false);
      setExprImgError(false);
      setFrontImgLoaded(false);
      setFrontImgError(false);
      setIsRollingCloseup(false);
      setIsRollingExpression(false);
      setIsRollingFront(false);
      setPreviewSlotMeta({ closeup: {}, expression: {}, front: {} });
      setPreviewError(null);
      setPreviewErrorMsg(null);
      setNewCharName("");
      setNewCharPrompt("");
      setNewCharBio("");
      setNewCharVoiceDna("");

      // Respect Global Acuan when applyToAllScenes is active; otherwise sync local selection without stale localStorage
      if (!applyToAllScenes) {
        const normModalProv = normalizeProviderId(addCharImageProvider);
        const modalSpec = AI_RENDER_PROVIDERS.find((p) => p.id === normModalProv);
        const modalModel =
          globalProviderConfigs[addCharImageProvider]?.modelId ||
          globalProviderConfigs[normModalProv]?.modelId ||
          modalSpec?.defaultModelId ||
          "";
        setSelectedProvider(normModalProv);
        setSelectedModel(modalModel);
      } else {
        setAddCharImageProvider(selectedProvider);
      }

      onRefresh();
      if (res?.data?.id) {
        handleSelectCharacter(res.data.id);
      }
    } catch (err: any) {
      console.error(err);
      const errMsg = err?.response?.data?.detail || err?.message || "Gagal menyimpan karakter.";
      setPreviewError(errMsg);
      setPreviewErrorMsg(errMsg);
    } finally {
      setIsSubmittingChar(false);
    }
  };

  // Helper to return character ID (Zero Static Data: all characters are persisted in database)
  const ensurePersistedCharacter = async (char: Character): Promise<string> => {
    return char.id;
  };

  const STATE_OPTIONS = [
    { value: "#State 01", title: "#State 01 - Normal", description: "Pristine initial baseline appearance" },
    { value: "#State 02", title: "#State 02 - Wear & Tear", description: "Minor dust, fatigue, loosened wardrobe" },
    { value: "#State 03", title: "#State 03 - Battle Damaged", description: "Scratches, torn fabrics, visible wounds" },
    { value: "#State 04", title: "#State 04 - Psychological Breakdown", description: "Disheveled hair, smeared makeup/grime, intense trauma" },
    { value: "#State 05", title: "#State 05 - Climax / Catharsis", description: "Peak climactic transformation or final resolution" },
  ];

  const getNextUnsavedStateCode = (charStates: { state_code: string }[] = [], currentCode?: string): string | null => {
    const existing = new Set(charStates.map((s) => s.state_code));
    const codes = STATE_OPTIONS.map((s) => s.value);
    if (currentCode) {
      const idx = codes.indexOf(currentCode);
      if (idx >= 0) {
        for (let i = idx + 1; i < codes.length; i++) {
          if (!existing.has(codes[i])) return codes[i];
        }
      }
    }
    for (const c of codes) {
      if (!existing.has(c)) return c;
    }
    return null;
  };

  const handleFetchStateSuggestion = async (
    targetCode: string,
    targetField: "all" | "wardrobe" | "injuries" | "expression" = "all",
    isRegen: boolean = false,
    prevVal?: string,
    explicitCurrentValues?: {
      wardrobe?: string;
      injuries_and_wear?: string;
      expression_anchor?: string;
    }
  ) => {
    if (!selectedChar?.id) return;
    setSuggestionError(null);

    // Cancel in-flight request to prevent race conditions
    if (suggestAbortControllerRef.current) {
      suggestAbortControllerRef.current.abort();
    }
    const controller = new AbortController();
    suggestAbortControllerRef.current = controller;

    if (targetField === "all") {
      setIsSuggestingAll(true);
    } else {
      setIsSuggestingField((prev) => ({ ...prev, [targetField]: true }));
    }

    try {
      const effectiveCharId = await ensurePersistedCharacter(selectedChar);
      const currentVals = explicitCurrentValues ?? {
        wardrobe: newWardrobe,
        injuries_and_wear: newInjuries,
        expression_anchor: newExpression,
      };

      const res = await api.bible.suggestCharacterState(
        effectiveCharId,
        {
          state_code: targetCode,
          target_field: targetField,
          current_values: currentVals,
          previous_value: prevVal,
          is_regeneration: isRegen,
          llm_provider: "9router",
        },
        controller.signal
      );

      if (res?.data) {
        if (targetField === "all") {
          if (res.data.wardrobe) setNewWardrobe(res.data.wardrobe);
          if (res.data.injuries_and_wear) setNewInjuries(res.data.injuries_and_wear);
          if (res.data.expression_anchor) setNewExpression(res.data.expression_anchor);
        } else if (targetField === "wardrobe" && res.data.wardrobe) {
          setNewWardrobe(res.data.wardrobe);
        } else if (targetField === "injuries" && res.data.injuries_and_wear) {
          setNewInjuries(res.data.injuries_and_wear);
        } else if (targetField === "expression" && res.data.expression_anchor) {
          setNewExpression(res.data.expression_anchor);
        }
      }
    } catch (err: any) {
      if (err.name === "AbortError" || err.message?.includes("aborted")) {
        return;
      }
      console.warn("Failed to fetch state suggestion:", err);
      setSuggestionError(err?.message || "Gagal mendapatkan saran AI.");
    } finally {
      if (targetField === "all") {
        setIsSuggestingAll(false);
      } else {
        setIsSuggestingField((prev) => ({ ...prev, [targetField]: false }));
      }
    }
  };

  const handleOpenAddState = () => {
    setEditingStateId(null);
    setSuggestionError(null);
    const nextCode = getNextUnsavedStateCode(selectedChar?.states || []) || "#State 01";
    setNewStateCode(nextCode);
    setNewStateLabel("");
    setNewWardrobe("");
    setNewInjuries("");
    setNewExpression("");
    setAddStateModalOpen(true);
    // Auto-fill recommendation immediately
    handleFetchStateSuggestion(nextCode, "all", false, undefined, {
      wardrobe: "",
      injuries_and_wear: "",
      expression_anchor: "",
    });
  };

  const handleOpenEditState = (st: any) => {
    // Keamanan Mode Edit: DO NOT run auto-suggest! Load DB values as is!
    if (suggestAbortControllerRef.current) {
      suggestAbortControllerRef.current.abort();
    }
    setEditingStateId(st.id);
    setSuggestionError(null);
    setNewStateCode(st.state_code);
    setNewStateLabel(st.state_label || "");
    setNewWardrobe(st.wardrobe || "");
    setNewInjuries(st.injuries_and_wear || "");
    setNewExpression(st.expression_anchor || "");
    setAddStateModalOpen(true);
  };

  const handleStateCodeChange = (code: string) => {
    setNewStateCode(code);
    if (!editingStateId) {
      // In Add Mode: immediately auto-fill recommendations for the newly selected state code
      setNewWardrobe("");
      setNewInjuries("");
      setNewExpression("");
      handleFetchStateSuggestion(code, "all", false, undefined, {
        wardrobe: "",
        injuries_and_wear: "",
        expression_anchor: "",
      });
    }
  };

  const handleSaveState = async (advanceNext: boolean = false) => {
    if (!selectedChar?.id || !newWardrobe.trim()) return;
    try {
      setIsSubmittingState(true);
      const effectiveCharId = await ensurePersistedCharacter(selectedChar);

      if (editingStateId) {
        // Edit mode: update existing state
        await api.bible.updateCharacterState(effectiveCharId, editingStateId, {
          state_code: newStateCode,
          state_label: newStateLabel.trim() || undefined,
          wardrobe: newWardrobe.trim(),
          injuries_and_wear: newInjuries.trim(),
          expression_anchor: newExpression.trim(),
        });
        setAddStateModalOpen(false);
        setEditingStateId(null);
        setNewStateLabel("");
        setNewWardrobe("");
        setNewInjuries("");
        setNewExpression("");
      } else {
        // Add mode: create state
        await api.bible.createCharacterState(effectiveCharId, {
          state_code: newStateCode,
          state_label: newStateLabel.trim() || undefined,
          wardrobe: newWardrobe.trim(),
          injuries_and_wear: newInjuries.trim(),
          expression_anchor: newExpression.trim(),
        });

        if (advanceNext) {
          // Check if there is another unsaved state after this one
          const updatedMock = [...(selectedChar.states || []), { state_code: newStateCode, state_label: newStateLabel }];
          const nextCode = getNextUnsavedStateCode(updatedMock, newStateCode) || getNextUnsavedStateCode(updatedMock);
          if (nextCode) {
            setNewStateCode(nextCode);
            setNewStateLabel("");
            setNewWardrobe("");
            setNewInjuries("");
            setNewExpression("");
            onRefresh();
            // Automatically fetch recommendation for next state
            handleFetchStateSuggestion(nextCode, "all", false, undefined, {
              wardrobe: "",
              injuries_and_wear: "",
              expression_anchor: "",
            });
            return;
          }
        }
        setAddStateModalOpen(false);
        setNewStateLabel("");
        setNewWardrobe("");
        setNewInjuries("");
        setNewExpression("");
      }
      onRefresh();
    } catch (err: any) {
      console.error("Save state error:", err);
      alert(err?.message || "Gagal menyimpan state karakter.");
    } finally {
      setIsSubmittingState(false);
    }
  };

  const handleDeleteState = async (st: any) => {
    if (!selectedChar?.id || !st.id) return;
    if (!confirm(`Hapus ${st.state_code} dari ${selectedChar.name}?`)) return;
    try {
      setDeletingStateId(st.id);
      await api.bible.deleteCharacterState(selectedChar.id, st.id);
      onRefresh();
    } catch (err: any) {
      console.error("Delete state error:", err);
      alert(err?.message || "Gagal menghapus state karakter.");
    } finally {
      setDeletingStateId(null);
    }
  };

  const [copiedSeed, setCopiedSeed] = useState(false);
  const handleCopySeed = (seedVal?: number | string | null) => {
    if (!seedVal) return;
    navigator.clipboard.writeText(String(seedVal));
    setCopiedSeed(true);
    setTimeout(() => setCopiedSeed(false), 2000);
  };

  // Fetch ready-to-copy master prompts for all 7 sheets and dynamic states
  const fetchPrompts = useCallback(async (charId: string) => {
    if (!charId) return;
    try {
      setIsLoadingPrompts(true);
      const res = await api.bible.getSheetPrompts(charId);
      if (res?.data?.prompts) {
        const mergedPrompts = {
          ...res.data.prompts,
          ...(res.data.states_prompts || {}),
        };
        setSheetPrompts(mergedPrompts);
      }
    } catch (err) {
      console.warn("Failed to fetch sheet prompts:", err);
    } finally {
      setIsLoadingPrompts(false);
    }
  }, []);

  const openPromptModal = (slot: string) => {
    setActivePromptModalSlot(slot);
    setIsEditingSlotPrompt(false);
    setPromptOverrideError(null);
    setPromptDraft({ positive: "", negative: "" });
  };

  const beginPromptEdit = (slot: string) => {
    const item = sheetPrompts[slot];
    setPromptDraft({
      positive: item?.effective_prompt || item?.positive_prompt || "",
      negative: item?.effective_negative_prompt || item?.negative_prompt || "",
    });
    setPromptOverrideError(null);
    setIsEditingSlotPrompt(true);
  };

  const handleSavePromptOverride = async (slot: string) => {
    if (!projectId || !selectedChar?.id) return;
    setIsSavingPromptOverride(true);
    setPromptOverrideError(null);
    try {
      await api.bible.saveSheetOverride(projectId, selectedChar.id, slot, {
        prompt_override: promptDraft.positive.trim() || null,
        negative_prompt_override: promptDraft.negative.trim() || null,
      });
      await fetchPrompts(selectedChar.id);
      setIsEditingSlotPrompt(false);
    } catch (err: any) {
      setPromptOverrideError(err?.message || "Failed to save prompt override.");
    } finally {
      setIsSavingPromptOverride(false);
    }
  };

  const handleClearPromptOverride = async (slot: string) => {
    if (!projectId || !selectedChar?.id) return;
    setIsSavingPromptOverride(true);
    setPromptOverrideError(null);
    try {
      await api.bible.saveSheetOverride(projectId, selectedChar.id, slot, {
        prompt_override: null,
        negative_prompt_override: null,
      });
      await fetchPrompts(selectedChar.id);
      setIsEditingSlotPrompt(false);
      setPromptDraft({ positive: "", negative: "" });
    } catch (err: any) {
      setPromptOverrideError(err?.message || "Failed to clear prompt override.");
    } finally {
      setIsSavingPromptOverride(false);
    }
  };

  // In-flight active jobs rehydration on mount / character switch
  const rehydrateInFlightJobs = useCallback(
    async (charId: string) => {
      if (!charId) return;
      try {
        const res = await api.bible.getActiveJobs(charId);
        if (res?.status === "success" && Array.isArray(res.jobs) && res.jobs.length > 0) {
          for (const job of res.jobs) {
            const targetKey =
              job.target_type === "state" && job.state_id
                ? `state_${job.state_id}`
                : `${job.target_type}_${job.asset_slot}`;

            if (activePollersRef.current.has(job.job_id)) continue;

            setRenderingTargets((prev) => ({ ...prev, [targetKey]: true }));
            const startTimeMs = parseUtcTimestampMs(job.started_at || job.created_at);
            const initialElapsed = Math.max(0, Math.round((Date.now() - startTimeMs) / 1000));
            setPollStatus((prev) => ({
              ...prev,
              [targetKey]: `Google Flow sedang memproses canvas (${initialElapsed}s)...`,
            }));

            const pollTimer = setInterval(async () => {
              const elapsedSec = Math.max(0, Math.round((Date.now() - startTimeMs) / 1000));
              try {
                const j = await api.flow.getJob(job.job_id);
                if (j.status === "completed" && j.image_url) {
                  clearInterval(pollTimer);
                  activePollersRef.current.delete(job.job_id);
                  await api.bible.attachCharacterJobResult(charId, {
                    job_id: job.job_id,
                    target_type: job.target_type,
                    angle: job.asset_slot,
                    state_id: job.state_id || undefined,
                  });
                  if (onPatchCharacterAsset) {
                    onPatchCharacterAsset(charId, job.asset_slot, j.image_url);
                  }
                  setRenderingTargets((prev) => ({ ...prev, [targetKey]: false }));
                  setPollStatus((prev) => ({ ...prev, [targetKey]: "" }));
                  if (onSilentRefresh) {
                    await onSilentRefresh();
                  } else {
                    await onRefresh({ silent: true });
                  }
                  fetchPrompts(charId);
                } else if (j.status === "failed") {
                  clearInterval(pollTimer);
                  activePollersRef.current.delete(job.job_id);
                  setRenderingTargets((prev) => ({ ...prev, [targetKey]: false }));
                  setPollStatus((prev) => ({ ...prev, [targetKey]: "" }));
                  setTargetErrors((prev) => ({
                    ...prev,
                    [targetKey]: j.error_message || "Generasi Google Flow gagal.",
                  }));
                } else {
                  setPollStatus((prev) => ({
                    ...prev,
                    [targetKey]: `Google Flow sedang memproses canvas (${elapsedSec}s)...`,
                  }));
                  if (elapsedSec > 240) {
                    clearInterval(pollTimer);
                    activePollersRef.current.delete(job.job_id);
                    setRenderingTargets((prev) => ({ ...prev, [targetKey]: false }));
                    setPollStatus((prev) => ({ ...prev, [targetKey]: "" }));
                    setTargetErrors((prev) => ({
                      ...prev,
                      [targetKey]: "Waktu tunggu antrean Google Flow habis (240s).",
                    }));
                  }
                }
              } catch {
                // Polling transient error
              }
            }, 3000);

            activePollersRef.current.set(job.job_id, pollTimer);
          }
        }
      } catch (err) {
        console.warn("Failed to rehydrate active jobs:", err);
      }
    },
    [parseUtcTimestampMs, onPatchCharacterAsset, onSilentRefresh, onRefresh, fetchPrompts]
  );

  useEffect(() => {
    if (characters.length > 0) {
      const currentExists = characters.some((c) => c.id === selectedCharId);
      if (!currentExists) {
        let savedId: string | null = null;
        if (typeof window !== "undefined") {
          try {
            const urlParams = new URLSearchParams(window.location.search);
            savedId = urlParams.get("characterId") || localStorage.getItem(`movieai_active_character_${projectId}`);
          } catch {}
        }
        if (savedId && characters.some((c) => c.id === savedId)) {
          handleSelectCharacter(savedId);
        } else {
          handleSelectCharacter(characters[0].id);
        }
      } else {
        if (typeof window !== "undefined") {
          try {
            localStorage.setItem(`movieai_active_character_${projectId}`, selectedCharId);
            const url = new URL(window.location.href);
            if (url.searchParams.get("characterId") !== selectedCharId) {
              url.searchParams.set("characterId", selectedCharId);
              window.history.replaceState({}, "", url.toString());
            }
          } catch {}
        }
      }
    }
  }, [characters, selectedCharId, projectId, handleSelectCharacter]);

  useEffect(() => {
    if (selectedChar?.id) {
      fetchPrompts(selectedChar.id);
      rehydrateInFlightJobs(selectedChar.id);
    }
  }, [selectedChar?.id, fetchPrompts, rehydrateInFlightJobs]);

  // Resilient Mobile Clipboard Helper (Fallback to textarea execCommand if navigator.clipboard restricted)
  const copyTextToClipboard = async (text: string, identifier?: string) => {
    if (!text) return false;
    let success = false;
    if (typeof navigator !== "undefined" && navigator.clipboard && navigator.clipboard.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        success = true;
      } catch {
        // Fallback below
      }
    }
    if (!success && typeof document !== "undefined") {
      try {
        const el = document.createElement("textarea");
        el.value = text;
        el.setAttribute("readonly", "");
        el.style.position = "fixed";
        el.style.opacity = "0";
        document.body.appendChild(el);
        el.focus();
        el.select();
        success = document.execCommand("copy");
        document.body.removeChild(el);
      } catch (err) {
        console.error("Clipboard copy failed:", err);
      }
    }
    if (success && identifier) {
      setCopiedPromptSlot(identifier);
      setTimeout(() => setCopiedPromptSlot((curr) => (curr === identifier ? null : curr)), 2000);
    }
    return success;
  };

  // Per-Card Manual Photo Upload / Replace Handler
  const handleUploadSheet = async (slot: string, file: File) => {
    if (!selectedChar?.id || !file) return;
    if (file.size > 20 * 1024 * 1024) {
      setUploadErrors((prev) => ({
        ...prev,
        [slot]: "File exceeds maximum 20MB limit.",
      }));
      return;
    }
    setUploadingSlots((prev) => ({ ...prev, [slot]: true }));
    setUploadErrors((prev) => ({ ...prev, [slot]: null }));
    try {
      const effectiveCharId = await ensurePersistedCharacter(selectedChar);
      await api.bible.uploadCharacterSheet(effectiveCharId, slot, file);
      onRefresh();
      fetchPrompts(effectiveCharId);
    } catch (err: any) {
      console.error("Upload sheet error:", err);
      setUploadErrors((prev) => ({
        ...prev,
        [slot]: err?.message || "Gagal mengunggah foto aset.",
      }));
    } finally {
      setUploadingSlots((prev) => ({ ...prev, [slot]: false }));
    }
  };

  // Render Visual Asset for Character Turnaround, 7-Sheet, or State
  const handleRenderAsset = async (
    targetType: "turnaround" | "sheet" | "state" | string,
    angle: "front" | "side" | "three_quarter" | "back" | "tpose" | "action" | "expression" | string = "closeup",
    stateId?: string,
    options?: { skipRefresh?: boolean; targetChar?: Character }
  ): Promise<boolean> => {
    const activeChar = options?.targetChar ?? selectedChar;
    if (!activeChar?.id) return false;

    // Strict batch guard for user-initiated clicks
    if (isBatchActive && !options?.targetChar) {
      showBatchLockNotification(targetType === "state" ? "Render Visual State" : `Render ${angle || "Asset"}`);
      return false;
    }

    const targetKey = targetType === "state" ? `state_${stateId}` : `${targetType}_${angle}`;
    setRenderingTargets((prev) => ({ ...prev, [targetKey]: true }));
    setTargetErrors((prev) => ({ ...prev, [targetKey]: null }));

    try {
      setPollStatus((prev) => ({
        ...prev,
        [targetKey]: "Menyiapkan karakter di database...",
      }));

      const effectiveCharId = await ensurePersistedCharacter(activeChar);

      setPollStatus((prev) => ({
        ...prev,
        [targetKey]:
          isGoogleFlowProvider(selectedProvider)
            ? "Mengirim job ke antrean Google Flow (Visual Anchoring)..."
            : selectedProvider === "ag_gemini_flash"
            ? "Merender dengan AG/Gemini 3.8 Flash (Seed Locked)..."
            : `Merender gambar via ${resolveProviderDisplayInfo(selectedProvider, selectedModel).label}...`,
      }));

      const aspect_ratio =
        angle === "expression" ? "16:9" : targetType === "state" || angle === "closeup" ? "1:1" : "3:4";

      const res = await api.bible.generateCharacterAsset(effectiveCharId, {
        target_type: targetType,
        angle,
        state_id: stateId,
        provider: selectedProvider,
        model: selectedModel || undefined,
        aspect_ratio,
      });

      // Synchronous Response (AG/Gemini 3.8 Flash, 9Router, SD 3.5 Large)
      if (res.status === "completed" && res.image_url) {
        if (targetType === "state") {
          if (stateId && onPatchCharacterStateAsset) {
            onPatchCharacterStateAsset(effectiveCharId, stateId, res.image_url);
          }
        } else {
          if (onPatchCharacterAsset) {
            onPatchCharacterAsset(effectiveCharId, angle, res.image_url);
          }
        }
        // Update in-memory workingChar immediately so subsequent cards/states see fresh anchor
        if (options?.targetChar) {
          if (targetType === "state" && stateId) {
            const stObj = options.targetChar.states?.find((s: any) => s.id === stateId);
            if (stObj) stObj.image_url = res.image_url;
          } else if (angle) {
            const keyMap: Record<string, string> = {
              closeup: "closeup_image_url",
              expression: "expression_image_url",
              front: "front_image_url",
              side: "side_image_url",
              three_quarter: "three_quarter_image_url",
              back: "back_image_url",
              tpose: "tpose_image_url",
              action: "action_image_url",
            };
            const field = keyMap[angle];
            if (field) (options.targetChar as any)[field] = res.image_url;
          }
        }
        setRenderingTargets((prev) => ({ ...prev, [targetKey]: false }));
        setPollStatus((prev) => ({ ...prev, [targetKey]: "" }));
        if (!options?.skipRefresh) {
          if (onSilentRefresh) {
            await onSilentRefresh();
          } else {
            await onRefresh({ silent: true });
          }
          if (activeChar.id === selectedChar?.id) {
            await fetchPrompts(effectiveCharId);
          }
        }
        return true;
      }

      // Asynchronous Response (Google Flow Worker with Long Polling)
      if (res.status === "queued" && res.job_id) {
        const jobId = res.job_id;
        let pollCount = 0;
        const renderStartTime = Date.now();
        setPollStatus((prev) => ({
          ...prev,
          [targetKey]: "Menunggu giliran worker Google Flow di server...",
        }));

        return new Promise<boolean>((resolve) => {
          const pollInterval = setInterval(async () => {
            pollCount++;
            const elapsedSec = Math.round((Date.now() - renderStartTime) / 1000);
            try {
              const job = await api.flow.getJob(jobId);
              if (job.status === "completed" && job.image_url) {
                clearInterval(pollInterval);
                activePollersRef.current.delete(jobId);
                // Attach job result persistently into SQLite database
                await api.bible.attachCharacterJobResult(effectiveCharId, {
                  job_id: jobId,
                  target_type: targetType,
                  angle,
                  state_id: stateId,
                });
                if (targetType === "state") {
                  if (stateId && onPatchCharacterStateAsset) {
                    onPatchCharacterStateAsset(effectiveCharId, stateId, job.image_url);
                  }
                } else {
                  if (onPatchCharacterAsset) {
                    onPatchCharacterAsset(effectiveCharId, angle, job.image_url);
                  }
                }
                // Update in-memory workingChar immediately so subsequent cards/states see fresh anchor
                if (options?.targetChar) {
                  if (targetType === "state" && stateId) {
                    const stObj = options.targetChar.states?.find((s: any) => s.id === stateId);
                    if (stObj) stObj.image_url = job.image_url;
                  } else if (angle) {
                    const keyMap: Record<string, string> = {
                      closeup: "closeup_image_url",
                      expression: "expression_image_url",
                      front: "front_image_url",
                      side: "side_image_url",
                      three_quarter: "three_quarter_image_url",
                      back: "back_image_url",
                      tpose: "tpose_image_url",
                      action: "action_image_url",
                    };
                    const field = keyMap[angle];
                    if (field) (options.targetChar as any)[field] = job.image_url;
                  }
                }
                setRenderingTargets((prev) => ({ ...prev, [targetKey]: false }));
                setPollStatus((prev) => ({ ...prev, [targetKey]: "" }));
                if (!options?.skipRefresh) {
                  if (onSilentRefresh) {
                    await onSilentRefresh();
                  } else {
                    await onRefresh({ silent: true });
                  }
                  if (activeChar.id === selectedChar?.id) {
                    await fetchPrompts(effectiveCharId);
                  }
                }
                resolve(true);
              } else if (job.status === "failed") {
                clearInterval(pollInterval);
                activePollersRef.current.delete(jobId);
                setRenderingTargets((prev) => ({ ...prev, [targetKey]: false }));
                setPollStatus((prev) => ({ ...prev, [targetKey]: "" }));
                const jErr = job.error_message || "Generasi Google Flow gagal.";
                if (isProxyOfflineError(jErr)) {
                  setProxyOfflineAlert({
                    isOpen: true,
                    message: "Proxy SOCKS5 Android Offline saat render visual",
                    detail: "Koneksi tunnel HP Android (127.0.0.1:10808) terputus saat render.",
                  });
                  setTargetErrors((prev) => ({
                    ...prev,
                    [targetKey]: "SOCKS5 Proxy Offline: Pastikan reverse tunnel Android aktif.",
                  }));
                } else {
                  setTargetErrors((prev) => ({
                    ...prev,
                    [targetKey]: jErr,
                  }));
                }
                resolve(false);
              } else {
                setPollStatus((prev) => ({
                  ...prev,
                  [targetKey]: `Google Flow sedang memproses canvas (${elapsedSec}s)...`,
                }));
                if (elapsedSec > 240 || pollCount > 80) {
                  // 240 seconds maximum timeout threshold
                  clearInterval(pollInterval);
                  activePollersRef.current.delete(jobId);
                  // Anti-Zombie: Cancel job on backend to release Flow account immediately
                  try {
                    await api.flow.cancelJob(jobId);
                  } catch (cErr) {
                    console.warn(`[handleRenderAsset] Error cancelling timed out job ${jobId}:`, cErr);
                  }
                  setRenderingTargets((prev) => ({ ...prev, [targetKey]: false }));
                  setPollStatus((prev) => ({ ...prev, [targetKey]: "" }));
                  setTargetErrors((prev) => ({
                    ...prev,
                    [targetKey]: "Waktu tunggu antrean Google Flow habis (240s).",
                  }));
                  resolve(false);
                }
              }
            } catch (pollErr: any) {
              clearInterval(pollInterval);
              activePollersRef.current.delete(jobId);
              setRenderingTargets((prev) => ({ ...prev, [targetKey]: false }));
              setPollStatus((prev) => ({ ...prev, [targetKey]: "" }));
              setTargetErrors((prev) => ({
                ...prev,
                [targetKey]: pollErr?.message || "Gagal memeriksa status job Flow.",
              }));
              resolve(false);
            }
          }, 3000);
          activePollersRef.current.set(jobId, pollInterval);
        });
      }
      return false;
    } catch (err: any) {
      console.error("Render asset error:", err);
      setRenderingTargets((prev) => ({ ...prev, [targetKey]: false }));
      setPollStatus((prev) => ({ ...prev, [targetKey]: "" }));
      if (isProxyOfflineError(err)) {
        const detailStr =
          typeof err?.message === "string" && err.message !== "[object Object]"
            ? err.message
            : (typeof err?.detail === "string"
                ? err.detail
                : (typeof err?.detail?.message === "string"
                    ? err.detail.message
                    : "Koneksi tunnel HP Android (127.0.0.1:10808) offline."));
        setProxyOfflineAlert({
          isOpen: true,
          message: "Proxy SOCKS5 Android Offline saat memulai render Google Flow",
          detail: detailStr,
        });
        setTargetErrors((prev) => ({
          ...prev,
          [targetKey]: "SOCKS5 Proxy Offline: Pastikan reverse tunnel Android aktif.",
        }));
      } else {
        const rawErr = err?.response?.data?.detail || err?.response?.data?.error?.message || err?.message || err;
        const errMsg =
          typeof rawErr === "string" && rawErr !== "[object Object]"
            ? rawErr
            : (typeof rawErr?.message === "string" && rawErr.message !== "[object Object]"
                ? rawErr.message
                : (typeof rawErr?.detail === "string"
                    ? rawErr.detail
                    : JSON.stringify(rawErr)));
        setTargetErrors((prev) => ({
          ...prev,
          [targetKey]: errMsg || "Gagal melakukan render gambar aset.",
        }));
      }
      return false;
    }
  };

  // Reusable Downstream Pipeline Runner (Strictly Cards 2–8 + Dynamic States)
  // Strict Card 1 Protection: Card 1 (Master Anchor) is read-only input anchor and NEVER modified.
  const executeDownstreamForCharacter = async (
    targetChar: Character,
    resumeMode: boolean,
    onStepProgress: (text: string, currentStep: number, totalSteps: number) => void,
    abortRef: React.MutableRefObject<boolean>
  ): Promise<{ success: boolean; error?: string }> => {
    if (!targetChar?.closeup_image_url) {
      return {
        success: false,
        error: "Card 1: Character Close-Up (Master Anchor) belum tersedia.",
      };
    }

    const workingChar: Character = { ...targetChar };
    const statesList = workingChar.states || [];
    const totalSteps = 7 + statesList.length; // 7 Cards (Cards 2-8) + N Dynamic States
    let currentStep = 0;
    const failedSlots: string[] = [];

    try {
      // ==========================================
      // PHASE 1: Card 2 & Card 3 (Anchored to Card 1)
      // ==========================================
      let card2Ok = false;
      let card3Ok = false;

      // Card 2: Expression Sheet
      const card2AlreadyDone = resumeMode && !!workingChar.expression_image_url;
      let card2Promise: Promise<boolean>;
      if (card2AlreadyDone) {
        card2Ok = true;
        currentStep++;
        onStepProgress(`[Step ${currentStep}/${totalSteps}] Card 2 (Expression Sheet) sudah ada, dilewati (Resume Mode)`, currentStep, totalSteps);
        card2Promise = Promise.resolve(true);
      } else {
        currentStep++;
        onStepProgress(`[Step ${currentStep}/${totalSteps}] Merender Card 2 (Expression Sheet)...`, currentStep, totalSteps);
        card2Promise = handleRenderAsset("sheet", "expression", undefined, { skipRefresh: true, targetChar: workingChar });
      }

      // Card 3: Full Body Front (Anchored to Card 1)
      const card3AlreadyDone = resumeMode && !!workingChar.front_image_url;
      let card3Promise: Promise<boolean>;
      if (card3AlreadyDone) {
        card3Ok = true;
        currentStep++;
        onStepProgress(`[Step ${currentStep}/${totalSteps}] Card 3 (Full Body Front) sudah ada, dilewati (Resume Mode)`, currentStep, totalSteps);
        card3Promise = Promise.resolve(true);
      } else {
        card3Promise = new Promise<boolean>((resolve) => {
          setTimeout(async () => {
            if (abortRef.current) {
              resolve(false);
              return;
            }
            let success = await handleRenderAsset("turnaround", "front", undefined, { skipRefresh: true, targetChar: workingChar });
            if (!success && !abortRef.current) {
              // Guardrail: 1 auto-retry on transient failure for Card 3
              console.warn("Card 3 (Full Body Front) failed on first attempt. Retrying once (auto-retry)...");
              onStepProgress(`[Step 2/${totalSteps}] Card 3 mencoba ulang (1x auto-retry)...`, 2, totalSteps);
              await new Promise((r) => setTimeout(r, 1500));
              if (!abortRef.current) {
                success = await handleRenderAsset("turnaround", "front", undefined, { skipRefresh: true, targetChar: workingChar });
              }
            }
            resolve(success);
          }, 500);
        });
      }

      const [p1Card2Result, p1Card3Result] = await Promise.all([card2Promise, card3Promise]);
      card2Ok = card2AlreadyDone || p1Card2Result;
      card3Ok = card3AlreadyDone || p1Card3Result;

      if (!card2Ok) {
        failedSlots.push("Card 2: Expression Sheet");
      }

      if (abortRef.current) {
        onStepProgress("Pipeline dihentikan oleh pengguna. Aset yang telah selesai tetap tersimpan.", currentStep, totalSteps);
        return { success: false, error: "Dihentikan oleh pengguna" };
      }

      if (!card3Ok) {
        failedSlots.push("Card 3: Full Body Front");
        console.warn("Phase 1 halted: Card 3 (Full Body Front) failed. Preserving Card 2 and halting Phase 2 & 3.");
        onStepProgress("Phase 2 & 3 dihentikan karena Card 3 (Full Body Front) gagal. Hasil Card 2 tetap tersimpan.", currentStep, totalSteps);
        return { success: false, error: "Card 3 (Full Body Front) gagal dirender." };
      }

      // ==========================================
      // PHASE 2: Cards 4-8 (Anchors: Card 1 + Card 3)
      // ==========================================
      const phase2Cards = [
        { slot: "side", targetType: "turnaround" as const, name: "Card 4: Side Profile", key: "side_image_url" as const },
        { slot: "three_quarter", targetType: "turnaround" as const, name: "Card 5: 3/4 Hero Angle", key: "three_quarter_image_url" as const },
        { slot: "back", targetType: "turnaround" as const, name: "Card 6: Back View", key: "back_image_url" as const },
        { slot: "tpose", targetType: "sheet" as const, name: "Card 7: T-Pose Sheet", key: "tpose_image_url" as const },
        { slot: "action", targetType: "sheet" as const, name: "Card 8: Dynamic Action", key: "action_image_url" as const },
      ];

      for (const item of phase2Cards) {
        if (abortRef.current) {
          onStepProgress("Pipeline dihentikan oleh pengguna. Aset yang telah selesai tetap tersimpan.", currentStep, totalSteps);
          return { success: false, error: "Dihentikan oleh pengguna" };
        }
        currentStep++;
        if (resumeMode && (workingChar as any)[item.key]) {
          onStepProgress(`[Step ${currentStep}/${totalSteps}] ${item.name} sudah ada, dilewati (Resume Mode)`, currentStep, totalSteps);
          continue;
        }
        onStepProgress(`[Step ${currentStep}/${totalSteps}] Merender ${item.name}...`, currentStep, totalSteps);
        const ok = await handleRenderAsset(item.targetType, item.slot, undefined, { skipRefresh: true, targetChar: workingChar });
        if (!ok) {
          failedSlots.push(item.name);
        }
      }

      if (abortRef.current) {
        return { success: false, error: "Dihentikan oleh pengguna" };
      }

      // ==========================================
      // PHASE 3: Dynamic States (Anchors: Card 1 + Card 3)
      // ==========================================
      if (card3Ok && statesList.length > 0) {
        for (const st of statesList) {
          if (abortRef.current) {
            onStepProgress("Pipeline dihentikan oleh pengguna. Aset yang telah selesai tetap tersimpan.", currentStep, totalSteps);
            return { success: false, error: "Dihentikan oleh pengguna" };
          }
          currentStep++;
          const label = st.state_label || st.state_code;
          if (resumeMode && st.image_url) {
            onStepProgress(`[Step ${currentStep}/${totalSteps}] State ${st.state_code} (${label}) sudah ada, dilewati (Resume Mode)`, currentStep, totalSteps);
            continue;
          }
          onStepProgress(`[Step ${currentStep}/${totalSteps}] Merender State ${st.state_code} (${label})...`, currentStep, totalSteps);
          const ok = await handleRenderAsset("state", undefined, st.id, { skipRefresh: true, targetChar: workingChar });
          if (!ok) {
            failedSlots.push(`State ${st.state_code} (${label})`);
          }
        }
      } else if (!card3Ok && statesList.length > 0) {
        onStepProgress("Phase 3 dilewati karena Card 3 (Full Body Front) belum siap.", currentStep, totalSteps);
      }

      if (failedSlots.length > 0) {
        return {
          success: false,
          error: `Gagal pada ${failedSlots.length} slot: ${failedSlots.join(", ")}`,
        };
      }

      return { success: true };
    } catch (err: any) {
      console.error(`Downstream error for ${targetChar.name}:`, err);
      return { success: false, error: err?.message || "Render aset downstream gagal." };
    }
  };

  // One-Click Retry Failed / Missing Only for Single Character
  const handleRetryFailedOnly = async (targetChar?: Character) => {
    const charToRun = targetChar || selectedChar;
    if (!charToRun?.closeup_image_url || isLocked || isRegeneratingAllDownstream || isBatchGenerating) return;

    if (isGoogleFlowProvider(selectedProvider)) {
      const pStatus = await handleCheckProxy();
      if (!pStatus.healthy) {
        setProxyOfflineAlert({
          isOpen: true,
          message: "Retry Failed / Missing Dibatalkan (SOCKS5 Proxy Offline)",
          detail: pStatus.detail || "Koneksi reverse tunnel HP Android (127.0.0.1:10808) tidak aktif.",
        });
        return;
      }
    }

    setIsRegeneratingAllDownstream(true);
    setIsStoppingDownstream(false);
    abortDownstreamRef.current = false;

    try {
      await executeDownstreamForCharacter(
        charToRun,
        true, // Resume mode: skip completed cards, only process missing/failed!
        (msg) => setDownstreamProgressText(msg),
        abortDownstreamRef
      );
    } catch (err: any) {
      console.error("Retry failed downstream error:", err);
    } finally {
      setDownstreamProgressText(null);
      setIsStoppingDownstream(false);
      setIsRegeneratingAllDownstream(false);
      if (onSilentRefresh) {
        await onSilentRefresh();
      } else {
        await onRefresh({ silent: true });
      }
      if (charToRun?.id) fetchPrompts(charToRun.id);
    }
  };

  // One-Click Full Downstream Pipeline for Single Character (Cards 2–8 + Dynamic States)
  const handleRegenerateAllDownstream = async () => {
    if (!selectedChar?.closeup_image_url || isLocked || isRegeneratingAllDownstream || isBatchGenerating) return;

    // Pre-flight check: batalkan langsung jika SOCKS5 proxy sedang offline
    if (isGoogleFlowProvider(selectedProvider)) {
      const pStatus = await handleCheckProxy();
      if (!pStatus.healthy) {
        setProxyOfflineAlert({
          isOpen: true,
          message: "Regenerate All Downstream Dibatalkan (SOCKS5 Proxy Offline)",
          detail: pStatus.detail || "Koneksi reverse tunnel HP Android (127.0.0.1:10808) tidak aktif.",
        });
        return;
      }
    }

    setIsRegeneratingAllDownstream(true);
    setIsStoppingDownstream(false);
    abortDownstreamRef.current = false;

    try {
      await executeDownstreamForCharacter(
        selectedChar,
        false, // Explicit single-character button re-renders all downstream
        (msg) => setDownstreamProgressText(msg),
        abortDownstreamRef
      );
    } catch (err: any) {
      console.error("Downstream generation error:", err);
    } finally {
      setDownstreamProgressText(null);
      setIsStoppingDownstream(false);
      setIsRegeneratingAllDownstream(false);
      if (onSilentRefresh) {
        await onSilentRefresh();
      } else {
        await onRefresh({ silent: true });
      }
      if (selectedChar?.id) fetchPrompts(selectedChar.id);
    }
  };

  // Helper to estimate asset count for batch downstream generation
  const calculateEstimatedAssets = (resume: boolean) => {
    const readyChars = characters.filter(
      (c) => c.closeup_image_url && c.closeup_image_url.trim().length > 0
    );
    let toRender = 0;
    let alreadyExists = 0;

    readyChars.forEach((c) => {
      const slots = [
        c.expression_image_url,
        c.front_image_url,
        c.side_image_url,
        c.three_quarter_image_url,
        c.back_image_url,
        c.tpose_image_url,
        c.action_image_url,
      ];
      slots.forEach((url) => {
        if (url) alreadyExists++;
        else toRender++;
      });
      const states = c.states || [];
      if (states.length > 0) {
        states.forEach((st) => {
          if (st.image_url) alreadyExists++;
          else toRender++;
        });
      } else {
        toRender += 5;
      }
    });

    if (!resume) {
      return {
        toRender: toRender + alreadyExists,
        alreadyExists: 0,
      };
    }
    return { toRender, alreadyExists };
  };

  // Open Batch Pre-Flight Check Modal
  const handleOpenBatchModal = async () => {
    if (isLocked || isBatchGenerating) return;
    if (isGoogleFlowProvider(selectedProvider)) {
      await handleCheckProxy();
    }
    setBatchPreflightModalOpen(true);
  };

  // Sequential Batch Orchestrator for All Ready Characters
  const handleStartBatchDownstream = async () => {
    if (isLocked || isBatchGenerating) return;

    const readyChars = characters.filter(
      (c) => c.closeup_image_url && c.closeup_image_url.trim().length > 0
    );
    const skippedChars = characters.filter(
      (c) => !c.closeup_image_url || !c.closeup_image_url.trim().length
    );

    if (readyChars.length === 0) return;

    if (isGoogleFlowProvider(selectedProvider)) {
      const pStatus = await handleCheckProxy();
      if (!pStatus.healthy) {
        setProxyOfflineAlert({
          isOpen: true,
          message: "Batch Downstream Dibatalkan (SOCKS5 Proxy Offline)",
          detail: pStatus.detail || "Koneksi reverse tunnel HP Android (127.0.0.1:10808) tidak aktif.",
        });
        return;
      }
    }

    setBatchPreflightModalOpen(false);
    setIsBatchGenerating(true);
    setIsStoppingBatch(false);
    abortBatchRef.current = false;

    // Mobile Wake Lock to prevent screen sleep / background throttling
    await requestWakeLock();

    // Prevent accidental page close or navigation during active batch
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "Batch Downstream Generation sedang berlangsung. Yakin ingin keluar?";
      return e.returnValue;
    };
    window.addEventListener("beforeunload", handleBeforeUnload);

    const successfulChars: string[] = [];
    const failedChars: { name: string; role: string; error: string }[] = [];

    try {
      for (let i = 0; i < readyChars.length; i++) {
        if (abortBatchRef.current) break;

        const char = readyChars[i];

        // Automatically switch view to the character currently being processed
        handleSelectCharacter(char.id);

        setBatchProgress({
          currentCharIdx: i + 1,
          totalReady: readyChars.length,
          charName: char.name,
          currentStep: 0,
          totalSteps: 7 + (char.states?.length || 5),
          stepText: "Memulai downstream pipeline...",
        });

        const res = await executeDownstreamForCharacter(
          char,
          batchResumeMode,
          (stepText, currentStep, totalSteps) => {
            setBatchProgress({
              currentCharIdx: i + 1,
              totalReady: readyChars.length,
              charName: char.name,
              currentStep,
              totalSteps,
              stepText,
            });
          },
          abortBatchRef
        );

        if (res.success) {
          successfulChars.push(char.name);
        } else if (!abortBatchRef.current) {
          failedChars.push({
            name: char.name,
            role: char.role,
            error: res.error || "Gagal menghasilkan aset downstream.",
          });
        }

        // Silent refresh after each character to sync database state
        if (onSilentRefresh) {
          await onSilentRefresh();
        } else {
          await onRefresh({ silent: true });
        }
      }
    } catch (err: any) {
      console.error("Batch downstream unexpected error:", err);
    } finally {
      window.removeEventListener("beforeunload", handleBeforeUnload);
      await releaseWakeLock();

      setIsBatchGenerating(false);
      setIsStoppingBatch(false);
      setBatchProgress(null);

      // Open Summary Modal
      setBatchSummaryData({
        total: characters.length,
        readyCount: readyChars.length,
        successCount: successfulChars.length,
        skippedChars: skippedChars.map((c) => ({
          name: c.name,
          role: c.role,
          reason: "Belum memiliki Card 1: Character Close-Up (Master Anchor)",
        })),
        failedChars,
        wasCancelled: abortBatchRef.current,
      });
      setBatchSummaryModalOpen(true);

      if (onSilentRefresh) {
        await onSilentRefresh();
      } else {
        await onRefresh({ silent: true });
      }
      if (selectedChar?.id) fetchPrompts(selectedChar.id);
    }
  };

  const handleStopBatch = () => {
    setIsStoppingBatch(true);
    abortBatchRef.current = true;
    if (batchProgress) {
      setBatchProgress((prev) =>
        prev ? { ...prev, stepText: "Menghentikan batch setelah aset aktif selesai..." } : null
      );
    }
  };

  const handleUpscaleAsset = async (slotKey: string, stateId?: string) => {
    if (!selectedChar?.id || isLocked) return;
    if (isBatchActive) {
      showBatchLockNotification(stateId ? "Upscale 2K Dynamic State" : `Upscale 2K (${slotKey})`);
      return;
    }
    const lockKey = stateId ? `state_${stateId}` : slotKey;
    if (upscalingSlots[lockKey]) return;

    setUpscalingSlots((prev) => ({ ...prev, [lockKey]: true }));
    setUpscaleErrors((prev) => ({ ...prev, [lockKey]: null }));
    try {
      const res = await api.bible.upscaleCharacterAsset(selectedChar.id, {
        slot_key: stateId ? "state" : slotKey,
        state_id: stateId,
      });
      const patchMeta = {
        resolution_width: res.resolution_width,
        resolution_height: res.resolution_height,
        width: res.resolution_width,
        height: res.resolution_height,
        is_2k: res.is_2k,
        previous_1k_url: res.previous_1k_url ?? null,
        provider: res.provider,
        model: res.model,
      };
      if (stateId) {
        onPatchCharacterStateAsset?.(selectedChar.id, stateId, res.image_url, patchMeta);
      } else {
        onPatchCharacterAsset?.(selectedChar.id, slotKey, res.image_url, patchMeta);
      }
      if (res.is_2k) {
        showUpscaleToast(
          "Upscale 2K Selesai",
          `Upscaled to ${res.resolution_width}×${res.resolution_height} (2K)${res.auto_routed_from ? ` via ${res.provider}` : ""}`
        );
      } else {
        showUpscaleToast(
          "Resolusi Di Bawah 2K",
          `Provider mengembalikan ${res.resolution_width}×${res.resolution_height} (< 1920px). Tidak dilabeli 2K.`,
          true
        );
      }
      if (onSilentRefresh) {
        await onSilentRefresh();
      } else {
        await onRefresh({ silent: true });
      }
      await fetchPrompts(selectedChar.id);
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail?.message ||
        err?.response?.data?.detail ||
        err?.message ||
        "Gagal melakukan Upscale 2K.";
      setUpscaleErrors((prev) => ({ ...prev, [lockKey]: String(msg) }));
      showUpscaleToast("Upscale 2K Gagal", String(msg), true);
    } finally {
      setUpscalingSlots((prev) => ({ ...prev, [lockKey]: false }));
    }
  };

  const handleRevertAsset = async (slotKey: string, stateId?: string) => {
    if (!selectedChar?.id || isLocked) return;
    if (isBatchActive) {
      showBatchLockNotification(stateId ? "Revert 1K State" : `Revert 1K (${slotKey})`);
      return;
    }
    const lockKey = stateId ? `state_${stateId}` : slotKey;
    if (upscalingSlots[lockKey]) return;

    setUpscalingSlots((prev) => ({ ...prev, [lockKey]: true }));
    setUpscaleErrors((prev) => ({ ...prev, [lockKey]: null }));
    try {
      const res = await api.bible.revertCharacterAsset(selectedChar.id, {
        slot_key: stateId ? "state" : slotKey,
        state_id: stateId,
      });
      const patchMeta = {
        resolution_width: res.resolution_width,
        resolution_height: res.resolution_height,
        width: res.resolution_width,
        height: res.resolution_height,
        is_2k: res.is_2k,
        previous_1k_url: null,
      };
      if (stateId) {
        onPatchCharacterStateAsset?.(selectedChar.id, stateId, res.image_url, patchMeta);
      } else {
        onPatchCharacterAsset?.(selectedChar.id, slotKey, res.image_url, patchMeta);
      }
      showUpscaleToast(
        "Dikembalikan ke 1K",
        `Reverted to ${res.resolution_width}×${res.resolution_height} (1K)`
      );
      if (onSilentRefresh) {
        await onSilentRefresh();
      } else {
        await onRefresh({ silent: true });
      }
    } catch (err: any) {
      const msg = err?.message || "Gagal mengembalikan ke versi 1K.";
      setUpscaleErrors((prev) => ({ ...prev, [lockKey]: String(msg) }));
      showUpscaleToast("Revert 1K Gagal", String(msg), true);
    } finally {
      setUpscalingSlots((prev) => ({ ...prev, [lockKey]: false }));
    }
  };

  const handleUpscalePreview = async (slot: "closeup" | "expression" | "front") => {
    if (!previewToken) return;
    const lockKey = `preview_${slot}`;
    if (upscalingSlots[lockKey] || isPreviewGenerating) return;
    setUpscalingSlots((prev) => ({ ...prev, [lockKey]: true }));
    setPreviewError(null);
    setPreviewErrorMsg(null);
    try {
      const res = await api.bible.upscaleCharacterPreview(projectId, {
        preview_token: previewToken,
        slot,
        name: newCharName.trim() || "Character",
        role: newCharRole,
        base_visual_prompt: newCharPrompt.trim(),
        dna_seed: newCharSeed,
      });
      if (slot === "closeup") setPreviewCloseupUrl(res.image_url);
      else if (slot === "expression") setPreviewExpressionUrl(res.image_url);
      else setPreviewFrontUrl(res.image_url);
      setPreviewSlotMeta((prev) => ({
        ...prev,
        [slot]: {
          resolution_width: res.resolution_width,
          resolution_height: res.resolution_height,
          is_2k: res.is_2k,
          previous_1k_url: res.previous_1k_url ?? null,
        },
      }));
      showUpscaleToast(
        res.is_2k ? "Preview Upscale 2K Selesai" : "Resolusi Di Bawah 2K",
        res.is_2k
          ? `Upscaled to ${res.resolution_width}×${res.resolution_height} (2K)`
          : `Provider mengembalikan ${res.resolution_width}×${res.resolution_height} (< 1920px).`,
        !res.is_2k
      );
    } catch (err: any) {
      const msg = err?.message || "Gagal upscale preview ke 2K.";
      setPreviewError(msg);
      setPreviewErrorMsg(msg);
    } finally {
      setUpscalingSlots((prev) => ({ ...prev, [lockKey]: false }));
    }
  };

  const handleRevertPreview = async (slot: "closeup" | "expression" | "front") => {
    if (!previewToken) return;
    const lockKey = `preview_${slot}`;
    if (upscalingSlots[lockKey]) return;
    setUpscalingSlots((prev) => ({ ...prev, [lockKey]: true }));
    try {
      const res = await api.bible.revertCharacterPreview(projectId, {
        preview_token: previewToken,
        slot,
      });
      if (slot === "closeup") setPreviewCloseupUrl(res.image_url);
      else if (slot === "expression") setPreviewExpressionUrl(res.image_url);
      else setPreviewFrontUrl(res.image_url);
      setPreviewSlotMeta((prev) => ({
        ...prev,
        [slot]: {
          resolution_width: res.resolution_width,
          resolution_height: res.resolution_height,
          is_2k: res.is_2k,
          previous_1k_url: null,
        },
      }));
      showUpscaleToast("Preview Dikembalikan ke 1K", `Reverted to ${res.resolution_width}×${res.resolution_height}`);
    } catch (err: any) {
      const msg = err?.message || "Gagal revert preview ke 1K.";
      setPreviewError(msg);
      setPreviewErrorMsg(msg);
    } finally {
      setUpscalingSlots((prev) => ({ ...prev, [lockKey]: false }));
    }
  };

  // Render Matrix Card for Turnaround & Rigging/Action/Expression Sheets
  const renderMatrixCard = (cfg: {
    slot: "closeup" | "front" | "side" | "three_quarter" | "back" | "tpose" | "action" | "expression";
    title: string;
    targetType: "turnaround" | "sheet";
    aspect: "3:4" | "16:9" | "1:1";
    imageUrl: string | null | undefined;
    subtitle: string;
    anchorBadge: string;
    isMasterAnchor?: boolean;
  }) => {
    const targetKey = `${cfg.targetType}_${cfg.slot}`;
    const isRendering = !!renderingTargets[targetKey];
    const isUploading = !!uploadingSlots[cfg.slot];
    const isUpscaling = !!upscalingSlots[cfg.slot];
    const statusText = pollStatus[targetKey];
    const errorMsg = upscaleErrors[cfg.slot] || uploadErrors[cfg.slot] || targetErrors[targetKey];
    const imageUrl = cfg.imageUrl;
    const promptItem = sheetPrompts[cfg.slot];
    const meta = selectedChar?.sheet_metadata?.[cfg.slot];
    const isUploaded = meta?.source === "manual_upload";
    const resW = meta?.resolution_width ?? meta?.width;
    const resH = meta?.resolution_height ?? meta?.height;
    const is2k = !!meta?.is_2k || (!!resW && !!resH && Math.max(resW, resH) >= 1920);
    const hasPrev1k = !!meta?.previous_1k_url;
    const resBadgeLabel = is2k
      ? `2K • ${resW || 2048}×${resH || 2048}`
      : resW && resH
      ? `1K • ${resW}×${resH}`
      : cfg.aspect === "16:9"
      ? "1K • 1344×768"
      : cfg.aspect === "1:1"
      ? "1K • 1024×1024"
      : "1K • 768×1024";

    return (
      <div
        key={cfg.slot}
        className="rounded-xl bg-canvas border border-border p-3 flex flex-col justify-between relative overflow-hidden group shadow-sm hover:border-amber-500/40 transition-all gap-2"
      >
        {/* Hidden File Input with accept image/*,.heic,.heif and immediate value reset for mobile re-upload */}
        <input
          type="file"
          id={`upload-sheet-${cfg.slot}`}
          className="hidden"
          accept="image/*,.heic,.heif"
          onChange={(e) => {
            const f = e.target.files?.[0];
            e.target.value = "";
            if (f) handleUploadSheet(cfg.slot, f);
          }}
        />

        {/* Card Header */}
        <div className="relative z-20 flex justify-between items-center text-[10px] font-mono gap-1">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="px-2 py-0.5 rounded bg-black/80 text-amber-400 font-bold border border-border shadow-sm">
              {cfg.title}
            </span>
            <span
              className={cn(
                "px-1.5 py-0.2 rounded text-[9px] font-semibold border",
                cfg.isMasterAnchor
                  ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
                  : isGoogleFlowProvider(selectedProvider)
                  ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                  : "bg-blue-500/15 text-blue-400 border-blue-500/30"
              )}
            >
              {cfg.anchorBadge}
            </span>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            {imageUrl && (
              <span
                className={cn(
                  "text-[9px] font-bold flex items-center gap-1 px-1.5 py-0.5 rounded border",
                  isUploaded
                    ? "bg-purple-500/15 text-purple-300 border-purple-500/30"
                    : "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                )}
                title={isUploaded ? "Uploaded from Smartphone / External Render" : "AI Generated in App"}
              >
                <CheckCircle2 className="w-3 h-3" />
                <span>{isUploaded ? "UPLOADED" : "SAVED"}</span>
              </span>
            )}
            {imageUrl && (
              <a
                href={imageUrl}
                target="_blank"
                rel="noreferrer"
                className="p-1 rounded bg-black/60 hover:bg-black text-amber-400 border border-border/80 transition-colors"
                title="Open full-resolution image"
              >
                <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>
        </div>

        {/* Card Preview Body */}
        <div
          className={cn(
            "relative w-full rounded-lg bg-panel/40 overflow-hidden flex items-center justify-center border border-border/50",
            cfg.aspect === "16:9" ? "aspect-[16/9]" : cfg.aspect === "1:1" ? "aspect-square" : "aspect-[3/4]"
          )}
        >
          {isRendering || isUploading ? (
            <div className="flex flex-col items-center justify-center p-3 text-center space-y-2">
              <Loader2 className="w-7 h-7 text-amber-500 animate-spin" />
              <span className="text-[10px] font-mono text-amber-300 leading-tight">
                {isUploading ? "Mengunggah & normalisasi foto..." : statusText || "Merender aset cinema-grade..."}
              </span>
            </div>
          ) : imageUrl ? (
            <div
              className="w-full h-full relative group/img cursor-pointer"
              onClick={() => {
                setLightboxImageUrl(imageUrl);
                setLightboxTitle(cfg.title);
              }}
              title="Klik untuk zoom pratinjau biometrik"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={imageUrl}
                alt={cfg.title}
                className="w-full h-full object-cover rounded-lg group-hover/img:scale-105 transition-transform duration-200"
              />
              <span
                className={cn(
                  "absolute top-2 left-2 px-1.5 py-0.5 rounded text-[9px] font-mono font-bold border backdrop-blur-sm shadow-sm",
                  is2k
                    ? "bg-emerald-950/85 text-emerald-300 border-emerald-500/50"
                    : "bg-black/75 text-amber-300 border-amber-500/30"
                )}
                title={is2k ? "Native 2K Verified" : "Standard 1K Render"}
              >
                {is2k ? "2K Ready" : resBadgeLabel}
              </span>
              <div className="absolute inset-0 bg-black/40 opacity-0 group-hover/img:opacity-100 transition-opacity flex items-center justify-center">
                <ZoomIn className="w-5 h-5 text-amber-400" />
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center text-obsidian-muted group-hover:text-amber-500/60 transition-colors p-3 text-center space-y-1">
              <Users className="w-9 h-9 opacity-25 group-hover:opacity-50 transition-opacity" />
              <span className="text-[10px] font-mono text-obsidian-secondary font-medium text-center px-1">
                {cfg.subtitle}
              </span>
              {!selectedChar.closeup_image_url && !cfg.isMasterAnchor && (
                <span className="text-[9px] font-mono text-amber-400/80">
                  (Card 1 Character Close-Up disarankan lebih dulu)
                </span>
              )}
            </div>
          )}
        </div>

        {/* Error Feedback */}
        {errorMsg && (
          <div className="p-1.5 rounded bg-rose-500/20 border border-rose-500/40 text-[9px] font-mono text-rose-300 truncate">
            {errorMsg}
          </div>
        )}

        {/* Always-Available Touch-Friendly Controls (Row 1: Render & Upload | Row 2: Copy Prompt & View) */}
        <div className="space-y-1.5 pt-1.5 border-t border-border/60 font-mono text-[10px]">
          {/* Row 1: Render & Upload Buttons */}
          <div className="grid grid-cols-2 gap-1.5">
            {!isLocked && (
              <button
                type="button"
                onClick={() => {
                  if (isBatchActive) {
                    showBatchLockNotification(imageUrl ? `Re-render ${cfg.title}` : `Render ${cfg.title}`);
                    return;
                  }
                  if (isRendering || isUploading) return;
                  handleRenderAsset(cfg.targetType, cfg.slot);
                }}
                disabled={isRendering || isUploading}
                aria-disabled={isBatchActive || isRendering || isUploading}
                className={cn(
                  "py-1.5 px-2 rounded-lg font-bold flex items-center justify-center gap-1 transition-colors shadow-sm disabled:opacity-50",
                  isBatchActive
                    ? "opacity-60 cursor-not-allowed border-amber-500/40 text-amber-300 bg-canvas"
                    : imageUrl
                    ? "bg-canvas hover:bg-elevated border border-border hover:border-amber-500/50 text-obsidian-primary"
                    : "bg-amber-500 hover:bg-amber-600 text-canvas"
                )}
                title={
                  isBatchActive
                    ? "Terkunci: Proses batch sedang berlangsung"
                    : imageUrl
                    ? `Re-render ${cfg.title}`
                    : `Render ${cfg.title}`
                }
              >
                {imageUrl ? (
                  <>
                    <RefreshCw className={cn("w-3 h-3 text-amber-400", isBatchActive && "opacity-60")} />
                    <span>Re-render</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3 h-3" />
                    <span>Render</span>
                  </>
                )}
              </button>
            )}

            {!isLocked && (
              <button
                type="button"
                onClick={() => {
                  if (isBatchActive) {
                    showBatchLockNotification(`Upload ${cfg.title}`);
                    return;
                  }
                  if (isRendering || isUploading) return;
                  document.getElementById(`upload-sheet-${cfg.slot}`)?.click();
                }}
                disabled={isRendering || isUploading}
                aria-disabled={isBatchActive || isRendering || isUploading}
                className={cn(
                  "py-1.5 px-2 rounded-lg border font-semibold flex items-center justify-center gap-1 transition-colors disabled:opacity-50",
                  isBatchActive
                    ? "opacity-60 cursor-not-allowed bg-canvas border-border text-obsidian-muted"
                    : "bg-canvas hover:bg-elevated border border-border hover:border-emerald-500/50 text-obsidian-secondary hover:text-obsidian-primary"
                )}
                title={
                  isBatchActive
                    ? "Terkunci: Proses batch sedang berlangsung"
                    : imageUrl
                    ? `Replace photo for ${cfg.title}`
                    : `Upload photo for ${cfg.title}`
                }
              >
                <Upload className="w-3 h-3 text-emerald-400 shrink-0" />
                <span>{imageUrl ? "Replace" : "Upload"}</span>
              </button>
            )}
          </div>

          {/* Row 2: One-Click Copy Prompt & View Prompt Modal */}
          <div className="grid grid-cols-3 gap-1.5">
            <button
              type="button"
              onClick={() => {
                const textToCopy =
                  promptItem?.copy_ready_text ||
                  promptItem?.positive_prompt ||
                  selectedChar.base_prompt;
                copyTextToClipboard(textToCopy, cfg.slot);
              }}
              className="col-span-2 py-1.5 px-2 rounded-lg bg-black/40 hover:bg-black/70 border border-border/80 hover:border-amber-500/40 text-obsidian-secondary hover:text-amber-400 font-semibold flex items-center justify-center gap-1 transition-colors"
              title="One-click copy compiled Master Prompt with negative & seed"
            >
              {copiedPromptSlot === cfg.slot ? (
                <>
                  <Check className="w-3 h-3 text-emerald-400 shrink-0" />
                  <span className="text-emerald-400 font-bold">Copied ✓</span>
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3 shrink-0 text-amber-500" />
                  <span>Copy Prompt</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={() => openPromptModal(cfg.slot)}
              className="py-1.5 px-1.5 rounded-lg bg-black/40 hover:bg-black/70 border border-border/80 hover:border-amber-500/40 text-obsidian-secondary hover:text-amber-400 font-semibold flex items-center justify-center gap-1 transition-colors"
              title="View full prompt breakdown, aspect ratio & camera directives"
            >
              <Eye className="w-3 h-3 shrink-0" />
              <span>View</span>
            </button>
          </div>

          {/* Row 3: Upscale Quality 2K & Revert 1K Controls */}
          {!isLocked && imageUrl && (
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => handleUpscaleAsset(cfg.slot)}
                disabled={isBatchActive || isRendering || isUploading || isUpscaling || is2k}
                className={cn(
                  "flex-1 py-1.5 px-2 rounded-lg border font-bold flex items-center justify-center gap-1 transition-colors disabled:opacity-60",
                  is2k
                    ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300 cursor-default"
                    : isBatchActive
                    ? "bg-canvas border-border text-obsidian-muted cursor-not-allowed"
                    : "bg-indigo-500/15 hover:bg-indigo-500/25 border-indigo-400/40 text-indigo-300 hover:text-indigo-200"
                )}
                title={
                  is2k
                    ? `Sudah 2K (${resBadgeLabel})`
                    : isBatchActive
                    ? "Dinonaktifkan saat Batch Orchestrator sedang aktif"
                    : "Refine & Upscale aset ini ke resolusi native 2K via Cloud API"
                }
              >
                {isUpscaling ? (
                  <>
                    <Loader2 className="w-3 h-3 animate-spin" />
                    <span>Upscaling 2K...</span>
                  </>
                ) : is2k ? (
                  <>
                    <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                    <span>2K Ready ({resW}×{resH})</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3 h-3 text-indigo-300" />
                    <span>Upscale 2K</span>
                  </>
                )}
              </button>

              {hasPrev1k && (
                <button
                  type="button"
                  onClick={() => handleRevertAsset(cfg.slot)}
                  disabled={isBatchActive || isUpscaling || isRendering}
                  className="py-1.5 px-2 rounded-lg bg-canvas hover:bg-elevated border border-border hover:border-amber-500/40 text-obsidian-secondary hover:text-amber-300 font-semibold flex items-center justify-center gap-1 transition-colors disabled:opacity-50"
                  title="Kembalikan ke versi 1K sebelumnya"
                >
                  <RotateCcw className="w-3 h-3" />
                  <span>Revert 1K</span>
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Top Section: Character Roster Bar & Action Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="space-y-1.5">
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <h3 className="font-cinzel text-sm sm:text-base font-bold uppercase tracking-wider text-obsidian-primary flex items-center gap-2">
              <Users className="w-4 h-4 text-amber-500 shrink-0" />
              <span>Character Cast &amp; Dynamic State Matrix</span>
            </h3>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-panel border border-amber-500/30 text-amber-400 font-medium whitespace-nowrap shadow-sm">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse shrink-0" />
              <span className="font-semibold">{characters.length} Characters</span>
              <span className="text-obsidian-muted">&bull;</span>
              <span className="text-obsidian-secondary">Polya AI Screenwriter</span>
            </span>
          </div>
          <p className="text-xs font-mono text-obsidian-muted">
            Maintains visual identity anchors, facial geometries, and wear states across all 50 scenes.
          </p>
        </div>

        {!isLocked && (
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setGenerateCastModalOpen(true)}
              disabled={isBatchGenerating}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-canvas font-mono font-bold text-xs transition-colors shadow-sm"
              title="Generate ensemble cast (5–8 karakter) via Polya AI Screenwriter"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>✨ Generate Cast (Polya AI)</span>
            </button>

            <button
              type="button"
              onClick={() => setAddOneModalOpen(true)}
              disabled={isBatchGenerating}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-panel hover:bg-elevated disabled:opacity-50 border border-border hover:border-amber-500/40 text-obsidian-primary font-mono font-semibold text-xs transition-colors shadow-sm"
              title="Tambah 1 karakter baru via Polya AI dengan proteksi anti-duplikasi persona"
            >
              <Plus className="w-3.5 h-3.5 text-amber-500" />
              <span>+ Add 1 Character (Polya AI)</span>
            </button>

            {/* Global Batch Downstream Generation Button */}
            <button
              type="button"
              onClick={handleOpenBatchModal}
              disabled={isBatchGenerating || characters.length === 0}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 disabled:opacity-50 text-canvas font-mono font-bold text-xs transition-all shadow-sm"
              title="Generate Cards 2–8 + 5 Dynamic States untuk seluruh karakter yang sudah memiliki Card 1 (Master Anchor)"
            >
              {isBatchGenerating ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Sparkles className="w-3.5 h-3.5" />
              )}
              <span>Generate All Downstream for All Characters (Cards 2–8 + 5 States)</span>
            </button>

            <button
              type="button"
              onClick={() => setAddCharModalOpen(true)}
              disabled={isBatchGenerating}
              className="flex items-center gap-1 px-2 py-1.5 rounded-lg bg-canvas hover:bg-elevated disabled:opacity-50 border border-border text-obsidian-muted hover:text-obsidian-primary font-mono text-xs transition-colors"
              title="Tambah karakter manual"
            >
              <span>+ Manual</span>
            </button>
          </div>
        )}
      </div>

      {/* Live Batch Downstream Progress HUD Banner */}
      {isBatchGenerating && batchProgress && (
        <div className="p-4 rounded-xl bg-gradient-to-r from-amber-500/10 via-canvas to-amber-500/5 border border-amber-500/40 space-y-3 shadow-md animate-in fade-in duration-200">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-ping" />
                <span className="text-xs font-mono font-bold text-amber-300 uppercase tracking-wider">
                  Processing Character {batchProgress.currentCharIdx}/{batchProgress.totalReady}: {batchProgress.charName} — Cards 2–8 + 5 States
                </span>
              </div>
              <p className="text-xs font-mono text-obsidian-secondary">
                {batchProgress.stepText}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleStopBatch}
                disabled={isStoppingBatch}
                className="px-3 py-1.5 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 disabled:opacity-50 border border-rose-500/40 text-rose-300 font-bold text-xs flex items-center gap-1.5 transition-all shadow-sm"
                title="Hentikan batch downstream setelah aset aktif selesai"
              >
                {isStoppingBatch ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Stopping...</span>
                  </>
                ) : (
                  <>
                    <XCircle className="w-3.5 h-3.5" />
                    <span>Stop Batch</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Granular Step Progress Bar */}
          <div className="w-full bg-black/40 rounded-full h-2 overflow-hidden border border-border/80">
            <div
              className="bg-gradient-to-r from-amber-500 to-amber-400 h-full transition-all duration-300"
              style={{
                width: `${Math.min(
                  100,
                  Math.round(
                    (((batchProgress.currentCharIdx - 1) * batchProgress.totalSteps +
                      batchProgress.currentStep) /
                      (batchProgress.totalReady * batchProgress.totalSteps)) *
                      100
                  )
                )}%`,
              }}
            />
          </div>

          <div className="flex items-center justify-between text-[10px] font-mono text-obsidian-muted">
            <div className="flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              <span>Card 1 Read-Only Protected</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>Auto-saved to Persistent SQLite Storage</span>
            </div>
          </div>
        </div>
      )}

      {characters.length === 0 ? (
        <div className="p-8 sm:p-12 rounded-2xl bg-panel border border-border/80 text-center space-y-6 shadow-sm">
          <div className="mx-auto w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 shadow-inner">
            <Sparkles className="w-8 h-8" />
          </div>
          <div className="max-w-xl mx-auto space-y-2">
            <h3 className="font-cinzel text-xl font-bold text-obsidian-primary">
              No Characters Created Yet
            </h3>
            <p className="text-xs font-mono text-obsidian-secondary leading-relaxed">
              Proyek <strong className="text-obsidian-primary">{project?.title || "Ini"}</strong> belum memiliki karakter di Master Production Bible.
              Gunakan <strong>Polya AI (Screenwriter)</strong> untuk men-generate susunan cast ensemble (5–8 karakter) secara otomatis berbasis sinopsis dan aturan dunia cerita.
            </p>
          </div>

          <div className="max-w-md mx-auto p-4 rounded-xl bg-canvas border border-border/80 flex items-center justify-between text-xs font-mono text-left shadow-sm">
            <div className="space-y-0.5">
              <span className="text-[10px] uppercase text-obsidian-muted font-semibold block">Konteks Cerita Proyek:</span>
              <span className="text-obsidian-primary font-bold text-xs block">
                {project?.title || "Project Untitled"} ({String((project?.settings as any)?.genre || project?.target_style_code || "Cinematic")})
              </span>
              <div className="text-[11px] text-obsidian-secondary truncate max-w-xs mt-0.5">
                {String((project?.settings as any)?.synopsis || (project?.settings as any)?.logline || (project?.settings as any)?.description || (project?.settings as any)?.premise || "Sinopsis siap diproses oleh Polya AI Screenwriter.")}
              </div>
            </div>
            <span className="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase shrink-0 border bg-emerald-500/10 text-emerald-400 border-emerald-500/30">
              Ready for Polya AI
            </span>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
            <button
              type="button"
              onClick={() => setGenerateCastModalOpen(true)}
              className="px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-600 text-canvas font-bold font-mono text-xs flex items-center gap-2 transition-all shadow-md hover:scale-[1.02]"
            >
              <Sparkles className="w-4 h-4" />
              <span>✨ Generate Cast Ensemble (Polya AI)</span>
            </button>
            <button
              type="button"
              onClick={() => setAddOneModalOpen(true)}
              className="px-4 py-2.5 rounded-xl bg-panel hover:bg-elevated text-obsidian-primary border border-border hover:border-amber-500/40 font-semibold font-mono text-xs flex items-center gap-2 transition-all"
            >
              <Plus className="w-4 h-4 text-amber-500" />
              <span>+ Add 1 Character (Polya AI)</span>
            </button>
          </div>
        </div>
      ) : selectedChar ? (
        <>
          {/* Main Character Selector Tabs */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
            {activeCharacters.map((char) => {
              const isSelected = selectedChar.id === char.id;
              const roleBadgeColor =
                char.role === "PROTAGONIST"
                  ? "text-amber-400 border-amber-500/30"
                  : char.role === "ANTAGONIST"
                  ? "text-rose-400 border-rose-500/30"
                  : char.role === "DEUTERAGONIST"
                  ? "text-blue-400 border-blue-500/30"
                  : char.role === "MENTOR"
                  ? "text-purple-400 border-purple-500/30"
                  : "text-emerald-400 border-emerald-500/30";

              return (
                <button
                  key={char.id}
                  type="button"
                  onClick={() => handleSelectCharacter(char.id)}
                  className={cn(
                    "px-3.5 py-2 rounded-xl text-xs font-mono transition-all border text-left shrink-0 flex items-center gap-2.5",
                    isSelected
                      ? "bg-amber-500/10 border-amber-500/50 text-amber-400 font-bold shadow-sm"
                      : "bg-panel border-border text-obsidian-secondary hover:text-obsidian-primary hover:border-border/80"
                  )}
                >
                  <div
                    className={cn(
                      "w-2 h-2 rounded-full",
                      isSelected ? "bg-amber-500" : "bg-obsidian-muted/40"
                    )}
                  />
                  <div>
                    <div className="font-medium text-obsidian-primary leading-tight">{char.name}</div>
                    <span className={cn("text-[9px] uppercase font-semibold", roleBadgeColor)}>
                      {char.role}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>

      {/* =========================================================================
       * AI Render Provider Card (Global Acuan SQLite)
       * ========================================================================= */}
      <AIRenderProviderCard
        projectId={projectId}
        initialProviderId={selectedProvider}
        socks5Online={proxyStatus?.healthy}
        onCheckSocks5={handleCheckProxy}
        onSaveGlobalConfig={(payload) => applyGlobalProviderState(payload)}
      />

      {/* Selected Character Profile Header */}
      <div className="p-4 rounded-xl bg-panel border border-border shadow-sm">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 flex-wrap">
                <span className={cn(
                  "text-[10px] font-mono font-bold uppercase px-2 py-0.5 rounded border",
                  selectedChar.role === "PROTAGONIST"
                    ? "text-amber-400 bg-amber-500/10 border-amber-500/30"
                    : selectedChar.role === "ANTAGONIST"
                    ? "text-rose-400 bg-rose-500/10 border-rose-500/30"
                    : "text-blue-400 bg-blue-500/10 border-blue-500/30"
                )}>
                  {selectedChar.role}
                </span>

                <button
                  type="button"
                  onClick={() => handleCopySeed(selectedChar.dna_seed || "—")}
                  className="flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/20 transition-colors"
                  title="Click to copy locked DNA Seed"
                >
                  <Lock className="w-3 h-3 text-emerald-400" />
                  <span>SEED: #{selectedChar.dna_seed || "—"}</span>
                  {copiedSeed ? (
                    <Check className="w-3 h-3 text-emerald-300 ml-1" />
                  ) : (
                    <Copy className="w-3 h-3 text-emerald-400/70 ml-1" />
                  )}
                </button>
                <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-bold">
                  DNA SEED LOCKED
                </span>
              </div>

              {!isLocked && (
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => setRegenModalOpen(true)}
                    disabled={isBatchGenerating}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30 text-[11px] font-mono font-semibold transition-colors disabled:opacity-50"
                    title="Generate ulang hanya karakter ini via Polya AI Screenwriter"
                  >
                    <RefreshCw className="w-3 h-3" />
                    <span>🔄 Re-generate Character (Polya AI)</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleDeleteCharacter(selectedChar.id, selectedChar.name)}
                    disabled={isDeletingChar || isBatchGenerating}
                    className="flex items-center gap-1 px-2 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 text-[11px] font-mono transition-colors disabled:opacity-50"
                    title="Hapus karakter ini dari proyek"
                  >
                    <Trash2 className="w-3 h-3" />
                    <span>Delete</span>
                  </button>
                </div>
              )}
            </div>

            {/* Character Name & Role Inline Edit */}
            {isEditingCharIdentity ? (
              <div className="p-3 rounded-xl bg-canvas border border-amber-500/40 space-y-2.5 animate-in fade-in duration-150">
                <div className="flex flex-col sm:flex-row gap-2">
                  <div className="flex-1">
                    <label className="text-[10px] text-obsidian-muted uppercase font-semibold block mb-1">
                      Nama Karakter
                    </label>
                    <input
                      type="text"
                      value={editCharName}
                      onChange={(e) => setEditCharName(e.target.value)}
                      className="w-full px-3 py-1.5 rounded-lg bg-panel border border-border text-obsidian-primary text-sm font-bold focus:border-amber-500 focus:outline-none"
                    />
                  </div>
                  <div className="sm:w-44">
                    <label className="text-[10px] text-obsidian-muted uppercase font-semibold block mb-1">
                      Peran / Role
                    </label>
                    <select
                      value={editCharRole}
                      onChange={(e) => setEditCharRole(e.target.value)}
                      className="w-full px-2.5 py-1.5 rounded-lg bg-panel border border-border text-obsidian-primary text-xs font-mono focus:border-amber-500 focus:outline-none"
                    >
                      <option value="PROTAGONIST">PROTAGONIST</option>
                      <option value="ANTAGONIST">ANTAGONIST</option>
                      <option value="DEUTERAGONIST">DEUTERAGONIST</option>
                      <option value="MENTOR">MENTOR</option>
                      <option value="SUPPORTING">SUPPORTING</option>
                      <option value="EXTRAS">EXTRAS</option>
                    </select>
                  </div>
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] text-obsidian-muted uppercase font-semibold block">
                    Narrative Summary &amp; Dramatic Arc
                  </label>
                  <textarea
                    value={editCharNarrativeSummary}
                    onChange={(e) => setEditCharNarrativeSummary(e.target.value)}
                    rows={2}
                    placeholder="Core motivation, flaw, and dramatic transformation arc..."
                    className="w-full px-3 py-1.5 rounded-lg bg-panel border border-border text-obsidian-primary text-xs focus:border-amber-500 focus:outline-none resize-none"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] text-obsidian-muted uppercase font-semibold block">
                    Voice DNA Profile (Cadence, Pacing &amp; Subtext Style)
                  </label>
                  <textarea
                    value={editCharVoiceDna}
                    onChange={(e) => setEditCharVoiceDna(e.target.value)}
                    rows={2}
                    placeholder="e.g. Sparse clipped clauses (~2.1 wps), dry wit, avoids overt emotion..."
                    className="w-full px-3 py-1.5 rounded-lg bg-panel border border-border text-obsidian-primary text-xs font-mono focus:border-amber-500 focus:outline-none resize-none"
                  />
                </div>
                <div className="flex items-center justify-end gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => setIsEditingCharIdentity(false)}
                    className="px-2.5 py-1 rounded text-xs font-mono text-obsidian-muted hover:text-obsidian-primary hover:bg-elevated transition-colors"
                  >
                    Batal
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveCharacterIdentity}
                    disabled={isSavingCharIdentity || !editCharName.trim()}
                    className="px-3 py-1 rounded bg-amber-500 hover:bg-amber-600 text-canvas text-xs font-mono font-bold flex items-center gap-1 transition-colors disabled:opacity-50"
                  >
                    {isSavingCharIdentity ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
                    <span>Simpan</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-2 group">
                <h4 className="font-cinzel text-lg font-bold text-obsidian-primary">
                  {selectedChar.name}
                </h4>
                {!isLocked && !isBatchGenerating && (
                  <button
                    type="button"
                    onClick={handleStartEditIdentity}
                    className="p-1 rounded text-obsidian-muted hover:text-amber-400 hover:bg-elevated transition-colors"
                    title="Edit nama dan peran karakter"
                  >
                    <Edit className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            )}

            {/* Narrative Summary (from Polya AI Screenwriter) */}
            {selectedChar.narrative_summary && (
              <div className="p-2.5 rounded-lg bg-canvas/70 border border-border/80 text-xs font-sans text-obsidian-secondary leading-relaxed">
                <span className="text-[10px] font-mono text-amber-400 font-bold uppercase tracking-wide block mb-0.5">
                  Narrative Profile &amp; Dramatic Arc
                </span>
                {selectedChar.narrative_summary}
              </div>
            )}

            {/* Base Visual Prompt with Inline Edit */}
            <div className="space-y-1 text-xs font-mono">
              <div className="flex items-center justify-between">
                <label className="text-[10px] text-obsidian-muted uppercase font-semibold">
                  Base Visual Prompt
                </label>
                {!isLocked && !isEditingPrompt && !isBatchGenerating && (
                  <button
                    type="button"
                    onClick={handleStartEditPrompt}
                    className="text-[10px] text-amber-400 hover:text-amber-300 flex items-center gap-1 hover:underline"
                  >
                    <Edit className="w-3 h-3" />
                    <span>Edit Prompt</span>
                  </button>
                )}
              </div>

              {isEditingPrompt ? (
                <div className="space-y-2">
                  <textarea
                    value={editBasePrompt}
                    onChange={(e) => setEditBasePrompt(e.target.value)}
                    rows={4}
                    className="w-full px-3 py-2 rounded-lg bg-canvas border border-amber-500/50 text-obsidian-primary leading-relaxed text-[11px] focus:outline-none focus:border-amber-500"
                  />
                  <div className="flex items-center justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => setIsEditingPrompt(false)}
                      className="px-2.5 py-1 rounded text-xs font-mono text-obsidian-muted hover:text-obsidian-primary"
                    >
                      Batal
                    </button>
                    <button
                      type="button"
                      onClick={handleSaveBasePrompt}
                      disabled={isSavingPrompt || !editBasePrompt.trim()}
                      className="px-3 py-1 rounded bg-amber-500 hover:bg-amber-600 text-canvas text-xs font-mono font-bold flex items-center gap-1 transition-colors disabled:opacity-50"
                    >
                      {isSavingPrompt ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
                      <span>Simpan Prompt</span>
                    </button>
                  </div>
                </div>
              ) : (
                <div className="p-2.5 rounded-lg bg-canvas border border-border text-obsidian-primary leading-relaxed text-[11px]">
                  {selectedChar.base_prompt}
                </div>
              )}
            </div>
          </div>

          <div className="space-y-3 font-mono text-xs">
            <div className="space-y-1">
              <label className="text-[10px] text-obsidian-muted uppercase font-semibold flex items-center gap-1.5">
                <Mic className="w-3.5 h-3.5 text-amber-500" />
                <span>Voice DNA Profile</span>
              </label>
              <div className="p-2.5 rounded-lg bg-canvas border border-border flex items-center justify-between gap-2">
                <span className="text-obsidian-secondary text-[11px] truncate">
                  {selectedChar.voice_dna_profile?.trim()
                    ? selectedChar.voice_dna_profile
                    : "Not configured — click Edit Identity above to set Voice DNA"}
                </span>
                <span
                  className={cn(
                    "px-1.5 py-0.5 rounded text-[9px] font-bold shrink-0 border",
                    selectedChar.voice_dna_profile?.trim()
                      ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                      : "bg-amber-500/10 text-amber-400 border-amber-500/30"
                  )}
                >
                  {selectedChar.voice_dna_profile?.trim() ? "Voice DNA Locked" : "Voice DNA Unset"}
                </span>
              </div>
            </div>

            {(() => {
              const engineInfo = resolveProviderDisplayInfo(selectedProvider, selectedModel);
              const isFlowEngine = isGoogleFlowProvider(selectedProvider);
              return (
                <div className="p-2.5 rounded-lg bg-canvas border border-border space-y-1.5 text-[10px]">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-obsidian-muted uppercase">Active Engine:</span>
                    <span className="text-amber-400 font-bold text-right truncate">
                      {isFlowEngine
                        ? "Google Flow (6 Akun PRO)"
                        : engineInfo.label}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-obsidian-muted uppercase">Anchoring Mode:</span>
                    <span
                      className={cn(
                        "px-1.5 py-0.5 rounded font-bold text-[9px]",
                        isFlowEngine || engineInfo.supportsVisualAnchor
                          ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                          : "bg-blue-500/15 text-blue-400 border border-blue-500/30"
                      )}
                    >
                      {isFlowEngine
                        ? "Multimodal Reference Upload (Max 4)"
                        : engineInfo.supportsVisualAnchor
                        ? "Visual Anchor + Seed Lock"
                        : "Strict Seed + Chained DNA Lock"}
                    </span>
                  </div>
                </div>
              );
            })()}
          </div>
        </div>
      </div>

      {/* =========================================================================
       * EIGHT-SHEET CHARACTER PRODUCTION MATRIX
       * ========================================================================= */}
      <div className="p-4 rounded-xl bg-panel border border-border space-y-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-border/80 pb-3">
          <div>
            <div className="flex items-center gap-2">
              <Camera className="w-4 h-4 text-amber-500" />
              <h4 className="font-cinzel text-sm font-bold uppercase tracking-wider text-obsidian-primary">
                Eight-Sheet Character Production Matrix
              </h4>
              <span className="px-2 py-0.5 rounded-full text-[9px] font-mono bg-amber-500/15 text-amber-400 border border-amber-500/30 font-bold">
                Sequential Visual Anchoring (8 Cards + Dynamic States)
              </span>
            </div>
            <p className="text-[11px] font-mono text-obsidian-muted mt-0.5">
              Dedicated high-resolution turnaround cards, rigging baseline, signature action breakdown, and micro-expressions panel.
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {!isLocked && (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleRegenerateAllDownstream}
                  disabled={isRegeneratingAllDownstream || isBatchGenerating || !selectedChar.closeup_image_url}
                  className="px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-canvas font-bold text-xs flex items-center gap-1.5 transition-all shadow-sm"
                  title={
                    isBatchGenerating
                      ? "Batch Downstream sedang berlangsung..."
                      : !selectedChar.closeup_image_url
                      ? "Card 1 Close-Up diperlukan sebagai Master Anchor"
                      : "Jalankan One-Click Full Downstream Pipeline (Card 2–8 + Dynamic States) secara sekuensial berfase"
                  }
                >
                  {isRegeneratingAllDownstream ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Sparkles className="w-3.5 h-3.5" />
                  )}
                  <span>
                    {isRegeneratingAllDownstream
                      ? downstreamProgressText || "Processing Pipeline..."
                      : `Regenerate All Downstream (Cards 2–8 + ${selectedChar.states?.length || 5} States)`}
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => handleRetryFailedOnly(selectedChar)}
                  disabled={isRegeneratingAllDownstream || isBatchGenerating || !selectedChar.closeup_image_url}
                  className="px-3 py-1.5 rounded-lg bg-panel hover:bg-elevated border border-amber-500/40 text-amber-300 font-bold text-xs flex items-center gap-1.5 transition-all shadow-sm disabled:opacity-50"
                  title="Hanya render ulang kartu dan state yang belum terisi atau gagal pada karakter ini (Resume Mode)"
                >
                  <RefreshCw className="w-3.5 h-3.5 text-amber-400" />
                  <span>Retry Missing / Failed</span>
                </button>

                {isRegeneratingAllDownstream && (
                  <button
                    type="button"
                    disabled={isStoppingDownstream}
                    onClick={() => {
                      setIsStoppingDownstream(true);
                      abortDownstreamRef.current = true;
                      setDownstreamProgressText("Menghentikan pipeline downstream...");
                    }}
                    className="px-2.5 py-1.5 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 disabled:opacity-50 border border-rose-500/40 text-rose-300 font-bold text-xs flex items-center gap-1 transition-all"
                    title="Hentikan pipeline setelah step aktif selesai"
                  >
                    {isStoppingDownstream ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Stopping...</span>
                      </>
                    ) : (
                      <>
                        <XCircle className="w-3.5 h-3.5" />
                        <span>Stop</span>
                      </>
                    )}
                  </button>
                )}
              </div>
            )}
            <div className="text-[10px] font-mono text-obsidian-muted flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>Auto-saved to Persistent SQLite Storage</span>
            </div>
          </div>
        </div>

        {/* Master Anchor Notice if Close-Up not rendered yet */}
        {!selectedChar.closeup_image_url && (
          <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-mono flex items-center gap-2">
            <Info className="w-4 h-4 shrink-0 text-amber-400" />
            <span>
              <strong>Production Rule:</strong> Card 1 Character Close-Up (Master Anchor) adalah Master Biometric Anchor. Merender Card 1 terlebih dahulu mengunci identitas biometrik wajah, detail mikroskopis kulit, dan konsistensi visual di seluruh Card 2&ndash;8.
            </span>
          </div>
        )}

        {/* ROW 1: Master Biometric & Primary Body Anchors (Card 1: Close-Up &bull; Card 2: Expression Sheet &bull; Card 3: Full Body Front) */}
        <div className="space-y-2.5">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-[11px] uppercase tracking-wider text-obsidian-secondary font-bold flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
              <span>Row 1 &mdash; Master Anchors (Card 1: Close-Up &bull; Card 2: Expression Sheet 3x2 &bull; Card 3: Full Body Front)</span>
            </span>
            <span className="text-[10px] text-obsidian-muted">Master Biometric Face &amp; Primary Anatomy Anchors</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
            <div>
              {renderMatrixCard({
                slot: "closeup",
                title: "CARD 1: CHARACTER CLOSE-UP",
                targetType: "sheet",
                aspect: "1:1",
                imageUrl: selectedChar.closeup_image_url,
                subtitle: isPhotorealisticCastingStyle(project?.target_style_code)
                  ? "1:1 Square • 85mm f/4.5 RAW"
                  : "1:1 Square • Stylized Master Anchor",
                anchorBadge: "Master Anchor",
                isMasterAnchor: true,
              })}
            </div>

            <div>
              {renderMatrixCard({
                slot: "expression",
                title: "CARD 2: EXPRESSION SHEET (3x2)",
                targetType: "sheet",
                aspect: "16:9",
                imageUrl: selectedChar.expression_image_url,
                subtitle: "6 Micro-Expressions Grid",
                anchorBadge: selectedChar.closeup_image_url ? "Anchor: [Card 1 Close-Up]" : "Master Anchor",
              })}
            </div>

            <div>
              {renderMatrixCard({
                slot: "front",
                title: "CARD 3: FULL BODY (FRONT)",
                targetType: "turnaround",
                aspect: "3:4",
                imageUrl: selectedChar.front_image_url,
                subtitle: "Orthogonal 0° • Primary Body Anchor",
                anchorBadge: selectedChar.closeup_image_url ? "Anchor: [Card 1 Close-Up]" : "Master Anchor",
              })}
            </div>
          </div>
        </div>

        {/* ROW 2: Turnaround Geometry, Rigging & Dynamic Motion (Cards 4 - 8) */}
        <div className="space-y-2.5 pt-3 border-t border-border/80">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-[11px] uppercase tracking-wider text-obsidian-secondary font-bold flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
              <span>Row 2 &mdash; Turnaround Geometry, Rigging &amp; Dynamic Action (Cards 4&ndash;8)</span>
            </span>
            <span className="text-[10px] text-obsidian-muted">Profile &bull; 3/4 Hero &bull; Back &bull; T-Pose &bull; Action Pose</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
            {renderMatrixCard({
              slot: "side",
              title: "CARD 4: SIDE PROFILE",
              targetType: "turnaround",
              aspect: "3:4",
              imageUrl: selectedChar.side_image_url,
              subtitle: "Profile 90° • Silhouette",
              anchorBadge: "Anchors: [Card 1, Card 3]",
            })}

            {renderMatrixCard({
              slot: "three_quarter",
              title: "CARD 5: 3/4 HERO ANGLE",
              targetType: "turnaround",
              aspect: "3:4",
              imageUrl: selectedChar.three_quarter_image_url,
              subtitle: "Oblique 45° • Hero Perspective",
              anchorBadge: "Anchors: [Card 1, Card 3]",
            })}

            {renderMatrixCard({
              slot: "back",
              title: "CARD 6: BACK VIEW",
              targetType: "turnaround",
              aspect: "3:4",
              imageUrl: selectedChar.back_image_url,
              subtitle: "Orthogonal 180° • Rear Anatomy",
              anchorBadge: "Anchors: [Card 1, Card 3]",
            })}

            {renderMatrixCard({
              slot: "tpose",
              title: "CARD 7: T-POSE SHEET",
              targetType: "sheet",
              aspect: "3:4",
              imageUrl: selectedChar.tpose_image_url,
              subtitle: "Symmetry • Rigging Baseline",
              anchorBadge: "Anchors: [Card 1, Card 3]",
            })}

            {renderMatrixCard({
              slot: "action",
              title: "CARD 8: DYNAMIC ACTION",
              targetType: "sheet",
              aspect: "3:4",
              imageUrl: selectedChar.action_image_url,
              subtitle: "Kinetic Motion Breakdown",
              anchorBadge: "Anchors: [Card 1, Card 3]",
            })}
          </div>
        </div>
      </div>

      {/* Dynamic State Progression Matrix (#State 01 to #State 05) */}
      <div className="p-4 rounded-xl bg-panel border border-border space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary flex items-center gap-2">
              <Layers className="w-4 h-4 text-amber-500" />
              <span>Dynamic State Progression Matrix (#State 01 - #State 05)</span>
            </h4>
            <p className="text-[11px] font-mono text-obsidian-muted mt-0.5">
              Tracks continuous costume weathering, physical wear/injuries, and psychological anchors across 50 scenes. Inherits Upstream Visual Style, Project Synopsis, DNA Seed Lock, and Master Card 1&ndash;3 Anchors.
            </p>
          </div>

          {!isLocked && (
            <button
              type="button"
              onClick={handleOpenAddState}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-secondary hover:text-amber-400 text-xs font-mono transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add State</span>
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {(selectedChar.states || []).map((st) => {
            const targetKey = `state_${st.id}`;
            const isRendering = renderingTargets[targetKey];
            const isStateUpscaling = !!upscalingSlots[targetKey];
            const stateMeta = selectedChar?.sheet_metadata?.[targetKey];
            const stW = st.resolution_width ?? stateMeta?.resolution_width ?? stateMeta?.width;
            const stH = st.resolution_height ?? stateMeta?.resolution_height ?? stateMeta?.height;
            const stIs2k = !!(st.is_2k ?? stateMeta?.is_2k) || (!!stW && !!stH && Math.max(stW, stH) >= 1920);
            const stPrev1k = st.previous_1k_url ?? stateMeta?.previous_1k_url;
            const stBadge = stIs2k
              ? `2K Ready • ${stW || 2048}×${stH || 2048}`
              : stW && stH
              ? `1K • ${stW}×${stH}`
              : "1K • 1024×1024";
            const statusText = pollStatus[targetKey];
            const errorMsg = upscaleErrors[targetKey] || targetErrors[targetKey];

            return (
              <div
                key={st.id || st.state_code}
                className="p-3.5 rounded-xl bg-canvas border border-border hover:border-amber-500/40 transition-all space-y-3 font-mono text-xs flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between border-b border-border/80 pb-2 mb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-amber-400 text-xs">{st.state_code}</span>
                      <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-blue-500/10 text-blue-400 border border-blue-500/20">
                        Anchors: [Card 1, 3]
                      </span>
                      <button
                        type="button"
                        onClick={() => openPromptModal(st.state_code)}
                        className="p-1 rounded hover:bg-elevated text-obsidian-muted hover:text-amber-400 transition-colors"
                        title={`Lihat master prompt & directives untuk ${st.state_code}`}
                      >
                        <Eye className="w-3.5 h-3.5" />
                      </button>
                      {!isLocked && !isBatchGenerating && (
                        <>
                          <button
                            type="button"
                            onClick={() => handleOpenEditState(st)}
                            className="p-1 rounded hover:bg-elevated text-obsidian-muted hover:text-amber-400 transition-colors"
                            title={`Edit ${st.state_code}`}
                          >
                            <Edit className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeleteState(st)}
                            disabled={deletingStateId === st.id}
                            className="p-1 rounded hover:bg-rose-500/20 text-obsidian-muted hover:text-rose-400 transition-colors disabled:opacity-50"
                            title={`Hapus ${st.state_code}`}
                          >
                            {deletingStateId === st.id ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin text-rose-400" />
                            ) : (
                              <Trash2 className="w-3.5 h-3.5" />
                            )}
                          </button>
                        </>
                      )}
                    </div>
                    <span className="text-[10px] text-obsidian-muted">
                      {st.state_label || (st.state_code === "#State 01"
                        ? "Normal Baseline"
                        : st.state_code === "#State 02"
                        ? "Fatigue & Wear"
                        : st.state_code === "#State 03"
                        ? "Battle Damaged"
                        : st.state_code === "#State 04"
                        ? "Psychological Breakdown"
                        : "Climax / Metamorphosis")}
                    </span>
                  </div>

                  {/* State Image Preview */}
                  {st.image_url ? (
                    <div className="space-y-1.5 mb-2.5">
                      <div className="relative aspect-video w-full rounded-lg overflow-hidden border border-border group/stateimg">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={st.image_url}
                          alt={st.state_code}
                          className="w-full h-full object-cover"
                        />
                        <span
                          className={cn(
                            "absolute top-2 left-2 px-1.5 py-0.5 rounded text-[9px] font-mono font-bold border backdrop-blur-sm",
                            stIs2k
                              ? "bg-emerald-950/85 text-emerald-300 border-emerald-500/50"
                              : "bg-black/75 text-amber-300 border-amber-500/30"
                          )}
                        >
                          {stBadge}
                        </span>
                        <div className="absolute inset-0 bg-black/60 opacity-0 group-hover/stateimg:opacity-100 transition-opacity flex items-center justify-center gap-2">
                          <a
                            href={st.image_url}
                            target="_blank"
                            rel="noreferrer"
                            className="p-1 rounded bg-black/80 hover:bg-black text-amber-400 border border-border text-[10px] flex items-center gap-1 px-2"
                          >
                            <ExternalLink className="w-3 h-3" />
                            <span>Buka</span>
                          </a>
                          {!isLocked && (
                            <button
                              type="button"
                              onClick={() => {
                                if (isBatchActive) {
                                  showBatchLockNotification(`Render Ulang State ${st.state_code}`);
                                  return;
                                }
                                handleRenderAsset("state", undefined, st.id);
                              }}
                              aria-disabled={isBatchActive}
                              className={cn(
                                "p-1 rounded text-canvas font-bold text-[10px] flex items-center gap-1 px-2 transition-colors",
                                isBatchActive
                                  ? "bg-amber-500/50 opacity-60 cursor-not-allowed"
                                  : "bg-amber-500 hover:bg-amber-600"
                              )}
                              title={
                                isBatchActive
                                  ? "Terkunci: Proses batch sedang berlangsung"
                                  : `Render Ulang State ${st.state_code}`
                              }
                            >
                              <RefreshCw className="w-3 h-3" />
                              <span>Render Ulang</span>
                            </button>
                          )}
                        </div>
                      </div>
                      {!isLocked && (
                        <div className="flex items-center gap-1.5">
                          <button
                            type="button"
                            onClick={() => handleUpscaleAsset("state", st.id)}
                            disabled={isBatchActive || isRendering || isStateUpscaling || stIs2k}
                            className={cn(
                              "flex-1 py-1 px-2 rounded-lg border text-[10px] font-bold flex items-center justify-center gap-1 transition-colors disabled:opacity-60",
                              stIs2k
                                ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300 cursor-default"
                                : "bg-indigo-500/15 hover:bg-indigo-500/25 border-indigo-400/40 text-indigo-300"
                            )}
                          >
                            {isStateUpscaling ? (
                              <>
                                <Loader2 className="w-3 h-3 animate-spin" />
                                <span>Upscaling 2K...</span>
                              </>
                            ) : stIs2k ? (
                              <>
                                <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                                <span>2K Ready</span>
                              </>
                            ) : (
                              <>
                                <Sparkles className="w-3 h-3 text-indigo-300" />
                                <span>Upscale 2K</span>
                              </>
                            )}
                          </button>
                          {stPrev1k && (
                            <button
                              type="button"
                              onClick={() => handleRevertAsset("state", st.id)}
                              disabled={isBatchActive || isStateUpscaling || isRendering}
                              className="py-1 px-2 rounded-lg bg-panel hover:bg-elevated border border-border text-[10px] font-semibold text-obsidian-secondary hover:text-amber-300 flex items-center gap-1"
                            >
                              <RotateCcw className="w-3 h-3" />
                              <span>Revert 1K</span>
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  ) : isRendering ? (
                    <div className="aspect-video w-full rounded-lg bg-panel border border-border/80 flex flex-col items-center justify-center p-3 mb-2.5 text-center space-y-1.5">
                      <Loader2 className="w-5 h-5 text-amber-500 animate-spin" />
                      <span className="text-[10px] text-amber-300">{statusText || "Rendering..."}</span>
                    </div>
                  ) : null}

                  {errorMsg && (
                    <div className="p-1.5 rounded bg-rose-500/20 border border-rose-500/40 text-[9px] font-mono text-rose-300 mb-2 truncate">
                      {errorMsg}
                    </div>
                  )}

                  <div className="space-y-1">
                    <span className="text-[10px] text-obsidian-muted uppercase">Wardrobe:</span>
                    <p className="text-[11px] text-obsidian-primary leading-tight font-sans">
                      {st.wardrobe}
                    </p>
                  </div>

                  {st.injuries_and_wear && (
                    <div className="space-y-1 mt-2">
                      <span className="text-[10px] text-rose-400 uppercase">Physical Damage:</span>
                      <p className="text-[11px] text-obsidian-secondary leading-tight font-sans">
                        {st.injuries_and_wear}
                      </p>
                    </div>
                  )}

                  {st.expression_anchor && (
                    <div className="space-y-1 mt-2">
                      <span className="text-[10px] text-amber-500 uppercase">Emotional Anchor:</span>
                      <p className="text-[11px] text-obsidian-secondary leading-tight font-sans">
                        {st.expression_anchor}
                      </p>
                    </div>
                  )}
                </div>

                {/* Render Button for State if not rendered yet */}
                {!isLocked && !st.image_url && !isRendering && (
                  <button
                    type="button"
                    onClick={() => {
                      if (isBatchActive) {
                        showBatchLockNotification(`Render Visual State ${st.state_code}`);
                        return;
                      }
                      handleRenderAsset("state", undefined, st.id);
                    }}
                    aria-disabled={isBatchActive}
                    className={cn(
                      "w-full mt-2.5 flex items-center justify-center gap-1.5 py-1.5 rounded-lg border text-[10px] font-bold transition-all shadow-sm",
                      isBatchActive
                        ? "bg-elevated opacity-60 cursor-not-allowed border-amber-500/30 text-amber-300"
                        : "bg-elevated hover:bg-amber-500 hover:text-canvas border-border text-obsidian-secondary"
                    )}
                    title={
                      isBatchActive
                        ? "Terkunci: Proses batch sedang berlangsung"
                        : `Render Visual State ${st.state_code}`
                    }
                  >
                    <Sparkles className="w-3 h-3 text-amber-400" />
                    <span>Render Visual State</span>
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>
        </>
      ) : null}

      {/* Add Character Modal & Pre-Creation Visual Gatekeeper */}
      {addCharModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-black/85 backdrop-blur-md overflow-y-auto animate-in fade-in duration-200">
          <div className="w-full max-w-5xl max-h-[92vh] flex flex-col rounded-2xl bg-panel border border-border shadow-2xl text-obsidian-primary font-sans overflow-hidden animate-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-border/80 px-5 py-3.5 gap-2 bg-canvas/40">
              <div className="flex items-center gap-3 flex-wrap">
                <h4 className="font-cinzel text-sm font-bold uppercase text-obsidian-primary flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-amber-500" />
                  <span>Add Cast Character &bull; Visual Gatekeeper</span>
                </h4>
                {/* Active NLE Studio Metadata Context Badges */}
                <div className="flex items-center gap-2 text-[10px] font-mono">
                  <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-300">
                    <Film className="w-3 h-3 text-amber-400" />
                    <span className="font-semibold truncate max-w-[150px]">
                      {project?.title || "Film Project"}
                    </span>
                  </div>
                  <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                    <Sparkles className="w-3 h-3" />
                    <span>
                      {String((project?.settings as any)?.tone || project?.target_style_code || "#Style 01")}
                    </span>
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={handleCloseAddModal}
                className="text-obsidian-muted hover:text-obsidian-primary p-1 rounded-lg hover:bg-elevated transition-colors self-end sm:self-center"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body: Split 2-Column Responsive Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 p-5 overflow-y-auto max-h-[calc(92vh-125px)]">
              {/* Left Column: Form Input, Dual AI Providers & Context Generator */}
              <div className="lg:col-span-6 space-y-4 font-mono text-xs">
                {/* 1. Dual AI Provider Selector */}
                <div className="p-3 rounded-xl bg-canvas border border-border space-y-2.5">
                  <div className="text-[10px] uppercase font-bold text-amber-400 flex items-center justify-between">
                    <span>Dual AI Engine Selectors</span>
                    <span className="text-obsidian-muted font-normal lowercase">(direct API / low latency)</span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <label className="text-[10px] text-obsidian-secondary font-semibold">1. Text Concept LLM</label>
                      <select
                        value={addCharLLMProvider}
                        onChange={(e) => setAddCharLLMProvider(e.target.value as any)}
                        className="w-full px-2.5 py-1.5 rounded-lg bg-panel border border-border text-[11px] text-obsidian-primary focus:border-amber-500 focus:outline-none"
                      >
                        <option value="9router">9Router (Gemini Flash)</option>
                        <option value="gemini">Gemini 2.5 Flash</option>
                        <option value="agy">Agy (Fast Reasoning)</option>
                      </select>
                    </div>

                    <div className="space-y-1">
                      <label className="text-[10px] text-obsidian-secondary font-semibold">2. Image Render Engine</label>
                      <select
                        value={addCharImageProvider}
                        onChange={(e) => setAddCharImageProvider(e.target.value)}
                        className="w-full px-2.5 py-1.5 rounded-lg bg-panel border border-border text-[11px] text-obsidian-primary focus:border-amber-500 focus:outline-none"
                      >
                        {AI_RENDER_PROVIDERS.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.id === "google-flow"
                              ? "Google Flow (6 Akun PRO) [Recommended]"
                              : `${p.name} (${p.vendor})`}
                          </option>
                        ))}
                        <option value="ag_gemini_flash">AG / Gemini 3.8 Flash (Legacy)</option>
                      </select>
                      {isGoogleFlowProvider(addCharImageProvider) && (
                        <div className="mt-1 flex items-center justify-between text-[10px] font-mono px-2 py-1 rounded bg-canvas border border-border">
                          <div className="flex items-center gap-1.5">
                            <span
                              className={cn(
                                "w-1.5 h-1.5 rounded-full",
                                proxyStatus?.healthy ? "bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.8)]" : "bg-rose-500 animate-pulse"
                              )}
                            />
                            <span className="text-obsidian-secondary">SOCKS5 Android:</span>
                            <span className={proxyStatus?.healthy ? "text-emerald-400 font-bold" : "text-rose-400 font-bold"}>
                              {proxyStatus?.healthy ? "ONLINE" : "OFFLINE"}
                            </span>
                          </div>
                          <button
                            type="button"
                            onClick={handleCheckProxy}
                            disabled={isCheckingProxy}
                            className="text-[9px] px-1.5 py-0.5 rounded bg-panel hover:bg-obsidian-muted/20 border border-border text-obsidian-primary transition"
                            title={proxyStatus?.detail || "Periksa koneksi SOCKS5 Android"}
                          >
                            {isCheckingProxy ? "Checking..." : "[Check Connection]"}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* 2. Master Auto-Generate All from NLE Context Button */}
                <button
                  type="button"
                  onClick={() => handleAutoGenerate("all")}
                  disabled={isAutoGeneratingAll}
                  className="w-full py-2 px-3 rounded-xl bg-gradient-to-r from-amber-500/20 via-amber-500/10 to-amber-500/20 hover:from-amber-500/30 hover:to-amber-500/30 border border-amber-500/40 text-amber-300 font-bold flex items-center justify-center gap-2 transition-all shadow-sm disabled:opacity-50"
                  title="Generate Name, Role, Suggestion/Bio, and Base Visual Prompt automatically from NLE Studio Metadata"
                >
                  {isAutoGeneratingAll ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin text-amber-400" />
                      <span>Menarik Konteks NLE Studio &amp; Auto-Generating...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4 text-amber-400" />
                      <span>Auto-Generate All from NLE Context</span>
                    </>
                  )}
                </button>

                {/* 3. Field: Character Name */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <label className="text-obsidian-secondary font-semibold">Character Name</label>
                    <button
                      type="button"
                      onClick={() => handleAutoGenerate("name")}
                      disabled={isGeneratingField["name"] || isAutoGeneratingAll}
                      className="text-amber-400 hover:text-amber-300 flex items-center gap-1 text-[10px] p-0.5 rounded hover:bg-elevated transition-colors"
                      title="Regenerate Character Name only from NLE Context"
                    >
                      <RefreshCw className={cn("w-3 h-3", isGeneratingField["name"] && "animate-spin")} />
                      <span>Regen Name</span>
                    </button>
                  </div>
                  <input
                    type="text"
                    value={newCharName}
                    onChange={(e) => setNewCharName(e.target.value)}
                    placeholder="e.g. Elena Rostova / Kaito Tanaka"
                    className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none"
                  />
                </div>

                {/* 4. Field: Narrative Archetype / Role */}
                <div className="space-y-1">
                  <ObsidianDropdown
                    label="Narrative Archetype / Role"
                    size="sm"
                    options={[
                      { value: "PROTAGONIST", title: "Protagonist", description: "Central character driving narrative arc", badge: "Lead" },
                      { value: "ANTAGONIST", title: "Antagonist", description: "Primary opposing force or villain", badge: "Conflict" },
                      { value: "DEUTERAGONIST", title: "Deuteragonist", description: "Secondary focal character", badge: "Support" },
                      { value: "MENTOR", title: "Mentor / Guide", description: "Archetypal guide or authority figure", badge: "Wisdom" },
                      { value: "EXTRAS", title: "Extras Ensemble", description: "Background / Ensemble character", badge: "Extras" },
                    ]}
                    value={newCharRole}
                    onChange={(val) => setNewCharRole(val)}
                  />
                </div>

                {/* 5. Field: Narrative Suggestion / Bio / Voice Profile */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <label className="text-obsidian-secondary font-semibold">Character Suggestion &amp; Bio</label>
                    <button
                      type="button"
                      onClick={() => handleAutoGenerate("suggestion")}
                      disabled={isGeneratingField["suggestion"] || isAutoGeneratingAll}
                      className="text-amber-400 hover:text-amber-300 flex items-center gap-1 text-[10px] p-0.5 rounded hover:bg-elevated transition-colors"
                      title="Regenerate Role Suggestion & Bio only"
                    >
                      <RefreshCw className={cn("w-3 h-3", isGeneratingField["suggestion"] && "animate-spin")} />
                      <span>Regen Suggestion</span>
                    </button>
                  </div>
                  <textarea
                    value={newCharBio}
                    onChange={(e) => setNewCharBio(e.target.value)}
                    rows={2}
                    placeholder="Personality archetype, core motivation, voice profile aligned with NLE synopsis..."
                    className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none resize-none text-[11px]"
                  />
                </div>

                {/* 6. Field: Base Visual Prompt */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-[11px]">
                    <label className="text-obsidian-secondary font-semibold">Base Visual Prompt</label>
                    <button
                      type="button"
                      onClick={() => handleAutoGenerate("visual_prompt")}
                      disabled={isGeneratingField["visual_prompt"] || isAutoGeneratingAll}
                      className="text-amber-400 hover:text-amber-300 flex items-center gap-1 text-[10px] p-0.5 rounded hover:bg-elevated transition-colors"
                      title="Regenerate Base Visual Prompt only"
                    >
                      <RefreshCw className={cn("w-3 h-3", isGeneratingField["visual_prompt"] && "animate-spin")} />
                      <span>Regen Visual Prompt</span>
                    </button>
                  </div>
                  <textarea
                    value={newCharPrompt}
                    onChange={(e) => setNewCharPrompt(e.target.value)}
                    rows={3}
                    placeholder="Biometric prompt: age, ethnicity, facial bone structure, scars, hairstyle, costume details..."
                    className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none resize-none text-[11px] leading-relaxed"
                  />
                  <span className="text-[10px] text-obsidian-muted block leading-tight">
                    *Standar studio gray (<span className="text-amber-400 font-semibold">#D4D4D4</span>) otomatis disisipkan &amp; disanitasi dari newline bermasalah (aman untuk ProseMirror).
                  </span>
                </div>

                {/* 7. Field: DNA Seed */}
                <div className="p-2.5 rounded-lg bg-canvas border border-border flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] uppercase text-obsidian-muted font-semibold">DNA Seed:</span>
                    <input
                      type="number"
                      value={newCharSeed}
                      onChange={(e) => setNewCharSeed(parseInt(e.target.value) || 100000)}
                      className="w-24 px-2 py-1 rounded bg-panel border border-border text-amber-400 font-bold text-center focus:outline-none"
                    />
                  </div>

                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={handleRerollSeed}
                      className="px-2 py-1 rounded bg-panel hover:bg-elevated border border-border text-[10px] text-obsidian-secondary hover:text-amber-400 font-semibold flex items-center gap-1 transition-colors"
                      title="Reroll random DNA seed"
                    >
                      <Dices className="w-3.5 h-3.5 text-amber-500" />
                      <span>Reroll Seed</span>
                    </button>
                    <span className="px-1.5 py-0.5 rounded text-[9px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                      <Lock className="w-2.5 h-2.5" />
                      <span>LOCKED</span>
                    </span>
                  </div>
                </div>
              </div>

              {/* Right Column: Pre-Creation Visual Inspection Panel */}
              <div className="lg:col-span-6 flex flex-col justify-between space-y-3 p-4 rounded-xl bg-canvas border border-border/80 font-mono text-xs">
                <div className="space-y-3">
                  <div className="flex items-center justify-between border-b border-border/70 pb-2">
                    <div>
                      <h5 className="font-cinzel text-xs font-bold text-obsidian-primary uppercase flex items-center gap-1.5">
                        <Eye className="w-3.5 h-3.5 text-amber-500" />
                        <span>Pre-Creation Visual Gatekeeper</span>
                      </h5>
                      <span className="text-[10px] text-obsidian-muted">
                        Preview &amp; verifikasi Slot 1 Close-Up Master Anchor sebelum commit ke SQLite.
                      </span>
                    </div>

                    <span className="px-2 py-0.5 rounded text-[9px] font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30">
                      SLOT 1 MASTER ANCHOR
                    </span>
                  </div>

                  {/* TOP CARD: Card 1 Character Close-Up (Master Anchor) */}
                  <div className="p-3 rounded-lg bg-panel/70 border border-amber-500/30 flex flex-col justify-between space-y-2">
                    <div className="flex items-center justify-between text-[10px]">
                      <span className="font-bold text-amber-400 flex items-center gap-1.5">
                        <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                        <span>Card 1: Character Close-Up (Master Anchor)</span>
                      </span>
                      <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
                        {isPhotorealisticCastingStyle(project?.target_style_code)
                          ? "1:1 Square • 85mm f/4.5 RAW"
                          : "1:1 Square • Master Anchor"}
                      </span>
                    </div>

                    {/* Close-Up Preview Body */}
                    <div className="relative aspect-square max-h-[220px] w-auto mx-auto rounded-md bg-black/40 overflow-hidden flex items-center justify-center border border-border/60">
                      {isRollingCloseup || (isPreviewGenerating && !previewCloseupUrl) ? (
                        <div className="flex flex-col items-center justify-center p-3 text-center space-y-1.5">
                          <Loader2 className="w-6 h-6 text-amber-500 animate-spin" />
                          <span className="text-[9px] text-amber-300 leading-tight">
                            {previewStatusText || "Merender Slot 1 Close-Up Master Anchor..."}
                          </span>
                        </div>
                      ) : closeupImgError ? (
                        <div className="flex flex-col items-center justify-center p-3 text-center space-y-1.5 bg-rose-950/40 border border-rose-500/30 rounded-md w-full h-full">
                          <AlertTriangle className="w-5 h-5 text-rose-400" />
                          <span className="text-[10px] text-rose-300 font-semibold">Gagal memuat gambar preview</span>
                          <button
                            type="button"
                            onClick={() => handleGeneratePreview("closeup")}
                            disabled={isPreviewGenerating || !newCharName.trim()}
                            className="px-2.5 py-1 rounded bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 text-[9px] text-rose-200 font-semibold flex items-center gap-1 transition-colors"
                          >
                            <RefreshCw className="w-3 h-3 text-rose-300" />
                            <span>Re-roll</span>
                          </button>
                        </div>
                      ) : previewCloseupUrl ? (
                        <div
                          className="w-full h-full relative group/closeup cursor-pointer"
                          onClick={() => {
                            setLightboxImageUrl(previewCloseupUrl);
                            setLightboxTitle("Card 1: Character Close-Up (Master Anchor)");
                          }}
                          title="Klik untuk zoom pratinjau biometrik"
                        >
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={previewCloseupUrl}
                            alt="Character Close-Up Preview"
                            className={cn(
                              "w-full h-full object-cover group-hover/closeup:scale-105 transition-transform duration-200",
                              !closeupImgLoaded && "opacity-0"
                            )}
                            onLoad={(e) => {
                              if (e.currentTarget.naturalWidth > 0) {
                                setCloseupImgLoaded(true);
                                setCloseupImgError(false);
                              } else {
                                setCloseupImgLoaded(false);
                                setCloseupImgError(true);
                              }
                            }}
                            onError={() => {
                              setCloseupImgError(true);
                              setCloseupImgLoaded(false);
                            }}
                          />
                          {!closeupImgLoaded && !closeupImgError && (
                            <div className="absolute inset-0 flex items-center justify-center">
                              <Loader2 className="w-5 h-5 text-amber-500 animate-spin" />
                            </div>
                          )}
                          {closeupImgLoaded && (
                            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover/closeup:opacity-100 transition-opacity flex items-center justify-center">
                              <ZoomIn className="w-5 h-5 text-amber-400" />
                            </div>
                          )}
                          {closeupImgLoaded && (
                            <span
                              className={cn(
                                "absolute top-1.5 left-1.5 px-1.5 py-0.5 rounded text-[8px] font-mono font-bold border backdrop-blur-sm",
                                previewSlotMeta.closeup?.is_2k
                                  ? "bg-emerald-950/85 text-emerald-300 border-emerald-500/50"
                                  : "bg-black/75 text-amber-300 border-amber-500/30"
                              )}
                            >
                              {previewSlotMeta.closeup?.is_2k
                                ? `2K Ready • ${previewSlotMeta.closeup.resolution_width || 2048}×${previewSlotMeta.closeup.resolution_height || 2048}`
                                : `1K • ${previewSlotMeta.closeup?.resolution_width || 1024}×${previewSlotMeta.closeup?.resolution_height || 1024}`}
                            </span>
                          )}
                        </div>
                      ) : (
                        <div className="flex flex-col items-center justify-center text-obsidian-muted p-3 text-center space-y-1">
                          <Users className="w-7 h-7 opacity-30" />
                          <span className="text-[10px] text-obsidian-secondary font-semibold">Slot 1 Belum di-generate</span>
                          <span className="text-[9px] text-obsidian-muted">Master Biometric Casting Anchor</span>
                        </div>
                      )}
                    </div>

                    {/* Independent Generate / Re-roll Close-Up + Upscale 2K Buttons */}
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => handleGeneratePreview("closeup")}
                        disabled={isPreviewGenerating || !!upscalingSlots["preview_closeup"] || !newCharName.trim()}
                        className="flex-1 py-1.5 px-2 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/40 text-[10px] text-amber-300 hover:text-amber-200 font-bold flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50"
                      >
                        <RefreshCw className={cn("w-3 h-3 text-amber-400", isRollingCloseup && "animate-spin")} />
                        <span>{previewCloseupUrl ? "Re-roll Close-Up (Slot 1)" : "Generate Close-Up (Master Anchor)"}</span>
                      </button>

                      {previewCloseupUrl && previewToken && (
                        <button
                          type="button"
                          onClick={() => handleUpscalePreview("closeup")}
                          disabled={isPreviewGenerating || isRollingCloseup || !!upscalingSlots["preview_closeup"] || !!previewSlotMeta.closeup?.is_2k}
                          className={cn(
                            "py-1.5 px-2.5 rounded-lg border text-[10px] font-bold flex items-center justify-center gap-1 transition-colors disabled:opacity-60",
                            previewSlotMeta.closeup?.is_2k
                              ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300 cursor-default"
                              : "bg-indigo-500/15 hover:bg-indigo-500/25 border-indigo-400/40 text-indigo-300"
                          )}
                        >
                          {upscalingSlots["preview_closeup"] ? (
                            <>
                              <Loader2 className="w-3 h-3 animate-spin" />
                              <span>Upscaling 2K...</span>
                            </>
                          ) : previewSlotMeta.closeup?.is_2k ? (
                            <>
                              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                              <span>2K Ready</span>
                            </>
                          ) : (
                            <>
                              <Sparkles className="w-3 h-3 text-indigo-300" />
                              <span>Upscale 2K</span>
                            </>
                          )}
                        </button>
                      )}

                      {previewSlotMeta.closeup?.previous_1k_url && previewToken && (
                        <button
                          type="button"
                          onClick={() => handleRevertPreview("closeup")}
                          disabled={isPreviewGenerating || !!upscalingSlots["preview_closeup"]}
                          className="py-1.5 px-2 rounded-lg bg-canvas hover:bg-elevated border border-border text-[10px] font-semibold text-obsidian-secondary hover:text-amber-300 flex items-center gap-1"
                        >
                          <RotateCcw className="w-3 h-3" />
                          <span>Revert 1K</span>
                        </button>
                      )}
                    </div>
                  </div>

                  {/* DOWNSTREAM ANCHORS: Slot 2 (Expression Sheet) & Slot 3 (Full Body Front) */}
                  <div className="space-y-1.5 pt-1 border-t border-border/60">
                    <div className="flex items-center justify-between text-[10px]">
                      <span className="font-semibold text-obsidian-secondary uppercase tracking-wider">
                        Downstream Anchors (Slot 2 &amp; 3 &bull; Optional)
                      </span>
                      <span className="text-[9px] text-obsidian-muted">
                        Chains from Slot 1
                      </span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                      {/* Expression Sheet (3x2) */}
                      <div className="p-2 rounded-lg bg-panel/50 border border-border flex flex-col justify-between space-y-1.5">
                        <div className="flex items-center justify-between text-[9px]">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="font-bold text-obsidian-primary">Card 2: Expression</span>
                            {isExprOutdated && (
                              <span
                                className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 text-[8px] font-semibold flex items-center gap-1"
                                title="Slot 1 telah di-reroll. Re-roll Slot 2 untuk sinkronisasi biometrik."
                              >
                                <AlertTriangle className="w-2.5 h-2.5 text-amber-400 shrink-0" />
                                <span>Outdated &mdash; Re-roll untuk sinkron dengan Slot 1 baru</span>
                              </span>
                            )}
                          </div>
                          <span className="px-1 py-0.2 rounded text-[8px] bg-panel text-obsidian-secondary border border-border">
                            16:9 Grid
                          </span>
                        </div>

                        <div className="relative aspect-[16/9] w-full rounded-md bg-black/40 overflow-hidden flex items-center justify-center border border-border/40">
                          {isRollingExpression ? (
                            <div className="flex flex-col items-center justify-center p-1 text-center space-y-1">
                              <Loader2 className="w-4 h-4 text-amber-500 animate-spin" />
                              <span className="text-[8px] text-amber-300">Merender...</span>
                            </div>
                          ) : exprImgError ? (
                            <div className="flex flex-col items-center justify-center p-1 text-center space-y-1 text-rose-300">
                              <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                              <span className="text-[8px]">Error</span>
                            </div>
                          ) : previewExpressionUrl ? (
                            <div
                              className="w-full h-full relative group/expr cursor-pointer"
                              onClick={() => {
                                setLightboxImageUrl(previewExpressionUrl);
                                setLightboxTitle("Preview 2: Expression Sheet (3x2)");
                              }}
                            >
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img
                                src={previewExpressionUrl}
                                alt="Expression Sheet Preview"
                                className={cn(
                                  "w-full h-full object-cover group-hover/expr:scale-105 transition-transform duration-200",
                                  !exprImgLoaded && "opacity-0"
                                )}
                                onLoad={() => {
                                  setExprImgLoaded(true);
                                  setExprImgError(false);
                                }}
                                onError={() => {
                                  setExprImgError(true);
                                  setExprImgLoaded(false);
                                }}
                              />
                              <span
                                className={cn(
                                  "absolute top-1 left-1 px-1 py-0.5 rounded text-[8px] font-mono font-bold border backdrop-blur-sm",
                                  previewSlotMeta.expression?.is_2k
                                    ? "bg-emerald-950/85 text-emerald-300 border-emerald-500/50"
                                    : "bg-black/75 text-amber-300 border-amber-500/30"
                                )}
                              >
                                {previewSlotMeta.expression?.is_2k
                                  ? "2K Ready"
                                  : `1K • ${previewSlotMeta.expression?.resolution_width || 1344}×${previewSlotMeta.expression?.resolution_height || 768}`}
                              </span>
                            </div>
                          ) : (
                            <span className="text-[9px] text-obsidian-muted">Opsional</span>
                          )}
                        </div>

                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => handleGeneratePreview("expression")}
                            disabled={isPreviewGenerating || !!upscalingSlots["preview_expression"] || !newCharName.trim()}
                            className="flex-1 py-1 px-1.5 rounded bg-canvas hover:bg-elevated border border-border text-[9px] text-obsidian-secondary hover:text-amber-300 font-semibold flex items-center justify-center gap-1 transition-colors disabled:opacity-50"
                          >
                            <RefreshCw className={cn("w-2.5 h-2.5 text-amber-400", isRollingExpression && "animate-spin")} />
                            <span>Re-roll Expression</span>
                          </button>
                          {previewExpressionUrl && previewToken && (
                            <button
                              type="button"
                              onClick={() => handleUpscalePreview("expression")}
                              disabled={isPreviewGenerating || isRollingExpression || !!upscalingSlots["preview_expression"] || !!previewSlotMeta.expression?.is_2k}
                              className={cn(
                                "py-1 px-1.5 rounded border text-[9px] font-bold flex items-center gap-1 disabled:opacity-60",
                                previewSlotMeta.expression?.is_2k
                                  ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300"
                                  : "bg-indigo-500/15 hover:bg-indigo-500/25 border-indigo-400/40 text-indigo-300"
                              )}
                            >
                              {upscalingSlots["preview_expression"] ? (
                                <Loader2 className="w-2.5 h-2.5 animate-spin" />
                              ) : previewSlotMeta.expression?.is_2k ? (
                                <span>2K Ready</span>
                              ) : (
                                <span>Upscale 2K</span>
                              )}
                            </button>
                          )}
                          {previewSlotMeta.expression?.previous_1k_url && previewToken && (
                            <button
                              type="button"
                              onClick={() => handleRevertPreview("expression")}
                              disabled={isPreviewGenerating || !!upscalingSlots["preview_expression"]}
                              className="py-1 px-1.5 rounded bg-canvas hover:bg-elevated border border-border text-[9px] text-obsidian-secondary hover:text-amber-300"
                              title="Revert 1K"
                            >
                              Revert 1K
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Full Body Front */}
                      <div className="p-2 rounded-lg bg-panel/50 border border-border flex flex-col justify-between space-y-1.5">
                        <div className="flex items-center justify-between text-[9px]">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="font-bold text-obsidian-primary">Card 3: Full Body</span>
                            {isFrontOutdated && (
                              <span
                                className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 text-[8px] font-semibold flex items-center gap-1"
                                title="Slot 1 telah di-reroll. Re-roll Slot 3 untuk sinkronisasi biometrik."
                              >
                                <AlertTriangle className="w-2.5 h-2.5 text-amber-400 shrink-0" />
                                <span>Outdated &mdash; Re-roll untuk sinkron dengan Slot 1 baru</span>
                              </span>
                            )}
                          </div>
                          <span className="px-1 py-0.2 rounded text-[8px] bg-panel text-obsidian-secondary border border-border">
                            3:4 Front
                          </span>
                        </div>

                        <div className="relative aspect-[16/9] w-full rounded-md bg-black/40 overflow-hidden flex items-center justify-center border border-border/40">
                          {isRollingFront ? (
                            <div className="flex flex-col items-center justify-center p-1 text-center space-y-1">
                              <Loader2 className="w-4 h-4 text-amber-500 animate-spin" />
                              <span className="text-[8px] text-amber-300">Merender...</span>
                            </div>
                          ) : frontImgError ? (
                            <div className="flex flex-col items-center justify-center p-1 text-center space-y-1 text-rose-300">
                              <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                              <span className="text-[8px]">Error</span>
                            </div>
                          ) : previewFrontUrl ? (
                            <div
                              className="w-full h-full relative group/front cursor-pointer"
                              onClick={() => {
                                setLightboxImageUrl(previewFrontUrl);
                                setLightboxTitle("Preview 3: Full Body (Front View)");
                              }}
                            >
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img
                                src={previewFrontUrl}
                                alt="Full Body Preview"
                                className={cn(
                                  "w-full h-full object-contain group-hover/front:scale-105 transition-transform duration-200",
                                  !frontImgLoaded && "opacity-0"
                                )}
                                onLoad={() => {
                                  setFrontImgLoaded(true);
                                  setFrontImgError(false);
                                }}
                                onError={() => {
                                  setFrontImgError(true);
                                  setFrontImgLoaded(false);
                                }}
                              />
                              <span
                                className={cn(
                                  "absolute top-1 left-1 px-1 py-0.5 rounded text-[8px] font-mono font-bold border backdrop-blur-sm",
                                  previewSlotMeta.front?.is_2k
                                    ? "bg-emerald-950/85 text-emerald-300 border-emerald-500/50"
                                    : "bg-black/75 text-amber-300 border-amber-500/30"
                                )}
                              >
                                {previewSlotMeta.front?.is_2k
                                  ? "2K Ready"
                                  : `1K • ${previewSlotMeta.front?.resolution_width || 768}×${previewSlotMeta.front?.resolution_height || 1024}`}
                              </span>
                            </div>
                          ) : (
                            <span className="text-[9px] text-obsidian-muted">Opsional</span>
                          )}
                        </div>

                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => handleGeneratePreview("front")}
                            disabled={isPreviewGenerating || !!upscalingSlots["preview_front"] || !newCharName.trim()}
                            className="flex-1 py-1 px-1.5 rounded bg-canvas hover:bg-elevated border border-border text-[9px] text-obsidian-secondary hover:text-amber-300 font-semibold flex items-center justify-center gap-1 transition-colors disabled:opacity-50"
                          >
                            <RefreshCw className={cn("w-2.5 h-2.5 text-amber-400", isRollingFront && "animate-spin")} />
                            <span>Re-roll Full Body</span>
                          </button>
                          {previewFrontUrl && previewToken && (
                            <button
                              type="button"
                              onClick={() => handleUpscalePreview("front")}
                              disabled={isPreviewGenerating || isRollingFront || !!upscalingSlots["preview_front"] || !!previewSlotMeta.front?.is_2k}
                              className={cn(
                                "py-1 px-1.5 rounded border text-[9px] font-bold flex items-center gap-1 disabled:opacity-60",
                                previewSlotMeta.front?.is_2k
                                  ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300"
                                  : "bg-indigo-500/15 hover:bg-indigo-500/25 border-indigo-400/40 text-indigo-300"
                              )}
                            >
                              {upscalingSlots["preview_front"] ? (
                                <Loader2 className="w-2.5 h-2.5 animate-spin" />
                              ) : previewSlotMeta.front?.is_2k ? (
                                <span>2K Ready</span>
                              ) : (
                                <span>Upscale 2K</span>
                              )}
                            </button>
                          )}
                          {previewSlotMeta.front?.previous_1k_url && previewToken && (
                            <button
                              type="button"
                              onClick={() => handleRevertPreview("front")}
                              disabled={isPreviewGenerating || !!upscalingSlots["preview_front"]}
                              className="py-1 px-1.5 rounded bg-canvas hover:bg-elevated border border-border text-[9px] text-obsidian-secondary hover:text-amber-300"
                              title="Revert 1K"
                            >
                              Revert 1K
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Error Feedback */}
                  {(previewErrorMsg || previewError) && (
                    <div className="p-3 rounded-lg bg-rose-500/15 border border-rose-500/40 text-[11px] font-mono text-rose-300 space-y-2">
                      <div className="flex items-start gap-2">
                        <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                        <div className="flex-1 space-y-1">
                          <p className="font-semibold leading-relaxed">{previewErrorMsg || previewError}</p>
                          {((previewErrorMsg || previewError || "").includes("429") ||
                            (previewErrorMsg || previewError || "").toLowerCase().includes("kuota") ||
                            (previewErrorMsg || previewError || "").toLowerCase().includes("quota") ||
                            (previewErrorMsg || previewError || "").toLowerCase().includes("rate limit") ||
                            !isGoogleFlowProvider(addCharImageProvider)) && (
                            <div className="mt-2 pt-2 border-t border-rose-500/20 flex flex-wrap items-center justify-between gap-2">
                              <span className="text-[10px] text-amber-300">
                                Rekomendasi: Beralih ke Google Flow [6 Akun PRO] yang memiliki kuota aktif dan stabil.
                              </span>
                              {!isGoogleFlowProvider(addCharImageProvider) && (
                                <button
                                  type="button"
                                  onClick={() => {
                                    setAddCharImageProvider("google-flow");
                                    setPreviewErrorMsg(null);
                                    setPreviewError(null);
                                  }}
                                  className="px-2.5 py-1 rounded bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-[10px] transition-colors shadow-sm"
                                >
                                  Pindah ke Google Flow
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Status Indicator */}
                  {previewStatusText && (
                    <div className="p-2 rounded bg-amber-500/10 border border-amber-500/30 text-[10px] font-mono text-amber-300 flex items-center gap-2">
                      <Loader2 className="w-3.5 h-3.5 text-amber-400 animate-spin shrink-0" />
                      <span>{previewStatusText}</span>
                    </div>
                  )}
                </div>

                {/* Primary Action Button: Generate Previews */}
                <div className="space-y-2 pt-2 border-t border-border/70">
                  <button
                    type="button"
                    onClick={() => handleGeneratePreview(previewCloseupUrl ? "both" : "closeup")}
                    disabled={isPreviewGenerating || !newCharName.trim()}
                    className="w-full py-2.5 px-3 rounded-xl bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-sm disabled:opacity-50"
                  >
                    {isPreviewGenerating ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Sparkles className="w-4 h-4" />
                    )}
                    <span>
                      {previewCloseupUrl
                        ? "Generate Downstream Anchors (Slot 2 & 3)"
                        : "Generate Slot 1 Close-Up (Master Anchor)"}
                    </span>
                  </button>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between border-t border-border/80 px-5 py-3 gap-2 bg-canvas/40">
              <div className="text-[11px] font-mono text-obsidian-muted">
                {!isVisualVerified ? (
                  <span className="text-amber-400/90 flex items-center gap-1.5">
                    <Info className="w-3.5 h-3.5 shrink-0 text-amber-400" />
                    <span>Generate &amp; verifikasi Slot 1 Close-Up terlebih dahulu sebelum commit.</span>
                  </span>
                ) : (
                  <span className="text-emerald-400 flex items-center gap-1.5 font-semibold">
                    <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                    <span>Visual verified! Siap didaftarkan sebagai Master Character di SQLite.</span>
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2 self-end sm:self-center">
                <button
                  type="button"
                  onClick={handleCloseAddModal}
                  disabled={isSubmittingChar}
                  className="px-4 py-2 rounded-xl bg-canvas hover:bg-elevated border border-border text-xs font-mono text-obsidian-secondary transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleCommitCharacter}
                  disabled={!isVisualVerified || isSubmittingChar || isPreviewGenerating}
                  className={cn(
                    "px-4 py-2 rounded-xl font-bold font-mono text-xs flex items-center gap-2 transition-all shadow-sm",
                    isVisualVerified
                      ? "bg-emerald-500 hover:bg-emerald-600 text-canvas"
                      : "bg-panel border border-border text-obsidian-muted cursor-not-allowed opacity-50"
                  )}
                  title={
                    !isVisualVerified
                      ? "Generate & verifikasi preview Slot 1 Close-Up terlebih dahulu"
                      : "Simpan karakter dan kunci Master Anchors"
                  }
                >
                  {isSubmittingChar ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Plus className="w-4 h-4" />
                  )}
                  <span>Create Character &amp; Register Anchors</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Add / Edit State Modal */}
      {addStateModalOpen && (() => {
        const existingStatesMap = new Set((selectedChar?.states || []).map((s) => s.state_code));
        const hasNextUnsaved = (() => {
          const currentSaved = new Set(existingStatesMap);
          currentSaved.add(newStateCode);
          return STATE_OPTIONS.some((opt) => !currentSaved.has(opt.value));
        })();
        const dropdownOptions = STATE_OPTIONS.map((opt) => {
          const isSaved = existingStatesMap.has(opt.value);
          return {
            value: opt.value,
            title: `${opt.title}${isSaved ? "  ✓ Saved" : ""}`,
            description: opt.description,
          };
        });

        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="w-full max-w-lg rounded-2xl bg-panel border border-border shadow-2xl p-5 space-y-4 text-obsidian-primary font-sans animate-in zoom-in-95 duration-150">
              {/* Modal Header */}
              <div className="flex items-center justify-between border-b border-border pb-3">
                <div className="flex items-center gap-2">
                  <Layers className="w-4 h-4 text-amber-500" />
                  <h4 className="font-cinzel text-sm font-bold uppercase text-obsidian-primary">
                    {editingStateId ? `Edit State: ${selectedChar?.name}` : `Add State: ${selectedChar?.name}`}
                  </h4>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      handleFetchStateSuggestion(newStateCode, "all", true, undefined, {
                        wardrobe: newWardrobe,
                        injuries_and_wear: newInjuries,
                        expression_anchor: newExpression,
                      })
                    }
                    disabled={isSuggestingAll || isSubmittingState}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30 text-xs font-mono transition-all disabled:opacity-50"
                    title="Generate variasi baru untuk seluruh box sekaligus"
                  >
                    <RefreshCw className={cn("w-3.5 h-3.5", isSuggestingAll && "animate-spin")} />
                    <span>{isSuggestingAll ? "Regenerating..." : "Regenerate All"}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      suggestAbortControllerRef.current?.abort();
                      setAddStateModalOpen(false);
                    }}
                    className="text-obsidian-muted hover:text-obsidian-primary p-1 rounded-lg hover:bg-elevated transition-colors"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
              </div>

              {/* Error Banner */}
              {suggestionError && (
                <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono flex items-center justify-between">
                  <span>{suggestionError}</span>
                  <button
                    type="button"
                    onClick={() => setSuggestionError(null)}
                    className="text-rose-400 hover:text-rose-200 ml-2"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}

              <div className="space-y-4 text-xs font-mono">
                {/* STATE CODE DROPDOWN WITH VISUAL INDICATOR */}
                <div className="space-y-1">
                  <ObsidianDropdown
                    label="State Code"
                    size="sm"
                    options={dropdownOptions}
                    value={newStateCode}
                    onChange={handleStateCodeChange}
                  />
                </div>

                {/* STATE LABEL / DRAMATIC SUBTITLE */}
                <div className="space-y-1">
                  <label className="text-obsidian-secondary font-semibold">State Label / Dramatic Subtitle</label>
                  <input
                    type="text"
                    value={newStateLabel}
                    onChange={(e) => setNewStateLabel(e.target.value)}
                    placeholder="e.g. Normal Baseline / Wear & Tear / Climax Catharsis"
                    className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none"
                  />
                </div>

                {/* BOX 1: WARDROBE */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-obsidian-secondary font-semibold">Wardrobe *</label>
                    {(isSuggestingAll || isSuggestingField.wardrobe) && (
                      <span className="text-[10px] text-amber-400 flex items-center gap-1 animate-pulse">
                        <Sparkles className="w-3 h-3" /> {isSuggestingField.wardrobe ? "Regenerating..." : "Auto-filling..."}
                      </span>
                    )}
                  </div>
                  <div className="relative">
                    <textarea
                      value={newWardrobe}
                      onChange={(e) => setNewWardrobe(e.target.value)}
                      rows={3}
                      placeholder="Signature costume, fabrics, textures, and condition..."
                      className={cn(
                        "w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none resize-none transition-opacity",
                        (isSuggestingAll || isSuggestingField.wardrobe) && "opacity-60"
                      )}
                    />
                    {(isSuggestingAll || isSuggestingField.wardrobe) && (
                      <div className="absolute inset-0 bg-canvas/30 rounded-lg flex items-center justify-center pointer-events-none">
                        <Loader2 className="w-4 h-4 text-amber-500 animate-spin" />
                      </div>
                    )}
                  </div>
                  <div className="flex justify-start">
                    <button
                      type="button"
                      onClick={() =>
                        handleFetchStateSuggestion(newStateCode, "wardrobe", true, newWardrobe, {
                          wardrobe: newWardrobe,
                          injuries_and_wear: newInjuries,
                          expression_anchor: newExpression,
                        })
                      }
                      disabled={isSuggestingField.wardrobe || isSuggestingAll || isSubmittingState}
                      className="flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-mono text-obsidian-muted hover:text-amber-400 hover:bg-elevated border border-border/60 transition-colors disabled:opacity-40"
                      title="Ganti rekomendasi wardrobe saja"
                    >
                      <RefreshCw className={cn("w-3 h-3", isSuggestingField.wardrobe && "animate-spin text-amber-400")} />
                      <span>{isSuggestingField.wardrobe ? "Regenerating..." : "Regenerate"}</span>
                    </button>
                  </div>
                </div>

                {/* BOX 2: INJURIES & PHYSICAL DAMAGE */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-obsidian-secondary font-semibold">Injuries &amp; Physical Damage</label>
                    {(isSuggestingAll || isSuggestingField.injuries) && (
                      <span className="text-[10px] text-amber-400 flex items-center gap-1 animate-pulse">
                        <Sparkles className="w-3 h-3" /> {isSuggestingField.injuries ? "Regenerating..." : "Auto-filling..."}
                      </span>
                    )}
                  </div>
                  <div className="relative">
                    <textarea
                      value={newInjuries}
                      onChange={(e) => setNewInjuries(e.target.value)}
                      rows={2}
                      placeholder="Scratches, dust, blood, burns, or physical trauma..."
                      className={cn(
                        "w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none resize-none transition-opacity",
                        (isSuggestingAll || isSuggestingField.injuries) && "opacity-60"
                      )}
                    />
                    {(isSuggestingAll || isSuggestingField.injuries) && (
                      <div className="absolute inset-0 bg-canvas/30 rounded-lg flex items-center justify-center pointer-events-none">
                        <Loader2 className="w-4 h-4 text-amber-500 animate-spin" />
                      </div>
                    )}
                  </div>
                  <div className="flex justify-start">
                    <button
                      type="button"
                      onClick={() =>
                        handleFetchStateSuggestion(newStateCode, "injuries", true, newInjuries, {
                          wardrobe: newWardrobe,
                          injuries_and_wear: newInjuries,
                          expression_anchor: newExpression,
                        })
                      }
                      disabled={isSuggestingField.injuries || isSuggestingAll || isSubmittingState}
                      className="flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-mono text-obsidian-muted hover:text-amber-400 hover:bg-elevated border border-border/60 transition-colors disabled:opacity-40"
                      title="Ganti rekomendasi injuries & physical damage saja"
                    >
                      <RefreshCw className={cn("w-3 h-3", isSuggestingField.injuries && "animate-spin text-amber-400")} />
                      <span>{isSuggestingField.injuries ? "Regenerating..." : "Regenerate"}</span>
                    </button>
                  </div>
                </div>

                {/* BOX 3: EXPRESSION ANCHOR */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-obsidian-secondary font-semibold">Expression Anchor</label>
                    {(isSuggestingAll || isSuggestingField.expression) && (
                      <span className="text-[10px] text-amber-400 flex items-center gap-1 animate-pulse">
                        <Sparkles className="w-3 h-3" /> {isSuggestingField.expression ? "Regenerating..." : "Auto-filling..."}
                      </span>
                    )}
                  </div>
                  <div className="relative">
                    <textarea
                      value={newExpression}
                      onChange={(e) => setNewExpression(e.target.value)}
                      rows={2}
                      placeholder="Emotional state, ocular tension, jaw posture..."
                      className={cn(
                        "w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none resize-none transition-opacity",
                        (isSuggestingAll || isSuggestingField.expression) && "opacity-60"
                      )}
                    />
                    {(isSuggestingAll || isSuggestingField.expression) && (
                      <div className="absolute inset-0 bg-canvas/30 rounded-lg flex items-center justify-center pointer-events-none">
                        <Loader2 className="w-4 h-4 text-amber-500 animate-spin" />
                      </div>
                    )}
                  </div>
                  <div className="flex justify-start">
                    <button
                      type="button"
                      onClick={() =>
                        handleFetchStateSuggestion(newStateCode, "expression", true, newExpression, {
                          wardrobe: newWardrobe,
                          injuries_and_wear: newInjuries,
                          expression_anchor: newExpression,
                        })
                      }
                      disabled={isSuggestingField.expression || isSuggestingAll || isSubmittingState}
                      className="flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-mono text-obsidian-muted hover:text-amber-400 hover:bg-elevated border border-border/60 transition-colors disabled:opacity-40"
                      title="Ganti rekomendasi expression anchor saja"
                    >
                      <RefreshCw className={cn("w-3 h-3", isSuggestingField.expression && "animate-spin text-amber-400")} />
                      <span>{isSuggestingField.expression ? "Regenerating..." : "Regenerate"}</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Modal Actions */}
              <div className="flex items-center justify-between pt-3 border-t border-border">
                <button
                  type="button"
                  onClick={() => {
                    suggestAbortControllerRef.current?.abort();
                    setAddStateModalOpen(false);
                  }}
                  className="px-3.5 py-1.5 rounded-lg bg-canvas hover:bg-elevated border border-border text-xs text-obsidian-secondary transition-colors"
                >
                  Cancel
                </button>

                <div className="flex items-center gap-2">
                  {!editingStateId && hasNextUnsaved && (
                    <button
                      type="button"
                      onClick={() => handleSaveState(true)}
                      disabled={isSubmittingState || isSuggestingAll || !newWardrobe.trim()}
                      className="px-3.5 py-1.5 rounded-lg bg-elevated hover:bg-elevated/80 border border-amber-500/40 text-amber-400 text-xs font-bold font-mono flex items-center gap-1.5 disabled:opacity-50 transition-colors"
                      title="Simpan state saat ini lalu otomatis lompat ke state berikutnya"
                    >
                      {isSubmittingState ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ArrowRight className="w-3.5 h-3.5" />}
                      <span>Save &amp; Next State</span>
                    </button>
                  )}

                  <button
                    type="button"
                    onClick={() => handleSaveState(false)}
                    disabled={isSubmittingState || isSuggestingAll || !newWardrobe.trim()}
                    className="px-4 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-xs flex items-center gap-2 disabled:opacity-50 shadow-md transition-all"
                  >
                    {isSubmittingState ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                    <span>{editingStateId ? "Save Changes" : "+ Save State"}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Master Prompt Viewer & One-Click Copy Modal */}
      {activePromptModalSlot && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-2xl max-h-[90vh] flex flex-col rounded-2xl bg-panel border border-border shadow-2xl text-obsidian-primary font-mono text-xs overflow-hidden">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 border-b border-border bg-canvas/60">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-amber-400 text-sm">
                    {sheetPrompts[activePromptModalSlot]?.card_title || `Card: ${activePromptModalSlot.toUpperCase()}`}
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30">
                    Aspect: {sheetPrompts[activePromptModalSlot]?.recommended_aspect_ratio || (activePromptModalSlot === "closeup" ? "1:1" : "3:4")}
                  </span>
                  {sheetPrompts[activePromptModalSlot]?.routing_mode && (
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 uppercase">
                      CASTING_CLOSEUP_REALISTIC_V1:{" "}
                      {sheetPrompts[activePromptModalSlot]?.routing_mode === "full"
                        ? "FULL"
                        : sheetPrompts[activePromptModalSlot]?.routing_mode === "light_override"
                        ? "LIGHT_OVERRIDE"
                        : "STRICT_BYPASS"}
                    </span>
                  )}
                </div>
                <div className="text-[11px] text-obsidian-muted flex items-center gap-2">
                  <span>Character: <strong className="text-obsidian-primary">{selectedChar.name}</strong></span>
                  <span>&bull;</span>
                  <span className="text-emerald-400 font-bold">DNA SEED: #{selectedChar?.dna_seed || "—"}</span>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setActivePromptModalSlot(null)}
                className="p-1.5 rounded-lg text-obsidian-muted hover:text-obsidian-primary hover:bg-canvas transition-colors"
                title="Close modal"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Quick Action Copy Bar */}
            <div className="p-3 bg-panel border-b border-border flex flex-wrap items-center justify-between gap-2 text-[11px]">
              <span className="text-obsidian-muted">Copy Options for External Rendering:</span>
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  onClick={async () => {
                    const text = sheetPrompts[activePromptModalSlot]?.copy_ready_text || "";
                    await copyTextToClipboard(text);
                    setCopiedModalField("all");
                    setTimeout(() => setCopiedModalField(null), 2000);
                  }}
                  className="px-3 py-1 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-xs flex items-center gap-1.5 transition-colors shadow-sm"
                >
                  {copiedModalField === "all" ? <Check className="w-3.5 h-3.5 text-canvas" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedModalField === "all" ? "Copied All ✓" : "Copy Complete Master Prompt"}</span>
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    const text = sheetPrompts[activePromptModalSlot]?.positive_prompt || "";
                    await copyTextToClipboard(text);
                    setCopiedModalField("pos");
                    setTimeout(() => setCopiedModalField(null), 2000);
                  }}
                  className="px-2.5 py-1 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-secondary hover:text-obsidian-primary text-xs flex items-center gap-1.5 transition-colors"
                >
                  {copiedModalField === "pos" ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedModalField === "pos" ? "Copied ✓" : "Positive Only"}</span>
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    const text = sheetPrompts[activePromptModalSlot]?.negative_prompt || "";
                    await copyTextToClipboard(text);
                    setCopiedModalField("neg");
                    setTimeout(() => setCopiedModalField(null), 2000);
                  }}
                  className="px-2.5 py-1 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-secondary hover:text-obsidian-primary text-xs flex items-center gap-1.5 transition-colors"
                >
                  {copiedModalField === "neg" ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedModalField === "neg" ? "Copied ✓" : "Negative Only"}</span>
                </button>
                {!isLocked && !isEditingSlotPrompt && (
                  <button
                    type="button"
                    onClick={() => beginPromptEdit(activePromptModalSlot)}
                    className="px-2.5 py-1 rounded-lg bg-canvas hover:bg-elevated border border-amber-500/40 text-amber-400 text-xs flex items-center gap-1.5 transition-colors"
                  >
                    <Edit className="w-3.5 h-3.5" />
                    <span>{sheetPrompts[activePromptModalSlot]?.has_override ? "Edit Override" : "Customize Prompt"}</span>
                  </button>
                )}
                {!isLocked && sheetPrompts[activePromptModalSlot]?.has_override && (
                  <button
                    type="button"
                    onClick={() => handleClearPromptOverride(activePromptModalSlot)}
                    disabled={isSavingPromptOverride}
                    className="px-2.5 py-1 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-muted hover:text-rose-400 text-xs flex items-center gap-1.5 transition-colors disabled:opacity-50"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>Reset</span>
                  </button>
                )}
              </div>
            </div>

            {sheetPrompts[activePromptModalSlot]?.has_override && (
              <div className="px-3 py-1.5 bg-amber-500/10 border-b border-amber-500/30 text-[10px] font-mono text-amber-300">
                Custom prompt override active for this slot. Reset to restore the compiled master prompt.
              </div>
            )}

            {promptOverrideError && (
              <div className="px-3 py-1.5 bg-rose-500/10 border-b border-rose-500/30 text-[10px] font-mono text-rose-400 flex items-center gap-1.5">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                <span>{promptOverrideError}</span>
              </div>
            )}

            {/* Scrollable Modal Content */}
            <div className="p-4 space-y-4 overflow-y-auto max-h-[calc(90vh-140px)] scrollbar-thin">
              {isLoadingPrompts && !sheetPrompts[activePromptModalSlot] ? (
                <div className="flex flex-col items-center justify-center p-8 space-y-2 text-obsidian-muted font-mono">
                  <Loader2 className="w-6 h-6 animate-spin text-amber-500" />
                  <span>Compiling master prompt directives...</span>
                </div>
              ) : (
                <>
                  {/* Positive Prompt */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-[10px] text-amber-400 font-bold uppercase tracking-wider">
                        {isEditingSlotPrompt ? "Positive Prompt Override" : "Positive Master Prompt (Project-Synced & DNA Seed Locked)"}
                      </label>
                      <span className="text-[10px] text-obsidian-muted">
                        {isEditingSlotPrompt
                          ? `${promptDraft.positive.length} chars`
                          : `${sheetPrompts[activePromptModalSlot]?.positive_prompt?.length || 0} chars`}
                      </span>
                    </div>
                    {isEditingSlotPrompt ? (
                      <textarea
                        value={promptDraft.positive}
                        onChange={(e) => setPromptDraft((prev) => ({ ...prev, positive: e.target.value }))}
                        rows={10}
                        className="w-full p-3 rounded-xl bg-canvas border border-amber-500/40 text-obsidian-primary text-[11px] leading-relaxed font-mono focus:border-amber-500 focus:outline-none resize-y"
                      />
                    ) : (
                      <div className="p-3 rounded-xl bg-canvas border border-border text-obsidian-primary text-[11px] leading-relaxed whitespace-pre-wrap select-all font-mono">
                        {sheetPrompts[activePromptModalSlot]?.effective_prompt ||
                          sheetPrompts[activePromptModalSlot]?.positive_prompt ||
                          "Generating prompt..."}
                      </div>
                    )}
                  </div>

                  {/* Negative Prompt */}
                  <div className="space-y-1.5">
                    <label className="text-[10px] text-rose-400 font-bold uppercase tracking-wider">
                      {isEditingSlotPrompt ? "Negative Prompt Override" : "Negative Prompt"}
                    </label>
                    {isEditingSlotPrompt ? (
                      <textarea
                        value={promptDraft.negative}
                        onChange={(e) => setPromptDraft((prev) => ({ ...prev, negative: e.target.value }))}
                        rows={4}
                        className="w-full p-2.5 rounded-xl bg-canvas border border-rose-500/40 text-obsidian-secondary text-[11px] leading-relaxed font-mono focus:border-rose-500 focus:outline-none resize-y"
                      />
                    ) : (
                      <div className="p-2.5 rounded-xl bg-canvas border border-border text-obsidian-secondary text-[11px] leading-relaxed whitespace-pre-wrap select-all font-mono">
                        {sheetPrompts[activePromptModalSlot]?.effective_negative_prompt ||
                          sheetPrompts[activePromptModalSlot]?.negative_prompt}
                      </div>
                    )}
                  </div>

                  {isEditingSlotPrompt && (
                    <div className="flex flex-wrap items-center justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          setIsEditingSlotPrompt(false);
                          setPromptOverrideError(null);
                        }}
                        disabled={isSavingPromptOverride}
                        className="px-3 py-1.5 rounded-lg bg-canvas border border-border text-obsidian-muted hover:text-obsidian-primary text-xs font-bold disabled:opacity-50"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={() => handleSavePromptOverride(activePromptModalSlot)}
                        disabled={isSavingPromptOverride}
                        className="px-3.5 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas text-xs font-bold flex items-center gap-1.5 disabled:opacity-50"
                      >
                        {isSavingPromptOverride ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Check className="w-3.5 h-3.5" />
                        )}
                        <span>Save Override</span>
                      </button>
                    </div>
                  )}

                  {/* Technical Specifications */}
                  <div className="p-3 rounded-xl bg-canvas border border-border grid grid-cols-2 sm:grid-cols-4 gap-2 text-[10px]">
                    <div>
                      <span className="text-obsidian-muted block">Slot / Type:</span>
                      <span className="text-obsidian-primary font-bold">{activePromptModalSlot.toUpperCase()}</span>
                    </div>
                    <div>
                      <span className="text-obsidian-muted block">Resolution:</span>
                      <span className="text-amber-400 font-bold">
                        {sheetPrompts[activePromptModalSlot]?.width}x{sheetPrompts[activePromptModalSlot]?.height}
                      </span>
                    </div>
                    <div>
                      <span className="text-obsidian-muted block">Aspect Ratio:</span>
                      <span className="text-emerald-400 font-bold">
                        {sheetPrompts[activePromptModalSlot]?.recommended_aspect_ratio}
                      </span>
                    </div>
                    <div>
                      <span className="text-obsidian-muted block">DNA Seed:</span>
                      <span className="text-blue-400 font-bold">
                        #{selectedChar?.dna_seed || "—"}
                      </span>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* High-Resolution Biometric Lightbox Modal */}
      {lightboxImageUrl && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/90 backdrop-blur-md animate-in fade-in duration-200"
          onClick={() => setLightboxImageUrl(null)}
        >
          <div
            className="relative max-w-5xl max-h-[90vh] bg-panel rounded-2xl border border-border p-3 flex flex-col space-y-2 shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-2 py-1 border-b border-border text-xs font-mono">
              <span className="text-amber-400 font-bold flex items-center gap-2">
                <ZoomIn className="w-4 h-4 text-amber-500" />
                <span>{lightboxTitle || "Biometric Asset Lightbox (Full Resolution)"}</span>
              </span>
              <button
                type="button"
                onClick={() => setLightboxImageUrl(null)}
                className="p-1 rounded hover:bg-elevated text-obsidian-muted hover:text-obsidian-primary"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="relative flex items-center justify-center max-h-[80vh] overflow-auto rounded-lg bg-black/50 p-1">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={lightboxImageUrl}
                alt="Full Resolution View"
                className="max-w-full max-h-[75vh] object-contain rounded-lg"
              />
            </div>
            <div className="flex justify-between items-center text-[10px] font-mono text-obsidian-muted px-2">
              <span>Standard: Neutral Matte Studio Gray (#D4D4D4)</span>
              <a
                href={lightboxImageUrl}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1 text-amber-400 hover:underline"
              >
                <ExternalLink className="w-3 h-3" />
                <span>Buka di Tab Baru</span>
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Polya AI Screenwriter: Generate Cast Modal */}
      {generateCastModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-lg rounded-2xl bg-panel border border-border shadow-2xl p-5 space-y-4 text-obsidian-primary font-sans animate-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-amber-500" />
                <h4 className="font-cinzel text-sm font-bold uppercase text-obsidian-primary">
                  Generate Cast Ensemble (Polya AI Screenwriter)
                </h4>
              </div>
              <button
                type="button"
                onClick={() => setGenerateCastModalOpen(false)}
                className="text-obsidian-muted hover:text-obsidian-primary p-1 rounded-lg hover:bg-elevated transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs font-mono text-obsidian-secondary leading-relaxed">
              Polya AI berperan sebagai Master Screenwriter Hollywood, membaca judul &amp; sinopsis proyek{" "}
              <strong className="text-obsidian-primary">{project?.title || "proyek"}</strong>, lalu menyusun 5–8 karakter ensemble lengkap beserta persona, base visual prompt, voice DNA profile, dan 5 dynamic progression states.
            </p>

            {characters.length > 0 && (
              <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs font-mono text-amber-300 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                <span>
                  <strong>Perhatian:</strong> Proyek sudah memiliki {characters.length} karakter. Menjalankan Generate Cast akan menggantikan cast yang ada dengan ensemble baru.
                </span>
              </div>
            )}

            <div className="space-y-3 text-xs font-mono">
              <div className="space-y-1">
                <label className="text-obsidian-secondary font-semibold">Jumlah Karakter (Cast Size)</label>
                <select
                  value={preferredCastCount || ""}
                  onChange={(e) => setPreferredCastCount(e.target.value ? parseInt(e.target.value) : null)}
                  className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary text-xs focus:border-amber-500 focus:outline-none"
                >
                  <option value="">Otomatis (Ditentukan Polya AI, 5–8 Karakter)</option>
                  <option value="5">5 Karakter (Tight Ensemble)</option>
                  <option value="6">6 Karakter (Standard Narrative)</option>
                  <option value="7">7 Karakter (Expanded Universe)</option>
                  <option value="8">8 Karakter (Epic Ensemble)</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-obsidian-secondary font-semibold">Catatan / Arahan Khusus Penulis (Opsional)</label>
                <textarea
                  value={castAdditionalNotes}
                  onChange={(e) => setCastAdditionalNotes(e.target.value)}
                  rows={3}
                  placeholder="Contoh: Tekankan konflik moral antara Protagonist dan Mentor, gunakan setting noir lembab..."
                  className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none resize-none text-xs"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
              <button
                type="button"
                onClick={() => setGenerateCastModalOpen(false)}
                className="px-4 py-2 rounded-xl bg-canvas border border-border text-xs font-semibold text-obsidian-secondary hover:text-obsidian-primary transition"
              >
                Batal
              </button>
              <button
                type="button"
                onClick={handleGenerateCast}
                disabled={isGeneratingCast}
                className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 active:scale-95 text-canvas font-bold text-xs flex items-center gap-2 shadow-lg transition disabled:opacity-50"
              >
                {isGeneratingCast ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                <span>Generate Cast Sekarang</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Polya AI Screenwriter: Add 1 Character Modal */}
      {addOneModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-lg rounded-2xl bg-panel border border-border shadow-2xl p-5 space-y-4 text-obsidian-primary font-sans animate-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <Plus className="w-4 h-4 text-amber-500" />
                <h4 className="font-cinzel text-sm font-bold uppercase text-obsidian-primary">
                  Add 1 Character (Polya AI Screenwriter)
                </h4>
              </div>
              <button
                type="button"
                onClick={() => setAddOneModalOpen(false)}
                className="text-obsidian-muted hover:text-obsidian-primary p-1 rounded-lg hover:bg-elevated transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs font-mono text-obsidian-secondary leading-relaxed">
              Menambahkan 1 karakter baru ke dalam ensemble dengan proteksi anti-duplikasi persona &amp; visual terhadap {characters.length} karakter yang sudah ada.
            </p>

            <div className="space-y-3 text-xs font-mono">
              <div className="space-y-1">
                <label className="text-obsidian-secondary font-semibold">Peran / Role yang Diinginkan</label>
                <select
                  value={addOnePreferredRole}
                  onChange={(e) => setAddOnePreferredRole(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary text-xs focus:border-amber-500 focus:outline-none"
                >
                  <option value="DEUTERAGONIST">DEUTERAGONIST (Secondary Lead)</option>
                  <option value="ANTAGONIST">ANTAGONIST (Opposing Force)</option>
                  <option value="MENTOR">MENTOR (Guide / Authority)</option>
                  <option value="SUPPORTING">SUPPORTING (Key Ally / Contact)</option>
                  <option value="EXTRAS">EXTRAS (Atmospheric / Ensemble)</option>
                  <option value="PROTAGONIST">PROTAGONIST (Co-lead)</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-obsidian-secondary font-semibold">Arahan Khusus Karakter (Opsional)</label>
                <textarea
                  value={addOneCustomDirective}
                  onChange={(e) => setAddOneCustomDirective(e.target.value)}
                  rows={3}
                  placeholder="Contoh: Hacker muda eksentrik berambut perak, spesialis kriptografi bawah tanah..."
                  className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none resize-none text-xs"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
              <button
                type="button"
                onClick={() => setAddOneModalOpen(false)}
                className="px-4 py-2 rounded-xl bg-canvas border border-border text-xs font-semibold text-obsidian-secondary hover:text-obsidian-primary transition"
              >
                Batal
              </button>
              <button
                type="button"
                onClick={handleGenerateOneCharacter}
                disabled={isGeneratingOneChar}
                className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 active:scale-95 text-canvas font-bold text-xs flex items-center gap-2 shadow-lg transition disabled:opacity-50"
              >
                {isGeneratingOneChar ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                <span>Generate Karakter</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Polya AI Screenwriter: Re-generate Single Character Modal */}
      {regenModalOpen && selectedChar && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-lg rounded-2xl bg-panel border border-border shadow-2xl p-5 space-y-4 text-obsidian-primary font-sans animate-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <RefreshCw className="w-4 h-4 text-amber-500" />
                <h4 className="font-cinzel text-sm font-bold uppercase text-obsidian-primary">
                  Re-generate Character: {selectedChar.name}
                </h4>
              </div>
              <button
                type="button"
                onClick={() => setRegenModalOpen(false)}
                className="text-obsidian-muted hover:text-obsidian-primary p-1 rounded-lg hover:bg-elevated transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <p className="text-xs font-mono text-obsidian-secondary leading-relaxed">
              Polya AI akan men-generate ulang identitas, base visual prompt, voice DNA, dan 5 dynamic states untuk{" "}
              <strong className="text-obsidian-primary">{selectedChar.name}</strong> ({selectedChar.role}) tanpa memengaruhi karakter lain.
            </p>

            <div className="space-y-3 text-xs font-mono">
              <label className="flex items-center gap-2 cursor-pointer p-2.5 rounded-lg bg-canvas border border-border">
                <input
                  type="checkbox"
                  checked={regenPreserveRole}
                  onChange={(e) => setRegenPreserveRole(e.target.checked)}
                  className="rounded border-border text-amber-500 focus:ring-amber-500"
                />
                <span className="text-obsidian-primary text-xs font-semibold">
                  Pertahankan Peran ({selectedChar.role})
                </span>
              </label>

              <div className="space-y-1">
                <label className="text-obsidian-secondary font-semibold">Arahan Penulis Baru (Opsional)</label>
                <textarea
                  value={regenCustomDirective}
                  onChange={(e) => setRegenCustomDirective(e.target.value)}
                  rows={3}
                  placeholder="Contoh: Ubah usia menjadi 40-an, wajah lebih lelah dan karismatik, mata abu-abu tajam..."
                  className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary focus:border-amber-500 focus:outline-none resize-none text-xs"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
              <button
                type="button"
                onClick={() => setRegenModalOpen(false)}
                className="px-4 py-2 rounded-xl bg-canvas border border-border text-xs font-semibold text-obsidian-secondary hover:text-obsidian-primary transition"
              >
                Batal
              </button>
              <button
                type="button"
                onClick={handleRegenerateCharacter}
                disabled={isRegeneratingChar}
                className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 active:scale-95 text-canvas font-bold text-xs flex items-center gap-2 shadow-lg transition disabled:opacity-50"
              >
                {isRegeneratingChar ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                <span>Re-generate Karakter</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Polya AI Screenwriter Loading Overlay */}
      {polyaLoadingText && (
        <div className="fixed inset-0 z-[120] flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
          <div className="max-w-md w-full bg-panel rounded-2xl border border-amber-500/50 p-6 flex flex-col items-center text-center space-y-4 shadow-2xl animate-in zoom-in-95 duration-150">
            <div className="w-14 h-14 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
              <Loader2 className="w-7 h-7 animate-spin" />
            </div>
            <div className="space-y-1">
              <span className="text-[10px] font-mono text-amber-400 font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20">
                Polya AI Screenwriter
              </span>
              <h4 className="font-cinzel text-base font-bold text-obsidian-primary mt-1">
                Screenplay &amp; Character Architecture
              </h4>
              <p className="text-xs font-mono text-obsidian-secondary leading-relaxed pt-1">
                {polyaLoadingText}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* SOCKS5 Proxy Offline Alert Modal */}
      {proxyOfflineAlert?.isOpen && (
        <div
          className="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-black/85 backdrop-blur-sm animate-in fade-in duration-200"
          onClick={() => setProxyOfflineAlert(null)}
        >
          <div
            className="relative max-w-lg w-full bg-panel rounded-2xl border border-rose-500/50 p-6 flex flex-col space-y-4 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start gap-3">
              <div className="p-2.5 rounded-xl bg-rose-500/20 text-rose-400 border border-rose-500/30">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div className="flex-1">
                <h3 className="text-base font-bold text-rose-300 font-sans">
                  SOCKS5 Proxy Android Offline
                </h3>
                <p className="text-xs text-obsidian-secondary mt-1 leading-relaxed">
                  Koneksi reverse tunnel HP Android (<span className="font-mono text-amber-300">socks5://127.0.0.1:10808</span>) tidak terhubung atau aplikasi SOCKS5 di HP belum dinyalakan.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setProxyOfflineAlert(null)}
                className="p-1 rounded text-obsidian-muted hover:text-obsidian-primary"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-3 rounded-xl bg-canvas border border-border text-xs space-y-2">
              <div className="flex items-center justify-between text-obsidian-muted font-mono text-[11px]">
                <span>Status Target:</span>
                <span className="font-bold text-rose-400">OFFLINE (Port 10808)</span>
              </div>
              <div className="text-[11px] text-obsidian-secondary font-mono bg-black/40 p-2 rounded border border-border/50">
                {proxyOfflineAlert.detail || proxyStatus?.detail || "Koneksi ditolak pada 127.0.0.1:10808. Aplikasi SOCKS5 HP Android kemungkinan mati."}
              </div>
              <p className="text-[11px] text-amber-300/90 leading-normal">
                <strong>Solusi:</strong> Buka aplikasi SOCKS5 / reverse tunnel di HP Android Anda, pastikan switch service dalam posisi <strong>ON</strong>, lalu klik tombol <strong>Check Connection</strong>.
              </p>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setProxyOfflineAlert(null)}
                className="px-4 py-2 rounded-xl bg-panel border border-border text-xs font-semibold text-obsidian-secondary hover:text-obsidian-primary transition"
              >
                Tutup
              </button>
              <button
                type="button"
                onClick={async () => {
                  const s = await handleCheckProxy();
                  if (s.healthy) {
                    setProxyOfflineAlert(null);
                  }
                }}
                disabled={isCheckingProxy}
                className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 active:scale-95 text-canvas font-bold text-xs flex items-center gap-2 shadow-lg transition"
              >
                {isCheckingProxy ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                <span>Check Connection</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Batch Downstream Pre-Flight Check & Confirmation Modal */}
      {batchPreflightModalOpen && (() => {
        const readyChars = characters.filter(
          (c) => c.closeup_image_url && c.closeup_image_url.trim().length > 0
        );
        const skippedChars = characters.filter(
          (c) => !c.closeup_image_url || !c.closeup_image_url.trim().length
        );
        const estimates = calculateEstimatedAssets(batchResumeMode);
        const isFlowOffline = isGoogleFlowProvider(selectedProvider) && proxyStatus?.healthy === false;

        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="w-full max-w-xl rounded-2xl bg-panel border border-border shadow-2xl p-5 space-y-4 text-obsidian-primary font-sans animate-in zoom-in-95 duration-150 max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between border-b border-border pb-3">
                <div className="flex items-center gap-2">
                  <div className="p-2 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
                    <Sparkles className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="font-cinzel text-sm font-bold uppercase text-obsidian-primary">
                      Generate All Downstream (Cards 2–8 + 5 States)
                    </h4>
                    <p className="text-[11px] font-mono text-obsidian-muted">
                      Pre-flight check &amp; alokasi antrean render berantai untuk seluruh cast
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setBatchPreflightModalOpen(false)}
                  className="text-obsidian-muted hover:text-obsidian-primary p-1 rounded-lg hover:bg-elevated transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Roster Readiness Summary */}
              <div className="grid grid-cols-3 gap-2 text-center font-mono text-xs">
                <div className="p-2.5 rounded-xl bg-canvas border border-border">
                  <span className="text-[10px] text-obsidian-muted block uppercase">Total Karakter</span>
                  <span className="text-base font-bold text-obsidian-primary">{characters.length}</span>
                </div>
                <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30">
                  <span className="text-[10px] text-emerald-400 block uppercase">Siap Diproses</span>
                  <span className="text-base font-bold text-emerald-400">{readyChars.length}</span>
                </div>
                <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30">
                  <span className="text-[10px] text-amber-400 block uppercase">Di-skip (No Card 1)</span>
                  <span className="text-base font-bold text-amber-400">{skippedChars.length}</span>
                </div>
              </div>

              {/* Resume Mode Toggle (Refinement 1) */}
              <div className="p-3 rounded-xl bg-canvas border border-border space-y-2">
                <label className="flex items-center justify-between cursor-pointer select-none">
                  <div className="space-y-0.5 pr-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-obsidian-primary">
                        Skip kartu &amp; state yang sudah ter-generate (Resume Mode)
                      </span>
                      <span className="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                        Recommended
                      </span>
                    </div>
                    <p className="text-[11px] text-obsidian-muted leading-tight">
                      Hanya me-render kartu dan state yang belum memiliki aset gambar. Aset yang sudah selesai tidak akan ditimpa ulang.
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={batchResumeMode}
                    onChange={(e) => setBatchResumeMode(e.target.checked)}
                    className="w-4 h-4 rounded text-amber-500 bg-panel border-border focus:ring-amber-500 cursor-pointer shrink-0"
                  />
                </label>

                <div className="pt-2 border-t border-border/60 flex items-center justify-between text-[11px] font-mono">
                  <span className="text-obsidian-muted">Estimasi Render:</span>
                  <span className="font-bold text-amber-400">
                    {batchResumeMode
                      ? `${estimates.toRender} aset gambar baru (${estimates.alreadyExists} aset sudah ada & dilewati)`
                      : `${estimates.toRender} aset gambar (seluruh Cards 2–8 + Dynamic States)`}
                  </span>
                </div>
              </div>

              {/* Roster Character List Breakdown */}
              <div className="space-y-1.5 max-h-44 overflow-y-auto pr-1">
                <span className="text-[10px] font-mono uppercase text-obsidian-muted block font-semibold">
                  Daftar Antrean Karakter:
                </span>
                {characters.map((c) => {
                  const hasCard1 = !!c.closeup_image_url && c.closeup_image_url.trim().length > 0;
                  return (
                    <div
                      key={c.id}
                      className={cn(
                        "p-2 rounded-lg border text-xs font-mono flex items-center justify-between transition-colors",
                        hasCard1
                          ? "bg-canvas border-border/80 text-obsidian-primary"
                          : "bg-canvas/40 border-dashed border-border/60 text-obsidian-muted"
                      )}
                    >
                      <div className="flex items-center gap-2 truncate">
                        {hasCard1 ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                        ) : (
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                        )}
                        <span className="font-bold truncate">{c.name}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-black/40 text-obsidian-muted">
                          {c.role}
                        </span>
                      </div>
                      <span
                        className={cn(
                          "text-[10px] shrink-0 font-semibold",
                          hasCard1 ? "text-emerald-400" : "text-amber-400/80"
                        )}
                      >
                        {hasCard1 ? "Card 1 Siap ✓" : "Di-skip (Card 1 Kosong)"}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* Guardrails Notice */}
              <div className="p-3 rounded-xl bg-amber-500/5 border border-amber-500/20 text-xs space-y-1.5">
                <div className="flex items-center gap-1.5 font-bold text-amber-400 text-[11px] font-mono">
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  <span>STRICT CARD 1 PROTECTION ACTIVE</span>
                </div>
                <p className="text-[11px] text-obsidian-secondary leading-relaxed">
                  Proses ini <strong>DILARANG KERAS</strong> mengubah atau menimpa Card 1 (Master Anchor).
                  Card 1 hanya digunakan sebagai read-only visual reference anchor untuk Phase 1, Phase 2, dan Phase 3.
                </p>
                <div className="pt-1 flex items-center justify-between text-[10px] font-mono text-obsidian-muted">
                  <span>Provider: <strong className="text-obsidian-primary">{resolveProviderDisplayInfo(selectedProvider, selectedModel).label}</strong></span>
                  <span>📱 Screen Wake Lock Otomatis Aktif</span>
                </div>
              </div>

              {isFlowOffline && (
                <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                  <span>SOCKS5 Proxy HP Android Offline. Nyalakan tunnel Android sebelum mulai.</span>
                </div>
              )}

              {readyChars.length === 0 && (
                <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-mono">
                  Belum ada karakter yang memiliki Card 1 (Master Anchor). Harap verifikasi setidaknya 1 karakter terlebih dahulu.
                </div>
              )}

              {/* Modal Actions */}
              <div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
                <button
                  type="button"
                  onClick={() => setBatchPreflightModalOpen(false)}
                  className="px-4 py-2 rounded-xl bg-panel border border-border text-xs font-mono text-obsidian-muted hover:text-obsidian-primary transition-colors"
                >
                  Batal
                </button>
                <button
                  type="button"
                  onClick={handleStartBatchDownstream}
                  disabled={readyChars.length === 0 || isFlowOffline}
                  className="px-4 py-2 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 disabled:opacity-50 text-canvas font-mono font-bold text-xs flex items-center gap-2 shadow-md transition-all"
                >
                  <Sparkles className="w-4 h-4" />
                  <span>Mulai Batch Downstream ({readyChars.length} Karakter)</span>
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Batch Downstream Completion Summary Modal */}
      {batchSummaryModalOpen && batchSummaryData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-lg rounded-2xl bg-panel border border-border shadow-2xl p-5 space-y-4 text-obsidian-primary font-sans animate-in zoom-in-95 duration-150 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <CheckCircle2 className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-cinzel text-sm font-bold uppercase text-obsidian-primary">
                    Ringkasan Batch Downstream Generation
                  </h4>
                  <p className="text-[11px] font-mono text-obsidian-muted">
                    {batchSummaryData.wasCancelled
                      ? "Batch dihentikan oleh pengguna. Aset yang telah selesai tetap tersimpan."
                      : "Seluruh antrean karakter yang siap telah selesai diproses."}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setBatchSummaryModalOpen(false)}
                className="text-obsidian-muted hover:text-obsidian-primary p-1 rounded-lg hover:bg-elevated transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Results Counters */}
            <div className="grid grid-cols-3 gap-2 text-center font-mono text-xs">
              <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30">
                <span className="text-[10px] text-emerald-400 block uppercase">Sukses</span>
                <span className="text-base font-bold text-emerald-400">{batchSummaryData.successCount}</span>
              </div>
              <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30">
                <span className="text-[10px] text-amber-400 block uppercase">Dilewati</span>
                <span className="text-base font-bold text-amber-400">{batchSummaryData.skippedChars.length}</span>
              </div>
              <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/30">
                <span className="text-[10px] text-rose-400 block uppercase">Gagal</span>
                <span className="text-base font-bold text-rose-400">{batchSummaryData.failedChars.length}</span>
              </div>
            </div>

            {/* Detail Skipped Characters */}
            {batchSummaryData.skippedChars.length > 0 && (
              <div className="space-y-1.5">
                <span className="text-[10px] font-mono uppercase text-amber-400 block font-semibold">
                  Karakter Dilewati ({batchSummaryData.skippedChars.length}):
                </span>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {batchSummaryData.skippedChars.map((sc, idx) => (
                    <div
                      key={idx}
                      className="p-2 rounded-lg bg-canvas border border-border/80 text-[11px] font-mono flex items-center justify-between"
                    >
                      <span className="font-bold text-obsidian-primary">{sc.name} ({sc.role})</span>
                      <span className="text-amber-400/90 text-[10px]">{sc.reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Detail Failed Characters if any */}
            {batchSummaryData.failedChars.length > 0 && (
              <div className="space-y-1.5">
                <span className="text-[10px] font-mono uppercase text-rose-400 block font-semibold">
                  Karakter Mengalami Kendala ({batchSummaryData.failedChars.length}):
                </span>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {batchSummaryData.failedChars.map((fc, idx) => (
                    <div
                      key={idx}
                      className="p-2 rounded-lg bg-rose-500/10 border border-rose-500/30 text-[11px] font-mono space-y-0.5"
                    >
                      <span className="font-bold text-rose-300">{fc.name} ({fc.role})</span>
                      <p className="text-[10px] text-rose-200/80">{fc.error}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="p-3 rounded-xl bg-canvas border border-border text-[11px] font-mono text-obsidian-muted flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span>Card 1 Master Anchors Utuh 100%</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                <span>Semua hasil tersimpan di SQLite</span>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
              {batchSummaryData.failedChars.length > 0 && !isBatchGenerating && (
                <button
                  type="button"
                  onClick={() => {
                    setBatchSummaryModalOpen(false);
                    setBatchResumeMode(true);
                    handleOpenBatchModal();
                  }}
                  className="px-4 py-2 rounded-xl bg-panel border border-amber-500/40 text-amber-300 hover:bg-elevated font-mono font-bold text-xs flex items-center gap-1.5 transition-colors shadow-sm"
                  title="Buka kembali batch pre-flight dengan Resume Mode untuk mengulang hanya karakter dan slot yang gagal"
                >
                  <RefreshCw className="w-3.5 h-3.5 text-amber-400" />
                  <span>Retry Failed Only</span>
                </button>
              )}
              <button
                type="button"
                onClick={() => setBatchSummaryModalOpen(false)}
                className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 text-canvas font-mono font-bold text-xs transition-colors shadow-sm"
              >
                Tutup Ringkasan
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Informative Mobile Tap-Friendly Batch Lock Toast Alert */}
      {batchLockToast?.isOpen && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 w-11/12 max-w-md animate-in fade-in slide-in-from-bottom-5 duration-200 pointer-events-auto">
          <div className="p-3.5 rounded-2xl bg-panel/95 backdrop-blur-md border border-amber-500/50 shadow-2xl flex items-start gap-3 text-obsidian-primary font-sans">
            <div className="p-2 rounded-xl bg-amber-500/20 text-amber-400 border border-amber-500/40 shrink-0 mt-0.5">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div className="flex-1 min-w-0 space-y-1">
              <div className="flex items-center justify-between gap-2">
                <h5 className="font-cinzel text-xs font-bold uppercase tracking-wider text-amber-300">
                  {batchLockToast.title}
                </h5>
                <button
                  type="button"
                  onClick={() => setBatchLockToast(null)}
                  className="p-1 rounded text-obsidian-muted hover:text-obsidian-primary transition-colors -mr-1 -mt-1"
                  title="Tutup notifikasi"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
              <p className="text-[11px] text-obsidian-secondary leading-relaxed font-mono">
                {batchLockToast.message}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Upscale 2K / Revert 1K Toast Notification */}
      {upscaleToast?.isOpen && (
        <div className="fixed bottom-6 right-6 z-50 w-11/12 max-w-sm animate-in fade-in slide-in-from-bottom-5 duration-200 pointer-events-auto">
          <div
            className={cn(
              "p-3.5 rounded-2xl bg-panel/95 backdrop-blur-md border shadow-2xl flex items-start gap-3 text-obsidian-primary font-sans",
              upscaleToast.isError ? "border-rose-500/50" : "border-emerald-500/50"
            )}
          >
            <div
              className={cn(
                "p-2 rounded-xl border shrink-0 mt-0.5",
                upscaleToast.isError
                  ? "bg-rose-500/20 text-rose-400 border-rose-500/40"
                  : "bg-emerald-500/20 text-emerald-400 border-emerald-500/40"
              )}
            >
              {upscaleToast.isError ? <AlertTriangle className="w-4 h-4" /> : <CheckCircle2 className="w-4 h-4" />}
            </div>
            <div className="flex-1 min-w-0 space-y-0.5">
              <div className="flex items-center justify-between gap-2">
                <h5
                  className={cn(
                    "font-cinzel text-xs font-bold uppercase tracking-wider",
                    upscaleToast.isError ? "text-rose-300" : "text-emerald-300"
                  )}
                >
                  {upscaleToast.title}
                </h5>
                <button
                  type="button"
                  onClick={() => setUpscaleToast(null)}
                  className="p-1 rounded text-obsidian-muted hover:text-obsidian-primary transition-colors -mr-1 -mt-1"
                  title="Tutup notifikasi"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
              <p className="text-[11px] text-obsidian-secondary leading-relaxed font-mono">
                {upscaleToast.message}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
