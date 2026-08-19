import type { Config } from "tailwindcss";

/**
 * HSAAI Enterprise Design System — Tailwind Config v2.0
 * ═══════════════════════════════════════════════════════════════════════
 *
 * All tokens reference CSS custom properties defined in globals.css.
 * This ensures a SINGLE SOURCE OF TRUTH and enables runtime theme switching.
 *
 * Colors are extracted from the official HSA logo:
 *   Primary Gold:  #F4C430
 *   Primary Black: #111111
 *
 * ═══════════════════════════════════════════════════════════════════════
 */
const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
    "./modules/**/*.{ts,tsx}",
    "./services/**/*.{ts,tsx}",
    "./store/**/*.{ts,tsx}",
    "./providers/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      // ─── Colors (CSS variable references) ─────────────────────────────
      colors: {
        // Primary brand
        primary: {
          gold: "var(--color-primary-gold)",
          "gold-hover": "var(--color-primary-gold-hover)",
          "gold-active": "var(--color-primary-gold-active)",
          "gold-soft": "var(--color-primary-gold-soft)",
          "gold-border": "var(--color-primary-gold-border)",
          black: "var(--color-primary-black)",
          "black-hover": "var(--color-primary-black-hover)",
          "black-soft": "var(--color-primary-black-soft)",
        },
        // Semantic
        success: {
          DEFAULT: "var(--color-success)",
          soft: "var(--color-success-soft)",
          border: "var(--color-success-border)",
        },
        warning: {
          DEFAULT: "var(--color-warning)",
          soft: "var(--color-warning-soft)",
          border: "var(--color-warning-border)",
        },
        danger: {
          DEFAULT: "var(--color-danger)",
          soft: "var(--color-danger-soft)",
          border: "var(--color-danger-border)",
        },
        info: {
          DEFAULT: "var(--color-info)",
          soft: "var(--color-info-soft)",
          border: "var(--color-info-border)",
        },
        // Neutral scale (warm-tinted stone palette)
        neutral: {
          0: "var(--color-neutral-0)",
          50: "var(--color-neutral-50)",
          100: "var(--color-neutral-100)",
          200: "var(--color-neutral-200)",
          300: "var(--color-neutral-300)",
          400: "var(--color-neutral-400)",
          500: "var(--color-neutral-500)",
          600: "var(--color-neutral-600)",
          700: "var(--color-neutral-700)",
          800: "var(--color-neutral-800)",
          900: "var(--color-neutral-900)",
          950: "var(--color-neutral-950)",
        },
        // Semantic surface tokens (auto-switch with dark mode)
        bg: "var(--color-bg)",
        surface: {
          DEFAULT: "var(--color-surface)",
          alt: "var(--color-surface-alt)",
        },
        border: {
          DEFAULT: "var(--color-border)",
          strong: "var(--color-border-strong)",
        },
        // Text tokens
        text: {
          primary: "var(--color-text-primary)",
          secondary: "var(--color-text-secondary)",
          muted: "var(--color-text-muted)",
          disabled: "var(--color-text-disabled)",
          inverse: "var(--color-text-inverse)",
        },
        // Focus
        focus: "var(--color-focus)",

        // Legacy aliases (for backward compatibility during migration)
        "hsa-yellow": "var(--color-primary-gold)",
        "hsa-black": "var(--color-primary-black)",
        "hsa-gold": "var(--color-primary-gold-active)",
        "hsa-soft": "var(--color-primary-gold-soft)",
        "enterprise-slate": "var(--color-neutral-950)",
      },

      // ─── Font Family ───────────────────────────────────────────────────
      fontFamily: {
        sans: "var(--font-sans)",
        serif: "var(--font-serif)",
        mono: "var(--font-mono)",
        display: "var(--font-display)",
      },

      // ─── Font Size Scale (AAA-compliant) ──────────────────────────────
      fontSize: {
        "display-lg": ["4.5rem", { lineHeight: "1.1", letterSpacing: "-0.02em" }],
        "display": ["3.5rem", { lineHeight: "1.15", letterSpacing: "-0.02em" }],
        "display-sm": ["3rem", { lineHeight: "1.2", letterSpacing: "-0.01em" }],
        "h1": ["2.5rem", { lineHeight: "1.2", letterSpacing: "-0.01em" }],
        "h2": ["2rem", { lineHeight: "1.25", letterSpacing: "-0.01em" }],
        "h3": ["1.5rem", { lineHeight: "1.3", letterSpacing: "0" }],
        "h4": ["1.25rem", { lineHeight: "1.4", letterSpacing: "0" }],
        "body-lg": ["1.125rem", { lineHeight: "1.625" }],
        "body": ["1rem", { lineHeight: "1.5" }],
        "body-sm": ["0.875rem", { lineHeight: "1.5" }],
        "caption": ["0.75rem", { lineHeight: "1.4" }],
        "label": ["0.6875rem", { lineHeight: "1.4" }],
        "code": ["0.8125rem", { lineHeight: "1.5" }],
        "button": ["0.875rem", { lineHeight: "1.4" }],
        "overline": ["0.6875rem", { lineHeight: "1.4", letterSpacing: "0.08em" }],
      },

      // ─── Font Weight ──────────────────────────────────────────────────
      fontWeight: {
        regular: "400",
        medium: "500",
        semibold: "600",
        bold: "700",
        black: "800",
      },

      // ─── Spacing (8px grid) ───────────────────────────────────────────
      spacing: {
        "1": "var(--space-1)",
        "2": "var(--space-2)",
        "3": "var(--space-3)",
        "4": "var(--space-4)",
        "5": "var(--space-5)",
        "6": "var(--space-6)",
        "8": "var(--space-8)",
        "10": "var(--space-10)",
        "12": "var(--space-12)",
        "16": "var(--space-16)",
        "20": "var(--space-20)",
        "24": "var(--space-24)",
      },

      // ─── Border Radius ────────────────────────────────────────────────
      borderRadius: {
        "none": "0",
        "sm": "var(--radius-sm)",
        "md": "var(--radius-md)",
        "lg": "var(--radius-lg)",
        "xl": "var(--radius-xl)",
        "2xl": "var(--radius-2xl)",
        "3xl": "var(--radius-3xl)",
        "4xl": "var(--radius-4xl)",
        "full": "var(--radius-full)",
      },

      // ─── Box Shadow (elevation scale) ─────────────────────────────────
      boxShadow: {
        "xs": "var(--shadow-xs)",
        "sm": "var(--shadow-sm)",
        "md": "var(--shadow-md)",
        "lg": "var(--shadow-lg)",
        "xl": "var(--shadow-xl)",
        "2xl": "var(--shadow-2xl)",
        "inner": "var(--shadow-inner)",
        "glow": "var(--shadow-glow)",
        "glow-lg": "var(--shadow-glow-lg)",
      },

      // ─── Z-Index Scale ────────────────────────────────────────────────
      zIndex: {
        "base": "var(--z-base)",
        "dropdown": "var(--z-dropdown)",
        "sticky": "var(--z-sticky)",
        "fixed": "var(--z-fixed)",
        "overlay": "var(--z-overlay)",
        "drawer": "var(--z-drawer)",
        "modal": "var(--z-modal)",
        "popover": "var(--z-popover)",
        "toast": "var(--z-toast)",
        "tooltip": "var(--z-tooltip)",
        "max": "var(--z-max)",
      },

      // ─── Transitions ──────────────────────────────────────────────────
      transitionDuration: {
        "instant": "var(--duration-instant)",
        "fast": "var(--duration-fast)",
        "normal": "var(--duration-normal)",
        "slow": "var(--duration-slow)",
        "slower": "var(--duration-slower)",
      },
      transitionTimingFunction: {
        "linear": "var(--ease-linear)",
        "in": "var(--ease-in)",
        "out": "var(--ease-out)",
        "in-out": "var(--ease-in-out)",
        "spring": "var(--ease-spring)",
        "gentle": "var(--ease-gentle)",
      },

      // ─── Layout ───────────────────────────────────────────────────────
      maxWidth: {
        "content": "var(--content-max-width)",
      },
      width: {
        "sidebar": "var(--sidebar-width)",
        "sidebar-collapsed": "var(--sidebar-collapsed-width)",
      },
      height: {
        "topbar": "var(--topbar-height)",
        "mobile-nav": "var(--mobile-nav-height)",
      },

      // ─── Animations ───────────────────────────────────────────────────
      animation: {
        "fade-in": "ds-fade-in var(--duration-normal) var(--ease-out)",
        "fade-in-up": "ds-fade-in-up var(--duration-normal) var(--ease-out)",
        "scale-in": "ds-scale-in var(--duration-fast) var(--ease-spring)",
        "slide-in-right": "ds-slide-in-right var(--duration-normal) var(--ease-out)",
        "shimmer": "ds-shimmer 1.5s infinite",
      },

      // ─── Keyframes ────────────────────────────────────────────────────
      keyframes: {
        "ds-fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "ds-fade-in-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "ds-scale-in": {
          from: { opacity: "0", transform: "scale(0.95)" },
          to: { opacity: "1", transform: "scale(1)" },
        },
        "ds-slide-in-right": {
          from: { transform: "translateX(100%)" },
          to: { transform: "translateX(0)" },
        },
        "ds-shimmer": {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
