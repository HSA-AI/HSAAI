import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * HSAAI Card — Design System primitive (reference index.html .card)
 * White surface · 1px #E7E5E4 border · 12–16px radius · very light shadow
 * hoverable → slight lift + soft shadow (reference hover behavior)
 */
export function Card({
  className,
  hoverable = false,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { hoverable?: boolean }) {
  return (
    <div
      className={cn(
        "rounded-xl border border-hsa-border bg-white p-5 shadow-hsa-card transition-all duration-200 dark:border-zinc-700 dark:bg-hsa-black-soft dark:text-white",
        hoverable && "hover:-translate-y-1 hover:shadow-hsa-card-hover",
        className,
      )}
      {...props}
    />
  );
}
