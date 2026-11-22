"use client";

import React, { useEffect, useState, useCallback } from "react";
import AppShell from "@/components/layout/AppShell";
import { api, FlowAccount, FlowSettings, FlowJob, FlowProxyStatus } from "@/lib/api";
import {
  Server,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Play,
  Settings as SettingsIcon,
  Copy,
  Check,
  Terminal,
  Clock,
  Sparkles,
  Loader2,
  ExternalLink,
  Power,
  RefreshCw,
} from "lucide-react";

export default function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [savingSettings, setSavingSettings] = useState(false);
  const [workerStatus, setWorkerStatus] = useState<{
    name: string;
    status: string;
    healthy: boolean;
  }>({ name: "flow-image-worker.service", status: "checking...", healthy: false });

  const [accounts, setAccounts] = useState<FlowAccount[]>([]);
  const [settings, setSettings] = useState<FlowSettings>({
    socks5_proxy: "socks5://127.0.0.1:10808",
    batch_size_per_account: 1,
    min_delay_sec: 5,
    max_delay_sec: 12,
    cooldown_minutes: 15,
    worker_enabled: true,
  });
  const [proxyStatus, setProxyStatus] = useState<FlowProxyStatus | null>(null);

  const [notification, setNotification] = useState<{
    type: "success" | "error" | "info";
    message: string;
  } | null>(null);

  const [copiedId, setCopiedId] = useState<number | null>(null);

  // Test Job Modal state
  const [testingAccountId, setTestingAccountId] = useState<number | null>(null);
  const [activeTestJob, setActiveTestJob] = useState<FlowJob | null>(null);
  const [testModalOpen, setTestModalOpen] = useState(false);

  const showNotification = (message: string, type: "success" | "error" | "info" = "success") => {
    setNotification({ message, type });
    setTimeout(() => {
      setNotification(null);
    }, 4000);
  };

  const loadData = useCallback(async () => {
    try {
      const [accRes, setRes, proxyRes] = await Promise.all([
        api.flow.getAccounts(),
        api.flow.getSettings(),
        api.flow.getProxyStatus().catch((e) => ({
          healthy: false,
          status: "offline" as const,
          host: "127.0.0.1",
          port: 10808,
          proxy_url: "socks5://127.0.0.1:10808",
          detail: e?.message || "Offline",
        })),
      ]);
      setWorkerStatus(accRes.worker_service);
      setAccounts(accRes.accounts);
      setSettings(setRes.settings);
      setProxyStatus(proxyRes);
    } catch (err: any) {
      console.error("Gagal memuat data Google Flow:", err);
      showNotification(err?.message || "Gagal memuat status Google Flow", "error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(() => {
      loadData();
    }, 10000);
    return () => clearInterval(interval);
  }, [loadData]);

  // Handle Save Settings
  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSavingSettings(true);
      const res = await api.flow.updateSettings(settings);
      setSettings(res.settings);
      showNotification("Pengaturan Google Flow worker berhasil disimpan!");
    } catch (err: any) {
      console.error(err);
      showNotification(err?.message || "Gagal menyimpan pengaturan", "error");
    } finally {
      setSavingSettings(false);
    }
  };

  // Handle Toggle Account Status
  const handleToggleAccount = async (account: FlowAccount) => {
    const nextStatus = account.status === "disabled" ? "active" : "disabled";
    try {
      await api.flow.patchAccount(account.id, { status: nextStatus });
      showNotification(`Akun #${account.id} sekarang ${nextStatus.toUpperCase()}`);
      loadData();
    } catch (err: any) {
      showNotification(err?.message || "Gagal mengubah status akun", "error");
    }
  };

  // Handle Reset Account
  const handleResetAccount = async (accountId: number) => {
    try {
      await api.flow.resetAccount(accountId);
      showNotification(`Akun #${accountId} berhasil di-reset ke ACTIVE!`);
      loadData();
    } catch (err: any) {
      showNotification(err?.message || "Gagal me-reset status akun", "error");
    }
  };

  // Handle Test Generate
  const handleTestGenerate = async (accountId: number) => {
    try {
      setTestingAccountId(accountId);
      setTestModalOpen(true);
      setActiveTestJob(null);
      const res = await api.flow.testAccount(accountId);
      showNotification(`Test job untuk Akun #${accountId} berhasil dimasukkan antrean!`, "info");

      // Polling test job
      const jobId = res.job_id;
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        try {
          const job = await api.flow.getJob(jobId);
          setActiveTestJob(job);
          if (job.status === "completed" || job.status === "failed" || attempts > 60) {
            clearInterval(poll);
            setTestingAccountId(null);
            loadData();
          }
        } catch {
          clearInterval(poll);
          setTestingAccountId(null);
        }
      }, 2500);
    } catch (err: any) {
      setTestingAccountId(null);
      const msg =
        (typeof err?.message === "string" && err.message !== "[object Object]" ? err.message : null) ||
        (typeof err?.detail === "string" ? err.detail : null) ||
        (typeof err?.message?.message === "string" ? err.message.message : null) ||
        (typeof err?.detail?.message === "string" ? err.detail.message : null) ||
        "Gagal menjalankan test generate";
      showNotification(msg, "error");
    }
  };

  const copyScriptCommand = (accountId: number) => {
    const cmd = `./scripts/login_flow_profile.sh ${accountId}`;
    navigator.clipboard.writeText(cmd);
    setCopiedId(accountId);
    setTimeout(() => setCopiedId(null), 2000);
    showNotification(`Perintah login Akun #${accountId} disalin!`);
  };

  const getStatusBadge = (status: string, cooldownUntil?: string | null) => {
    switch (status) {
      case "active":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            ACTIVE
          </span>
        );
      case "busy":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono font-bold bg-blue-500/15 text-blue-400 border border-blue-500/30">
            <Loader2 className="w-3 h-3 animate-spin" />
            BUSY
          </span>
        );
      case "cooldown": {
        let minutesLeft = 0;
        if (cooldownUntil) {
          const diff = new Date(cooldownUntil).getTime() - Date.now();
          minutesLeft = Math.max(0, Math.ceil(diff / 60000));
        }
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30">
            <Clock className="w-3 h-3" />
            COOLDOWN {minutesLeft > 0 ? `(${minutesLeft}m)` : ""}
          </span>
        );
      }
      case "need_relogin":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono font-bold bg-rose-500/15 text-rose-400 border border-rose-500/30">
            <ShieldAlert className="w-3 h-3" />
            NEED RE-LOGIN
          </span>
        );
      case "disabled":
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono font-bold bg-obsidian-muted/20 text-obsidian-muted border border-border">
            <Power className="w-3 h-3" />
            DISABLED
          </span>
        );
    }
  };

  return (
    <AppShell>
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 font-sans">
        {/* Toast Notification */}
        {notification && (
          <div
            className={`fixed bottom-6 right-6 z-50 px-4 py-3 rounded-lg shadow-studio border text-xs font-medium flex items-center gap-2 animate-in fade-in slide-in-from-bottom-5 duration-200 ${
              notification.type === "error"
                ? "bg-rose-950/90 border-rose-500/50 text-rose-200"
                : notification.type === "info"
                ? "bg-blue-950/90 border-blue-500/50 text-blue-200"
                : "bg-emerald-950/90 border-emerald-500/50 text-emerald-200"
            }`}
          >
            {notification.type === "error" ? (
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            ) : notification.type === "info" ? (
              <Loader2 className="w-4 h-4 text-blue-400 animate-spin shrink-0" />
            ) : (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            )}
            <span>{notification.message}</span>
          </div>
        )}

        {/* Page Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border pb-6">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-canvas border border-border text-amber-500">
                <SettingsIcon className="w-5 h-5" />
              </div>
              <h1 className="font-cinzel text-xl sm:text-2xl font-bold uppercase tracking-wider text-obsidian-primary">
                Google Flow Image Pool
              </h1>
            </div>
            <p className="mt-1 text-xs text-obsidian-muted">
              Sistem Otomasi 6 Profil Google Chrome (Batch Round-Robin) untuk Generasi Gambar 0 Poin
              (Gratis) di <span className="font-mono text-amber-400">labs.google/fx/tools/flow</span>
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Service Status Badge */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-panel border border-border">
              <Server className="w-4 h-4 text-obsidian-muted" />
              <span className="text-xs font-mono text-obsidian-secondary">Worker Service:</span>
              <span
                className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                  workerStatus.healthy
                    ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
                    : "bg-rose-500/20 text-rose-400 border border-rose-500/40"
                }`}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    workerStatus.healthy ? "bg-emerald-400 animate-pulse" : "bg-rose-400"
                  }`}
                />
                {workerStatus.status.toUpperCase()}
              </span>
            </div>

            {/* SOCKS5 Android Proxy Status Badge */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-panel border border-border">
              <span className="text-xs font-mono text-obsidian-secondary">SOCKS5 Android:</span>
              <span
                className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                  proxyStatus?.healthy
                    ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
                    : "bg-rose-500/20 text-rose-400 border border-rose-500/40"
                }`}
                title={proxyStatus?.detail || "SOCKS5 Proxy Status"}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    proxyStatus?.healthy ? "bg-emerald-400 animate-pulse" : "bg-rose-400"
                  }`}
                />
                {proxyStatus?.healthy ? `ONLINE (${proxyStatus.latency_ms}ms)` : "OFFLINE"}
              </span>
            </div>

            <button
              type="button"
              onClick={loadData}
              disabled={loading}
              className="p-2 rounded-lg bg-panel hover:bg-elevated border border-border text-obsidian-secondary hover:text-obsidian-primary transition-colors disabled:opacity-50"
              title="Refresh status"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>

        {/* =========================================================================
         * Configuration Form
         * ========================================================================= */}
        <section className="p-6 rounded-xl bg-panel border border-border shadow-studio space-y-4">
          <div className="flex items-center justify-between border-b border-border/70 pb-3">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-500" />
              <h2 className="font-cinzel text-sm font-bold uppercase tracking-wider text-obsidian-primary">
                Worker Configuration
              </h2>
            </div>
            <span className="text-[11px] font-mono text-obsidian-muted">
              Overrides .env defaults dynamically in DB
            </span>
          </div>

          <form onSubmit={handleSaveSettings} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* SOCKS5 Proxy */}
              <div className="space-y-1.5">
                <label className="text-[11px] font-mono text-obsidian-secondary flex items-center justify-between">
                  <span>SOCKS5 Proxy URL</span>
                  <span className="text-[9px] text-obsidian-muted">(Opsional)</span>
                </label>
                <input
                  type="text"
                  value={settings.socks5_proxy}
                  onChange={(e) => setSettings({ ...settings, socks5_proxy: e.target.value })}
                  placeholder="socks5://127.0.0.1:1080"
                  className="w-full px-3 py-1.5 rounded-lg bg-canvas border border-border text-obsidian-primary text-xs font-mono focus:outline-none focus:border-amber-500 transition-colors"
                />
              </div>

              {/* Batch Size */}
              <div className="space-y-1.5">
                <label className="text-[11px] font-mono text-obsidian-secondary">
                  Batch Size per Akun
                </label>
                <input
                  type="number"
                  min="1"
                  max="20"
                  value={settings.batch_size_per_account}
                  onChange={(e) =>
                    setSettings({ ...settings, batch_size_per_account: parseInt(e.target.value) || 1 })
                  }
                  className="w-full px-3 py-1.5 rounded-lg bg-canvas border border-border text-obsidian-primary text-xs font-mono focus:outline-none focus:border-amber-500 transition-colors"
                />
              </div>

              {/* Delay Min - Max */}
              <div className="space-y-1.5">
                <label className="text-[11px] font-mono text-obsidian-secondary">
                  Jeda Natural (Min - Max detik)
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min="1"
                    max="60"
                    value={settings.min_delay_sec}
                    onChange={(e) =>
                      setSettings({ ...settings, min_delay_sec: parseInt(e.target.value) || 1 })
                    }
                    className="w-full px-2.5 py-1.5 rounded-lg bg-canvas border border-border text-obsidian-primary text-xs font-mono focus:outline-none focus:border-amber-500"
                  />
                  <span className="text-obsidian-muted text-xs">-</span>
                  <input
                    type="number"
                    min="2"
                    max="120"
                    value={settings.max_delay_sec}
                    onChange={(e) =>
                      setSettings({ ...settings, max_delay_sec: parseInt(e.target.value) || 2 })
                    }
                    className="w-full px-2.5 py-1.5 rounded-lg bg-canvas border border-border text-obsidian-primary text-xs font-mono focus:outline-none focus:border-amber-500"
                  />
                </div>
              </div>

              {/* Cooldown Minutes & Toggle Worker */}
              <div className="space-y-1.5">
                <label className="text-[11px] font-mono text-obsidian-secondary">
                  Durasi Cooldown (Menit)
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    min="1"
                    max="1440"
                    value={settings.cooldown_minutes}
                    onChange={(e) =>
                      setSettings({ ...settings, cooldown_minutes: parseInt(e.target.value) || 15 })
                    }
                    className="w-24 px-3 py-1.5 rounded-lg bg-canvas border border-border text-obsidian-primary text-xs font-mono focus:outline-none focus:border-amber-500"
                  />

                  <label className="flex items-center gap-2 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={settings.worker_enabled}
                      onChange={(e) =>
                        setSettings({ ...settings, worker_enabled: e.target.checked })
                      }
                      className="sr-only peer"
                    />
                    <div className="w-8 h-4 bg-canvas border border-border peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-obsidian-muted peer-checked:after:bg-amber-400 after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-amber-500/20 peer-checked:border-amber-500/50 relative" />
                    <span className="text-xs font-medium text-obsidian-primary">
                      {settings.worker_enabled ? "Worker Aktif" : "Worker Jeda"}
                    </span>
                  </label>
                </div>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="submit"
                disabled={savingSettings}
                className="flex items-center gap-2 px-5 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-bold text-xs shadow-glow transition-all disabled:opacity-50"
              >
                {savingSettings ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Menyimpan...</span>
                  </>
                ) : (
                  <>
                    <Check className="w-3.5 h-3.5" />
                    <span>Simpan Pengaturan</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </section>

        {/* =========================================================================
         * 6-Account Pool Grid
         * ========================================================================= */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-cinzel text-sm font-bold uppercase tracking-wider text-obsidian-primary">
              Profil Google Flow (Pool 6 Akun)
            </h2>
            <span className="text-xs font-mono text-obsidian-muted">
              Total Render Terakumulasi:{" "}
              <span className="text-amber-400 font-bold">
                {accounts.reduce((acc, a) => acc + (a.total_count || 0), 0)}
              </span>{" "}
              gambar
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {accounts.map((account) => {
              const isTesting = testingAccountId === account.id;

              return (
                <div
                  key={account.id}
                  className="p-5 rounded-xl bg-panel border border-border shadow-studio flex flex-col justify-between space-y-4 transition-all hover:border-border/90"
                >
                  {/* Card Header */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="w-6 h-6 rounded bg-canvas border border-border text-amber-500 font-mono text-xs font-bold flex items-center justify-center shrink-0">
                          #{account.id}
                        </span>
                        <h3 className="font-semibold text-sm text-obsidian-primary truncate">
                          {account.label}
                        </h3>
                      </div>
                      {getStatusBadge(account.status, account.cooldown_until)}
                    </div>

                    <div className="text-[10px] font-mono text-obsidian-muted truncate">
                      {account.profile_dir}
                    </div>
                  </div>

                  {/* Render Stats */}
                  <div className="grid grid-cols-3 gap-2 py-3 px-3 rounded-lg bg-canvas border border-border/80 text-center font-mono">
                    <div>
                      <div className="text-[10px] text-obsidian-muted uppercase">Hari Ini</div>
                      <div className="text-sm font-bold text-obsidian-primary">
                        {account.daily_count}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-obsidian-muted uppercase">Total</div>
                      <div className="text-sm font-bold text-amber-400">
                        {account.total_count}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-obsidian-muted uppercase">Failures</div>
                      <div
                        className={`text-sm font-bold ${
                          account.consecutive_failures > 0 ? "text-rose-400" : "text-obsidian-muted"
                        }`}
                      >
                        {account.consecutive_failures}
                      </div>
                    </div>
                  </div>

                  {/* Last Error Box if present */}
                  {account.last_error && (
                    <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-[11px] font-mono break-all line-clamp-2">
                      <span className="font-bold text-rose-400">Error: </span>
                      {account.last_error}
                    </div>
                  )}

                  {/* Action Buttons */}
                  <div className="space-y-2 pt-2 border-t border-border/60">
                    <div className="flex items-center gap-2">
                      {/* Test Generate */}
                      <button
                        type="button"
                        onClick={() => handleTestGenerate(account.id)}
                        disabled={isTesting || account.status === "disabled"}
                        className="flex-1 flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-lg bg-canvas hover:bg-elevated border border-border text-amber-400 font-mono text-xs font-semibold transition-colors disabled:opacity-40"
                      >
                        {isTesting ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Play className="w-3 h-3 fill-current" />
                        )}
                        <span>Test Render</span>
                      </button>

                      {/* Reset Status */}
                      <button
                        type="button"
                        onClick={() => handleResetAccount(account.id)}
                        className="py-1.5 px-3 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-secondary hover:text-emerald-400 transition-colors"
                        title="Reset Status ke Active & bersihkan kegagalan"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                      </button>

                      {/* Enable/Disable Toggle */}
                      <button
                        type="button"
                        onClick={() => handleToggleAccount(account)}
                        className={`py-1.5 px-3 rounded-lg border transition-colors ${
                          account.status === "disabled"
                            ? "bg-canvas hover:bg-elevated border-border text-obsidian-muted hover:text-emerald-400"
                            : "bg-canvas hover:bg-elevated border-border text-obsidian-muted hover:text-rose-400"
                        }`}
                        title={account.status === "disabled" ? "Aktifkan Akun" : "Nonaktifkan Akun"}
                      >
                        <Power className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    {/* Helper Login Quick Copy */}
                    <button
                      type="button"
                      onClick={() => copyScriptCommand(account.id)}
                      className="w-full flex items-center justify-between px-2.5 py-1 rounded bg-canvas/60 hover:bg-canvas border border-border/50 text-[10px] font-mono text-obsidian-muted hover:text-obsidian-primary transition-colors"
                    >
                      <span className="truncate">
                        ./scripts/login_flow_profile.sh {account.id}
                      </span>
                      {copiedId === account.id ? (
                        <Check className="w-3 h-3 text-emerald-400 shrink-0 ml-1" />
                      ) : (
                        <Copy className="w-3 h-3 shrink-0 ml-1" />
                      )}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* =========================================================================
         * Terminal Login Guide Box
         * ========================================================================= */}
        <section className="p-6 rounded-xl bg-panel border border-border shadow-studio space-y-3 font-sans">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-amber-500" />
            <h3 className="font-cinzel text-xs font-bold uppercase tracking-wider text-obsidian-primary">
              Panduan Login Ulang Profil Google Flow
            </h3>
          </div>

          <div className="space-y-2 text-xs text-obsidian-secondary leading-relaxed">
            <p>
              Jika akun berstatus <span className="text-rose-400 font-bold">NEED RE-LOGIN</span> atau
              ingin login sesi baru untuk pertama kali:
            </p>
            <ol className="list-decimal list-inside space-y-1 pl-2 text-obsidian-muted font-mono text-[11px]">
              <li>
                Buka terminal VPS dan jalankan helper login:{" "}
                <code className="text-amber-400 bg-canvas px-1.5 py-0.5 rounded border border-border">
                  ./scripts/login_flow_profile.sh &lt;nomor_akun_1_sampai_6&gt;
                </code>
              </li>
              <li>
                Di laptop/komputer lokal Anda, buat SSH tunnel:{" "}
                <code className="text-amber-400 bg-canvas px-1.5 py-0.5 rounded border border-border">
                  ssh -N -L 6080:127.0.0.1:6080 ubuntu@&lt;IP_VPS&gt;
                </code>
              </li>
              <li>
                Buka browser di komputer lokal:{" "}
                <a
                  href="http://127.0.0.1:6080/vnc.html"
                  target="_blank"
                  rel="noreferrer"
                  className="text-amber-400 hover:underline"
                >
                  http://127.0.0.1:6080/vnc.html
                </a>{" "}
                lalu klik &quot;Connect&quot;.
              </li>
              <li>
                Selesaikan login Google di tampilan browser Google Flow. Setelah login selesai, tekan{" "}
                <kbd className="px-1 py-0.5 rounded bg-canvas border border-border text-obsidian-primary">
                  Ctrl + C
                </kbd>{" "}
                pada terminal VPS.
              </li>
              <li>
                Klik tombol <RotateCcw className="w-3 h-3 inline text-emerald-400" />{" "}
                <strong>Reset Status</strong> pada kartu akun di atas untuk mengaktifkannya kembali.
              </li>
            </ol>
          </div>
        </section>

        {/* =========================================================================
         * Test Result Modal
         * ========================================================================= */}
        {testModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
            <div className="w-full max-w-xl rounded-xl bg-panel border border-border shadow-studio p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-border pb-3">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-amber-500" />
                  <h3 className="font-cinzel text-sm font-bold uppercase tracking-wider text-obsidian-primary">
                    Uji Render Akun #{testingAccountId || activeTestJob?.assigned_account_id}
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => setTestModalOpen(false)}
                  className="text-obsidian-muted hover:text-obsidian-primary text-xs font-mono"
                >
                  Tutup [ESC]
                </button>
              </div>

              {activeTestJob ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-obsidian-muted">Status Job:</span>
                    <span
                      className={`font-bold ${
                        activeTestJob.status === "completed"
                          ? "text-emerald-400"
                          : activeTestJob.status === "failed"
                          ? "text-rose-400"
                          : "text-amber-400"
                      }`}
                    >
                      {activeTestJob.status.toUpperCase()}
                    </span>
                  </div>

                  <div className="p-3 rounded-lg bg-canvas border border-border text-xs text-obsidian-secondary font-mono">
                    <div className="text-[10px] text-obsidian-muted uppercase">Prompt:</div>
                    <div className="mt-0.5 line-clamp-2">{activeTestJob.prompt}</div>
                  </div>

                  {/* Gambar Hasil Render */}
                  {activeTestJob.image_url && (
                    <div className="space-y-2">
                      <div className="text-xs font-semibold text-emerald-400 flex items-center gap-1.5">
                        <CheckCircle2 className="w-4 h-4" />
                        <span>Render Berhasil (Disajikan via Nginx):</span>
                      </div>
                      <div className="aspect-video w-full rounded-lg overflow-hidden border border-border bg-black">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={activeTestJob.image_url}
                          alt="Test Result"
                          className="w-full h-full object-contain"
                        />
                      </div>
                      <div className="text-right">
                        <a
                          href={activeTestJob.image_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-xs text-amber-400 hover:underline font-mono"
                        >
                          <span>Buka Gambar Resolusi Penuh</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                    </div>
                  )}

                  {/* Error & Debug Screenshot */}
                  {activeTestJob.status === "failed" && (
                    <div className="space-y-3">
                      <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-mono">
                        <span className="font-bold text-rose-400">Pesan Error: </span>
                        {activeTestJob.error_message || "Generasi gambar gagal."}
                      </div>

                      {activeTestJob.debug_screenshot_url && (
                        <div className="space-y-1.5">
                          <div className="text-xs font-mono text-obsidian-muted">
                            Screenshot Debug UI Google Flow:
                          </div>
                          <div className="aspect-video w-full rounded-lg overflow-hidden border border-border bg-black">
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img
                              src={activeTestJob.debug_screenshot_url}
                              alt="Debug Screenshot"
                              className="w-full h-full object-contain"
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Sedang Berjalan */}
                  {activeTestJob.status !== "completed" && activeTestJob.status !== "failed" && (
                    <div className="py-8 flex flex-col items-center justify-center text-center space-y-3">
                      <Loader2 className="w-8 h-8 text-amber-500 animate-spin" />
                      <div className="space-y-1">
                        <p className="text-xs font-semibold text-obsidian-primary">
                          Sedang Memproses di Google Flow...
                        </p>
                        <p className="text-[11px] text-obsidian-muted font-mono">
                          Chrome sedang membuka canvas, mengisi prompt, dan menangkap gambar via virtual
                          display :99.
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="py-8 flex flex-col items-center justify-center text-center space-y-3">
                  <Loader2 className="w-8 h-8 text-amber-500 animate-spin" />
                  <p className="text-xs text-obsidian-muted font-mono">
                    Memasukkan job uji coba ke antrean worker...
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
