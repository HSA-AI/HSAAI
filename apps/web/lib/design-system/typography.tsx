/**
 * HSAAI Design System — Typography Components
 * ═══════════════════════════════════════════════════════════════════════
 *
 * Unified typography system. All text in the platform should use these
 * components or the corresponding Tailwind classes.
 *
 * Hierarchy:
 *   Display (hero pages only)
 *   H1 (page titles)
 *   H2 (section titles)
 *   H3 (subsection titles)
 *   H4 (card titles)
 *   Body (paragraphs)
 *   BodySmall (secondary text)
 *   Caption (metadata, timestamps)
 *   Label (form labels, tags)
 *   Code (inline code)
 *   Eyebrow (overline above titles)
 *
 * ═══════════════════════════════════════════════════════════════════════
 */
import { forwardRef } from "react";
import { cn } from "@/lib/utils";

type ElementType = "h1" | "h2" | "h3" | "h4" | "h5" | "h6" | "p" | "span" | "div" | "label" | "code";

interface TypographyProps extends React.HTMLAttributes<HTMLElement> {
  as?: ElementType;
}

const createComponent = (defaultTag: ElementType, className: string) => {
  const Comp = forwardRef<HTMLElement, TypographyProps>(
    ({ as, className: cn_, ...props }, ref) => {
      const Tag = (as || defaultTag) as React.ElementType;
      return <Tag ref={ref} className={cn(className, cn_)} {...props} />;
    }
  );
  Comp.displayName = defaultTag.toUpperCase();
  return Comp;
};

// ─── Display (hero/landing pages) ───────────────────────────────────────
export const Display = createComponent(
  "h1",
  "font-display font-black text-display leading-tight tracking-tighter text-text-primary"
);

export const DisplaySm = createComponent(
  "h2",
  "font-display font-black text-display-sm leading-tight tracking-tight text-text-primary"
);

// ─── Headings ───────────────────────────────────────────────────────────
export const H1 = createComponent(
  "h1",
  "font-display font-bold text-h1 leading-tight tracking-tight text-text-primary"
);

export const H2 = createComponent(
  "h2",
  "font-display font-bold text-h2 leading-snug tracking-tight text-text-primary"
);

export const H3 = createComponent(
  "h3",
  "font-display font-semibold text-h3 leading-normal text-text-primary"
);

export const H4 = createComponent(
  "h4",
  "font-display font-semibold text-h4 leading-snug text-text-primary"
);

// ─── Body ───────────────────────────────────────────────────────────────
export const Body = createComponent(
  "p",
  "font-sans text-body leading-relaxed text-text-secondary"
);

export const BodyLarge = createComponent(
  "p",
  "font-sans text-body-lg leading-relaxed text-text-secondary"
);

export const BodySmall = createComponent(
  "p",
  "font-sans text-body-sm leading-relaxed text-text-secondary"
);

// ─── Utility text ───────────────────────────────────────────────────────
export const Caption = createComponent(
  "span",
  "font-sans text-caption leading-normal text-text-muted"
);

export const Label = createComponent(
  "label",
  "font-sans text-label font-semibold leading-normal text-text-secondary"
);

export const Code = createComponent(
  "code",
  "font-mono text-code bg-surface-alt text-text-primary px-1.5 py-0.5 rounded-sm border border-border"
);

export const Eyebrow = createComponent(
  "span",
  "font-sans text-overline font-semibold uppercase tracking-widest text-primary-gold"
);

// ─── Page Title (standardized page header text) ─────────────────────────
export const PageTitle = createComponent(
  "h1",
  "font-display font-bold text-h1 leading-tight tracking-tight text-text-primary text-balance"
);

export const SectionTitle = createComponent(
  "h2",
  "font-display font-bold text-h2 leading-snug tracking-tight text-text-primary"
);

export const CardTitle = createComponent(
  "h3",
  "font-display font-semibold text-h4 leading-snug text-text-primary"
);
