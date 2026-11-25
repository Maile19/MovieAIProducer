"use client";

import React, { useState } from "react";
import {
  ShieldCheck,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  X,
  RefreshCw,
} from "lucide-react";
import { api, ContinuityAuditResult } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ContinuityAuditPanelProps {
  projectId: string;
  onClose?: () => void;
  compact?: boolean;
}

const SEVERITY_OPTIONS = ["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"] as const;

export default function ContinuityAuditPanel({
  projectId,
  onClose,
  compact = false,
}: ContinuityAuditPanelProps) {
  const [audit, setAudit] = useState<ContinuityAuditResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [strictMode, setStrictMode] = useState(false);
  const [severityFilter, setSeverityFilter] = useState<(typeof SEVERITY_OPTIONS)[number]>("ALL");

  const handleRunAudit = async (overrideStrict?: boolean) => {
    if (!projectId || isRunning) return;
    const useStrict = overrideStrict !== undefined ? overrideStrict : strictMode;
    try {
      setIsRunning(true);
      setErrorMsg(null);
      const res = await api.qc.continuityAudit(projectId, { strict_mode: useStrict });
      if (res?.data) {
        setAudit(res.data);
      }
    } catch (err: any) {
      setErrorMsg(err?.message || "Failed to execute cross-scene continuity audit.");
    } finally {
      setIsRunning(false);
    }
  };

  const filteredFindings = (audit?.findings || []).filter(
    (f) => severityFilter === "ALL" || f.severity === severityFilter
  );

  const gateClass =
    audit?.gate_status === "PASS"
      ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-400"
      : audit?.gate_status === "FAIL"
      ? "bg-rose-500/15 border-rose-500/40 text-rose-400"
      : "bg-amber-500/15 border-amber-500/40 text-amber-400";

  return (
    <div
      className={cn(
        "rounded-xl bg-panel border border-border space-y-4 font-sans text-xs",
        compact ? "p-3.5" : "p-4"
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-amber-500 shrink-0" />
          <h4 className="font-cinzel text-xs sm:text-sm font-bold uppercase tracking-wider text-obsidian-primary">
            Cross-Scene Continuity Audit (ADR-0009)
          </h4>
          {audit && (
            <span className={cn("px-2 py-0.5 rounded-full text-[10px] font-mono font-bold border", gateClass)}>
              {audit.gate_status} &bull; {audit.continuity_score}/100
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-canvas border border-border text-[10px] font-mono text-obsidian-secondary cursor-pointer">
            <input
              type="checkbox"
              checked={strictMode}
              onChange={(e) => {
                const next = e.target.checked;
                setStrictMode(next);
                if (audit) handleRunAudit(next);
              }}
              className="accent-amber-500"
            />
            <span>Strict Mode</span>
          </label>

          <button
            type="button"
            onClick={() => handleRunAudit()}
            disabled={isRunning || !projectId}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-[11px] font-mono transition-colors disabled:opacity-50"
          >
            {isRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
            <span>{isRunning ? "Auditing..." : audit ? "Re-run Audit" : "Run Continuity Audit"}</span>
          </button>

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="p-1 rounded-lg text-obsidian-muted hover:text-obsidian-primary hover:bg-canvas transition-colors"
              title="Close Continuity Audit"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {errorMsg && (
        <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-[11px] font-mono flex items-center gap-2">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {!audit ? (
        <div className="p-4 rounded-lg bg-canvas/50 border border-border text-[11px] font-mono text-obsidian-muted">
          Audits Character DNA &amp; #State 01–05 progression, World Props/Environments &amp; lighting consistency, optical/transition safety, and style-safe Bible invariants across all scenes.
        </div>
      ) : (
        <>
          {/* 4 Pillar Scores */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 font-mono">
            {[
              { key: "character_dna_states", label: "DNA & States", value: audit.pillar_scores.character_dna_states },
              { key: "world_props_lighting", label: "World & Light", value: audit.pillar_scores.world_props_lighting },
              { key: "optical_spatial", label: "Optical & Spatial", value: audit.pillar_scores.optical_spatial },
              { key: "rules_invariants", label: "Rules & Negatives", value: audit.pillar_scores.rules_invariants },
            ].map((p) => (
              <div key={p.key} className="p-2.5 rounded-lg bg-canvas border border-border text-center space-y-0.5">
                <span className="text-[9px] uppercase text-obsidian-muted block">{p.label}</span>
                <div
                  className={cn(
                    "text-base font-bold",
                    p.value >= 85 ? "text-emerald-400" : p.value >= 65 ? "text-amber-400" : "text-rose-400"
                  )}
                >
                  {p.value}/100
                </div>
              </div>
            ))}
          </div>

          {/* Severity Filter Pills */}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-1.5 font-mono text-[10px]">
              {SEVERITY_OPTIONS.map((sev) => {
                const count =
                  sev === "ALL"
                    ? audit.findings.length
                    : sev === "CRITICAL"
                    ? audit.summary.critical_count
                    : sev === "HIGH"
                    ? audit.summary.high_count
                    : sev === "MEDIUM"
                    ? audit.summary.medium_count
                    : audit.summary.low_count;
                return (
                  <button
                    key={sev}
                    type="button"
                    onClick={() => setSeverityFilter(sev)}
                    className={cn(
                      "px-2 py-0.5 rounded border transition-colors",
                      severityFilter === sev
                        ? "bg-amber-500/20 border-amber-500/50 text-amber-300 font-bold"
                        : "bg-canvas border-border text-obsidian-muted hover:text-obsidian-primary"
                    )}
                  >
                    {sev} ({count})
                  </button>
                );
              })}
            </div>
            <span className="text-[10px] font-mono text-obsidian-muted">
              {audit.summary.scenes_audited} scenes &bull; {audit.summary.shots_audited} shots &bull; {audit.style_code}
            </span>
          </div>

          {/* Findings List */}
          <div className="space-y-2 max-h-72 overflow-y-auto pr-1 font-mono">
            {filteredFindings.length === 0 ? (
              <div className="p-3 rounded-lg bg-canvas border border-border text-emerald-400 text-[11px] flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span>No continuity findings for this severity filter.</span>
              </div>
            ) : (
              filteredFindings.map((f) => (
                <div
                  key={f.finding_id}
                  className="p-3 rounded-lg bg-canvas border border-border/80 space-y-1 text-[11px]"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5 font-bold">
                      <span
                        className={cn(
                          "px-1.5 py-0.5 rounded text-[9px] border",
                          f.severity === "CRITICAL"
                            ? "bg-rose-500/15 border-rose-500/40 text-rose-400"
                            : f.severity === "HIGH"
                            ? "bg-orange-500/15 border-orange-500/40 text-orange-300"
                            : f.severity === "MEDIUM"
                            ? "bg-amber-500/15 border-amber-500/40 text-amber-300"
                            : "bg-blue-500/15 border-blue-500/40 text-blue-300"
                        )}
                      >
                        {f.severity}
                      </span>
                      <span className="text-obsidian-primary">{f.title}</span>
                    </div>
                    <span className="text-[9px] text-obsidian-muted">
                      {f.scene_number ? `Scene #${f.scene_number}` : "Project"}
                      {f.shot_number ? ` · Shot #${f.shot_number}` : ""}
                    </span>
                  </div>
                  <p className="text-obsidian-secondary font-sans text-[11px] leading-relaxed">{f.detail}</p>
                  <p className="text-[10px] text-emerald-400/90">
                    Remediation: {f.remediation}
                  </p>
                </div>
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}
