'use client';

import React, { useEffect, useState } from 'react';
import {
  AI_RENDER_PROVIDERS,
  DEFAULT_FREE_PORTALS,
  FreePortalItem,
  UserProviderConfig,
} from '@/config/aiProviders';

export const GLOBAL_PROVIDER_STORAGE_KEY = 'movieai_global_render_provider_v2';
export const FREE_PORTALS_UPDATED_EVENT = 'movieai:free-portals-updated';

interface StoredRenderSettingsSnapshot {
  activeProviderId?: string;
  applyToAllScenes?: boolean;
  configs?: Record<string, UserProviderConfig>;
  freePortals?: FreePortalItem[];
}

function buildDefaultConfigs(): Record<string, UserProviderConfig> {
  const map: Record<string, UserProviderConfig> = {};
  for (const p of AI_RENDER_PROVIDERS) {
    map[p.id] = {
      baseUrl: p.defaultBaseUrl,
      apiKey: '',
      modelId: p.defaultModelId,
    };
  }
  return map;
}

export function emitFreePortalsUpdated(projectId: string, freePortals: FreePortalItem[]) {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(
    new CustomEvent(FREE_PORTALS_UPDATED_EVENT, {
      detail: { projectId, freePortals },
    })
  );
}

function readLocalPortals(projectId: string): FreePortalItem[] | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(`${GLOBAL_PROVIDER_STORAGE_KEY}_${projectId}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredRenderSettingsSnapshot;
    if (Array.isArray(parsed?.freePortals)) {
      return parsed.freePortals;
    }
  } catch {
    // ignore corrupted JSON
  }
  return null;
}

async function syncStandalonePortalsToStorageAndSQLite(
  projectId: string,
  updatedPortals: FreePortalItem[]
) {
  let baseSnapshot: StoredRenderSettingsSnapshot = {};
  try {
    const raw = localStorage.getItem(`${GLOBAL_PROVIDER_STORAGE_KEY}_${projectId}`);
    if (raw) {
      baseSnapshot = JSON.parse(raw) as StoredRenderSettingsSnapshot;
    }
  } catch {
    baseSnapshot = {};
  }

  // Update localStorage cache immediately so local state stays in sync even offline
  try {
    localStorage.setItem(
      `${GLOBAL_PROVIDER_STORAGE_KEY}_${projectId}`,
      JSON.stringify({
        activeProviderId: baseSnapshot.activeProviderId || 'google-flow',
        applyToAllScenes:
          typeof baseSnapshot.applyToAllScenes === 'boolean' ? baseSnapshot.applyToAllScenes : true,
        configs: baseSnapshot.configs || buildDefaultConfigs(),
        freePortals: updatedPortals,
      })
    );
  } catch {
    // ignore storage quota errors
  }

  try {
    // Fetch latest server snapshot so we preserve activeProviderId & masked encrypted API keys
    const getRes = await fetch(`/api/v1/projects/${projectId}/render-provider`, {
      headers: { Accept: 'application/json' },
    });
    if (!getRes.ok && !baseSnapshot.configs) {
      // Avoid overwriting server provider API keys if server snapshot could not be read
      return;
    }
    if (getRes.ok) {
      const serverData = (await getRes.json()) as StoredRenderSettingsSnapshot & {
        configured?: boolean;
      };
      if (serverData.configured) {
        baseSnapshot = {
          activeProviderId: serverData.activeProviderId || baseSnapshot.activeProviderId,
          applyToAllScenes:
            typeof serverData.applyToAllScenes === 'boolean'
              ? serverData.applyToAllScenes
              : baseSnapshot.applyToAllScenes,
          configs: serverData.configs || baseSnapshot.configs,
        };
      }
    }

    const payload = {
      activeProviderId: baseSnapshot.activeProviderId || 'google-flow',
      applyToAllScenes:
        typeof baseSnapshot.applyToAllScenes === 'boolean' ? baseSnapshot.applyToAllScenes : true,
      configs: {
        ...buildDefaultConfigs(),
        ...(baseSnapshot.configs || {}),
      },
      freePortals: updatedPortals,
    };

    try {
      localStorage.setItem(`${GLOBAL_PROVIDER_STORAGE_KEY}_${projectId}`, JSON.stringify(payload));
    } catch {
      // ignore storage quota errors
    }

    await fetch(`/api/v1/projects/${projectId}/render-provider`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch (err) {
    console.warn('Auto-sync free portals to SQLite failed:', err);
  }
}

export interface FreeGeneratePortalsProps {
  projectId: string;
  portals?: FreePortalItem[];
  onPortalsChange?: (updatedPortals: FreePortalItem[]) => void;
  defaultOpen?: boolean;
  className?: string;
}

export default function FreeGeneratePortals({
  projectId,
  portals,
  onPortalsChange,
  defaultOpen = false,
  className = '',
}: FreeGeneratePortalsProps) {
  const isControlled = Array.isArray(portals) && typeof onPortalsChange === 'function';

  const [freeOpen, setFreeOpen] = useState<boolean>(defaultOpen);
  const [localPortals, setLocalPortals] = useState<FreePortalItem[]>(
    () => readLocalPortals(projectId) ?? DEFAULT_FREE_PORTALS
  );
  const [newFreeName, setNewFreeName] = useState('');
  const [newFreeUrl, setNewFreeUrl] = useState('');
  const [newFreeNote, setNewFreeNote] = useState('');

  // Hydrate & keep standalone instance synchronized with SQLite + localStorage + sibling components
  useEffect(() => {
    if (isControlled) return;
    let isMounted = true;

    const cached = readLocalPortals(projectId);
    if (cached && isMounted) {
      setLocalPortals(cached);
    }

    async function loadFromServer() {
      try {
        const res = await fetch(`/api/v1/projects/${projectId}/render-provider`, {
          headers: { Accept: 'application/json' },
        });
        if (!res.ok || !isMounted) return;
        const data = await res.json();
        if (data?.configured && Array.isArray(data.freePortals) && isMounted) {
          setLocalPortals(data.freePortals);
          try {
            localStorage.setItem(
              `${GLOBAL_PROVIDER_STORAGE_KEY}_${projectId}`,
              JSON.stringify({
                activeProviderId: data.activeProviderId,
                applyToAllScenes: data.applyToAllScenes,
                configs: data.configs,
                freePortals: data.freePortals,
              })
            );
          } catch {
            // ignore storage errors
          }
        }
      } catch {
        // fallback already loaded from localStorage / defaults
      }
    }

    loadFromServer();

    const handleCustomSync = (ev: Event) => {
      const detail = (ev as CustomEvent<{ projectId?: string; freePortals?: FreePortalItem[] }>).detail;
      if (detail?.projectId === projectId && Array.isArray(detail.freePortals) && isMounted) {
        setLocalPortals(detail.freePortals);
      }
    };

    const handleStorageSync = (ev: StorageEvent) => {
      if (ev.key !== `${GLOBAL_PROVIDER_STORAGE_KEY}_${projectId}` || !ev.newValue || !isMounted) return;
      try {
        const parsed = JSON.parse(ev.newValue) as StoredRenderSettingsSnapshot;
        if (Array.isArray(parsed?.freePortals)) {
          setLocalPortals(parsed.freePortals);
        }
      } catch {
        // ignore invalid JSON
      }
    };

    window.addEventListener(FREE_PORTALS_UPDATED_EVENT, handleCustomSync);
    window.addEventListener('storage', handleStorageSync);
    return () => {
      isMounted = false;
      window.removeEventListener(FREE_PORTALS_UPDATED_EVENT, handleCustomSync);
      window.removeEventListener('storage', handleStorageSync);
    };
  }, [isControlled, projectId]);

  const activePortals = isControlled ? portals : localPortals;

  const commitPortalsUpdate = (updated: FreePortalItem[]) => {
    if (isControlled) {
      onPortalsChange(updated);
      emitFreePortalsUpdated(projectId, updated);
      return;
    }
    setLocalPortals(updated);
    emitFreePortalsUpdated(projectId, updated);
    void syncStandalonePortalsToStorageAndSQLite(projectId, updated);
  };

  const handleAddFreePortal = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFreeName.trim() || !newFreeUrl.trim()) return;
    const normalizedUrl = newFreeUrl.trim().startsWith('http')
      ? newFreeUrl.trim()
      : `https://${newFreeUrl.trim()}`;

    const updated: FreePortalItem[] = [
      ...activePortals,
      {
        id: `free-${Date.now()}`,
        name: newFreeName.trim(),
        url: normalizedUrl,
        note: newFreeNote.trim() || undefined,
      },
    ];
    setNewFreeName('');
    setNewFreeUrl('');
    setNewFreeNote('');
    commitPortalsUpdate(updated);
  };

  const handleDeleteFreePortal = (id: string) => {
    const updated = activePortals.filter((item) => item.id !== id);
    commitPortalsUpdate(updated);
  };

  return (
    <div className={`rounded-lg border border-slate-800 bg-[#070a12] font-mono ${className}`.trim()}>
      <button
        type="button"
        onClick={() => setFreeOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2.5 text-left text-xs font-bold text-emerald-400 hover:bg-slate-900/60 transition rounded-lg"
      >
        <span>🎁 Free Generate Portals ({activePortals.length} tersimpan)</span>
        <span className="text-slate-400 shrink-0">{freeOpen ? '▲ Tutup' : '▼ Buka'}</span>
      </button>

      {freeOpen && (
        <div className="border-t border-slate-800 p-3 space-y-3">
          {/* Daftar Link Tersimpan */}
          <div className="space-y-2">
            {activePortals.map((item) => (
              <div
                key={item.id}
                className="flex items-center justify-between gap-2 rounded border border-slate-800 bg-[#111827] px-2.5 py-2"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-semibold text-slate-100">{item.name}</p>
                  {item.note && <p className="truncate text-[10px] text-slate-400">{item.note}</p>}
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rounded bg-emerald-500/20 border border-emerald-500/40 px-2.5 py-1 text-[10px] font-bold text-emerald-300 hover:bg-emerald-500/30 transition"
                  >
                    Buka ↗
                  </a>
                  <button
                    type="button"
                    onClick={() => handleDeleteFreePortal(item.id)}
                    className="rounded border border-rose-500/30 px-2 py-1 text-[10px] text-rose-400 hover:bg-rose-500/10 transition"
                    title="Hapus link"
                  >
                    ✕
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Form Tambah Link Free Generate Baru */}
          <form onSubmit={handleAddFreePortal} className="space-y-2 border-t border-slate-800 pt-2.5">
            <p className="text-[10px] font-semibold text-slate-400 uppercase">
              + Tambah Portal Free Generate
            </p>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <input
                type="text"
                value={newFreeName}
                onChange={(e) => setNewFreeName(e.target.value)}
                placeholder="Nama Portal (cth: Whisk / Bing)"
                className="min-w-0 rounded border border-slate-700 bg-[#0b101b] px-2.5 py-1.5 text-xs text-slate-200 focus:border-emerald-400 focus:outline-none"
              />
              <input
                type="text"
                value={newFreeUrl}
                onChange={(e) => setNewFreeUrl(e.target.value)}
                placeholder="https://..."
                className="min-w-0 rounded border border-slate-700 bg-[#0b101b] px-2.5 py-1.5 text-xs text-slate-200 focus:border-emerald-400 focus:outline-none"
              />
            </div>
            <div className="flex flex-col sm:flex-row gap-2">
              <input
                type="text"
                value={newFreeNote}
                onChange={(e) => setNewFreeNote(e.target.value)}
                placeholder="Catatan kuota gratis (opsional)"
                className="min-w-0 flex-1 rounded border border-slate-700 bg-[#0b101b] px-2.5 py-1.5 text-xs text-slate-200 focus:border-emerald-400 focus:outline-none"
              />
              <button
                type="submit"
                className="rounded bg-emerald-500 px-3 py-1.5 text-xs font-bold text-slate-950 hover:bg-emerald-400 transition shrink-0"
              >
                Simpan Link
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
