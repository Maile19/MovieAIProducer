"use client";

import React, { useState } from "react";
import {
  Lock,
  Unlock,
  ShieldCheck,
  Download,
  FileCode,
  FileText,
  AlertTriangle,
  Loader2,
  CheckCircle,
  BookmarkPlus,
  Mic,
  Subtitles,
  Eye,
  Copy,
  Check,
} from "lucide-react";
import { api, MasterProductionBible, AudioScriptData } from "@/lib/api";
import { formatMpbVersion } from "@/lib/versioning";
import { cn } from "@/lib/utils";
import SavePresetModal from "@/components/presets/SavePresetModal";

interface RevisionLockTabProps {
  projectId: string;
  bible: MasterProductionBible | null;
  onRefresh: () => void;
}

export default function RevisionLockTab({
  projectId,
  bible,
  onRefresh,
}: RevisionLockTabProps) {
  const [isLocking, setIsLocking] = useState(false);
  const [approvalNotes, setApprovalNotes] = useState(
    "Showrunner Master Production Bible DNA Freeze approved. All character states, environments, and optical invariants signed off for production execution."
  );
  const [lockModalOpen, setLockModalOpen] = useState(false);
  const [isDownloading, setIsDownloading] = useState<string | null>(null);
  const [savePresetModalOpen, setSavePresetModalOpen] = useState(false);
  const [includeSfx, setIncludeSfx] = useState(false);
  const [audioPreviewOpen, setAudioPreviewOpen] = useState(false);
  const [audioPreviewData, setAudioPreviewData] = useState<AudioScriptData | null>(null);
  const [audioPreviewSsml, setAudioPreviewSsml] = useState<string>("");
  const [copiedSsml, setCopiedSsml] = useState(false);

  const isLocked = bible?.is_locked || false;

  const handleExecuteLock = async () => {
    try {
      setIsLocking(true);
      await api.bible.lock(projectId, {
        approval_notes: approvalNotes,
        confirm_dna_freeze: true,
      });
      setLockModalOpen(false);
      onRefresh();
    } catch (err) {
      console.error(err);
    } finally {
      setIsLocking(false);
    }
  };

  const handleExportDownload = async (format: "json" | "markdown") => {
    try {
      setIsDownloading(format);
      const res = await api.export.getProjectPackage(projectId, format);

      // Create a blob and download
      const content =
        format === "json"
          ? JSON.stringify(res, null, 2)
          : typeof res === "string"
          ? res
          : JSON.stringify(res, null, 2);

      const mimeType = format === "json" ? "application/json" : "text/markdown";
      const blob = new Blob([content], { type: mimeType });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `Master_Production_Bible_${projectId}_v${bible?.version || 1}.${
        format === "json" ? "json" : "md"
      }`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
    } finally {
      setIsDownloading(null);
    }
  };

  const triggerTextDownload = (content: string, filename: string, mimeType: string) => {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleAudioScriptDownload = async (fmt: "ssml" | "markdown" | "json") => {
    try {
      setIsDownloading(`audio_${fmt}`);
      const res = await api.export.getAudioScript(projectId, fmt);
      const content = typeof res === "string" ? res : JSON.stringify(res, null, 2);
      const ext = fmt === "ssml" ? "ssml" : fmt === "markdown" ? "md" : "json";
      const mime =
        fmt === "ssml"
          ? "application/ssml+xml"
          : fmt === "markdown"
          ? "text/markdown"
          : "application/json";
      triggerTextDownload(content, `TTS_Delivery_Script_${projectId}.${ext}`, mime);
    } catch (err) {
      console.error(err);
    } finally {
      setIsDownloading(null);
    }
  };

  const handleSubtitleDownload = async (fmt: "srt" | "vtt") => {
    try {
      setIsDownloading(`sub_${fmt}`);
      const text = await api.export.getSubtitles(projectId, fmt, includeSfx);
      triggerTextDownload(
        text,
        `Subtitles_${projectId}.${fmt}`,
        fmt === "vtt" ? "text/vtt" : "application/x-subrip"
      );
    } catch (err) {
      console.error(err);
    } finally {
      setIsDownloading(null);
    }
  };

  const handlePreviewAudioScript = async () => {
    try {
      setIsDownloading("audio_preview");
      const [jsonRes, ssmlRes] = await Promise.all([
        api.export.getAudioScript(projectId, "json"),
        api.export.getAudioScript(projectId, "ssml"),
      ]);
      if (jsonRes && typeof jsonRes === "object" && "data" in jsonRes) {
        setAudioPreviewData(jsonRes.data);
      }
      if (typeof ssmlRes === "string") {
        setAudioPreviewSsml(ssmlRes);
      }
      setAudioPreviewOpen(true);
    } catch (err) {
      console.error(err);
    } finally {
      setIsDownloading(null);
    }
  };

  return (
    <div className="space-y-6 font-sans">
      {/* Immutability Status Card */}
      <div
        className={cn(
          "p-5 rounded-xl border transition-all",
          isLocked
            ? "bg-amber-500/10 border-amber-500/50 shadow-glow"
            : "bg-panel border-border"
        )}
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div
              className={cn(
                "w-12 h-12 rounded-xl flex items-center justify-center border font-bold text-lg",
                isLocked
                  ? "bg-amber-500 text-canvas border-amber-300 shadow-glow"
                  : "bg-canvas text-obsidian-muted border-border"
              )}
            >
              {isLocked ? <Lock className="w-6 h-6" /> : <Unlock className="w-6 h-6" />}
            </div>

            <div>
              <div className="flex items-center gap-2 mb-1">
                <span
                  className={cn(
                    "px-2 py-0.5 rounded text-[10px] font-mono font-bold tracking-wider",
                    isLocked
                      ? "bg-amber-500/20 text-amber-400 border border-amber-500/40"
                      : "bg-canvas text-emerald-400 border border-emerald-500/30"
                  )}
                >
                  {isLocked ? "IMMUTABLE DNA FREEZE" : "MUTABLE PRE-PRODUCTION"}
                </span>
                <span className="text-xs font-mono text-obsidian-muted">
                  {formatMpbVersion(bible?.version, isLocked).label}
                </span>
              </div>
              <h3 className="font-cinzel text-base font-bold text-obsidian-primary">
                {isLocked ? "Production Bible is Permanently Frozen" : "Production Bible is Currently Editable"}
              </h3>
              <p className="text-xs text-obsidian-muted mt-0.5">
                {isLocked
                  ? `Locked on ${bible?.locked_at ? new Date(bible.locked_at).toLocaleString() : "Active Stage"}. All characters, worlds, and styles are immutable.`
                  : "Locking the Bible freezes visual continuity for batch generation across generative models."}
              </p>
            </div>
          </div>

          <div>
            {!isLocked ? (
              <button
                type="button"
                onClick={() => setLockModalOpen(true)}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-xs transition-all shadow-glow"
              >
                <Lock className="w-4 h-4" />
                <span>Execute DNA Freeze Lock</span>
              </button>
            ) : (
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-canvas border border-amber-500/30 text-amber-400 text-xs font-mono">
                <ShieldCheck className="w-4 h-4" />
                <span>Cryptographically Sealed</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Production Package Export Downloads */}
      <div className="p-4 rounded-xl bg-panel border border-border space-y-4">
        <div>
          <h4 className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary flex items-center gap-2">
            <Download className="w-4 h-4 text-amber-500" />
            <span>Master Production Package Export</span>
          </h4>
          <p className="text-xs font-mono text-obsidian-muted mt-0.5">
            Download complete production specifications for generative pipelines and distribution.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* JSON Export */}
          <div className="p-4 rounded-xl bg-canvas border border-border space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileCode className="w-5 h-5 text-amber-400" />
                <span className="font-mono text-xs font-bold text-obsidian-primary">
                  Hollywood JSON Bundle
                </span>
              </div>
              <span className="text-[10px] font-mono text-obsidian-muted">
                Pipeline Automation
              </span>
            </div>
            <p className="text-xs text-obsidian-secondary leading-relaxed font-sans">
              Complete machine-readable JSON bundle containing visual DNA, character state matrices, 50-scene blueprints, and QC thresholds.
            </p>
            <button
              type="button"
              disabled={isDownloading === "json"}
              onClick={() => handleExportDownload("json")}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-lg bg-panel hover:bg-elevated border border-border hover:border-amber-500/40 text-amber-400 font-mono text-xs font-semibold transition-all disabled:opacity-50"
            >
              {isDownloading === "json" ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Packaging JSON...</span>
                </>
              ) : (
                <>
                  <Download className="w-3.5 h-3.5" />
                  <span>Download Bible JSON (.json)</span>
                </>
              )}
            </button>
          </div>

          {/* Markdown Script Package */}
          <div className="p-4 rounded-xl bg-canvas border border-border space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-blue-400" />
                <span className="font-mono text-xs font-bold text-obsidian-primary">
                  Production Markdown Binder
                </span>
              </div>
              <span className="text-[10px] font-mono text-obsidian-muted">
                Human Showrunner Reader
              </span>
            </div>
            <p className="text-xs text-obsidian-secondary leading-relaxed font-sans">
              Human-readable Markdown document structured with Hollywood scene headings, beat descriptions, character dialogue, and camera matrices.
            </p>
            <button
              type="button"
              disabled={isDownloading === "markdown"}
              onClick={() => handleExportDownload("markdown")}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-lg bg-panel hover:bg-elevated border border-border hover:border-blue-500/40 text-blue-400 font-mono text-xs font-semibold transition-all disabled:opacity-50"
            >
              {isDownloading === "markdown" ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Generating Markdown...</span>
                </>
              ) : (
                <>
                  <Download className="w-3.5 h-3.5" />
                  <span>Download Bible Script (.md)</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Stage S13-S15: Screenwriter Audio / TTS Delivery Script (SSML) & Subtitles (.SRT / .VTT) */}
        <div className="p-4 rounded-xl bg-canvas border border-border space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Mic className="w-4 h-4 text-emerald-400 shrink-0" />
              <div>
                <h5 className="font-mono text-xs font-bold text-obsidian-primary">
                  Stage S13–S15: TTS / SSML Delivery Script &amp; Subtitles
                </h5>
                <p className="text-[11px] text-obsidian-muted">
                  Compiles speaker Voice DNA, act-mapped #State emotion, and J/L-Cut offsets into SSML, .SRT, and .VTT.
                </p>
              </div>
            </div>

            <label className="inline-flex items-center gap-1.5 text-[11px] font-mono text-obsidian-secondary cursor-pointer select-none shrink-0">
              <input
                type="checkbox"
                checked={includeSfx}
                onChange={(e) => setIncludeSfx(e.target.checked)}
                className="rounded border-border bg-panel text-amber-500 focus:ring-0 focus:ring-offset-0"
              />
              <span>Include [SFX] SDH Cues</span>
            </label>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 font-mono text-xs">
            <button
              type="button"
              disabled={isDownloading === "audio_preview"}
              onClick={handlePreviewAudioScript}
              className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-panel hover:bg-elevated border border-emerald-500/40 text-emerald-400 font-semibold transition-all disabled:opacity-50 cursor-pointer"
            >
              {isDownloading === "audio_preview" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Eye className="w-3.5 h-3.5" />}
              <span>Preview SSML &amp; Cues</span>
            </button>

            <button
              type="button"
              disabled={isDownloading === "audio_ssml"}
              onClick={() => handleAudioScriptDownload("ssml")}
              className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-panel hover:bg-elevated border border-border hover:border-amber-500/40 text-amber-400 font-semibold transition-all disabled:opacity-50 cursor-pointer"
            >
              {isDownloading === "audio_ssml" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
              <span>Export TTS / SSML</span>
            </button>

            <button
              type="button"
              disabled={isDownloading === "sub_srt"}
              onClick={() => handleSubtitleDownload("srt")}
              className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-panel hover:bg-elevated border border-border hover:border-blue-500/40 text-blue-400 font-semibold transition-all disabled:opacity-50 cursor-pointer"
            >
              {isDownloading === "sub_srt" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Subtitles className="w-3.5 h-3.5" />}
              <span>Download .SRT Subtitles</span>
            </button>

            <button
              type="button"
              disabled={isDownloading === "sub_vtt"}
              onClick={() => handleSubtitleDownload("vtt")}
              className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-panel hover:bg-elevated border border-border hover:border-violet-500/40 text-violet-400 font-semibold transition-all disabled:opacity-50 cursor-pointer"
            >
              {isDownloading === "sub_vtt" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Subtitles className="w-3.5 h-3.5" />}
              <span>Download .VTT Subtitles</span>
            </button>
          </div>
        </div>

        {/* Reusable Production Preset Library Action */}
        <div className="p-4 rounded-xl bg-canvas border border-border flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-500 shrink-0">
              <BookmarkPlus className="w-5 h-5" />
            </div>
            <div>
              <h5 className="font-mono text-xs font-bold text-obsidian-primary">
                Reusable Production Preset Library
              </h5>
              <p className="text-xs text-obsidian-muted">
                Save this project&apos;s visual DNA, cinematography rules, and QC thresholds as a template for new productions.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setSavePresetModalOpen(true)}
            className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-xs shadow-glow transition-all shrink-0 cursor-pointer"
          >
            <BookmarkPlus className="w-4 h-4" />
            <span>Save as Reusable Preset</span>
          </button>
        </div>
      </div>

      {/* Save as Preset Modal */}
      <SavePresetModal
        isOpen={savePresetModalOpen}
        onClose={() => setSavePresetModalOpen(false)}
        projectId={projectId}
        defaultTitle={`Production v${bible?.version || 1}`}
      />

      {/* Stage S13-S15 Audio / SSML Preview Modal */}
      {audioPreviewOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="w-full max-w-3xl max-h-[88vh] flex flex-col rounded-2xl bg-panel border border-border shadow-2xl overflow-hidden font-mono text-xs">
            <div className="p-4 border-b border-border bg-canvas/60 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Mic className="w-4 h-4 text-emerald-400" />
                <div>
                  <h4 className="font-cinzel text-sm font-bold text-obsidian-primary uppercase">
                    TTS / SSML Voice Delivery Script Preview
                  </h4>
                  {audioPreviewData && (
                    <p className="text-[10px] text-obsidian-muted">
                      {audioPreviewData.total_cues} Cues ({audioPreviewData.spoken_cues} spoken, {audioPreviewData.sfx_cues} SFX) &bull; Runtime {audioPreviewData.total_runtime_seconds}s
                    </p>
                  )}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setAudioPreviewOpen(false)}
                className="px-2.5 py-1 rounded bg-canvas border border-border text-obsidian-muted hover:text-obsidian-primary"
              >
                Close
              </button>
            </div>

            <div className="p-4 overflow-y-auto space-y-4 flex-1">
              {audioPreviewData?.cues && audioPreviewData.cues.length > 0 ? (
                <div className="space-y-2">
                  {audioPreviewData.cues.map((cue) => (
                    <div key={cue.cue_number} className="p-3 rounded-lg bg-canvas border border-border space-y-1">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-bold text-amber-400">
                          Cue #{cue.cue_number} &bull; Scene {cue.scene_number} Shot #{cue.shot_number} &bull; {cue.speaker}
                        </span>
                        <span className="text-[10px] text-blue-300">
                          {cue.start_seconds.toFixed(2)}s &rarr; {cue.end_seconds.toFixed(2)}s ({cue.transition_type})
                        </span>
                      </div>
                      <div className="text-[10px] text-obsidian-muted">
                        Voice DNA: {cue.voice_profile} &bull; {cue.active_state_code} ({cue.emotion_cue}) &bull; rate {cue.prosody_rate}, pitch {cue.prosody_pitch}
                      </div>
                      <p className="font-sans text-xs text-obsidian-primary">&ldquo;{cue.text}&rdquo;</p>
                      <code className="block text-[10px] text-emerald-300/90 bg-black/40 p-1.5 rounded overflow-x-auto">
                        {cue.ssml}
                      </code>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-6 text-center text-obsidian-muted">
                  No dialogue or SFX cues found across scenes/shots yet.
                </div>
              )}

              {audioPreviewSsml && (
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] uppercase font-bold text-amber-400">Full XML SSML Document</span>
                    <button
                      type="button"
                      onClick={() => {
                        navigator.clipboard.writeText(audioPreviewSsml);
                        setCopiedSsml(true);
                        setTimeout(() => setCopiedSsml(false), 2000);
                      }}
                      className="flex items-center gap-1 px-2 py-0.5 rounded bg-canvas border border-border text-amber-400"
                    >
                      {copiedSsml ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      <span>{copiedSsml ? "Copied SSML" : "Copy SSML"}</span>
                    </button>
                  </div>
                  <pre className="p-3 rounded-lg bg-black/60 border border-border text-[10px] text-emerald-300 overflow-x-auto max-h-48">
                    {audioPreviewSsml}
                  </pre>
                </div>
              )}
            </div>

            <div className="p-3 border-t border-border bg-canvas/40 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => handleAudioScriptDownload("markdown")}
                className="px-3 py-1.5 rounded bg-panel border border-border text-blue-400 font-bold"
              >
                Download Script (.md)
              </button>
              <button
                type="button"
                onClick={() => handleAudioScriptDownload("ssml")}
                className="px-3 py-1.5 rounded bg-amber-500 text-canvas font-bold"
              >
                Download SSML (.ssml)
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Lock Modal */}
      {lockModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-lg rounded-2xl bg-panel border border-border shadow-2xl p-5 space-y-4 text-obsidian-primary font-sans animate-in zoom-in-95 duration-150">
            <div className="flex items-center gap-3 border-b border-border pb-3">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
                <Lock className="w-5 h-5" />
              </div>
              <div>
                <h4 className="font-cinzel text-sm font-bold uppercase text-obsidian-primary">
                  Confirm Master Production Bible Lock
                </h4>
                <p className="text-xs font-mono text-obsidian-muted">
                  Irreversible DNA Freeze &bull; Master Version Lock
                </p>
              </div>
            </div>

            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 flex items-start gap-2.5 text-xs text-rose-300">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-rose-400" />
              <span>
                WARNING: Executing DNA Freeze will permanently lock all 5 character profiles, 5 key environments, and visual style tokens. Future changes will require spawning a new Bible revision version.
              </span>
            </div>

            <div className="space-y-1.5 text-xs font-mono">
              <label className="text-obsidian-secondary font-semibold">
                Showrunner Signoff Justification &amp; Notes:
              </label>
              <textarea
                value={approvalNotes}
                onChange={(e) => setApprovalNotes(e.target.value)}
                rows={3}
                className="w-full px-3 py-2 rounded-lg bg-canvas border border-border text-obsidian-primary text-xs focus:border-amber-500 focus:outline-none resize-none"
              />
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-border">
              <button
                type="button"
                onClick={() => setLockModalOpen(false)}
                className="px-3.5 py-1.5 rounded-lg bg-canvas border border-border text-xs text-obsidian-secondary"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleExecuteLock}
                disabled={isLocking}
                className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-xs flex items-center gap-2 shadow-glow"
              >
                {isLocking ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Sealing Bible...</span>
                  </>
                ) : (
                  <>
                    <CheckCircle className="w-4 h-4" />
                    <span>Confirm DNA Freeze</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
