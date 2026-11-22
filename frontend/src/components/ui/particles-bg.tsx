"use client";

import { useEffect, useCallback } from "react";

export default function ParticlesComponent() {
  const initParticles = useCallback((isDark: boolean) => {
    if (typeof window === "undefined") return;

    const win = window as any;

    // cleanup old canvas
    const oldCanvas = document.querySelector("#particles-js canvas");
    if (oldCanvas) oldCanvas.remove();

    if (Array.isArray(win.pJSDom) && win.pJSDom.length > 0) {
      win.pJSDom.forEach((p: any) => {
        try {
          p?.pJS?.fn?.vendors?.destroypJS?.();
        } catch {
          // ignore cleanup errors
        }
      });
      win.pJSDom = [];
    }

    const colors = isDark
      ? {
          particles: "#00f5ff",
          lines: "#00d9ff",
          accent: "#0096c7",
        }
      : {
          particles: "#0277bd",
          lines: "#0288d1",
          accent: "#039be5",
        };

    if (typeof win.particlesJS === "function") {
      win.particlesJS("particles-js", {
        particles: {
          number: { value: 140, density: { enable: true, value_area: 800 } },
          color: { value: colors.particles },
          shape: { type: "circle", stroke: { width: 0.5, color: colors.accent } },
          opacity: {
            value: 0.7,
            random: true,
            anim: { enable: true, speed: 1, opacity_min: 0.3 },
          },
          size: {
            value: 3,
            random: true,
            anim: { enable: true, speed: 2, size_min: 1 },
          },
          line_linked: {
            enable: true,
            distance: 160,
            color: colors.lines,
            opacity: 0.4,
            width: 1.2,
          },
          move: { enable: true, speed: 2, random: true, out_mode: "bounce" },
        },
        interactivity: {
          detect_on: "canvas",
          events: {
            onhover: { enable: true, mode: "grab" },
            onclick: { enable: true, mode: "push" },
            resize: true,
          },
          modes: {
            grab: { distance: 220, line_linked: { opacity: 0.8 } },
            push: { particles_nb: 4 },
            repulse: { distance: 180, duration: 0.4 },
          },
        },
        retina_detect: true,
      });
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;

    let observer: MutationObserver | null = null;
    let script: HTMLScriptElement | null = null;

    const win = window as any;
    const html = document.documentElement;
    const detectDark = () => {
      // Defaults cleanly to true (DaVinci Obsidian dark theme) unless explicitly toggled light
      const isExplicitLight =
        html.classList.contains("light") ||
        html.getAttribute("data-theme") === "light";
      return !isExplicitLight;
    };

    const setupObserver = () => {
      initParticles(detectDark());

      // observe changes from 21st.dev theme button or manual theme toggle
      observer = new MutationObserver(() => initParticles(detectDark()));
      observer.observe(html, {
        attributes: true,
        attributeFilter: ["class", "data-theme"],
      });
    };

    // Forward mouse events from window to particles so background reacts to hover & click
    // without blocking foreground UI (modals, drawers, buttons)
    const handleMouseMove = (e: MouseEvent) => {
      const pJS = win.pJSDom?.[0]?.pJS;
      if (pJS && pJS.interactivity) {
        const pxRatio = pJS.tmp?.retina ? (pJS.canvas?.pxratio || 1) : 1;
        pJS.interactivity.mouse.pos_x = e.clientX * pxRatio;
        pJS.interactivity.mouse.pos_y = e.clientY * pxRatio;
        pJS.interactivity.status = "mousemove";
      }
    };

    const handleMouseLeave = () => {
      const pJS = win.pJSDom?.[0]?.pJS;
      if (pJS && pJS.interactivity) {
        pJS.interactivity.mouse.pos_x = null;
        pJS.interactivity.mouse.pos_y = null;
        pJS.interactivity.status = "mouseleave";
      }
    };

    const handleClick = () => {
      const pJS = win.pJSDom?.[0]?.pJS;
      if (pJS && pJS.interactivity?.events?.onclick?.enable) {
        pJS.interactivity.mouse.click_pos_x = pJS.interactivity.mouse.pos_x;
        pJS.interactivity.mouse.click_pos_y = pJS.interactivity.mouse.pos_y;
        pJS.interactivity.mouse.click_time = new Date().getTime();
        if (pJS.interactivity.events.onclick.mode === "push" && pJS.fn?.modes?.pushParticles) {
          pJS.fn.modes.pushParticles(
            pJS.interactivity.modes.push.particles_nb,
            pJS.interactivity.mouse
          );
        }
      }
    };

    window.addEventListener("mousemove", handleMouseMove, { passive: true });
    window.addEventListener("mouseleave", handleMouseLeave, { passive: true });
    window.addEventListener("click", handleClick, { passive: true });

    if (typeof win.particlesJS === "function") {
      setupObserver();
    } else {
      script = document.createElement("script");
      script.src = "https://cdn.jsdelivr.net/particles.js/2.0.0/particles.min.js";
      script.async = true;
      script.onload = () => {
        setupObserver();
      };
      document.body.appendChild(script);
    }

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseleave", handleMouseLeave);
      window.removeEventListener("click", handleClick);

      if (observer) {
        observer.disconnect();
      }
      if (script && document.body.contains(script)) {
        document.body.removeChild(script);
      }

      // cleanup canvas & particles instance on unmount
      const oldCanvas = document.querySelector("#particles-js canvas");
      if (oldCanvas) oldCanvas.remove();

      if (Array.isArray(win.pJSDom) && win.pJSDom.length > 0) {
        win.pJSDom.forEach((p: any) => {
          try {
            p?.pJS?.fn?.vendors?.destroypJS?.();
          } catch {
            // ignore cleanup errors
          }
        });
        win.pJSDom = [];
      }
    };
  }, [initParticles]);

  return (
    <div
      id="particles-js"
      className="w-full h-screen fixed inset-0 -z-10 pointer-events-auto transition-colors duration-500 bg-gradient-to-tr from-[#e3f2fd] via-[#90caf9] to-[#64b5f6] dark:from-[#000814] dark:via-[#003566] dark:to-[#0077b6]"
    />
  );
}
