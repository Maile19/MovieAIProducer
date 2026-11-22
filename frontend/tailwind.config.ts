import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/lib/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/hooks/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: "#090B0E",
        panel: "#12161D",
        elevated: "#1A1F28",
        border: "#262C36",
        crisp: "#262C36",
        amber: {
          DEFAULT: "#F59E0B",
          cinema: "#F59E0B",
          400: "#FBBF24",
          500: "#F59E0B",
          600: "#D97706",
        },
        emerald: {
          DEFAULT: "#10B981",
          400: "#34D399",
          500: "#10B981",
          600: "#059669",
        },
        rose: {
          DEFAULT: "#F43F5E",
          400: "#FB7185",
          500: "#F43F5E",
          600: "#E11D48",
        },
        blue: {
          DEFAULT: "#3B82F6",
          400: "#60A5FA",
          500: "#3B82F6",
          600: "#2563EB",
        },
        violet: {
          DEFAULT: "#8B5CF6",
          400: "#A78BFA",
          500: "#8B5CF6",
          600: "#7C3AED",
        },
        obsidian: {
          canvas: "#090B0E",
          panel: "#12161D",
          elevated: "#1A1F28",
          border: "#262C36",
          muted: "#64748B",
          secondary: "#94A3B8",
          primary: "#F8FAFC",
        },
      },
      fontFamily: {
        cinzel: ["var(--font-cinzel)", "Cinzel", "serif"],
        sans: ["var(--font-inter)", "Inter", "sans-serif"],
        mono: ["var(--font-mono)", "JetBrains Mono", "monospace"],
      },
      boxShadow: {
        studio: "0 4px 20px -2px rgba(0, 0, 0, 0.7)",
        glow: "0 0 15px -3px rgba(245, 158, 11, 0.3)",
      },
    },
  },
  plugins: [],
};
export default config;
