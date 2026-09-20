import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * HSAAI Badge — Design System primitive (reference index.html .badge)
 * tone="gold" (default) → Soft Gold bg + Dark Gold text
 */
type Tone = "gold" | "neutral" | "ok" | "warn" | "error" | "info";

const tones: Record<Tone, string> = {
  gold: "bg-hsa-soft text-hsa-gold border border-hsa-yellow/30",
  neutral: "bg-white text-hsa-secondary border border-hsa-border",
  ok: "bg-emerald-50 text-emerald-700 border border-emerald-200",
  warn: "bg-amber-50 text-amber-700 border border-amber-200",
  error: "bg-red-50 text-red-700 border border-red-200",
  info: "bg-hsa-soft text-hsa-gold border border-hsa-yellow/30",
};

export function Badge({
  className,
  tone = "gold",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-micro font-semibold leading-none",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}
