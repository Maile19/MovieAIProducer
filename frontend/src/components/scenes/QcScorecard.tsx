"use client";

import React, { useState, useEffect } from "react";
import {
  ShieldCheck,
  RefreshCw,
  Loader2,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";
import { api, QCReport } from "@/lib/api";
import { cn } from "@/lib/utils";

interface QcScorecardProps {
  sceneId: string;
  shotId?: string;
  keyframeUrl?: string | null;
  onAuditCompleted?: (report: QCReport) => void;
}

export default function QcScorecard({
  sceneId,
  keyframeUrl,
  onAuditCompleted,
}: QcScorecardProps) {
  const [isRunningAudit, setIsRunningAudit] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);
  const [qcReport, setQcReport] = useState<QCReport | null>(null);

  useEffect(() => {
    setQcReport(null);
    setAuditError(null);
  }, [sceneId]);

  const handleRunAudit = async () => {
    if (!sceneId) return;
    try {
      setIsRunningAudit(true);
      setAuditError(null);
      const res = await api.qc.auditScene(sceneId);
      if (res?.data) {
        setQcReport(res.data);
        onAuditCompleted?.(res.data);
      }
    } catch (err: any) {
      console.error(err);
      setAuditError(err?.message || "Failed to run backend scene QC audit.");
    } finally {
      setIsRunningAudit(false);
    }
  };

  const overallPercent =
    qcReport?.overall_score_100 !== undefined
      ? Math.round(qcReport.overall_score_100)
      : qcReport?.overall_score !== undefined
      ? Math.round(qcReport.overall_score * 100)
      : 0;

  const statusBadge = qcReport?.status || (qcReport?.passed ? "PASS" : "WARN");
  const hasKeyframe = Boolean(keyframeUrl && keyframeUrl.trim().length > 0);

  return (
    <div className="p-4 rounded-xl bg-panel border border-border space-y-4 font-sans text-xs">
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ShieldCheck
            className={cn(
              "w-4 h-4",
              qcReport
                ? statusBadge === "PASS"
                  ? "text-emerald-400"
                  : statusBadge === "FAIL"
                  ? "text-rose-400"
                  : "text-amber-400"
                : "text-amber-500"
            )}
          />
          <h4 className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary">
            Scene QC Continuity Scorecard
          </h4>
        </div>

        <button
          type="button"
          onClick={handleRunAudit}
          disabled={isRunningAudit || !sceneId}
          className="flex items-center gap-1.5 px-3 py-1 rounded-lg border bg-canvas hover:bg-elevated border-border text-amber-400 font-mono text-[11px] font-bold transition-all disabled:opacity-40 cursor-pointer"
          title="Audit real narrative pacing, Character DNA continuity, optical coverage & asset readiness"
        >
          {isRunningAudit ? (
            <>
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>Auditing...</span>
            </>
          ) : (
            <>
              <RefreshCw className="w-3 h-3" />
              <span>Run QC Audit</span>
            </>
          )}
        </button>
      </div>

      {auditError && (
        <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-[11px] font-mono flex items-center gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          <span>{auditError}</span>
        </div>
      )}

      {!qcReport ? (
        <div className="p-4 rounded-lg bg-canvas/40 border border-border flex flex-col items-center justify-center text-center space-y-1.5 py-5">
          <div className="w-8 h-8 rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
            <ShieldCheck className="w-4 h-4" />
          </div>
          <div className="text-obsidian-primary font-semibold text-xs">Not Audited Yet</div>
          <p className="text-obsidian-muted text-[11px] max-w-sm">
            Click <span className="text-amber-400 font-bold">&ldquo;Run QC Audit&rdquo;</span> to inspect real slugline/pacing compliance, Cast Voice DNA &amp; #State lock, optical coverage, and{" "}
            {hasKeyframe ? "attached keyframe media." : "visual asset readiness (pending keyframe)."}
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5 font-mono">
            {/* Overall Score */}
            <div className="p-2.5 rounded-lg bg-canvas border border-border text-center space-y-1">
              <span className="text-[9px] text-obsidian-muted uppercase block">Overall</span>
              <div
                className={cn(
                  "text-lg font-bold tracking-tight",
                  statusBadge === "PASS"
                    ? "text-emerald-400"
                    : statusBadge === "FAIL"
                    ? "text-rose-400"
                    : "text-amber-400"
                )}
              >
                {overallPercent}/100
              </div>
              <span
                className={cn(
                  "text-[9px] uppercase font-bold block",
                  statusBadge === "PASS"
                    ? "text-emerald-400"
                    : statusBadge === "FAIL"
                    ? "text-rose-400"
                    : "text-amber-400"
                )}
              >
                {statusBadge}
              </span>
            </div>

            {/* Narrative & Pacing */}
            <div className="p-2.5 rounded-lg bg-canvas border border-border text-center space-y-1">
              <span className="text-[9px] text-obsidian-muted uppercase block">Narrative</span>
              <div className="text-lg font-bold text-obsidian-primary">
                {qcReport.sub_scores?.narrative_pacing ?? "—"}%
              </div>
              <span className="text-[9px] text-obsidian-muted block">
                {qcReport.metrics?.dialogue_word_count ?? 0}/{qcReport.metrics?.dialogue_max_words ?? 14}w
              </span>
            </div>

            {/* Continuity & DNA */}
            <div className="p-2.5 rounded-lg bg-canvas border border-border text-center space-y-1">
              <span className="text-[9px] text-obsidian-muted uppercase block">DNA Lock</span>
              <div className="text-lg font-bold text-obsidian-primary">
                {qcReport.sub_scores?.continuity_dna ?? "—"}%
              </div>
              <span className="text-[9px] text-obsidian-muted block">Voice &amp; State</span>
            </div>

            {/* Optical Coverage */}
            <div className="p-2.5 rounded-lg bg-canvas border border-border text-center space-y-1">
              <span className="text-[9px] text-obsidian-muted uppercase block">Optical</span>
              <div className="text-lg font-bold text-obsidian-primary">
                {qcReport.sub_scores?.optical_coverage ?? "—"}%
              </div>
              <span className="text-[9px] text-obsidian-muted block">
                {qcReport.metrics?.shots_count ?? 0} Shots ({qcReport.metrics?.shot_duration_total ?? 0}s)
              </span>
            </div>

            {/* Asset Readiness */}
            <div className="p-2.5 rounded-lg bg-canvas border border-border text-center space-y-1 col-span-2 sm:col-span-1">
              <span className="text-[9px] text-obsidian-muted uppercase block">Assets</span>
              <div className="text-lg font-bold text-obsidian-primary">
                {qcReport.sub_scores?.asset_readiness ?? "—"}%
              </div>
              <span
                className={cn(
                  "text-[9px] uppercase font-bold block",
                  qcReport.asset_status === "ready"
                    ? "text-emerald-400"
                    : qcReport.asset_status === "partial"
                    ? "text-amber-400"
                    : "text-obsidian-muted"
                )}
              >
                {qcReport.asset_status || "pending_asset"}
              </span>
            </div>
          </div>

          {/* Actionable Issues & Fix Suggestions */}
          <div className="space-y-1.5 font-mono text-[11px]">
            <label className="text-[10px] text-obsidian-muted uppercase">
              Audit Diagnostics &amp; Actionable Fixes:
            </label>
            <div className="p-2.5 rounded-lg bg-canvas border border-border/80 space-y-2 max-h-40 overflow-y-auto">
              {qcReport.issues && qcReport.issues.length > 0 ? (
                qcReport.issues.map((iss, idx) => (
                  <div key={idx} className="space-y-0.5 border-b border-border/40 last:border-none pb-1.5 last:pb-0">
                    <div
                      className={cn(
                        "flex items-start gap-1.5 leading-tight font-semibold",
                        iss.severity === "CRITICAL"
                          ? "text-rose-400"
                          : iss.severity === "WARNING"
                          ? "text-amber-400"
                          : "text-blue-300"
                      )}
                    >
                      <span>[{iss.severity}]</span>
                      <span>{iss.message}</span>
                    </div>
                    {iss.suggestion && (
                      <div className="text-[10px] text-obsidian-muted pl-3">
                        Fix: {iss.suggestion}
                      </div>
                    )}
                  </div>
                ))
              ) : (
                <div className="flex items-center gap-1.5 text-emerald-400">
                  <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                  <span>All narrative, DNA continuity, optical coverage, and asset checks passed.</span>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
