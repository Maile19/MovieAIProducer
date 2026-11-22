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
} from "lucide-react";
import { api, MasterProductionBible } from "@/lib/api";
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
                  Version {bible?.version || 1}.0.0
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
