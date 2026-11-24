"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Clapperboard,
  LayoutDashboard,
  Film,
  BookOpen,
  Grid,
  LogOut,
  Menu,
  X,
  ChevronDown,
  ChevronRight,
  Settings,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { api, Project } from "@/lib/api";
import { cn } from "@/lib/utils";

interface AppShellProps {
  children: React.ReactNode;
  activeProjectId?: string;
  activeProjectTitle?: string;
  currentStage?: number;
  stageName?: string;
}

export default function AppShell({
  children,
  activeProjectId,
  activeProjectTitle,
  currentStage,
  stageName,
}: AppShellProps) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const [isMyProjectsExpanded, setIsMyProjectsExpanded] = useState(true);

  // Synchronized User Projects Query (identical queryKey and limit to DashboardPage)
  const { data: projectsData, isLoading: projectsLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.projects.list({ limit: 200 }),
    enabled: !!user,
  });

  const userProjects: Project[] = projectsData?.data || [];

  // Stage color coding helper for project hierarchy
  const getStageBadgeStyle = (stage: number) => {
    if (stage <= 5) {
      return "bg-blue-500/10 text-blue-400 border-blue-500/30";
    }
    if (stage <= 11) {
      return "bg-amber-500/10 text-amber-400 border-amber-500/30";
    }
    return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
  };

  // Navigation Links
  const navItems = [
    {
      name: "Production Slate",
      href: "/dashboard",
      icon: LayoutDashboard,
      active: pathname === "/dashboard",
    },
    {
      name: "Settings & Flow Pool",
      href: "/settings",
      icon: Settings,
      active: pathname === "/settings",
    },
    ...(activeProjectId
      ? [
          {
            name: "NLE Studio",
            href: `/projects/${activeProjectId}/studio`,
            icon: Film,
            active: pathname?.includes(`/projects/${activeProjectId}/studio`),
          },
          {
            name: "Production Bible",
            href: `/projects/${activeProjectId}/bible`,
            icon: BookOpen,
            active: pathname?.includes(`/projects/${activeProjectId}/bible`),
          },
          {
            name: "50-Scene Storyboard",
            href: `/projects/${activeProjectId}/scenes`,
            icon: Grid,
            active: pathname?.includes(`/projects/${activeProjectId}/scenes`),
          },
        ]
      : []),
  ];

  return (
    <div className="relative min-h-screen bg-canvas/75 text-obsidian-primary flex flex-col selection:bg-amber-500/20 selection:text-amber-400">
      <div className="fixed inset-0 pointer-events-none -z-10 backdrop-blur-[2px]" />
      {/* =========================================================================
       * Global Showrunner Header (Sticky, 1440px desktop & 390px mobile responsive)
       * ========================================================================= */}
      <header className="sticky top-0 z-50 w-full bg-panel/90 backdrop-blur-md border-b border-border">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
          {/* Left: Brand & Active Project Badge */}
          <div className="flex items-center gap-4 min-w-0">
            <Link
              href="/dashboard"
              className="flex items-center gap-2.5 text-obsidian-primary hover:text-amber-400 transition-colors shrink-0 group"
            >
              <div className="w-9 h-9 rounded-lg bg-canvas border border-border group-hover:border-amber-500/50 flex items-center justify-center text-amber-500 transition-colors shadow-inner">
                <Clapperboard className="w-5 h-5" />
              </div>
              <div className="hidden sm:block">
                <span className="font-cinzel font-bold tracking-wider text-base uppercase block leading-none">
                  MovieAI
                </span>
                <span className="font-mono text-[9px] uppercase tracking-widest text-amber-500 font-semibold leading-none">
                  Producer
                </span>
              </div>
            </Link>

            {/* Breadcrumb / Active Project Context */}
            {activeProjectTitle && (
              <div className="hidden md:flex items-center gap-2 pl-4 border-l border-border/80 min-w-0">
                <span className="text-obsidian-muted text-xs font-mono">/</span>
                <div className="min-w-0">
                  <div className="text-xs font-semibold text-obsidian-primary truncate flex items-center gap-1.5">
                    <span className="truncate">{activeProjectTitle}</span>
                    {currentStage && (
                      <span className="shrink-0 px-1.5 py-0.5 rounded text-[10px] font-mono bg-amber-500/10 text-amber-400 border border-amber-500/30">
                        Stage {currentStage}/16
                      </span>
                    )}
                  </div>
                  {stageName && (
                    <div className="text-[10px] font-mono text-obsidian-muted truncate">
                      {stageName}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Center: Desktop Navigation Bar */}
          <nav className="hidden lg:flex items-center gap-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-2 px-3.5 py-2 rounded-md text-xs font-medium transition-all",
                    item.active
                      ? "bg-elevated text-amber-400 border border-amber-500/30 shadow-sm"
                      : "text-obsidian-secondary hover:text-obsidian-primary hover:bg-canvas border border-transparent"
                  )}
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  <span>{item.name}</span>
                </Link>
              );
            })}
          </nav>

          {/* Right: Studio Engine Status & User Profile */}
          <div className="flex items-center gap-2 sm:gap-3 shrink-0">
            {/* Polya AI Live Status Indicator (Universal Responsive) */}
            <div className="flex items-center gap-1.5 sm:gap-2 px-2 sm:px-2.5 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-[10px] sm:text-[11px] font-mono text-emerald-400 font-semibold shrink-0 shadow-sm">
              <span className="relative flex h-2 w-2 shrink-0">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
              </span>
              <span className="tracking-wide">Polya AI</span>
            </div>

            {/* User Profile & Menu */}
            {user ? (
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setUserDropdownOpen(!userDropdownOpen)}
                  className="flex items-center gap-2 p-1.5 sm:px-3 sm:py-1.5 rounded-lg bg-canvas hover:bg-elevated border border-border transition-colors text-xs"
                >
                  {user.avatar_url ? (
                    /* eslint-disable-next-line @next/next/no-img-element */
                    <img
                      src={user.avatar_url}
                      alt={user.full_name || "Showrunner"}
                      className="w-6 h-6 rounded-full border border-amber-500/40 object-cover"
                    />
                  ) : (
                    <div className="w-6 h-6 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30 flex items-center justify-center font-mono text-[10px] font-bold">
                      {(user.full_name || user.email)[0].toUpperCase()}
                    </div>
                  )}
                  <div className="hidden sm:block text-left leading-tight">
                    <span className="font-medium text-obsidian-primary block truncate max-w-[120px]">
                      {user.full_name || user.email.split("@")[0]}
                    </span>
                    <span className="text-[9px] font-mono uppercase text-amber-500 font-semibold">
                      {user.role || "SHOWRUNNER"}
                    </span>
                  </div>
                  <ChevronDown className="w-3.5 h-3.5 text-obsidian-muted" />
                </button>

                {/* Dropdown Popover */}
                {userDropdownOpen && (
                  <>
                    <div
                      className="fixed inset-0 z-40"
                      onClick={() => setUserDropdownOpen(false)}
                    />
                    <div className="absolute right-0 mt-2 w-56 rounded-lg bg-panel border border-border shadow-studio p-2 z-50 text-xs font-sans animate-in fade-in zoom-in-95 duration-150">
                      <div className="px-3 py-2 border-b border-border/70 mb-1">
                        <p className="font-semibold text-obsidian-primary truncate">
                          {user.full_name || "Showrunner"}
                        </p>
                        <p className="text-[11px] font-mono text-obsidian-muted truncate">
                          {user.email}
                        </p>
                      </div>

                      <div className="px-3 py-1.5 text-[10px] font-mono text-obsidian-muted uppercase">
                        Role: <span className="text-amber-400 font-bold">{user.role}</span>
                      </div>

                      <Link
                        href="/settings"
                        onClick={() => setUserDropdownOpen(false)}
                        className="w-full flex items-center gap-2 px-3 py-2 rounded text-obsidian-secondary hover:text-obsidian-primary hover:bg-elevated transition-colors text-left font-medium text-xs border-t border-border/40 mt-1"
                      >
                        <Settings className="w-3.5 h-3.5 text-amber-500" />
                        <span>Settings & Flow Pool</span>
                      </Link>

                      <button
                        type="button"
                        onClick={async () => {
                          setUserDropdownOpen(false);
                          await logout();
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2 rounded text-rose-400 hover:bg-rose-500/10 transition-colors text-left font-medium mt-1"
                      >
                        <LogOut className="w-4 h-4" />
                        <span>Sign Out of Studio</span>
                      </button>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <Link
                href="/login"
                className="px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-canvas font-medium text-xs transition-colors"
              >
                Sign In
              </Link>
            )}

            {/* Navigation Hamburger Toggle (Responsive across Mobile & Desktop) */}
            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-lg bg-canvas hover:bg-elevated border border-border text-obsidian-secondary hover:text-amber-400 transition-colors flex items-center justify-center shrink-0 cursor-pointer"
              aria-label="Toggle Navigation Menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5 text-amber-400" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* =========================================================================
         * Navigation Drawer & "My Projects" Hierarchical Tree
         * ========================================================================= */}
        {mobileMenuOpen && (
          <>
            <div
              className="fixed inset-0 z-40 bg-canvas/60 backdrop-blur-xs"
              onClick={() => setMobileMenuOpen(false)}
            />
            <div className="absolute top-16 right-0 w-full sm:w-96 border-b sm:border-l sm:rounded-bl-xl border-border bg-panel/95 backdrop-blur-md px-4 py-4 space-y-3 z-50 shadow-studio animate-in slide-in-from-top-2 duration-200">
              <div className="flex items-center justify-between pb-2 border-b border-border/70">
                <span className="text-[11px] font-mono uppercase tracking-wider text-obsidian-muted font-semibold flex items-center gap-1.5">
                  <Film className="w-3.5 h-3.5 text-amber-500" />
                  <span>Showrunner Console</span>
                </span>
                <button
                  type="button"
                  onClick={() => setMobileMenuOpen(false)}
                  className="p-1 rounded text-obsidian-muted hover:text-obsidian-primary transition-colors cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {activeProjectTitle && (
                <div className="p-3 rounded-lg bg-canvas border border-border/80">
                  <div className="text-[10px] font-mono text-obsidian-muted uppercase">
                    Active Production
                  </div>
                  <div className="text-sm font-semibold text-amber-400 truncate">
                    {activeProjectTitle}
                  </div>
                  {stageName && (
                    <div className="text-xs text-obsidian-secondary font-mono mt-0.5">
                      Stage {currentStage || 1}: {stageName}
                    </div>
                  )}
                </div>
              )}

              {/* Standard Nav Items */}
              <div className="space-y-1">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setMobileMenuOpen(false)}
                      className={cn(
                        "flex items-center gap-3 px-3 py-2 rounded-md text-xs sm:text-sm font-medium transition-all",
                        item.active
                          ? "bg-elevated text-amber-400 border border-amber-500/40 shadow-sm"
                          : "text-obsidian-secondary hover:text-obsidian-primary hover:bg-canvas"
                      )}
                    >
                      <Icon className="w-4 h-4 shrink-0" />
                      <span>{item.name}</span>
                    </Link>
                  );
                })}
              </div>

              {/* "My Projects" Hierarchical Tree (Collapsible Accordion) */}
              <div className="pt-2 border-t border-border/70">
                <button
                  type="button"
                  onClick={() => setIsMyProjectsExpanded(!isMyProjectsExpanded)}
                  className="w-full flex items-center justify-between px-3 py-2 rounded-md bg-canvas/80 hover:bg-elevated border border-border transition-colors text-xs font-semibold text-obsidian-primary group cursor-pointer"
                >
                  <div className="flex items-center gap-2">
                    <Film className="w-4 h-4 text-amber-500" />
                    <span>My Projects</span>
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-amber-500/10 text-amber-400 border border-amber-500/30">
                      {userProjects.length}
                    </span>
                  </div>
                  {isMyProjectsExpanded ? (
                    <ChevronDown className="w-4 h-4 text-obsidian-muted group-hover:text-amber-400 transition-colors" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-obsidian-muted group-hover:text-amber-400 transition-colors" />
                  )}
                </button>

                {isMyProjectsExpanded && (
                  <div className="mt-1.5 max-h-72 overflow-y-auto space-y-1 pl-1 pr-1.5 py-1">
                    {projectsLoading ? (
                      <div className="space-y-1.5 py-2">
                        {[1, 2, 3].map((i) => (
                          <div
                            key={i}
                            className="h-8 rounded bg-canvas border border-border/50 animate-pulse"
                          />
                        ))}
                      </div>
                    ) : userProjects.length === 0 ? (
                      <div className="py-4 text-center text-xs text-obsidian-muted font-mono rounded bg-canvas/40 border border-border/40 border-dashed">
                        No productions commissioned yet.
                      </div>
                    ) : (
                      userProjects.map((p, idx) => {
                        const isCurrent =
                          activeProjectId === p.id || activeProjectId === p.slug;
                        return (
                          <Link
                            key={p.id}
                            href={`/projects/${p.id}/studio`}
                            onClick={() => setMobileMenuOpen(false)}
                            className={cn(
                              "flex items-center justify-between gap-2 px-2.5 py-2 rounded-md text-xs transition-all group/item",
                              isCurrent
                                ? "bg-amber-500/15 border border-amber-500/50 text-amber-300 font-semibold shadow-sm"
                                : "hover:bg-canvas border border-transparent text-obsidian-secondary hover:text-obsidian-primary"
                            )}
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="text-[10px] font-mono text-obsidian-muted shrink-0 w-4 text-right">
                                {idx + 1}.
                              </span>
                              <span className="truncate group-hover/item:text-amber-400 transition-colors">
                                {p.title}
                              </span>
                            </div>
                            <div className="flex items-center gap-1.5 shrink-0">
                              <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-canvas border border-border/60 text-obsidian-muted">
                                {p.aspect_ratio}
                              </span>
                              <span
                                className={cn(
                                  "px-1.5 py-0.5 rounded text-[10px] font-mono border",
                                  getStageBadgeStyle(p.operational_stage)
                                )}
                              >
                                S{p.operational_stage}
                              </span>
                            </div>
                          </Link>
                        );
                      })
                    )}
                  </div>
                )}
              </div>

              {user && (
                <div className="pt-2 border-t border-border mt-2">
                  <button
                    type="button"
                    onClick={async () => {
                      setMobileMenuOpen(false);
                      await logout();
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-rose-400 hover:bg-rose-500/10 rounded text-xs sm:text-sm font-medium transition-colors cursor-pointer"
                  >
                    <LogOut className="w-4 h-4" />
                    <span>Sign Out ({user.email})</span>
                  </button>
                </div>
              )}
            </div>
          </>
        )}
      </header>

      {/* =========================================================================
       * Main Content Area (Max 1440px desktop container, fluid responsive)
       * ========================================================================= */}
      <main className="flex-1 max-w-[1440px] w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {children}
      </main>

      {/* =========================================================================
       * Global Studio Footer (Observability & Architecture Status)
       * ========================================================================= */}
      <footer className="border-t border-border bg-panel/60 py-3 text-center text-xs font-mono text-obsidian-muted">
        <div className="max-w-[1440px] mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
            <span>DaVinci Obsidian Engine // NLE Studio v2.4</span>
          </div>
          <div className="text-[11px] text-obsidian-muted/70">
            16-Stage Gates &bull; 50-Scene Hollywood Arc &bull; 4-Act Storyboard
          </div>
        </div>
      </footer>
    </div>
  );
}
