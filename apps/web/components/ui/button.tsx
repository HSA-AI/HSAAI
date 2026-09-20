import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * HSAAI Button — Design System primitive
 * variant="primary"   → Gold #F4C430, hover Dark Gold #A67C00 (reference CTA)
 * variant="secondary" → White card button with unified border
 * variant="ghost"     → Borderless, hover Soft Gold
 */
type Variant = "primary" | "secondary" | "ghost" | "ai";

const variants: Record<Variant, string> = {
  primary: "bg-hsa-yellow text-hsa-black hover:bg-hsa-gold-dark hover:text-white shadow-hsa-gold/0 hover:shadow-hsa-gold",
  secondary: "border border-hsa-border bg-white text-hsa-black hover:border-hsa-gold/50 hover:bg-hsa-soft",
  ghost: "bg-transparent text-hsa-secondary hover:bg-hsa-soft hover:text-hsa-black",
  ai: "bg-hsa-yellow text-hsa-black border border-hsa-gold hover:bg-hsa-gold-dark hover:text-white",
};

export function Button({
  className,
  variant = "primary",
  type = "button",
  loading = false,
  disabled,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition-all",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-hsa-gold/60 focus-visible:ring-offset-2",
        "disabled:cursor-not-allowed disabled:opacity-50",
        variants[variant],
        className,
      )}
      {...props}
    >
      {loading && <span aria-hidden="true" className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />}
      {children}
    </button>
  );
}
