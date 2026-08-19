/**
 * HSAAI Design System — PageHero Component
 * ═══════════════════════════════════════════════════════════════════════
 *
 * Standardized page header for ALL authenticated pages.
 * Replaces the 4+ hero patterns currently in use.
 *
 * Layout:
 *   ┌─────────────────────────────────────────────┐
 *   │  EYEBROW (uppercase, gold)                  │
 *   │  Page Title (H1, bold)                      │
 *   │  Description (Body, secondary)              │
 *   │                          [Action Buttons]   │
 *   └─────────────────────────────────────────────┘
 *
 * ═══════════════════════════════════════════════════════════════════════
 */
import { forwardRef } from "react";
import { cn } from "@/lib/utils";

export interface PageHeroProps extends React.HTMLAttributes<HTMLDivElement> {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: React.ReactNode;
  variant?: "default" | "brand" | "minimal";
}

export const PageHero = forwardRef<HTMLDivElement, PageHeroProps>(
  ({ className, eyebrow, title, description, actions, variant = "default", ...props }, ref) => {
    const variantClasses = {
      default: "bg-surface border-border shadow-sm",
      brand: "bg-primary-black border-primary-gold/20 shadow-glow text-white",
      minimal: "bg-transparent border-transparent shadow-none",
    };

    return (
      <div
        ref={ref}
        className={cn(
          "rounded-3xl border p-6 sm:p-8 mb-6",
          "flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between",
          variantClasses[variant],
          className
        )}
        {...props}
      >
        <div className="flex flex-col gap-2 min-w-0 flex-1">
          {eyebrow && (
            <span className="font-sans text-overline font-semibold uppercase tracking-widest text-primary-gold">
              {eyebrow}
            </span>
          )}
          <h1
            className={cn(
              "font-display font-bold text-h1 leading-tight tracking-tight text-balance",
              variant === "brand" ? "text-white" : "text-text-primary"
            )}
          >
            {title}
          </h1>
          {description && (
            <p
              className={cn(
                "font-sans text-body-lg leading-relaxed max-w-2xl",
                variant === "brand" ? "text-neutral-300" : "text-text-secondary"
              )}
            >
              {description}
            </p>
          )}
        </div>
        {actions && (
          <div className="flex items-center gap-3 flex-shrink-0">
            {actions}
          </div>
        )}
      </div>
    );
  }
);

PageHero.displayName = "PageHero";
