import type { Config } from "tailwindcss";

/**
 * HSAAI Design Tokens — Single Source of Truth
 * =============================================
 * Derived EXCLUSIVELY from the official design reference (index.html):
 *   Primary Gold   #EFB323   (main accent, active states, CTAs)
 *   Dark Gold      #A67C00   (hover, large numerals, accent text on white)
 *   Soft Gold      #FDF4E3   (badge/chip/active-item backgrounds)
 *   Main Black     #111111   (headings, primary text)
 *   Dark Black     #151515   (dark surfaces — footer, dark-mode panels)
 *   Main BG        #FAFAFA   (app background)
 *   White          #FFFFFF   (cards, panels)
 *   Border         #E7E5E4   (all hairline borders)
 *   Secondary Text #64748B   (descriptions, hints, captions)
 *
 * Legacy token names (hsa-yellow, hsa-soft, hsa-gold, hsa-black) are kept as
 * aliases so every existing usage across the codebase instantly adopts the
 * official palette without breaking.
 */
const config: Config = {
  darkMode: "class",
  // FIX FIX-MEDIUM-QUALITY: include every dir that uses Tailwind classes so
  // production builds don't purge classes used only in lib/modules/services/store/providers.
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
      /* ============================================================
       * TYPOGRAPHY v2 — IBM Plex superfamily (single source: globals.css)
       *   --font-sans-ar / --font-sans-en : IBM Plex Sans Arabic
       *     (its Latin glyphs ARE IBM Plex Sans → AR + EN share one
       *      family, one baseline, identical visual weight)
       *   --font-mono : IBM Plex Mono (code, API endpoints, IDs, tokens)
       * Only weights 400/500/600/700 are used. The `black`/`extrabold`
       * aliases below are deprecated safety nets: IBM Plex Sans Arabic
       * has no real weight above 700, so legacy `font-black` renders as
       * true Bold instead of ugly synthetic faux-bold.
       * ============================================================ */
      fontFamily: {
        sans: ["var(--font-sans-ar)", "IBM Plex Sans Arabic", "IBM Plex Sans", "Segoe UI", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "IBM Plex Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      fontSize: {
        /* Fluid display + heading tokens (clamp → covers desktop/tablet/mobile) */
        display: ["var(--fs-display)", { lineHeight: "var(--lh-display)" }],
        h1: ["var(--fs-h1)", { lineHeight: "var(--lh-h1)" }],
        h2: ["var(--fs-h2)", { lineHeight: "var(--lh-h2)" }],
        h3: ["var(--fs-h3)", { lineHeight: "var(--lh-h3)" }],
        h4: ["var(--fs-h4)", { lineHeight: "var(--lh-h4)" }],
        /* Body + UI tokens — line-heights tuned for Arabic legibility */
        "body-lg": ["var(--fs-body-lg)", { lineHeight: "var(--lh-body-lg)" }],
        base: ["var(--fs-body)", { lineHeight: "var(--lh-body)" }],
        sm: ["var(--fs-sm)", { lineHeight: "var(--lh-sm)" }],
        xs: ["var(--fs-xs)", { lineHeight: "var(--lh-xs)" }],
        micro: ["var(--fs-micro)", { lineHeight: "var(--lh-micro)" }],
        nano: ["var(--fs-nano)", { lineHeight: "var(--lh-nano)" }],
        /* Heading sizes mapped onto the same scale (legacy classes keep working) */
        lg: ["var(--fs-h4)", { lineHeight: "var(--lh-h4)" }],
        xl: ["var(--fs-h3)", { lineHeight: "var(--lh-h3)" }],
        "2xl": ["var(--fs-h2)", { lineHeight: "var(--lh-h2)" }],
        "3xl": ["1.875rem", { lineHeight: "var(--lh-h1)" }],
        "4xl": ["2.25rem", { lineHeight: "1.2" }],
        "5xl": ["3rem", { lineHeight: "1.15" }],
        "6xl": ["3.75rem", { lineHeight: "1.1" }],
      },
      fontWeight: {
        regular: "400",
        medium: "500",
        semibold: "600",
        bold: "700",
        /* Deprecated aliases — kept so legacy classes render true 700 */
        extrabold: "700",
        black: "700",
      },
      borderRadius: {
        xl: "1rem",       // 16px — large cards
        lg: "0.75rem",    // 12px — standard cards (reference uses 10–16px)
      },
      colors: {
        /* ===== Official HSAAI palette (index.html) ===== */
        "hsa-yellow": "#EFB323",      // Primary Gold
        "hsa-gold": "#A67C00",
        "hsa-gold-dark": "#8A6500",        // Dark Gold (hover / accent text)
        "hsa-soft": "#FDF4E3",        // Soft Gold background
        "hsa-black": "#111111",       // Main Black
        "hsa-black-soft": "#151515",  // Dark Black (footer / dark surfaces)
        "hsa-bg": "#FAFAFA",          // Main background
        "hsa-white": "#FFFFFF",
        "hsa-border": "#E7E5E4",      // Unified hairline border
        "hsa-secondary": "#64748B",   // Secondary text
        /* ===== Semantic aliases kept for compatibility ===== */
        "enterprise-slate": "#151515",
        "hsa-surface": "#FFFFFF",
        "hsa-muted": "#64748B",
        /* Chart palette */
        "chart-gold": "#EFB323",
        "chart-gold-dark": "#A67C00",
        "chart-ink": "#111111",
      },
      boxShadow: {
        // Subtle enterprise elevation (reference: card hover 0 8px 25px rgba(0,0,0,.12))
        "hsa-glow": "0 8px 25px rgba(17, 17, 17, 0.10)",
        "hsa-card": "0 1px 2px rgba(17, 17, 17, 0.04)",
        "hsa-card-hover": "0 8px 25px rgba(17, 17, 17, 0.10)",
        "hsa-gold": "0 6px 20px rgba(244, 196, 48, 0.28)",
      },
    },
  },
  plugins: [],
};
export default config;
