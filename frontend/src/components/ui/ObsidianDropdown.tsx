"use client";

import React, { useState, useRef, useEffect } from "react";
import { ChevronUp, Check } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ObsidianDropdownOption {
  value: string;
  title: string;
  description?: string;
  badge?: string;
  icon?: React.ReactNode;
}

export interface ObsidianDropdownProps {
  label?: string;
  subtitle?: string;
  placeholder?: string;
  icon?: React.ReactNode;
  options: ObsidianDropdownOption[];
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  className?: string;
  size?: "default" | "sm";
}

export default function ObsidianDropdown({
  label,
  subtitle,
  placeholder = "Select an option...",
  icon,
  options,
  value,
  onChange,
  disabled = false,
  className,
  size = "default",
}: ObsidianDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedOption = options.find((opt) => String(opt.value) === String(value));

  // Close on outside click or escape key
  useEffect(() => {
    function handleClickOutside(event: MouseEvent | TouchEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("touchstart", handleClickOutside);
      document.addEventListener("keydown", handleKeyDown);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("touchstart", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  const isCompact = size === "sm";

  return (
    <div
      ref={containerRef}
      className={cn(
        "relative w-full border border-slate-800 bg-slate-950/90 text-obsidian-primary transition-all duration-500 ease-[cubic-bezier(0.4,0,0.2,1)] shadow-studio backdrop-blur-md",
        isOpen
          ? "rounded-3xl border-slate-700 shadow-glow ring-1 ring-amber-500/20"
          : isCompact
          ? "rounded-xl"
          : "rounded-2xl",
        disabled && "opacity-50 pointer-events-none cursor-not-allowed",
        className
      )}
    >
      {/* Header / Trigger */}
      <button
        type="button"
        disabled={disabled}
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
        className={cn(
          "w-full flex items-center justify-between text-left select-none transition-colors",
          isCompact ? "p-2.5" : "p-3 sm:p-3.5"
        )}
      >
        <div className="flex items-center gap-2.5 sm:gap-3 min-w-0 flex-1">
          {/* Icon Box */}
          {(selectedOption?.icon || icon) ? (
            <div
              className={cn(
                "shrink-0 rounded-xl flex items-center justify-center border transition-all duration-300",
                isCompact ? "h-8 w-8 text-xs rounded-lg" : "h-10 w-10 text-sm",
                isOpen
                  ? "bg-amber-500/20 border-amber-500/40 text-amber-400"
                  : "bg-neutral-900 border-slate-800 text-obsidian-muted"
              )}
            >
              {selectedOption?.icon || icon}
            </div>
          ) : null}

          {/* Title & Subtitle */}
          <div className="min-w-0 flex-1">
            {label && (
              <span className="block text-[10px] font-mono uppercase tracking-wider text-obsidian-muted mb-0.5 truncate">
                {label}
              </span>
            )}

            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "font-semibold truncate",
                  isCompact ? "text-xs font-mono" : "text-xs sm:text-sm text-obsidian-primary",
                  !selectedOption && "text-obsidian-muted font-normal"
                )}
              >
                {selectedOption ? selectedOption.title : placeholder}
              </span>

              {selectedOption?.badge && (
                <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/30 shrink-0">
                  {selectedOption.badge}
                </span>
              )}
            </div>

            {/* Collapsible Subtitle - Smoothly shrinks to height 0 and fades out when opened */}
            <div
              className={cn(
                "overflow-hidden transition-all duration-500 ease-[cubic-bezier(0.4,0,0.2,1)]",
                isOpen
                  ? "max-h-0 opacity-0 mt-0"
                  : "max-h-8 opacity-100 mt-0.5"
              )}
            >
              <p className="text-[10px] sm:text-[11px] text-obsidian-muted truncate">
                {selectedOption?.description || subtitle || placeholder || ""}
              </p>
            </div>
          </div>
        </div>

        {/* Right Arrow / Chevron */}
        <div className="shrink-0 pl-2">
          <ChevronUp
            className={cn(
              "w-4 h-4 sm:w-5 sm:h-5 text-obsidian-muted transition-transform duration-500 ease-[cubic-bezier(0.4,0,0.2,1)]",
              isOpen ? "rotate-0 text-amber-400" : "rotate-180"
            )}
          />
        </div>
      </button>

      {/* Expandable Options List (grid-rows animation) */}
      <div
        className={cn(
          "grid transition-all duration-500 ease-[cubic-bezier(0.4,0,0.2,1)]",
          isOpen
            ? "grid-rows-[1fr] opacity-100 border-t border-slate-800/80"
            : "grid-rows-[0fr] opacity-0 pointer-events-none"
        )}
      >
        <div className="overflow-hidden">
          <div className="max-h-72 overflow-y-auto overscroll-contain p-2 space-y-1">
            {options.map((option, index) => {
              const isSelected = String(option.value) === String(value);
              // Staggered delay, capped at 300ms so item 15+ appears briskly
              const delay = Math.min(index * 18, 300);

              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => {
                    onChange(option.value);
                    setIsOpen(false);
                  }}
                  style={{
                    transitionDelay: isOpen ? `${delay}ms` : "0ms",
                  }}
                  className={cn(
                    "w-full flex items-start gap-2.5 sm:gap-3 rounded-xl p-2 sm:p-2.5 text-left transition-all duration-300 ease-[cubic-bezier(0.4,0,0.2,1)] group",
                    isOpen
                      ? "opacity-100 translate-y-0"
                      : "opacity-0 translate-y-2",
                    isSelected
                      ? "bg-amber-500/20 border border-amber-500/40 text-amber-400 shadow-sm"
                      : "hover:bg-neutral-800/60 border border-transparent text-slate-300 hover:text-white"
                  )}
                >
                  {/* Option Icon */}
                  {option.icon ? (
                    <div
                      className={cn(
                        "h-7 w-7 rounded-lg shrink-0 flex items-center justify-center text-xs mt-0.5 transition-colors",
                        isSelected
                          ? "bg-amber-500/30 text-amber-300 border border-amber-500/40"
                          : "bg-panel text-obsidian-muted group-hover:text-obsidian-primary border border-slate-800"
                      )}
                    >
                      {option.icon}
                    </div>
                  ) : null}

                  {/* Option Text */}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span
                        className={cn(
                          "text-xs font-semibold truncate",
                          isSelected
                            ? "text-amber-400 font-bold"
                            : "text-obsidian-primary group-hover:text-white"
                        )}
                      >
                        {option.title}
                      </span>

                      {option.badge && (
                        <span
                          className={cn(
                            "text-[9px] font-mono px-1.5 py-0.2 rounded shrink-0",
                            isSelected
                              ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                              : "bg-canvas text-obsidian-muted border border-border"
                          )}
                        >
                          {option.badge}
                        </span>
                      )}
                    </div>

                    {option.description && (
                      <p
                        className={cn(
                          "text-[10px] mt-0.5 line-clamp-2 leading-relaxed font-sans",
                          isSelected
                            ? "text-amber-300/80"
                            : "text-obsidian-muted group-hover:text-slate-300"
                        )}
                      >
                        {option.description}
                      </p>
                    )}
                  </div>

                  {/* Selected Indicator Checkmark */}
                  {isSelected && (
                    <div className="w-4 h-4 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/50 flex items-center justify-center shrink-0 mt-0.5">
                      <Check className="w-2.5 h-2.5 stroke-[2.5]" />
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
