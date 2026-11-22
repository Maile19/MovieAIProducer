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
} from "lucide-react";
import { Character, SheetPromptItem, Project, api, FlowProxyStatus } from "@/lib/api";
import { cn } from "@/lib/utils";
import ObsidianDropdown from "@/components/ui/ObsidianDropdown";

interface CharacterMatrixTabProps {
  projectId: string;
  project?: Project | null;
  characters: Character[];
  isLocked: boolean;
  onRefresh: (options?: { silent?: boolean }) => void | Promise<void>;
  onSilentRefresh?: () => void | Promise<void>;
  onPatchCharacterAsset?: (characterId: string, slot: string, imageUrl: string, metaPatch?: Record<string, any>) => void;
}

export default function CharacterMatrixTab({
  projectId,
  project,
  characters,
  isLocked,
  onRefresh,
  onSilentRefresh,
  onPatchCharacterAsset,
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
    return characters[0]?.id || "char_1";
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
  const [newCharPrompt, setNewCharPrompt] = useState("");
  const [newCharSeed, setNewCharSeed] = useState<number>(() => Math.floor(100000 + Math.random() * 900000));
  const [isSubmittingChar, setIsSubmittingChar] = useState(false);

  // Dual AI Provider Selector for Add Character Modal (Default: Google Flow [5 Akun PRO])
  const [addCharLLMProvider, setAddCharLLMProvider] = useState<"9router" | "gemini" | "agy">("9router");
  const [addCharImageProvider, setAddCharImageProvider] = useState<
    "ag_gemini_flash" | "google_flow" | "9router" | "sd35_large_hf"
  >("google_flow");

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
  const [downstreamProgressText, setDownstreamProgressText] = useState<string | null>(null);

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
  const [newWardrobe, setNewWardrobe] = useState("");
  const [newInjuries, setNewInjuries] = useState("");
  const [newExpression, setNewExpression] = useState("");
  const [isSubmittingState, setIsSubmittingState] = useState(false);

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

  // AI Generation Provider & Model Configuration (Default: Google Flow [5 Akun PRO])
  const [selectedProvider, setSelectedProvider] = useState<
    "ag_gemini_flash" | "9router" | "sd35_large_hf" | "google_flow"
  >(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("movieai_active_character_provider");
      if (saved && ["ag_gemini_flash", "9router", "sd35_large_hf", "google_flow"].includes(saved)) {
        return saved as any;
      }
    }
    return "google_flow";
  });
  const [selectedModel, setSelectedModel] = useState<string>("ag/gemini-3.8-flash");

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

  // Per-slot upload states
  const [uploadingSlots, setUploadingSlots] = useState<Record<string, boolean>>({});
  const [uploadErrors, setUploadErrors] = useState<Record<string, string | null>>({});

  // Fallback mock characters if database has none
  const activeCharacters: Character[] =
    characters.length > 0
      ? characters
      : [
          {
            id: "char_1",
            project_id: projectId,
            name: "Cipher Vance",
            role: "PROTAGONIST",
            base_prompt:
              "Male cybernetic operative, 34 years old, sharp angular jawline, obsidian fiber-optic jacket, amber cybernetic optical lens implant in right eye.",
            voice_ref_asset_id: "elevenlabs_vance_gravel_noir",
            states: [
              {
                id: "st_1",
                character_id: "char_1",
                state_code: "#State 01",
                wardrobe: "Pristine tailored obsidian trenchcoat, carbon-fiber tactical underlayer.",
                injuries_and_wear: "Zero defects, immaculate posture, polished cybernetic eye housing.",
                expression_anchor: "Stoic, guarded, calculating ocular focus.",
              },
              {
                id: "st_2",
                character_id: "char_1",
                state_code: "#State 02",
                wardrobe: "Trenchcoat unbuttoned, water-soaked lapels, fraying ballistic seams.",
                injuries_and_wear: "Light cheek lacerations, soot smudge across collarbone.",
                expression_anchor: "Fatigued, hyper-vigilant scanning.",
              },
              {
                id: "st_3",
                character_id: "char_1",
                state_code: "#State 03",
                wardrobe: "Trenchcoat torn at left shoulder, exposed reactive armor plates.",
                injuries_and_wear: "Singed synthetic skin, leaking amber fluid from optic socket.",
                expression_anchor: "Adrenaline surge, jaw clenched in defiance.",
              },
              {
                id: "st_4",
                character_id: "char_1",
                state_code: "#State 04",
                wardrobe: "Shredded armor, emergency tourniquet on cybernetic forearm.",
                injuries_and_wear: "Sparks emitting from damaged ocular servo, bloodied temple.",
                expression_anchor: "Desperation transitioning to lethal focus.",
              },
              {
                id: "st_5",
                character_id: "char_1",
                state_code: "#State 05",
                wardrobe: "Overcharged neural suit glowing with violet discharge.",
                injuries_and_wear: "Full cybernetic overload, shattered lens, heroic battle patina.",
                expression_anchor: "Transcendent catharsis, absolute resolve.",
              },
            ],
          },
          {
            id: "char_2",
            project_id: projectId,
            name: "Director Mara Thorne",
            role: "ANTAGONIST",
            base_prompt:
              "Female Syndicate Overseer, 45 years old, cold alabaster skin, sharp asymmetrical bob haircut, monochromatic silver velvet power suit.",
            voice_ref_asset_id: "elevenlabs_thorne_crisp_cold",
            states: [
              {
                id: "st_6",
                character_id: "char_2",
                state_code: "#State 01",
                wardrobe: "Immaculate silver velvet power suit, gold geometric cufflinks.",
                injuries_and_wear: "Flawless, perfectly symmetrical appearance.",
                expression_anchor: "Chilled condescension, predatory calm.",
              },
            ],
          },
        ];

  const selectedChar =
    activeCharacters.find((c) => c.id === selectedCharId) || activeCharacters[0];

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
      addCharImageProvider === "google_flow"
        ? `Mengirim ${target === "closeup" ? "Slot 1: Close-Up Master Anchor" : target === "expression" ? "Expression Sheet" : "Full Body"} ke antrean Google Flow PRO...`
        : `Merender ${target === "closeup" ? "Card 1: Character Close-Up (Master Anchor)" : target === "expression" ? "Card 2: Expression Sheet" : "Card 3: Full Body"}...`
    );

    try {
      const res = await api.bible.previewCharacter(projectId, {
        name: newCharName.trim(),
        role: newCharRole,
        base_visual_prompt: effectivePrompt,
        dna_seed: newCharSeed,
        image_provider: addCharImageProvider,
        target,
        aspect_ratio: (target === "expression" || target === "both") ? "16:9" : "3:4",
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
    setIsExprOutdated(false);
    setIsFrontOutdated(false);
    setPreviewError(null);
    setPreviewErrorMsg(null);
    setPreviewStatusText("");
    setNewCharName("");
    setNewCharPrompt("");
    setNewCharBio("");
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
      setPreviewError(null);
      setPreviewErrorMsg(null);
      setNewCharName("");
      setNewCharPrompt("");
      setNewCharBio("");

      // Sync active provider in main matrix with provider used during character creation & persist
      setSelectedProvider(addCharImageProvider);
      if (typeof window !== "undefined") {
        localStorage.setItem("movieai_active_character_provider", addCharImageProvider);
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

  // Helper to ensure a character is persisted in the database before generating assets
  const ensurePersistedCharacter = async (char: Character): Promise<string> => {
    // If it's already in the persisted characters list from server and not a mock ID
    const isSaved =
      characters.some((c) => c.id === char.id) &&
      char.id !== "char_1" &&
      char.id !== "char_2" &&
      !char.id.startsWith("mock_");

    if (isSaved) {
      return char.id;
    }

    // Auto-create in database
    const created = await api.bible.createCharacter(projectId, {
      name: char.name,
      role: char.role,
      base_prompt: char.base_prompt,
    });
    const realCharId = created.data.id;

    // Auto-create initial states if template has them
    if (char.states && char.states.length > 0) {
      for (const st of char.states) {
        try {
          await api.bible.createCharacterState(realCharId, {
            state_code: st.state_code,
            wardrobe: st.wardrobe,
            injuries_and_wear: st.injuries_and_wear,
            expression_anchor: st.expression_anchor,
          });
        } catch {
          // Non-blocking
        }
      }
    }

    handleSelectCharacter(realCharId);
    onRefresh();
    return realCharId;
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
          wardrobe: newWardrobe.trim(),
          injuries_and_wear: newInjuries.trim(),
          expression_anchor: newExpression.trim(),
        });
        setAddStateModalOpen(false);
        setEditingStateId(null);
        setNewWardrobe("");
        setNewInjuries("");
        setNewExpression("");
      } else {
        // Add mode: create state
        await api.bible.createCharacterState(effectiveCharId, {
          state_code: newStateCode,
          wardrobe: newWardrobe.trim(),
          injuries_and_wear: newInjuries.trim(),
          expression_anchor: newExpression.trim(),
        });

        if (advanceNext) {
          // Check if there is another unsaved state after this one
          const updatedMock = [...(selectedChar.states || []), { state_code: newStateCode }];
          const nextCode = getNextUnsavedStateCode(updatedMock, newStateCode) || getNextUnsavedStateCode(updatedMock);
          if (nextCode) {
            setNewStateCode(nextCode);
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
    if (!charId || charId === "char_1" || charId === "char_2" || charId.startsWith("mock_")) return;
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

  // In-flight active jobs rehydration on mount / character switch
  const rehydrateInFlightJobs = useCallback(
    async (charId: string) => {
      if (!charId || charId === "char_1" || charId === "char_2" || charId.startsWith("mock_")) return;
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
    options?: { skipRefresh?: boolean }
  ): Promise<boolean> => {
    if (!selectedChar?.id) return false;
    const targetKey = targetType === "state" ? `state_${stateId}` : `${targetType}_${angle}`;
    setRenderingTargets((prev) => ({ ...prev, [targetKey]: true }));
    setTargetErrors((prev) => ({ ...prev, [targetKey]: null }));

    try {
      setPollStatus((prev) => ({
        ...prev,
        [targetKey]: "Menyiapkan karakter di database...",
      }));

      const effectiveCharId = await ensurePersistedCharacter(selectedChar);

      setPollStatus((prev) => ({
        ...prev,
        [targetKey]:
          selectedProvider === "google_flow"
            ? "Mengirim job ke antrean Google Flow (Visual Anchoring)..."
            : selectedProvider === "ag_gemini_flash"
            ? "Merender dengan AG/Gemini 3.8 Flash (Seed Locked)..."
            : "Merender gambar cinema-grade...",
      }));

      const aspect_ratio = angle === "expression" ? "16:9" : targetType === "state" ? "1:1" : "3:4";

      const res = await api.bible.generateCharacterAsset(effectiveCharId, {
        target_type: targetType,
        angle,
        state_id: stateId,
        provider: selectedProvider,
        model:
          selectedProvider === "9router" || selectedProvider === "ag_gemini_flash"
            ? selectedModel
            : undefined,
        aspect_ratio,
      });

      // Synchronous Response (AG/Gemini 3.8 Flash, 9Router, SD 3.5 Large)
      if (res.status === "completed" && res.image_url) {
        if (onPatchCharacterAsset) {
          onPatchCharacterAsset(effectiveCharId, angle, res.image_url);
        }
        setRenderingTargets((prev) => ({ ...prev, [targetKey]: false }));
        setPollStatus((prev) => ({ ...prev, [targetKey]: "" }));
        if (!options?.skipRefresh) {
          if (onSilentRefresh) {
            await onSilentRefresh();
          } else {
            await onRefresh({ silent: true });
          }
          await fetchPrompts(effectiveCharId);
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
                if (onPatchCharacterAsset) {
                  onPatchCharacterAsset(effectiveCharId, angle, job.image_url);
                }
                setRenderingTargets((prev) => ({ ...prev, [targetKey]: false }));
                setPollStatus((prev) => ({ ...prev, [targetKey]: "" }));
                if (!options?.skipRefresh) {
                  if (onSilentRefresh) {
                    await onSilentRefresh();
                  } else {
                    await onRefresh({ silent: true });
                  }
                  await fetchPrompts(effectiveCharId);
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

  // DAG Wave Regenerate All Downstream Anchors (Slot 2 to 7 / 8)
  const handleRegenerateAllDownstream = async () => {
    if (!selectedChar?.closeup_image_url || isLocked || isRegeneratingAllDownstream) return;

    // Pre-flight check: batalkan batch langsung jika SOCKS5 proxy sedang offline
    if (selectedProvider === "google_flow") {
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

    try {
      // WAVE 1: Run Card 2 (Expression) & Card 3 (Full Body Front) in parallel
      // Both depend ONLY on Card 1 (closeup master anchor)
      setDownstreamProgressText("[Gelombang 1/2] Merender Card 2 (Expression) & Card 3 (Full Body) paralel...");

      const card2Promise = handleRenderAsset("sheet", "expression", undefined, { skipRefresh: true });
      // Stagger second launch slightly (500ms) to ensure distinct queue timestamps
      const card3Promise = new Promise<boolean>((resolve) => {
        setTimeout(async () => {
          let success = await handleRenderAsset("turnaround", "front", undefined, { skipRefresh: true });
          if (!success) {
            // Guardrail: 1 auto-retry on transient failure for Card 3
            console.warn("Card 3 (Full Body Front) failed on first attempt. Retrying once (auto-retry)...");
            setDownstreamProgressText("[Gelombang 1/2] Card 3 mencoba ulang (1x auto-retry)...");
            await new Promise((r) => setTimeout(r, 1500));
            success = await handleRenderAsset("turnaround", "front", undefined, { skipRefresh: true });
          }
          resolve(success);
        }, 500);
      });

      const [_card2Success, card3Success] = await Promise.all([card2Promise, card3Promise]);

      if (!card3Success) {
        console.warn("Wave 1 halted: Card 3 (Full Body Front) failed after retry. Preserving Card 2 and halting Wave 2.");
        setDownstreamProgressText(
          "Gelombang 2 dihentikan karena Card 3 (Full Body Front) gagal. Hasil Card 2 tetap tersimpan."
        );
        setTimeout(() => setDownstreamProgressText(null), 5000);
        return;
      }

      // WAVE 2: Cards 4, 5, 6, 7, 8 in parallel (staggered by 800ms)
      // These all depend on Card 1 (closeup) + Card 3 (front body)
      setDownstreamProgressText("[Gelombang 2/2] Merender Card 4-8 paralel (anchored ke Card 1 + Card 3)...");

      const wave2Slots: {
        slot: "side" | "three_quarter" | "back" | "tpose" | "action";
        targetType: "sheet" | "turnaround";
        title: string;
      }[] = [
        { slot: "side", targetType: "turnaround", title: "Card 4: Side Profile" },
        { slot: "three_quarter", targetType: "turnaround", title: "Card 5: 3/4 Hero Angle" },
        { slot: "back", targetType: "turnaround", title: "Card 6: Back View" },
        { slot: "tpose", targetType: "sheet", title: "Card 7: T-Pose Sheet" },
        { slot: "action", targetType: "sheet", title: "Card 8: Dynamic Action" },
      ];

      // Launch Wave 2 with controlled staggering (800ms) to prevent proxy socket bursts
      const wave2Promises = wave2Slots.map((item, idx) => {
        return new Promise<boolean>((resolve) => {
          setTimeout(async () => {
            const ok = await handleRenderAsset(item.targetType, item.slot, undefined, { skipRefresh: true });
            resolve(ok);
          }, idx * 800);
        });
      });

      await Promise.all(wave2Promises);
    } finally {
      setDownstreamProgressText(null);
      setIsRegeneratingAllDownstream(false);
      if (onSilentRefresh) {
        await onSilentRefresh();
      } else {
        await onRefresh({ silent: true });
      }
      if (selectedChar?.id) fetchPrompts(selectedChar.id);
    }
  };

  // Render Matrix Card for Turnaround & Rigging/Action/Expression Sheets
  const renderMatrixCard = (cfg: {
    slot: "closeup" | "front" | "side" | "three_quarter" | "back" | "tpose" | "action" | "expression";
    title: string;
    targetType: "turnaround" | "sheet";
    aspect: "3:4" | "16:9";
    imageUrl: string | null | undefined;
    subtitle: string;
    anchorBadge: string;
    isMasterAnchor?: boolean;
  }) => {
    const targetKey = `${cfg.targetType}_${cfg.slot}`;
    const isRendering = !!renderingTargets[targetKey];
    const isUploading = !!uploadingSlots[cfg.slot];
    const statusText = pollStatus[targetKey];
    const errorMsg = uploadErrors[cfg.slot] || targetErrors[targetKey];
    const imageUrl = cfg.imageUrl;
    const promptItem = sheetPrompts[cfg.slot];
    const meta = selectedChar?.sheet_metadata?.[cfg.slot];
    const isUploaded = meta?.source === "manual_upload";

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
                  : selectedProvider === "google_flow"
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
            cfg.aspect === "16:9" ? "aspect-[16/9]" : "aspect-[3/4]"
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
                onClick={() => handleRenderAsset(cfg.targetType, cfg.slot)}
                disabled={isRendering || isUploading}
                className={cn(
                  "py-1.5 px-2 rounded-lg font-bold flex items-center justify-center gap-1 transition-colors shadow-sm disabled:opacity-50",
                  imageUrl
                    ? "bg-canvas hover:bg-elevated border border-border hover:border-amber-500/50 text-obsidian-primary"
                    : "bg-amber-500 hover:bg-amber-600 text-canvas"
                )}
                title={imageUrl ? `Re-render ${cfg.title}` : `Render ${cfg.title}`}
              >
                {imageUrl ? (
                  <>
                    <RefreshCw className="w-3 h-3 text-amber-400" />
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
                onClick={() => document.getElementById(`upload-sheet-${cfg.slot}`)?.click()}
                disabled={isRendering || isUploading}
                className="py-1.5 px-2 rounded-lg bg-canvas hover:bg-elevated border border-border hover:border-emerald-500/50 text-obsidian-secondary hover:text-obsidian-primary font-semibold flex items-center justify-center gap-1 transition-colors disabled:opacity-50"
                title={imageUrl ? `Replace photo for ${cfg.title}` : `Upload photo for ${cfg.title}`}
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
              onClick={() => setActivePromptModalSlot(cfg.slot)}
              className="py-1.5 px-1.5 rounded-lg bg-black/40 hover:bg-black/70 border border-border/80 hover:border-amber-500/40 text-obsidian-secondary hover:text-amber-400 font-semibold flex items-center justify-center gap-1 transition-colors"
              title="View full prompt breakdown, aspect ratio & camera directives"
            >
              <Eye className="w-3 h-3 shrink-0" />
              <span>View</span>
            </button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Top Section: Character Roster Bar */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-cinzel text-sm font-bold uppercase tracking-wider text-obsidian-primary flex items-center gap-2">
            <Users className="w-4 h-4 text-amber-500" />
            <span>Character Cast &amp; Dynamic State Matrix</span>
          </h3>
          <p className="text-xs font-mono text-obsidian-muted mt-0.5">
            Maintains visual identity anchors, facial geometries, and wear states across all 50 scenes.
          </p>
        </div>

        {!isLocked && (
          <button
            type="button"
            onClick={() => setAddCharModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-mono font-bold text-xs transition-colors shadow-sm"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Character</span>
          </button>
        )}
      </div>

      {/* Main Character Selector Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
        {activeCharacters.map((char) => (
          <button
            key={char.id}
            type="button"
            onClick={() => handleSelectCharacter(char.id)}
            className={cn(
              "px-3.5 py-2 rounded-xl text-xs font-mono transition-all border text-left shrink-0 flex items-center gap-2.5",
              selectedChar.id === char.id
                ? "bg-amber-500/10 border-amber-500/50 text-amber-400 font-bold shadow-sm"
                : "bg-panel border-border text-obsidian-secondary hover:text-obsidian-primary hover:border-border/80"
            )}
          >
            <div
              className={cn(
                "w-2 h-2 rounded-full",
                selectedChar.id === char.id ? "bg-amber-500" : "bg-obsidian-muted/40"
              )}
            />
            <div>
              <div className="font-medium text-obsidian-primary leading-tight">{char.name}</div>
              <span className="text-[9px] uppercase text-obsidian-muted font-semibold">
                {char.role}
              </span>
            </div>
          </button>
        ))}
      </div>

      {/* Informational banner when operating on template characters */}
      {characters.length === 0 && (
        <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-start sm:items-center gap-2.5">
            <Sparkles className="w-4 h-4 text-amber-400 shrink-0 mt-0.5 sm:mt-0" />
            <div>
              <span className="font-semibold text-amber-300">Template Karakter Aktif:</span>
              <span className="text-obsidian-secondary ml-1.5">
                Proyek ini belum memiliki karakter tersimpan di database. Anda dapat langsung mengklik <strong>Render</strong> atau <strong>Upload</strong> pada kartu di bawah (akan disimpan otomatis), atau simpan sekarang.
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={async () => {
                try {
                  await ensurePersistedCharacter(selectedChar);
                } catch (e: any) {
                  console.error(e);
                }
              }}
              className="px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-bold font-mono text-[11px] transition-all shadow-sm flex items-center gap-1.5"
            >
              <Users className="w-3.5 h-3.5" />
              <span>Simpan &quot;{selectedChar.name}&quot; ke Proyek</span>
            </button>
          </div>
        </div>
      )}

      {/* =========================================================================
       * AI Render Model & Provider Selection Toolbar
       * ========================================================================= */}
      <div className="p-3.5 rounded-xl bg-panel/90 border border-border flex flex-col md:flex-row md:items-center justify-between gap-3 font-mono text-xs shadow-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-bold uppercase text-amber-400 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-amber-500" />
            <span>AI Render Provider:</span>
          </span>

          <div className="flex flex-wrap items-center gap-1.5">
            {[
              {
                id: "google_flow" as const,
                label: "Google Flow",
                badge: "Visual Anchor &bull; 5 PRO",
                modelVal: "google_flow_pro",
              },
              {
                id: "ag_gemini_flash" as const,
                label: "AG/Gemini 3.8 Flash",
                badge: "Text-Only &bull; Fast",
                modelVal: "ag/gemini-3.8-flash",
              },
              {
                id: "9router" as const,
                label: "9Router",
                badge: "Text-Only &bull; Combo",
                modelVal: "ag/gemini-3.8-flash",
              },
              {
                id: "sd35_large_hf" as const,
                label: "SD 3.5 Large",
                badge: "Text-Only &bull; HF",
                modelVal: "sd35_large_hf",
              },
            ].map((prov) => {
              const isSelected = selectedProvider === prov.id;
              return (
                <button
                  key={prov.id}
                  type="button"
                  onClick={() => {
                    setSelectedProvider(prov.id);
                    if (typeof window !== "undefined") {
                      localStorage.setItem("movieai_active_character_provider", prov.id);
                    }
                    if (prov.id === "ag_gemini_flash") {
                      setSelectedModel("ag/gemini-3.8-flash");
                    }
                  }}
                  className={cn(
                    "px-3 py-1.5 rounded-lg border text-[11px] font-semibold transition-all flex items-center gap-1.5",
                    isSelected
                      ? "bg-amber-500/15 border-amber-500 text-amber-400 shadow-sm"
                      : "bg-canvas border-border text-obsidian-secondary hover:text-obsidian-primary hover:border-border/80"
                  )}
                >
                  <span>{prov.label}</span>
                  <span
                    className={cn(
                      "text-[9px] px-1 py-0.2 rounded font-mono",
                      isSelected
                        ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                        : "bg-black/30 text-obsidian-muted"
                    )}
                    dangerouslySetInnerHTML={{ __html: prov.badge }}
                  />
                </button>
              );
            })}
          </div>
        </div>

        {/* Model Selector for 9Router */}
        {selectedProvider === "9router" && (
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase text-obsidian-muted">Model:</span>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="px-2.5 py-1 rounded-lg bg-canvas border border-border text-[11px] text-obsidian-primary focus:border-amber-500 focus:outline-none"
            >
              <option value="ag/gemini-3.8-flash">ag/gemini-3.8-flash (Recommended)</option>
              <option value="gemini-3.1-flash-image">gemini-3.1-flash-image</option>
              <option value="geminis">geminis (Combo Pool)</option>
              <option value="Agy">Agy (Antigravity High-Speed)</option>
            </select>
          </div>
        )}

        {/* SOCKS5 Android Proxy Live Indicator */}
        <div className="flex items-center gap-2 px-2.5 py-1 rounded-lg bg-canvas border border-border">
          <span className="text-[10px] uppercase font-bold text-obsidian-muted flex items-center gap-1.5">
            <span
              className={cn(
                "inline-block w-2 h-2 rounded-full",
                proxyStatus?.healthy
                  ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.7)]"
                  : "bg-rose-500 animate-pulse"
              )}
            />
            <span>SOCKS5 Android:</span>
          </span>
          <span
            className={cn(
              "font-mono font-bold text-[11px]",
              proxyStatus?.healthy ? "text-emerald-400" : "text-rose-400"
            )}
          >
            {proxyStatus?.healthy ? "ONLINE" : "OFFLINE"}
          </span>
          {proxyStatus?.healthy && proxyStatus.latency_ms ? (
            <span className="text-[9px] text-obsidian-muted font-mono">
              ({proxyStatus.latency_ms}ms)
            </span>
          ) : null}
          <button
            type="button"
            onClick={handleCheckProxy}
            disabled={isCheckingProxy}
            className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-panel hover:bg-canvas border border-border text-obsidian-secondary hover:text-obsidian-primary transition-all disabled:opacity-50"
            title={proxyStatus?.detail || "Periksa koneksi SOCKS5 Android"}
          >
            {isCheckingProxy ? "Checking..." : "[Check Connection]"}
          </button>
        </div>

        <div className="text-[10px] text-obsidian-muted">
          Render target: <span className="text-emerald-400">Persistent SQLite Storage</span>
        </div>
      </div>

      {/* Warning banner when a text-only provider is active */}
      {selectedProvider !== "google_flow" && (
        <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-start gap-3 text-xs shadow-sm">
          <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
          <div className="flex-1 space-y-1">
            <div className="flex items-center justify-between gap-2">
              <span className="font-bold text-amber-300 uppercase tracking-wide text-[11px]">
                Peringatan Engine Render: Visual Anchoring Tidak Aktif
              </span>
              <button
                type="button"
                onClick={() => {
                  setSelectedProvider("google_flow");
                  if (typeof window !== "undefined") {
                    localStorage.setItem("movieai_active_character_provider", "google_flow");
                  }
                }}
                className="px-2.5 py-1 rounded bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-[10px] transition-colors shadow-sm shrink-0"
              >
                Aktifkan Google Flow (5 Akun PRO)
              </button>
            </div>
            <p className="text-[11px] text-amber-200/90 leading-relaxed font-sans">
              Engine <strong>{selectedProvider === "ag_gemini_flash" ? "AG/Gemini 3.8 Flash" : selectedProvider === "9router" ? "9Router" : "SD 3.5 Large"}</strong> adalah engine <em>Text-to-Image</em> murni yang tidak mendukung referensi visual (Visual Anchor Card 1 & Card 3). Hal ini berisiko menyebabkan <em>character &amp; gender drift</em> saat merender Card 2 s/d Card 8. Untuk menjaga konsistensi 100% wajah, gender, usia, dan kostum, disarankan menggunakan <strong>Google Flow</strong>.
            </p>
          </div>
        </div>
      )}

      {/* Selected Character Profile Header */}
      <div className="p-4 rounded-xl bg-panel border border-border shadow-sm">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-amber-500 font-bold uppercase px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/30">
                  {selectedChar.role}
                </span>
                <button
                  type="button"
                  onClick={() => handleCopySeed(selectedChar.dna_seed || "285358")}
                  className="flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/20 transition-colors"
                  title="Click to copy locked DNA Seed"
                >
                  <Lock className="w-3 h-3 text-emerald-400" />
                  <span>SEED: #{selectedChar.dna_seed || "285358"}</span>
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
              <span className="text-[10px] font-mono text-obsidian-muted">
                Biometric Identity &bull; Locked Deterministic Truth
              </span>
            </div>

            <h4 className="font-cinzel text-lg font-bold text-obsidian-primary">
              {selectedChar.name}
            </h4>

            <div className="space-y-1 text-xs font-mono">
              <label className="text-[10px] text-obsidian-muted uppercase font-semibold">Base Visual Prompt</label>
              <div className="p-2.5 rounded-lg bg-canvas border border-border text-obsidian-primary leading-relaxed text-[11px]">
                {selectedChar.base_prompt}
              </div>
            </div>
          </div>

          <div className="space-y-3 font-mono text-xs">
            <div className="space-y-1">
              <label className="text-[10px] text-obsidian-muted uppercase font-semibold flex items-center gap-1.5">
                <Mic className="w-3.5 h-3.5 text-amber-500" />
                <span>Voice DNA Profile</span>
              </label>
              <div className="p-2.5 rounded-lg bg-canvas border border-border flex items-center justify-between">
                <span className="text-obsidian-secondary text-[11px] truncate">
                  {selectedChar.voice_ref_asset_id || "Acoustic Timbre Default"}
                </span>
                <span className="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 text-[9px] font-bold shrink-0">
                  128kbps HQ
                </span>
              </div>
            </div>

            <div className="p-2.5 rounded-lg bg-canvas border border-border space-y-1.5 text-[10px]">
              <div className="flex items-center justify-between">
                <span className="text-obsidian-muted uppercase">Active Engine:</span>
                <span className="text-amber-400 font-bold">
                  {selectedProvider === "google_flow"
                    ? "Google Flow (5 Akun PRO)"
                    : selectedProvider === "ag_gemini_flash"
                    ? "AG/Gemini 3.8 Flash"
                    : selectedProvider === "9router"
                    ? `9Router (${selectedModel})`
                    : "SD 3.5 Large (HF)"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-obsidian-muted uppercase">Anchoring Mode:</span>
                <span
                  className={cn(
                    "px-1.5 py-0.5 rounded font-bold text-[9px]",
                    selectedProvider === "google_flow"
                      ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                      : "bg-blue-500/15 text-blue-400 border border-blue-500/30"
                  )}
                >
                  {selectedProvider === "google_flow"
                    ? "Multimodal Reference Upload (Max 4)"
                    : "Strict Seed + Chained DNA Lock"}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* =========================================================================
       * SEVEN-SHEET CHARACTER PRODUCTION MATRIX
       * ========================================================================= */}
      <div className="p-4 rounded-xl bg-panel border border-border space-y-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-border/80 pb-3">
          <div>
            <div className="flex items-center gap-2">
              <Camera className="w-4 h-4 text-amber-500" />
              <h4 className="font-cinzel text-sm font-bold uppercase tracking-wider text-obsidian-primary">
                Seven-Sheet Character Production Matrix
              </h4>
              <span className="px-2 py-0.5 rounded-full text-[9px] font-mono bg-amber-500/15 text-amber-400 border border-amber-500/30 font-bold">
                Sequential Visual Anchoring
              </span>
            </div>
            <p className="text-[11px] font-mono text-obsidian-muted mt-0.5">
              Dedicated high-resolution turnaround cards, rigging baseline, signature action breakdown, and micro-expressions panel.
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {!isLocked && (
              <button
                type="button"
                onClick={handleRegenerateAllDownstream}
                disabled={isRegeneratingAllDownstream || !selectedChar.closeup_image_url}
                className="px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-canvas font-bold text-xs flex items-center gap-1.5 transition-all shadow-sm"
                title={
                  !selectedChar.closeup_image_url
                    ? "Slot 1 Close-Up diperlukan sebagai Master Anchor"
                    : "Regenerate Card 2 hingga 8 secara sekuensial satu per satu"
                }
              >
                {isRegeneratingAllDownstream ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Sparkles className="w-3.5 h-3.5" />
                )}
                <span>
                  {isRegeneratingAllDownstream
                    ? downstreamProgressText || "Regenerating Downstream..."
                    : "Regenerate All Downstream (Slot 2 → 7)"}
                </span>
              </button>
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
                aspect: "3:4",
                imageUrl: selectedChar.closeup_image_url,
                subtitle: "Master Biometric Headshot • 100mm f/5.6 RAW",
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
            const statusText = pollStatus[targetKey];
            const errorMsg = targetErrors[targetKey];

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
                        Anchors: [Card 1, 2]
                      </span>
                      <button
                        type="button"
                        onClick={() => setActivePromptModalSlot(st.state_code)}
                        className="p-1 rounded hover:bg-elevated text-obsidian-muted hover:text-amber-400 transition-colors"
                        title={`Lihat master prompt & directives untuk ${st.state_code}`}
                      >
                        <Eye className="w-3.5 h-3.5" />
                      </button>
                      {!isLocked && (
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
                      {st.state_code === "#State 01"
                        ? "Normal Baseline"
                        : st.state_code === "#State 02"
                        ? "Fatigue & Wear"
                        : st.state_code === "#State 03"
                        ? "Battle Damaged"
                        : st.state_code === "#State 04"
                        ? "Psychological Breakdown"
                        : "Climax / Metamorphosis"}
                    </span>
                  </div>

                  {/* State Image Preview */}
                  {st.image_url ? (
                    <div className="relative aspect-video w-full rounded-lg overflow-hidden border border-border mb-2.5 group/stateimg">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={st.image_url}
                        alt={st.state_code}
                        className="w-full h-full object-cover"
                      />
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
                            onClick={() => handleRenderAsset("state", undefined, st.id)}
                            className="p-1 rounded bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-[10px] flex items-center gap-1 px-2"
                          >
                            <RefreshCw className="w-3 h-3" />
                            <span>Render Ulang</span>
                          </button>
                        )}
                      </div>
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
                    onClick={() => handleRenderAsset("state", undefined, st.id)}
                    className="w-full mt-2.5 flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-elevated hover:bg-amber-500 hover:text-canvas border border-border text-obsidian-secondary text-[10px] font-bold transition-all shadow-sm"
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
                        onChange={(e) => setAddCharImageProvider(e.target.value as any)}
                        className="w-full px-2.5 py-1.5 rounded-lg bg-panel border border-border text-[11px] text-obsidian-primary focus:border-amber-500 focus:outline-none"
                      >
                        <option value="google_flow">Google Flow (5 Akun PRO) [Recommended]</option>
                        <option value="ag_gemini_flash">AG / Gemini 3.8 Flash (Fast)</option>
                        <option value="9router">9Router Multi-Combo</option>
                        <option value="sd35_large_hf">SD 3.5 Large (HF)</option>
                      </select>
                      {addCharImageProvider === "google_flow" && (
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
                    placeholder="e.g. Elena Rostova / Cipher Vance"
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
                        3:4 Portrait &bull; 85mm Prime
                      </span>
                    </div>

                    {/* Close-Up Preview Body */}
                    <div className="relative aspect-[3/4] max-h-[220px] w-auto mx-auto rounded-md bg-black/40 overflow-hidden flex items-center justify-center border border-border/60">
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
                        </div>
                      ) : (
                        <div className="flex flex-col items-center justify-center text-obsidian-muted p-3 text-center space-y-1">
                          <Users className="w-7 h-7 opacity-30" />
                          <span className="text-[10px] text-obsidian-secondary font-semibold">Slot 1 Belum di-generate</span>
                          <span className="text-[9px] text-obsidian-muted">Master Biometric Casting Anchor</span>
                        </div>
                      )}
                    </div>

                    {/* Independent Generate / Re-roll Close-Up Button */}
                    <button
                      type="button"
                      onClick={() => handleGeneratePreview("closeup")}
                      disabled={isPreviewGenerating || !newCharName.trim()}
                      className="w-full py-1.5 px-2 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/40 text-[10px] text-amber-300 hover:text-amber-200 font-bold flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50"
                    >
                      <RefreshCw className={cn("w-3 h-3 text-amber-400", isRollingCloseup && "animate-spin")} />
                      <span>{previewCloseupUrl ? "Re-roll Close-Up (Slot 1)" : "Generate Close-Up (Master Anchor)"}</span>
                    </button>
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
                            </div>
                          ) : (
                            <span className="text-[9px] text-obsidian-muted">Opsional</span>
                          )}
                        </div>

                        <button
                          type="button"
                          onClick={() => handleGeneratePreview("expression")}
                          disabled={isPreviewGenerating || !newCharName.trim()}
                          className="w-full py-1 px-1.5 rounded bg-canvas hover:bg-elevated border border-border text-[9px] text-obsidian-secondary hover:text-amber-300 font-semibold flex items-center justify-center gap-1 transition-colors disabled:opacity-50"
                        >
                          <RefreshCw className={cn("w-2.5 h-2.5 text-amber-400", isRollingExpression && "animate-spin")} />
                          <span>Re-roll Expression</span>
                        </button>
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
                            </div>
                          ) : (
                            <span className="text-[9px] text-obsidian-muted">Opsional</span>
                          )}
                        </div>

                        <button
                          type="button"
                          onClick={() => handleGeneratePreview("front")}
                          disabled={isPreviewGenerating || !newCharName.trim()}
                          className="w-full py-1 px-1.5 rounded bg-canvas hover:bg-elevated border border-border text-[9px] text-obsidian-secondary hover:text-amber-300 font-semibold flex items-center justify-center gap-1 transition-colors disabled:opacity-50"
                        >
                          <RefreshCw className={cn("w-2.5 h-2.5 text-amber-400", isRollingFront && "animate-spin")} />
                          <span>Re-roll Full Body</span>
                        </button>
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
                            addCharImageProvider !== "google_flow") && (
                            <div className="mt-2 pt-2 border-t border-rose-500/20 flex flex-wrap items-center justify-between gap-2">
                              <span className="text-[10px] text-amber-300">
                                Rekomendasi: Beralih ke Google Flow [5 Akun PRO] yang memiliki kuota aktif dan stabil.
                              </span>
                              {addCharImageProvider !== "google_flow" && (
                                <button
                                  type="button"
                                  onClick={() => {
                                    setAddCharImageProvider("google_flow");
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
                    Aspect: {sheetPrompts[activePromptModalSlot]?.recommended_aspect_ratio || "3:4"}
                  </span>
                </div>
                <div className="text-[11px] text-obsidian-muted flex items-center gap-2">
                  <span>Character: <strong className="text-obsidian-primary">{selectedChar.name}</strong></span>
                  <span>&bull;</span>
                  <span className="text-emerald-400 font-bold">DNA SEED: #{selectedChar.dna_seed || "285358"}</span>
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
              </div>
            </div>

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
                        Positive Master Prompt (Project-Synced &amp; DNA Seed Locked)
                      </label>
                      <span className="text-[10px] text-obsidian-muted">
                        {sheetPrompts[activePromptModalSlot]?.positive_prompt?.length || 0} chars
                      </span>
                    </div>
                    <div className="p-3 rounded-xl bg-canvas border border-border text-obsidian-primary text-[11px] leading-relaxed whitespace-pre-wrap select-all font-mono">
                      {sheetPrompts[activePromptModalSlot]?.positive_prompt || "Generating prompt..."}
                    </div>
                  </div>

                  {/* Negative Prompt */}
                  <div className="space-y-1.5">
                    <label className="text-[10px] text-rose-400 font-bold uppercase tracking-wider">
                      Negative Prompt
                    </label>
                    <div className="p-2.5 rounded-xl bg-canvas border border-border text-obsidian-secondary text-[11px] leading-relaxed whitespace-pre-wrap select-all font-mono">
                      {sheetPrompts[activePromptModalSlot]?.negative_prompt}
                    </div>
                  </div>

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
                        #{selectedChar.dna_seed || "285358"}
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
    </div>
  );
}
