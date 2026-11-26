'use client';

import React, { useEffect, useMemo, useState } from 'react';
import {
  AI_RENDER_PROVIDERS,
  DEFAULT_FREE_PORTALS,
  FreePortalItem,
  ProviderCategory,
  UserProviderConfig,
} from '@/config/aiProviders';
import FreeGeneratePortals, {
  FREE_PORTALS_UPDATED_EVENT,
  emitFreePortalsUpdated,
} from './FreeGeneratePortals';

interface Props {
  projectId: string;
  initialProviderId?: string;
  socks5Online?: boolean;
  onCheckSocks5?: () => void;
  onSaveGlobalConfig?: (payload: {
    activeProviderId: string;
    applyToAllScenes: boolean;
    configs: Record<string, UserProviderConfig>;
    freePortals: FreePortalItem[];
  }) => Promise<void> | void;
}

const STORAGE_KEY = 'movieai_global_render_provider_v2';

export default function AIRenderProviderCard({
  projectId,
  initialProviderId = 'google-flow',
  socks5Online = false,
  onCheckSocks5,
  onSaveGlobalConfig,
}: Props) {
  const [activeTab, setActiveTab] = useState<ProviderCategory>('core');
  const [selectedId, setSelectedId] = useState<string>(initialProviderId);
  const [savedProviderId, setSavedProviderId] = useState<string>(initialProviderId);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState<boolean>(false);
  const [applyToAllScenes, setApplyToAllScenes] = useState<boolean>(true);
  const [showKey, setShowKey] = useState<boolean>(false);
  const [saving, setSaving] = useState<boolean>(false);
  const [statusMsg, setStatusMsg] = useState<string>('');

  // Ping / Test API Key State
  const [testingKey, setTestingKey] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<{
    ok?: boolean;
    message?: string;
  } | null>(null);

  // Konfigurasi Base URL, API Key, & Model ID per provider
  const [configs, setConfigs] = useState<Record<string, UserProviderConfig>>(() => {
    const map: Record<string, UserProviderConfig> = {};
    for (const p of AI_RENDER_PROVIDERS) {
      map[p.id] = {
        baseUrl: p.defaultBaseUrl,
        apiKey: '',
        modelId: p.defaultModelId,
      };
    }
    return map;
  });

  // Free Generate Portals (synced via SQLite, localStorage, & custom event)
  const [freePortals, setFreePortals] = useState<FreePortalItem[]>(DEFAULT_FREE_PORTALS);

  // Load saved state dari backend API & localStorage fallback
  useEffect(() => {
    let isMounted = true;

    async function loadSettings() {
      // 1. Coba baca langsung dari backend SQLite sebagai Source of Truth (Multi-Device Sync HP & PC)
      try {
        const res = await fetch(`/api/v1/projects/${projectId}/render-provider`, {
          headers: { Accept: 'application/json' },
        });
        if (res.ok) {
          const data = await res.json();
          if (data.configured && isMounted) {
            if (data.activeProviderId) {
              setSelectedId(data.activeProviderId);
              setSavedProviderId(data.activeProviderId);
              setHasUnsavedChanges(false);
            }
            if (typeof data.applyToAllScenes === 'boolean') {
              setApplyToAllScenes(data.applyToAllScenes);
            }
            if (data.configs) {
              setConfigs((prev) => ({ ...prev, ...data.configs }));
            }
            if (Array.isArray(data.freePortals)) {
              setFreePortals(data.freePortals);
            }
            // Update browser localStorage sebagai offline cache
            try {
              localStorage.setItem(
                `${STORAGE_KEY}_${projectId}`,
                JSON.stringify({
                  activeProviderId: data.activeProviderId,
                  applyToAllScenes: data.applyToAllScenes,
                  configs: data.configs,
                  freePortals: data.freePortals,
                })
              );
            } catch {}
            return;
          }
        }
      } catch {
        // Fallback ke localStorage jika network gagal / offline
      }

      // 2. Fallback baca dari browser localStorage jika SQLite belum dikonfigurasi / offline
      try {
        const raw = localStorage.getItem(`${STORAGE_KEY}_${projectId}`);
        if (!raw || !isMounted) return;
        const parsed = JSON.parse(raw);
        if (parsed.activeProviderId) setSelectedId(parsed.activeProviderId);
        if (typeof parsed.applyToAllScenes === 'boolean') {
          setApplyToAllScenes(parsed.applyToAllScenes);
        }
        if (parsed.configs) {
          setConfigs((prev) => ({ ...prev, ...parsed.configs }));
        }
        if (Array.isArray(parsed.freePortals)) {
          setFreePortals(parsed.freePortals);
        }
      } catch {
        // Abaikan jika JSON rusak
      }
    }

    loadSettings();

    const handlePortalsSync = (ev: Event) => {
      const detail = (ev as CustomEvent<{ projectId?: string; freePortals?: FreePortalItem[] }>).detail;
      if (detail?.projectId === projectId && Array.isArray(detail.freePortals) && isMounted) {
        setFreePortals(detail.freePortals);
      }
    };

    window.addEventListener(FREE_PORTALS_UPDATED_EVENT, handlePortalsSync);
    return () => {
      isMounted = false;
      window.removeEventListener(FREE_PORTALS_UPDATED_EVENT, handlePortalsSync);
    };
  }, [projectId]);

  const activeProvider = useMemo(
    () => AI_RENDER_PROVIDERS.find((p) => p.id === selectedId) ?? AI_RENDER_PROVIDERS[0],
    [selectedId]
  );

  const activeConfig = configs[activeProvider.id] ?? {
    baseUrl: activeProvider.defaultBaseUrl,
    apiKey: '',
    modelId: activeProvider.defaultModelId,
  };

  const filteredProviders = useMemo(
    () => AI_RENDER_PROVIDERS.filter((p) => p.category === activeTab),
    [activeTab]
  );

  const updateActiveConfig = (patch: Partial<UserProviderConfig>) => {
    setConfigs((prev) => ({
      ...prev,
      [activeProvider.id]: {
        ...activeConfig,
        ...patch,
      },
    }));
    setHasUnsavedChanges(true);
    setTestResult(null); // Reset hasil ping jika config berubah
  };

  // Mode Custom Model ID: apakah model saat ini bukan bagian dari preset options
  const isCustomModel = useMemo(() => {
    if (!activeProvider.modelOptions) return false;
    return !activeProvider.modelOptions.some((opt) => opt.id === activeConfig.modelId);
  }, [activeProvider, activeConfig.modelId]);

  // Handler Test/Ping API Key
  const handleTestApiKey = async () => {
    setTestingKey(true);
    setTestResult(null);
    try {
      const res = await fetch(`/api/v1/projects/${projectId}/render-provider/test-key`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          providerId: activeProvider.id,
          baseUrl: activeConfig.baseUrl,
          apiKey: activeConfig.apiKey,
          modelId: activeConfig.modelId,
        }),
      });

      const data = await res.json();
      if (res.ok && data.ok) {
        setTestResult({
          ok: true,
          message: data.message || '✓ API Key valid & quota active (200 OK)',
        });
      } else {
        setTestResult({
          ok: false,
          message: data.detail || data.message || `HTTP ${res.status}: Gagal verifikasi kunci`,
        });
      }
    } catch (err: unknown) {
      setTestResult({
        ok: false,
        message: err instanceof Error ? err.message : 'Koneksi ke backend gagal',
      });
    } finally {
      setTestingKey(false);
    }
  };

  const handleSaveAll = async () => {
    setSaving(true);
    setStatusMsg('');
    const payload = {
      activeProviderId: selectedId,
      applyToAllScenes,
      configs,
      freePortals,
    };

    try {
      localStorage.setItem(`${STORAGE_KEY}_${projectId}`, JSON.stringify(payload));

      const res = await fetch(`/api/v1/projects/${projectId}/render-provider`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (onSaveGlobalConfig) {
        await onSaveGlobalConfig(payload);
      }

      if (res.ok) {
        setSavedProviderId(selectedId);
        setHasUnsavedChanges(false);
        setStatusMsg(
          applyToAllScenes
            ? `Tersimpan & diterapkan global ke seluruh scene (${activeProvider.name})`
            : `Tersimpan untuk MPB (${activeProvider.name})`
        );
      } else {
        setStatusMsg('Tersimpan di browser lokal (Sinkronisasi SQLite status: error)');
      }
    } catch {
      setStatusMsg('Gagal menyinkronkan ke server SQLite, tersimpan di browser.');
    } finally {
      setSaving(false);
    }
  };

  const syncFreePortalsToSQLite = async (updatedPortals: FreePortalItem[]) => {
    try {
      const payload = {
        activeProviderId: selectedId,
        applyToAllScenes,
        configs,
        freePortals: updatedPortals,
      };
      localStorage.setItem(`${STORAGE_KEY}_${projectId}`, JSON.stringify(payload));
      emitFreePortalsUpdated(projectId, updatedPortals);
      await fetch(`/api/v1/projects/${projectId}/render-provider`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch (err) {
      console.warn('Auto-sync free portals to SQLite failed:', err);
    }
  };

  return (
    <div className="rounded-xl border border-slate-800 bg-[#0b101b] p-3 sm:p-4 font-mono text-slate-200 shadow-xl">
      {/* Header */}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/80 pb-2.5">
        <div className="flex items-center gap-2">
          <span className="text-amber-400">✨</span>
          <h3 className="text-xs font-bold tracking-wider text-slate-200 uppercase">
            AI Render Provider (Global Acuan)
          </h3>
        </div>
        <span className="rounded bg-amber-500/15 px-2.5 py-0.5 text-[10px] font-semibold text-amber-400 border border-amber-500/30">
          Aktif: {activeProvider.name}
        </span>
      </div>

      {/* Category Tabs */}
      <div className="mb-3 grid grid-cols-3 gap-1.5 rounded-lg bg-[#070a12] p-1 border border-slate-800/80">
        {(
          [
            { key: 'core', label: 'Core (3)' },
            { key: 'priority', label: 'Cloud Utama (4)' },
            { key: 'additional', label: 'Top 10 Lain' },
          ] as { key: ProviderCategory; label: string }[]
        ).map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className={`rounded-md py-1.5 text-[11px] font-semibold transition ${
              activeTab === tab.key
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/50 shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Daftar Model + Link Portal di Sebelah Kanan */}
      <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
        {filteredProviders.map((provider) => {
          const isSelected = provider.id === selectedId;
          const hasKey = Boolean(configs[provider.id]?.apiKey?.trim());

          return (
            <div
              key={provider.id}
              className={`flex items-center justify-between gap-2 rounded-lg border px-3 py-2 transition ${
                isSelected
                  ? 'border-amber-400 bg-amber-500/15 shadow-[0_0_12px_rgba(245,158,11,0.15)]'
                  : 'border-slate-800 bg-[#111827] hover:border-slate-700'
              }`}
            >
              {/* Area Pilih Model */}
              <button
                type="button"
                onClick={() => {
                  setSelectedId(provider.id);
                  setHasUnsavedChanges(provider.id !== savedProviderId);
                  setTestResult(null);
                }}
                className="flex flex-1 flex-col items-start text-left min-w-0"
              >
                <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
                  <span
                    className={`text-xs font-bold truncate ${
                      isSelected ? 'text-amber-300' : 'text-slate-100'
                    }`}
                  >
                    {provider.name}
                  </span>
                  <span className="text-[10px] text-slate-400">{provider.badge}</span>
                  {provider.requiresApiKey && (
                    <span
                      className={`h-2 w-2 rounded-full ${
                        hasKey ? 'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]' : 'bg-slate-600'
                      }`}
                      title={hasKey ? 'API Key terisi' : 'API Key belum diisi'}
                    />
                  )}
                </div>
                <span className="text-[10px] text-slate-500">{provider.vendor}</span>
              </button>

              {/* Tombol Link Portal di Sebelah Kanan */}
              <a
                href={provider.portalUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="shrink-0 rounded border border-slate-700 bg-slate-900 px-2.5 py-1 text-[10px] font-semibold text-sky-400 hover:border-sky-400 hover:bg-sky-500/10 transition"
                title={`Buka portal ${provider.portalLabel}`}
              >
                {provider.portalLabel} ↗
              </a>
            </div>
          );
        })}
      </div>

      {/* Panel Konfigurasi Base URL, Model ID, & API Key */}
      <div className="mt-4 rounded-lg border border-slate-800 bg-[#0d1322] p-3 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-1 border-b border-slate-800 pb-2">
          <span className="text-[11px] font-bold text-amber-400 uppercase">
            Konfigurasi: {activeProvider.name}
          </span>
          <a
            href={activeProvider.portalUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[10px] text-sky-400 underline hover:text-sky-300"
          >
            Ambil API Key ↗
          </a>
        </div>

        {/* Base URL */}
        <div>
          <label className="mb-1 block text-[10px] text-slate-400 uppercase">Base URL</label>
          <input
            type="url"
            value={activeConfig.baseUrl}
            onChange={(e) => updateActiveConfig({ baseUrl: e.target.value })}
            placeholder={activeProvider.defaultBaseUrl}
            className="w-full rounded border border-slate-700 bg-[#070a12] px-2.5 py-1.5 text-xs text-slate-200 focus:border-amber-400 focus:outline-none"
          />
        </div>

        {/* Model ID with Presets + Custom Option */}
        <div>
          <div className="mb-1 flex items-center justify-between">
            <label className="text-[10px] text-slate-400 uppercase">Model ID</label>
            {activeProvider.modelOptions && (
              <span className="text-[9px] text-slate-500">
                {isCustomModel ? 'Mode: Custom Model String' : 'Mode: Preset'}
              </span>
            )}
          </div>
          {activeProvider.modelOptions ? (
            <div className="space-y-1.5">
              <select
                value={isCustomModel ? '__custom__' : activeConfig.modelId}
                onChange={(e) => {
                  if (e.target.value === '__custom__') {
                    // Beri default custom jika sebelumnya pakai preset
                    updateActiveConfig({ modelId: activeConfig.modelId });
                  } else {
                    updateActiveConfig({ modelId: e.target.value });
                  }
                }}
                className="w-full rounded border border-slate-700 bg-[#070a12] px-2.5 py-1.5 text-xs text-slate-200 focus:border-amber-400 focus:outline-none"
              >
                {activeProvider.modelOptions.map((opt) => (
                  <option key={opt.id} value={opt.id}>
                    {opt.label}
                  </option>
                ))}
                <option value="__custom__">+ Custom Model ID... (Bebas Ketik)</option>
              </select>

              {isCustomModel && (
                <input
                  type="text"
                  value={activeConfig.modelId}
                  onChange={(e) => updateActiveConfig({ modelId: e.target.value })}
                  placeholder="Ketik string model kustom (cth: qwen-mt-image-2.0)"
                  className="w-full rounded border border-amber-500/50 bg-[#070a12] px-2.5 py-1.5 text-xs text-amber-200 focus:border-amber-400 focus:outline-none"
                />
              )}
            </div>
          ) : (
            <input
              type="text"
              value={activeConfig.modelId}
              onChange={(e) => updateActiveConfig({ modelId: e.target.value })}
              placeholder={activeProvider.defaultModelId}
              className="w-full rounded border border-slate-700 bg-[#070a12] px-2.5 py-1.5 text-xs text-slate-200 focus:border-amber-400 focus:outline-none"
            />
          )}
        </div>

        {/* API Key Input + Ping Button */}
        {activeProvider.requiresApiKey && (
          <div>
            <div className="mb-1 flex items-center justify-between">
              <label className="text-[10px] text-slate-400 uppercase">API Key</label>
              {testResult && (
                <span
                  className={`text-[10px] font-semibold ${
                    testResult.ok ? 'text-emerald-400' : 'text-rose-400'
                  }`}
                >
                  {testResult.message}
                </span>
              )}
            </div>
            <div className="flex gap-1.5">
              <input
                type={showKey ? 'text' : 'password'}
                value={activeConfig.apiKey}
                onChange={(e) => updateActiveConfig({ apiKey: e.target.value })}
                placeholder={activeProvider.apiKeyPlaceholder}
                autoComplete="off"
                className="w-full rounded border border-slate-700 bg-[#070a12] px-2.5 py-1.5 text-xs text-slate-200 focus:border-amber-400 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => setShowKey((s) => !s)}
                className="shrink-0 rounded border border-slate-700 bg-slate-800 px-2 text-[10px] text-slate-300 hover:bg-slate-700"
              >
                {showKey ? 'Hide' : 'Show'}
              </button>
              <button
                type="button"
                onClick={handleTestApiKey}
                disabled={testingKey || !activeConfig.apiKey}
                className="shrink-0 rounded border border-sky-600/50 bg-sky-950/60 px-2.5 text-[10px] font-bold text-sky-300 hover:bg-sky-900/60 disabled:opacity-40 transition"
                title="Kirim lightweight request untuk verifikasi API key sebelum render"
              >
                {testingKey ? 'Pinging...' : '⚡ Test Key'}
              </button>
            </div>
          </div>
        )}

        {/* SOCKS5 Bar khusus Google Flow */}
        {activeProvider.requiresProxy && (
          <div className="flex items-center justify-between rounded border border-slate-800 bg-[#070a12] px-3 py-2">
            <div className="flex items-center gap-2 text-[11px]">
              <span
                className={`h-2 w-2 rounded-full ${
                  socks5Online ? 'bg-emerald-400' : 'bg-rose-500'
                }`}
              />
              <span className="text-slate-400">SOCKS5 ANDROID:</span>
              <span className={socks5Online ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                {socks5Online ? 'ONLINE' : 'OFFLINE'}
              </span>
            </div>
            <button
              type="button"
              onClick={onCheckSocks5}
              className="rounded border border-slate-700 bg-slate-800 px-2 py-1 text-[10px] text-slate-200 hover:border-amber-400"
            >
              [Check Connection]
            </button>
          </div>
        )}

        {/* Peringatan Visual Anchoring */}
        {!activeProvider.supportsVisualAnchor && (
          <div className="rounded border border-amber-500/40 bg-amber-500/10 p-2.5 text-[11px] text-amber-200">
            <p className="font-bold text-amber-400">⚠ VISUAL ANCHORING TIDAK AKTIF</p>
            <p className="mt-1 text-slate-300">
              Engine <strong>{activeProvider.name}</strong> berjalan dalam mode Text-to-Image murni.
              Berisiko terjadi <em>character drift</em>. Untuk konsistensi 100%, gunakan Google Flow,
              Gemini Direct, Qwen Image, atau Seedream 5.5.
            </p>
          </div>
        )}

        {/* Toggle Terapkan ke Seluruh Scene + Tombol Simpan */}
        {(hasUnsavedChanges || selectedId !== savedProviderId) && (
          <div className="rounded border border-amber-500/40 bg-amber-500/10 px-2.5 py-1.5 text-[10px] text-amber-300">
            Perubahan provider/konfigurasi (<strong>{activeProvider.name}</strong>) belum disimpan — klik{' '}
            <strong>Save Global Provider</strong> untuk mengaktifkan saat render.
          </div>
        )}
        <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-slate-800/80">
          <label className="flex items-center gap-2 text-[11px] text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={applyToAllScenes}
              onChange={(e) => setApplyToAllScenes(e.target.checked)}
              className="accent-amber-400"
            />
            Jadikan acuan global seluruh Storyboard Scene
          </label>

          <button
            type="button"
            disabled={saving}
            onClick={handleSaveAll}
            className="rounded-md bg-amber-500 px-3.5 py-1.5 text-xs font-bold text-slate-950 hover:bg-amber-400 disabled:opacity-50 transition shadow-sm"
          >
            {saving ? 'Menyimpan...' : 'Save Global Provider'}
          </button>
        </div>

        {statusMsg && <p className="text-[11px] text-emerald-400">{statusMsg}</p>}
      </div>

      {/* === SPOILER: FREE GENERATE PORTALS === */}
      <FreeGeneratePortals
        projectId={projectId}
        portals={freePortals}
        onPortalsChange={(updated) => {
          setFreePortals(updated);
          void syncFreePortalsToSQLite(updated);
        }}
        className="mt-4"
      />

      {/* Footer Target */}
      <div className="mt-3 flex items-center justify-between text-[10px] text-slate-500">
        <span>
          Render target: <strong className="text-emerald-400">Persistent SQLite Storage</strong>
        </span>
        <span>Project: {projectId}</span>
      </div>
    </div>
  );
}
