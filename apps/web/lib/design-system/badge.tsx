/**
 * HSAAI Design System — Badge Component
 * ═══════════════════════════════════════════════════════════════════════
 *
 * Unified badge/status indicator system.
 * Replaces all ad-hoc emerald/amber/rose/blue/slate badge usage.
 *
 * Variants: success | warning | danger | info | neutral | brand
 * Sizes:    sm | md
 *
 * ═══════════════════════════════════════════════════════════════════════
 */
import { forwardRef } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  [
    "inline-flex items-center gap-1.5",
    "font-semibold rounded-full",
    "border",
  ],
  {
    variants: {
      variant: {
        success: "bg-success-soft text-success border-success-border",
        warning: "bg-warning-soft text-warning border-warning-border",
        danger: "bg-danger-soft text-danger border-danger-border",
        info: "bg-info-soft text-info border-info-border",
        neutral: "bg-surface-alt text-text-secondary border-border",
        brand: "bg-primary-gold-soft text-primary-gold-active border-primary-gold-border",
      },
      size: {
        sm: "px-2 py-0.5 text-label",
        md: "px-2.5 py-1 text-caption",
      },
    },
    defaultVariants: {
      variant: "neutral",
      size: "sm",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {
  dot?: boolean;
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant, size, dot, children, ...props }, ref) => (
    <span
      ref={ref}
      className={cn(badgeVariants({ variant, size }), className)}
      {...props}
    >
      {dot && (
        <span
          className="h-1.5 w-1.5 rounded-full bg-current"
          aria-hidden="true"
        />
      )}
      {children}
    </span>
  )
);
Badge.displayName = "Badge";

export { badgeVariants };
