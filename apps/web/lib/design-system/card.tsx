/**
 * HSAAI Design System — Card Component
 * ═══════════════════════════════════════════════════════════════════════
 *
 * Unified card system with variants.
 * Replaces all 8+ ad-hoc card styles across the platform.
 *
 * Variants:
 *   default  — light surface, subtle border, shadow-sm
 *   elevated — white surface, shadow-md, hover lifts to shadow-lg
 *   brand    — dark brand surface (primary-black) with gold accents
 *   outline  — transparent background, border only
 *   metric   — compact card for KPI/metric display
 *   hero     — large card for page headers (radius-3xl, padding-8)
 *
 * Sub-components: Card.Header, Card.Body, Card.Footer, Card.Title, Card.Description
 *
 * ═══════════════════════════════════════════════════════════════════════
 */
import { forwardRef } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const cardVariants = cva(
  ["transition-all duration-normal ease-out"],
  {
    variants: {
      variant: {
        default: [
          "rounded-2xl border border-border bg-surface shadow-sm",
        ],
        elevated: [
          "rounded-2xl border border-border bg-surface shadow-md",
          "hover:shadow-lg hover:border-border-strong",
        ],
        brand: [
          "rounded-3xl border border-primary-gold/20 bg-primary-black text-white shadow-glow",
        ],
        outline: [
          "rounded-2xl border border-border bg-transparent",
        ],
        metric: [
          "rounded-xl border border-border bg-surface p-4 shadow-sm",
        ],
        hero: [
          "rounded-3xl border border-border bg-surface p-8 shadow-sm",
        ],
        glass: [
          "rounded-2xl border border-white/10 bg-white/5 backdrop-blur-md shadow-lg",
        ],
      },
      padding: {
        none: "",
        sm: "p-3",
        md: "p-5",
        lg: "p-6",
        xl: "p-8",
      },
    },
    defaultVariants: {
      variant: "default",
      padding: "md",
    },
  }
);

export interface CardProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof cardVariants> {}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, variant, padding, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(cardVariants({ variant, padding }), className)}
      {...props}
    />
  )
);
Card.displayName = "Card";

// ─── Card Sub-components ────────────────────────────────────────────────

export const CardHeader = forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex flex-col gap-1.5 pb-4", className)}
    {...props}
  />
));
CardHeader.displayName = "CardHeader";

export const CardTitle = forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn("text-h4 font-bold text-text-primary leading-tight", className)}
    {...props}
  />
));
CardTitle.displayName = "CardTitle";

export const CardDescription = forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("text-body-sm text-text-secondary leading-relaxed", className)}
    {...props}
  />
));
CardDescription.displayName = "CardDescription";

export const CardBody = forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("flex-1", className)} {...props} />
));
CardBody.displayName = "CardBody";

export const CardFooter = forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex items-center gap-3 pt-4", className)}
    {...props}
  />
));
CardFooter.displayName = "CardFooter";

export { cardVariants };
