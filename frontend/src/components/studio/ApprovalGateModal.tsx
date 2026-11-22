"use client";

import React, { useState } from "react";
import {
  CheckCircle,
  AlertTriangle,
  Lock,
  X,
  History,
  ShieldAlert,
  Send,
  Loader2,
} from "lucide-react";
import { api, GateActionInput } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ApprovalGateModalProps {
  projectId: string;
  currentStage: number;
  projectStatus?: string;
  gateHistory?: Array<{
    action: string;
    stage: number;
    notes?: string;
    timestamp: string;
    decided_by_email?: string;
  }>;
  onGateProcessed: () => void;
}

export default function ApprovalGateModal({
  projectId,
  currentStage,
  projectStatus: _projectStatus,
  gateHistory = [],
  onGateProcessed,
}: ApprovalGateModalProps) {
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedAction, setSelectedAction] = useState<"APPROVE" | "REVISE" | "LOCK">("APPROVE");
  const [notes, setNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);

  // Quick feedback tags for rapid showrunner direction
  const quickTags = [
    "DNA Drift Detected",
    "Lighting Inconsistency",
    "Motion Blur Artifact",
    "Dialogue Overflow",
    "Anamorphic Flare Misaligned",
    "Pacing Approved",
    "Cinematography Golden Cut",
  ];

  const handleOpenAction = (action: "APPROVE" | "REVISE" | "LOCK") => {
    setSelectedAction(action);
    setNotes(
      action === "APPROVE"
        ? "Stage execution satisfies showrunner aesthetic and narrative requirements."
        : action === "REVISE"
        ? "Revisions required for continuity and prompt calibration."
        : "Showrunner DNA freeze confirmed. Immutable state applied."
    );
    setErrorMsg(null);
    setModalOpen(true);
  };

  const handleTagClick = (tag: string) => {
    if (notes.includes(tag)) return;
    setNotes((prev) => (prev ? `${prev} [${tag}]` : `[${tag}]`));
  };

  const handleSubmitGate = async () => {
    try {
      setIsSubmitting(true);
      setErrorMsg(null);

      const payload: GateActionInput = {
        action: selectedAction,
        notes: notes.trim(),
        target_stage: selectedAction === "APPROVE" ? Math.min(currentStage + 1, 16) : undefined,
      };

      await api.projects.gateAction(projectId, payload);
      setModalOpen(false);
      onGateProcessed();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to submit stage gate decision.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-panel border border-border rounded-xl p-3.5 shadow-studio space-y-3">
      {/* Control Bar Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-amber-500" />
          <h3 className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary">
            Human Approval Gate &bull; Stage {currentStage}
          </h3>
        </div>

        {gateHistory.length > 0 && (
          <button
            type="button"
            onClick={() => setShowHistory(!showHistory)}
            className="flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono bg-canvas hover:bg-elevated text-obsidian-secondary border border-border transition-colors"
          >
            <History className="w-3 h-3" />
            <span>Gate Logs ({gateHistory.length})</span>
          </button>
        )}
      </div>

      {/* Primary Action Buttons */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
        {/* APPROVE */}
        <button
          type="button"
          onClick={() => handleOpenAction("APPROVE")}
          className="flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:border-emerald-500/60 font-semibold text-xs transition-all shadow-sm group"
        >
          <CheckCircle className="w-4 h-4 text-emerald-400 group-hover:scale-110 transition-transform" />
          <span>APPROVE &amp; ADVANCE</span>
        </button>

        {/* REVISE */}
        <button
          type="button"
          onClick={() => handleOpenAction("REVISE")}
          className="flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 hover:border-rose-500/60 font-semibold text-xs transition-all shadow-sm group"
        >
          <AlertTriangle className="w-4 h-4 text-rose-400 group-hover:scale-110 transition-transform" />
          <span>REQUEST REVISION</span>
        </button>

        {/* LOCK */}
        <button
          type="button"
          onClick={() => handleOpenAction("LOCK")}
          className="flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30 hover:border-amber-500/60 font-semibold text-xs transition-all shadow-sm group"
        >
          <Lock className="w-4 h-4 text-amber-400 group-hover:scale-110 transition-transform" />
          <span>FREEZE &amp; LOCK DNA</span>
        </button>
      </div>

      {/* Gate History Dropdown Panel */}
      {showHistory && gateHistory.length > 0 && (
        <div className="p-3 rounded-lg bg-canvas border border-border space-y-2 animate-in fade-in duration-150">
          <div className="text-[10px] font-mono text-obsidian-muted uppercase tracking-wider">
            Previous Showrunner Decisions
          </div>
          <div className="space-y-1.5 max-h-36 overflow-y-auto font-mono text-[11px]">
            {gateHistory.slice().reverse().map((entry, idx) => (
              <div
                key={idx}
                className="p-2 rounded bg-panel/80 border border-border/70 flex items-start justify-between gap-2"
              >
                <div>
                  <div className="flex items-center gap-1.5">
                    <span
                      className={cn(
                        "px-1.5 py-0.2 rounded text-[9px] font-bold",
                        entry.action === "APPROVE"
                          ? "bg-emerald-500/20 text-emerald-400"
                          : entry.action === "REVISE"
                          ? "bg-rose-500/20 text-rose-400"
                          : "bg-amber-500/20 text-amber-400"
                      )}
                    >
                      {entry.action}
                    </span>
                    <span className="text-obsidian-secondary">Stage {entry.stage}</span>
                    {entry.decided_by_email && (
                      <span className="text-obsidian-muted text-[10px]">
                        by {entry.decided_by_email.split("@")[0]}
                      </span>
                    )}
                  </div>
                  {entry.notes && (
                    <p className="text-[10px] text-obsidian-secondary font-sans mt-1">
                      {entry.notes}
                    </p>
                  )}
                </div>
                <span className="text-[9px] text-obsidian-muted shrink-0">
                  {new Date(entry.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* =========================================================================
       * Interactive Modal Popover
       * ========================================================================= */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-lg rounded-2xl bg-panel border border-border shadow-2xl p-5 space-y-4 text-obsidian-primary font-sans animate-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2.5">
                <div
                  className={cn(
                    "w-8 h-8 rounded-lg flex items-center justify-center border font-bold",
                    selectedAction === "APPROVE"
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                      : selectedAction === "REVISE"
                      ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
                      : "bg-amber-500/10 text-amber-400 border-amber-500/30"
                  )}
                >
                  {selectedAction === "APPROVE" && <CheckCircle className="w-4 h-4" />}
                  {selectedAction === "REVISE" && <AlertTriangle className="w-4 h-4" />}
                  {selectedAction === "LOCK" && <Lock className="w-4 h-4" />}
                </div>
                <div>
                  <h4 className="font-cinzel text-sm font-bold uppercase tracking-wider text-obsidian-primary">
                    Stage Gate: {selectedAction}
                  </h4>
                  <p className="text-[11px] font-mono text-obsidian-muted">
                    Operational Stage {currentStage} Execution Decision
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setModalOpen(false)}
                className="p-1 rounded-md text-obsidian-muted hover:text-obsidian-primary hover:bg-canvas transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Error Message */}
            {errorMsg && (
              <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
                {errorMsg}
              </div>
            )}

            {/* Quick Tags */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-mono text-obsidian-muted uppercase">
                Quick Director Directive Tags:
              </label>
              <div className="flex flex-wrap gap-1.5">
                {quickTags.map((tag) => (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => handleTagClick(tag)}
                    className="px-2 py-0.5 rounded text-[10px] font-mono bg-canvas hover:bg-elevated text-obsidian-secondary hover:text-amber-400 border border-border transition-colors"
                  >
                    + {tag}
                  </button>
                ))}
              </div>
            </div>

            {/* Notes Textarea */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-obsidian-primary">
                Showrunner Notes &amp; Rationale:
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={4}
                placeholder="Enter feedback notes, continuity checks, or prompt adjustment directives..."
                className="w-full px-3 py-2 rounded-lg bg-canvas border border-border focus:border-amber-500 focus:outline-none text-xs text-obsidian-primary font-mono placeholder:text-obsidian-muted resize-none"
              />
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-border">
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                className="px-3.5 py-1.5 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-secondary text-xs transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSubmitGate}
                disabled={isSubmitting}
                className={cn(
                  "px-4 py-2 rounded-lg font-bold text-xs flex items-center gap-2 transition-all shadow-glow",
                  selectedAction === "APPROVE"
                    ? "bg-emerald-500 hover:bg-emerald-600 text-canvas"
                    : selectedAction === "REVISE"
                    ? "bg-rose-500 hover:bg-rose-600 text-canvas"
                    : "bg-amber-500 hover:bg-amber-600 text-canvas"
                )}
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Signing Decision...</span>
                  </>
                ) : (
                  <>
                    <Send className="w-3.5 h-3.5" />
                    <span>Confirm {selectedAction}</span>
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
